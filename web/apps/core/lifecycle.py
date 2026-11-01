import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import AccountInvitation, AccountSecurity, AccountSecurityEvent, EmailChangeVerification, ReaderProfile


def digest_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def record_security_event(subject, kind, actor=None, details=None, reason=""):
    details = details or {}
    return AccountSecurityEvent.objects.create(
        subject=subject,
        actor=actor if actor and actor.is_authenticated else None,
        kind=kind,
        reason=(reason or details.get("reason", ""))[:300],
        details=details,
    )


def _send_mail(subject, message, recipient, *, fail_silently=False):
    try:
        sent = send_mail(subject, message, None, [recipient], fail_silently=fail_silently)
    except Exception as exc:
        if fail_silently:
            return 0
        raise ValidationError("Không gửi được email. Hãy kiểm tra cấu hình thư và thử lại.") from exc
    return sent


@transaction.atomic
def issue_account_invitation(*, actor, request, username, email, first_name="", last_name="", role="reader", reader_number="", reader_type="", valid_from=None, valid_until=None):
    if not actor.is_superuser and not actor.has_perm("core.issue_account_invitation"):
        raise PermissionError("Tài khoản không được cấp quyền gửi lời mời.")
    allowed_roles = {"reader", "cataloger", "circulation_staff", "librarian"}
    if role not in allowed_roles:
        raise ValidationError("Vai trò này chỉ được cấp bởi quản trị khẩn cấp.")
    user_model = get_user_model()
    if user_model.objects.filter(username__iexact=username).exists():
        raise ValidationError("Tên đăng nhập này đã được sử dụng.")
    if user_model.objects.filter(email__iexact=email).exists():
        raise ValidationError("Email này đã gắn với một tài khoản.")
    user = user_model(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=False,
        is_staff=role != "reader",
    )
    user.set_unusable_password()
    user.save()
    security, _ = AccountSecurity.objects.get_or_create(user=user)
    security.must_change_password = False
    security.save(update_fields=["must_change_password", "updated_at"])
    from django.contrib.auth.models import Group
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)

    if role == "reader":
        ReaderProfile.objects.create(
            user=user,
            reader_number=reader_number,
            reader_type=reader_type,
            valid_from=valid_from,
            valid_until=valid_until,
            membership_verified=False,
        )

    raw_token = secrets.token_urlsafe(36)
    invitation = AccountInvitation.objects.create(
        user=user,
        invited_email=email,
        token_digest=digest_token(raw_token),
        invited_by=actor,
        expires_at=timezone.now() + timedelta(hours=72),
    )
    invitation_url = request.build_absolute_uri(reverse("account_invite_accept", kwargs={"token": raw_token}))
    sent = _send_mail(
        "Lời mời kích hoạt tài khoản thư viện",
        f"Xin chào {first_name or username},\n\nTài khoản của bạn đang chờ kích hoạt. Hãy đặt mật khẩu qua liên kết sau trong vòng 72 giờ:\n{invitation_url}\n\nNếu bạn không mong đợi email này, hãy bỏ qua và liên hệ thư viện.",
        fail_silently=False,
        recipient=email,
    )
    if sent != 1:
        raise ValidationError("Không gửi được email mời; tài khoản chưa được tạo.")
    record_security_event(user, AccountSecurityEvent.Kind.INVITATION_SENT, actor, {"role": role, "expires_at": invitation.expires_at.isoformat()})
    return user, invitation


@transaction.atomic
def resend_account_invitation(*, invitation, actor, request):
    if not actor.is_superuser and not actor.has_perm("core.issue_account_invitation"):
        raise PermissionError("Tài khoản không được cấp quyền gửi lời mời.")
    invitation = AccountInvitation.objects.select_for_update().select_related("user").get(pk=invitation.pk)
    if invitation.accepted_at or invitation.user.is_active:
        raise ValidationError("Tài khoản đã được kích hoạt, không thể gửi lại lời mời.")
    if not invitation.user.email:
        raise ValidationError("Tài khoản chưa có email nhận lời mời.")
    now = timezone.now()
    if not invitation.revoked_at:
        invitation.revoked_at = now
        invitation.save(update_fields=["revoked_at"])
    raw_token = secrets.token_urlsafe(36)
    new_invitation = AccountInvitation.objects.create(
        user=invitation.user,
        invited_email=invitation.user.email,
        token_digest=digest_token(raw_token),
        invited_by=actor,
        expires_at=now + timedelta(hours=72),
    )
    link = request.build_absolute_uri(reverse("account_invite_accept", kwargs={"token": raw_token}))
    sent = _send_mail(
        "Lời mời kích hoạt tài khoản thư viện",
        f"Tài khoản của bạn đang chờ kích hoạt. Hãy đặt mật khẩu qua liên kết sau trong vòng 72 giờ:\n{link}\n\nNếu bạn không mong đợi email này, hãy bỏ qua và liên hệ thư viện.",
        fail_silently=False,
        recipient=new_invitation.invited_email,
    )
    if sent != 1:
        raise ValidationError("Không gửi được email mời.")
    record_security_event(invitation.user, AccountSecurityEvent.Kind.INVITATION_SENT, actor, {"invitation_id": new_invitation.pk, "resent": True})
    return new_invitation


