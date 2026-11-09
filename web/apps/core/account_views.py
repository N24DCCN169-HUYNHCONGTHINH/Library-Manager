from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .account_forms import ProfileForm, AccountEditForm, AppearanceForm, ManagedEmailForm, ROLE_CHOICES, protected_user
from .roles import ALL_ROLES, canonical_roles, can_manage_target
from .models import AppearancePreferences, AccountSecurity, AccountSecurityEvent
from .lifecycle import record_security_event, issue_email_confirmation, issue_account_invitation, revoke_totp_devices, set_account_active
from .lifecycle_forms import AccountInvitationForm
from .views import staff_mfa_required

User = get_user_model()

def own_guard(request):
    from .context_processors import library_roles
    if library_roles(request)["library_roles"].get("librarian") and not request.user.is_verified():
        return redirect("otp_verify")

@never_cache
@login_required
def profile(request):
    denied = own_guard(request)
    if denied: return denied
    form = ProfileForm(request.POST if request.method == "POST" else None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            profile_user = form.save(commit=False)
            profile_user.save(update_fields=["first_name", "last_name"])
            record_security_event(request.user, AccountSecurityEvent.Kind.PROFILE_UPDATED, request.user, reason="Tự sửa hồ sơ")
        messages.success(request, "Đã lưu hồ sơ của bạn.")
        return redirect("profile")
    return render(request, "core/profile.html", {"form": form})

@never_cache
@login_required
def appearance_settings(request):
    denied = own_guard(request)
    if denied: return denied
    prefs, _ = AppearancePreferences.objects.get_or_create(user=request.user)
    form = AppearanceForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=prefs)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã lưu giao diện riêng của bạn.")
        return redirect("appearance_settings")
    return render(request, "core/appearance.html", {"form": form, "prefs": prefs})

@never_cache
@login_required
@require_POST
def theme_change(request):
    denied = own_guard(request)
    if denied: return denied
    theme = request.POST.get("theme")
    if theme not in {"system", "light", "dark"}:
        return JsonResponse({"error": "Chế độ không hợp lệ."}, status=400)
    AppearancePreferences.objects.update_or_create(user=request.user, defaults={"theme": theme})
    return JsonResponse({"theme": theme})

@never_cache
@login_required
def appearance_image(request, kind):
    if kind not in {"avatar", "background"}: raise Http404
    denied = own_guard(request)
    if denied: return denied
    data = AppearancePreferences.objects.filter(user=request.user).values_list(kind + "_image", flat=True).first()
    if not data: raise Http404
    response = HttpResponse(bytes(data), content_type="image/jpeg")
    response["X-Content-Type-Options"] = "nosniff"
    return response

def can_archive_accounts(user):
    return user.has_perms(["auth.view_user", "core.manage_account_lifecycle", "core.revoke_totp_device"])


@never_cache
@staff_mfa_required
@require_POST
def account_bulk(request):
    if not can_archive_accounts(request.user):
        return HttpResponseForbidden()
    action = request.POST.get("action")
    ids = set(request.POST.getlist("account_id"))
    reason = request.POST.get("reason", "").strip()
    if action not in {"archive", "restore"} or not 1 <= len(ids) <= 20 or not all(
        value.isascii() and value.isdecimal() and len(value) <= 18 for value in ids
    ) or not 1 <= len(reason) <= 300:
        messages.error(request, "Chọn từ 1 đến 20 tài khoản và nhập lý do từ 1 đến 300 ký tự.")
    else:
        try:
            with transaction.atomic():
                subjects = list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
                if len(subjects) != len(ids):
                    raise ValidationError("Có tài khoản không còn tồn tại.")
                changed = 0
                for subject in subjects:
                    if subject.pk == request.user.pk or subject.is_superuser or not can_manage_target(request.user, subject):
                        raise PermissionError("Không thể thao tác với một hoặc nhiều tài khoản đã chọn.")
                    security, _ = AccountSecurity.objects.get_or_create(user=subject)
                    if action == "archive" and security.archived_was_active is None:
                        security.archived_was_active = subject.is_active
                        subject.is_active = False
                        revoke_totp_devices(subject=subject, actor=request.user, reason=reason, channel="account_archive")
                    elif action == "restore" and security.archived_was_active is not None:
                        subject.is_active = security.archived_was_active
                        security.archived_was_active = None
                    else:
                        continue
                    security.save(update_fields=["archived_was_active", "updated_at"])
                    subject.save(update_fields=["is_active"])
                    record_security_event(subject, AccountSecurityEvent.Kind.SYSTEM_OPERATION, request.user,
                                          {"action": action, "is_active": subject.is_active}, reason=reason)
                    changed += 1
            messages.success(request, f"Đã xử lý {changed} tài khoản.")
        except (PermissionError, ValidationError) as exc:
            messages.error(request, str(exc))
    if action == "restore":
        from django.urls import reverse
        return redirect(reverse("account_list") + "?archived=1")
    return redirect("account_list")


