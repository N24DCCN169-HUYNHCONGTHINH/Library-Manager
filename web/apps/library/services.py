from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import ReaderProfile
from .models import (
    Book, BookCopy, CirculationPolicy, DamageCase, Fine, FinePayment, Loan, LoanEvent,
    LoanRenewal, LibraryClosure, LibraryHours, ReaderRestriction, Reservation,
)


class CirculationError(Exception):
    """A circulation rule prevents this transaction."""


def _require_permission(actor, permission):
    if not actor or not actor.is_authenticated or not (actor.is_superuser or actor.has_perm(f"library.{permission}")):
        raise CirculationError("Tài khoản không được cấp quyền thực hiện nghiệp vụ này.")


def _next_service_day(day):
    schedule = {item.weekday: item.is_open for item in LibraryHours.objects.all()}
    closures = set(LibraryClosure.objects.filter(is_full_day=True, date__gte=day).values_list("date", flat=True))
    for _ in range(370):
        if day not in closures and (day.weekday() not in schedule or schedule[day.weekday()]):
            return day
        day += timedelta(days=1)
    raise CirculationError("Lịch phục vụ không có ngày mở cửa trong 12 tháng tới.")


def _due_at(started_at, days):
    due_day = _next_service_day(timezone.localtime(started_at).date() + timedelta(days=days))
    return timezone.make_aware(datetime.combine(due_day, time(23, 59)), timezone.get_current_timezone())


def _hold_expiry(started_at):
    expiry = started_at + timedelta(hours=48)
    local_expiry = timezone.localtime(expiry)
    closure = LibraryClosure.objects.filter(date=local_expiry.date(), is_full_day=True).exists()
    hours = LibraryHours.objects.filter(weekday=local_expiry.weekday()).first()
    outside_hours = hours and (not hours.is_open or local_expiry.time().replace(tzinfo=None) < hours.opens_at or local_expiry.time().replace(tzinfo=None) >= hours.closes_at)
    if closure or outside_hours:
        next_day = _next_service_day(local_expiry.date() + timedelta(days=1))
        next_hours = LibraryHours.objects.filter(weekday=next_day.weekday(), is_open=True).first()
        if next_hours:
            expiry = timezone.make_aware(datetime.combine(next_day, next_hours.closes_at), timezone.get_current_timezone())
        else:
            expiry = timezone.make_aware(datetime.combine(next_day, time(23, 59)), timezone.get_current_timezone())
    return expiry


def _policy(reader, copy, today):
    policy = CirculationPolicy.objects.filter(
        reader_type=reader.reader_type,
        material_type=copy.book.material_type,
        effective_from__lte=today,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gte=today)).order_by("-effective_from", "-version").first()
    if not policy:
        raise CirculationError("Chưa cấu hình chính sách mượn cho loại bạn đọc và tài liệu này.")
    return policy


def _assert_eligible(reader, policy=None):
    today = timezone.localdate()
    if not reader.user.is_active or not reader.card_is_current:
        raise CirculationError("Tài khoản hoặc thẻ bạn đọc chưa hoạt động, chưa xác minh hoặc đã hết hạn.")
    if reader.restrictions.filter(resolved_at__isnull=True).exists():
        raise CirculationError("Hồ sơ đang bị hạn chế giao dịch; vui lòng liên hệ thư viện.")
    open_loans = Loan.objects.filter(reader=reader, status=Loan.Status.OPEN).select_related("fine")
    for loan in open_loans:
        if loan.due_at < timezone.now():
            raise CirculationError("Bạn đang có tài liệu quá hạn; cần trả tài liệu trước khi mượn tiếp.")
        try:
            if loan.fine.balance > 0:
                raise CirculationError("Bạn còn khoản phạt chưa thanh toán.")
        except Fine.DoesNotExist:
            pass
    if policy and open_loans.count() >= policy.max_active_loans:
        raise CirculationError(f"Đã đạt hạn mức {policy.max_active_loans} tài liệu đang mượn.")


