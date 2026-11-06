from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.core.models import ReaderProfile
from .models import (Book, BookCopy, CirculationPolicy, Fine, LibraryClosure, LibraryHours,
                     Loan, LoanEvent, LoanRenewal, Reservation, ReservationNotification)
from .services import (CirculationError, _hold_expiry, checkout_copy, return_copy, renew_loan,
                       place_reservation, cancel_reservation, expire_ready_reservations, allocate_next_reservation)


class CirculationFixtures:
    def setup_circulation_data(self):
        call_command("setup_roles", stdout=StringIO())
        self.staff = get_user_model().objects.create_user("desk", email="desk@example.invalid")
        self.staff.groups.add(Group.objects.get(name="circulation_staff"))
        self.a = self.make_reader("a")
        self.b = self.make_reader("b")
        self.c = self.make_reader("c")
        self.book = Book.objects.create(catalog_number="DAY5", title="Sách lưu thông", created_by=self.staff, updated_by=self.staff)
        self.copy = self.make_copy("COPY-1")
        self.policy = CirculationPolicy.objects.create(reader_type="student", material_type="general",
            effective_from=timezone.localdate() - timedelta(days=1), created_by=self.staff,
            max_active_loans=1, loan_days=14, max_renewals=1, renewal_days=7)

    def make_reader(self, name):
        user = get_user_model().objects.create_user(name, email=f"{name}@example.invalid")
        user.groups.add(Group.objects.get(name="reader"))
        return ReaderProfile.objects.create(user=user, reader_number=name, reader_type="student",
            valid_from=timezone.localdate() - timedelta(days=1), valid_until=timezone.localdate() + timedelta(days=365),
            membership_verified=True)

    def make_copy(self, barcode):
        return BookCopy.objects.create(book=self.book, barcode=barcode, created_by=self.staff)

    def make_renewable(self, loan):
        loan.due_at = timezone.now() + timedelta(hours=24)
        loan.save(update_fields=["due_at"])
        return loan


class CirculationTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()

    def test_checkout_snapshots_policy_and_due_date(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, "on_loan")
        self.assertEqual(loan.max_renewals_snapshot, 1)
        self.assertEqual(loan.renewal_days_snapshot, 7)
        local = timezone.localtime(loan.due_at)
        self.assertEqual(local.date(), timezone.localdate() + timedelta(days=14))
        self.assertEqual((local.hour, local.minute), (23, 59))
        self.assertEqual(LoanEvent.objects.get().event_type, "checkout")

    def test_checkout_replay_and_key_mismatch(self):
        key = uuid4()
        first = checkout_copy("a", "COPY-1", self.staff, key)
        self.assertEqual(checkout_copy("a", "COPY-1", self.staff, key).pk, first.pk)
        with self.assertRaises(CirculationError):
            checkout_copy("b", "COPY-1", self.staff, key)
        self.assertEqual(Loan.objects.count(), 1)

    def test_unavailable_copy_and_reader_quota(self):
        checkout_copy("a", "COPY-1", self.staff)
        with self.assertRaises(CirculationError):
            checkout_copy("b", "COPY-1", self.staff)
        other = self.make_copy("COPY-2")
        with self.assertRaisesMessage(CirculationError, "hạn mức"):
            checkout_copy("a", other.barcode, self.staff)
        other.refresh_from_db()
        self.assertEqual(other.status, "available")

    def test_inactive_or_expired_or_unverified_card(self):
        for field, value in [("membership_verified", False), ("status", "suspended"),
                             ("valid_until", timezone.localdate() - timedelta(days=1))]:
            original = getattr(self.a, field)
            setattr(self.a, field, value)
            self.a.save()
            with self.assertRaises(CirculationError):
                checkout_copy("a", "COPY-1", self.staff)
            setattr(self.a, field, original)
        self.a.save()
        self.a.user.is_active = False
        self.a.user.save()
        with self.assertRaises(CirculationError):
            checkout_copy("a", "COPY-1", self.staff)

    def test_returned_book_debt_still_blocks_checkout(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        return_copy("COPY-1", self.staff)
        Fine.objects.create(loan=loan, rate_per_day=1000, cap_amount=30000, accrued_amount=1000, status="due")
        with self.assertRaisesMessage(CirculationError, "chưa thanh toán"):
            checkout_copy("a", "COPY-1", self.staff)

    def test_overdue_loan_blocks_new_checkout(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        loan.due_at = timezone.now() - timedelta(minutes=1)
        loan.save()
        self.make_copy("COPY-2")
        with self.assertRaisesMessage(CirculationError, "quá hạn"):
            checkout_copy("a", "COPY-2", self.staff)

    def test_read_in_library_or_inactive_copy_cannot_be_loaned(self):
        for field, value in [("home_loan_override", False), ("is_active", False)]:
            original = getattr(self.copy, field)
            setattr(self.copy, field, value)
            self.copy.save()
            with self.assertRaises(CirculationError):
                checkout_copy("a", "COPY-1", self.staff)
            setattr(self.copy, field, original)
        self.assertEqual(Loan.objects.count(), 0)

    def test_return_replay_after_copy_has_been_loaned_again(self):
        first = checkout_copy("a", "COPY-1", self.staff)
        key = uuid4()
        return_copy("COPY-1", self.staff, idempotency_key=key)
        second = checkout_copy("b", "COPY-1", self.staff)
        self.assertEqual(return_copy("COPY-1", self.staff, idempotency_key=key).pk, first.pk)
        second.refresh_from_db()
        self.assertEqual(second.status, "open")
        self.assertEqual(LoanEvent.objects.filter(event_type="return").count(), 1)

    def test_return_damage_is_not_available_and_does_not_allocate(self):
        checkout_copy("a", "COPY-1", self.staff)
        reservation = place_reservation(self.b, self.book.pk, self.b.user)
        loan = return_copy("COPY-1", self.staff, "Rách trang")
        self.copy.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(loan.status, "returned")
        self.assertEqual(self.copy.status, "return_review")
        self.assertEqual(reservation.status, "waiting")
        self.assertEqual(loan.damage_cases.count(), 1)
        self.assertTrue(self.a.restrictions.filter(resolved_at__isnull=True).exists())
        self.assertIsNone(return_copy("COPY-1", self.staff))

    def test_renewal_snapshot_replay_and_history(self):
        loan = self.make_renewable(checkout_copy("a", "COPY-1", self.staff))
        old = loan.due_at
        self.policy.renewal_days = 100
        self.policy.max_renewals = 10
        self.policy.save()
        key = uuid4()
        renewed = renew_loan(loan.pk, self.a.user, key)
        self.assertEqual(timezone.localtime(renewed.due_at).date(), timezone.localtime(old).date() + timedelta(days=7))
        self.assertEqual(renew_loan(loan.pk, self.a.user, key).renewal_count, 1)
        self.assertEqual(LoanRenewal.objects.count(), 1)
        self.make_renewable(renewed)
        with self.assertRaisesMessage(CirculationError, "hết số lần"):
            renew_loan(loan.pk, self.a.user)

    def test_renewal_rejects_early_overdue_closed_and_queue(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        with self.assertRaises(CirculationError):
            renew_loan(loan.pk, self.a.user)
        loan.due_at = timezone.now() - timedelta(minutes=1)
        loan.save()
        with self.assertRaises(CirculationError):
            renew_loan(loan.pk, self.a.user)
        self.make_renewable(loan)
        place_reservation(self.b, self.book.pk, self.b.user)
        with self.assertRaisesMessage(CirculationError, "đặt trước"):
            renew_loan(loan.pk, self.staff)
        return_copy("COPY-1", self.staff)
        with self.assertRaises(CirculationError):
            renew_loan(loan.pk, self.a.user)

    def test_reservation_rejects_available_and_duplicate_and_wrong_owner(self):
        with self.assertRaises(CirculationError):
            place_reservation(self.b, self.book.pk, self.b.user)
        checkout_copy("a", "COPY-1", self.staff)
        place_reservation(self.b, self.book.pk, self.b.user)
        with self.assertRaises(CirculationError):
            place_reservation(self.b, self.book.pk, self.b.user)
        with self.assertRaises(CirculationError):
            place_reservation(self.c, self.book.pk, self.b.user)

    def test_fifo_return_allocate_cancel_and_fulfill(self):
        checkout_copy("a", "COPY-1", self.staff)
        first = place_reservation(self.b, self.book.pk, self.b.user)
        second = place_reservation(self.c, self.book.pk, self.c.user)
        return_copy("COPY-1", self.staff)
        first.refresh_from_db()
        self.assertEqual(first.status, "ready")
        self.assertTrue(ReservationNotification.objects.filter(reservation=first).exists())
        with self.assertRaises(CirculationError):
            checkout_copy("c", "COPY-1", self.staff)
        cancel_reservation(self.b, first.pk, self.b.user)
        cancel_reservation(self.b, first.pk, self.b.user)
        second.refresh_from_db()
        self.assertEqual(second.status, "ready")
        checkout_copy("c", "COPY-1", self.staff)
        second.refresh_from_db()
        self.assertEqual(second.status, "fulfilled")

    def test_expired_pickup_cannot_checkout_and_next_reader_receives_copy(self):
        checkout_copy("a", "COPY-1", self.staff)
        first = place_reservation(self.b, self.book.pk, self.b.user)
        second = place_reservation(self.c, self.book.pk, self.c.user)
        return_copy("COPY-1", self.staff)
        Reservation.objects.filter(pk=first.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(CirculationError):
            checkout_copy("b", "COPY-1", self.staff)
        self.assertEqual(expire_ready_reservations(), 0)
        self.assertEqual(expire_ready_reservations(), 0)
        second.refresh_from_db()
        self.assertEqual(second.status, "ready")

    def test_ineligible_queue_reader_is_skipped(self):
        checkout_copy("a", "COPY-1", self.staff)
        first = place_reservation(self.b, self.book.pk, self.b.user)
        second = place_reservation(self.c, self.book.pk, self.c.user)
        self.b.status = "suspended"
        self.b.save()
        return_copy("COPY-1", self.staff)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "ineligible")
        self.assertTrue(first.close_reason)
        self.assertEqual(second.status, "ready")

    def test_read_only_return_is_not_assigned_to_queue(self):
        checkout_copy("a", "COPY-1", self.staff)
        reservation = place_reservation(self.b, self.book.pk, self.b.user)
        self.copy.home_loan_override = False
        self.copy.save()
        return_copy("COPY-1", self.staff)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "waiting")

    def test_closed_due_day_and_before_opening_hold_expiry(self):
        day = timezone.localdate() + timedelta(days=14)
        LibraryClosure.objects.create(date=day, reason="Đóng cửa thử", is_full_day=True, created_by=self.staff)
        loan = checkout_copy("a", "COPY-1", self.staff)
        self.assertEqual(timezone.localtime(loan.due_at).date(), day + timedelta(days=1))
        started = timezone.make_aware(datetime.combine(timezone.localdate(), time(7)))
        expiry_day = (started + timedelta(hours=48)).date()
        LibraryHours.objects.create(weekday=expiry_day.weekday(), is_open=True, opens_at=time(8), closes_at=time(17))
        expiry = timezone.localtime(_hold_expiry(started))
        self.assertEqual(expiry.date(), expiry_day)
        self.assertEqual(expiry.hour, 17)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_notification_failure_retry_and_no_duplicate_send(self):
        checkout_copy("a", "COPY-1", self.staff)
        reservation = place_reservation(self.b, self.book.pk, self.b.user)
        return_copy("COPY-1", self.staff)
        with patch("apps.library.management.commands.send_reservation_notifications.send_mail", side_effect=RuntimeError("fail")):
            call_command("send_reservation_notifications", stdout=StringIO())
        notice = reservation.notification
        self.assertIsNone(notice.sent_at)
        self.assertTrue(notice.last_error)
        call_command("send_reservation_notifications", stdout=StringIO())
        call_command("send_reservation_notifications", stdout=StringIO())
        notice.refresh_from_db()
        self.assertIsNotNone(notice.sent_at)
        self.assertEqual(notice.attempts, 2)
        self.assertEqual(len(mail.outbox), 1)

    def login_staff(self):
        self.client.force_login(self.staff)
        device = TOTPDevice.objects.create(user=self.staff, confirmed=True)
        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()

    def test_desk_preserves_invalid_form_and_shows_success(self):
        self.login_staff()
        response = self.client.post(reverse("library:circulation_desk"), {"action": "checkout", "barcode": "COPY-1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["checkout_form"].errors)
        response = self.client.post(reverse("library:circulation_desk"), {
            "action": "checkout", "barcode": "COPY-1", "reader_number": "a", "idempotency_key": uuid4()}, follow=True)
        self.assertContains(response, "Đã ghi nhận mượn")

    def test_desk_renewal_and_unknown_loan_display_error(self):
        loan = self.make_renewable(checkout_copy("a", "COPY-1", self.staff))
        self.login_staff()
        response = self.client.post(reverse("library:circulation_desk"), {
            "action": "renew", "loan_id": loan.pk, "idempotency_key": uuid4()}, follow=True)
        self.assertContains(response, "Đã gia hạn")
        response = self.client.post(reverse("library:circulation_desk"), {
            "action": "renew", "loan_id": 999999, "idempotency_key": uuid4()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["renewal_form"].non_field_errors())

    def test_failed_event_rolls_back_loan_and_copy(self):
        with patch("apps.library.services._event", side_effect=RuntimeError("event failed")):
            with self.assertRaises(RuntimeError):
                checkout_copy("a", "COPY-1", self.staff)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, "available")
        self.assertEqual(Loan.objects.count(), 0)

    def test_exact_renewal_window_boundary(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        now = timezone.now()
        with patch("apps.library.services.timezone.now", return_value=now):
            loan.due_at = now + timedelta(hours=48, seconds=1)
            loan.save()
            with self.assertRaises(CirculationError):
                renew_loan(loan.pk, self.a.user)
            loan.due_at = now + timedelta(hours=48)
            loan.save()
            self.assertEqual(renew_loan(loan.pk, self.a.user).renewal_count, 1)


class ConcurrentCirculationTests(CirculationFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_circulation_data()

    def race(self, operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.staff.pk)
                actor.has_perm("library.checkout_loan")
                barrier.wait(timeout=10)
                try:
                    return operation(actor)
                except CirculationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, operation) for operation in operations]
            return [future.result(timeout=20) for future in futures]

    def test_two_readers_competing_for_last_copy(self):
        results = self.race([lambda actor: checkout_copy("a", "COPY-1", actor),
                             lambda actor: checkout_copy("b", "COPY-1", actor)])
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(Loan.objects.filter(status="open", copy=self.copy).count(), 1)
        self.assertEqual(BookCopy.objects.filter(status="available").count(), 0)

    def test_two_copies_competing_for_last_reader_quota(self):
        self.make_copy("COPY-2")
        results = self.race([lambda actor: checkout_copy("a", "COPY-1", actor),
                             lambda actor: checkout_copy("a", "COPY-2", actor)])
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(Loan.objects.filter(reader=self.a, status="open").count(), 1)
        self.assertEqual(BookCopy.objects.filter(status="available").count(), 1)

    def test_duplicate_checkout_requests_create_one_loan(self):
        key = uuid4()
        results = self.race([lambda actor: checkout_copy("a", "COPY-1", actor, key),
                             lambda actor: checkout_copy("a", "COPY-1", actor, key)])
        self.assertTrue(all(result is not None for result in results))
        self.assertEqual(results[0].pk, results[1].pk)
        self.assertEqual(Loan.objects.count(), 1)

    def test_two_returns_assign_distinct_copies_to_fifo_readers(self):
        self.make_copy("COPY-2")
        checkout_copy("a", "COPY-1", self.staff)
        checkout_copy("b", "COPY-2", self.staff)
        d = self.make_reader("d")
        first = place_reservation(self.c, self.book.pk, self.c.user)
        second = place_reservation(d, self.book.pk, d.user)
        self.race([lambda actor: return_copy("COPY-1", actor), lambda actor: return_copy("COPY-2", actor)])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "ready")
        self.assertEqual(second.status, "ready")
        self.assertNotEqual(first.copy_id, second.copy_id)
        self.assertEqual(Loan.objects.filter(status="open").count(), 0)

    def test_simultaneous_renewals_only_consume_one_allowance(self):
        loan = self.make_renewable(checkout_copy("a", "COPY-1", self.staff))
        results = self.race([lambda actor: renew_loan(loan.pk, actor), lambda actor: renew_loan(loan.pk, actor)])
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(LoanRenewal.objects.filter(loan=loan).count(), 1)

    def test_simultaneous_returns_only_close_loan_once(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        self.race([lambda actor: return_copy("COPY-1", actor), lambda actor: return_copy("COPY-1", actor)])
        loan.refresh_from_db()
        self.assertEqual(loan.status, "returned")
        self.assertEqual(LoanEvent.objects.filter(loan=loan, event_type="return").count(), 1)

    def test_renewal_and_reservation_are_ordered(self):
        loan = self.make_renewable(checkout_copy("a", "COPY-1", self.staff))
        self.race([lambda actor: renew_loan(loan.pk, actor),
                   lambda actor: place_reservation(self.b, self.book.pk, self.b.user)])
        reservation = Reservation.objects.get(reader=self.b)
        history = LoanRenewal.objects.filter(loan=loan).first()
        if history:
            self.assertLessEqual(history.renewed_at, reservation.created_at)
        self.assertEqual(reservation.status, "waiting")

    def test_simultaneous_duplicate_reservations(self):
        checkout_copy("a", "COPY-1", self.staff)
        self.race([lambda actor: place_reservation(self.b, self.book.pk, self.b.user),
                   lambda actor: place_reservation(self.b, self.book.pk, self.b.user)])
        self.assertEqual(Reservation.objects.filter(reader=self.b, status="waiting").count(), 1)
