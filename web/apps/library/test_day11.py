from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.core.lifecycle import issue_account_invitation

from .test_circulation import CirculationFixtures
from .models import Fine, FinePayment, Loan, Reservation
from .services import (CirculationError, checkout_copy, place_reservation,
                       record_fine_payment, renew_loan, return_copy)


class Day11Regressions(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()
        self.loan = self.make_renewable(checkout_copy("a", "COPY-1", self.staff))

    def test_reservation_obeys_disabled_home_loan_policy(self):
        self.policy.allow_home_loan = False
        self.policy.save()
        with self.assertRaises(CirculationError):
            place_reservation(self.b, self.book.pk, self.b.user)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_renewal_rejects_copy_no_longer_loanable(self):
        self.copy.home_loan_override = False
        self.copy.save()
        with self.assertRaises(CirculationError):
            renew_loan(self.loan.pk, self.a.user)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.renewal_count, 0)

    def test_renewal_obeys_disabled_current_policy(self):
        self.policy.allow_home_loan = False
        self.policy.save()
        with self.assertRaises(CirculationError):
            renew_loan(self.loan.pk, self.a.user)

    def test_duplicate_partial_payment_only_charges_once(self):
        fine = Fine.objects.create(loan=self.loan, accrued_amount=10000, rate_per_day=1000, cap_amount=30000)
        key = uuid4()
        first = record_fine_payment(fine.pk, 2000, self.staff, idempotency_key=key)
        second = record_fine_payment(fine.pk, 2000, self.staff, idempotency_key=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(fine.transactions.count(), 1)
        self.assertEqual(fine.balance, 8000)
        with self.assertRaises(CirculationError):
            record_fine_payment(fine.pk, 3000, self.staff, idempotency_key=key)

    def test_invalid_money_is_domain_error_and_never_writes(self):
        fine = Fine.objects.create(loan=self.loan, accrued_amount=10000, rate_per_day=1000, cap_amount=30000)
        for value in [Decimal("NaN"), Decimal("Infinity"), Decimal("1.5"), "invalid", -1, 0]:
            with self.subTest(value=str(value)):
                with self.assertRaises(CirculationError):
                    record_fine_payment(fine.pk, value, self.staff)
        self.assertEqual(FinePayment.objects.count(), 0)

    def test_expired_hold_cleanup_survives_rejected_pickup(self):
        first = place_reservation(self.b, self.book.pk, self.b.user)
        second = place_reservation(self.c, self.book.pk, self.c.user)
        return_copy("COPY-1", self.staff)
        Reservation.objects.filter(pk=first.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(CirculationError):
            checkout_copy("b", "COPY-1", self.staff)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "expired")
        self.assertEqual(second.status, "ready")
        self.assertEqual(Loan.objects.filter(status="open").count(), 0)

    def test_inactive_superuser_cannot_call_service(self):
        actor = get_user_model().objects.create_superuser("inactive-root", "root@example.invalid", "test-pass", is_active=False)
        with self.assertRaises(CirculationError):
            return_copy("COPY-1", actor)

    def test_payment_at_desk_is_idempotent_through_http(self):
        fine = Fine.objects.create(loan=self.loan, accrued_amount=10000, rate_per_day=1000, cap_amount=30000)
        self.client.force_login(self.staff)
        device = TOTPDevice.objects.create(user=self.staff, confirmed=True)
        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()
        data = {"action": "payment", "fine_id": fine.pk, "amount": 2000, "reason": "Thu thử", "idempotency_key": uuid4()}
        for _ in range(2):
            response = self.client.post(reverse("library:circulation_desk"), data, follow=True)
            self.assertRedirects(response, reverse("library:circulation_desk") + "?tab=loans&operation=fines#fines")
            self.assertContains(response, 'id="fines" open', html=False)
            self.assertContains(response, "Đã ghi nhận thanh toán")
        self.assertEqual(fine.transactions.count(), 1)

    def test_view_only_permission_cannot_post_circulation_actions(self):
        user = get_user_model().objects.create_user("view-only")
        user.groups.add(Group.objects.get(name="circulation_staff"))
        from django.contrib.auth.models import Permission
        user.groups.clear()
        user.groups.add(Group.objects.get(name="system_admin"))
        user.user_permissions.add(*Permission.objects.filter(codename__in=["view_loan", "view_fine"]))
        self.client.force_login(user)
        device = TOTPDevice.objects.create(user=user, confirmed=True)
        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()
        self.assertEqual(self.client.get(reverse("library:circulation_desk")).status_code, 200)
        for action in ("checkout", "return", "renew", "payment", "expire"):
            with self.subTest(action=action):
                self.assertEqual(self.client.post(reverse("library:circulation_desk"), {"action": action}).status_code, 403)

    def test_bad_waiver_needs_reason_and_distinct_approver(self):
        manager = get_user_model().objects.create_user("approver")
        manager.groups.add(Group.objects.get(name="library_manager"))
        fine = Fine.objects.create(loan=self.loan, accrued_amount=10000, rate_per_day=1000, cap_amount=30000)
        with self.assertRaises(CirculationError):
            record_fine_payment(fine.pk, 1000, self.staff, kind="waiver", approved_by=manager)
        self.assertEqual(fine.transactions.count(), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class Day11InvitationTests(TestCase):
    def setUp(self):
        call_command("setup_roles", stdout=StringIO())
        self.manager = get_user_model().objects.create_user("inviter")
        self.manager.groups.add(Group.objects.get(name="library_manager"))
        from django.test import RequestFactory
        self.request = RequestFactory().get("/", HTTP_HOST="localhost")

    def test_direct_service_rejects_invalid_reader_metadata_atomically(self):
        today = timezone.localdate()
        for extra in ({"reader_number": "invalid code"}, {"reader_type": "invented"},
                      {"valid_until": today - timedelta(days=1)}, {"username": "bad name"}):
            args = dict(actor=self.manager, request=self.request, username="new-reader", email="new@example.invalid",
                        reader_number="NEW-READER", reader_type="student", valid_from=today,
                        valid_until=today + timedelta(days=10))
            with self.subTest(extra=extra), patch("apps.core.lifecycle.send_mail") as send:
                with self.assertRaises(ValidationError):
                    issue_account_invitation(**(args | extra))
                send.assert_not_called()
        self.assertEqual(get_user_model().objects.count(), 1)