def _event(loan, event_type, actor, reason="", details=None):
    LoanEvent.objects.create(loan=loan, event_type=event_type, actor=actor, reason=reason, details=details or {})


@transaction.atomic
def checkout_copy(reader_number, barcode, actor, idempotency_key=None):
    _require_permission(actor, "checkout_loan")
    reader = ReaderProfile.objects.select_for_update().select_related("user").get(reader_number=reader_number)
    copy = BookCopy.objects.select_for_update().select_related("book").get(barcode=barcode)
    Book.objects.select_for_update().get(pk=copy.book_id)
    if idempotency_key:
        existing = Loan.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
    if not copy.is_active or not copy.book.is_active or copy.status not in {BookCopy.Status.AVAILABLE, BookCopy.Status.ON_HOLD}:
        raise CirculationError("Bản sách không sẵn sàng để cho mượn.")
    if not copy.allows_home_loan:
        raise CirculationError("Tài liệu này chỉ được đọc tại chỗ.")
    today = timezone.localdate()
    policy = _policy(reader, copy, today)
    if not policy.allow_home_loan:
        raise CirculationError("Chính sách hiện tại không cho mượn loại tài liệu này.")
    _assert_eligible(reader, policy)
    active_queue = Reservation.objects.filter(book=copy.book, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).order_by("created_at", "pk")
    assigned = active_queue.filter(reader=reader, status=Reservation.Status.READY, copy=copy).first()
    if copy.status == BookCopy.Status.ON_HOLD and not assigned:
        raise CirculationError("Bản sách đang được giữ cho bạn đọc trong hàng chờ.")
    if active_queue.exists():
        if not assigned:
            raise CirculationError("Sách đang có hàng chờ; chỉ bạn đọc được chỉ định nhận bản này mới được mượn.")
        assigned.status = Reservation.Status.FULFILLED
        assigned.closed_at = timezone.now()
        assigned.save(update_fields=["status", "closed_at"])
    now = timezone.now()
    loan = Loan.objects.create(
        reader=reader, copy=copy, policy=policy, reader_type_snapshot=reader.reader_type,
        material_type_snapshot=copy.book.material_type, policy_version_snapshot=policy.version,
        max_loans_snapshot=policy.max_active_loans, overdue_rate_snapshot=policy.overdue_rate_per_day,
        overdue_cap_snapshot=policy.overdue_fine_cap, loaned_at=now, due_at=_due_at(now, policy.loan_days),
        idempotency_key=idempotency_key, created_by=actor,
    )
    copy.status = BookCopy.Status.ON_LOAN
    copy.save(update_fields=["status"])
    _event(loan, "checkout", actor, details={"policy_version": policy.version})
    return loan


def _accrue_fine(loan, returned_at):
    start = timezone.localtime(loan.due_at).date() + timedelta(days=1)
    end = timezone.localtime(returned_at).date()
    closures = set(LibraryClosure.objects.filter(is_full_day=True, date__gte=start, date__lte=end).values_list("date", flat=True))
    days = sum(1 for offset in range(max(0, (end - start).days + 1)) if start + timedelta(days=offset) not in closures)
    cap = loan.overdue_cap_snapshot
    if loan.copy.book.replacement_price is not None:
        cap = min(cap, loan.copy.book.replacement_price)
    amount = min(Decimal(days) * loan.overdue_rate_snapshot, cap)
    if amount <= 0:
        return None
    fine, _ = Fine.objects.get_or_create(loan=loan, defaults={
        "rate_per_day": loan.overdue_rate_snapshot, "cap_amount": cap,
    })
    fine.accrued_days = days
    fine.accrued_amount = amount
    fine.calculated_at = returned_at
    fine.save(update_fields=["accrued_days", "accrued_amount", "calculated_at"])
    fine.status = Fine.Status.PAID if fine.balance == 0 else (Fine.Status.DUE if loan.status == Loan.Status.RETURNED else Fine.Status.ACCRUING)
    fine.save(update_fields=["status"])
    return fine


