from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import PasswordResetForm
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.urls import path

from .lifecycle import issue_account_invitation, record_security_event, resend_account_invitation, revoke_totp_devices, set_account_active
from .lifecycle_forms import AccountInvitationForm
from .models import AccountInvitation, AccountSecurity, AccountSecurityEvent, EmailChangeVerification, ReaderProfile

User = get_user_model()


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    def save_model(self, request, obj, form, change):
        previous_active = None
        previous_roles = set()
        if change:
            old_user = User.objects.get(pk=obj.pk)
            previous_active = old_user.is_active
            previous_roles = set(old_user.groups.values_list("name", flat=True))
            obj._security_actor = request.user
        obj._security_previous_roles = previous_roles
        super().save_model(request, obj, form, change)
        security, _ = AccountSecurity.objects.get_or_create(user=obj)
        if not change:
            security.must_change_password = True
            security.save(update_fields=("must_change_password", "updated_at"))
            record_security_event(obj, AccountSecurityEvent.Kind.ACCOUNT_CREATED, request.user)
        else:
            if previous_active != obj.is_active:
                kind = AccountSecurityEvent.Kind.ACCOUNT_REACTIVATED if obj.is_active else AccountSecurityEvent.Kind.ACCOUNT_DISABLED
                record_security_event(obj, kind, request.user, {"source": "admin_user_edit"}, reason="Trạng thái đăng nhập được đổi trong Django Admin")
                if not obj.is_active:
                    revoke_totp_devices(subject=obj, actor=request.user, reason="Tài khoản bị khóa từ quản trị người dùng")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        previous_roles = getattr(user, "_security_previous_roles", set())
        current_roles = set(user.groups.values_list("name", flat=True))
        if previous_roles != current_roles:
            record_security_event(user, AccountSecurityEvent.Kind.ROLE_CHANGED, request.user, {
                "before": sorted(previous_roles), "after": sorted(current_roles),
            }, reason="Vai trò được cập nhật trong Django Admin")


