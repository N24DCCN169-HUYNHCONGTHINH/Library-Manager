from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import ReaderProfile
from apps.core.views import has_role, staff_mfa_required
from .forms import CheckoutForm, FinePaymentForm, ReturnForm
from .models import Book, BookCopy, Fine, LibraryBranch, Loan, Reservation
from .services import CirculationError, cancel_reservation, checkout_copy, place_reservation, record_fine_payment, renew_loan, return_copy


def catalog(request):
    query = request.GET.get("q", "").strip()
    branch_id = request.GET.get("branch", "").strip()
    branches = LibraryBranch.objects.filter(is_active=True)
    books = Book.objects.filter(is_active=True)
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
        available_copies_count=Count("copies", filter=available_filter),
        has_available_copies_anywhere=Exists(BookCopy.objects.filter(
            book_id=OuterRef("pk"), status=BookCopy.Status.AVAILABLE, is_active=True,
        )),
    ).prefetch_related(
        Prefetch("copies", queryset=copies, to_attr="catalog_copies")
    ).distinct()
    is_reader = request.user.is_authenticated and request.user.groups.filter(name="reader").exists()
    return render(request, "library/catalog.html", {
        "books": books, "query": query, "is_reader": is_reader, "branches": branches, "selected_branch": branch_id,
    })


@staff_mfa_required
def circulation_desk(request):
    if not (request.user.is_superuser or (request.user.has_perm("library.view_loan") and request.user.has_perm("library.view_fine"))):
        return HttpResponseForbidden("Bạn không được cấp quyền xem quầy lưu thông.")
    checkout_form = CheckoutForm(request.POST if request.method == "POST" and request.POST.get("action") == "checkout" else None)
    return_form = ReturnForm(request.POST if request.method == "POST" and request.POST.get("action") == "return" else None)
    payment_form = FinePaymentForm(request.POST if request.method == "POST" and request.POST.get("action") == "payment" else None)
    if request.method == "POST":
        try:
            if request.POST.get("action") == "checkout" and checkout_form.is_valid():
                loan = checkout_copy(checkout_form.cleaned_data["reader_number"], checkout_form.cleaned_data["barcode"], request.user)
                messages.success(request, f"Đã ghi nhận mượn. Hạn trả: {loan.due_at:%d/%m/%Y %H:%M}.")
            elif request.POST.get("action") == "return" and return_form.is_valid():
                loan = return_copy(return_form.cleaned_data["barcode"], request.user, return_form.cleaned_data["condition_note"])
                if loan:
                    messages.success(request, "Đã ghi nhận trả sách." + (" Bản sách đang chờ kiểm tra tình trạng." if return_form.cleaned_data["condition_note"] else ""))
                else:
                    messages.info(request, "Bản sách đã ở trạng thái sẵn sàng; không tạo giao dịch trả trùng.")
            elif request.POST.get("action") == "payment" and payment_form.is_valid():
                row = record_fine_payment(payment_form.cleaned_data["fine_id"], payment_form.cleaned_data["amount"], request.user, reason=payment_form.cleaned_data["reason"])
                messages.success(request, f"Đã ghi nhận thanh toán. Biên nhận: {row.receipt_number}.")
            return redirect("library:circulation_desk")
        except (CirculationError, ReaderProfile.DoesNotExist, BookCopy.DoesNotExist, Fine.DoesNotExist) as exc:
            messages.error(request, str(exc) or "Không tìm thấy bạn đọc hoặc bản sách.")
    loans = Loan.objects.filter(status=Loan.Status.OPEN).select_related("reader", "copy__book").order_by("due_at")[:50]
    unpaid_fines = Fine.objects.filter(status=Fine.Status.DUE).select_related("loan__reader", "loan__copy__book").order_by("calculated_at")[:50]
    return render(request, "library/circulation_desk.html", {"checkout_form": checkout_form, "return_form": return_form, "payment_form": payment_form, "loans": loans, "unpaid_fines": unpaid_fines})


@login_required
@user_passes_test(has_role("reader"), login_url="home")
def reserve(request, book_id):
    if request.method == "POST":
        try:
            profile = request.user.reader_profile
            place_reservation(profile, book_id, request.user)
            messages.success(request, "Đã thêm bạn vào hàng chờ của đầu sách.")
        except (CirculationError, ObjectDoesNotExist, Book.DoesNotExist) as exc:
            messages.error(request, str(exc) or "Không thể tạo yêu cầu đặt trước.")
    return redirect("library:catalog")


@login_required
@user_passes_test(has_role("reader"), login_url="home")
def renew(request, loan_id):
    if request.method == "POST":
        try:
            profile = request.user.reader_profile
            loan = get_object_or_404(Loan, pk=loan_id, reader=profile)
            loan = renew_loan(loan.pk, request.user)
            messages.success(request, f"Đã gia hạn. Hạn trả mới: {loan.due_at:%d/%m/%Y %H:%M}.")
        except (CirculationError, ObjectDoesNotExist) as exc:
            messages.error(request, str(exc) or "Không thể gia hạn lượt mượn.")
    return redirect("reader_portal")


@login_required
@user_passes_test(has_role("reader"), login_url="home")
def cancel_reservation_view(request, reservation_id):
    if request.method == "POST":
        try:
            profile = request.user.reader_profile
            cancel_reservation(profile, reservation_id, request.user)
            messages.success(request, "Đã hủy yêu cầu đặt trước.")
        except (CirculationError, ObjectDoesNotExist) as exc:
            messages.error(request, str(exc) or "Không thể hủy yêu cầu đặt trước.")
    return redirect("reader_portal")
