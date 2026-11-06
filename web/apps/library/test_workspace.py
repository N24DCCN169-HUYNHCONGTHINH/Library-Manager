import json
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .test_circulation import CirculationFixtures
from .services import checkout_copy
from .views import circulation_desk
from apps.core.dashboard import dashboard_context


class WorkspaceTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()
        self.staff.groups.add(Group.objects.get(name="library_manager"))
        self.staff = type(self.staff).objects.get(pk=self.staff.pk)
        self.factory = RequestFactory()

    def request(self, method, data=None, **headers):
        request = getattr(self.factory, method)(reverse("library:circulation_desk"), data or {}, **headers)
        request.user = self.staff
        request.user.is_verified = lambda: True
        return request

    def test_workspace_links_and_active_panel_render_without_any_write(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        response = circulation_desk(self.request("get", {"tab": "reservations"}))
        self.assertContains(response, 'data-circulation-menu')
        self.assertContains(response, 'data-desk-panel="reservations" id="reservations" >')
        self.assertContains(response, 'data-desk-panel="checkout" id="checkout" hidden')
        self.assertContains(response, 'data-async-expire')
        loan.refresh_from_db()
        self.assertEqual(loan.status, "open")

    def test_expiry_updates_only_rows_with_json_and_no_mail_side_effect(self):
        with patch("apps.library.views.expire_ready_reservations", return_value=0) as expire:
            response = circulation_desk(self.request("post", {"action": "expire"}, HTTP_ACCEPT="application/json"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(expire.call_count, 1)
        data = json.loads(response.content)
        self.assertIn("table", data["html"])
        self.assertNotIn("<html", data["html"])
        self.assertIn("0 yêu cầu", data["message"])
        self.assertEqual(len(mail.outbox), 0)

    def test_expiry_without_js_preserves_reservation_page(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.request("post", {"action": "expire"})
        request.session = {}
        request._messages = FallbackStorage(request)
        response = circulation_desk(request)
        self.assertEqual(response.url, reverse("library:circulation_desk") + "?tab=reservations")

    def test_empty_historical_period_does_not_reuse_current_totals(self):
        checkout_copy("a", "COPY-1", self.staff)
        data = dashboard_context(self.staff, {"period": "day", "date": "2020-01-01"})
        self.assertTrue(all(metric["value"] == 0 for metric in data["metrics"]))
        self.assertEqual(list(data["recent_loans"]), [])
        self.assertEqual(data["current_books"], 1)
