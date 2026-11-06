import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import ReaderProfile


class CirculationPolicy(models.Model):
    class ReaderType(models.TextChoices):
        STUDENT = "student", "Sinh viên"
        FACULTY = "faculty", "Giảng viên"
        EMPLOYEE = "employee", "Nhân viên"

    class MaterialType(models.TextChoices):
        GENERAL = "general", "Thông thường"
        REFERENCE = "reference", "Tham khảo"
        TEXTBOOK = "textbook", "Giáo trình"
        RARE = "rare", "Quý/hiếm"
        PERIODICAL = "periodical", "Báo/tạp chí"
        THESIS = "thesis", "Luận văn/luận án"

    reader_type = models.CharField(max_length=16, choices=ReaderType.choices)
    material_type = models.CharField(max_length=16, choices=MaterialType.choices)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(default=timezone.localdate)
    effective_until = models.DateField(null=True, blank=True)
    allow_home_loan = models.BooleanField(default=True)
    max_active_loans = models.PositiveSmallIntegerField(default=5)
    loan_days = models.PositiveSmallIntegerField(default=14)
    max_renewals = models.PositiveSmallIntegerField(default=1)
    renewal_days = models.PositiveSmallIntegerField(default=7)
    overdue_rate_per_day = models.DecimalField(max_digits=8, decimal_places=0, default=1000, validators=[MinValueValidator(0)])
    overdue_fine_cap = models.DecimalField(max_digits=10, decimal_places=0, default=30000, validators=[MinValueValidator(0)])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_circulation_policies")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["reader_type", "material_type", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["reader_type", "material_type", "version"], name="uniq_circulation_policy_version"),
            models.CheckConstraint(condition=Q(effective_until__isnull=True) | Q(effective_until__gte=models.F("effective_from")), name="policy_effective_date_order"),
        ]

    def __str__(self):
        return f"{self.get_reader_type_display()} / {self.get_material_type_display()} · v{self.version}"


class Book(models.Model):
    class MaterialType(models.TextChoices):
        GENERAL = "general", "Thông thường"
        REFERENCE = "reference", "Tham khảo"
        TEXTBOOK = "textbook", "Giáo trình"
        RARE = "rare", "Quý/hiếm"
        PERIODICAL = "periodical", "Báo/tạp chí"
        THESIS = "thesis", "Luận văn/luận án"

    class LoanMode(models.TextChoices):
        HOME_LOAN = "home_loan", "Mượn về"
        IN_LIBRARY_ONLY = "in_library_only", "Chỉ đọc tại chỗ"

    catalog_number = models.CharField(max_length=40, unique=True, validators=[RegexValidator(r"^[A-Za-z0-9._/-]+$")])
    isbn = models.CharField(max_length=20, blank=True, null=True, unique=True)
    cover_image = models.BinaryField(blank=True, default=bytes)
    has_cover = models.BooleanField(default=False)
    title = models.CharField(max_length=300, db_index=True)
    subtitle = models.CharField(max_length=300, blank=True)
    authors = models.CharField(max_length=500, blank=True, db_index=True)
    subjects = models.CharField(max_length=500, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    material_type = models.CharField(max_length=16, choices=MaterialType.choices, default=MaterialType.GENERAL)
    loan_mode = models.CharField(max_length=24, choices=LoanMode.choices, default=LoanMode.HOME_LOAN)
    replacement_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(0)])
    replacement_price_source = models.CharField(max_length=500, blank=True)
    replacement_price_checked_at = models.DateField(null=True, blank=True)
    replacement_price_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_book_prices")
    replacement_price_approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_books")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_books")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "edition"]
        permissions = [("manage_catalog", "Can manage library catalog"), ("view_system_reports", "Can export combined library reports")]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.only("replacement_price", "replacement_price_source", "replacement_price_checked_at").get(pk=self.pk)
            price_fields = ("replacement_price", "replacement_price_source", "replacement_price_checked_at")
            if any(getattr(old, key) != getattr(self, key) for key in price_fields):
                self.replacement_price_approved_by = None
                self.replacement_price_approved_at = None
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"replacement_price_approved_by", "replacement_price_approved_at"}
        if self._state.adding and self.material_type in {self.MaterialType.RARE, self.MaterialType.PERIODICAL, self.MaterialType.THESIS}:
            self.loan_mode = self.LoanMode.IN_LIBRARY_ONLY
        super().save(*args, **kwargs)

    @property
    def available_copies(self):
        return self.copies.filter(status=BookCopy.Status.AVAILABLE, is_active=True).count()

    def __str__(self):
        return f"{self.title} ({self.catalog_number})"


