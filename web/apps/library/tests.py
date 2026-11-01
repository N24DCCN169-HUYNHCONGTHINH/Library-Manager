from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ReaderProfile
from .models import Book, BookCopy, CirculationPolicy, Fine, FinePayment, LibraryBranch, Loan, Reservation
from .services import CirculationError, checkout_copy, record_fine_payment, renew_loan


User = get_user_model()


class LibraryRoleAcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.root = User.objects.create_superuser("root", "root@example.test", "Test-password-123!")
        cls.reader_a = cls.make_user("reader-a", "reader")
        cls.reader_b = cls.make_user("reader-b", "reader")
        cls.cataloger = cls.make_user("cataloger", "cataloger")
        cls.circulation = cls.make_user("circulation", "circulation_staff")
        cls.manager = cls.make_user("manager", "library_manager")
        cls.system_admin = cls.make_user("system-admin", "system_admin", staff=True)

        today = timezone.localdate()
        cls.profile_a = ReaderProfile.objects.create(
            user=cls.reader_a, reader_number="TEST-READER-A", reader_type=ReaderProfile.ReaderType.STUDENT,
            status=ReaderProfile.Status.ACTIVE, valid_from=today - timedelta(days=30),
            valid_until=today + timedelta(days=30), membership_verified=True,
        )
        cls.profile_b = ReaderProfile.objects.create(
            user=cls.reader_b, reader_number="TEST-READER-B", reader_type=ReaderProfile.ReaderType.STUDENT,
            status=ReaderProfile.Status.ACTIVE, valid_from=today - timedelta(days=30),
            valid_until=today + timedelta(days=30), membership_verified=True,
        )
        cls.policy = CirculationPolicy.objects.create(
            reader_type=CirculationPolicy.ReaderType.STUDENT,
            material_type=CirculationPolicy.MaterialType.GENERAL,
            effective_from=today - timedelta(days=30), max_active_loans=5, loan_days=14,
            max_renewals=1, renewal_days=7, created_by=cls.root,
        )
        cls.book_a = cls.make_book("TEST-CAT-A", "Sách của độc giả A")
        cls.book_b = cls.make_book("TEST-CAT-B", "Sách riêng của độc giả B")
        cls.copy_a = BookCopy.objects.create(book=cls.book_a, barcode="TEST-BC-A", created_by=cls.root, status=BookCopy.Status.ON_LOAN)
        cls.copy_b = BookCopy.objects.create(book=cls.book_b, barcode="TEST-BC-B", created_by=cls.root, status=BookCopy.Status.ON_LOAN)
        now = timezone.now()
        cls.loan_a = cls.make_loan(cls.profile_a, cls.copy_a, now + timedelta(hours=12))
        cls.loan_b = cls.make_loan(cls.profile_b, cls.copy_b, now + timedelta(hours=12))

    @classmethod
    def make_user(cls, username, role, staff=False):
        user = User.objects.create_user(username, password="Test-password-123!", is_staff=staff)
        user.groups.add(Group.objects.get(name=role))
        return user

    @classmethod
    def make_book(cls, catalog_number, title):
        return Book.objects.create(
            catalog_number=catalog_number, title=title, created_by=cls.root, updated_by=cls.root,
        )

    @classmethod
    def make_loan(cls, profile, copy, due_at):
        return Loan.objects.create(
            reader=profile, copy=copy, policy=cls.policy, reader_type_snapshot=profile.reader_type,
            material_type_snapshot=copy.book.material_type, policy_version_snapshot=cls.policy.version,
            max_loans_snapshot=cls.policy.max_active_loans,
            overdue_rate_snapshot=cls.policy.overdue_rate_per_day,
            overdue_cap_snapshot=cls.policy.overdue_fine_cap, due_at=due_at, created_by=cls.root,
        )

    def test_reader_portal_only_returns_the_signed_in_readers_records(self):
        self.client.force_login(self.reader_a)
        response = self.client.get(reverse("reader_portal"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["loans"]), [self.loan_a])
        self.assertEqual(list(response.context["reservations"]), [])
        self.assertEqual(list(response.context["fines"]), [])
        self.assertNotContains(response, "Sách riêng của độc giả B")

    def test_reader_can_renew_own_loan_but_cannot_renew_another_readers_loan(self):
        updated = renew_loan(self.loan_a.pk, self.reader_a)
        self.assertEqual(updated.renewal_count, 1)

        with self.assertRaises(CirculationError):
            renew_loan(self.loan_b.pk, self.reader_a)

    def test_cataloger_cannot_call_circulation_services_directly(self):
        with self.assertRaises(CirculationError):
            checkout_copy("TEST-READER-A", "TEST-BC-A", self.cataloger)

        with self.assertRaises(CirculationError):
            record_fine_payment(999999, Decimal("1000"), self.cataloger)

    def test_each_staff_role_gets_only_its_expected_business_permissions(self):
        self.assertTrue(self.cataloger.has_perm("library.add_book"))
        self.assertTrue(self.cataloger.has_perm("library.view_librarybranch"))
        self.assertFalse(self.cataloger.has_perm("core.view_readerprofile"))
        self.assertTrue(self.circulation.has_perm("library.checkout_loan"))
        self.assertTrue(self.circulation.has_perm("library.return_loan"))
        self.assertFalse(self.circulation.has_perm("library.change_book"))
        self.assertTrue(self.manager.has_perm("library.approve_finepayment"))
        self.assertTrue(self.manager.has_perm("library.approve_damagecase"))
        self.assertFalse(self.manager.has_perm("library.change_loan"))
        self.assertFalse(self.reader_a.has_perm("library.view_book"))

    def test_circulation_staff_can_collect_but_cannot_approve_waivers(self):
        self.assertTrue(self.circulation.has_perm("library.collect_finepayment"))
        self.assertFalse(self.circulation.has_perm("library.approve_finepayment"))
        self.assertFalse(self.cataloger.has_perm("library.collect_finepayment"))

    def test_manager_can_approve_a_waiver_collected_by_another_staff_member(self):
        fine = Fine.objects.create(
            loan=self.loan_a, rate_per_day=Decimal("1000"), cap_amount=Decimal("30000"),
            accrued_amount=Decimal("10000"), status=Fine.Status.DUE,
        )
        row = record_fine_payment(
            fine.pk, Decimal("10000"), self.circulation,
            kind=FinePayment.Kind.WAIVER, approved_by=self.manager, reason="Synthetic acceptance scenario",
        )
        self.assertEqual(row.approved_by, self.manager)

    def test_manager_cannot_self_approve_a_waiver(self):
        fine = Fine.objects.create(
            loan=self.loan_a, rate_per_day=Decimal("1000"), cap_amount=Decimal("30000"),
            accrued_amount=Decimal("10000"), status=Fine.Status.DUE,
        )
        with self.assertRaisesMessage(CirculationError, "không được tự phê duyệt"):
            record_fine_payment(
                fine.pk, Decimal("10000"), self.manager,
                kind=FinePayment.Kind.WAIVER, approved_by=self.manager, reason="Synthetic self-approval attempt",
            )

    def test_system_admin_has_no_catalog_or_circulation_permissions(self):
        self.assertTrue(self.system_admin.is_staff)
        self.assertTrue(self.system_admin.has_perm("auth.view_user"))
        self.assertFalse(self.system_admin.has_perm("library.view_book"))
        self.assertFalse(self.system_admin.has_perm("library.checkout_loan"))
        self.assertFalse(self.system_admin.has_perm("library.collect_finepayment"))

    def test_catalog_search_can_be_scoped_to_a_branch_and_copy_barcode(self):
        branch_a = LibraryBranch.objects.create(code="TEST-A", name="Cơ sở thử A")
        branch_b = LibraryBranch.objects.create(code="TEST-B", name="Cơ sở thử B")
        self.copy_a.branch = branch_a
        self.copy_a.shelf_location = "A-01"
        self.copy_a.status = BookCopy.Status.AVAILABLE
        self.copy_a.save(update_fields=["branch", "shelf_location", "status"])
        self.copy_b.branch = branch_b
        self.copy_b.save(update_fields=["branch"])

        response = self.client.get(reverse("library:catalog"), {"branch": branch_a.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.book_a.title)
        self.assertNotContains(response, self.book_b.title)
        self.assertContains(response, "A-01")

        response = self.client.get(reverse("library:catalog"), {"q": self.copy_b.barcode})
        self.assertContains(response, self.book_b.title)

    def test_reader_portal_shows_current_reservation_queue_position(self):
        Reservation.objects.create(reader=self.profile_b, book=self.book_a)
        Reservation.objects.create(reader=self.profile_a, book=self.book_a)
        self.client.force_login(self.reader_a)

        response = self.client.get(reverse("reader_portal"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vị trí hiện tại trong hàng chờ: 2")
