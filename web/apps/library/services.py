from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from uuid import uuid4
from time import sleep

from django.db import OperationalError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import ReaderProfile
from .models import (
    Book, BookCopy, CirculationPolicy, DamageCase, Fine, FinePayment, Loan, LoanEvent,
    LoanRenewal, LibraryClosure, LibraryHours, ReaderRestriction, Reservation,
    CirculationMutex, ReservationNotification,
)


class CirculationError(Exception):
    """A circulation rule prevents this transaction."""


def circulation_write(func):
    """Serialize short circulation transactions across workers, including on SQLite.

    Always take this lock before entity locks. A no-op UPDATE acquires a real
    write lock; select_for_update alone provides no protection on SQLite.
    """
    @wraps(func)
    def wrapped(*args, **kwargs):
        for attempt in range(10):
            try:
                with transaction.atomic():
                    if not CirculationMutex.objects.filter(pk=1).update(id=1):
                        CirculationMutex.objects.get_or_create(pk=1)
                        CirculationMutex.objects.filter(pk=1).update(id=1)
                    return func(*args, **kwargs)
            except OperationalError as exc:
                if connection.vendor != "sqlite" or "locked" not in str(exc).lower():
                    raise
                if attempt == 9:
                    raise CirculationError("Đang có giao dịch khác. Vui lòng thử lại sau ít giây.") from exc
                sleep(0.025 * (attempt + 1))
    return wrapped


def _require_permission(actor, permission):
    if not actor or not actor.is_authenticated or not actor.is_active or not (actor.is_superuser or actor.has_perm(f"library.{permission}")):
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
    local_time = local_expiry.time().replace(tzinfo=None)
    outside_hours = hours and (not hours.is_open or not hours.opens_at or not hours.closes_at
                              or local_time < hours.opens_at or local_time >= hours.closes_at)
    if closure or outside_hours:
        # Before opening on an otherwise open day, the next service is today.
        before_opening = (hours and hours.is_open and hours.opens_at and hours.closes_at
                          and local_time < hours.opens_at and not closure)
        next_day = _next_service_day(local_expiry.date() if before_opening else local_expiry.date() + timedelta(days=1))
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
    for fine in Fine.objects.filter(loan__reader=reader):
        if fine.balance > 0:
            raise CirculationError("Bạn còn khoản phạt chưa thanh toán.")
    open_loans = Loan.objects.filter(reader=reader, status=Loan.Status.OPEN)
    for loan in open_loans:
        if loan.due_at < timezone.now():
            raise CirculationError("Bạn đang có tài liệu quá hạn; cần trả tài liệu trước khi mượn tiếp.")
    if policy and open_loans.count() >= policy.max_active_loans:
        raise CirculationError(f"Đã đạt hạn mức {policy.max_active_loans} tài liệu đang mượn.")


def _event(loan, event_type, actor, reason="", details=None):
    LoanEvent.objects.create(loan=loan, event_type=event_type, actor=actor, reason=reason, details=details or {})


def _calendar_snapshot():
    return {
        "captured_at": timezone.now().isoformat(),
        "closures": [str(d) for d in LibraryClosure.objects.filter(is_full_day=True).values_list("date", flat=True)],
        "hours": list(LibraryHours.objects.values("weekday", "is_open")),
    }


def checkout_copy(reader_number, barcode, actor, idempotency_key=None):
    _require_permission(actor, "checkout_loan")
    # Housekeeping commits independently; rejecting a pickup must not resurrect
    # an expired hold or roll back allocation to the next reader.
    expire_ready_reservations()
    return _checkout_copy(reader_number, barcode, actor, idempotency_key)


