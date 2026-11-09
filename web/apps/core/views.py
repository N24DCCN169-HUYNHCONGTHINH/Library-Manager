import base64
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import quote

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
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


def _staff_destination(request):
    destination = request.session.pop("staff_mfa_next", "")
    if (destination and url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure())
            and ("/accounts/" not in destination or destination.startswith("/accounts/email/confirm/"))):
        return destination
    return reverse("staff_dashboard")


class RoleAwareLoginView(auth_views.LoginView):
    def get_success_url(self):
        from .models import SystemConfiguration
        duration = SystemConfiguration.objects.filter(pk=1).values_list("session_minutes", flat=True).first()
        if duration in {30, 60, 120, 240, 480}:
            self.request.session.set_expiry(min(duration * 60, settings.SESSION_COOKIE_AGE))
        destination = self.get_redirect_url()
        from .email_otp import verified_email, send_code
        if verified_email(self.request.user):
            self.request.session.pop("otp_device_id", None)
            self.request.user.otp_device = None
            fallback = reverse("staff_dashboard") if has_staff_role(self.request.user) else reverse("reader_portal") if self.request.user.groups.filter(name="reader").exists() else reverse("profile")
            self.request.session["email_otp_pending"] = True
            self.request.session["email_otp_next"] = destination or fallback
            self.request.session["staff_mfa_next"] = destination or fallback
            try:
                send_code(self.request)
            except ValidationError as exc:
                messages.error(self.request, str(exc.messages[0]))
            return reverse("email_otp_verify")
        if has_staff_role(self.request.user):
            if not getattr(self.request.user, "is_verified", lambda: False)():
                self.request.session["staff_mfa_next"] = destination or reverse("staff_dashboard")
                return reverse("otp_verify" if TOTPDevice.objects.filter(user=self.request.user, confirmed=True).exists() else "otp_setup")
            return destination or reverse("staff_dashboard")
        return destination or (reverse("reader_portal") if self.request.user.groups.filter(name="reader").exists() else reverse("home"))


def staff_mfa_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not has_staff_role(request.user):
            return redirect("home")
        if not request.user.is_verified():
            request.session["staff_mfa_next"] = request.get_full_path()
            if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
                return redirect("otp_verify")
            return redirect("otp_setup")
        return view(request, *args, **kwargs)
    return wrapped


def home(request):
    return render(request, "core/home.html")


@never_cache
@staff_mfa_required
def staff_dashboard(request):
    if request.user.has_perm("core.manage_system_operations") and request.GET.get("view") != "library":
        from .operations_views import render_operations
        return render_operations(request, dashboard=True)
    from .dashboard import dashboard_context
    return render(request, "core/staff_dashboard.html", dashboard_context(request.user, request.GET))


@never_cache
@login_required
@user_passes_test(has_role("reader"), login_url="home")
def reader_portal(request):
    try:
        profile = request.user.reader_profile
    except ObjectDoesNotExist:
        profile = None
    loans = reservations = fines = compensation_cases = []
    loan_notifications = []
    summary = {}
    loan_status = request.GET.get("loan_status", "")
    if profile:
        from apps.library.models import DamageCase, Fine, Loan, Reservation
        from apps.library.models import LoanNotification
        loan_notifications = LoanNotification.objects.filter(loan__reader=profile, loan__status="open", due_at=F("loan__due_at")).select_related("loan__copy__book").defer('loan__copy__book__cover_image').order_by("-created_at")[:10]
        now = timezone.now()
        own_loans = Loan.objects.filter(reader=profile)
        own_reservations = Reservation.objects.filter(reader=profile)
        own_fines = Fine.objects.filter(loan__reader=profile).select_related("loan__copy__book", "loan__reader").prefetch_related("transactions").defer('loan__copy__book__cover_image').order_by("-calculated_at", "-pk")
        summary = {"open_loans": own_loans.filter(status=Loan.Status.OPEN).count(),
                   "overdue_loans": own_loans.filter(status=Loan.Status.OPEN, due_at__lt=now).count(),
                   "active_reservations": own_reservations.filter(status__in=["waiting", "ready"]).count(),
                   "balance": sum(fine.balance for fine in own_fines)}
        if loan_status == "overdue":
            own_loans = own_loans.filter(status=Loan.Status.OPEN, due_at__lt=now)
        elif loan_status in Loan.Status.values:
            own_loans = own_loans.filter(status=loan_status)
        else:
            loan_status = ""
        loans = Paginator(own_loans.select_related("copy__book", "copy__branch", "policy").defer('copy__book__cover_image')
                          .order_by("-loaned_at", "-pk"), 20).get_page(request.GET.get("loan_page"))
        for loan in loans:
            loan.is_overdue = loan.status == Loan.Status.OPEN and loan.due_at < now
            if loan.status != Loan.Status.OPEN:
                loan.renewal_message = "Lượt mượn đã đóng."
            elif loan.renewal_count >= loan.max_renewals_snapshot:
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
        reservations = Paginator(own_reservations.select_related("book", "copy__branch", "pickup_branch").defer('book__cover_image')
                                 .order_by("-created_at", "-pk"), 20).get_page(request.GET.get("reservation_page"))
        for reservation in reservations:
            if reservation.status == Reservation.Status.WAITING:
                queue = Reservation.objects.filter(
                    book=reservation.book, status=Reservation.Status.WAITING,
                ).filter(
                    Q(created_at__lt=reservation.created_at)
                    | Q(created_at=reservation.created_at, id__lte=reservation.id)
                )
                if reservation.pickup_branch_id:
                    queue = queue.filter(Q(pickup_branch__isnull=True) | Q(pickup_branch_id=reservation.pickup_branch_id))
                reservation.queue_position = queue.count()
        fines = Paginator(own_fines, 20).get_page(request.GET.get("fine_page"))
        own_compensation = DamageCase.objects.filter(loan__reader=profile)
        compensation_cases = Paginator(
            own_compensation.select_related("loan__copy__book").defer("loan__copy__book__cover_image")
            .order_by("-reported_at", "-pk"), 20,
        ).get_page(request.GET.get("compensation_page"))

    return render(request, "core/reader_portal.html", {"profile": profile, "today": timezone.localdate(),
        "loans": loans, "reservations": reservations, "fines": fines, "summary": summary,
        "loan_status": loan_status, "loan_notifications": loan_notifications, "compensation_cases": compensation_cases})


