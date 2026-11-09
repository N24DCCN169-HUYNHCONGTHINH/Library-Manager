from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.models import ReaderProfile, SystemConfiguration
from apps.core.views import has_role, staff_mfa_required
from .forms import BookForm, CheckoutForm, FinePaymentForm, ReturnForm, RenewalForm, ReopenReaderForm, ReservationRequestForm
from .models import Book, BookCopy, DamageCase, Fine, LibraryBranch, Loan, LoanEvent, LoanNotification, Reservation
from .services import CirculationError, DamageRestrictionError, cancel_reservation, checkout_copy, place_reservation, record_fine_payment, renew_loan, return_copy, expire_ready_reservations
from .services import checkout_reservation, reopen_reader, request_return, report_lost_loan, settle_damage_case, update_damaged_copy_status
from .services import approve_damage_case, prepare_loan_notifications, refresh_overdue_loans
from .forms import DamageApprovalForm, DamageQuoteForm
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
        "long_overdue_review": "Chạm trần phạt — cần xem xét", "damage_approved": "Duyệt hồ sơ hư hỏng", "return_requested": "Độc giả yêu cầu trả"}
    for event in events:
        event.display_label = event_labels.get(event.event_type, "Cập nhật giao dịch")
    return render(request, "library/staff_loan_detail.html", {"loan": loan, "fine": fine,
        "events": events,
        "can_open_renewal": loan.status == Loan.Status.OPEN and loan.due_at >= timezone.now() and request.user.has_perm("library.renew_loan"),
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
    from apps.core.memberships import guest_profile
    guest_reader = guest_profile(request)
    member = getattr(request.user, "reader_profile", None) if is_reader else guest_reader
    page = Paginator(books.order_by("title", "pk"), 12).get_page(request.GET.get("page"))
    for book in page:
        eligible = [
            copy for copy in book.catalog_copies
            if copy.allows_home_loan and copy.status in {
                BookCopy.Status.AVAILABLE, BookCopy.Status.ON_LOAN, BookCopy.Status.ON_HOLD, BookCopy.Status.RETURN_PENDING,
            } and (not copy.branch_id or copy.branch.is_active)
        ]
        book.pickup_branches = sorted(
            {copy.branch_id: copy.branch for copy in eligible if copy.branch_id}.values(),
            key=lambda branch: branch.name,
        )
        book.pickup_can_request = bool(eligible)
        book.pickup_available = any(copy.status == BookCopy.Status.AVAILABLE for copy in eligible)
    return render(request, "library/catalog.html", {
        "books": page, "page_obj": page, "query": query, "is_reader": is_reader, "member_can_reserve": bool(member and member.card_is_current), "branches": branches, "selected_branch": branch_id,
    })


@never_cache
@staff_mfa_required
def circulation_desk(request):
    if not (request.user.is_superuser or (request.user.has_perm("library.view_loan") and request.user.has_perm("library.view_fine"))):
        return HttpResponseForbidden("Bạn không được cấp quyền xem quầy lưu thông.")
    from .desk_browser import DESK_TABS, browser_context
    action_tabs = {"pickup": "reservations", "checkout": "checkout", "return": "loans", "report_lost": "loans", "renew": "renew", "payment": "fines", "settle_damage": "fines", "close_damage_no_charge": "damage", "update_copy_condition": "damage", "approve_damage": "damage", "reopen": "overdue", "refresh_overdue": "overdue", "prepare_notices": "notices", "expire": "reservations"}
    active_tab = request.GET.get("tab", "checkout")
    if request.method == "POST":
        active_tab = action_tabs.get(request.POST.get("action"), "checkout")
    loan_operations = {"renew", "damage", "overdue", "notices", "fines"}
    loan_operation = request.GET.get("operation", "")
    if active_tab in loan_operations:
        loan_operation = active_tab
        active_tab = "loans"
    if active_tab == "return":
        active_tab = "loans"
    if active_tab not in DESK_TABS:
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
    damage_approval_form = DamageApprovalForm(request.POST) if request.method == "POST" and request.POST.get("action") == "approve_damage" else None
    blocking_damage_case = None
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            forms = {"checkout": checkout_form, "return": return_form, "payment": payment_form, "renew": renewal_form, "reopen": reopen_form}
            permissions = {"pickup": "checkout_loan", "checkout": "checkout_loan", "return": "return_loan", "report_lost": "return_loan", "payment": "collect_finepayment", "settle_damage": "collect_finepayment", "close_damage_no_charge": "approve_damagecase", "update_copy_condition": "approve_damagecase", "approve_damage": "approve_damagecase", "renew": "renew_loan", "expire": "manage_reservation", "reopen": "manage_reader_restrictions", "refresh_overdue": "manage_reader_restrictions", "prepare_notices": "return_loan"}
            if action not in permissions:
                messages.error(request, "Thao tác không hợp lệ.")
            elif not request.user.has_perm(f"library.{permissions[action]}"):
                return HttpResponseForbidden("Bạn không được cấp quyền thực hiện thao tác này.")
            elif action == "prepare_notices":
                reminder_days = SystemConfiguration.objects.filter(pk=1).values_list("reminder_days", flat=True).first()
                count = prepare_loan_notifications(3 if reminder_days is None else reminder_days)
                messages.success(request, f"Đã tạo {count} thông báo mới trong Cổng độc giả. Thao tác này không gửi email.")
                return redirect(reverse("library:circulation_desk") + "?tab=loans&operation=notices#notices")
            elif action == "refresh_overdue":
                count = refresh_overdue_loans(actor=request.user)
                messages.success(request, f"Đã rà soát {count} phiếu quá hạn và cập nhật theo chính sách.")
                return redirect(reverse("library:circulation_desk") + "?tab=loans&operation=overdue#overdue")
            elif action == "report_lost":
                loan_id = request.POST.get("loan_id", "")
                if not loan_id.isascii() or not loan_id.isdecimal() or len(loan_id) > 18:
                    raise CirculationError("Mã phiếu mượn không hợp lệ.")
                try:
                    loan = report_lost_loan(int(loan_id), request.user, request.POST.get("reason", ""))
                except Loan.DoesNotExist as exc:
                    raise CirculationError("Không tìm thấy phiếu mượn.") from exc
                messages.success(request, f"Đã ghi nhận báo mất cho phiếu #{loan.pk}. Xem hồ sơ trong mục Mất / hỏng.")
                return redirect(reverse("library:circulation_desk") + f"?tab=loans&loan_q=%23{loan.pk}")
            elif action == "approve_damage":
                if damage_approval_form.is_valid():
                    try:
                        approve_damage_case(actor=request.user, **damage_approval_form.cleaned_data)
                    except (CirculationError, DamageCase.DoesNotExist) as exc:
                        damage_approval_form.add_error(None, str(exc) if isinstance(exc, CirculationError) else "Không tìm thấy hồ sơ mất/hỏng.")
                    else:
                        messages.success(request, "Đã duyệt mức bồi thường.")
                        case_id = damage_approval_form.cleaned_data["case_id"]
                        return redirect(reverse("library:circulation_desk") + f"?tab=loans&operation=damage&case={case_id}#damage-case-{case_id}")
            elif action == "update_copy_condition":
                case_id = request.POST.get("case_id", "")
                if not case_id.isascii() or not case_id.isdecimal() or len(case_id) > 18:
                    raise CirculationError("Mã hồ sơ mất/hỏng không hợp lệ.")
                try:
                    copy = update_damaged_copy_status(
                        int(case_id), request.user, request.POST.get("copy_status", ""), request.POST.get("reason", ""),
                    )
                except DamageCase.DoesNotExist as exc:
                    raise CirculationError("Không tìm thấy hồ sơ mất/hỏng.") from exc
                messages.success(request, f"Đã cập nhật {copy.barcode}: {copy.get_status_display()}.")
                return redirect(reverse("library:circulation_desk") + "?tab=loans&operation=damage#damage")
            elif action in {"settle_damage", "close_damage_no_charge"}:
                case_id = request.POST.get("case_id", "")
                if not case_id.isascii() or not case_id.isdecimal() or len(case_id) > 18:
                    raise CirculationError("Mã hồ sơ bồi thường không hợp lệ.")
                try:
                    case = settle_damage_case(int(case_id), request.user, no_charge=action == "close_damage_no_charge", reason=request.POST.get("reason", ""))
                except DamageCase.DoesNotExist as exc:
                    raise CirculationError("Không tìm thấy hồ sơ bồi thường.") from exc
                if not case.compensation_total:
                    messages.success(request, "Đã hoàn tất hồ sơ không thu bồi thường.")
                    return redirect(reverse("library:circulation_desk") + "?tab=loans&operation=damage#damage")
                messages.success(request, f"Đã hoàn tất bồi thường. Mã biên nhận: BT-{case.pk}.")
                return redirect(reverse("library:circulation_desk") + "?tab=loans&operation=fines#fines")
            elif action == "pickup":
                reservation_id = request.POST.get("reservation_id", "")
                if not reservation_id.isascii() or not reservation_id.isdecimal() or len(reservation_id) > 18:
                    raise CirculationError("Mã yêu cầu giữ chỗ không hợp lệ.")
                loan = checkout_reservation(int(reservation_id), request.user)
                messages.success(request, f"Đã tạo phiếu mượn #{loan.pk}. Hạn trả: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M:%S}.")
                return redirect(reverse("library:circulation_desk") + "?tab=reservations")
            elif action == "expire":
                count = expire_ready_reservations()
                if request.headers.get("Accept") == "application/json":
                    reservations = Reservation.objects.select_related("reader", "book", "copy__branch", "pickup_branch", "notification").defer('book__cover_image').filter(status__in=["waiting", "ready"]).order_by("created_at", "pk")[:50]
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
                    loan_days = data["loan_days"]
                    exact_duration = None
                    if any(data[field] is not None for field in ("loan_hours", "loan_minutes", "loan_seconds")):
                        exact_duration = timedelta(
                            days=loan_days or 0, hours=data["loan_hours"] or 0,
                            minutes=data["loan_minutes"] or 0, seconds=data["loan_seconds"] or 0,
                        )
                        loan_days = None
                    loan = checkout_copy(
                        data["reader_number"], data["barcode"], request.user, data["idempotency_key"],
                        loan_days=loan_days, exact_duration=exact_duration,
                    )
                    messages.success(request, f"Đã ghi nhận mượn #{loan.pk}. Hạn trả: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M:%S}.")
                elif action == "return":
                    loan = return_copy(data["barcode"], request.user, data["condition_note"], data["idempotency_key"], data["condition_kind"])
                    messages.success(request, "Đã xử lý trả sách; tình trạng và căn cứ đã được ghi nhận.")
                elif action == "renew":
                    loan = renew_loan(
                        data["loan_id"], request.user, data["idempotency_key"], extension=data.get("extension"),
                    )
                    messages.success(request, f"Đã gia hạn #{loan.pk}. Hạn mới: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M:%S}.")
                else:
                    row = record_fine_payment(data["fine_id"], data["amount"], request.user, reason=data["reason"], idempotency_key=data["idempotency_key"])
                    messages.success(request, f"Đã ghi nhận thanh toán. Biên nhận: {row.receipt_number}.")
                target = "?tab=" + active_tab
                if loan_operation in loan_operations:
                    target += f"&operation={loan_operation}#{loan_operation}"
                return redirect(reverse("library:circulation_desk") + target)
        except (CirculationError, ObjectDoesNotExist) as exc:
            if isinstance(exc, DamageRestrictionError):
                blocking_damage_case = exc.case_id
            if action in forms:
                forms[action].add_error(None, str(exc) if isinstance(exc, CirculationError) else "Không tìm thấy độc giả, bản sách hoặc lượt giao dịch.")
            else:
                messages.error(request, str(exc))
    return_requests = LoanEvent.objects.filter(loan_id=OuterRef("pk"), event_type="return_requested")
    return_events = LoanEvent.objects.filter(loan_id=OuterRef("pk"), event_type="return").order_by("-pk")
    damage_reports = DamageCase.objects.filter(loan_id=OuterRef("pk")).order_by("-pk")
    compensation_reports = damage_reports.filter(
        status__in=[DamageCase.Status.APPROVED, DamageCase.Status.SETTLED],
        replacement_amount__isnull=False,
    ).annotate(total=F("replacement_amount") + F("processing_fee"))
    all_loans = Loan.objects.annotate(
        return_requested=Exists(return_requests),
        has_due_fine=Exists(Fine.objects.filter(loan_id=OuterRef("pk"), status=Fine.Status.DUE)),
        returned_condition=Subquery(return_events.values("details__condition")[:1]),
        reported_condition=Subquery(damage_reports.values("kind")[:1]),
        damage_case_id=Subquery(damage_reports.values("pk")[:1]),
        condition_description=Subquery(damage_reports.values("description")[:1]),
        compensation_amount=Subquery(compensation_reports.values("total")[:1]),
        compensation_status=Subquery(compensation_reports.values("status")[:1]),
    ).select_related("reader__user", "copy__book").defer("copy__book__cover_image", "reader__user__password").order_by("due_at", "pk")
    open_loans = all_loans.filter(status=Loan.Status.OPEN)
    now = timezone.now()
    end_date = timezone.localdate(now) + timedelta(days=4)
    end = timezone.make_aware(datetime.combine(end_date, time.min))
    loan_filters = {
        "all": ("Tất cả trạng thái", Q()),
        "open": ("Đang mượn", Q(status=Loan.Status.OPEN)),
        "returned": ("Đã trả", Q(status=Loan.Status.RETURNED)),
        "lost": ("Đã báo mất", Q(status=Loan.Status.LOST)),
        "due_soon": ("Sắp đến hạn", Q(due_at__gte=now, due_at__lt=end)),
        "overdue": ("Quá hạn", Q(due_at__lt=now)),
        "in_time": ("Còn hơn 3 ngày", Q(due_at__gte=end)),
        "return_requested": ("Đã yêu cầu trả", Q(return_requested=True)),
    }
    default_loan_status = {"overdue": "overdue", "notices": "due_soon"}.get(loan_operation, "all")
    loan_status = request.GET.get("loan_status", default_loan_status)
    if loan_status not in loan_filters:
        loan_status = "all"
    loan_query = request.GET.get("loan_q", request.GET.get("barcode", "") if active_tab == "loans" else "").strip()[:100]
    if loan_status in {"due_soon", "overdue", "in_time", "return_requested"}:
        loans = open_loans
    else:
        loans = all_loans.order_by("-pk")
    loans = loans.filter(loan_filters[loan_status][1])
    if loan_query:
        matches = (
            Q(copy__book__title__icontains=loan_query)
            | Q(copy__barcode__icontains=loan_query)
            | Q(reader__reader_number__icontains=loan_query)
            | Q(reader__user__username__icontains=loan_query)
            | Q(reader__user__first_name__icontains=loan_query)
            | Q(reader__user__last_name__icontains=loan_query)
        )
        loan_number = loan_query.removeprefix("#").strip()
        if loan_number.isascii() and loan_number.isdecimal() and len(loan_number) <= 18:
            by_number = Q(pk=int(loan_number))
            matches = by_number if loan_query.startswith("#") else matches | by_number
        loans = loans.filter(matches)


    selected_fine_loan = (
        int(loan_query[1:]) if loan_operation == "fines" and loan_query.startswith("#")
        and loan_query[1:].isascii() and loan_query[1:].isdecimal() and len(loan_query) <= 19 else None
    )
    overdue_fines = Fine.objects.select_related("loan__reader", "loan__copy__book").defer('loan__copy__book__cover_image').prefetch_related("transactions").order_by("calculated_at")
    damage_receivables = DamageCase.objects.filter(
        status__in=[DamageCase.Status.APPROVED, DamageCase.Status.SETTLED],
        replacement_amount__isnull=False,
    ).select_related("loan__copy__book", "loan__reader").defer("loan__copy__book__cover_image").order_by("-pk")
    if selected_fine_loan is not None:
        overdue_fines = overdue_fines.filter(loan_id=selected_fine_loan)
        damage_receivables = damage_receivables.filter(loan_id=selected_fine_loan)
    reservations = Reservation.objects.select_related("reader", "book", "copy__branch", "pickup_branch", "notification").defer('book__cover_image').filter(status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).order_by("created_at", "pk")[:50]
    damage_case_query = request.GET.get("case", "")
    selected_damage_case = int(damage_case_query) if damage_case_query.isascii() and damage_case_query.isdecimal() and len(damage_case_query) <= 18 else None
    damage_cases = DamageCase.objects.select_related("loan__copy__book", "loan__reader", "approved_by").defer(
        "loan__copy__book__cover_image"
    ).annotate(latest_case_id=Subquery(
        DamageCase.objects.filter(loan__copy_id=OuterRef("loan__copy_id")).order_by("-pk").values("pk")[:1]
    )).order_by("-reported_at")
    if selected_damage_case is not None:
        damage_cases = damage_cases.filter(pk=selected_damage_case)

    browse = {}
    if active_tab == "checkout":
        try:
            browse = browser_context(request)
        except PermissionError:
            return HttpResponseForbidden()
    return render(request, "library/circulation_desk.html", {**browse,"checkout_form": checkout_form, "return_form": return_form, "payment_form": payment_form, "renewal_form": renewal_form, "reopen_form": reopen_form, "loans": Paginator(loans, 25).get_page(request.GET.get("loan_page")) if active_tab == "loans" else None, "loan_query": loan_query, "loan_status": loan_status,
        "loan_filter_options": [(key, label) for key, (label, _) in loan_filters.items()], "active_tab": active_tab, "loan_operation": loan_operation, "blocking_damage_case": blocking_damage_case, "damage_approval_form": damage_approval_form,
        "damage_cases": damage_cases[:50] if request.user.has_perm("library.view_damagecase") else [],
        "selected_damage_case": selected_damage_case,
        "loan_notices": LoanNotification.objects.select_related("loan__copy__book", "loan__reader").defer('loan__copy__book__cover_image').order_by("-created_at")[:50] if request.user.has_perm("library.view_loannotification") else [],
        "damage_receivables": damage_receivables
        if request.user.has_perm("library.collect_finepayment") or request.user.has_perm("library.view_damagecase") else [],
        "unpaid_fines": overdue_fines.filter(status=Fine.Status.DUE)[:50],
        "accruing_fines": overdue_fines.filter(status=Fine.Status.ACCRUING)[:50], "reservations": reservations, "loan_now": now, "loan_reminder_end": end})


@never_cache
@require_POST
def reserve(request, book_id):
    from apps.core.memberships import guest_profile

    if request.user.is_authenticated:
        if not request.user.groups.filter(name="reader").exists():
            return redirect("home")
        profile = getattr(request.user, "reader_profile", None)
    else:
        profile = guest_profile(request)
    if not profile:
        messages.error(request, "Hãy tạo hồ sơ và kích hoạt gói thẻ trước khi gửi yêu cầu.")
        return redirect("membership_plans") if not request.user.is_authenticated else redirect("library:catalog")
    if not profile.card_is_current:
        messages.error(request, "Bạn cần có thẻ còn hiệu lực trước khi gửi yêu cầu mượn hoặc đặt trước.")
        return redirect("membership_plans")
    form = ReservationRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect("library:catalog")
    try:
        reservation = place_reservation(profile, book_id, profile.user, allow_available=True, **form.cleaned_data)
        if reservation.status == Reservation.Status.READY:
            messages.success(request, "Sách đã được giữ. Xem hạn nhận và đến quầy để nhận.")
        elif reservation.status == Reservation.Status.WAITING:
            messages.success(request, "Đã thêm bạn vào hàng chờ của đầu sách.")
        else:
            messages.error(request, reservation.close_reason)
    except (CirculationError, ObjectDoesNotExist) as exc:
        messages.error(request, str(exc) or "Không thể tạo yêu cầu đặt trước.")
    return redirect("library:catalog" if request.user.is_authenticated else "membership_plans")


@never_cache
@login_required
@user_passes_test(has_role("reader"), login_url="home")
@require_POST
def request_return_view(request, loan_id):
    try:
        request_return(loan_id, request.user)
        messages.success(request, "Đã gửi yêu cầu. Hãy mang sách tới quầy để thủ thư xác nhận.")
    except Loan.DoesNotExist as exc:
        raise Http404 from exc
    except CirculationError as exc:
        messages.error(request, str(exc))
    return redirect("reader_loan_detail", loan_id=loan_id)


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