@transaction.atomic
def accept_account_invitation(raw_token, password):
    invitation = AccountInvitation.objects.select_for_update().select_related("user").filter(token_digest=digest_token(raw_token)).first()
    if not invitation or invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= timezone.now():
        raise ValidationError("Liên kết lời mời không hợp lệ hoặc đã hết hạn.")
    user = get_user_model().objects.select_for_update().get(pk=invitation.user_id)
    if user.is_active or user.email.casefold() != invitation.invited_email.casefold():
        raise ValidationError("Lời mời không còn áp dụng cho tài khoản này.")
    from django.contrib.auth.password_validation import validate_password
    validate_password(password, user=user)
    user.set_password(password)
    user.is_active = True
    user.save(update_fields=["password", "is_active"])
    security, _ = AccountSecurity.objects.get_or_create(user=user)
    security.verified_email = invitation.invited_email
    security.email_verified_at = timezone.now()
    security.must_change_password = False
    security.save(update_fields=["verified_email", "email_verified_at", "must_change_password", "updated_at"])
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    record_security_event(user, AccountSecurityEvent.Kind.INVITATION_ACCEPTED, user, {"invitation_id": invitation.pk})
    return user


@transaction.atomic
def request_email_change(*, user, email, current_password, request):
    if not user.check_password(current_password):
        raise ValidationError("Mật khẩu hiện tại không đúng.")
    if get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        raise ValidationError("Email này đã gắn với tài khoản khác.")
    if email.casefold() == (user.email or "").casefold():
        raise ValidationError("Email này hiện đang được dùng cho tài khoản của bạn.")
    now = timezone.now()
    EmailChangeVerification.objects.select_for_update().filter(
        user=user, confirmed_at__isnull=True, revoked_at__isnull=True, expires_at__gt=now
    ).update(revoked_at=now)
    raw_token = secrets.token_urlsafe(36)
    verification = EmailChangeVerification.objects.create(
        user=user,
        pending_email=email,
        token_digest=digest_token(raw_token),
        expires_at=now + timedelta(hours=2),
    )
    link = request.build_absolute_uri(reverse("email_change_confirm", kwargs={"token": raw_token}))
    sent = _send_mail(
        "Xác nhận đổi email tài khoản thư viện",
        f"Bạn vừa yêu cầu đổi email. Xác nhận địa chỉ mới trong vòng 2 giờ bằng liên kết sau:\n{link}\n\nNếu bạn không thực hiện yêu cầu này, hãy bỏ qua email.",
        fail_silently=False,
        recipient=email,
    )
    if sent != 1:
        raise ValidationError("Không gửi được email xác nhận.")
    if user.email:
        _send_mail(
            "Yêu cầu đổi email tài khoản thư viện",
            "Có yêu cầu đổi email tài khoản của bạn. Nếu không phải bạn, hãy liên hệ thư viện và đổi mật khẩu ngay.",
            fail_silently=True,
            recipient=user.email,
        )
    record_security_event(user, AccountSecurityEvent.Kind.EMAIL_CHANGE_REQUESTED, user, {"verification_id": verification.pk})
    return verification


@transaction.atomic
def confirm_email_change(raw_token, user):
    verification = EmailChangeVerification.objects.select_for_update().filter(
        user=user,
        token_digest=digest_token(raw_token),
        confirmed_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if not verification:
        raise ValidationError("Liên kết xác nhận email không hợp lệ hoặc đã hết hạn.")
    user_model = get_user_model()
    if user_model.objects.filter(email__iexact=verification.pending_email).exclude(pk=user.pk).exists():
        raise ValidationError("Email này đã được gắn với tài khoản khác.")
    user.email = verification.pending_email
    user._security_actor = user
    user.save(update_fields=["email"])
    security, _ = AccountSecurity.objects.get_or_create(user=user)
    security.verified_email = user.email
    security.email_verified_at = timezone.now()
    security.save(update_fields=["verified_email", "email_verified_at", "updated_at"])
    verification.confirmed_at = timezone.now()
    verification.save(update_fields=["confirmed_at"])
    return verification


@transaction.atomic
def revoke_totp_devices(*, subject, actor, reason="", channel="admin"):
    if not actor.is_superuser and not actor.has_perm("core.revoke_totp_device"):
        raise PermissionError("Tài khoản không được cấp quyền thu hồi thiết bị xác thực.")
    devices = TOTPDevice.objects.select_for_update().filter(user=subject)
    count = devices.count()
    devices.delete()
    expired = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        try:
            session_data = session.get_decoded()
        except Exception:
            continue
        if str(session_data.get("_auth_user_id", "")) == str(subject.pk):
            session.delete()
            expired += 1
    record_security_event(subject, AccountSecurityEvent.Kind.TOTP_REVOKED, actor, {
        "device_count": count,
        "session_count": expired,
        "reason": reason[:300],
        "channel": channel,
    })
    return count, expired


@transaction.atomic
def set_account_active(*, subject, actor, is_active, reason=""):
    if not actor.is_superuser and not actor.has_perm("core.manage_account_lifecycle"):
        raise PermissionError("Tài khoản không được cấp quyền khóa hoặc mở tài khoản.")
    subject = get_user_model().objects.select_for_update().get(pk=subject.pk)
    if not is_active and subject.is_superuser and not actor.is_superuser:
        raise ValidationError("Chỉ một superuser khác mới được khóa tài khoản superuser.")
    security, _ = AccountSecurity.objects.get_or_create(user=subject)
    if is_active and not security.email_is_verified:
        raise ValidationError("Chỉ mở lại tài khoản sau khi email đã được xác minh.")
    if subject.is_active == is_active:
        return False
    subject.is_active = is_active
    subject.save(update_fields=["is_active"])
    kind = AccountSecurityEvent.Kind.ACCOUNT_REACTIVATED if is_active else AccountSecurityEvent.Kind.ACCOUNT_DISABLED
    record_security_event(subject, kind, actor, {"reason": reason[:300]})
    if not is_active:
        revoke_totp_devices(subject=subject, actor=actor, reason=reason or "Khóa tài khoản", channel="account_disable")
    return True
