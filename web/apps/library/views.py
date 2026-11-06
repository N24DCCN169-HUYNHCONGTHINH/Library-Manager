from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.models import ReaderProfile
from apps.core.views import has_role, staff_mfa_required
from .forms import BookForm, CheckoutForm, FinePaymentForm, ReturnForm, RenewalForm, ReopenReaderForm
from .models import Book, BookCopy, DamageCase, Fine, LibraryBranch, Loan, LoanNotification, Reservation
from .services import CirculationError, cancel_reservation, checkout_copy, place_reservation, record_fine_payment, renew_loan, return_copy, expire_ready_reservations
from .services import reopen_reader
from .forms import DamageQuoteForm
from .damage_pricing import quote_damage


@never_cache
@staff_mfa_required
def staff_loan_detail(request, loan_id):
    if not request.user.has_perm("library.view_loan"):
        return HttpResponseForbidden("Bạn không được cấp quyền xem lượt mượn.")
    loan = get_object_or_404(Loan.objects.select_related("reader__user", "copy__book", "copy__branch").defer('copy__book__cover_image'), pk=loan_id)
    fine = Fine.objects.filter(loan=loan).first() if request.user.has_perm("library.view_fine") else None
    events = list(loan.events.select_related("actor").order_by("occurred_at", "pk")) if request.user.has_perm("library.view_loanevent") else []
    event_labels = {"checkout": "Cho mượn", "return": "Nhận trả", "renewal": "Gia hạn", "renew": "Gia hạn",
        "long_overdue_review": "Chạm trần phạt — cần xem xét", "damage_approved": "Duyệt hồ sơ hư hỏng"}
    for event in events:
        event.display_label = event_labels.get(event.event_type, "Cập nhật giao dịch")
    return render(request, "library/staff_loan_detail.html", {"loan": loan, "fine": fine,
        "events": events,
        "payments": fine.transactions.all() if fine and request.user.has_perm("library.view_finepayment") else []})


@never_cache
@staff_mfa_required
def damage_quote(request):
    if not request.user.has_perm("library.approve_damagecase"):
        return HttpResponseForbidden("Chỉ quản lý được lập mức bồi thường có căn cứ.")
    form = DamageQuoteForm(request.POST if request.method == "POST" else None)
    quote = None
    if request.method == "POST" and form.is_valid():
        try:
            quote = quote_damage(**form.cleaned_data)
        except CirculationError as exc:
            form.add_error(None, str(exc))
    return render(request, "library/damage_quote.html", {"form": form, "quote": quote})


@staff_mfa_required
def book_list(request):
    if not request.user.has_perm("library.view_book"):
        return HttpResponseForbidden("Bạn không được cấp quyền xem danh mục nội bộ.")
    query = request.GET.get("q", "").strip()
    books = Book.objects.defer("cover_image").order_by("title", "pk")
    if query:
        books = books.filter(Q(title__icontains=query) | Q(authors__icontains=query)
                             | Q(catalog_number__icontains=query) | Q(isbn__icontains=query))
    books = books.annotate(copy_count=Count("copies", filter=Q(copies__is_active=True), distinct=True),
        ready_count=Count("copies", filter=Q(copies__is_active=True, copies__status=BookCopy.Status.AVAILABLE, is_active=True), distinct=True))
    page = Paginator(books, 24).get_page(request.GET.get("page"))
    return render(request, "library/book_list.html", {
        "page_obj": page, "query": query,
    })


@staff_mfa_required
def book_edit(request, book_id=None):
    permission = "library.add_book" if book_id is None else "library.change_book"
    if not request.user.has_perm(permission):
        return HttpResponseForbidden("Bạn không được cấp quyền thay đổi danh mục.")
    book = get_object_or_404(Book, pk=book_id) if book_id is not None else None
    form = BookForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=book)
    if request.method == "POST" and form.is_valid():
        book = form.save(commit=False)
        if book_id is None:
            book.created_by = request.user
        book.updated_by = request.user
        book.save()
        from apps.core.lifecycle import record_security_event
        from apps.core.models import AccountSecurityEvent
        record_security_event(request.user, AccountSecurityEvent.Kind.SYSTEM_OPERATION, request.user, {"book":book.pk,"fields":form.changed_data}, reason="Cập nhật danh mục sách")
        messages.success(request, "Đã lưu thông tin sách.")
        return redirect("library:book_list")
    return render(request, "library/book_form.html", {"form": form, "book": book})


