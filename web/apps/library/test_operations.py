from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.core.models import ReaderProfile, AccountSecurityEvent
from .test_circulation import CirculationFixtures
from .models import DamageCase, Fine, LibraryClosure, LoanNotification, LoanEvent
from .services import CirculationError, checkout_copy, refresh_overdue_loans, return_copy, reopen_reader


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OperationalCompletionTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()

    def test_approved_price_snapshot_survives_catalog_change_and_cap_review_is_once(self):
        self.book.replacement_price = 18000
        self.book.replacement_price_source = "Báo giá"
        self.book.replacement_price_checked_at = timezone.localdate()
        self.book.save()
        self.book.replacement_price_approved_by = self.staff
        self.book.replacement_price_approved_at = timezone.now()
        self.book.save()
        loan = checkout_copy("a", "COPY-1", self.staff)
        self.assertEqual(loan.replacement_price_snapshot, 18000)
        self.assertIn("captured_at", loan.calendar_snapshot)
        self.book.replacement_price = 1000
        self.book.save()
        self.assertIsNone(self.book.replacement_price_approved_at)
        loan.due_at = timezone.now() - timedelta(days=40)
        loan.save()
        refresh_overdue_loans()
        refresh_overdue_loans()
        self.assertEqual(Fine.objects.get().accrued_amount, 18000)
        self.assertEqual(LoanEvent.objects.filter(event_type="long_overdue_review").count(), 1)

    def test_unapproved_price_does_not_lower_cap(self):
        self.book.replacement_price = 1000
        self.book.save()
        loan = checkout_copy("a", "COPY-1", self.staff)
        self.assertIsNone(loan.replacement_price_snapshot)
        loan.due_at = timezone.now() - timedelta(days=40)
        loan.save()
        refresh_overdue_loans()
        self.assertEqual(Fine.objects.get().accrued_amount, 30000)

    def test_natural_wear_does_not_create_damage_debt_or_restriction(self):
        checkout_copy("a", "COPY-1", self.staff)
        return_copy("COPY-1", self.staff, "Bìa cũ do sử dụng", condition_kind="normal_wear")
        self.assertFalse(DamageCase.objects.exists())
        self.assertFalse(self.a.restrictions.exists())
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, "available")

    def test_reopening_requires_manager_no_overdue_and_records_actor(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        loan.due_at = timezone.now() - timedelta(days=8)
        loan.save()
        refresh_overdue_loans()
        with self.assertRaises(CirculationError):
            reopen_reader("a", self.staff, "Đã kiểm tra")
        self.staff.groups.add(Group.objects.get(name="library_manager"))
        self.staff = type(self.staff).objects.get(pk=self.staff.pk)
        with self.assertRaises(CirculationError):
            reopen_reader("a", self.staff, "Đã kiểm tra")
        return_copy("COPY-1", self.staff)
        Fine.objects.filter(loan=loan).update(accrued_amount=0)
        reopen_reader("a", self.staff, "Đã đối soát xong")
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, ReaderProfile.Status.ACTIVE)
        self.assertTrue(AccountSecurityEvent.objects.filter(subject=self.a.user, actor=self.staff).exists())

    def test_reminders_are_deduplicated_and_stale_due_date_is_not_sent(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        loan.due_at = timezone.now() + timedelta(days=3)
        loan.save()
        for _ in range(2):
            call_command("send_loan_notifications", stdout=StringIO())
        self.assertEqual(LoanNotification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        loan.due_at += timedelta(days=7)
        loan.save()
        call_command("send_loan_notifications", send=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)

    def test_reminders_send_once_and_do_not_replay(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        loan.due_at = timezone.now() - timedelta(days=3)
        loan.save()
        for _ in range(2):
            call_command("send_loan_notifications", send=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(LoanNotification.objects.get().attempts, 1)

    def test_failed_email_remains_retryable_without_leaking_error(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        loan.due_at = timezone.now()
        loan.save()
        with patch("apps.library.management.commands.send_loan_notifications.send_mail", side_effect=RuntimeError("private-key")):
            call_command("send_loan_notifications", send=True, stdout=StringIO())
        notice = LoanNotification.objects.get()
        self.assertIsNone(notice.sent_at)
        self.assertNotIn("private-key", notice.last_error)
        call_command("send_loan_notifications", send=True, stdout=StringIO())
        notice.refresh_from_db()
        self.assertIsNotNone(notice.sent_at)
        self.assertEqual(notice.attempts, 2)

    def test_notices_are_private_to_loan_owner(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        LoanNotification.objects.create(loan=loan, due_at=loan.due_at, reminder_date=timezone.localdate(), kind="due")
        self.client.force_login(self.b.user)
        response = self.client.get("/reader/")
        self.assertEqual(list(response.context["loan_notifications"]), [])
        self.client.force_login(self.a.user)
        response = self.client.get("/reader/")
        self.assertEqual(len(response.context["loan_notifications"]), 1)

    def test_confirmed_service_hours_are_explicit_and_idempotent(self):
        from django.contrib.admin.models import LogEntry
        from .models import LibraryHours
        self.staff.groups.add(Group.objects.get(name="library_manager"))
        call_command("configure_service_hours", actor=self.staff.username, stdout=StringIO())
        self.assertEqual(LibraryHours.objects.count(), 0)
        call_command("configure_service_hours", actor=self.staff.username, apply=True, stdout=StringIO())
        call_command("configure_service_hours", actor=self.staff.username, apply=True, stdout=StringIO())
        self.assertEqual(LibraryHours.objects.count(), 7)
        self.assertEqual(LogEntry.objects.count(), 7)
        self.assertEqual(LibraryHours.objects.get(weekday=6).closes_at.hour, 16)

    def test_quote_page_requires_manager_and_never_creates_a_charge(self):
        from .views import damage_quote
        from .models import FinePayment
        request = RequestFactory().post("/library/staff/damage/quote/", {
            "method": "domestic_cash", "reference_price": "100000", "multiplier": "1.5", "source": "Giá bìa và quyết định"})
        request.user = self.staff
        request.user.is_verified = lambda: True
        self.assertEqual(damage_quote(request).status_code, 403)
        self.staff.groups.add(Group.objects.get(name="library_manager"))
        request.user = type(self.staff).objects.get(pk=self.staff.pk)
        request.user.is_verified = lambda: True
        response = damage_quote(request)
        self.assertContains(response, "160000")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertFalse(Fine.objects.exists())
        self.assertFalse(FinePayment.objects.exists())