@circulation_write
def _checkout_copy(reader_number, barcode, actor, idempotency_key=None):
    _require_permission(actor, "checkout_loan")
    reader = ReaderProfile.objects.select_for_update().select_related("user").get(reader_number=reader_number)
    copy = BookCopy.objects.select_for_update().select_related("book").defer('book__cover_image').get(barcode=barcode)
    Book.objects.select_for_update().get(pk=copy.book_id)
    if idempotency_key:
        existing = Loan.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.reader_id != reader.pk or existing.copy_id != copy.pk or existing.created_by_id != actor.pk:
                raise CirculationError("Mã thao tác đã được sử dụng cho một giao dịch khác.")
            return existing
    copy.refresh_from_db()
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
        overdue_cap_snapshot=policy.overdue_fine_cap,
        replacement_price_snapshot=(copy.book.replacement_price if copy.book.replacement_price_approved_at else None),
        calendar_snapshot=_calendar_snapshot(),
        loaned_at=now, due_at=_due_at(now, policy.loan_days),
        max_renewals_snapshot=policy.max_renewals, renewal_days_snapshot=policy.renewal_days,
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
    # Preserve closures announced at checkout, while also honoring later
    # emergency closures. Removing a calendar row must not increase old fines.
    closures.update(date.fromisoformat(day) for day in loan.calendar_snapshot.get("closures", []))
    days = sum(1 for offset in range(max(0, (end - start).days + 1)) if start + timedelta(days=offset) not in closures)
    cap = loan.overdue_cap_snapshot
    if loan.replacement_price_snapshot is not None:
        cap = min(cap, loan.replacement_price_snapshot)
    # An existing fine's cap is immutable even if catalog prices change later.
    existing_fine = Fine.objects.filter(loan=loan).first()
    if existing_fine:
        cap = min(cap, existing_fine.cap_amount)
    amount = min(Decimal(days) * loan.overdue_rate_snapshot, cap)
    if days > 0 and Decimal(days) * loan.overdue_rate_snapshot >= cap and loan.status == Loan.Status.OPEN and not loan.long_overdue_review_at:
        loan.long_overdue_review_at = returned_at
        loan.save(update_fields=["long_overdue_review_at"])
        _event(loan, "long_overdue_review", None, "Đã chạm trần phạt; cần liên hệ độc giả, không tự kết luận mất sách.", {"cap": str(cap), "source": "automatic"})
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


@circulation_write
def refresh_overdue_loans(reader=None):
    now = timezone.now()
    loans = Loan.objects.filter(status=Loan.Status.OPEN, due_at__lt=now).select_related("reader__user", "copy__book").defer('copy__book__cover_image')
    if reader is not None:
        loans = loans.filter(reader=reader)
    refreshed = 0
    for loan_id in loans.values_list("id", flat=True).iterator():
        with transaction.atomic():
            loan = Loan.objects.select_for_update().select_related("reader__user", "copy__book").defer('copy__book__cover_image').get(pk=loan_id)
            if loan.status != Loan.Status.OPEN or loan.due_at >= now:
                continue
            _accrue_fine(loan, now)
            overdue_day = timezone.localtime(loan.due_at).date() + timedelta(days=7)
            profile = ReaderProfile.objects.select_for_update().get(pk=loan.reader_id)
            if timezone.localdate() >= overdue_day and profile.status == ReaderProfile.Status.ACTIVE:
                profile.status = ReaderProfile.Status.SUSPENDED
                profile.save(update_fields=["status", "updated_at"])
                from apps.core.lifecycle import record_security_event
                from apps.core.models import AccountSecurityEvent
                record_security_event(profile.user, AccountSecurityEvent.Kind.ACCOUNT_DISABLED,
                    details={"reason": "Tạm ngưng do quá hạn đủ 7 ngày", "source": "automatic_overdue_review", "loan_id": loan.pk})
            refreshed += 1
    return refreshed


def _money(value, max_digits=10, allow_zero=False):
    try:
        if isinstance(value, bool):
            raise ValueError()
        amount = Decimal(value)
        if not amount.is_finite() or amount != amount.to_integral_value() or amount < 0 or amount >= 10 ** max_digits:
            raise ValueError()
        if not allow_zero and amount == 0:
            raise ValueError()
        return amount
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CirculationError("Số tiền VND phải là số nguyên hợp lệ trong giới hạn cho phép.") from exc


