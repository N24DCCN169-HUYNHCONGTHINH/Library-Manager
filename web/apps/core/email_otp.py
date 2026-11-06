import hashlib, hmac, secrets
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django_otp import login as otp_login
from .models import EmailLoginChallenge, EmailLoginDevice, AccountSecurityEvent
from .lifecycle import _send_mail, record_security_event


def digest(value):
    return hmac.new(settings.SECRET_KEY.encode(),str(value).encode(),hashlib.sha256).hexdigest()

def verified_email(user):
    security=getattr(user,"security_profile",None)
    return bool(security and security.email_is_verified)

@transaction.atomic
def send_code(request):
    from django.contrib.auth import get_user_model
    user=get_user_model().objects.select_for_update().get(pk=request.user.pk)
    if not verified_email(user): raise ValidationError("Cần xác minh email trước khi dùng OTP email.")
    now=timezone.now(); recent=EmailLoginChallenge.objects.filter(user=user,created_at__gt=now-timedelta(hours=1))
    if recent.filter(created_at__gt=now-timedelta(seconds=60)).exists():
        raise ValidationError("Chờ ít nhất 60 giây trước khi gửi lại mã.")
    if recent.count()>=5: raise ValidationError("Đã đạt giới hạn 5 lần gửi trong một giờ. Hãy thử lại sau hoặc dùng ứng dụng xác thực.")
    if not request.session.session_key: request.session.save()
    code=f"{secrets.randbelow(1000000):06d}"
    challenge=EmailLoginChallenge(user=user,email=user.email,session_digest=digest(request.session.session_key),expires_at=now+timedelta(minutes=5))
    challenge.code_digest=digest(f"{challenge.pk}:{code}")
    _send_mail("Library Hub — Mã xác minh đăng nhập",f"Mã OTP đăng nhập: {code}. Mã có hiệu lực 5 phút và chỉ dùng một lần. Không chia sẻ mã này. Nếu không phải bạn đăng nhập, hãy đổi mật khẩu.",recipient=user.email,fail_silently=False)
    EmailLoginChallenge.objects.filter(user=user,consumed_at__isnull=True).update(consumed_at=now)
    challenge.save();request.session["email_otp_challenge"]=str(challenge.pk)
    return challenge

@transaction.atomic
def verify_code(request, code):
    challenge=EmailLoginChallenge.objects.select_for_update().filter(pk=request.session.get("email_otp_challenge"),user=request.user).first()
    now=timezone.now()
    if not challenge or challenge.consumed_at or challenge.expires_at<=now or challenge.attempts>=5:
        return False
    if not verified_email(request.user) or challenge.email.casefold()!=request.user.email.casefold() or not hmac.compare_digest(challenge.session_digest,digest(request.session.session_key)):
        return False
    challenge.attempts+=1
    good=hmac.compare_digest(challenge.code_digest,digest(f"{challenge.pk}:{code}"))
    if good or challenge.attempts>=5: challenge.consumed_at=now
    challenge.save(update_fields=["attempts","consumed_at"])
    if good:
        device,_=EmailLoginDevice.objects.get_or_create(user=request.user,email=request.user.email,defaults={"name":"Email đã xác minh","confirmed":True})
        otp_login(request,device);request.session.pop("email_otp_pending",None);request.session.pop("email_otp_challenge",None)
        record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,reason="Đăng nhập đã xác minh OTP email")
    return good

@never_cache
@login_required
def verify_email_login(request):
    from .views import OTPCodeForm
    if not request.session.get("email_otp_pending"):
        return redirect("profile")
    form=OTPCodeForm(request.POST if request.method=="POST" and request.POST.get("action")!="resend" else None)
    if request.method=="POST":
        if request.POST.get("action")=="resend":
            try: send_code(request)
            except ValidationError as exc: messages.error(request,str(exc.messages[0]))
            else: messages.success(request,"Đã gửi mã mới đến email đã đăng ký.")
        elif form.is_valid():
            if verify_code(request,form.cleaned_data["code"]):
                destination=request.session.pop("email_otp_next",reverse("profile"))
                if not url_has_allowed_host_and_scheme(destination,{request.get_host()},require_https=request.is_secure()): destination=reverse("profile")
                return redirect(destination)
            form.add_error("code","Mã không hợp lệ, đã dùng, hết hạn hoặc đã nhập sai 5 lần.")
    email=request.user.email;parts=email.split("@")
    masked=parts[0][:2]+"***@"+parts[-1] if len(parts)==2 else "email đã đăng ký"
    return render(request,"registration/email_otp.html",{"form":form,"masked_email":masked})
