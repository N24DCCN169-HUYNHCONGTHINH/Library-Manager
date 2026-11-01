from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import AccountSecurity


User = get_user_model()


class AccountAccessAcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.reader = cls.make_user("reader-test", "reader")
        cls.staff = cls.make_user("staff-test", "circulation_staff", is_staff=True)

    @classmethod
    def make_user(cls, username, role, is_staff=False, is_active=True):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Test-password-123!",
            is_staff=is_staff,
            is_active=is_active,
        )
        user.groups.add(Group.objects.get(name=role))
        return user

    def test_login_accepts_valid_credentials_and_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.reader.username, "password": "Test-password-123!"},
        )
        self.assertRedirects(response, reverse("home"))

        self.client.logout()
        response = self.client.post(
            reverse("login"),
            {"username": self.reader.username, "password": "incorrect"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_inactive_account_cannot_log_in(self):
        inactive = self.make_user("inactive-test", "reader", is_active=False)

        response = self.client.post(
            reverse("login"),
            {"username": inactive.username, "password": "Test-password-123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_reader_cannot_open_staff_dashboard(self):
        self.client.force_login(self.reader)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertRedirects(response, reverse("home"))

    def test_staff_must_enroll_totp_before_opening_staff_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertRedirects(response, reverse("otp_setup"))

    def test_django_admin_rejects_staff_without_verified_totp(self):
        self.client.force_login(self.staff)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_enrolled_staff_is_sent_to_otp_verification_before_dashboard(self):
        self.client.force_login(self.staff)
        TOTPDevice.objects.create(user=self.staff, name="test device", key="a" * 40, confirmed=True)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertRedirects(response, reverse("otp_verify"))

    def test_staff_can_enroll_a_totp_device_and_open_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("otp_setup"))
        self.assertEqual(response.status_code, 200)
        device = TOTPDevice.objects.get(user=self.staff, confirmed=False)
        token = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift).token()

        response = self.client.post(reverse("otp_setup"), {"code": f"{token:06d}"})

        self.assertRedirects(response, reverse("staff_dashboard"))
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertTrue(response.wsgi_request.user.is_verified())

    def test_temporary_password_blocks_access_until_changed(self):
        security = AccountSecurity.objects.get(user=self.reader)
        security.must_change_password = True
        security.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(self.reader)

        response = self.client.get(reverse("home"))

        self.assertRedirects(response, reverse("password_change"))

    def test_setup_roles_is_idempotent_and_keeps_reader_out_of_staff_permissions(self):
        call_command("setup_roles", stdout=StringIO())

        reader_role = Group.objects.get(name="reader")
        circulation_role = Group.objects.get(name="circulation_staff")
        self.assertFalse(reader_role.permissions.exists())
        self.assertTrue(circulation_role.permissions.filter(codename="checkout_loan").exists())
        self.assertFalse(circulation_role.permissions.filter(codename="change_book").exists())
