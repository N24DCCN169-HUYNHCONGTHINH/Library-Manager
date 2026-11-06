import re
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import ReaderRegistration, ReaderProfile, AccountSecurityEvent
from .lifecycle import set_account_active
from .registration import SALT

User = get_user_model()

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReaderRegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.admin = User.objects.create_user("review-admin", password="Strong!Test4821", is_staff=True)
        cls.admin.groups.add(Group.objects.get(name="system_admin"))
        cls.librarian = User.objects.create_user("review-librarian", is_staff=True)
        cls.librarian.groups.add(Group.objects.get(name="librarian"))

    def submit(self, **overrides):
        data = dict(username="new-reader", first_name="An", last_name="Nguyễn", email="an@example.test", password1="Strong!Test4821", password2="Strong!Test4821")
        data.update(overrides)
        return self.client.post(reverse("reader_signup"), data)

    def login_staff(self, user):
        self.client.force_login(user)
        device = TOTPDevice.objects.create(user=user, confirmed=True)
        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()

    def confirm(self, entry):
        token = signing.dumps({"id":entry.pk,"email":entry.user.email},salt=SALT)
        url = reverse("reader_signup_confirm",args=[token])
        self.assertEqual(self.client.get(url).status_code,200)
        entry.refresh_from_db()
        self.assertIsNone(entry.email_verified_at)
        return self.client.post(url)

    def review(self, entry, decision="approve"):
        return self.client.post(reverse("reader_registration_review",args=[entry.pk]),dict(decision=decision,reader_type="student",valid_until=(timezone.localdate()+timedelta(days=365)).isoformat(),reason="Đã kiểm tra thông tin hồ sơ tại thư viện"))

    def test_registration_verification_approval_and_otp_login(self):
        self.assertRedirects(self.submit(groups="system_admin",is_staff="on",is_active="on"),reverse("reader_signup_done"))
        entry = ReaderRegistration.objects.select_related("user").get()
        self.assertFalse(entry.user.is_active)
        self.assertFalse(entry.user.is_staff)
        self.assertFalse(entry.user.groups.exists())
        self.assertFalse(ReaderProfile.objects.filter(user=entry.user).exists())
        self.assertEqual(len(mail.outbox),1)
        self.client.post(reverse("login"),dict(username="new-reader",password="Strong!Test4821"))
        self.assertNotIn("_auth_user_id",self.client.session)
        self.confirm(entry)
        entry.user.refresh_from_db()
        self.assertTrue(entry.user.security_profile.email_is_verified)
        self.assertFalse(entry.user.is_active)
        self.login_staff(self.admin)
        self.assertRedirects(self.review(entry),reverse("reader_registration_list"))
        entry.refresh_from_db();entry.user.refresh_from_db()
        self.assertEqual(entry.status,"approved")
        self.assertTrue(entry.user.is_active)
        self.assertEqual(list(entry.user.groups.values_list("name",flat=True)),["reader"])
        self.assertTrue(entry.user.reader_profile.card_is_current)
        self.assertEqual(entry.reviewed_by,self.admin)
        self.assertTrue(AccountSecurityEvent.objects.filter(subject=entry.user,actor=self.admin,details__decision="approved").exists())
        self.assertContains(self.review(entry),"Yêu cầu đã được xử lý")
        self.assertEqual(ReaderProfile.objects.filter(user=entry.user).count(),1)
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("login"),dict(username="new-reader",password="Strong!Test4821")),reverse("email_otp_verify"))

    def test_only_system_admin_can_review_and_mfa_is_required(self):
        self.submit();entry=ReaderRegistration.objects.get()
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("reader_registration_list")),reverse("otp_setup"))
        self.login_staff(self.librarian)
        self.assertEqual(self.client.get(reverse("reader_registration_list")).status_code,403)
        self.assertEqual(self.review(entry).status_code,403)
        entry.refresh_from_db();self.assertEqual(entry.status,"pending")

    def test_unverified_email_cannot_be_approved_or_generically_activated(self):
        self.submit();entry=ReaderRegistration.objects.get()
        self.login_staff(self.admin)
        self.assertContains(self.review(entry),"Độc giả cần xác minh email")
        with self.assertRaises(ValidationError):
            set_account_active(subject=entry.user,actor=self.admin,is_active=True)
        entry.user.refresh_from_db();self.assertFalse(entry.user.is_active)

    def test_reject_keeps_account_inactive(self):
        self.submit();entry=ReaderRegistration.objects.get()
        self.login_staff(self.admin)
        self.assertEqual(self.review(entry,"reject").status_code,302)
        entry.refresh_from_db();entry.user.refresh_from_db()
        self.assertEqual(entry.status,"rejected")
        self.assertFalse(entry.user.is_active)
        self.assertFalse(entry.user.groups.exists())

    def test_bad_expired_and_tampered_email_tokens(self):
        self.submit();entry=ReaderRegistration.objects.get()
        url=reverse("reader_signup_confirm",args=["bad"])
        self.assertContains(self.client.post(url),"Liên kết không hợp lệ")
        token=signing.dumps({"id":entry.pk,"email":"wrong@example.test"},salt=SALT)
        self.assertEqual(self.client.post(reverse("reader_signup_confirm",args=[token])).status_code,404)
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp()-90000):
            token=signing.dumps({"id":entry.pk,"email":entry.user.email},salt=SALT)
        self.assertContains(self.client.post(reverse("reader_signup_confirm",args=[token])),"Liên kết không hợp lệ")

    def test_duplicate_invalid_password_honeypot_and_delivery_failure(self):
        self.submit()
        self.assertContains(self.submit(username="NEW-READER",email="other@example.test"),"Tên đăng nhập này đã được sử dụng")
        self.assertContains(self.submit(username="other-reader"),"Email này đã được sử dụng")
        self.submit(username="weak",email="weak@example.test",password1="123",password2="123")
        self.assertFalse(User.objects.filter(username="weak").exists())
        self.submit(username="bot",email="bot@example.test",website="spam")
        self.assertFalse(User.objects.filter(username="bot").exists())
        with patch("apps.core.registration._send_mail",side_effect=ValidationError("Lỗi gửi thư")):
            self.assertContains(self.submit(username="failed",email="failed@example.test"),"Lỗi gửi thư")
        self.assertFalse(User.objects.filter(username="failed").exists())

    @override_settings(REGISTRATION_HOURLY_LIMIT=5)
    def test_registration_limit_and_csrf(self):
        for i in range(5):
            self.assertEqual(self.submit(username=f"r{i}",email=f"r{i}@example.test").status_code,302)
        self.assertContains(self.submit(username="r6",email="r6@example.test"),"Bạn đã gửi nhiều yêu cầu")
        from django.test import Client
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse("reader_signup"),{}).status_code,403)

    def test_registration_pages_render_and_login_has_registration_link(self):
        self.assertContains(self.client.get(reverse("login")),reverse("reader_signup"))
        self.assertContains(self.client.get(reverse("reader_signup")),"password2")
        self.login_staff(self.admin)
        self.assertContains(self.client.get(reverse("reader_registration_list")),"Duyệt đăng ký độc giả")

    def test_invitation_cannot_bypass_public_review(self):
        from .models import AccountInvitation
        from .lifecycle import digest_token, accept_account_invitation
        self.submit();entry=ReaderRegistration.objects.get()
        AccountInvitation.objects.create(user=entry.user,invited_email=entry.user.email,token_digest=digest_token("bypass-token"),invited_by=self.admin,expires_at=timezone.now()+timedelta(hours=1))
        with self.assertRaises(ValidationError):
            accept_account_invitation("bypass-token","Strong!Test4821")
        entry.user.refresh_from_db();self.assertFalse(entry.user.is_active)

    def test_admin_can_resend_expired_confirmation_without_activating_account(self):
        self.submit();entry=ReaderRegistration.objects.get()
        self.login_staff(self.admin)
        url=reverse("reader_registration_review",args=[entry.pk])
        for i in range(3):
            self.assertEqual(self.client.post(url,{"action":"resend"}).status_code,302)
        self.assertEqual(len(mail.outbox),4)
        self.client.post(url,{"action":"resend"})
        self.assertEqual(len(mail.outbox),4)
        entry.user.refresh_from_db();self.assertFalse(entry.user.is_active)
