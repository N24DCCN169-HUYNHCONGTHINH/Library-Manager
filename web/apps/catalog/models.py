from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Book(models.Model):
    code = models.CharField("Mã sách", max_length=30, unique=True)
    title = models.CharField("Tên sách", max_length=250)
    author = models.CharField("Tác giả", max_length=250)
    category = models.CharField("Thể loại", max_length=100, blank=True)
    publisher = models.CharField("Nhà xuất bản", max_length=150, blank=True)
    publication_year = models.PositiveSmallIntegerField(
        "Năm xuất bản", null=True, blank=True
    )
    edition = models.CharField("Ấn bản", max_length=50, blank=True, default="1")
    total_copies = models.PositiveIntegerField("Tổng số bản", default=1)
    available_copies = models.PositiveIntegerField("Số bản còn", default=1)
    cover_path = models.CharField("Đường dẫn ảnh bìa", max_length=500, blank=True)
    description = models.TextField("Mô tả", blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        ordering = ["title", "code"]
        verbose_name = "sách"
        verbose_name_plural = "sách"
        constraints = [
            models.CheckConstraint(
                condition=Q(available_copies__lte=F("total_copies")),
                name="catalog_available_not_over_total",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.total_copies is not None
            and self.available_copies is not None
            and self.available_copies > self.total_copies
        ):
            raise ValidationError(
                {"available_copies": "Số bản còn không được lớn hơn tổng số bản."}
            )

    def __str__(self):
        return f"{self.code} — {self.title}"