def refresh_overdue_loans(reader=None):
    now = timezone.now()
    loans = Loan.objects.filter(status=Loan.Status.OPEN, due_at__lt=now).select_related("reader__user", "copy__book")
    if reader is not None:
        loans = loans.filter(reader=reader)
    refreshed = 0
    for loan_id in loans.values_list("id", flat=True).iterator():
        with transaction.atomic():
            loan = Loan.objects.select_for_update().select_related("reader__user", "copy__book").get(pk=loan_id)
            if loan.status != Loan.Status.OPEN or loan.due_at >= now:
                continue
            _accrue_fine(loan, now)
            overdue_day = timezone.localtime(loan.due_at).date() + timedelta(days=7)
            profile = ReaderProfile.objects.select_for_update().get(pk=loan.reader_id)
            if timezone.localdate() >= overdue_day and profile.status == ReaderProfile.Status.ACTIVE:
                profile.status = ReaderProfile.Status.SUSPENDED
                profile.save(update_fields=["status", "updated_at"])
            refreshed += 1
    return refreshed


@transaction.atomic
def record_fine_payment(fine_id, amount, actor, kind=FinePayment.Kind.PAYMENT, approved_by=None, reason=""):
    _require_permission(actor, "collect_finepayment")
    fine = Fine.objects.select_for_update().get(pk=fine_id)
    amount = Decimal(amount)
    if kind not in {FinePayment.Kind.PAYMENT, FinePayment.Kind.WAIVER}:
        raise CirculationError("Loại điều chỉnh này cần luồng phê duyệt riêng.")
    if amount <= 0 or amount > fine.balance:
        raise CirculationError("Số tiền phải lớn hơn 0 và không vượt số dư còn phải trả.")
    if kind == FinePayment.Kind.WAIVER and not approved_by:
        raise CirculationError("Miễn/giảm khoản phạt cần người quản lý phê duyệt.")
    if kind == FinePayment.Kind.WAIVER:
        _require_permission(approved_by, "approve_finepayment")
        if approved_by.pk == actor.pk:
            raise CirculationError("Người thu tiền không được tự phê duyệt miễn/giảm khoản phạt.")
    transaction_row = FinePayment.objects.create(
        fine=fine, kind=kind, amount=amount, receipt_number=f"PT-{uuid4().hex[:12].upper()}",
        reason=reason[:500], created_by=actor, approved_by=approved_by,
    )
    if fine.balance == 0:
        fine.status = Fine.Status.WAIVED if kind == FinePayment.Kind.WAIVER else Fine.Status.PAID
    else:
        fine.status = Fine.Status.DUE
    fine.save(update_fields=["status"])
    return transaction_row


@transaction.atomic
def resolve_reader_restriction(restriction_id, actor, resolution):
    _require_permission(actor, "manage_reader_restrictions")
    restriction = ReaderRestriction.objects.select_for_update().get(pk=restriction_id, resolved_at__isnull=True)
    restriction.resolved_by = actor
    restriction.resolved_at = timezone.now()
    restriction.resolution = resolution[:500]
    restriction.save(update_fields=["resolved_by", "resolved_at", "resolution"])
    return restriction


@transaction.atomic
def approve_damage_case(case_id, actor, replacement_amount, processing_fee, reason):
    _require_permission(actor, "approve_damagecase")
    case = DamageCase.objects.select_for_update().get(pk=case_id)
    if case.status not in {DamageCase.Status.OPEN, DamageCase.Status.CONTESTED}:
        raise CirculationError("Chỉ hồ sơ đang xác minh/khiếu nại mới được phê duyệt.")
    replacement_amount = Decimal(replacement_amount)
    processing_fee = Decimal(processing_fee)
    if replacement_amount < 0 or processing_fee < 0 or not reason.strip():
        raise CirculationError("Cần số tiền không âm và lý do quyết định.")
    case.replacement_amount = replacement_amount
    case.processing_fee = processing_fee
    case.decision_reason = reason[:2000]
    case.approved_by = actor
    case.approved_at = timezone.now()
    case.status = DamageCase.Status.APPROVED
    case.save(update_fields=["replacement_amount", "processing_fee", "decision_reason", "approved_by", "approved_at", "status"])
    _event(case.loan, "damage_approved", actor, reason=reason[:500], details={
        "replacement_amount": str(replacement_amount), "processing_fee": str(processing_fee),
    })
    return case


