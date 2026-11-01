from django.urls import path

from . import views

app_name = "library"
urlpatterns = [
    path("catalog/", views.catalog, name="catalog"),
    path("staff/circulation/", views.circulation_desk, name="circulation_desk"),
    path("reader/reserve/<int:book_id>/", views.reserve, name="reserve"),
    path("reader/reservation/<int:reservation_id>/cancel/", views.cancel_reservation_view, name="cancel_reservation"),
    path("reader/renew/<int:loan_id>/", views.renew, name="renew"),
]
