from django import forms

from .lifecycle_forms import AccountInvitationForm
from .models import ReaderProfile


class ReaderInvitationForm(AccountInvitationForm):
    role = forms.ChoiceField(choices=[("reader", "Độc giả")], initial="reader", widget=forms.HiddenInput)
    reader_number = forms.CharField(
        label="Mã bạn đọc", max_length=32,
        validators=ReaderProfile._meta.get_field("reader_number").validators,
    )


class ReaderProfileForm(forms.ModelForm):
    reason = forms.CharField(label="Lý do cập nhật", max_length=300)

    class Meta:
        model = ReaderProfile
        fields = ["reader_number", "reader_type", "valid_from", "valid_until", "status"]
        error_messages = {"reader_number": {"unique": "Mã bạn đọc này đã tồn tại."}}
        widgets = {name: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
                   for name in ("valid_from", "valid_until")}

    def __init__(self, *args, can_suspend=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_suspend:
            self.fields.pop("status")

    def clean(self):
        data = super().clean()
        if data.get("valid_from") and data.get("valid_until") and data["valid_until"] < data["valid_from"]:
            self.add_error("valid_until", "Ngày hết hạn phải bằng hoặc sau ngày bắt đầu.")
        return data
