"""Read-only, paginated selectors for the circulation counter."""
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.utils import timezone
from apps.core.models import ReaderProfile
from apps.core.views import staff_mfa_required
from .models import BookCopy, Loan

DESK_TABS = {"checkout", "return", "loans", "renew", "damage", "overdue", "notices", "reservations", "fines"}

KINDS={"readers":("core.view_readerprofile",),"copies":("library.view_book","library.view_bookcopy"),"loans":("library.view_loan","core.view_readerprofile","library.view_bookcopy","library.view_book")}

def can_browse(user):
    return user.has_perms(["library.view_loan","library.view_fine"])

def browser_context(request):
    allowed=[kind for kind,permissions in KINDS.items() if request.user.has_perms(permissions)]
    if not allowed: return {"desk_browser_enabled":False}
    tab = request.GET.get("tab", "checkout")
    if tab not in DESK_TABS:
        tab = "checkout"
    kind=request.GET.get("desk_kind", "loans" if tab=="return" and "loans" in allowed else allowed[0])
    if kind not in KINDS: kind=allowed[0]
    if kind not in allowed: raise PermissionError
    query=request.GET.get("desk_q", "").strip()[:120]
    status=request.GET.get("desk_status", "all")
    if status not in {"all","available","on_loan"}: status="all"
    if kind=="readers":
        rows=ReaderProfile.objects.select_related("user").defer("user__password","user__email").order_by("user__last_name","user__first_name","reader_number")
        for term in query.split()[:8]: rows=rows.filter(Q(reader_number__icontains=term)|Q(user__username__icontains=term)|Q(user__first_name__icontains=term)|Q(user__last_name__icontains=term))
    elif kind=="copies":
        rows=BookCopy.objects.select_related("book","branch").defer("book__cover_image").filter(is_active=True,book__is_active=True).order_by("book__title","barcode")
        if query: rows=rows.filter(Q(barcode__icontains=query)|Q(book__title__icontains=query)|Q(book__authors__icontains=query)|Q(book__catalog_number__icontains=query)|Q(book__isbn__icontains=query)|Q(branch__name__icontains=query))
        if status!="all": rows=rows.filter(status=status)
    else:
        rows=Loan.objects.filter(status=Loan.Status.OPEN).select_related("copy__book","copy__branch","reader__user").defer("copy__book__cover_image","reader__user__password","reader__user__email").order_by("due_at","pk")
        if query: rows=rows.filter(Q(copy__barcode__icontains=query)|Q(copy__book__title__icontains=query)|Q(reader__reader_number__icontains=query)|Q(reader__user__first_name__icontains=query)|Q(reader__user__last_name__icontains=query))
    page=Paginator(rows,8).get_page(request.GET.get("desk_page"))
    return {"desk_browser_enabled":True,"desk_allowed_kinds":allowed,"desk_kind":kind,"desk_query":query,"desk_status":status,"desk_page":page,"desk_today":timezone.localdate(),"desk_tab":tab}

@never_cache
@staff_mfa_required
@require_GET
def desk_browser(request):
    if not can_browse(request.user): return HttpResponseForbidden()
    try: context=browser_context(request)
    except PermissionError: return HttpResponseForbidden()
    if not context.get("desk_browser_enabled"): return HttpResponseForbidden()
    return render(request,"library/partials/desk_browser_results.html",context)
