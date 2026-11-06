from datetime import datetime, time, timedelta
from django.test import TestCase, RequestFactory
from django.template.loader import render_to_string
from django.utils import timezone
from apps.library.test_circulation import CirculationFixtures
from apps.library.services import checkout_copy
from .dashboard import dashboard_context

class DashboardTests(CirculationFixtures, TestCase):
    def setUp(self):
        self.setup_circulation_data()

    def test_daily_boundary_chart_and_template(self):
        loan = checkout_copy("a", "COPY-1", self.staff)
        today = timezone.localdate()
        midnight = timezone.make_aware(datetime.combine(today, time.min))
        loan.loaned_at = midnight - timedelta(seconds=1)
        loan.save(update_fields=["loaned_at"])
        context = dashboard_context(self.staff, {"period": "day", "date": today.isoformat()})
        self.assertEqual(context["chart_total"], 0)
        self.assertEqual(context["metrics"][0]["note"], "Kỳ trước cùng độ dài: 1 lượt")
        loan.loaned_at = midnight
        loan.save(update_fields=["loaned_at"])
        context = dashboard_context(self.staff, {"period": "day", "date": today.isoformat()})
        self.assertEqual(context["chart_total"], 1)
        self.assertEqual(sum(p["count"] for p in context["chart_points"]), 1)
        request = RequestFactory().get("/staff/")
        request.user = self.staff
        html = render_to_string("core/staff_dashboard.html", context, request=request)
        self.assertIn("Hoạt động mượn sách", html)
        self.assertIn("Sách lưu thông", html)

    def test_no_staff_statistics_for_reader(self):
        context = dashboard_context(self.a.user, {})
        self.assertEqual(context["metrics"], [])
        for key in ("recent_loans", "chart_points", "copy_total", "waiting_reservations"):
            self.assertNotIn(key, context)

    def test_invalid_filters_and_leap_year(self):
        context = dashboard_context(self.staff, {"period": "oops", "date": "9999-12-31"})
        self.assertEqual(context["period"], "month")
        self.assertEqual(context["selected_date"], timezone.localdate())
        context = dashboard_context(self.staff, {"period": "year", "date": "2024-02-29"})
        self.assertEqual(len(context["chart_points"]), 12)
        self.assertEqual((context["range_end"]-context["range_start"]).days, 365)
