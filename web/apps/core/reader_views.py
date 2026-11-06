from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .lifecycle import issue_account_invitation, record_security_event
from .models import AccountSecurityEvent, ReaderProfile
from .reader_forms import ReaderInvitationForm, ReaderProfileForm
from .views import staff_mfa_required


@staff_mfa_required
def reader_list(request):
    if not request.user.has_perm("core.view_readerprofile"):
        return HttpResponseForbidden("Bạn không được cấp quyền xem hồ sơ độc giả.")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    profiles = ReaderProfile.objects.select_related("user").order_by("reader_number", "pk")
    if query:
        profiles = profiles.filter(Q(reader_number__icontains=query) | Q(user__username__icontains=query)
                                   | Q(user__email__icontains=query) | Q(user__first_name__icontains=query)
                                   | Q(user__last_name__icontains=query))
    if status in ReaderProfile.Status.values:
        profiles = profiles.filter(status=status)
    else:
        status = ""
    return render(request, "core/reader_list.html", {
        "page_obj": Paginator(profiles, 25).get_page(request.GET.get("page")),
        "query": query, "selected_status": status, "statuses": ReaderProfile.Status.choices,
    })


@staff_mfa_required
def reader_add(request):
    if not (request.user.has_perm("core.add_readerprofile") and (request.user.has_perm("core.issue_account_invitation") or request.user.has_perm("core.invite_reader"))):
        return HttpResponseForbidden("Bạn không được cấp quyền tạo độc giả và gửi lời mời.")
    form = ReaderInvitationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            issue_account_invitation(actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionError) as exc:
            form.add_error(None, str(exc))
        except IntegrityError:
            form.add_error(None, "Tên đăng nhập hoặc mã bạn đọc vừa được sử dụng. Hãy kiểm tra lại.")
        else:
            messages.success(request, "Đã tạo độc giả chờ kích hoạt và gửi lời mời đặt mật khẩu. Thẻ cần được xác minh riêng.")
            return redirect("reader_list")
    return render(request, "core/reader_form.html", {"form": form})


@staff_mfa_required
def reader_edit(request, reader_id):
    if not request.user.has_perm("core.change_readerprofile"):
        return HttpResponseForbidden("Bạn không được cấp quyền sửa hồ sơ độc giả.")
    with transaction.atomic():
        profiles = ReaderProfile.objects.all()
        if request.method == "POST":
            profiles = profiles.select_for_update()
        profile = get_object_or_404(profiles, pk=reader_id)
        fields = ("reader_number", "reader_type", "valid_from", "valid_until", "status")
        before = {name: str(getattr(profile, name)) for name in fields}
        form = ReaderProfileForm(request.POST if request.method == "POST" else None, instance=profile,
                                 can_suspend=request.user.has_perm("core.suspend_reader"),
                                 can_reactivate=request.user.has_perm("library.manage_reader_restrictions"))
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    profile = form.save()
                    after = {name: str(getattr(profile, name)) for name in fields}
                    record_security_event(profile.user, AccountSecurityEvent.Kind.MEMBERSHIP_CHANGED,
                                          request.user, {"before": before, "after": after},
                                          reason=form.cleaned_data["reason"])
            except IntegrityError:
                form.add_error("reader_number", "Mã bạn đọc vừa được sử dụng. Hãy chọn mã khác.")
            else:
                messages.success(request, "Đã cập nhật hồ sơ độc giả.")
                return redirect("reader_list")
    return render(request, "core/reader_form.html", {"form": form, "profile": profile})