@circulation_write
def record_fine_payment(fine_id, amount, actor, kind=FinePayment.Kind.PAYMENT, approved_by=None, reason="", idempotency_key=None):
    _require_permission(actor, "collect_finepayment")
    fine = Fine.objects.select_for_update().get(pk=fine_id)
    amount = _money(amount)
    if idempotency_key:
        existing = FinePayment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if (existing.fine_id != fine.pk or existing.amount != amount or existing.created_by_id != actor.pk
                or existing.kind != kind or existing.approved_by_id != getattr(approved_by, "pk", None)
                or existing.reason != reason[:500]):
                raise CirculationError("Mã thao tác đã được sử dụng cho một giao dịch khác.")
            return existing
    if kind not in {FinePayment.Kind.PAYMENT, FinePayment.Kind.WAIVER}:
        raise CirculationError("Loại điều chỉnh này cần luồng phê duyệt riêng.")
    if amount <= 0 or amount > fine.balance:
        raise CirculationError("Số tiền phải lớn hơn 0 và không vượt số dư còn phải trả.")
    if kind == FinePayment.Kind.WAIVER and not approved_by:
        raise CirculationError("Miễn/giảm khoản phạt cần người quản lý phê duyệt.")
    if kind == FinePayment.Kind.WAIVER and not reason.strip():
        raise CirculationError("Miễn/giảm khoản phạt cần ghi lý do.")
    if kind == FinePayment.Kind.WAIVER:
        _require_permission(approved_by, "approve_finepayment")
        if approved_by.pk == actor.pk:
            raise CirculationError("Người thu tiền không được tự phê duyệt miễn/giảm khoản phạt.")
    transaction_row = FinePayment.objects.create(
        fine=fine, kind=kind, amount=amount, receipt_number=f"PT-{uuid4().hex[:12].upper()}",
        reason=reason[:500], created_by=actor, approved_by=approved_by,
        idempotency_key=idempotency_key,
    )
    if fine.balance == 0:
        fine.status = Fine.Status.WAIVED if kind == FinePayment.Kind.WAIVER else Fine.Status.PAID
    else:
        fine.status = Fine.Status.DUE
    fine.save(update_fields=["status"])
    return transaction_row


@circulation_write
def resolve_reader_restriction(restriction_id, actor, resolution):
    _require_permission(actor, "manage_reader_restrictions")
    if not resolution.strip():
        raise CirculationError("Cần ghi lý do gỡ hạn chế.")
    restriction = ReaderRestriction.objects.select_for_update().get(pk=restriction_id, resolved_at__isnull=True)
    restriction.resolved_by = actor
    restriction.resolved_at = timezone.now()
    restriction.resolution = resolution[:500]
    restriction.save(update_fields=["resolved_by", "resolved_at", "resolution"])
    return restriction


@circulation_write
def reopen_reader(reader_number, actor, reason):
    _require_permission(actor, "manage_reader_restrictions")
    if not reason.strip():
        raise CirculationError("Cần ghi lý do mở lại hồ sơ.")
    reader = ReaderProfile.objects.select_for_update().select_related("user").get(reader_number=reader_number)
    if reader.status != ReaderProfile.Status.SUSPENDED:
        raise CirculationError("Hồ sơ không ở trạng thái tạm ngưng.")
    if reader.loans.filter(status=Loan.Status.OPEN, due_at__lt=timezone.now()).exists():
        raise CirculationError("Vẫn còn sách quá hạn.")
    if reader.restrictions.filter(resolved_at__isnull=True).exists() or reader.loans.filter(damage_cases__status__in=["open", "contested", "approved"]).exists():
        raise CirculationError("Cần giải quyết hồ sơ hạn chế/mất hỏng trước.")
    if any(fine.balance > 0 for fine in Fine.objects.filter(loan__reader=reader)):
        raise CirculationError("Vẫn còn khoản phải thanh toán.")
    from apps.core.models import AccountSecurityEvent
    from apps.core.lifecycle import record_security_event
    reader.status = ReaderProfile.Status.ACTIVE
    reader.save(update_fields=["status", "updated_at"])
    record_security_event(reader.user, AccountSecurityEvent.Kind.ACCOUNT_REACTIVATED, actor, {"reason": reason[:500], "source": "circulation_review"})
    return reader


@circulation_write
def approve_damage_case(case_id, actor, replacement_amount, processing_fee, reason):
    _require_permission(actor, "approve_damagecase")
    case = DamageCase.objects.select_for_update().get(pk=case_id)
    if case.status not in {DamageCase.Status.OPEN, DamageCase.Status.CONTESTED}:
        raise CirculationError("Chỉ hồ sơ đang xác minh/khiếu nại mới được phê duyệt.")
    replacement_amount = _money(replacement_amount, max_digits=12, allow_zero=True)
    processing_fee = _money(processing_fee, allow_zero=True)
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


