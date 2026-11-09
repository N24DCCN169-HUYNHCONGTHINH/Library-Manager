from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

from django.test import Client, TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.core.models import MembershipPurchase, MembershipSandboxPayment

from .payments import vnpay_signature
from .models import Book, LibraryBranch, Loan, Reservation
from .services import _due_at, checkout_reservation
from .test_circulation import CirculationFixtures


class CatalogWorkflowTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()

    def login_desk(self):
        self.client.force_login(self.staff)
        device = TOTPDevice.objects.create(user=self.staff, confirmed=True)
        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()

    def test_pagination_keeps_query_and_has_no_duplicate_books(self):
        Book.objects.bulk_create([Book(catalog_number=f"PAGE-{i}", title=f"Page book {i:02}",
            created_by=self.staff, updated_by=self.staff) for i in range(25)])
        first = self.client.get(reverse("library:catalog"), {"q": "Page book"})
        second = self.client.get(reverse("library:catalog"), {"q": "Page book", "page": 2})
        self.assertEqual(first.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(first.context["books"]), 12)
        self.assertFalse(set(b.pk for b in first.context["books"]) & set(b.pk for b in second.context["books"]))
        self.assertContains(second, "q=Page%20book")
        invalid = self.client.get(reverse("library:catalog"), {"page": "invalid"})
        self.assertEqual(invalid.status_code, 200)

    def test_copy_code_is_staff_only_and_get_does_not_checkout(self):
        public = self.client.get(reverse("library:catalog"))
        self.assertNotContains(public, "COPY-1")
        self.assertNotContains(public, "Mượn bản này tại quầy")
        self.login_desk()
        staff = self.client.get(reverse("library:catalog"))
        self.assertContains(staff, "COPY-1")
        self.assertContains(staff, "?barcode=COPY-1")
        desk = self.client.get(reverse("library:circulation_desk"), {"barcode": "COPY-1"})
        self.assertEqual(desk.context["checkout_form"]["barcode"].value(), "COPY-1")
        self.assertEqual(Loan.objects.count(), 0)

    def test_guest_cannot_reserve_until_day_pass_is_paid(self):
        guest = Client()
        plans = reverse("membership_plans")
        reserve = reverse("library:reserve", args=[self.book.pk])
        profile_data = {
            "full_name": "Guest Reader", "reader_type": "student", "address": "Test address",
            "citizen_id": "001234567890", "citizen_id_issued_on": "2020-01-01",
            "contact_email": "guest@example.invalid", "phone_number": "0901234567",
        }
        guest.post(plans, profile_data | {"plan": "week"})
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertRedirects(guest.post(plans, profile_data | {"plan": "day"}), plans)
        purchase = MembershipPurchase.objects.get()
        self.assertEqual(purchase.amount, 7000)
        self.assertFalse(purchase.reader.user.has_usable_password())
        self.assertRedirects(guest.post(reserve), plans)
        self.assertFalse(Reservation.objects.exists())

        self.login_desk()
        confirm = reverse("membership_confirm", args=[purchase.pk])
        self.assertRedirects(self.client.post(confirm), reverse("membership_queue"))
        purchase.refresh_from_db()
        self.assertIsNotNone(purchase.paid_at)
        self.assertRedirects(guest.post(reserve), plans)
        reservation = Reservation.objects.get(reader=purchase.reader)
        self.assertEqual(reservation.status, Reservation.Status.READY)
        self.assertLessEqual(reservation.expires_at, purchase.expires_at)


    def test_pickup_uses_selected_branch_and_requested_days(self):
        first = LibraryBranch.objects.create(code="FIRST", name="First")
        second = LibraryBranch.objects.create(code="SECOND", name="Second")
        self.copy.branch = first
        self.copy.save(update_fields=["branch"])
        other_copy = self.make_copy("COPY-SECOND")
        other_copy.branch = second
        other_copy.save(update_fields=["branch"])
        self.client.force_login(self.a.user)
        reserve = reverse("library:reserve", args=[self.book.pk])
        self.client.post(reserve, {"branch": second.pk, "loan_days": 15})
        self.assertFalse(Reservation.objects.exists())
        self.client.post(reserve, {"branch": second.pk, "loan_days": 3})
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.copy_id, other_copy.pk)
        self.assertEqual(reservation.pickup_branch_id, second.pk)
        self.assertEqual(reservation.requested_loan_days, 3)
        loan = checkout_reservation(reservation.pk, self.staff)
        self.assertEqual(loan.due_at, _due_at(loan.loaned_at, 3))


    def test_requested_duration_is_applied_to_the_second_at_pickup(self):
        self.client.force_login(self.a.user)
        reserve = reverse("library:reserve", args=[self.book.pk])
        self.client.post(reserve, {"loan_days": 14, "loan_seconds": 1})
        self.assertFalse(Reservation.objects.exists())
        self.client.post(reserve, {"loan_hours": 2, "loan_minutes": 30, "loan_seconds": 15})
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.requested_duration_seconds, 9015)
        loan = checkout_reservation(reservation.pk, self.staff)
        self.assertEqual((loan.due_at - loan.loaned_at).total_seconds(), 9015)


    @patch("apps.library.payments.vnpay_keys", return_value=("TEST", "test-secret"))
    def test_vnpay_membership_callback_is_verified_and_does_not_post_real_money(self, keys):
        self.client.force_login(self.a.user)
        self.client.post(reverse("membership_plans"), {"plan": "day"})
        purchase = MembershipPurchase.objects.get()
        response = self.client.post(reverse("membership_sandbox_start"))
        self.assertEqual(response.status_code, 302)
        url = urlsplit(response["Location"])
        self.assertEqual(url.hostname, "sandbox.vnpayment.vn")
        checkout = dict(parse_qsl(url.query))
        self.assertEqual(checkout["vnp_Amount"], "700000")
        payment = MembershipSandboxPayment.objects.get()
        ipn = reverse("library:vnpay_ipn")
        payload = {
            "vnp_TmnCode": "TEST", "vnp_TxnRef": checkout["vnp_TxnRef"],
            "vnp_OrderInfo": checkout["vnp_OrderInfo"], "vnp_Amount": "700000",
            "vnp_ResponseCode": "00", "vnp_TransactionStatus": "00", "vnp_TransactionNo": "123",
        }
        self.assertEqual(self.client.get(ipn, payload).json()["RspCode"], "97")
        wrong = payload | {"vnp_Amount": "1"}
        self.assertEqual(self.client.get(ipn, wrong | {"vnp_SecureHash": vnpay_signature(wrong, "test-secret")}).json()["RspCode"], "04")
        signed = payload | {"vnp_SecureHash": vnpay_signature(payload, "test-secret")}
        self.assertEqual(self.client.get(ipn, signed).json()["RspCode"], "00")
        self.assertEqual(self.client.get(ipn, signed).json()["RspCode"], "02")
        payment.refresh_from_db()
        purchase.refresh_from_db()
        self.a.refresh_from_db()
        self.assertTrue(payment.successful)
        self.assertIsNone(purchase.paid_at)
        self.assertIsNone(self.a.membership_expires_at)