@transaction.atomic
def return_copy(barcode, actor, condition_note=""):
    _require_permission(actor, "return_loan")
    copy = BookCopy.objects.select_for_update().get(barcode=barcode)
    Book.objects.select_for_update().get(pk=copy.book_id)
    loan = Loan.objects.select_for_update().filter(copy=copy, status=Loan.Status.OPEN).first()
    if not loan:
        if copy.status == BookCopy.Status.AVAILABLE:
            return None
        raise CirculationError("Không tìm thấy lượt mượn đang mở cho bản sách này.")
    now = timezone.now()
    loan.status = Loan.Status.RETURNED
    loan.returned_at = now
    loan.returned_by = actor
    loan.save(update_fields=["status", "returned_at", "returned_by"])
    _accrue_fine(loan, now)
    if condition_note:
        copy.status = BookCopy.Status.RETURN_REVIEW
        copy.condition_note = condition_note[:500]
        copy.save(update_fields=["status", "condition_note"])
        from .models import DamageCase, ReaderRestriction
        DamageCase.objects.create(loan=loan, kind=DamageCase.Kind.MINOR_DAMAGE, description=condition_note, created_by=actor)
        ReaderRestriction.objects.get_or_create(reader=loan.reader, kind=ReaderRestriction.Kind.DAMAGE_REVIEW, resolved_at__isnull=True,
            defaults={"reason": condition_note[:500], "created_by": actor})
    else:
        copy.status = BookCopy.Status.AVAILABLE
        copy.save(update_fields=["status"])
        allocate_next_reservation(copy, actor)
    _event(loan, "return", actor, reason=condition_note)
    return loan


@transaction.atomic
def renew_loan(loan_id, actor):
    loan = Loan.objects.select_for_update().select_related("reader__user", "copy__book", "policy").get(pk=loan_id)
    now = timezone.now()
    if loan.reader.user_id != getattr(actor, "pk", None):
        _require_permission(actor, "renew_loan")
    if loan.status != Loan.Status.OPEN:
        raise CirculationError("Chỉ có thể gia hạn lượt mượn đang mở.")
    if loan.renewal_count >= loan.policy.max_renewals:
        raise CirculationError("Lượt mượn đã hết số lần gia hạn.")
    if loan.due_at - now > timedelta(hours=48) or loan.due_at < now:
        raise CirculationError("Chỉ được gia hạn trong 48 giờ cuối trước hạn trả.")
    if Reservation.objects.filter(book=loan.copy.book, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).exists():
        raise CirculationError("Sách đã có người đặt trước, không thể gia hạn.")
    _assert_eligible(loan.reader)
    old_due = loan.due_at
    new_due = _due_at(old_due, loan.policy.renewal_days)
    loan.due_at = new_due
    loan.renewal_count += 1
    loan.save(update_fields=["due_at", "renewal_count"])
    LoanRenewal.objects.create(loan=loan, old_due_at=old_due, new_due_at=new_due, renewed_by=actor)
    _event(loan, "renewal", actor, details={"old_due_at": old_due.isoformat(), "new_due_at": new_due.isoformat()})
    return loan


