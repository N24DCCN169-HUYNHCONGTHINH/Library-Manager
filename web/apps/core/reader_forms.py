from django import forms
from django.utils import timezone

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
        fields = [
            "reader_number", "reader_type", "valid_from", "valid_until", "status",
            "address", "citizen_id", "citizen_id_issued_on", "contact_email", "phone_number",
        ]
        help_texts = {"contact_email": "Email dùng để liên hệ, tách riêng với email xác minh của tài khoản."}
        error_messages = {"reader_number": {"unique": "Mã bạn đọc này đã tồn tại."}}
        widgets = {name: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
                   for name in ("valid_from", "valid_until", "citizen_id_issued_on")}

    def __init__(self, *args, can_suspend=False, can_reactivate=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_suspend:
            self.fields.pop("status")
        elif not can_reactivate:
            self.fields["status"].choices = [choice for choice in ReaderProfile.Status.choices if choice[0] in {self.instance.status, ReaderProfile.Status.SUSPENDED}]

    def clean(self):
        data = super().clean()
        issued_on = data.get("citizen_id_issued_on")
        if issued_on and issued_on > timezone.localdate():
            self.add_error("citizen_id_issued_on", "Ngày cấp không được ở tương lai.")
        if issued_on and "citizen_id" in data and not data["citizen_id"]:
            self.add_error("citizen_id", "Nhập số căn cước nếu đã nhập ngày cấp.")
        if data.get("valid_from") and data.get("valid_until") and data["valid_until"] < data["valid_from"]:
            self.add_error("valid_until", "Ngày hết hạn phải bằng hoặc sau ngày bắt đầu.")
        if self.instance.pk and self.instance.status == ReaderProfile.Status.SUSPENDED and data.get("status") == ReaderProfile.Status.ACTIVE:
            from apps.library.models import Loan, Fine
            reader=self.instance
            if (reader.loans.filter(status=Loan.Status.OPEN,due_at__lt=timezone.now()).exists()
                or reader.restrictions.filter(resolved_at__isnull=True).exists()
                or reader.loans.filter(damage_cases__status__in=["open","contested","approved"]).exists()
                or any(fine.balance>0 for fine in Fine.objects.filter(loan__reader=reader))):
                self.add_error("status","Cần giải quyết quá hạn, khoản phải trả và hồ sơ hạn chế/mất hỏng trước khi mở lại thẻ.")
        return data


class ReaderHistoryDateForm(forms.Form):
    date_from = forms.DateField(label="Từ ngày", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="Đến ngày", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        start, end = data.get("date_from"), data.get("date_to")
        if start and end and start > end:
            self.add_error("date_to", "Đến ngày phải bằng hoặc sau Từ ngày.")
        return data
