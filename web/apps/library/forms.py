from django import forms
from django.utils import timezone
from uuid import uuid4

from .models import Book


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["catalog_number", "isbn", "title", "subtitle", "authors", "subjects", "publisher",
                  "publication_year", "edition", "material_type", "loan_mode", "replacement_price",
                  "replacement_price_source", "replacement_price_checked_at", "is_active"]
        labels = {"catalog_number": "Mã danh mục", "isbn": "ISBN", "title": "Nhan đề",
                  "subtitle": "Nhan đề phụ", "authors": "Tác giả", "subjects": "Chủ đề",
                  "publisher": "Nhà xuất bản", "publication_year": "Năm xuất bản", "edition": "Ấn bản",
                  "material_type": "Loại tài liệu", "loan_mode": "Hình thức mượn",
                  "replacement_price": "Giá thay thế (VND)", "replacement_price_source": "Nguồn giá",
                  "replacement_price_checked_at": "Ngày kiểm tra giá", "is_active": "Đang sử dụng"}
        widgets = {"replacement_price_checked_at": forms.DateInput(attrs={"type": "date"})}
        error_messages = {
            "catalog_number": {"unique": "Mã danh mục này đã tồn tại.", "invalid": "Mã danh mục chỉ được dùng chữ, số và các dấu . _ / - ."},
            "isbn": {"unique": "ISBN này đã được sử dụng cho đầu sách khác."},
        }

    def clean_isbn(self):
        value = self.cleaned_data.get("isbn")
        if not value:
            return None
        value = value.replace("-", "").replace(" ", "").upper()
        valid = False
        if len(value) == 13 and value.isascii() and value.isdigit() and value.startswith(("978", "979")):
            valid = sum(int(digit) * (1 if i % 2 == 0 else 3) for i, digit in enumerate(value)) % 10 == 0
        elif len(value) == 10 and value[:9].isascii() and value[:9].isdigit() and value[-1] in "0123456789X":
            valid = (sum(int(digit) * (10 - i) for i, digit in enumerate(value[:9])) + (10 if value[-1] == "X" else int(value[-1]))) % 11 == 0
        if not valid:
            raise forms.ValidationError("ISBN phải có 10 hoặc 13 ký tự và đúng số kiểm tra.")
        return value

    def clean_publication_year(self):
        year = self.cleaned_data.get("publication_year")
        if year is not None and not 1 <= year <= timezone.localdate().year + 1:
            raise forms.ValidationError("Năm xuất bản phải từ 1 đến năm kế tiếp.")
        return year

    def clean(self):
        data = super().clean()
        if data.get("material_type") in {Book.MaterialType.RARE, Book.MaterialType.PERIODICAL, Book.MaterialType.THESIS}:
            data["loan_mode"] = Book.LoanMode.IN_LIBRARY_ONLY
        return data


class CheckoutForm(forms.Form):
    idempotency_key = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    reader_number = forms.CharField(label="Mã bạn đọc", max_length=32, widget=forms.TextInput(attrs={"data-lookup": "readers", "placeholder": "Gõ tên hoặc mã bạn đọc…"}))
    barcode = forms.CharField(label="Mã vạch bản sách", max_length=64, widget=forms.TextInput(attrs={"data-lookup": "copies", "placeholder": "Quét mã hoặc gõ tên sách…"}))


class ReturnForm(forms.Form):
    idempotency_key = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    barcode = forms.CharField(label="Mã vạch bản sách", max_length=64, widget=forms.TextInput(attrs={"data-lookup": "copies", "placeholder": "Quét mã hoặc gõ tên sách…"}))
    condition_kind = forms.ChoiceField(label="Tình trạng khi nhận", required=False, choices=[("", "Bình thường / phân loại theo ghi chú"), ("normal_wear", "Hao mòn tự nhiên — không thu phí"), ("minor_damage", "Hư hỏng nhẹ — cần kiểm tra"), ("major_damage", "Hư hỏng nặng — cần kiểm tra")])
    condition_note = forms.CharField(label="Ghi nhận tình trạng bất thường (nếu có)", required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2}))


class RenewalForm(forms.Form):
    idempotency_key = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    loan_id = forms.IntegerField(label="Mã lượt mượn", min_value=1, widget=forms.TextInput(attrs={"data-lookup": "loans", "placeholder": "Tìm bằng tên sách, mã bản hoặc mã bạn đọc…"}))


class FinePaymentForm(forms.Form):
    idempotency_key = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    fine_id = forms.IntegerField(label="Mã khoản phạt", min_value=1, widget=forms.TextInput(attrs={"data-lookup": "fines", "placeholder": "Tìm sách, mã bạn đọc hoặc khoản phạt…"}))
    amount = forms.DecimalField(label="Số tiền nhận (VND)", min_value=1, decimal_places=0, max_digits=10)
    reason = forms.CharField(label="Ghi chú biên nhận", required=False, max_length=500)


class ReopenReaderForm(forms.Form):
    reader_number = forms.CharField(label="Mã bạn đọc cần mở lại", max_length=32, widget=forms.TextInput(attrs={"data-lookup": "readers"}))
    reason = forms.CharField(label="Căn cứ mở lại hồ sơ", max_length=500)


class DamageQuoteForm(forms.Form):
    method = forms.ChoiceField(label="Phương án", choices=[("replacement", "Mua trả đúng tài liệu"), ("domestic_cash", "Tiền mặt — tài liệu trong nước"), ("foreign_cash", "Tiền mặt — ngoại văn / nhập khẩu"), ("repair", "Sửa chữa hỏng nhẹ"), ("appraisal", "Theo quyết định thẩm định")])
    reference_price = forms.DecimalField(label="Giá có căn cứ, đã quy đổi VND", required=False, decimal_places=0, max_digits=12, min_value=1)
    multiplier = forms.DecimalField(label="Hệ số quản lý lựa chọn (trong nước 1–2; ngoại văn 2–3)", required=False, decimal_places=2, max_digits=3)
    repair_cost = forms.DecimalField(label="Chi phí sửa chữa có chứng từ", required=False, decimal_places=0, max_digits=10, min_value=1)
    appraisal_amount = forms.DecimalField(label="Tổng mức được hội đồng phê duyệt", required=False, decimal_places=0, max_digits=12, min_value=0)
    source = forms.CharField(label="Nguồn giá, ngày, tỷ giá (nếu có) và căn cứ lựa chọn mức", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