@circulation_write
def return_copy(barcode, actor, condition_note="", idempotency_key=None, condition_kind=None):
    _require_permission(actor, "return_loan")
    condition_kind = condition_kind or (DamageCase.Kind.MINOR_DAMAGE if condition_note else DamageCase.Kind.NORMAL_WEAR)
    if condition_kind not in {DamageCase.Kind.NORMAL_WEAR, DamageCase.Kind.MINOR_DAMAGE, DamageCase.Kind.MAJOR_DAMAGE}:
        raise CirculationError("Phân loại tình trạng trả không hợp lệ.")
    if condition_kind != DamageCase.Kind.NORMAL_WEAR and not condition_note.strip():
        raise CirculationError("Cần mô tả tình trạng hư hỏng.")
    copy = BookCopy.objects.select_for_update().get(barcode=barcode)
    Book.objects.select_for_update().get(pk=copy.book_id)
    if idempotency_key:
        existing = Loan.objects.filter(return_idempotency_key=idempotency_key).first()
        if existing:
            if existing.copy_id != copy.pk or existing.returned_by_id != actor.pk:
                raise CirculationError("Mã thao tác đã được sử dụng cho một giao dịch khác.")
            return existing
    loan = Loan.objects.select_for_update().filter(copy=copy, status=Loan.Status.OPEN).first()
    if not loan:
        if copy.status in {BookCopy.Status.AVAILABLE, BookCopy.Status.ON_HOLD, BookCopy.Status.RETURN_REVIEW}:
            return None
        raise CirculationError("Không tìm thấy lượt mượn đang mở cho bản sách này.")
    now = timezone.now()
    loan.status = Loan.Status.RETURNED
    loan.returned_at = now
    loan.returned_by = actor
    loan.return_idempotency_key = idempotency_key
    loan.save(update_fields=["status", "returned_at", "returned_by", "return_idempotency_key"])
    _accrue_fine(loan, now)
    if condition_kind != DamageCase.Kind.NORMAL_WEAR:
        copy.status = BookCopy.Status.RETURN_REVIEW
        copy.condition_note = condition_note[:500]
        copy.save(update_fields=["status", "condition_note"])
        DamageCase.objects.create(loan=loan, kind=condition_kind, description=condition_note, created_by=actor)
        ReaderRestriction.objects.get_or_create(reader=loan.reader, kind=ReaderRestriction.Kind.DAMAGE_REVIEW, resolved_at__isnull=True,
            defaults={"reason": condition_note[:500], "created_by": actor})
    else:
        copy.status = BookCopy.Status.AVAILABLE
        copy.save(update_fields=["status"])
        allocate_next_reservation(copy, actor)
    _event(loan, "return", actor, reason=condition_note, details={"condition": condition_kind})
    return loan


@circulation_write
def renew_loan(loan_id, actor, idempotency_key=None):
    loan = Loan.objects.select_for_update().select_related("reader__user", "copy__book", "policy").defer('copy__book__cover_image').get(pk=loan_id)
    now = timezone.now()
    if loan.reader.user_id != getattr(actor, "pk", None):
        _require_permission(actor, "renew_loan")
    if idempotency_key:
        existing = LoanRenewal.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.loan_id != loan.pk or existing.renewed_by_id != actor.pk:
                raise CirculationError("Mã thao tác đã được sử dụng cho một giao dịch khác.")
            return loan
    if loan.status != Loan.Status.OPEN:
        raise CirculationError("Chỉ có thể gia hạn lượt mượn đang mở.")
    if (loan.copy.status != BookCopy.Status.ON_LOAN or not loan.copy.is_active
        or not loan.copy.book.is_active or not loan.copy.allows_home_loan
        or not _policy(loan.reader, loan.copy, timezone.localdate()).allow_home_loan):
        raise CirculationError("Bản sách hoặc chính sách hiện tại không cho phép gia hạn.")
    if loan.renewal_count >= loan.max_renewals_snapshot:
        raise CirculationError("Lượt mượn đã hết số lần gia hạn.")
    if loan.due_at - now > timedelta(hours=48) or loan.due_at < now:
        raise CirculationError("Chỉ được gia hạn trong 48 giờ cuối trước hạn trả.")
    if Reservation.objects.filter(book=loan.copy.book, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).exists():
        raise CirculationError("Sách đã có người đặt trước, không thể gia hạn.")
    _assert_eligible(loan.reader)
    old_due = loan.due_at
    new_due = _due_at(old_due, loan.renewal_days_snapshot)
    loan.due_at = new_due
    loan.renewal_count += 1
    loan.save(update_fields=["due_at", "renewal_count"])
    LoanRenewal.objects.create(loan=loan, old_due_at=old_due, new_due_at=new_due, renewed_by=actor,
                               idempotency_key=idempotency_key)
    _event(loan, "renewal", actor, details={"old_due_at": old_due.isoformat(), "new_due_at": new_due.isoformat()})
    return loan


