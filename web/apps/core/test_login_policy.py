from io import StringIO

from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import AccountSecurityEvent


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountLockoutExceptionTests(TestCase):
    def setUp(self):
        call_command("setup_roles", stdout=StringIO())
        self.admin = get_user_model().objects.create_user("admin", password="Test-password-123!", is_staff=True)
        self.other = get_user_model().objects.create_user("other-admin", password="Test-password-123!", is_staff=True)
        for user in (self.admin, self.other):
            user.groups.add(Group.objects.get(name="library_manager"))
        TOTPDevice.objects.create(user=self.admin, name="Test device", confirmed=True)

    def enable(self):
        call_command("set_login_test_exception", username="admin", actor="admin", mode="enable",
                     reason="Chủ dự án đang kiểm thử", stdout=StringIO())

    def test_selected_admin_can_retry_but_still_needs_correct_password_and_mfa(self):
        self.enable()
        for _ in range(8):
            response = self.client.post(reverse("login"), {"username": "admin", "password": "wrong"})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("login"), {"username": "admin", "password": "Test-password-123!"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(self.client.get(reverse("staff_dashboard")), reverse("otp_verify"), fetch_redirect_response=False)
        self.assertTrue(AccountSecurityEvent.objects.filter(subject=self.admin, kind="lockout_exception").exists())

    def test_other_admin_still_locks_on_same_ip_and_existing_lock_is_cleared_only_for_target(self):
        for username in ("admin", "other-admin"):
            for _ in range(5):
                self.client.post(reverse("login"), {"username": username, "password": "wrong"})
        self.assertTrue(AccessAttempt.objects.filter(username="admin").exists())
        self.enable()
        self.assertFalse(AccessAttempt.objects.filter(username="admin").exists())
        self.assertTrue(AccessAttempt.objects.filter(username="other-admin").exists())
        self.assertEqual(self.client.post(reverse("login"), {"username": "other-admin", "password": "Test-password-123!"}).status_code, 429)
        self.assertEqual(self.client.post(reverse("login"), {"username": "admin", "password": "Test-password-123!"}).status_code, 302)

    def test_revoking_exception_restores_normal_lockout(self):
        self.enable()
        call_command("set_login_test_exception", username="admin", actor="admin", mode="disable", reason="Kết thúc thử", stdout=StringIO())
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "admin", "password": "wrong"})
        self.assertEqual(self.client.post(reverse("login"), {"username": "admin", "password": "Test-password-123!"}).status_code, 429)
