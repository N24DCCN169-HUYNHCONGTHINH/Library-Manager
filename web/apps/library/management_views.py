from uuid import uuid4, uuid5, NAMESPACE_URL
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction, IntegrityError
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from apps.core.views import staff_mfa_required
from apps.core.models import AccountSecurityEvent
from apps.core.lifecycle import record_security_event
from .models import Book, BookCopy, CirculationPolicy, Fine, FinePayment, FineWaiverRequest, DamageCase, Loan, Reservation
from .services import CirculationError, circulation_write, record_fine_payment, approve_damage_case, allocate_next_reservation

class CopyForm(forms.ModelForm):
    class Meta:
        model=BookCopy
        fields=("barcode","branch","shelf_location","home_loan_override","condition_note","acquired_at","is_active")
        labels={"barcode":"Mã vạch bản sách","branch":"Cơ sở","shelf_location":"Vị trí kệ","home_loan_override":"Cho mượn về nhà (để trống: theo đầu sách)","condition_note":"Ghi chú tình trạng","acquired_at":"Ngày nhập kho","is_active":"Đang sử dụng"}
        widgets={"acquired_at":forms.DateInput(format="%Y-%m-%d",attrs={"type":"date"})}
    def clean(self):
        data=super().clean()
        if self.instance.pk and self.instance.status not in {"available","retired","inventory_review"}:
            if set(self.changed_data)&{"barcode","branch","home_loan_override","is_active"}:
                raise forms.ValidationError("Bản sách đang có giao dịch. Chỉ sửa kệ hoặc ghi chú; trả/giải quyết giao dịch trước khi đổi mã hoặc cơ sở.")
        return data

@never_cache
@staff_mfa_required
@permission_required("library.view_bookcopy",raise_exception=True)
def copies(request,book_id,copy_id=None):
    book=get_object_or_404(Book.objects.defer("cover_image"),pk=book_id)
    edit=copy_id is not None
    permission="library.change_bookcopy" if edit else "library.add_bookcopy"
    form=None
    if request.user.has_perm(permission):
        with transaction.atomic():
            obj=get_object_or_404(BookCopy.objects.select_for_update(),pk=copy_id,book=book) if edit else BookCopy(book=book,created_by=request.user,barcode="B-"+uuid4().hex[:8].upper())
            form=CopyForm(request.POST if request.method=="POST" else None,instance=obj)
            if request.method=="POST" and form.is_valid():
                try:
                    with transaction.atomic():
                        item=form.save()
                        record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,{"copy":item.pk,"book":book.pk},reason="Cập nhật bản sách" if edit else "Bổ sung bản sách")
                except IntegrityError: form.add_error(None,"Mã vạch vừa được sử dụng. Hãy chọn mã khác.")
                else:
                    messages.success(request,"Đã lưu bản sách.");return redirect("library:copies",book_id=book.pk)
    elif request.method=="POST" or edit: return HttpResponseForbidden()
    return render(request,"library/copies.html",{"book":book,"form":form,"editing":edit,"copies":book.copies.select_related("branch").all()})

@circulation_write
def change_copy_lifecycle(book_id, copy_id, actor, action, reason):
    copy = get_object_or_404(BookCopy.objects.select_for_update(), pk=copy_id, book_id=book_id)
    Book.objects.select_for_update().only("id").get(pk=book_id)
    if not reason or len(reason) > 300:
        raise CirculationError("Nhập lý do từ 1 đến 300 ký tự.")
    if action not in {"found", "remove", "restore"}:
        raise CirculationError("Thao tác không hợp lệ.")
    if (copy.status in {BookCopy.Status.ON_LOAN, BookCopy.Status.ON_HOLD, BookCopy.Status.RETURN_PENDING}
        or Loan.objects.filter(copy=copy, status=Loan.Status.OPEN).exists()
        or Reservation.objects.filter(copy=copy, status=Reservation.Status.READY).exists()):
        raise CirculationError("Bản sách đang có giao dịch mượn hoặc giữ chỗ. Hãy xử lý giao dịch trước.")
    previous = {"status": copy.status, "is_active": copy.is_active}
    if action == "found":
        if not copy.is_active or copy.status != BookCopy.Status.LOST:
            raise CirculationError("Chỉ ghi nhận tìm lại với bản đang sử dụng ở trạng thái Đã mất.")
        copy.status = BookCopy.Status.AVAILABLE
        copy.condition_note = reason
        copy.save(update_fields=["status", "condition_note"])
    else:
        active = action == "restore"
        if copy.is_active == active:
            return copy
        copy.is_active = active
        copy.save(update_fields=["is_active"])
    if copy.is_active and copy.status == BookCopy.Status.AVAILABLE:
        allocate_next_reservation(copy, actor)
        copy.refresh_from_db(fields=["status"])
    record_security_event(
        actor, AccountSecurityEvent.Kind.SYSTEM_OPERATION, actor,
        {"copy": copy.pk, "book": book_id, "action": action, "before": previous,
         "after": {"status": copy.status, "is_active": copy.is_active}}, reason=reason,
    )
    return copy


