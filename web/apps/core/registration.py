"""Public reader enrollment, email ownership and System Admin review."""
import secrets
from datetime import timedelta
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from .models import ReaderRegistration, ReaderProfile, AccountSecurity, AccountSecurityEvent
from .lifecycle import _send_mail, record_security_event
from .views import staff_mfa_required

User = get_user_model()
SALT = "library.reader-registration.email.v1"

class ReaderSignupForm(UserCreationForm):
    first_name = forms.CharField(label="Tên", max_length=150)
    last_name = forms.CharField(label="Họ và tên đệm", max_length=150)
    email = forms.EmailField(label="Email", max_length=254)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = ("last_name", "first_name", "username", "email")

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=value).exists():
            raise ValidationError("Tên đăng nhập này đã được sử dụng.")
        return value

    def clean_email(self):
        value = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise ValidationError("Email này đã được sử dụng. Hãy đăng nhập hoặc khôi phục mật khẩu.")
        return value

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Không thể gửi yêu cầu đăng ký.")
        return ""

class RegistrationReviewForm(forms.Form):
    decision = forms.ChoiceField(label="Quyết định", choices=[("approve", "Duyệt đăng ký"), ("reject", "Từ chối")])
    reader_type = forms.ChoiceField(label="Loại độc giả", choices=ReaderProfile.ReaderType.choices)
    valid_until = forms.DateField(label="Thẻ có hiệu lực đến", widget=forms.DateInput(attrs={"type":"date"}, format="%Y-%m-%d"))
    reason = forms.CharField(label="Căn cứ / lý do xử lý", max_length=300, widget=forms.Textarea(attrs={"rows":3}))

    def clean(self):
        data = super().clean()
        if data.get("decision") == "approve" and data.get("valid_until") and data["valid_until"] < timezone.localdate():
            self.add_error("valid_until", "Ngày hết hạn không được trước hôm nay.")
        return data

@never_cache
def signup(request):
    if request.user.is_authenticated:
        return redirect("profile")
    form = ReaderSignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        source = salted_hmac("registration-source", request.META.get("REMOTE_ADDR", "unknown")).hexdigest()
        if ReaderRegistration.objects.filter(source_digest=source, submitted_at__gte=timezone.now()-timedelta(hours=1)).count() >= getattr(settings, "REGISTRATION_HOURLY_LIMIT", 30):
            form.add_error(None, "Bạn đã gửi nhiều yêu cầu. Vui lòng thử lại sau một giờ.")
        else:
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.is_staff = user.is_superuser = False
                    user.save()
                    AccountSecurity.objects.get_or_create(user=user)
                    registration = ReaderRegistration.objects.create(user=user, source_digest=source)
                    token = signing.dumps({"id":registration.pk, "email":user.email}, salt=SALT)
                    link = request.build_absolute_uri(reverse("reader_signup_confirm", args=[token]))
                    if _send_mail("Xác minh đăng ký độc giả · Library Hub", f"Chào {user.get_full_name()},\n\nBạn vừa đăng ký tài khoản độc giả. Mở liên kết sau và bấm xác nhận trong vòng 24 giờ:\n{link}\n\nSau khi xác minh email, tài khoản vẫn cần System Admin phê duyệt. Nếu không phải bạn đăng ký, hãy bỏ qua thư này.", user.email) != 1:
                        raise ValidationError("Không gửi được email xác minh. Vui lòng thử lại.")
                    record_security_event(user, AccountSecurityEvent.Kind.ACCOUNT_CREATED, details={"source":"public_registration", "registration_id":registration.pk})
                return redirect("reader_signup_done")
            except ValidationError as exc:
                form.add_error(None, exc)
            except IntegrityError:
                form.add_error(None, "Thông tin tài khoản đã được sử dụng. Vui lòng kiểm tra lại.")
    return render(request, "registration/signup.html", {"form":form})

@never_cache
def signup_done(request):
    return render(request, "registration/signup_done.html")

@never_cache
def confirm_signup(request, token):
    form = forms.Form(request.POST if request.method == "POST" else None)
    confirmed = False
    try:
        payload = signing.loads(token, salt=SALT, max_age=86400)
        registration = get_object_or_404(ReaderRegistration, pk=payload["id"], user__email=payload["email"])
        if request.method == "POST":
            with transaction.atomic():
                registration = ReaderRegistration.objects.select_for_update().get(pk=registration.pk)
                if registration.user.email != payload["email"]:
                    raise ValidationError("Email tài khoản đã thay đổi. Hãy yêu cầu gửi lại liên kết xác minh.")
                if registration.status != ReaderRegistration.Status.PENDING:
                    raise ValidationError("Yêu cầu này đã được xử lý.")
                if not registration.email_verified_at:
                    registration.email_verified_at = timezone.now()
                    registration.save(update_fields=["email_verified_at"])
                    AccountSecurity.objects.update_or_create(user=registration.user, defaults={"verified_email":registration.user.email,"email_verified_at":registration.email_verified_at})
                    record_security_event(registration.user, AccountSecurityEvent.Kind.EMAIL_VERIFIED, details={"source":"public_registration"})
                confirmed = True
    except (signing.BadSignature, KeyError):
        form.add_error(None, "Liên kết không hợp lệ hoặc đã quá 24 giờ. Vui lòng liên hệ thư viện để được hỗ trợ.")
    except ValidationError as exc:
        form.add_error(None, exc)
    return render(request, "registration/signup_confirm.html", {"form":form,"confirmed":confirmed})