class LibraryBranch(models.Model):
    code = models.CharField(max_length=24, unique=True, validators=[RegexValidator(r"^[A-Za-z0-9._/-]+$")])
    name = models.CharField(max_length=160)
    address = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "cơ sở thư viện"
        verbose_name_plural = "cơ sở thư viện"

    def __str__(self):
        return f"{self.name} ({self.code})"


class BookCopy(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Sẵn sàng"
        ON_LOAN = "on_loan", "Đang mượn"
        ON_HOLD = "on_hold", "Đang giữ chỗ"
        RETURN_PENDING = "return_pending", "Chờ kiểm tra trả"
        RETURN_REVIEW = "return_review", "Đang xem xét tình trạng"
        DAMAGED = "damaged", "Hư hỏng"
        LOST = "lost", "Đã mất"
        INVENTORY_REVIEW = "inventory_review", "Chờ kiểm kê"
        RETIRED = "retired", "Đã thanh lý"

    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="copies")
    branch = models.ForeignKey(LibraryBranch, null=True, blank=True, on_delete=models.PROTECT, related_name="copies")
    barcode = models.CharField(max_length=64, unique=True, validators=[RegexValidator(r"^[A-Za-z0-9._/-]+$")])
    shelf_location = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    home_loan_override = models.BooleanField(null=True, blank=True)
    condition_note = models.CharField(max_length=500, blank=True)
    acquired_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_book_copies")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["barcode"]
        permissions = [("manage_bookcopy", "Can manage physical book copies")]

    @property
    def allows_home_loan(self):
        return self.home_loan_override if self.home_loan_override is not None else self.book.loan_mode == Book.LoanMode.HOME_LOAN

    def __str__(self):
        return f"{self.barcode} — {self.book.title}"


class LibraryHours(models.Model):
    WEEKDAYS = [(0, "Thứ Hai"), (1, "Thứ Ba"), (2, "Thứ Tư"), (3, "Thứ Năm"), (4, "Thứ Sáu"), (5, "Thứ Bảy"), (6, "Chủ Nhật")]
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS, unique=True)
    is_open = models.BooleanField(default=False)
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["weekday"]
        verbose_name = "giờ phục vụ"
        verbose_name_plural = "giờ phục vụ"
        constraints = [
            models.CheckConstraint(condition=Q(is_open=False) | (Q(opens_at__isnull=False) & Q(closes_at__isnull=False) & Q(closes_at__gt=models.F("opens_at"))), name="open_hours_have_valid_interval"),
        ]

    def __str__(self):
        return self.get_weekday_display()


class LibraryClosure(models.Model):
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=300)
    is_full_day = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_library_closures")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date}: {self.reason}"


class ReaderRestriction(models.Model):
    class Kind(models.TextChoices):
        MANUAL = "manual", "Tạm khóa thủ công"
        DAMAGE_REVIEW = "damage_review", "Hồ sơ mất/hỏng đang xử lý"

    reader = models.ForeignKey(ReaderProfile, on_delete=models.PROTECT, related_name="restrictions")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    reason = models.CharField(max_length=500)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_reader_restrictions")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="resolved_reader_restrictions")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("manage_reader_restrictions", "Can manage reader restrictions")]
        constraints = [models.UniqueConstraint(fields=["reader", "kind"], condition=Q(resolved_at__isnull=True), name="uniq_active_reader_restriction_kind")]

    @property
    def is_active(self):
        return self.resolved_at is None


