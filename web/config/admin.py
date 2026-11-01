from django.contrib.admin.apps import AdminConfig


class LibraryAdminConfig(AdminConfig):
    default_site = "django_otp.admin.OTPAdminSite"