def catalog(request):
    query = request.GET.get("q", "").strip()
    branch_id = request.GET.get("branch", "").strip()
    branches = LibraryBranch.objects.filter(is_active=True)
    books = Book.objects.filter(is_active=True).defer("cover_image")
    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(authors__icontains=query) | Q(isbn__icontains=query)
            | Q(catalog_number__icontains=query) | Q(subjects__icontains=query)
            | Q(copies__barcode__icontains=query)
        )
    if branch_id.isdigit():
        books = books.filter(copies__branch_id=branch_id, copies__is_active=True)
        available_filter = Q(copies__status=BookCopy.Status.AVAILABLE, copies__is_active=True, copies__branch_id=branch_id)
        copies = BookCopy.objects.filter(branch_id=branch_id, is_active=True).select_related("branch")
    else:
        branch_id = ""
        available_filter = Q(copies__status=BookCopy.Status.AVAILABLE, copies__is_active=True)
        copies = BookCopy.objects.filter(is_active=True).select_related("branch")
    books = books.annotate(
        available_copies_count=Count("copies", filter=available_filter, distinct=True),
        has_available_copies_anywhere=Exists(BookCopy.objects.filter(
            book_id=OuterRef("pk"), status=BookCopy.Status.AVAILABLE, is_active=True,
        )),
        has_loanable_copies=Exists(BookCopy.objects.filter(book_id=OuterRef("pk"), is_active=True)
            .filter(Q(home_loan_override=True) | Q(home_loan_override__isnull=True, book__loan_mode=Book.LoanMode.HOME_LOAN))),
        has_available_loanable_copies=Exists(BookCopy.objects.filter(book_id=OuterRef("pk"), is_active=True,
            status=BookCopy.Status.AVAILABLE).filter(Q(home_loan_override=True)
            | Q(home_loan_override__isnull=True, book__loan_mode=Book.LoanMode.HOME_LOAN))),
    ).prefetch_related(
        Prefetch("copies", queryset=copies, to_attr="catalog_copies")
    ).distinct()
    is_reader = request.user.is_authenticated and request.user.groups.filter(name="reader").exists()
    page = Paginator(books.order_by("title", "pk"), 12).get_page(request.GET.get("page"))
    return render(request, "library/catalog.html", {
        "books": page, "page_obj": page, "query": query, "is_reader": is_reader, "branches": branches, "selected_branch": branch_id,
    })


