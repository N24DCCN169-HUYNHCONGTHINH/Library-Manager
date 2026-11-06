from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.library.test_circulation import CirculationFixtures
from apps.library.models import Book, BookCopy, Fine, FinePayment, Loan, Reservation
from apps.library.services import checkout_copy


class ReaderPortalTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()
        self.loan = self.make_renewable(checkout_copy("a", "COPY-1", self.staff))
        book = Book.objects.create(catalog_number="PRIVATE-B", title="PRIVATE OTHER READER BOOK",
                                   created_by=self.staff, updated_by=self.staff)
        copy = BookCopy.objects.create(book=book, barcode="PRIVATE-COPY", created_by=self.staff)
        self.other_loan = checkout_copy("b", copy.barcode, self.staff)
        self.fine = Fine.objects.create(loan=self.loan, rate_per_day=1000, cap_amount=30000,
                                       accrued_amount=2000, status="due")
        FinePayment.objects.create(fine=self.fine, kind="payment", amount=1000,
                                   receipt_number="OWN-RECEIPT", created_by=self.staff)
        other_fine = Fine.objects.create(loan=self.other_loan, rate_per_day=1000, cap_amount=30000,
                                         accrued_amount=9000, status="due")
        FinePayment.objects.create(fine=other_fine, kind="payment", amount=1000,
                                   receipt_number="PRIVATE-OTHER-RECEIPT", created_by=self.staff)
        self.client.force_login(self.a.user)

    def test_lists_and_summary_ignore_other_readers_and_query_ids(self):
        response = self.client.get(reverse("reader_portal"), {"reader_id": self.b.pk, "user_id": self.b.user_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["loans"]), [self.loan])
        self.assertEqual(response.context["summary"]["balance"], 1000)
        self.assertEqual(response.context["summary"]["open_loans"], 1)
        self.assertNotContains(response, "PRIVATE OTHER READER BOOK")

    def test_detail_is_scoped_and_receipts_are_private(self):
        response = self.client.get(reverse("reader_loan_detail", args=[self.loan.pk]))
        self.assertContains(response, "OWN-RECEIPT")
        self.assertNotContains(response, "PRIVATE-OTHER-RECEIPT")
        self.assertEqual(self.client.get(reverse("reader_loan_detail", args=[self.other_loan.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("reader_loan_detail", args=[999999])).status_code, 404)

    def test_history_includes_closed_reservations_and_only_own(self):
        for status in ["cancelled", "expired", "fulfilled", "ineligible"]:
            Reservation.objects.create(reader=self.a, book=self.book, status=status, close_reason="Đã xử lý")
        Reservation.objects.create(reader=self.b, book=self.other_loan.copy.book, status="cancelled")
        response = self.client.get(reverse("reader_portal"))
        self.assertEqual(response.context["reservations"].paginator.count, 4)
        self.assertContains(response, "Đã xử lý")
        self.assertNotContains(response, "PRIVATE OTHER READER BOOK")
        self.assertNotContains(response, "Hủy yêu cầu")

    def test_loan_history_beyond_previous_100_row_limit(self):
        Loan.objects.bulk_create([Loan(reader=self.a, copy=self.copy, policy=self.policy, status="returned",
            reader_type_snapshot="student", material_type_snapshot="general", policy_version_snapshot=1,
            max_loans_snapshot=1, overdue_rate_snapshot=1000, overdue_cap_snapshot=30000,
            due_at=timezone.now(), created_by=self.staff) for _ in range(105)])
        response = self.client.get(reverse("reader_portal"), {"loan_status": "returned", "loan_page": 6})
        self.assertEqual(response.context["loans"].paginator.count, 105)
        self.assertEqual(len(response.context["loans"]), 5)
        self.assertEqual(response.context["summary"]["open_loans"], 1)
        self.assertContains(response, "loan_status=returned")

    def test_invalid_pages_and_status_are_safe(self):
        response = self.client.get(reverse("reader_portal"), {"loan_page": "bad", "loan_status": "bad",
            "reservation_page": "-100", "fine_page": "99999"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["loan_status"], "")

    def test_reservation_and_fine_pages_are_independent(self):
        Reservation.objects.bulk_create([Reservation(reader=self.a, book=self.book, status="cancelled") for _ in range(21)])
        history = Loan.objects.bulk_create([Loan(reader=self.a, copy=self.copy, policy=self.policy, status="returned",
            reader_type_snapshot="student", material_type_snapshot="general", policy_version_snapshot=1,
            max_loans_snapshot=1, overdue_rate_snapshot=1000, overdue_cap_snapshot=30000,
            due_at=timezone.now(), created_by=self.staff) for _ in range(21)])
        Fine.objects.bulk_create([Fine(loan=loan, rate_per_day=1000, cap_amount=30000, accrued_amount=1000) for loan in history])
        response = self.client.get(reverse("reader_portal"), {"reservation_page": 2, "fine_page": 2, "loan_status": "open"})
        self.assertEqual(len(response.context["reservations"]), 1)
        self.assertEqual(len(response.context["fines"]), 2)
        self.assertEqual(len(response.context["loans"]), 1)
        self.assertEqual(response.context["summary"]["balance"], 22000)
        self.assertContains(response, "loan_status=open")

    def test_get_portal_does_not_change_fines_or_card(self):
        self.loan.due_at = timezone.now() - timedelta(days=10)
        self.loan.save()
        with patch("apps.library.services.refresh_overdue_loans", side_effect=AssertionError("GET must be read-only")):
            response = self.client.get(reverse("reader_portal"))
        self.assertContains(response, "Đã quá hạn")
        self.assertEqual(response.context["summary"]["overdue_loans"], 1)
        self.a.refresh_from_db()
        self.fine.refresh_from_db()
        self.assertEqual(self.a.status, "active")
        self.assertEqual(self.fine.accrued_amount, 2000)

    def test_private_pages_disable_caching(self):
        for url in [reverse("reader_portal"), reverse("reader_loan_detail", args=[self.loan.pk])]:
            response = self.client.get(url)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("private", response["Cache-Control"])

    def test_cannot_post_renewal_or_cancellation_for_another_reader(self):
        reservation = Reservation.objects.create(reader=self.b, book=self.book)
        self.assertEqual(self.client.post(reverse("library:renew", args=[self.other_loan.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("library:cancel_reservation", args=[reservation.pk])).status_code, 404)
        self.other_loan.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(self.other_loan.renewal_count, 0)
        self.assertEqual(reservation.status, "waiting")

    def test_get_cannot_mutate_reader_actions(self):
        reservation = Reservation.objects.create(reader=self.a, book=self.book)
        for name, pk in [("renew", self.loan.pk), ("cancel_reservation", reservation.pk), ("reserve", self.book.pk)]:
            self.assertEqual(self.client.get(reverse("library:" + name, args=[pk])).status_code, 405)

    def test_reader_actions_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.a.user)
        for name, pk in [("renew", self.loan.pk), ("cancel_reservation", 1), ("reserve", self.book.pk)]:
            self.assertEqual(client.post(reverse("library:" + name, args=[pk])).status_code, 403)

    def test_missing_profile_is_clear_and_never_shows_other_records(self):
        user = get_user_model().objects.create_user("unlinked")
        user.groups.add(Group.objects.get(name="reader"))
        self.client.force_login(user)
        response = self.client.get(reverse("reader_portal"))
        self.assertContains(response, "chưa được thư viện liên kết")
        self.assertNotContains(response, "PRIVATE OTHER READER BOOK")
        self.assertEqual(self.client.get(reverse("reader_loan_detail", args=[self.loan.pk])).status_code, 404)

    def test_anonymous_and_staff_cannot_open_reader_pages(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reader_portal")).status_code, 302)
        self.client.force_login(self.staff)
        for url in [reverse("reader_portal"), reverse("reader_loan_detail", args=[self.loan.pk])]:
            self.assertRedirects(self.client.get(url), reverse("home") + "?next=" + url)
