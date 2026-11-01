from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import (
    Book, BookCopy, CirculationPolicy, DamageCase, Fine, FinePayment,
    LibraryClosure, LibraryHours, Loan, LoanEvent, LoanRenewal,
    LibraryBranch, ReaderRestriction, Reservation,
)


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 0
    fields = ("barcode", "branch", "shelf_location", "status", "home_loan_override", "condition_note", "is_active")
    readonly_fields = ("status",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("catalog_number", "title", "authors", "material_type", "loan_mode", "available_copies", "is_active")
    list_filter = ("material_type", "loan_mode", "is_active")
    search_fields = ("catalog_number", "isbn", "title", "authors", "publisher")
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")
    actions = ("deactivate_books",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Ngừng hiển thị các đầu sách đã chọn")
    def deactivate_books(self, request, queryset):
        for book in queryset:
            book.is_active = False
            book.updated_by = request.user
            book.save(update_fields=("is_active", "updated_by", "updated_at"))


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ("barcode", "book", "branch", "shelf_location", "status", "allows_home_loan", "is_active")
    list_filter = ("branch", "status", "is_active", "book__material_type")
    search_fields = ("barcode", "book__title", "book__catalog_number", "book__isbn")
    readonly_fields = ("status", "created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LibraryBranch)
class LibraryBranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "address", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "address")


@admin.register(CirculationPolicy)
class CirculationPolicyAdmin(admin.ModelAdmin):
    list_display = ("reader_type", "material_type", "version", "effective_from", "effective_until", "allow_home_loan", "max_active_loans", "loan_days", "overdue_rate_per_day", "overdue_fine_cap")
    list_filter = ("reader_type", "material_type", "allow_home_loan")
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("id", "reader", "copy", "status", "loaned_at", "due_at", "returned_at")
    list_filter = ("status", "reader_type_snapshot", "material_type_snapshot")
    search_fields = ("reader__reader_number", "copy__barcode", "copy__book__title")
    readonly_fields = tuple(field.name for field in Loan._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "reader", "book", "status", "created_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("reader__reader_number", "book__title", "book__catalog_number")
    readonly_fields = tuple(field.name for field in Reservation._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ("loan", "accrued_amount", "status", "calculated_at")
    readonly_fields = tuple(field.name for field in Fine._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)


@admin.register(FinePayment)
class FinePaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "fine", "kind", "amount", "created_by", "created_at")
    readonly_fields = tuple(field.name for field in FinePayment._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LibraryHours)
class LibraryHoursAdmin(admin.ModelAdmin):
    list_display = ("weekday", "is_open", "opens_at", "closes_at")


@admin.register(LibraryClosure)
class LibraryClosureAdmin(admin.ModelAdmin):
    list_display = ("date", "reason", "is_full_day")
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReaderRestriction)
class ReaderRestrictionAdmin(admin.ModelAdmin):
    list_display = ("reader", "kind", "reason", "created_at", "resolved_at")
    list_filter = ("kind", "resolved_at")
    search_fields = ("reader__reader_number", "reason")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        elif obj.resolved_at and not obj.resolved_by_id:
            obj.resolved_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DamageCase)
class DamageCaseAdmin(admin.ModelAdmin):
    list_display = ("loan", "kind", "status", "reported_at", "replacement_amount")
    list_filter = ("kind", "status")
    search_fields = ("loan__reader__reader_number", "loan__copy__barcode", "description")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status in {DamageCase.Status.APPROVED, DamageCase.Status.SETTLED}:
            return tuple(field.name for field in self.model._meta.fields)
        return ("reported_at", "created_by", "approved_by", "approved_at", "settled_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        elif obj.status == DamageCase.Status.APPROVED and not obj.approved_at:
            if not request.user.has_perm("library.approve_damagecase"):
                raise PermissionDenied("Chỉ quản lý được duyệt hồ sơ mất/hỏng.")
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)


class AuditRecordAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET" and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(LoanRenewal, AuditRecordAdmin)
admin.site.register(LoanEvent, AuditRecordAdmin)