@never_cache
@staff_mfa_required
def circulation_desk(request):
    if not (request.user.is_superuser or (request.user.has_perm("library.view_loan") and request.user.has_perm("library.view_fine"))):
        return HttpResponseForbidden("Bạn không được cấp quyền xem quầy lưu thông.")
    tabs = {"checkout", "return", "loans", "renew", "damage", "overdue", "notices", "reservations", "fines"}
    action_tabs = {"checkout": "checkout", "return": "return", "renew": "renew", "payment": "fines", "reopen": "overdue", "expire": "reservations"}
    active_tab = request.GET.get("tab", "checkout")
    if request.method == "POST":
        active_tab = action_tabs.get(request.POST.get("action"), "checkout")
    if active_tab not in tabs:
        active_tab = "checkout"
    checkout_initial = {"barcode": request.GET.get("barcode", "")[:64]} if request.method == "GET" else {}
    checkout_form = CheckoutForm(request.POST if request.method == "POST" and request.POST.get("action") == "checkout" else None, initial=checkout_initial, auto_id="checkout_%s")
    return_form = ReturnForm(request.POST if request.method == "POST" and request.POST.get("action") == "return" else None, auto_id="return_%s")
    payment_form = FinePaymentForm(request.POST if request.method == "POST" and request.POST.get("action") == "payment" else None, auto_id="payment_%s")
    renewal_form = RenewalForm(request.POST if request.method == "POST" and request.POST.get("action") == "renew" else None, auto_id="renewal_%s")
    if request.method == "GET":
        return_form.initial["barcode"] = request.GET.get("barcode", "")[:64]
        for form, key, parameter in ((renewal_form, "loan_id", "loan"), (payment_form, "fine_id", "fine")):
            value = request.GET.get(parameter, "")
            if value.isascii() and value.isdigit() and len(value) < 10:
                form.initial[key] = value
    reopen_form = ReopenReaderForm(request.POST if request.method == "POST" and request.POST.get("action") == "reopen" else None)
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            forms = {"checkout": checkout_form, "return": return_form, "payment": payment_form, "renew": renewal_form, "reopen": reopen_form}
            permissions = {"checkout": "checkout_loan", "return": "return_loan", "payment": "collect_finepayment", "renew": "renew_loan", "expire": "manage_reservation", "reopen": "manage_reader_restrictions"}
            if action not in permissions:
                messages.error(request, "Thao tác không hợp lệ.")
            elif not request.user.has_perm(f"library.{permissions[action]}"):
                return HttpResponseForbidden("Bạn không được cấp quyền thực hiện thao tác này.")
            elif action == "expire":
                count = expire_ready_reservations()
                if request.headers.get("Accept") == "application/json":
                    reservations = Reservation.objects.select_related("reader", "book", "copy", "notification").defer('book__cover_image').filter(status__in=["waiting", "ready"]).order_by("created_at", "pk")[:50]
                    html = render_to_string("library/partials/reservation_rows.html", {"reservations": reservations}, request=request)
                    return JsonResponse({"message": f"Đã kiểm tra: {count} yêu cầu hết hạn được xử lý.", "html": html})
                messages.success(request, f"Đã xử lý {count} yêu cầu hết hạn giữ chỗ.")
                return redirect(reverse("library:circulation_desk") + "?tab=reservations")
            elif forms[action].is_valid():
                data = forms[action].cleaned_data
                if action == "reopen":
                    reopen_reader(data["reader_number"], request.user, data["reason"])
                    messages.success(request, "Đã mở lại hồ sơ và lưu căn cứ xử lý.")
                elif action == "checkout":
                    loan = checkout_copy(data["reader_number"], data["barcode"], request.user, data["idempotency_key"])
                    messages.success(request, f"Đã ghi nhận mượn #{loan.pk}. Hạn trả: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M}.")
                elif action == "return":
                    loan = return_copy(data["barcode"], request.user, data["condition_note"], data["idempotency_key"], data["condition_kind"])
                    messages.success(request, "Đã xử lý trả sách; tình trạng và căn cứ đã được ghi nhận.")
                elif action == "renew":
                    loan = renew_loan(data["loan_id"], request.user, data["idempotency_key"])
                    messages.success(request, f"Đã gia hạn #{loan.pk}. Hạn mới: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M}.")
                else:
                    row = record_fine_payment(data["fine_id"], data["amount"], request.user, reason=data["reason"], idempotency_key=data["idempotency_key"])
                    messages.success(request, f"Đã ghi nhận thanh toán. Biên nhận: {row.receipt_number}.")
                return redirect(reverse("library:circulation_desk") + "?tab=" + active_tab)
        except (CirculationError, ObjectDoesNotExist) as exc:
            if action in forms:
                forms[action].add_error(None, str(exc) if isinstance(exc, CirculationError) else "Không tìm thấy độc giả, bản sách hoặc lượt giao dịch.")
            else:
                messages.error(request, str(exc))
    loans = list(Loan.objects.filter(status=Loan.Status.OPEN).select_related("reader", "copy__book").defer('copy__book__cover_image').order_by("due_at")[:50])
    overdue_loans = [loan for loan in loans if loan.due_at < timezone.now()]
    unpaid_fines = Fine.objects.filter(status=Fine.Status.DUE).select_related("loan__reader", "loan__copy__book").defer('loan__copy__book__cover_image').prefetch_related("transactions").order_by("calculated_at")[:50]
    reservations = Reservation.objects.select_related("reader", "book", "copy", "notification").defer('book__cover_image').filter(status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).order_by("created_at", "pk")[:50]
    from .desk_browser import browser_context
    try: browse = browser_context(request)
    except PermissionError: return HttpResponseForbidden()
    return render(request, "library/circulation_desk.html", {**browse,"checkout_form": checkout_form, "return_form": return_form, "payment_form": payment_form, "renewal_form": renewal_form, "reopen_form": reopen_form, "loans": loans, "overdue_loans": overdue_loans, "active_tab": active_tab,
        "damage_cases": DamageCase.objects.select_related("loan__copy__book", "loan__reader").defer('loan__copy__book__cover_image').order_by("-reported_at")[:50] if request.user.has_perm("library.view_damagecase") else [],
        "loan_notices": LoanNotification.objects.select_related("loan__copy__book", "loan__reader").defer('loan__copy__book__cover_image').order_by("-created_at")[:50] if request.user.has_perm("library.view_loannotification") else [],
        "unpaid_fines": unpaid_fines, "reservations": reservations})


@never_cache
@login_required
@user_passes_test(has_role("reader"), login_url="home")
@require_POST
def reserve(request, book_id):
    if request.method == "POST":
        try:
            profile = request.user.reader_profile
            place_reservation(profile, book_id, request.user)
            messages.success(request, "Đã thêm bạn vào hàng chờ của đầu sách.")
        except (CirculationError, ObjectDoesNotExist, Book.DoesNotExist) as exc:
            messages.error(request, str(exc) or "Không thể tạo yêu cầu đặt trước.")
    return redirect("library:catalog")


@never_cache
@login_required
@user_passes_test(has_role("reader"), login_url="home")
@require_POST
def renew(request, loan_id):
    if request.method == "POST":
        try:
            profile = request.user.reader_profile
            loan = get_object_or_404(Loan, pk=loan_id, reader=profile)
            loan = renew_loan(loan.pk, request.user)
            messages.success(request, f"Đã gia hạn. Hạn trả mới: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M}.")
        except (CirculationError, ObjectDoesNotExist) as exc:
            messages.error(request, str(exc) or "Không thể gia hạn lượt mượn.")
    return redirect("reader_portal")


@never_cache
@login_required
@user_passes_test(has_role("reader"), login_url="home")
@require_POST
def cancel_reservation_view(request, reservation_id):
    if request.method == "POST":
        try:
            profile = request.user.reader_profile
            get_object_or_404(Reservation, pk=reservation_id, reader=profile)
            cancel_reservation(profile, reservation_id, request.user)
            messages.success(request, "Đã hủy yêu cầu đặt trước.")
        except (CirculationError, ObjectDoesNotExist) as exc:
            messages.error(request, str(exc) or "Không thể hủy yêu cầu đặt trước.")
    return redirect("reader_portal")