@never_cache
@login_required
@user_passes_test(has_role("reader"), login_url="home")
def reader_loan_detail(request, loan_id):
    from apps.library.models import Fine, Loan
    loan = get_object_or_404(Loan.objects.select_related("copy__book", "copy__branch", "reader").defer('copy__book__cover_image'),
                             pk=loan_id, reader__user=request.user)
    fine = Fine.objects.filter(loan=loan).first()
    return render(request, "core/reader_loan_detail.html", {"loan": loan, "fine": fine,
        "return_requested": loan.events.filter(event_type="return_requested").exists(),
        "renewals": loan.renewals.order_by("renewed_at", "pk"),
        "payments": fine.transactions.order_by("created_at", "pk") if fine else []})


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


@never_cache
def email_change_confirm(request, token):
    from .models import EmailChangeVerification

    verification = EmailChangeVerification.objects.select_related("user").filter(
        token_digest=digest_token(token), confirmed_at__isnull=True,
        revoked_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True,
    ).first()
    form = forms.Form(request.POST if request.method == "POST" else None)
    confirmed = False
    needs_staff_mfa = False
    if verification:
        owner = verification.user
        same_account = request.user == owner
        needs_staff_mfa = has_staff_role(owner) and not (
            same_account and request.user.is_verified()
        )
        if not same_account and not needs_staff_mfa:
            form.fields["current_password"] = forms.CharField(
                label="Mật khẩu hiện tại", strip=False,
                widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
            )
        if request.method == "POST" and not needs_staff_mfa and form.is_valid():
            if not same_account and not owner.check_password(form.cleaned_data["current_password"]):
                form.add_error("current_password", "Mật khẩu không đúng.")
            else:
                try:
                    confirm_email_change(token, owner)
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    confirmed = True
    response = render(request, "registration/email_change_confirm.html", {
        "form": form, "valid_link": verification is not None,
        "confirmed": confirmed, "needs_staff_mfa": needs_staff_mfa,
    })
    response["Referrer-Policy"] = "strict-origin"
    return response


@never_cache
@login_required
def otp_setup(request):
    if not has_staff_role(request.user):
        return redirect("home")
    if request.user.is_verified():
        return redirect(_staff_destination(request))
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
                request.session.pop("email_otp_pending", None)
                record_security_event(request.user, AccountSecurityEvent.Kind.TOTP_ENROLLED, request.user, {"device_name": locked_device.name})
                return redirect(_staff_destination(request))
        form.add_error("code", "Mã không hợp lệ hoặc đã hết hạn. Hãy thử mã mới.")
    return render(request, "registration/otp_setup.html", {"form": form, "secret": secret, "otpauth_uri": otpauth_uri})


@never_cache
@login_required
def otp_verify(request):
    if not has_staff_role(request.user):
        return redirect("home")
    if request.user.is_verified():
        return redirect(_staff_destination(request))
    from .email_otp import send_code, verified_email

    can_use_email = verified_email(request.user)
    if request.method == "POST" and request.POST.get("action") == "send_email_otp":
        if not can_use_email:
            return HttpResponseForbidden("Tài khoản cần có email đã xác minh.")
        if not request.session.get("email_otp_pending"):
            request.session["email_otp_pending"] = True
            request.session["email_otp_next"] = request.session.get("staff_mfa_next") or reverse("staff_dashboard")
            try:
                send_code(request)
            except ValidationError as exc:
                messages.error(request, str(exc.messages[0]))
        return redirect("email_otp_verify")
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
                request.session.pop("email_otp_pending", None)
                return redirect(_staff_destination(request))
        form.add_error("code", "Mã không hợp lệ hoặc đã hết hạn. Hãy thử mã mới.")
    return render(request, "registration/otp_verify.html", {"form": form, "can_use_email": can_use_email})


def health(request):
    return JsonResponse({"status": "ok"})
