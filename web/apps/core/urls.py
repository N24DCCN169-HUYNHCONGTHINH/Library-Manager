from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
    path("reader/", views.reader_portal, name="reader_portal"),
]
