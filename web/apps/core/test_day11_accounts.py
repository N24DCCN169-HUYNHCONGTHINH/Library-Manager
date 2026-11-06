from datetime import timedelta
from io import StringIO
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .lifecycle import issue_account_invitation, accept_account_invitation, set_account_active


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class Day11AccountJourneyTests(TestCase):
    def setUp(self):
        call_command("setup_roles", stdout=StringIO())
        self.manager = get_user_model().objects.create_user("journey-manager")
        self.manager.groups.add(Group.objects.get(name="library_manager"))
        self.password = "Reader-test-Only-1287!"
        request = RequestFactory().get("/", HTTP_HOST="localhost")
        self.user, self.invitation = issue_account_invitation(actor=self.manager, request=request,
            username="journey-reader", email="reader@example.invalid", reader_number="JOURNEY-1", reader_type="student",
            valid_from=timezone.localdate(), valid_until=timezone.localdate() + timedelta(days=30))
        self.token = re.search(r"/accounts/invitation/([^/\s]+)/", mail.outbox[-1].body).group(1)

    def activate(self):
        response = self.client.post(reverse("account_invite_accept", args=[self.token]),
            {"new_password1": self.password, "new_password2": self.password})
        self.assertRedirects(response, reverse("login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.security_profile.email_is_verified)
        self.assertFalse(self.user.reader_profile.membership_verified)
        self.login_reader()

    def login_reader(self):
        response = self.client.post(reverse("login"), {"username": self.user.username, "password": self.password})
        self.assertRedirects(response, reverse("home"))

    def test_activation_email_change_and_account_disable_reactivate(self):
        self.activate()
        with self.assertRaises(ValidationError):
            accept_account_invitation(self.token, self.password)
        response = self.client.post(reverse("email_change_request"),
            {"email": "changed@example.invalid", "current_password": self.password})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "reader@example.invalid")
        message = next(message for message in reversed(mail.outbox) if message.to == ["changed@example.invalid"])
        token = re.search(r"/accounts/email/confirm/([^/\s]+)/", message.body).group(1)
        response = self.client.get(reverse("email_change_confirm", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "reader@example.invalid")
        response = self.client.post(reverse("email_change_confirm", args=[token]))
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "changed@example.invalid")
        self.assertTrue(self.user.security_profile.email_is_verified)
        set_account_active(subject=self.user, actor=self.manager, is_active=False, reason="Kiểm thử khóa")
        self.assertEqual(self.client.get(reverse("reader_portal")).status_code, 302)
        set_account_active(subject=self.user, actor=self.manager, is_active=True, reason="Kiểm thử mở lại")
        self.login_reader()
        self.assertEqual(self.client.get(reverse("reader_portal")).status_code, 200)

    def test_expired_invitation_cannot_activate_or_set_password(self):
        self.invitation.expires_at = timezone.now() - timedelta(seconds=1)
        self.invitation.save()
        response = self.client.post(reverse("account_invite_accept", args=[self.token]),
            {"new_password1": self.password, "new_password2": self.password})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())

    def test_wrong_current_password_cannot_change_email(self):
        self.activate()
        previous_count = len(mail.outbox)
        response = self.client.post(reverse("email_change_request"),
            {"email": "attacker@example.invalid", "current_password": "wrong-password"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), previous_count)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "reader@example.invalid")

    def test_verify_existing_unverified_email_requires_confirmation(self):
        self.activate()
        security = self.user.security_profile
        security.email_verified_at = None
        security.verified_email = ""
        security.save()
        count = len(mail.outbox)
        response = self.client.post(reverse("email_change_request"),
            {"email": self.user.email, "current_password": self.password})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), count + 1)
        token = re.search(r"/accounts/email/confirm/([^/\s]+)/", mail.outbox[-1].body).group(1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.security_profile.email_is_verified)
        self.client.get(reverse("email_change_confirm", args=[token]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.security_profile.email_is_verified)
        self.client.post(reverse("email_change_confirm", args=[token]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.security_profile.email_is_verified)
        count = len(mail.outbox)
        response = self.client.post(reverse("email_change_request"),
            {"email": self.user.email, "current_password": self.password})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), count)
