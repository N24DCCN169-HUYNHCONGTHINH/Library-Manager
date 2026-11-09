import re
from datetime import timedelta
from django.test import TestCase,override_settings,Client
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from .models import EmailLoginChallenge,EmailLoginDevice

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailOTPTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user("email-reader",email="reader@example.test",password="A-strong-pass-123")
        security=self.user.security_profile;security.verified_email=self.user.email;security.email_verified_at=timezone.now();security.save()
    def sign_in(self,client=None):
        client=client or self.client
        response=client.post(reverse("login"),{"username":self.user.username,"password":"A-strong-pass-123"})
        self.assertRedirects(response,reverse("email_otp_verify"))
        return re.search(r"Mã OTP đăng nhập: (\d{6})",mail.outbox[-1].body).group(1)
    def test_automatic_email_pending_blocks_direct_urls_and_code_is_single_use(self):
        code=self.sign_in()
        self.assertEqual(mail.outbox[-1].to,[self.user.email])
        challenge=EmailLoginChallenge.objects.get();self.assertNotIn(code,challenge.code_digest)
        self.assertRedirects(self.client.get(reverse("profile")),reverse("email_otp_verify"))
        self.assertRedirects(self.client.post(reverse("email_otp_verify"),{"code":code}),reverse("profile"))
        self.assertEqual(self.client.get(reverse("profile")).status_code,200)
        self.assertTrue(EmailLoginDevice.objects.filter(user=self.user).exists())
        challenge.refresh_from_db();self.assertIsNotNone(challenge.consumed_at)
    def test_five_failures_expiry_resend_throttle(self):
        code=self.sign_in();challenge=EmailLoginChallenge.objects.get()
        wrong="000000" if code!="000000" else "111111"
        for _ in range(5):self.client.post(reverse("email_otp_verify"),{"code":wrong})
        response=self.client.post(reverse("email_otp_verify"),{"code":code});self.assertEqual(response.status_code,200)
        self.assertTrue(self.client.session.get("email_otp_pending"))
        count=len(mail.outbox);self.client.post(reverse("email_otp_verify"),{"action":"resend"});self.assertEqual(len(mail.outbox),count)
        EmailLoginChallenge.objects.update(created_at=timezone.now()-timedelta(minutes=2))
        self.client.post(reverse("email_otp_verify"),{"action":"resend"});self.assertEqual(len(mail.outbox),count+1)
        EmailLoginChallenge.objects.filter(consumed_at__isnull=True).update(expires_at=timezone.now()-timedelta(seconds=1))
        new=re.search(r"Mã OTP đăng nhập: (\d{6})",mail.outbox[-1].body).group(1)
        self.assertEqual(self.client.post(reverse("email_otp_verify"),{"code":new}).status_code,200)
    def test_code_is_bound_to_login_session(self):
        code=self.sign_in();challenge=EmailLoginChallenge.objects.get()
        other=Client();other.force_login(self.user)
        session=other.session;session["email_otp_pending"]=True;session["email_otp_challenge"]=str(challenge.pk);session.save()
        self.assertEqual(other.post(reverse("email_otp_verify"),{"code":code}).status_code,200)
        self.assertTrue(other.session.get("email_otp_pending"))
    def test_unverified_address_never_receives_login_otp(self):
        security=self.user.security_profile;security.email_verified_at=None;security.save()
        self.client.post(reverse("login"),{"username":self.user.username,"password":"A-strong-pass-123"})
        self.assertEqual(len(mail.outbox),0)

    def test_email_otp_completes_before_forced_password_change_without_redirect_loop(self):
        security=self.user.security_profile;security.must_change_password=True;security.save()
        code=self.sign_in()
        self.assertContains(self.client.get(reverse("email_otp_verify")),"Kiểm tra email")
        response=self.client.post(reverse("email_otp_verify"),{"code":code})
        self.assertEqual(response.status_code,302)
        self.assertRedirects(self.client.get(reverse("profile")),reverse("password_change"))

    def test_staff_can_switch_from_authenticator_to_email(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        TOTPDevice.objects.create(user=self.user, confirmed=True)
        self.client.force_login(self.user)
        destination = reverse("staff_dashboard")
        session = self.client.session
        session["staff_mfa_next"] = destination
        session.save()

        verify_url = reverse("otp_verify")
        self.assertContains(self.client.get(verify_url), "send_email_otp")
        response = self.client.post(verify_url, {"action": "send_email_otp"})
        self.assertRedirects(response, reverse("email_otp_verify"))
        self.assertEqual(mail.outbox[-1].to, [self.user.email])
        code = re.search(r"([0-9]{6})", mail.outbox[-1].body).group(1)
        response = self.client.post(reverse("email_otp_verify"), {"code": code})
        self.assertRedirects(response, destination)