class CirculationMutex(models.Model):
    """One database row serializes circulation writes for the small internal MVP."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)


class Loan(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Đang mượn"
        RETURNED = "returned", "Đã trả"
        LOST = "lost", "Đã báo mất"

    reader = models.ForeignKey(ReaderProfile, on_delete=models.PROTECT, related_name="loans")
    copy = models.ForeignKey(BookCopy, on_delete=models.PROTECT, related_name="loans")
    policy = models.ForeignKey(CirculationPolicy, on_delete=models.PROTECT, related_name="loans")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    reader_type_snapshot = models.CharField(max_length=16, choices=CirculationPolicy.ReaderType.choices)
    material_type_snapshot = models.CharField(max_length=16, choices=CirculationPolicy.MaterialType.choices)
    policy_version_snapshot = models.PositiveIntegerField()
    max_loans_snapshot = models.PositiveSmallIntegerField()
    overdue_rate_snapshot = models.DecimalField(max_digits=8, decimal_places=0)
    overdue_cap_snapshot = models.DecimalField(max_digits=10, decimal_places=0)
    replacement_price_snapshot = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    calendar_snapshot = models.JSONField(default=dict, blank=True)
    long_overdue_review_at = models.DateTimeField(null=True, blank=True)
    loaned_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(db_index=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    renewal_count = models.PositiveSmallIntegerField(default=0)
    max_renewals_snapshot = models.PositiveSmallIntegerField(default=1)
    renewal_days_snapshot = models.PositiveSmallIntegerField(default=7)
    idempotency_key = models.UUIDField(null=True, blank=True, unique=True)
    return_idempotency_key = models.UUIDField(null=True, blank=True, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_loans")
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="closed_loans")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-loaned_at"]
        constraints = [models.UniqueConstraint(fields=["copy"], condition=Q(status="open"), name="uniq_open_loan_per_copy")]
        indexes = [models.Index(fields=["reader", "status", "due_at"])]
        permissions = [
            ("checkout_loan", "Can check out a book copy"),
            ("return_loan", "Can record a book return"),
            ("renew_loan", "Can renew a reader loan on their behalf"),
        ]

    def __str__(self):
        return f"{self.copy.barcode} · {self.reader.reader_number} · {self.get_status_display()}"


class LoanRenewal(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="renewals")
    old_due_at = models.DateTimeField()
    new_due_at = models.DateTimeField()
    renewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="loan_renewals")
    renewed_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=500, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True, unique=True)


class Reservation(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Đang chờ"
        READY = "ready", "Sẵn sàng nhận"
        FULFILLED = "fulfilled", "Đã nhận"
        CANCELLED = "cancelled", "Đã hủy"
        EXPIRED = "expired", "Hết hạn nhận"
        INELIGIBLE = "ineligible", "Không đủ điều kiện"

    reader = models.ForeignKey(ReaderProfile, on_delete=models.PROTECT, related_name="reservations")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="reservations")
    copy = models.ForeignKey(BookCopy, null=True, blank=True, on_delete=models.PROTECT, related_name="reservations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=500, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["reader", "book"], condition=Q(status__in=["waiting", "ready"]), name="uniq_active_reservation_reader_book"),
            models.UniqueConstraint(fields=["copy"], condition=Q(status="ready"), name="uniq_ready_reservation_copy"),
        ]
        indexes = [models.Index(fields=["book", "status", "created_at"])]
        permissions = [("manage_reservation", "Can manage reader reservations")]


class ReservationNotification(models.Model):
    reservation = models.OneToOneField(Reservation, on_delete=models.PROTECT, related_name="notification")
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    attempts = models.PositiveIntegerField(default=0)


class Fine(models.Model):
    class Status(models.TextChoices):
        ACCRUING = "accruing", "Đang phát sinh"
        DUE = "due", "Đến hạn thanh toán"
        PAID = "paid", "Đã thanh toán"
        WAIVED = "waived", "Đã miễn"

    loan = models.OneToOneField(Loan, on_delete=models.PROTECT, related_name="fine")
    rate_per_day = models.DecimalField(max_digits=8, decimal_places=0)
    cap_amount = models.DecimalField(max_digits=10, decimal_places=0)
    accrued_days = models.PositiveIntegerField(default=0)
    accrued_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACCRUING)
    calculated_at = models.DateTimeField(default=timezone.now)

    @property
    def balance(self):
        cached = getattr(self, "_prefetched_objects_cache", {}).get("transactions")
        if cached is not None:
            net = sum((-row.amount if row.kind in {FinePayment.Kind.PAYMENT, FinePayment.Kind.WAIVER} else row.amount) for row in cached)
            return max(0, self.accrued_amount + net)
        totals = self.transactions.aggregate(
            paid=models.Sum("amount", filter=Q(kind=FinePayment.Kind.PAYMENT)),
            waived=models.Sum("amount", filter=Q(kind=FinePayment.Kind.WAIVER)),
            refunded=models.Sum("amount", filter=Q(kind=FinePayment.Kind.REFUND)),
            adjustments=models.Sum("amount", filter=Q(kind=FinePayment.Kind.ADJUSTMENT)))
        paid, waived, refunded, adjustments = (totals[key] or 0 for key in ("paid", "waived", "refunded", "adjustments"))
        return max(0, self.accrued_amount - paid + refunded - waived + adjustments)


class FinePayment(models.Model):
    class Kind(models.TextChoices):
        PAYMENT = "payment", "Thu tiền"
        REFUND = "refund", "Hoàn tiền"
        WAIVER = "waiver", "Miễn/giảm"
        ADJUSTMENT = "adjustment", "Điều chỉnh"

    fine = models.ForeignKey(Fine, on_delete=models.PROTECT, related_name="transactions")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(1)])
    receipt_number = models.CharField(max_length=40, unique=True)
    idempotency_key = models.UUIDField(null=True, blank=True, unique=True)
    reason = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="fine_transactions")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_fine_transactions")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]
        permissions = [
            ("collect_finepayment", "Can collect a fine payment"),
            ("approve_finepayment", "Can approve a fine waiver or adjustment"),
        ]


class DamageCase(models.Model):
    class Kind(models.TextChoices):
        NORMAL_WEAR = "normal_wear", "Hao mòn tự nhiên"
        MINOR_DAMAGE = "minor_damage", "Hư hỏng nhẹ"
        MAJOR_DAMAGE = "major_damage", "Hư hỏng nặng"
        LOST = "lost", "Mất"

    class Status(models.TextChoices):
        OPEN = "open", "Đang xác minh"
        CONTESTED = "contested", "Đang khiếu nại"
        APPROVED = "approved", "Đã duyệt mức bồi thường"
        SETTLED = "settled", "Đã hoàn tất"
        CANCELLED = "cancelled", "Đã hủy"

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="damage_cases")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    description = models.TextField()
    patron_statement = models.TextField(blank=True)
    replacement_amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(0)])
    processing_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    decision_reason = models.TextField(blank=True)
    reported_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_damage_cases")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_damage_cases")
    approved_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-reported_at"]
        permissions = [("approve_damagecase", "Can approve damage and replacement amounts")]


class LoanEvent(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=32)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="loan_events")
    occurred_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["occurred_at", "pk"]


class LoanNotification(models.Model):
    """One notice per loan, due-date version and reminder date; email is retryable."""

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="notifications")
    due_at = models.DateTimeField()
    reminder_date = models.DateField()
    kind = models.CharField(max_length=16, choices=[("upcoming", "Sắp đến hạn"), ("due", "Đến hạn"), ("overdue", "Quá hạn")])
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["loan", "due_at", "reminder_date"], name="uniq_loan_reminder_date")]


class PaymentOrder(models.Model):
    """Test ledger only: never posts to FinePayment or changes a live balance."""
    import uuid
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_orders")
    fine = models.ForeignKey(Fine, on_delete=models.PROTECT, related_name="payment_orders")
    channel = models.CharField(max_length=12, choices=[("bank", "Ngân hàng"), ("momo", "MoMo")])
    mode = models.CharField(max_length=20, choices=[("simulator", "Mô phỏng nội bộ"), ("momo_sandbox", "MoMo Sandbox"), ("vnpay_sandbox", "VNPAY Sandbox")], default="simulator")
    amount = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(1)])
    state = models.CharField(max_length=12, choices=[("pending", "Chờ thanh toán thử"), ("success", "Thành công — giao dịch thử"), ("failed", "Thất bại"), ("cancelled", "Đã hủy"), ("expired", "Hết hạn")], default="pending")
    request_key = models.UUIDField(unique=True)
    provider_transaction = models.CharField(max_length=100, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    result_code = models.CharField(max_length=30, blank=True)
    provider_pay_url = models.URLField(max_length=1500, blank=True)
    class Meta:
        ordering = ["-created_at"]

class FineWaiverRequest(models.Model):
    request_key = models.UUIDField(default=uuid.uuid4, unique=True)
    kind = models.CharField(max_length=12, choices=[("waiver","Miễn/giảm"),("adjustment","Điều chỉnh tăng có căn cứ")], default="waiver")
    fine = models.ForeignKey(Fine, on_delete=models.PROTECT, related_name="waiver_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_waivers")
    amount = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(1)])
    reason = models.CharField(max_length=500)
    state = models.CharField(max_length=12, choices=[("pending", "Chờ duyệt"), ("approved", "Đã duyệt"), ("rejected", "Từ chối")], default="pending")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_waivers")
    review_reason = models.CharField(max_length=500, blank=True)
    payment = models.OneToOneField(FinePayment, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