@never_cache
@staff_mfa_required
@permission_required(("library.view_bookcopy", "library.manage_bookcopy"), raise_exception=True)
@require_POST
def copy_lifecycle(request, book_id, copy_id):
    action = request.POST.get("action", "")
    try:
        copy = change_copy_lifecycle(book_id, copy_id, request.user, action, request.POST.get("reason", "").strip())
    except CirculationError as exc:
        messages.error(request, str(exc))
    else:
        labels = {"found": "Đã ghi nhận tìm lại", "remove": "Đã xóa khỏi kho lưu thông", "restore": "Đã khôi phục"}
        messages.success(request, f"{labels[action]}: {copy.barcode}.")
    return redirect("library:copies", book_id=book_id)


@never_cache
@staff_mfa_required
@permission_required("library.delete_book",raise_exception=True)
def retire_book(request,book_id):
    book=get_object_or_404(Book.objects.defer("cover_image"),pk=book_id)
    if request.method=="POST":
        reason=request.POST.get("reason","").strip()
        if not reason: messages.error(request,"Cần ghi lý do ngừng sử dụng.")
        else:
            with transaction.atomic():
                book=Book.objects.select_for_update().get(pk=book.pk);book.is_active=False;book.updated_by=request.user;book.save(update_fields=["is_active","updated_by","updated_at"])
                record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,{"book":book.pk},reason=reason[:300])
            messages.success(request,"Đã ngừng sử dụng đầu sách; lịch sử mượn trả được giữ lại.");return redirect("library:book_list")
    return render(request,"library/retire_book.html",{"book":book})

@never_cache
def cover_image(request,book_id):
    book=get_object_or_404(Book.objects.only("id","cover_image","is_active","has_cover"),pk=book_id)
    if not book.is_active and not (request.user.is_authenticated and getattr(request.user,"is_verified",lambda:False)() and request.user.has_perm("library.view_book")): raise Http404
    if not book.has_cover: raise Http404
    response=HttpResponse(bytes(book.cover_image),content_type="image/jpeg");response["X-Content-Type-Options"]="nosniff";return response

class PolicyForm(forms.ModelForm):
    reason=forms.CharField(label="Căn cứ thay đổi",max_length=300)
    class Meta:
        model=CirculationPolicy
        fields=("reader_type","material_type","version","effective_from","effective_until","allow_home_loan","max_active_loans","loan_days","max_renewals","renewal_days","overdue_rate_per_day","overdue_fine_cap")
        widgets={k:forms.DateInput(format="%Y-%m-%d",attrs={"type":"date"}) for k in ("effective_from","effective_until")}
        labels={"reader_type":"Loại độc giả","material_type":"Loại tài liệu","version":"Phiên bản","effective_from":"Hiệu lực từ","effective_until":"Hiệu lực đến","allow_home_loan":"Cho mượn về nhà","max_active_loans":"Số sách tối đa","loan_days":"Số ngày mượn","max_renewals":"Số lần gia hạn","renewal_days":"Số ngày mỗi lần gia hạn","overdue_rate_per_day":"Phạt mỗi ngày (VND)","overdue_fine_cap":"Trần tiền phạt (VND)"}
    def clean(self):
        data=super().clean()
        if data.get("loan_days",1)<1 or data.get("renewal_days",1)<1 or data.get("version",1)<1 or data.get("max_active_loans",1)<1:
            raise forms.ValidationError("Phiên bản, số sách và số ngày phải lớn hơn 0.")
        return data

@never_cache
@staff_mfa_required
@permission_required("library.view_circulationpolicy",raise_exception=True)
def policies(request):
    can_add=request.user.has_perm("library.add_circulationpolicy")
    form=PolicyForm(request.POST if request.method=="POST" else None,initial={"version":1,"loan_days":14,"max_active_loans":5,"max_renewals":1,"renewal_days":7,"overdue_rate_per_day":1000,"overdue_fine_cap":30000})
    if request.method=="POST":
        if not can_add: return HttpResponseForbidden()
        if form.is_valid():
            try:
                with transaction.atomic():
                    policy=form.save(commit=False);policy.created_by=request.user;policy.save()
                    record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,{"policy":policy.pk},reason=form.cleaned_data["reason"])
            except IntegrityError: form.add_error(None,"Phiên bản chính sách đã tồn tại.")
            else: messages.success(request,"Đã thêm phiên bản quy định. Lượt mượn cũ giữ chính sách đã chốt.");return redirect("library:policies")
    return render(request,"library/policies.html",{"form":form,"can_add":can_add,"policies":CirculationPolicy.objects.order_by("reader_type","material_type","-version")})