def may_review(user):
    return user.is_superuser or (user.groups.filter(name="system_admin").exists() and user.has_perm("core.approve_reader_registration"))

@never_cache
@staff_mfa_required
def registration_list(request):
    if not may_review(request.user): return HttpResponseForbidden()
    status = request.GET.get("status", "pending")
    if status not in ReaderRegistration.Status.values: status = "pending"
    entries = ReaderRegistration.objects.select_related("user", "reviewed_by").filter(status=status)
    return render(request, "core/registration_list.html", {"page_obj":Paginator(entries,20).get_page(request.GET.get("page")),"statuses":ReaderRegistration.Status.choices,"selected_status":status})

@never_cache
@staff_mfa_required
def registration_review(request, registration_id):
    if not may_review(request.user): return HttpResponseForbidden()
    entry = get_object_or_404(ReaderRegistration.objects.select_related("user", "reviewed_by"), pk=registration_id)
    if request.method == "POST" and request.POST.get("action") == "resend":
        try:
            with transaction.atomic():
                entry = ReaderRegistration.objects.select_for_update().select_related("user").get(pk=entry.pk)
                if entry.status != "pending" or entry.user.security_profile.email_is_verified:
                    raise ValidationError("Hồ sơ không cần gửi lại thư xác minh.")
                if AccountSecurityEvent.objects.filter(subject=entry.user, details__registration_confirmation_sent=entry.pk, occurred_at__gte=timezone.now()-timedelta(hours=1)).count() >= 3:
                    raise ValidationError("Đã gửi lại 3 lần trong một giờ. Vui lòng chờ trước khi gửi tiếp.")
                token = signing.dumps({"id":entry.pk,"email":entry.user.email},salt=SALT)
                link = request.build_absolute_uri(reverse("reader_signup_confirm",args=[token]))
                if _send_mail("Xác minh đăng ký độc giả · Library Hub", f"Thư viện gửi lại liên kết xác minh theo yêu cầu hỗ trợ. Mở và xác nhận trong 24 giờ:\n{link}\nTài khoản vẫn cần System Admin phê duyệt.", entry.user.email) != 1:
                    raise ValidationError("Chưa gửi được thư xác minh.")
                record_security_event(entry.user, AccountSecurityEvent.Kind.SYSTEM_OPERATION, request.user, {"registration_confirmation_sent":entry.pk}, reason="Gửi lại liên kết xác minh đăng ký")
            messages.success(request,"Đã gửi lại thư xác minh đăng ký.")
        except ValidationError as exc:
            messages.error(request,exc.messages[0])
        return redirect("reader_registration_review",registration_id=entry.pk)
    form = RegistrationReviewForm(request.POST if request.method == "POST" else None, initial={"reader_type":"student", "valid_until":timezone.localdate()+timedelta(days=365)})
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                entry = ReaderRegistration.objects.select_for_update().get(pk=entry.pk)
                user = User.objects.select_for_update().get(pk=entry.user_id)
                if entry.status != ReaderRegistration.Status.PENDING:
                    raise ValidationError("Yêu cầu đã được xử lý, không thể duyệt lại.")
                approved = form.cleaned_data["decision"] == "approve"
                if approved and user.security_profile.archived_was_active is not None:
                    raise ValidationError("Hãy khôi phục tài khoản từ mục Đã xóa trước.")
                if approved and (not entry.email_verified_at or not user.security_profile.email_is_verified):
                    raise ValidationError("Độc giả cần xác minh email trước khi được duyệt.")
                if user.is_active or user.is_staff or user.is_superuser or user.groups.exists():
                    raise ValidationError("Tài khoản đã thay đổi. Hãy kiểm tra trong quản lý tài khoản.")
                if approved:
                    user.groups.add(Group.objects.get(name="reader"))
                    ReaderProfile.objects.create(user=user, reader_number="R-"+secrets.token_hex(6).upper(), reader_type=form.cleaned_data["reader_type"], valid_from=timezone.localdate(), valid_until=form.cleaned_data["valid_until"], membership_verified=True, membership_verified_at=timezone.now(), membership_verified_by=request.user, verification_method="admin_registration", requires_paid_plan=True)
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                entry.status = "approved" if approved else "rejected"
                entry.reviewed_by = request.user
                entry.reviewed_at = timezone.now()
                entry.review_reason = form.cleaned_data["reason"]
                entry.save(update_fields=["status","reviewed_by","reviewed_at","review_reason"])
                record_security_event(user, AccountSecurityEvent.Kind.SYSTEM_OPERATION, request.user, {"registration_id":entry.pk,"decision":entry.status}, reason=entry.review_reason)
            messages.success(request, "Đã duyệt tài khoản độc giả." if approved else "Đã từ chối yêu cầu đăng ký.")
            return redirect("reader_registration_list")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "core/registration_review.html", {"entry":entry,"form":form})
