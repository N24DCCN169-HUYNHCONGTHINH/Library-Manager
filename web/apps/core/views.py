import base64
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from .lifecycle import (
    accept_account_invitation, confirm_email_change, digest_token,
    record_security_event, request_email_change,
)
from .lifecycle_forms import EmailChangeRequestForm, InvitationAcceptForm
from .models import AccountInvitation, AccountSecurity, AccountSecurityEvent

STAFF_ROLES = ("librarian", "circulation_staff", "cataloger", "library_manager", "system_admin")


class OTPCodeForm(forms.Form):
    code = forms.CharField(
        label="Mã xác minh gồm 6 chữ số",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
    )

    def clean_code(self):
        code = self.cleaned_data["code"]
        if not re.fullmatch(r"\d{6}", code):
            raise forms.ValidationError("Nhập mã gồm 6 chữ số.")
        return code


class OTPVerifyForm(OTPCodeForm):
    device_id = forms.ChoiceField(label="Thiết bị xác thực")

    def __init__(self, devices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["device_id"].choices = [(str(device.pk), device.name or "Ứng dụng xác thực") for device in devices]
        self.order_fields(["device_id", "code"])


def has_role(role):
    def check(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        roles = STAFF_ROLES if role == "librarian" else (role,)
        return user.groups.filter(name__in=roles).exists()
    return check


def has_staff_role(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=STAFF_ROLES).exists())


def staff_mfa_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not has_staff_role(request.user):
            return redirect("home")
        if not request.user.is_verified():
            if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
                return redirect("otp_verify")
            return redirect("otp_setup")
        return view(request, *args, **kwargs)
    return wrapped


def home(request):
    return render(request, "core/home.html")


@staff_mfa_required
def staff_dashboard(request):
    return render(request, "core/staff_dashboard.html")


@login_required
@user_passes_test(has_role("reader"), login_url="home")
def reader_portal(request):
    try:
        profile = request.user.reader_profile
    except ObjectDoesNotExist:
        profile = None
    loans = reservations = fines = []
    if profile:
        from apps.library.models import Fine, Loan, Reservation
        from apps.library.services import refresh_overdue_loans
        refresh_overdue_loans(profile)
        loans = list(Loan.objects.filter(reader=profile).select_related("copy__book", "copy__branch", "policy").order_by("status", "due_at")[:100])
        now = timezone.now()
        for loan in loans:
            if loan.status != Loan.Status.OPEN:
                loan.renewal_message = "Lượt mượn đã đóng."
            elif loan.renewal_count >= loan.policy.max_renewals:
                loan.renewal_message = "Đã dùng hết số lần gia hạn theo chính sách."
            elif loan.due_at < now:
                loan.renewal_message = "Lượt mượn đã quá hạn; vui lòng liên hệ quầy."
            elif loan.due_at - now > timedelta(hours=48):
                loan.renewal_message = "Có thể yêu cầu gia hạn trong 48 giờ cuối trước hạn trả."
            elif Reservation.objects.filter(book=loan.copy.book, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).exists():
                loan.renewal_message = "Đầu sách có người đặt trước nên chưa thể gia hạn."
            else:
                loan.can_request_renewal = loan.due_at >= now and loan.due_at - now <= timedelta(hours=48)
                loan.renewal_message = "Có thể gửi yêu cầu; hệ thống sẽ kiểm tra lại tình trạng thẻ và điều kiện giao dịch."
        reservations = Reservation.objects.filter(reader=profile, status__in=["waiting", "ready"]).select_related("book").order_by("created_at")
        for reservation in reservations:
            if reservation.status == Reservation.Status.WAITING:
                reservation.queue_position = Reservation.objects.filter(
                    book=reservation.book, status=Reservation.Status.WAITING,
                ).filter(
                    Q(created_at__lt=reservation.created_at)
                    | Q(created_at=reservation.created_at, id__lte=reservation.id)
                ).count()
        fines = Fine.objects.filter(loan__reader=profile).select_related("loan__copy__book").order_by("-calculated_at")
    return render(request, "core/reader_portal.html", {"profile": profile, "today": timezone.localdate(), "loans": loans, "reservations": reservations, "fines": fines})


class AuditedPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "registration/password_change_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        security, _ = AccountSecurity.objects.get_or_create(user=self.request.user)
        security.must_change_password = False
        security.save(update_fields=["must_change_password", "updated_at"])
        record_security_event(self.request.user, AccountSecurityEvent.Kind.PASSWORD_CHANGED, self.request.user)
        return response


class AuditedPasswordResetView(auth_views.PasswordResetView):
    def form_valid(self, form):
        users = list(form.get_users(form.cleaned_data["email"]))
        response = super().form_valid(form)
        for user in users:
            record_security_event(user, AccountSecurityEvent.Kind.PASSWORD_RESET_REQUIRED, user, {"source": "self_service"})
        return response


class AuditedPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        security, _ = AccountSecurity.objects.get_or_create(user=self.user)
        security.must_change_password = False
        security.save(update_fields=["must_change_password", "updated_at"])
        record_security_event(self.user, AccountSecurityEvent.Kind.PASSWORD_RESET_COMPLETED, self.user)
        return response


@never_cache
def account_invite_accept(request, token):
    invitation = AccountInvitation.objects.select_related("user").filter(token_digest=digest_token(token)).first()
    if not invitation or not invitation.is_pending or invitation.user.is_active:
        return render(request, "registration/invitation_invalid.html", status=HttpResponseBadRequest.status_code)
    form = InvitationAcceptForm(invitation.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            accept_account_invitation(token, form.cleaned_data["new_password1"])
            messages.success(request, "Tài khoản đã được kích hoạt. Hãy đăng nhập bằng mật khẩu vừa tạo.")
            return redirect("login")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "registration/invitation_accept.html", {"form": form, "username": invitation.user.get_username()})


@login_required
def email_change_request(request):
    if has_staff_role(request.user) and not request.user.is_verified():
        return redirect("otp_verify" if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists() else "otp_setup")
    form = EmailChangeRequestForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            request_email_change(
                user=request.user,
                email=form.cleaned_data["email"],
                current_password=form.cleaned_data["current_password"],
                request=request,
            )
            messages.success(request, "Đã gửi liên kết xác nhận tới email mới. Email tài khoản chỉ đổi sau khi xác nhận liên kết.")
            return redirect("home")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "registration/email_change_form.html", {"form": form})