@never_cache
@staff_mfa_required
def account_list(request):
    if not request.user.has_perm("auth.view_user"): return HttpResponseForbidden()
    archived = request.GET.get("archived") == "1"
    users = User.objects.filter(security_profile__archived_was_active__isnull=not archived).select_related("security_profile").prefetch_related("groups").order_by("username")
    q = request.GET.get("q", "").strip()[:150]
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if role in dict(ROLE_CHOICES): users = users.filter(groups__name=role)
    if status in {"active", "inactive"}: users = users.filter(is_active=status == "active")
    page = Paginator(users, 20).get_page(request.GET.get("page"))
    can_bulk = can_archive_accounts(request.user)
    for account in page:
        account.can_bulk = can_bulk and account.pk != request.user.pk and not account.is_superuser and can_manage_target(request.user, account)
        account.role_labels = [dict(ROLE_CHOICES).get("librarian" if group.name == "library_manager" else group.name, group.name) for group in account.groups.all()]
    return render(request, "core/account_list.html", {"page_obj": page, "query": q, "selected_role": role, "selected_status": status, "roles": ROLE_CHOICES, "total_accounts": User.objects.filter(security_profile__archived_was_active__isnull=True).count(), "active_accounts": User.objects.filter(is_active=True).count(), "archived": archived, "can_bulk": can_bulk})

def can_reset_account_password(actor, subject):
    return (
        actor.has_perms(["auth.view_user", "core.manage_account_lifecycle"])
        and subject.pk != actor.pk and subject.is_active and not subject.is_superuser
        and not subject.has_perm("core.manage_system_operations")
        and subject.security_profile.archived_was_active is None
        and can_manage_target(actor, subject)
    )