@circulation_write
def place_reservation(reader, book_id, actor, *, allow_available=False):
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
    available_copies = loanable_copies.filter(status=BookCopy.Status.AVAILABLE)
    if not queueable_copies.exists() and not (allow_available and available_copies.exists()):
        raise CirculationError("Hiện không có bản sách mượn về nào đang lưu thông để đặt trước.")
    sample_copy = loanable_copies.first()
    policy = _policy(reader, sample_copy, timezone.localdate())
    if not policy.allow_home_loan:
        raise CirculationError("Chính sách hiện tại không cho đặt trước loại tài liệu này.")
    _assert_eligible(reader, policy)
    if not allow_available and available_copies.exists():
        raise CirculationError("Đang có bản sẵn sàng; hãy liên hệ quầy để mượn.")
    if Reservation.objects.filter(reader=reader, book=book, status__in=[Reservation.Status.WAITING, Reservation.Status.READY]).exists():
        raise CirculationError("Bạn đã có yêu cầu đặt trước đang hoạt động cho sách này.")
    reservation = Reservation.objects.create(reader=reader, book=book)
    if allow_available:
        for copy in available_copies.order_by("pk"):
            allocate_next_reservation(copy, actor)
            reservation.refresh_from_db()
            if reservation.status != Reservation.Status.WAITING:
                break
    return reservation


@circulation_write
def request_return(loan_id, actor):
    loan = Loan.objects.select_for_update().get(pk=loan_id, reader__user=actor)
    if loan.status != Loan.Status.OPEN:
        raise CirculationError("Lượt mượn này đã đóng.")
    LoanEvent.objects.get_or_create(loan=loan, event_type="return_requested", defaults={"actor": actor})
    return loan


@circulation_write
def cancel_reservation(reader, reservation_id, actor):
    if reader.user_id != getattr(actor, "pk", None):
        raise CirculationError("Bạn chỉ được hủy yêu cầu đặt trước của chính mình.")
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id, reader=reader)
    if reservation.status == Reservation.Status.CANCELLED:
        return reservation
    if reservation.status not in {Reservation.Status.WAITING, Reservation.Status.READY}:
        raise CirculationError("Yêu cầu đặt trước đã kết thúc, không thể hủy.")
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


@circulation_write
def allocate_next_reservation(copy, actor):
    copy = BookCopy.objects.select_for_update().select_related("book").defer('book__cover_image').get(pk=copy.pk)
    if not copy.is_active or not copy.book.is_active or not copy.allows_home_loan or copy.status != BookCopy.Status.AVAILABLE:
        return None
    now = timezone.now()
    queue = Reservation.objects.select_for_update().filter(book=copy.book, status=Reservation.Status.WAITING).select_related("reader__user").order_by("created_at", "pk")
    for reservation in queue:
        try:
            policy = _policy(reservation.reader, copy, timezone.localdate())
            if not policy.allow_home_loan:
                raise CirculationError("Chính sách hiện tại không cho mượn loại tài liệu này.")
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
        ReservationNotification.objects.get_or_create(reservation=reservation)
        return reservation
    return None


@circulation_write
def expire_ready_reservations():
    now = timezone.now()
    expired = Reservation.objects.select_for_update().filter(
        status=Reservation.Status.READY, expires_at__lte=now
    ).order_by("expires_at", "pk")
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
