from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "author",
        "category",
        "total_copies",
        "available_copies",
        "updated_at",
    )
    list_filter = ("category", "publication_year", "publisher")
    search_fields = ("code", "title", "author", "category", "publisher")
    ordering = ("title", "code")
    list_per_page = 25
    fieldsets = (
        ("Thông tin sách", {"fields": ("code", "title", "author", "category", "publisher", "publication_year", "edition")}),
        ("Kho sách", {"fields": ("total_copies", "available_copies")}),
        ("Thông tin bổ sung", {"fields": ("cover_path", "description")}),
        ("Theo dõi", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")