class ManagedPasswordResetForm(SetPasswordForm):
    current_password = forms.CharField(
        label="Mật khẩu hiện tại của quản trị viên",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    reason = forms.CharField(label="Lý do đặt lại mật khẩu", max_length=300)
    field_order = ("current_password", "new_password1", "new_password2", "reason")

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if not self.actor.check_password(password):
            raise ValidationError("Mật khẩu xác nhận của quản trị viên không đúng.")
        return password


@never_cache
@staff_mfa_required
def account_reset_password(request, user_id):
    if not request.user.has_perms(["auth.view_user", "core.manage_account_lifecycle"]):
        return HttpResponseForbidden()
    with transaction.atomic():
        users = User.objects.select_for_update() if request.method == "POST" else User.objects.all()
        subject = get_object_or_404(users, pk=user_id)
        if not can_reset_account_password(request.user, subject):
            return HttpResponseForbidden("Không được đặt lại mật khẩu của tài khoản này.")
        form = ManagedPasswordResetForm(
            subject, request.POST if request.method == "POST" else None, actor=request.user,
        )
        if request.method == "POST" and form.is_valid():
            form.save()
            AccountSecurity.objects.filter(user=subject).update(must_change_password=True)
            record_security_event(
                subject, AccountSecurityEvent.Kind.PASSWORD_RESET_REQUIRED, request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, "Đã đặt mật khẩu tạm. Chủ tài khoản cần đổi mật khẩu khi đăng nhập.")
            return redirect("account_detail", user_id=subject.pk)
    return render(request, "core/account_reset_password.html", {"subject": subject, "form": form})


@never_cache
@staff_mfa_required
def account_detail(request, user_id):
    if not request.user.has_perm("auth.view_user"): return HttpResponseForbidden()
    subject = get_object_or_404(User.objects.select_related("security_profile").prefetch_related("groups"), pk=user_id)
    can_edit = request.user.has_perm("core.manage_account_lifecycle") and subject.security_profile.archived_was_active is None
    can_email = can_edit and (can_manage_target(request.user, subject))
    form = AccountEditForm(instance=subject, actor=request.user)
    email_form = ManagedEmailForm(auto_id="email_%s")
    if request.method == "POST":
        if not can_edit: return HttpResponseForbidden()
        action = request.POST.get("action", "profile")
        try:
            with transaction.atomic():
                subject = User.objects.select_for_update().get(pk=subject.pk)
                if subject.security_profile.archived_was_active is not None:
                    raise ValidationError("Hãy khôi phục tài khoản trước khi chỉnh sửa.")
                if action == "email":
                    if not can_email: return HttpResponseForbidden()
                    email_form = ManagedEmailForm(request.POST, auto_id="email_%s")
                    if email_form.is_valid():
                        verification = issue_email_confirmation(user=subject, email=email_form.cleaned_data["email"], request=request, actor=request.user)
                        record_security_event(subject, AccountSecurityEvent.Kind.PROFILE_UPDATED, request.user, {"email_request": verification.pk}, reason=email_form.cleaned_data["reason"])
                        messages.success(request, "Đã gửi liên kết xác nhận. Email hiện tại được giữ đến khi chủ tài khoản xác nhận.")
                        return redirect("account_detail", user_id=subject.pk)
                else:
                    form = AccountEditForm(request.POST, instance=subject, actor=request.user)
                    if form.is_valid():
                        old_roles = set(subject.groups.filter(name__in=ALL_ROLES).values_list("name", flat=True))
                        active = subject.is_active
                        obj = form.save(commit=False)
                        obj._security_actor = request.user
                        obj.save(update_fields=["username", "first_name", "last_name"])
                        if not form.restricted:
                            roles = form.cleaned_data["roles"]
                            if not request.user.has_perm("core.assign_account_roles") and not request.user.is_superuser:
                                roles = old_roles
                            obj.groups.remove(*Group.objects.filter(name__in=old_roles - roles))
                            obj.groups.add(*Group.objects.filter(name__in=roles - old_roles))
                            obj.is_staff = bool(roles - {"reader"}) or obj.is_superuser
                            obj.save(update_fields=["is_staff"])
                            if roles != old_roles:
                                record_security_event(obj, AccountSecurityEvent.Kind.ROLE_CHANGED, request.user, {"before": sorted(old_roles), "after": sorted(roles)}, reason=form.cleaned_data["reason"])
                            if active != form.cleaned_data["is_active"]:
                                set_account_active(subject=obj, actor=request.user, is_active=form.cleaned_data["is_active"], reason=form.cleaned_data["reason"])
                        record_security_event(obj, AccountSecurityEvent.Kind.PROFILE_UPDATED, request.user, reason=form.cleaned_data["reason"])
                        messages.success(request, "Đã cập nhật tài khoản.")
                        return redirect("account_detail", user_id=obj.pk)
        except (ValidationError, PermissionError, IntegrityError) as exc:
            (email_form if action == "email" else form).add_error(None, "Không lưu được thay đổi. " + ("Thông tin đã tồn tại." if isinstance(exc, IntegrityError) else str(exc)))
    return render(request, "core/account_detail.html", {"subject": subject, "form": form, "email_form": email_form, "can_edit": can_edit, "can_email": can_email, "can_reset_password": can_reset_account_password(request.user, subject), "events": subject.security_events.select_related("actor")[:20], "pending_emails": subject.email_change_requests.filter(confirmed_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now())})

@never_cache
@staff_mfa_required
def account_add(request):
    if not request.user.has_perm("core.issue_account_invitation"): return HttpResponseForbidden()
    form = AccountInvitationForm(request.POST if request.method == "POST" else None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            invitation = issue_account_invitation(actor=request.user, request=request, **form.cleaned_data)
            messages.success(request, "Đã tạo tài khoản và gửi lời mời đặt mật khẩu.")
            return redirect("account_list")
        except (ValidationError, PermissionError) as exc:
            form.add_error(None, str(exc))
    return render(request, "core/account_add.html", {"form": form})
