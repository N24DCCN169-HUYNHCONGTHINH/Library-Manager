from django.test import TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import Book, Loan
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
