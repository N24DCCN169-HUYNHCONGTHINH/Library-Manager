from django.urls import path

from . import views, management_views, reports, payments
from .lookup import lookup
from .desk_browser import desk_browser

app_name = "library"
urlpatterns = [
    path("staff/circulation/browse/", desk_browser, name="desk_browser"),
    path("staff/reports/", reports.reports, name="reports"),
    path("staff/policies/", management_views.policies, name="policies"),
    path("staff/waivers/", management_views.waivers, name="waivers"),
    path("staff/books/<int:book_id>/copies/", management_views.copies, name="copies"),
    path("staff/books/<int:book_id>/copies/<int:copy_id>/lifecycle/", management_views.copy_lifecycle, name="copy_lifecycle"),
    path("staff/books/<int:book_id>/copies/<int:copy_id>/", management_views.copies, name="copy_edit"),
    path("staff/books/<int:book_id>/retire/", management_views.retire_book, name="retire_book"),
    path("covers/<int:book_id>/", management_views.cover_image, name="cover_image"),
    path("payments/damage/<int:case_id>/vnpay/", payments.damage_payment_start, name="damage_payment_start"),
    path("payments/damage/<int:case_id>/confirm-sandbox/", payments.confirm_damage_sandbox, name="confirm_damage_sandbox"),
    path("payments/fines/<int:fine_id>/", payments.payment_start, name="payment_start"),
    path("payments/", payments.payment_history, name="payment_history"),
    path("payments/<uuid:order_id>/", payments.payment_detail, name="payment_detail"),
    path("payments/<uuid:order_id>/simulate/", payments.simulate_payment, name="simulate_payment"),
    path("loans/<int:loan_id>/request-return/", views.request_return_view, name="request_return"),
    path("payments/vnpay/ipn/", payments.vnpay_ipn, name="vnpay_ipn"),
    path("payments/momo/ipn/", payments.momo_ipn, name="momo_ipn"),
    path("lookup/", lookup, name="lookup"),
    path("staff/loans/<int:loan_id>/", views.staff_loan_detail, name="staff_loan_detail"),
    path("staff/damage/quote/", views.damage_quote, name="damage_quote"),
    path("staff/books/", views.book_list, name="book_list"),
    path("staff/books/add/", views.book_edit, name="book_add"),
    path("staff/books/<int:book_id>/edit/", views.book_edit, name="book_edit"),
    path("catalog/", views.catalog, name="catalog"),
    path("staff/circulation/", views.circulation_desk, name="circulation_desk"),
    path("reader/reserve/<int:book_id>/", views.reserve, name="reserve"),
    path("reader/reservation/<int:reservation_id>/cancel/", views.cancel_reservation_view, name="cancel_reservation"),
    path("reader/renew/<int:loan_id>/", views.renew, name="renew"),
]
