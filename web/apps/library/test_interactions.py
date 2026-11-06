import json

from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .lookup import lookup
from .models import Book, Loan, FinePayment
from .test_circulation import CirculationFixtures
from .services import checkout_copy
from .views import book_list, staff_loan_detail


class QuickInteractionTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()
        self.factory = RequestFactory()

    def request(self, path, data=None, user=None, verified=True):
        request = self.factory.get(path, data or {})
        request.user = user or AnonymousUser()
        request.user.is_verified = lambda: verified
        return request

    def test_public_lookup_excludes_inactive_books_and_private_fields(self):
        Book.objects.create(catalog_number="SECRET", title="Sách không công khai", is_active=False, created_by=self.staff, updated_by=self.staff)
        response = lookup(self.request("/library/lookup/", {"q": "Sách"}))
        rows = json.loads(response.content)["results"]
        self.assertEqual([row["value"] for row in rows], [self.book.catalog_number])
        self.assertNotIn("COPY-1", response.content.decode())
        self.assertNotIn(self.a.user.email, response.content.decode())

    def test_private_lookup_requires_role_mfa_and_permission_even_for_short_queries(self):
        for user, verified in [(None, True), (self.a.user, True), (self.staff, False)]:
            self.assertEqual(lookup(self.request("/library/lookup/", {"kind": "readers", "q": "a"}, user, verified)).status_code, 403)
        self.staff.groups.clear()
        self.staff.groups.add(Group.objects.get(name="cataloger"))
        self.staff = type(self.staff).objects.get(pk=self.staff.pk)
        self.assertEqual(lookup(self.request("/library/lookup/", {"kind": "readers", "q": "ab"}, self.staff)).status_code, 403)

    def test_desk_suggestions_fill_real_ids_without_creating_a_transaction(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        for kind, query, expected in [("readers", "a@", "a"), ("copies", "COPY", "COPY-1"), ("loans", str(loan.pk), str(loan.pk))]:
            response = lookup(self.request("/library/lookup/", {"kind": kind, "q": query}, self.staff))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)["results"][0]["value"], expected)
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(Loan.objects.count(), 1)
        self.assertEqual(FinePayment.objects.count(), 0)

    def test_book_management_cards_and_table_show_actual_copy_counts(self):
        self.staff.groups.add(Group.objects.get(name="library_manager"))
        self.staff = type(self.staff).objects.get(pk=self.staff.pk)
        response = book_list(self.request(reverse("library:book_list"), user=self.staff))
        self.assertContains(response, "managed-book-grid")
        self.assertContains(response, 'data-lookup="staff_books"')
        self.assertContains(response, 'data-open-url=')
        self.assertContains(response, "1 bản trong kho")
        self.assertContains(response, "Dạng bảng")

    def test_staff_loan_detail_has_links_and_rejects_reader(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        response = staff_loan_detail(self.request("/", user=self.staff), loan.pk)
        self.assertContains(response, "COPY-1")
        self.assertContains(response, f"loan={loan.pk}")
        self.assertEqual(staff_loan_detail(self.request("/", user=self.a.user), loan.pk).status_code, 302)

    def test_catalog_suggestions_preserve_selected_branch(self):
        from .models import LibraryBranch
        branch = LibraryBranch.objects.create(code="PICK", name="Cơ sở đã chọn")
        response = lookup(self.request("/", {"q": "Sách", "branch": branch.pk}))
        self.assertEqual(json.loads(response.content)["results"], [])
        self.copy.branch = branch
        self.copy.save()
        response = lookup(self.request("/", {"q": "Sách", "branch": branch.pk}))
        self.assertIn(f"branch={branch.pk}", json.loads(response.content)["results"][0]["url"])
