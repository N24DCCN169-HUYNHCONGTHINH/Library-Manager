from django.urls import path
from . import views
from . import reader_views, account_views, operations_views

urlpatterns = [
    path("staff/access/", operations_views.role_inspector, name="role_inspector"),
    path("staff/operations/", operations_views.operations, name="operations"),
    path("staff/operations/backup/", operations_views.backup_download, name="backup_download"),
    path("staff/operations/restore/", operations_views.restore_rehearsal, name="restore_rehearsal"),
    path("staff/operations/sessions/<int:user_id>/", operations_views.revoke_sessions, name="revoke_sessions"),
    path("profile/", account_views.profile, name="profile"),
    path("settings/appearance/", account_views.appearance_settings, name="appearance_settings"),
    path("settings/theme/", account_views.theme_change, name="theme_change"),
    path("settings/image/<str:kind>/", account_views.appearance_image, name="appearance_image"),
    path("staff/accounts/", account_views.account_list, name="account_list"),
    path("staff/accounts/add/", account_views.account_add, name="account_add"),
    path("staff/accounts/<int:user_id>/", account_views.account_detail, name="account_detail"),
    path("reader/loans/<int:loan_id>/", views.reader_loan_detail, name="reader_loan_detail"),
    path("staff/readers/", reader_views.reader_list, name="reader_list"),
    path("staff/readers/add/", reader_views.reader_add, name="reader_add"),
    path("staff/readers/<int:reader_id>/edit/", reader_views.reader_edit, name="reader_edit"),
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
    path("reader/", views.reader_portal, name="reader_portal"),
]
