"""Permission-scoped, read-only statistics for the staff dashboard."""
from datetime import date, datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone


def dashboard_context(user, params):
    from apps.library.models import Book, BookCopy, Loan, Reservation
    from .models import ReaderProfile

    today = timezone.localdate()
    try:
        selected = date.fromisoformat(params.get("date", ""))
        if not 2000 <= selected.year <= 2099:
            selected = today
    except (ValueError, TypeError):
        selected = today
    period = params.get("period", "month")
    if period not in ("day", "week", "month", "year"):
        period = "month"
    if period == "day":
        start, end = selected, selected + timedelta(days=1)
    elif period == "week":
        start = selected - timedelta(days=selected.weekday())
        end = start + timedelta(days=7)
    elif period == "year":
        start, end = date(selected.year, 1, 1), date(selected.year + 1, 1, 1)
    else:
        start = selected.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    def aware(value):
        return timezone.make_aware(datetime.combine(value, time.min))
    context = {"period": period, "selected_date": selected, "range_start": start,
               "range_end": end - timedelta(days=1), "dashboard_today": today}
    metrics = []
    if user.has_perm("library.view_loan"):
        loans = Loan.objects.all()
        current = loans.filter(loaned_at__gte=aware(start), loaned_at__lt=aware(end)).count()
        previous = loans.filter(loaned_at__gte=aware(start - (end-start)), loaned_at__lt=aware(start)).count()
        metrics.append({"label": "Lượt mượn trong kỳ", "value": current,
                        "note": f"Kỳ trước cùng độ dài: {previous} lượt", "featured": True})
        metrics.append({"label": "Lượt trả trong kỳ", "value": loans.filter(returned_at__gte=aware(start), returned_at__lt=aware(end)).count(),
                        "note": "Theo ngày xác nhận nhận trả"})
        context["current_overdue"] = loans.filter(status="open", due_at__lt=timezone.now()).count()
        trunc = TruncMonth if period == "year" else TruncDate
        rows = loans.filter(loaned_at__gte=aware(start), loaned_at__lt=aware(end)).annotate(bucket=trunc("loaned_at")).values("bucket").annotate(total=Count("pk"))
        counts = {(r["bucket"].date() if isinstance(r["bucket"], datetime) else r["bucket"]): r["total"] for r in rows}
        points = []
        cursor = start
        while cursor < end:
            points.append({"label": f"T{cursor.month}" if period == "year" else cursor.strftime("%d/%m"), "count": counts.get(cursor, 0)})
            cursor = (cursor + timedelta(days=32)).replace(day=1) if period == "year" else cursor + timedelta(days=1)
        maximum = max([p["count"] for p in points] + [1])
        for point in points:
            point["height"] = round(point["count"] * 100 / maximum)
        context.update(chart_points=points, chart_total=current, chart_max=maximum,
                       recent_loans=loans.filter(loaned_at__gte=aware(start), loaned_at__lt=aware(end)).select_related("reader__user", "copy__book").order_by("-loaned_at", "-pk")[:8])
        dates = [selected + timedelta(days=i) for i in range(7)]
        due_counts = {r["bucket"]: r["total"] for r in loans.filter(status="open", due_at__gte=aware(dates[0]), due_at__lt=aware(dates[-1]+timedelta(days=1))).annotate(bucket=TruncDate("due_at")).values("bucket").annotate(total=Count("pk"))}
        weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        context["due_days"] = [{"date": d, "weekday": weekdays[d.weekday()], "count": due_counts.get(d, 0), "today": d == today} for d in dates]
        context["due_total"] = sum(due_counts.values())
    if user.has_perm("core.view_readerprofile"):
        metrics.append({"label": "Độc giả mới trong kỳ", "value": ReaderProfile.objects.filter(created_at__gte=aware(start), created_at__lt=aware(end)).count(), "note": "Hồ sơ được tạo trong khoảng đã chọn"})
    if user.has_perm("library.view_book"):
        metrics.append({"label": "Đầu sách bổ sung trong kỳ", "value": Book.objects.filter(created_at__gte=aware(start), created_at__lt=aware(end)).count(), "note": "Theo ngày tạo đầu sách"})
        context["current_books"] = Book.objects.filter(is_active=True).count()
    if user.has_perm("library.view_bookcopy"):
        total = BookCopy.objects.filter(is_active=True).count()
        available = BookCopy.objects.filter(status="available", is_active=True, book__is_active=True).count()
        context.update(copy_total=total, available_copies=available, availability_percent=round(available * 100 / total) if total else 0)
    if user.has_perm("library.view_reservation"):
        context["waiting_reservations"] = Reservation.objects.filter(status="waiting").count()
        context["ready_reservations"] = Reservation.objects.filter(status="ready").count()
    context["metrics"] = metrics
    return context
