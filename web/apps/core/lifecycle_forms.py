from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError

from .models import ReaderProfile


INVITABLE_ROLES = (
    ("reader", "Độc giả"),
    ("cataloger", "Nhân viên biên mục"),
    ("circulation_staff", "Nhân viên lưu thông"),
    ("librarian", "Thủ thư"),
)


class AccountInvitationForm(forms.Form):
    username = forms.CharField(label="Tên đăng nhập", max_length=150)
    email = forms.EmailField(label="Email nhận lời mời")
    first_name = forms.CharField(label="Tên", max_length=150, required=False)
    last_name = forms.CharField(label="Họ", max_length=150, required=False)
    role = forms.ChoiceField(label="Vai trò", choices=INVITABLE_ROLES)
    reader_number = forms.CharField(label="Mã bạn đọc", max_length=32, required=False)
    reader_type = forms.ChoiceField(label="Loại bạn đọc", choices=ReaderProfile.ReaderType.choices, required=False)
    valid_from = forms.DateField(label="Thẻ có hiệu lực từ", widget=forms.DateInput(attrs={"type": "date"}), required=False)
    valid_until = forms.DateField(label="Thẻ có hiệu lực đến", widget=forms.DateInput(attrs={"type": "date"}), required=False)

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        username_field = get_user_model()._meta.get_field("username")
        for validator in username_field.validators:
            validator(value)
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise ValidationError("Tên đăng nhập này đã được sử dụng.")
        return value

    def clean_email(self):
        value = self.cleaned_data["email"].strip()
        if get_user_model().objects.filter(email__iexact=value).exists():
            raise ValidationError("Email này đã gắn với một tài khoản.")
        return value

    def clean(self):
        data = super().clean()
        if data.get("role") == "reader":
            required = ("reader_number", "reader_type", "valid_from", "valid_until")
            missing = [field for field in required if not data.get(field)]
            if missing:
                raise ValidationError("Độc giả cần có mã bạn đọc, loại bạn đọc và thời hạn thẻ.")
            if data["valid_until"] < data["valid_from"]:
                self.add_error("valid_until", "Ngày hết hạn phải bằng hoặc sau ngày bắt đầu.")
            if ReaderProfile.objects.filter(reader_number=data["reader_number"]).exists():
                self.add_error("reader_number", "Mã bạn đọc này đã được sử dụng.")
        return data


class InvitationAcceptForm(SetPasswordForm):
    pass


class EmailChangeRequestForm(forms.Form):
    email = forms.EmailField(label="Email mới")
    current_password = forms.CharField(label="Mật khẩu hiện tại", widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        users = get_user_model().objects.filter(email__iexact=email).exclude(pk=self.user.pk)
        if users.exists():
            raise ValidationError("Email này đã gắn với một tài khoản khác.")
        if email.casefold() == (self.user.email or "").casefold():
            raise ValidationError("Email này hiện đang được dùng cho tài khoản của bạn.")
        return email

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if not self.user.check_password(password):
            raise ValidationError("Mật khẩu hiện tại không đúng.")
        return password
