from calendar import monthrange
from datetime import datetime, time, timedelta
from urllib.parse import urlencode
from uuid import UUID, uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.library.services import circulation_write
from .lifecycle import record_security_event
from .models import AccountSecurityEvent, MembershipPurchase, MembershipSandboxPayment, ReaderProfile
from .views import staff_mfa_required


PLANS = {
    "day": ("1 ngày", 7000, 1, 0),
    "week": ("1 tuần", 30000, 7, 0),
    "month": ("1 tháng", 90000, 0, 1),
    "half_year": ("6 tháng", 400000, 0, 6),
    "year": ("1 năm", 600000, 0, 12),
}


PLAN_DESCRIPTIONS = {
    "day": "Dành cho một lần ghé thư viện hoặc nhu cầu mượn ngắn hạn.",
    "week": "Phù hợp khi bạn cần sử dụng thư viện trong một tuần.",
    "month": "Dành cho nhu cầu đọc và tra cứu thường xuyên trong tháng.",
    "half_year": "Phù hợp với một học kỳ hoặc một đợt nghiên cứu dài.",
    "year": "Dành cho người sử dụng thư viện thường xuyên quanh năm.",
}


class GuestProfileForm(forms.ModelForm):
    full_name = forms.CharField(label="Họ và tên", max_length=150)

    class Meta:
        model = ReaderProfile
        fields = ("full_name", "reader_type", "address", "citizen_id", "citizen_id_issued_on", "contact_email", "phone_number")
        widgets = {"citizen_id_issued_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

    def clean_citizen_id_issued_on(self):
        issued = self.cleaned_data["citizen_id_issued_on"]
        if issued > timezone.localdate():
            raise ValidationError("Ngày cấp không được ở tương lai.")
        return issued


def guest_profile(request):
    if request.user.is_authenticated:
        return None
    key = request.session.get("guest_reader")
    return ReaderProfile.objects.select_related("user").filter(pk=key, is_guest=True).first() if key else None


@circulation_write
def create_guest_purchase(form):
    identifier = form.cleaned_data["citizen_id"]
    if ReaderProfile.objects.filter(citizen_id=identifier).exists():
        raise ValidationError("Hãy đăng nhập hoặc liên hệ quầy để tiếp tục với hồ sơ hiện có.")
    code = uuid4().hex[:16]
    user = get_user_model().objects.create_user(username=f"guest_{code}", first_name=form.cleaned_data["full_name"])
    reader = form.save(commit=False)
    reader.user = user
    reader.reader_number = f"G-{code.upper()}"
    reader.is_guest = reader.requires_paid_plan = True
    reader.valid_from = reader.valid_until = timezone.localdate()
    reader.save()
    MembershipPurchase.objects.create(reader=reader, plan="day", amount=PLANS["day"][1])
    return reader


@circulation_write
def request_purchase(reader, plan):
    reader = ReaderProfile.objects.select_for_update().get(pk=reader.pk)
    if plan not in PLANS or (reader.is_guest and plan != "day"):
        raise ValidationError("Gói thẻ không hợp lệ.")
    pending = reader.membership_purchases.filter(paid_at__isnull=True).first()
    if pending:
        if pending.plan != plan:
            raise ValidationError("Bạn đang có một yêu cầu chờ thanh toán. Liên hệ quầy để đổi gói.")
        return pending
    return MembershipPurchase.objects.create(reader=reader, plan=plan, amount=PLANS[plan][1])


@never_cache
def membership_plans(request):
    guest = not request.user.is_authenticated
    reader = guest_profile(request) if guest else getattr(request.user, "reader_profile", None)
    can_purchase = guest or bool(reader and request.user.groups.filter(name="reader").exists())
    if not can_purchase and request.method == "POST":
        return HttpResponseForbidden()
    form = GuestProfileForm(request.POST if request.method == "POST" else None) if guest and not reader else None
    if request.method == "POST":
        try:
            if reader:
                request_purchase(reader, request.POST.get("plan"))
            elif form.is_valid():
                if request.POST.get("plan") != "day":
                    raise ValidationError("Khách chỉ được chọn gói 1 ngày.")
                reader = create_guest_purchase(form)
                request.session.cycle_key()
                request.session["guest_reader"] = reader.pk
            if reader:
                messages.success(request, "Đã ghi nhận yêu cầu. Đọc mã bạn đọc tại quầy để thanh toán.")
                return redirect("membership_plans")
        except ValidationError as exc:
            if form is not None:
                form.add_error(None, exc)
            else:
                messages.error(request, exc.messages[0])
    from apps.library.payments import vnpay_keys
    pending = reader.membership_purchases.filter(paid_at__isnull=True).first() if reader and can_purchase else None
    return render(request, "core/membership_plans.html", {
        "plans": [
            {"key": key, "label": label, "price": f"{amount:,}".replace(",", "."), "description": PLAN_DESCRIPTIONS[key]}
            for key, (label, amount, _, _) in PLANS.items() if not guest or key == "day"
        ],
        "guest": guest, "guest_form": form, "reader": reader if can_purchase else None,
        "can_purchase": can_purchase,
        "pending": pending,
        "sandbox_enabled": all(vnpay_keys()),
        "sandbox_payment": pending.sandbox_payments.order_by("-successful", "-created_at").first() if pending else None,
        "reservations": reader.reservations.select_related("book", "pickup_branch").defer("book__cover_image").order_by("-pk")[:20] if guest and reader else (),
    })


@never_cache
@require_POST
def membership_sandbox_start(request):
    from apps.library.payments import vnpay_keys, vnpay_signature

    merchant, secret = vnpay_keys()
    if not merchant or not secret:
        messages.error(request, "Chưa cấu hình VNPAY Sandbox.")
        return redirect("membership_plans")
    reader = guest_profile(request)
    if request.user.is_authenticated and request.user.groups.filter(name="reader").exists():
        reader = getattr(request.user, "reader_profile", None)
    if reader is None:
        return HttpResponseForbidden()
    with transaction.atomic():
        purchase = MembershipPurchase.objects.select_for_update().filter(reader=reader, paid_at__isnull=True).first()
        if purchase is None:
            messages.error(request, "Hãy chọn gói trước khi mở thanh toán thử.")
            return redirect("membership_plans")
        if purchase.sandbox_payments.filter(successful=True).exists():
            messages.info(request, "Gói này đã có giao dịch Sandbox thành công.")
            return redirect("membership_plans")
        now = timezone.now()
        payment = purchase.sandbox_payments.filter(completed_at__isnull=True, expires_at__gt=now).order_by("-created_at").first()
        if payment is None:
            payment = MembershipSandboxPayment.objects.create(purchase=purchase, expires_at=now + timedelta(minutes=15))
    reference = "TV" + payment.pk.hex
    payload = {
        "vnp_Version": "2.1.0", "vnp_Command": "pay", "vnp_TmnCode": merchant,
        "vnp_Amount": str(purchase.amount * 100), "vnp_CurrCode": "VND",
        "vnp_TxnRef": reference, "vnp_OrderInfo": "Library Hub MEMBERSHIP SANDBOX " + reference,
        "vnp_OrderType": "other", "vnp_Locale": "vn",
        "vnp_ReturnUrl": request.build_absolute_uri(reverse("membership_plans")),
        "vnp_IpAddr": request.META.get("REMOTE_ADDR", "127.0.0.1"),
        "vnp_CreateDate": timezone.localtime(payment.created_at).strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": timezone.localtime(payment.expires_at).strftime("%Y%m%d%H%M%S"),
    }
    payload["vnp_SecureHash"] = vnpay_signature(payload, secret)
    return redirect("https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?" + urlencode(sorted(payload.items())))


def confirm_membership_sandbox(data):
    """Record only provider-authenticated sandbox results, without posting a real receipt."""
    reference = data.get("vnp_TxnRef", "")
    if len(reference) != 34 or data.get("vnp_OrderInfo") != "Library Hub MEMBERSHIP SANDBOX " + reference:
        return JsonResponse({"RspCode": "01", "Message": "Invalid order"})
    try:
        with transaction.atomic():
            payment = MembershipSandboxPayment.objects.select_for_update().select_related("purchase").get(pk=UUID(reference[2:]))
            if data.get("vnp_Amount") != str(payment.purchase.amount * 100):
                return JsonResponse({"RspCode": "04", "Message": "Invalid amount"})
            if payment.completed_at:
                return JsonResponse({"RspCode": "02", "Message": "Already confirmed"})
            number = data.get("vnp_TransactionNo", "")
            successful = data.get("vnp_ResponseCode") == "00" and data.get("vnp_TransactionStatus") == "00"
            if successful and (not number.isascii() or not number.isdecimal() or len(number) > 30 or int(number) == 0):
                return JsonResponse({"RspCode": "99", "Message": "Invalid transaction number"})
            payment.provider_transaction = number if successful else None
            payment.successful = successful
            payment.result_code = data.get("vnp_ResponseCode", "")[:10]
            payment.completed_at = timezone.now()
            payment.save(update_fields=["provider_transaction", "successful", "result_code", "completed_at"])
    except (MembershipSandboxPayment.DoesNotExist, ValueError):
        return JsonResponse({"RspCode": "01", "Message": "Order not found"})
    except IntegrityError:
        return JsonResponse({"RspCode": "02", "Message": "Already confirmed"})
    return JsonResponse({"RspCode": "00", "Message": "Confirm Success"})


@circulation_write
def activate_purchase(purchase_id, actor):
    purchase = get_object_or_404(MembershipPurchase.objects.select_for_update(), pk=purchase_id)
    if purchase.paid_at:
        return purchase
    reader = ReaderProfile.objects.select_for_update().get(pk=purchase.reader_id)
    if not reader.user.is_active or reader.status == ReaderProfile.Status.SUSPENDED:
        raise ValidationError("Hồ sơ đang bị khóa. Hãy xử lý trước khi kích hoạt gói.")
    if reader.is_guest and purchase.plan != "day":
        raise ValidationError("Khách chỉ được kích hoạt gói 1 ngày.")
    if not reader.is_guest and not reader.membership_verified:
        raise ValidationError("Hãy xác minh hồ sơ độc giả trước khi kích hoạt.")
    now = timezone.now()
    if reader.membership_expires_at:
        start = max(now, reader.membership_expires_at)
    elif reader.card_is_current:
        start = timezone.make_aware(datetime.combine(reader.valid_until + timedelta(days=1), time.min))
    else:
        start = now
    _, _, days, months = PLANS[purchase.plan]
    local = timezone.localtime(start)
    if months:
        year, month = divmod(local.year * 12 + local.month - 1 + months, 12)
        expiry = local.replace(year=year, month=month + 1, day=min(local.day, monthrange(year, month + 1)[1]))
    else:
        expiry = start + timedelta(days=days)
    reader.membership_expires_at = expiry
    reader.valid_from = timezone.localdate(now)
    reader.valid_until = timezone.localdate(expiry)
    reader.status = ReaderProfile.Status.ACTIVE
    if reader.is_guest:
        reader.membership_verified = True
        reader.membership_verified_at = now
        reader.membership_verified_by = actor
        reader.verification_method = "staff_review"
    reader.save(update_fields=["membership_expires_at", "valid_from", "valid_until", "status",
                               "membership_verified", "membership_verified_at", "membership_verified_by", "verification_method"])
    purchase.paid_at, purchase.paid_by, purchase.expires_at = now, actor, expiry
    purchase.save(update_fields=["paid_at", "paid_by", "expires_at"])
    record_security_event(reader.user, AccountSecurityEvent.Kind.MEMBERSHIP_CHANGED, actor,
                          {"purchase_id": purchase.pk, "plan": purchase.plan, "amount": purchase.amount},
                          reason="Đã xác nhận thu tiền gói thẻ tại quầy")
    return purchase


@never_cache
@staff_mfa_required
def membership_queue(request):
    if not request.user.has_perms(["library.collect_finepayment", "core.view_readerprofile"]):
        return HttpResponseForbidden()
    rows = MembershipPurchase.objects.select_related("reader__user").order_by("-pk")
    query = request.GET.get("q", "").strip()[:32]
    if query:
        rows = rows.filter(reader__reader_number__icontains=query)
    if request.GET.get("paid") != "1":
        rows = rows.filter(paid_at__isnull=True)
    return render(request, "core/membership_queue.html", {
        "purchases": Paginator(rows, 20).get_page(request.GET.get("page")), "query": query,
    })


@never_cache
@staff_mfa_required
@require_POST
def membership_confirm(request, purchase_id):
    if not request.user.has_perms(["library.collect_finepayment", "core.view_readerprofile"]):
        return HttpResponseForbidden()
    try:
        purchase = activate_purchase(purchase_id, request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, f"Đã ghi nhận gói thẻ. Biên nhận TV-{purchase.pk}.")
    return redirect("membership_queue")
