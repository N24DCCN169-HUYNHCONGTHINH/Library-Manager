from django import forms


class CheckoutForm(forms.Form):
    reader_number = forms.CharField(label="Mã bạn đọc", max_length=32)
    barcode = forms.CharField(label="Mã vạch bản sách", max_length=64)


class ReturnForm(forms.Form):
    barcode = forms.CharField(label="Mã vạch bản sách", max_length=64)
    condition_note = forms.CharField(label="Ghi nhận tình trạng bất thường (nếu có)", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class FinePaymentForm(forms.Form):
    fine_id = forms.IntegerField(label="Mã khoản phạt", min_value=1)
    amount = forms.DecimalField(label="Số tiền nhận (VND)", min_value=1, decimal_places=0, max_digits=10)
    reason = forms.CharField(label="Ghi chú biên nhận", required=False, max_length=500)
