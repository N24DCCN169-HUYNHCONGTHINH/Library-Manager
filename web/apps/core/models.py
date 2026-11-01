from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class AccountSecurityEvent(models.Model):
    class Kind(models.TextChoices):
        ACCOUNT_CREATED = "account_created", "Đã tạo tài khoản"
        ROLE_CHANGED = "role_changed", "Đã đổi vai trò"
        INVITATION_SENT = "invitation_sent", "Đã gửi lời mời"
        INVITATION_ACCEPTED = "invitation_accepted", "Đã nhận lời mời"
        INVITATION_REVOKED = "invitation_revoked", "Đã thu hồi lời mời"
        MEMBERSHIP_EXPIRED = "membership_expired", "Thẻ bạn đọc hết hạn"
        MEMBERSHIP_VERIFIED = "membership_verified", "Đã xác minh thẻ bạn đọc"
        MEMBERSHIP_CHANGED = "membership_changed", "Đã đổi trạng thái/thời hạn thẻ"
        EMAIL_VERIFIED = "email_verified", "Đã xác minh email"
        EMAIL_CHANGE_REQUESTED = "email_change_requested", "Yêu cầu đổi email"
        EMAIL_CHANGED = "email_changed", "Đã đổi email"
        PASSWORD_RESET_REQUIRED = "password_reset_required", "Yêu cầu đặt lại mật khẩu"
        PASSWORD_RESET_COMPLETED = "password_reset_completed", "Đã đặt lại mật khẩu"
        PASSWORD_CHANGED = "password_changed", "Đã đổi mật khẩu"
        ACCOUNT_DISABLED = "account_disabled", "Đã khóa tài khoản"
        ACCOUNT_REACTIVATED = "account_reactivated", "Đã mở khóa tài khoản"
        TOTP_ENROLLED = "totp_enrolled", "Đã đăng ký thiết bị xác thực"
        TOTP_REVOKED = "totp_revoked", "Đã thu hồi thiết bị xác thực"

    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="security_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="performed_security_events")
    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    reason = models.CharField("lý do", max_length=300, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.subject} · {self.occurred_at:%Y-%m-%d %H:%M}"


class AccountSecurity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="security_profile",
    )
    verified_email = models.EmailField("email đã xác minh", blank=True)
    email_verified_at = models.DateTimeField("xác minh lúc", null=True, blank=True)
    must_change_password = models.BooleanField("bắt buộc đổi mật khẩu", default=False)
    created_at = models.DateTimeField("tạo lúc", auto_now_add=True)
    updated_at = models.DateTimeField("cập nhật lúc", auto_now=True)

    class Meta:
        verbose_name = "bảo mật tài khoản"
        verbose_name_plural = "bảo mật tài khoản"
        permissions = [
            ("verify_account_email", "Can verify account email"),
            ("issue_account_invitation", "Can issue account invitations"),
            ("manage_account_lifecycle", "Can disable and reactivate accounts"),
            ("revoke_totp_device", "Can revoke staff authenticator devices"),
        ]

    @property
    def email_is_verified(self):
        return bool(
            self.email_verified_at
            and self.verified_email
            and self.user.email
            and self.verified_email.casefold() == self.user.email.casefold()
        )

    def __str__(self):
        return f"Bảo mật tài khoản {self.user.get_username()}"


class ReaderProfile(models.Model):
    class ReaderType(models.TextChoices):
        STUDENT = "student", "Sinh viên"
        FACULTY = "faculty", "Giảng viên"
        EMPLOYEE = "employee", "Nhân viên"

    class Status(models.TextChoices):
        ACTIVE = "active", "Đang hoạt động"
        SUSPENDED = "suspended", "Tạm khóa"
        EXPIRED = "expired", "Hết hạn"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reader_profile",
    )
    reader_number = models.CharField(
        "mã bạn đọc", max_length=32, unique=True,
        validators=[RegexValidator(r"^[A-Za-z0-9_-]+$", "Chỉ dùng chữ, số, dấu gạch ngang hoặc gạch dưới.")],
    )
    reader_type = models.CharField("loại bạn đọc", max_length=16, choices=ReaderType.choices)
    status = models.CharField("trạng thái thẻ", max_length=16, choices=Status.choices, default=Status.ACTIVE)
    valid_from = models.DateField("có hiệu lực từ")
    valid_until = models.DateField("có hiệu lực đến")
    membership_verified = models.BooleanField("thẻ đã được xác minh", default=False)
    membership_verified_at = models.DateTimeField("xác minh lúc", null=True, blank=True)
    membership_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="verified_reader_memberships",
    )
    verification_method = models.CharField("cách xác minh", max_length=32, blank=True)
    created_at = models.DateTimeField("tạo lúc", auto_now_add=True)
    updated_at = models.DateTimeField("cập nhật lúc", auto_now=True)

    class Meta:
        ordering = ["reader_number"]
        verbose_name = "hồ sơ bạn đọc"
        verbose_name_plural = "hồ sơ bạn đọc"
        permissions = [
            ("verify_reader_membership", "Can verify reader membership"),
            ("suspend_reader", "Can suspend reader account"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_until__gte=F("valid_from")),
                name="reader_valid_until_gte_valid_from",
            ),
        ]

    def __str__(self):
        return f"{self.reader_number} — {self.user.get_username()}"

    @property
    def card_is_current(self):
        today = timezone.localdate()
        return self.membership_verified and self.status == self.Status.ACTIVE and self.valid_from <= today <= self.valid_until


class AccountInvitation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account_invitations")
    invited_email = models.EmailField()
    token_digest = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issued_account_invitations")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("manage_account_invitations", "Can revoke account invitations")]

    @property
    def is_pending(self):
        return self.accepted_at is None and self.revoked_at is None and self.expires_at > timezone.now()


class EmailChangeVerification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="email_change_requests")
    pending_email = models.EmailField()
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