@login_required
@never_cache
def email_change_confirm(request, token):
    if has_staff_role(request.user) and not request.user.is_verified():
        return redirect("otp_verify" if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists() else "otp_setup")
    form = forms.Form(request.POST or None)
    if request.method == "POST":
        try:
            verification = confirm_email_change(token, request.user)
            messages.success(request, f"Email tài khoản đã được đổi và xác minh: {verification.pending_email}.")
            return redirect("home")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "registration/email_change_confirm.html", {"form": form})


@never_cache
@login_required
def otp_setup(request):
    if not has_staff_role(request.user):
        return redirect("home")
    if request.user.is_verified():
        return redirect("staff_dashboard")
    if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        return redirect("otp_verify")

    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(
            user=request.user,
            name="Authenticator app",
            key=secrets.token_hex(20),
            confirmed=False,
        )
    secret = base64.b32encode(bytes.fromhex(device.key)).decode("ascii").rstrip("=")
    issuer = "Library Manager"
    account = quote(f"{issuer}:{request.user.get_username()}", safe="")
    otpauth_uri = f"otpauth://totp/{account}?secret={secret}&issuer={quote(issuer)}"
    form = OTPCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_device = TOTPDevice.objects.select_for_update().get(pk=device.pk)
            if locked_device.verify_token(form.cleaned_data["code"]):
                locked_device.confirmed = True
                locked_device.save(update_fields=["confirmed", "last_t"])
                otp_login(request, locked_device)
                record_security_event(request.user, AccountSecurityEvent.Kind.TOTP_ENROLLED, request.user, {"device_name": locked_device.name})
                return redirect("staff_dashboard")
        form.add_error("code", "Mã không hợp lệ hoặc đã hết hạn. Hãy thử mã mới.")
    return render(request, "registration/otp_setup.html", {"form": form, "secret": secret, "otpauth_uri": otpauth_uri})


@never_cache
@login_required
def otp_verify(request):
    if not has_staff_role(request.user):
        return redirect("home")
    if request.user.is_verified():
        return redirect("staff_dashboard")
    devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)
    if not devices.exists():
        return redirect("otp_setup")
    form = OTPVerifyForm(devices, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked_device = TOTPDevice.objects.select_for_update().get(
                pk=form.cleaned_data["device_id"], user=request.user, confirmed=True
            )
            if locked_device.verify_token(form.cleaned_data["code"]):
                otp_login(request, locked_device)
                return redirect("staff_dashboard")
        form.add_error("code", "Mã không hợp lệ hoặc đã hết hạn. Hãy thử mã mới.")
    return render(request, "registration/otp_verify.html", {"form": form})


def health(request):
    return JsonResponse({"status": "ok"})