@admin.register(AccountSecurity)
class AccountSecurityAdmin(admin.ModelAdmin):
    list_display = ("user", "verified_email", "email_is_verified", "email_verified_at", "must_change_password")
    search_fields = ("verified_email", "user__username", "user__email")
    readonly_fields = ("verified_email", "email_verified_at", "must_change_password", "created_at", "updated_at")
    actions = ("verify_account_emails", "require_password_reset", "disable_accounts", "reactivate_accounts", "revoke_authenticator_devices")
    change_list_template = "admin/core/accountsecurity/change_list.html"

    def get_urls(self):
        custom = [path("invite/", self.admin_site.admin_view(self.invite_account), name="core_accountsecurity_invite")]
        return custom + super().get_urls()

    def invite_account(self, request):
        if not request.user.has_perm("core.issue_account_invitation") and not request.user.is_superuser:
            return HttpResponseForbidden("Bạn không được cấp quyền mời tài khoản.")
        form = AccountInvitationForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                issue_account_invitation(
                    actor=request.user,
                    request=request,
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    role=form.cleaned_data["role"],
                    reader_number=form.cleaned_data["reader_number"],
                    reader_type=form.cleaned_data["reader_type"],
                    valid_from=form.cleaned_data["valid_from"],
                    valid_until=form.cleaned_data["valid_until"],
                )
                self.message_user(request, "Đã tạo tài khoản chờ kích hoạt và gửi liên kết đặt mật khẩu.", messages.SUCCESS)
                return redirect("admin:core_accountsecurity_changelist")
            except (ValidationError, PermissionError) as exc:
                form.add_error(None, exc)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Mời tài khoản thư viện",
            "form": form,
        }
        return TemplateResponse(request, "admin/core/invite_account.html", context)

    @admin.action(description="Xác nhận email hiện tại đã được kiểm tra", permissions=["verify_account_email"])
    def verify_account_emails(self, request, queryset):
        count = 0
        for security in queryset.select_related("user"):
            if security.user.email:
                security.verified_email = security.user.email
                security.email_verified_at = timezone.now()
                security.save(update_fields=("verified_email", "email_verified_at", "updated_at"))
                record_security_event(security.user, AccountSecurityEvent.Kind.EMAIL_VERIFIED, request.user, {"method": "staff_review"})
                count += 1
        self.message_user(request, f"Đã xác nhận email cho {count} tài khoản.")

    def has_verify_account_email_permission(self, request):
        return request.user.has_perm("core.verify_account_email")

    @admin.action(description="Gửi liên kết đặt lại mật khẩu bắt buộc", permissions=["manage_account_lifecycle"])
    def require_password_reset(self, request, queryset):
        sent = 0
        for security in queryset.select_related("user"):
            if not security.user.is_active or not security.email_is_verified or User.objects.filter(email__iexact=security.user.email).count() != 1:
                continue
            form = PasswordResetForm({"email": security.user.email})
            if form.is_valid():
                form.save(request=request, use_https=request.is_secure())
                security.must_change_password = True
                security.save(update_fields=("must_change_password", "updated_at"))
                record_security_event(security.user, AccountSecurityEvent.Kind.PASSWORD_RESET_REQUIRED, request.user)
                sent += 1
        self.message_user(request, f"Đã yêu cầu đặt lại mật khẩu cho {sent} tài khoản có email đã xác minh.")

    def has_manage_account_lifecycle_permission(self, request):
        return request.user.has_perm("core.manage_account_lifecycle")

    @admin.action(description="Khóa đăng nhập và thu hồi phiên", permissions=["manage_account_lifecycle"])
    def disable_accounts(self, request, queryset):
        changed = 0
        for security in queryset.select_related("user"):
            try:
                changed += set_account_active(subject=security.user, actor=request.user, is_active=False, reason="Khóa bởi quản lý thư viện")
            except (PermissionError, ValidationError) as exc:
                self.message_user(request, f"{security.user.get_username()}: {exc}", messages.ERROR)
        self.message_user(request, f"Đã khóa {changed} tài khoản.")

    @admin.action(description="Mở lại tài khoản có email đã xác minh", permissions=["manage_account_lifecycle"])
    def reactivate_accounts(self, request, queryset):
        changed = 0
        for security in queryset.select_related("user"):
            try:
                changed += set_account_active(subject=security.user, actor=request.user, is_active=True, reason="Mở lại bởi quản lý thư viện")
            except (PermissionError, ValidationError) as exc:
                self.message_user(request, f"{security.user.get_username()}: {exc}", messages.ERROR)
        self.message_user(request, f"Đã mở lại {changed} tài khoản.")

    @admin.action(description="Thu hồi thiết bị xác thực OTP", permissions=["revoke_totp_device"])
    def revoke_authenticator_devices(self, request, queryset):
        count = sessions = 0
        for security in queryset.select_related("user"):
            try:
                revoked, expired = revoke_totp_devices(subject=security.user, actor=request.user, reason="Thiết bị bị mất hoặc cần đăng ký lại")
            except PermissionError as exc:
                self.message_user(request, str(exc), messages.ERROR)
                return
            count += revoked
            sessions += expired
        self.message_user(request, f"Đã thu hồi {count} thiết bị OTP và kết thúc {sessions} phiên đăng nhập.")

    def has_revoke_totp_device_permission(self, request):
        return request.user.has_perm("core.revoke_totp_device")


