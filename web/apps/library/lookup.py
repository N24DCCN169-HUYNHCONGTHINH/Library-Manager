from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from urllib.parse import urlencode

from apps.core.models import ReaderProfile
from apps.core.views import has_staff_role
from .models import Book, BookCopy, Fine, Loan


@never_cache
@require_GET
def lookup(request):
    kind = request.GET.get("kind", "books")
    query = request.GET.get("q", "").strip()[:100]
    permissions = {"staff_books": "library.view_book", "readers": "core.view_readerprofile",
                   "copies": "library.view_bookcopy", "loans": "library.view_loan", "fines": "library.view_fine"}
    if kind != "books":
        if kind not in permissions:
            return JsonResponse({"error": "Loại tìm kiếm không hợp lệ."}, status=400)
        if not (has_staff_role(request.user) and request.user.is_verified()
                and request.user.has_perm(permissions[kind])):
            return JsonResponse({"error": "Cần đăng nhập nhân viên, xác minh hai bước và quyền xem phù hợp."}, status=403)
    if len(query) < 2 and not (kind in {"loans", "fines"} and query.isascii() and query.isdigit()):
        return JsonResponse({"results": []})
    results = []
    if kind in {"books", "staff_books"}:
        rows = Book.objects.all() if kind == "staff_books" else Book.objects.filter(is_active=True)
        branch = request.GET.get("branch", "")
        if kind == "books" and branch.isascii() and branch.isdigit() and len(branch) < 10:
            rows = rows.filter(copies__branch_id=int(branch), copies__is_active=True)
        rows = rows.filter(Q(title__icontains=query) | Q(authors__icontains=query) | Q(catalog_number__icontains=query) | Q(isbn__icontains=query) | Q(copies__barcode__icontains=query) | Q(copies__shelf_location__icontains=query)).distinct().order_by("title", "pk")[:8]
        for row in rows:
            url = reverse("library:catalog") + "?" + urlencode({"q": row.catalog_number})
            if kind == "books" and branch.isascii() and branch.isdigit() and len(branch) < 10:
                url += "&" + urlencode({"branch": branch})
            if kind == "staff_books" and request.user.has_perm("library.change_book"):
                url = reverse("library:book_edit", args=[row.pk])
            results.append({"label": row.title, "detail": f"{row.authors} · {row.catalog_number}", "value": row.catalog_number, "url": url})
    elif kind == "readers":
        rows = ReaderProfile.objects.select_related("user")
        for term in query.split()[:6]:
            rows = rows.filter(Q(reader_number__icontains=term) | Q(user__username__icontains=term) | Q(user__first_name__icontains=term) | Q(user__last_name__icontains=term) | Q(user__email__icontains=term))
        status = request.GET.get("status", "")
        if status in ReaderProfile.Status.values:
            rows = rows.filter(status=status)
        rows = rows.order_by("reader_number")[:8]
        for row in rows:
            url = reverse("reader_list") + "?" + urlencode({"q": row.reader_number})
            if request.user.has_perm("core.change_readerprofile"):
                url = reverse("reader_edit", args=[row.pk])
            results.append({"label": row.user.get_full_name() or row.user.username, "detail": f"{row.reader_number} · {row.get_status_display()}", "value": row.reader_number, "url": url})
    elif kind == "copies":
        rows = BookCopy.objects.select_related("book", "branch").filter(Q(barcode__icontains=query) | Q(book__title__icontains=query) | Q(book__catalog_number__icontains=query)).order_by("barcode")[:8]
        for row in rows:
            results.append({"label": row.book.title, "detail": f"{row.barcode} · {row.get_status_display()} · {row.branch.name if row.branch else ''}", "value": row.barcode})
    else:
        match = Q(copy__barcode__icontains=query) | Q(copy__book__title__icontains=query) | Q(reader__reader_number__icontains=query)
        if kind == "loans":
            rows = Loan.objects.filter(status=Loan.Status.OPEN).select_related("copy__book", "reader").filter(match | (Q(pk=int(query)) if query.isascii() and query.isdigit() and len(query) < 10 else Q(pk__isnull=True))).order_by("due_at")[:8]
            for row in rows:
                results.append({"label": row.copy.book.title, "detail": f"#{row.pk} · {row.copy.barcode} · {row.reader.reader_number}", "value": str(row.pk), "url": reverse("library:staff_loan_detail", args=[row.pk])})
        else:
            match = Q(loan__copy__barcode__icontains=query) | Q(loan__copy__book__title__icontains=query) | Q(loan__reader__reader_number__icontains=query)
            if query.isascii() and query.isdigit() and len(query) < 10:
                match |= Q(pk=int(query))
            rows = Fine.objects.select_related("loan__copy__book", "loan__reader").filter(match).order_by("-calculated_at")[:8]
            for row in rows:
                results.append({"label": row.loan.copy.book.title, "detail": f"Khoản #{row.pk} · {row.loan.reader.reader_number} · còn {row.balance:,.0f} ₫", "value": str(row.pk), "url": reverse("library:staff_loan_detail", args=[row.loan_id])})
    return JsonResponse({"results": results})
