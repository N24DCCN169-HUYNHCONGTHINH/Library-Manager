from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .test_circulation import CirculationFixtures
from .models import BookCopy, Fine, Loan, Reservation
from .services import (CirculationError, checkout_copy, return_copy, place_reservation,
                       renew_loan, record_fine_payment)


class AcceptanceJourneyTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()

    def test_full_reader_and_desk_journey(self):
        key = uuid4()
        first = checkout_copy("a", "COPY-1", self.staff, key)
        self.assertEqual(checkout_copy("a", "COPY-1", self.staff, key).pk, first.pk)
        with self.assertRaises(CirculationError):
            checkout_copy("b", "COPY-1", self.staff)
        reservation = place_reservation(self.b, self.book.pk, self.b.user)
        return_copy("COPY-1", self.staff)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "ready")
        with self.assertRaises(CirculationError):
            checkout_copy("c", "COPY-1", self.staff)
        second = checkout_copy("b", "COPY-1", self.staff)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "fulfilled")
        second.due_at = timezone.now() + timedelta(hours=24)
        second.save(update_fields=["due_at"])
        renew_loan(second.pk, self.b.user)
        self.client.force_login(self.b.user)
        response = self.client.get(reverse("reader_loan_detail", args=[second.pk]))
        self.assertContains(response, "Lịch sử gia hạn")
        self.assertEqual(response.context["renewals"].count(), 1)
        self.assertEqual(self.client.get(reverse("reader_loan_detail", args=[first.pk])).status_code, 404)
        second.refresh_from_db()
        second.due_at = timezone.now() - timedelta(days=3)
        second.save(update_fields=["due_at"])
        return_copy("COPY-1", self.staff)
        fine = Fine.objects.get(loan=second)
        self.assertGreater(fine.balance, 0)
        with self.assertRaises(CirculationError):
            checkout_copy("b", "COPY-1", self.staff)
        payment_key = uuid4()
        payment = record_fine_payment(fine.pk, fine.balance, self.staff, idempotency_key=payment_key)
        self.assertEqual(record_fine_payment(fine.pk, payment.amount, self.staff, idempotency_key=payment_key).pk, payment.pk)
        self.assertEqual(fine.balance, 0)
        self.assertContains(self.client.get(reverse("reader_loan_detail", args=[second.pk])), payment.receipt_number)
        third = checkout_copy("b", "COPY-1", self.staff)
        self.assertEqual(Loan.objects.filter(copy=self.copy, status="open").count(), 1)
        self.assertEqual(third.copy.status, BookCopy.Status.ON_LOAN)

    def test_book_form_duplicate_message_is_readable_vietnamese(self):
        from .forms import BookForm
        form = BookForm(data={"catalog_number": self.book.catalog_number, "title": "Sách thử",
                              "material_type": "general", "loan_mode": "home_loan", "is_active": "on"})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["catalog_number"], ["Mã danh mục này đã tồn tại."])
