from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse
from .test_circulation import CirculationFixtures
from .desk_browser import desk_browser, browser_context
from .views import circulation_desk
from .models import BookCopy, Loan, Fine
from .services import checkout_copy

class DeskBrowserTests(CirculationFixtures,TestCase):
    def setUp(self):
        self.setup_circulation_data();self.factory=RequestFactory()
    def request(self,data=None,user=None,verified=True,method="get"):
        request=getattr(self.factory,method)(reverse("library:desk_browser"),data or {})
        request.user=user if user is not None else self.staff
        request.session={}
        request.user.is_verified=lambda:verified
        return request
    def test_lists_readers_and_copies_without_writing_transactions(self):
        counts=(Loan.objects.count(),Fine.objects.count())
        response=desk_browser(self.request({"desk_kind":"readers"}))
        self.assertContains(response,'data-desk-pick="reader"')
        self.assertContains(response,'data-code="a"')
        self.assertNotContains(response,self.a.user.email)
        response=desk_browser(self.request({"desk_kind":"copies"}))
        self.assertContains(response,'data-code="COPY-1"')
        self.assertContains(response,'data-desk-pick="checkout"')
        self.assertEqual((Loan.objects.count(),Fine.objects.count()),counts)
    def test_paginated_results_and_filters(self):
        for i in range(15): self.make_copy(f"MORE-{i:02d}")
        first=browser_context(self.request({"desk_kind":"copies"}))
        second=browser_context(self.request({"desk_kind":"copies","desk_page":2}))
        self.assertEqual(len(first["desk_page"]),8);self.assertEqual(len(second["desk_page"]),8)
        self.assertFalse(set(x.pk for x in first["desk_page"]) & set(x.pk for x in second["desk_page"]))
        checkout_copy("a","COPY-1",self.staff)
        context=browser_context(self.request({"desk_kind":"copies","desk_status":"on_loan"}))
        self.assertEqual([x.barcode for x in context["desk_page"]],["COPY-1"])
    def test_return_list_searches_reader_and_fills_exact_physical_barcode(self):
        loan=checkout_copy("a","COPY-1",self.staff)
        response=desk_browser(self.request({"desk_kind":"loans","desk_q":"a"}))
        self.assertContains(response,'data-desk-pick="return"')
        self.assertContains(response,'data-code="COPY-1"')
        loan.refresh_from_db();self.assertEqual(loan.status,"open")
    def test_multiple_name_terms_and_escaped_book_text(self):
        self.a.user.first_name="An";self.a.user.last_name="Nguyễn";self.a.user.save()
        context=browser_context(self.request({"desk_kind":"readers","desk_q":"Nguyễn An"}))
        self.assertEqual([x.pk for x in context["desk_page"]],[self.a.pk])
        type(self.book).objects.filter(pk=self.book.pk).update(title='<img src=x onerror="alert(1)">')
        response=desk_browser(self.request({"desk_kind":"copies"}))
        self.assertContains(response,'&lt;img');self.assertNotContains(response,'<img src=x')
    def test_permission_role_and_mfa_guards(self):
        for user,verified in [(AnonymousUser(),True),(self.a.user,True),(self.staff,False)]:
            self.assertEqual(desk_browser(self.request(user=user,verified=verified)).status_code,302)
        self.staff.groups.clear();self.staff.groups.add(Group.objects.get(name="cataloger"))
        self.staff=get_user_model().objects.get(pk=self.staff.pk)
        self.assertEqual(desk_browser(self.request()).status_code,403)
    def test_each_private_list_requires_its_own_permissions(self):
        group=Group.objects.get(name="circulation_staff")
        group.permissions.remove(Permission.objects.get(content_type__app_label="core",codename="view_readerprofile"))
        self.staff=get_user_model().objects.get(pk=self.staff.pk)
        self.assertEqual(desk_browser(self.request({"desk_kind":"readers"})).status_code,403)
        self.assertEqual(desk_browser(self.request({"desk_kind":"loans"})).status_code,403)
        self.assertEqual(desk_browser(self.request({"desk_kind":"copies"})).status_code,200)
    def test_post_is_not_a_browse_action_and_main_workspace_contains_picker(self):
        self.assertEqual(desk_browser(self.request(method="post")).status_code,405)
        response=circulation_desk(self.request({"tab":"return"}))
        self.assertContains(response,'id="desk-browser"')
        self.assertContains(response,'name="desk_kind"')
        self.assertContains(response,'value="loans" selected')
