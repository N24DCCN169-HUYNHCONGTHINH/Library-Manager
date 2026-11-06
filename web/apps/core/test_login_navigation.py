from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LoginNavigationTests(TestCase):
    def setUp(self):
        call_command("setup_roles", stdout=StringIO())
        self.user = get_user_model().objects.create_user("desk-test", password="Test-password-only-123!")
        self.user.groups.add(Group.objects.get(name="library_manager"))
        self.device = TOTPDevice.objects.create(user=self.user, confirmed=True)

    def test_password_then_mfa_then_original_workspace(self):
        destination = reverse("library:circulation_desk") + "?tab=reservations"
        response = self.client.post(reverse("login"), {"username": self.user.username, "password": "Test-password-only-123!", "next": destination})
        self.assertRedirects(response, reverse("otp_verify"), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("otp_verify")), "Mật khẩu đã được xác nhận")
        with patch.object(TOTPDevice, "verify_token", return_value=True):
            response = self.client.post(reverse("otp_verify"), {"device_id": self.device.pk, "code": "123456"})
        self.assertRedirects(response, destination, fetch_redirect_response=False)
        self.assertEqual(self.client.get(destination).status_code, 200)

    def test_external_destination_is_not_used_after_verification(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["staff_mfa_next"] = "https://outside.invalid/phishing"
        session.save()
        with patch.object(TOTPDevice, "verify_token", return_value=True):
            response = self.client.post(reverse("otp_verify"), {"device_id": self.device.pk, "code": "123456"})
        self.assertRedirects(response, reverse("staff_dashboard"), fetch_redirect_response=False)