class WaiverForm(forms.Form):
    request_key=forms.UUIDField(initial=uuid4,widget=forms.HiddenInput)
    kind=forms.ChoiceField(label="Loại đề nghị", choices=[("waiver","Miễn/giảm khoản phạt"),("adjustment","Điều chỉnh tăng có căn cứ")])
    fine_id=forms.IntegerField(label="Mã khoản phạt",min_value=1,widget=forms.TextInput(attrs={"data-lookup":"fines"}))
    amount=forms.DecimalField(label="Số tiền đề nghị miễn/giảm",min_value=1,max_digits=10,decimal_places=0)
    reason=forms.CharField(label="Lý do và căn cứ",max_length=500,widget=forms.Textarea)

@circulation_write
def review_waiver(pk,actor,action,reason):
    if not actor.has_perm("library.approve_finepayment"): raise CirculationError("Không có quyền phê duyệt.")
    row=FineWaiverRequest.objects.select_for_update().get(pk=pk)
    if row.state!="pending": return row
    if row.requested_by_id==actor.pk: raise CirculationError("Cần người có quyền khác phê duyệt, không tự duyệt yêu cầu của mình.")
    if action not in {"approve","reject"} or not reason.strip(): raise CirculationError("Cần quyết định và lý do xét duyệt.")
    if action=="approve" and row.kind=="waiver":
        row.payment=record_fine_payment(row.fine_id,row.amount,row.requested_by,kind=FinePayment.Kind.WAIVER,approved_by=actor,reason=row.reason+" | Duyệt: "+reason,idempotency_key=uuid5(NAMESPACE_URL,f"waiver:{pk}"))
    elif action=="approve" and row.kind=="adjustment":
        if not row.requested_by.has_perm("library.collect_finepayment"): raise CirculationError("Người đề nghị không còn quyền nghiệp vụ.")
        fine=Fine.objects.select_for_update().get(pk=row.fine_id)
        row.payment=FinePayment.objects.create(fine=fine,kind=FinePayment.Kind.ADJUSTMENT,amount=row.amount,receipt_number="DC-"+uuid4().hex[:12].upper(),created_by=row.requested_by,approved_by=actor,reason=(row.reason+" | Duyệt: "+reason)[:500],idempotency_key=uuid5(NAMESPACE_URL,f"waiver:{pk}"))
        fine.status=Fine.Status.DUE;fine.save(update_fields=["status"])
    elif action=="approve": raise CirculationError("Loại đề nghị không hợp lệ.")
    record_security_event(actor,AccountSecurityEvent.Kind.SYSTEM_OPERATION,actor,{"fine":row.fine_id,"request":row.pk,"decision":action},reason=reason[:300])
    row.state="approved" if action=="approve" else "rejected";row.reviewed_by=actor;row.review_reason=reason[:500];row.reviewed_at=timezone.now();row.save();return row

@never_cache
@staff_mfa_required
@permission_required("library.collect_finepayment",raise_exception=True)
def waivers(request):
    form=WaiverForm(request.POST if request.method=="POST" and request.POST.get("action")=="request" else None)
    if request.method=="POST":
        try:
            if request.POST.get("action")=="request" and form.is_valid():
                fine=get_object_or_404(Fine,pk=form.cleaned_data["fine_id"])
                if form.cleaned_data["kind"]=="waiver" and form.cleaned_data["amount"]>fine.balance: form.add_error("amount","Vượt số dư còn phải trả.")
                else:
                    row,created=FineWaiverRequest.objects.get_or_create(request_key=form.cleaned_data["request_key"],defaults={"fine":fine,"kind":form.cleaned_data["kind"],"requested_by":request.user,"amount":form.cleaned_data["amount"],"reason":form.cleaned_data["reason"]})
                    if (row.requested_by_id,row.fine_id,row.amount,row.kind,row.reason)!=(request.user.pk,fine.pk,form.cleaned_data["amount"],form.cleaned_data["kind"],form.cleaned_data["reason"]):
                        raise CirculationError("Mã đề nghị đã được sử dụng cho thao tác khác.")
                    messages.success(request,"Đã gửi đề nghị, chưa thay đổi số dư khoản phạt.");return redirect("library:waivers")
            elif request.POST.get("action") in {"approve","reject"}:
                if not request.user.has_perm("library.approve_finepayment"): return HttpResponseForbidden()
                pk=request.POST.get("request_id","")
                if not pk.isdigit(): raise CirculationError("Mã đề nghị không hợp lệ.")
                review_waiver(int(pk),request.user,request.POST["action"],request.POST.get("reason",""))
                messages.success(request,"Đã lưu quyết định.");return redirect("library:waivers")
        except (CirculationError,FineWaiverRequest.DoesNotExist) as exc: messages.error(request,str(exc) or "Không tìm thấy đề nghị.")
    rows=FineWaiverRequest.objects.select_related("fine__loan__copy__book","requested_by","reviewed_by").defer('fine__loan__copy__book__cover_image').order_by("-created_at")[:100]
    return render(request,"library/waivers.html",{"form":form,"requests":rows})
