from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import AccountInvitation, AccountSecurityEvent, ReaderProfile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ReaderManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.manager = cls.make_user("manager", "library_manager")
        cls.reader = cls.make_user("reader", "reader")
        cls.today = timezone.localdate()
        cls.profile = ReaderProfile.objects.create(
            user=cls.reader, reader_number="RD-1", reader_type="student", valid_from=cls.today,
            valid_until=cls.today + timedelta(days=365), membership_verified=True,
        )

    @classmethod
    def make_user(cls, name, role):
        user = get_user_model().objects.create_user(name, email=f"{name}@example.invalid")
        user.groups.add(Group.objects.get(name=role))
        return user

    def login(self, user=None, verified=True, client=None):
        user = user or self.manager
        client = client or self.client
        client.force_login(user)
        if verified:
            device = TOTPDevice.objects.create(user=user, confirmed=True)
            session = client.session
            session["otp_device_id"] = device.persistent_id
            session.save()

    def invitation(self, **changes):
        data = {"username": "new-reader", "email": "new@example.invalid", "first_name": "An",
                "last_name": "Nguyễn", "role": "reader", "reader_number": "RD-2", "reader_type": "student",
                "valid_from": self.today.isoformat(), "valid_until": (self.today + timedelta(days=365)).isoformat()}
        return data | changes

    def edit_data(self, **changes):
        return {"reader_number": "RD-1", "reader_type": "faculty", "valid_from": self.today.isoformat(),
                "valid_until": (self.today + timedelta(days=30)).isoformat(), "status": "active",
                "reason": "Cập nhật thời hạn thẻ"} | changes

    def test_invite_creates_pending_reader_and_email(self):
        self.login()
        response = self.client.post(reverse("reader_add"), self.invitation())
        self.assertRedirects(response, reverse("reader_list"))
        user = get_user_model().objects.get(username="new-reader")
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["reader"])
        self.assertFalse(user.reader_profile.membership_verified)
        self.assertEqual(AccountInvitation.objects.get(user=user).invited_by, self.manager)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/invitation/", mail.outbox[0].body)

    def test_invalid_invitations_leave_no_accounts(self):
        self.login()
        for changes in [{"username": "reader"}, {"email": "READER@example.invalid"},
                        {"reader_number": "RD-1"}, {"reader_number": "bad code!"},
                        {"valid_until": (self.today - timedelta(days=1)).isoformat()},
                        {"role": "library_manager"}, {"reader_type": "invalid"}]:
            response = self.client.post(reverse("reader_add"), self.invitation(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 2)
        self.assertEqual(AccountInvitation.objects.count(), 0)

    def test_mail_failure_rolls_back_account_and_profile(self):
        self.login()
        with patch("apps.core.lifecycle.send_mail", side_effect=RuntimeError("mail unavailable")):
            response = self.client.post(reverse("reader_add"), self.invitation())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(get_user_model().objects.filter(username="new-reader").exists())
        self.assertEqual(ReaderProfile.objects.count(), 1)
        self.assertEqual(AccountInvitation.objects.count(), 0)

    def test_edit_records_actor_reason_and_ignores_security_fields(self):
        self.login()
        response = self.client.post(reverse("reader_edit", args=[self.profile.pk]), self.edit_data(
            status="suspended", user=self.manager.pk, membership_verified="", is_superuser="on", email="changed@example.invalid"))
        self.assertRedirects(response, reverse("reader_detail", args=[self.profile.pk]))
        self.profile.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.profile.status, "suspended")
        self.assertEqual(self.profile.user, self.reader)
        self.assertTrue(self.profile.membership_verified)
        self.assertFalse(self.reader.is_superuser)
        self.assertTrue(self.reader.is_active)
        self.assertEqual(self.reader.email, "reader@example.invalid")
        event = AccountSecurityEvent.objects.get(kind="membership_changed")
        self.assertEqual(event.actor, self.manager)
        self.assertEqual(event.reason, "Cập nhật thời hạn thẻ")
        self.assertEqual(event.details["before"]["status"], "active")
        self.assertEqual(event.details["after"]["status"], "suspended")

    def test_invalid_edit_and_missing_reason_do_not_save(self):
        self.login()
        for changes in [{"valid_until": "2000-01-01"}, {"reader_number": "bad code"}, {"reason": " "}]:
            response = self.client.post(reverse("reader_edit", args=[self.profile.pk]), self.edit_data(**changes))
            self.assertTrue(response.context["form"].errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.reader_type, "student")
        self.assertFalse(AccountSecurityEvent.objects.filter(kind="membership_changed").exists())

    def test_edit_duplicate_number_does_not_save(self):
        self.login()
        self.client.post(reverse("reader_add"), self.invitation())
        response = self.client.post(reverse("reader_edit", args=[self.profile.pk]), self.edit_data(reader_number="RD-2"))
        self.assertIn("reader_number", response.context["form"].errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.reader_number, "RD-1")

    def test_search_filter_and_pagination(self):
        self.login()
        users = [get_user_model().objects.create_user(f"page-{i}") for i in range(26)]
        ReaderProfile.objects.bulk_create([
            ReaderProfile(user=user, reader_number=f"PAGE-{i:02}", reader_type="student", status="expired",
                          valid_from=self.today, valid_until=self.today) for i, user in enumerate(users)
        ])
        response = self.client.get(reverse("reader_list"), {"q": "PAGE-", "status": "expired", "page": 2})
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(len(response.context["page_obj"]), 1)
        self.assertContains(response, "PAGE-25")
        response = self.client.get(reverse("reader_list"), {"q": "reader@example.invalid", "page": "bad"})
        self.assertContains(response, "RD-1")
        response = self.client.get(reverse("reader_list"), {"q": "missing"})
        self.assertContains(response, "Không tìm thấy độc giả")

    def test_roles_mfa_and_direct_posts(self):
        self.assertEqual(self.client.get(reverse("reader_list")).status_code, 302)
        self.login(verified=False)
        self.assertRedirects(self.client.get(reverse("reader_list")), reverse("otp_setup"))
        for role in ["cataloger", "system_admin", "circulation_staff", "librarian", "reader"]:
            user = self.make_user(f"role-{role}", role)
            self.login(user)
            expected_list = 200 if role in {"circulation_staff", "librarian"} else (302 if role == "reader" else 403)
            self.assertEqual(self.client.get(reverse("reader_list")).status_code, expected_list)
            expected_write = 302 if role in {"reader", "circulation_staff", "librarian"} else 403
            payload=self.invitation(username="new-"+role,email=role+"@example.invalid",reader_number="NEW-"+role)
            self.assertEqual(self.client.post(reverse("reader_add"), payload).status_code, expected_write)
            self.assertEqual(self.client.post(reverse("reader_edit", args=[self.profile.pk]), self.edit_data()).status_code, expected_write)
        self.assertEqual(ReaderProfile.objects.count(), 3)

    def test_change_permission_does_not_grant_suspend_permission(self):
        user = self.make_user("limited-editor", "cataloger")
        user.user_permissions.add(Permission.objects.get(codename="change_readerprofile"))
        self.login(user)
        self.client.post(reverse("reader_edit", args=[self.profile.pk]), self.edit_data(status="suspended"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.reader_type, "faculty")
        self.assertEqual(self.profile.status, "active")

    def test_csrf_required_for_create(self):
        client = Client(enforce_csrf_checks=True)
        self.login(client=client)
        self.assertEqual(client.post(reverse("reader_add"), self.invitation()).status_code, 403)

    def test_manager_can_render_forms_and_missing_profile_is_404(self):
        self.login()
        self.assertContains(self.client.get(reverse("reader_add")), "Tạo và gửi lời mời")
        self.assertContains(self.client.get(reverse("reader_edit", args=[self.profile.pk])), "Lý do cập nhật")
        self.assertEqual(self.client.get(reverse("reader_edit", args=[999999])).status_code, 404)
