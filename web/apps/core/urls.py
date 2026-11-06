from django.urls import path
from . import views
from . import reader_views

urlpatterns = [
    path("reader/loans/<int:loan_id>/", views.reader_loan_detail, name="reader_loan_detail"),
    path("staff/readers/", reader_views.reader_list, name="reader_list"),
    path("staff/readers/add/", reader_views.reader_add, name="reader_add"),
    path("staff/readers/<int:reader_id>/edit/", reader_views.reader_edit, name="reader_edit"),
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
    path("reader/", views.reader_portal, name="reader_portal"),
]
