def library_roles(request):
    user = request.user
    if not user.is_authenticated:
        return {"library_roles": {"librarian": False, "reader": False}}
    if user.is_superuser:
        return {"library_roles": {"librarian": True, "reader": False, "can_circulate": True, "can_catalog": True, "staff_roles": ["system_admin"]}}
    roles = set(user.groups.values_list("name", flat=True))
    staff_roles = {"librarian", "circulation_staff", "cataloger", "library_manager", "system_admin"}
    return {
        "library_roles": {
            "librarian": bool(roles & staff_roles),
            "reader": "reader" in roles,
            "can_circulate": user.has_perm("library.view_loan") and user.has_perm("library.view_fine"),
            "can_catalog": user.has_perm("library.view_book"),
            "staff_roles": sorted(roles & staff_roles),
        }
    }


def appearance_context(request):
    from .models import AppearancePreferences
    prefs = None
    if request.user.is_authenticated:
        prefs = AppearancePreferences.objects.defer("avatar_image", "background_image").filter(user=request.user).first()
    return {"appearance_prefs": prefs}


def circulation_bell(request):
    from django.utils.functional import SimpleLazyObject

    return {"circulation_bell": SimpleLazyObject(lambda: _bell_counts(request.user))}


def _bell_counts(user):
    from datetime import datetime, time, timedelta

    from django.contrib.auth import get_user_model
    from django.db.models import Count, IntegerField, Subquery, Value
    from django.db.models.functions import Coalesce
    from django.utils import timezone

    from apps.library.models import DamageCase, Fine, Loan, Reservation

    staff = user.has_perms(["library.view_loan", "library.view_fine"])
    loans = Loan.objects.filter(status=Loan.Status.OPEN)
    reservations = Reservation.objects.filter(status__in=[Reservation.Status.WAITING, Reservation.Status.READY])
    fines = Fine.objects.filter(status=Fine.Status.DUE)
    damage = DamageCase.objects.filter(status=DamageCase.Status.APPROVED, replacement_amount__isnull=False)
    if not staff:
        loans = loans.filter(reader__user=user)
        reservations = reservations.filter(reader__user=user)
        fines = fines.filter(loan__reader__user=user)
        damage = damage.filter(loan__reader__user=user)
    elif not user.has_perm("library.view_reservation"):
        reservations = reservations.none()

    now = timezone.now()
    end = timezone.make_aware(datetime.combine(timezone.localdate(now) + timedelta(days=4), time.min))
    reminders = loans.filter(due_at__gte=now, due_at__lt=end)

    def count_rows(rows):
        grouped = rows.order_by().annotate(bucket=Value(1)).values("bucket").annotate(total=Count("pk"))
        return Coalesce(Subquery(grouped.values("total"), output_field=IntegerField()), 0)

    can_see_damage = staff and (user.has_perm("library.view_damagecase") or user.has_perm("library.collect_finepayment"))
    counts = get_user_model().objects.filter(pk=user.pk).annotate(
        open_count=count_rows(loans),
        reservation_count=count_rows(reservations),
        reminder_count=count_rows(reminders),
        overdue_count=count_rows(loans.filter(due_at__lt=now)),
        fine_count=count_rows(fines) + count_rows(damage if can_see_damage else damage.none()),
    ).values("open_count", "reservation_count", "reminder_count", "overdue_count", "fine_count").get()
    counts["total"] = sum(counts.values())
    return counts