@transaction.atomic
def place_reservation(reader, book_id, actor):
    if reader.user_id != getattr(actor, "pk", None):
        raise CirculationError("Bạn chỉ được đặt trước bằng hồ sơ bạn đọc của chính mình.")
    reader = ReaderProfile.objects.select_for_update().select_related("user").get(pk=reader.pk)
    book = Book.objects.select_for_update().get(pk=book_id, is_active=True)
    if not reader.user.is_active or not reader.card_is_current:
        raise CirculationError("Thẻ bạn đọc chưa hợp lệ để đặt trước.")
    if reader.restrictions.filter(resolved_at__isnull=True).exists():
        raise CirculationError("Hồ sơ đang bị hạn chế giao dịch.")
    loanable_copies = book.copies.filter(is_active=True).filter(Q(home_loan_override=True) | Q(home_loan_override__isnull=True, book__loan_mode=Book.LoanMode.HOME_LOAN))
    if not loanable_copies.exists():
        raise CirculationError("Tài liệu chỉ phục vụ đọc tại chỗ, không nhận đặt trước.")
    queueable_copies = loanable_copies.filter(status__in=[BookCopy.Status.ON_LOAN, BookCopy.Status.ON_HOLD, BookCopy.Status.RETURN_PENDING])
    if not queueable_copies.exists():
        raise CirculationError("Hiện không có bản sách mượn về nào đang lưu thông để đặt trước.")
    sample_copy = loanable_copies.first()
    policy = _policy(reader, sample_copy, timezone.localdate())
    _assert_eligible(reader, policy)
    if loanable_copies.filter(status=BookCopy.Status.AVAILABLE).exists():
        raise CirculationError("Đang có bản sẵn sàng; hãy liên hệ quầy để mượn.")
    if Reservation.objects.filter(reader=reader, book=book, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).exists():
        raise CirculationError("Bạn đã có yêu cầu đặt trước đang hoạt động cho sách này.")
    return Reservation.objects.create(reader=reader, book=book)


@transaction.atomic
def cancel_reservation(reader, reservation_id, actor):
    if reader.user_id != getattr(actor, "pk", None):
        raise CirculationError("Bạn chỉ được hủy yêu cầu đặt trước của chính mình.")
    reservation = Reservation.objects.select_for_update().get(
        pk=reservation_id, reader=reader, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]
    )
    Book.objects.select_for_update().get(pk=reservation.book_id)
    reservation.status = Reservation.Status.CANCELLED
    reservation.closed_at = timezone.now()
    reservation.close_reason = "Bạn đọc đã hủy yêu cầu."
    reservation.save(update_fields=["status", "closed_at", "close_reason"])
    if reservation.copy_id:
        copy = BookCopy.objects.select_for_update().get(pk=reservation.copy_id)
        copy.status = BookCopy.Status.AVAILABLE
        copy.save(update_fields=["status"])
        allocate_next_reservation(copy, reader.user)
    return reservation


def allocate_next_reservation(copy, actor):
    now = timezone.now()
    queue = Reservation.objects.select_for_update().filter(book=copy.book, status=Reservation.Status.WAITING).select_related("reader__user").order_by("created_at", "pk")
    for reservation in queue:
        try:
            policy = _policy(reservation.reader, copy, timezone.localdate())
            _assert_eligible(reservation.reader, policy)
        except CirculationError as exc:
            reservation.status = Reservation.Status.INELIGIBLE
            reservation.closed_at = now
            reservation.close_reason = str(exc)[:500]
            reservation.save(update_fields=["status", "closed_at", "close_reason"])
            continue
        copy.status = BookCopy.Status.ON_HOLD
        copy.save(update_fields=["status"])
        reservation.status = Reservation.Status.READY
        reservation.copy = copy
        reservation.ready_at = now
        reservation.expires_at = _hold_expiry(now)
        reservation.save(update_fields=["status", "copy", "ready_at", "expires_at"])
        return reservation
    return None


@transaction.atomic
def expire_ready_reservations():
    now = timezone.now()
    expired = Reservation.objects.select_for_update().filter(
        status=Reservation.Status.READY, expires_at__lte=now
    ).select_related("copy__book").order_by("expires_at")
    count = 0
    for reservation in expired:
        copy = BookCopy.objects.select_for_update().get(pk=reservation.copy_id)
        Book.objects.select_for_update().get(pk=copy.book_id)
        reservation.status = Reservation.Status.EXPIRED
        reservation.closed_at = now
        reservation.close_reason = "Không nhận sách trong thời hạn giữ chỗ."
        reservation.save(update_fields=["status", "closed_at", "close_reason"])
        copy.status = BookCopy.Status.AVAILABLE
        copy.save(update_fields=["status"])
        allocate_next_reservation(copy, reservation.reader.user)
        count += 1
    return count
