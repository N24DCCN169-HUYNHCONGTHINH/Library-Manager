from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.core import views
from apps.core.forms import VerifiedReaderEmailPasswordResetForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_change/", views.AuditedPasswordChangeView.as_view(), name="password_change"),
    path("accounts/password_change/done/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
    path("accounts/password_reset/", views.AuditedPasswordResetView.as_view(form_class=VerifiedReaderEmailPasswordResetForm, template_name="registration/password_reset_form.html", email_template_name="registration/password_reset_email.html", subject_template_name="registration/password_reset_subject.txt"), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", views.AuditedPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
    path("accounts/authenticator/setup/", views.otp_setup, name="otp_setup"),
    path("accounts/authenticator/verify/", views.otp_verify, name="otp_verify"),
    path("accounts/invitation/<str:token>/", views.account_invite_accept, name="account_invite_accept"),
    path("accounts/email/change/", views.email_change_request, name="email_change_request"),
    path("accounts/email/confirm/<str:token>/", views.email_change_confirm, name="email_change_confirm"),
    path("library/", include("apps.library.urls")),
    path("", include("apps.core.urls")),
]
