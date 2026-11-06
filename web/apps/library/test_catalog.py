from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from .forms import BookForm
from .models import Book


class CatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.editor = get_user_model().objects.create_user("editor")
        cls.editor.groups.add(Group.objects.get(name="cataloger"))
        cls.device = TOTPDevice.objects.create(user=cls.editor, confirmed=True)
        cls.book = Book.objects.create(catalog_number="BK-1", title="Sách thử",
                                      created_by=cls.editor, updated_by=cls.editor)

    def login_verified(self, user=None):
        self.client.force_login(user or self.editor)
        if user is None:
            session = self.client.session
            session["otp_device_id"] = self.device.persistent_id
            session.save()

    def payload(self, **overrides):
        data = {"catalog_number": "BK-2", "title": "Sách mới", "material_type": "general",
                "loan_mode": "home_loan", "is_active": "on"}
        data.update(overrides)
        return data

    def test_create_and_edit_with_actor_and_blank_isbn(self):
        self.login_verified()
        response = self.client.post(reverse("library:book_add"), self.payload())
        self.assertRedirects(response, reverse("library:book_list"))
        book = Book.objects.get(catalog_number="BK-2")
        self.assertIsNone(book.isbn)
        self.assertEqual(book.created_by, self.editor)
        response = self.client.post(reverse("library:book_edit", args=[book.pk]),
                                    self.payload(title="Nhan đề đã sửa"))
        self.assertEqual(response.status_code, 302)
        book.refresh_from_db()
        self.assertEqual(book.title, "Nhan đề đã sửa")
        self.assertEqual(book.updated_by, self.editor)

    def test_invalid_data_does_not_write(self):
        self.login_verified()
        for changes in [{"catalog_number": "BK-1"}, {"title": "   "}, {"isbn": "123"},
                        {"publication_year": "0"}, {"replacement_price": "-1"}]:
            response = self.client.post(reverse("library:book_add"), self.payload(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(Book.objects.count(), 1)

    def test_isbn_normalization_checksum_and_duplicate(self):
        form = BookForm(data=self.payload(isbn="978-0-306-40615-7"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["isbn"], "9780306406157")
        self.book.isbn = "9780306406157"
        self.book.save()
        self.assertFalse(BookForm(data=self.payload(isbn="978-0-306-40615-7")).is_valid())
        self.assertTrue(BookForm(data=self.payload(isbn="0-8044-2957-X")).is_valid())

    def test_rare_material_is_read_in_library_on_edit(self):
        self.login_verified()
        self.client.post(reverse("library:book_edit", args=[self.book.pk]),
                         self.payload(catalog_number="BK-1", material_type="rare"))
        self.book.refresh_from_db()
        self.assertEqual(self.book.loan_mode, Book.LoanMode.IN_LIBRARY_ONLY)

    def test_search_includes_inactive_and_paginates(self):
        self.login_verified()
        self.book.is_active = False
        self.book.save()
        response = self.client.get(reverse("library:book_list"), {"q": "BK-1"})
        self.assertContains(response, "Sách thử")
        self.assertContains(response, "Ngừng sử dụng")
        response = self.client.get(reverse("library:book_list"), {"q": "missing", "page": "bad"})
        self.assertContains(response, "Không tìm thấy sách")

    def test_mfa_and_permissions_protect_direct_requests(self):
        self.client.force_login(self.editor)
        self.assertRedirects(self.client.get(reverse("library:book_list")), reverse("otp_verify"))
        user = get_user_model().objects.create_user("circulation")
        user.groups.add(Group.objects.get(name="circulation_staff"))
        device = TOTPDevice.objects.create(user=user, confirmed=True)
        self.login_verified(user)
        session = self.client.session
        session["otp_device_id"] = device.persistent_id
        session.save()
        self.assertEqual(self.client.post(reverse("library:book_add"), self.payload()).status_code, 403)
        self.assertEqual(self.client.post(reverse("library:book_edit", args=[self.book.pk]), self.payload()).status_code, 403)
        self.assertEqual(Book.objects.count(), 1)