@admin.register(ReaderProfile)
class ReaderProfileAdmin(admin.ModelAdmin):
    list_display = ("reader_number", "user", "reader_type", "status", "valid_until", "membership_verified")
    list_filter = ("reader_type", "status", "membership_verified")
    search_fields = ("reader_number", "user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("membership_verified", "membership_verified_at", "membership_verified_by", "verification_method", "created_at", "updated_at")
    actions = ("verify_reader_memberships", "suspend_reader_accounts")

    @admin.action(description="Xác minh thẻ/hồ sơ bạn đọc", permissions=["verify_reader_membership"])
    def verify_reader_memberships(self, request, queryset):
        count = 0
        for profile in queryset:
            if not profile.membership_verified or not profile.membership_verified_at:
                profile.membership_verified = True
                profile.membership_verified_at = timezone.now()
                profile.membership_verified_by = request.user
                profile.verification_method = "staff_review"
                profile.save(update_fields=("membership_verified", "membership_verified_at", "membership_verified_by", "verification_method", "updated_at"))
                record_security_event(profile.user, AccountSecurityEvent.Kind.MEMBERSHIP_VERIFIED, request.user, {
                    "reader_number": profile.reader_number,
                    "method": profile.verification_method,
                }, reason="Nhân viên đối chiếu và xác minh hồ sơ bạn đọc")
                count += 1
        self.message_user(request, f"Đã xác minh tư cách bạn đọc cho {count} hồ sơ.")

    def has_verify_reader_membership_permission(self, request):
        return request.user.has_perm("core.verify_reader_membership")

    @admin.action(description="Tạm khóa thẻ bạn đọc", permissions=["suspend_reader"])
    def suspend_reader_accounts(self, request, queryset):
        count = 0
        for profile in queryset.exclude(status=ReaderProfile.Status.SUSPENDED):
            profile.status = ReaderProfile.Status.SUSPENDED
            profile.save(update_fields=("status", "updated_at"))
            record_security_event(profile.user, AccountSecurityEvent.Kind.MEMBERSHIP_CHANGED, request.user, {
                "reader_number": profile.reader_number,
                "status": ReaderProfile.Status.SUSPENDED,
            }, reason="Tạm khóa thẻ theo nghiệp vụ thư viện")
            count += 1
        self.message_user(request, f"Đã tạm khóa {count} hồ sơ.")

    def has_suspend_reader_permission(self, request):
        return request.user.has_perm("core.suspend_reader")

    def save_model(self, request, obj, form, change):
        before = ReaderProfile.objects.get(pk=obj.pk) if change else None
        super().save_model(request, obj, form, change)
        if before and (before.status != obj.status or before.valid_until != obj.valid_until):
            record_security_event(obj.user, AccountSecurityEvent.Kind.MEMBERSHIP_CHANGED, request.user, {
                "reader_number": obj.reader_number,
                "status_before": before.status,
                "status_after": obj.status,
                "valid_until_before": before.valid_until.isoformat(),
                "valid_until_after": obj.valid_until.isoformat(),
            }, reason="Cập nhật trạng thái hoặc thời hạn thẻ trong Django Admin")


@admin.register(AccountInvitation)
class AccountInvitationAdmin(admin.ModelAdmin):
    list_display = ("user", "invited_email", "invited_by", "created_at", "expires_at", "accepted_at", "revoked_at")
    search_fields = ("user__username", "invited_email")
    readonly_fields = tuple(field.name for field in AccountInvitation._meta.fields)
    actions = ("revoke_pending_invitations", "resend_invitations")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Thu hồi lời mời đang chờ", permissions=["manage_account_invitations"])
    def revoke_pending_invitations(self, request, queryset):
        count = 0
        for invitation in queryset.filter(accepted_at__isnull=True, revoked_at__isnull=True, user__is_active=False):
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=("revoked_at",))
            record_security_event(invitation.user, AccountSecurityEvent.Kind.INVITATION_REVOKED, request.user, {"invitation_id": invitation.pk})
            count += 1
        self.message_user(request, f"Đã thu hồi {count} lời mời.")

    def has_manage_account_invitations_permission(self, request):
        return request.user.has_perm("core.manage_account_invitations")

    @admin.action(description="Gửi lại lời mời cho tài khoản chưa kích hoạt", permissions=["issue_account_invitation"])
    def resend_invitations(self, request, queryset):
        count = 0
        for invitation in queryset.filter(accepted_at__isnull=True).select_related("user"):
            try:
                resend_account_invitation(invitation=invitation, actor=request.user, request=request)
                count += 1
            except (PermissionError, ValidationError) as exc:
                self.message_user(request, f"{invitation.user.get_username()}: {exc}", messages.ERROR)
        self.message_user(request, f"Đã gửi lại {count} lời mời.")

    def has_issue_account_invitation_permission(self, request):
        return request.user.has_perm("core.issue_account_invitation")


class ReadOnlySecurityRecordAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccountSecurityEvent)
class AccountSecurityEventAdmin(ReadOnlySecurityRecordAdmin):
    list_display = ("occurred_at", "subject", "actor", "kind", "reason")
    list_filter = ("kind", "occurred_at")
    search_fields = ("subject__username", "actor__username", "kind", "reason")


@admin.register(EmailChangeVerification)
class EmailChangeVerificationAdmin(ReadOnlySecurityRecordAdmin):
    list_display = ("user", "pending_email", "created_at", "expires_at", "confirmed_at", "revoked_at")
    search_fields = ("user__username", "pending_email")
