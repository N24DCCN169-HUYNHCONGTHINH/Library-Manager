import csv
from datetime import datetime, time, timedelta
from io import BytesIO, StringIO
from django import forms
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from apps.core.views import staff_mfa_required
from apps.core.models import AccountSecurityEvent, ReaderProfile
from apps.core.lifecycle import record_security_event
from .models import Book, BookCopy, Loan, Fine, FinePayment

REPORTS = {"inventory": ("Kho sách", "library.view_bookcopy"), "circulation": ("Mượn / trả", "library.view_loan"), "summary": ("Tổng hợp thư viện", "library.view_system_reports")}
class ReportForm(forms.Form):
    kind = forms.ChoiceField(label="Loại báo cáo", choices=[])
    start = forms.DateField(label="Từ ngày", widget=forms.DateInput(attrs={"type":"date"}))
    end = forms.DateField(label="Đến ngày", widget=forms.DateInput(attrs={"type":"date"}))
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [(key, label) for key,(label,perm) in REPORTS.items() if user.has_perm(perm)]
    def clean(self):
        data=super().clean()
        if data.get("start") and data.get("end") and not 0 <= (data["end"]-data["start"]).days <= 730:
            raise forms.ValidationError("Chọn khoảng thời gian đúng thứ tự, tối đa 731 ngày.")
        return data

def safe_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")):
        return "'"+value
    return value

def report_data(kind, start, end):
    begin=timezone.make_aware(datetime.combine(start,time.min));stop=timezone.make_aware(datetime.combine(end+timedelta(days=1),time.min))
    if kind == "inventory":
        rows=BookCopy.objects.select_related("book","branch").defer('book__cover_image').defer("book__cover_image").filter(created_at__lt=stop).order_by("book__title","barcode")
        if rows.count()>50000: raise ValueError("Báo cáo quá 50.000 dòng; hãy thu hẹp phạm vi.")
        headers=["Mã sách","Nhan đề","Tác giả","Mã bản sách","Cơ sở","Vị trí kệ","Tình trạng hiện tại","Đang sử dụng","Ngày bổ sung"]
        return headers, [[r.book.catalog_number,r.book.title,r.book.authors,r.barcode,r.branch.name if r.branch else "",r.shelf_location,r.get_status_display(),"Có" if r.is_active else "Không",timezone.localtime(r.created_at).strftime("%d/%m/%Y")] for r in rows], "Kho sách bổ sung đến ngày cuối kỳ; tình trạng là hiện tại, không phải ảnh chụp lịch sử."
    loans=Loan.objects.filter(loaned_at__gte=begin,loaned_at__lt=stop)
    if kind == "circulation":
        if loans.count()>50000: raise ValueError("Báo cáo quá 50.000 dòng; hãy thu hẹp khoảng thời gian.")
        headers=["Mã lượt","Mã bạn đọc","Nhan đề","Mã bản","Ngày mượn","Hạn trả","Ngày trả","Trạng thái hiện tại"]
        rows=[[r.pk,r.reader.reader_number,r.copy.book.title,r.copy.barcode,timezone.localtime(r.loaned_at).strftime("%d/%m/%Y %H:%M"),timezone.localtime(r.due_at).strftime("%d/%m/%Y %H:%M"),timezone.localtime(r.returned_at).strftime("%d/%m/%Y %H:%M") if r.returned_at else "",r.get_status_display()] for r in loans.select_related("reader","copy__book").defer('copy__book__cover_image').defer("copy__book__cover_image").order_by("loaned_at","pk")]
        return headers, rows, "Theo ngày mượn trong kỳ; trạng thái và ngày trả cập nhật đến lúc xuất."
    receipts=FinePayment.objects.filter(created_at__gte=begin,created_at__lt=stop)
    return ["Chỉ tiêu","Giá trị","Phạm vi"], [
        ["Lượt mượn",loans.count(),"Theo ngày mượn trong kỳ"],
        ["Lượt trả",Loan.objects.filter(returned_at__gte=begin,returned_at__lt=stop).count(),"Theo ngày trả trong kỳ"],
        ["Độc giả mới",ReaderProfile.objects.filter(created_at__gte=begin,created_at__lt=stop).count(),"Theo ngày tạo trong kỳ"],
        ["Đầu sách mới",Book.objects.filter(created_at__gte=begin,created_at__lt=stop).count(),"Theo ngày tạo trong kỳ"],
        ["Tiền đã thu (VND)",receipts.filter(kind="payment").aggregate(v=Sum("amount"))["v"] or 0,"Biên nhận thực, không gồm giao dịch thử"],
        ["Đã miễn/giảm (VND)",receipts.filter(kind="waiver").aggregate(v=Sum("amount"))["v"] or 0,"Theo ngày phê duyệt trong kỳ"],
        ["Đang quá hạn",Loan.objects.filter(status="open",due_at__lt=timezone.now()).count(),"Hiện tại"],
        ["Bản sách hoạt động",BookCopy.objects.filter(is_active=True).count(),"Hiện tại"]], "Tách số liệu phát sinh trong kỳ và hiện trạng; không trộn thanh toán thử vào tiền thu."

@never_cache
@staff_mfa_required
def reports(request):
    allowed=[key for key,(_,perm) in REPORTS.items() if request.user.has_perm(perm)]
    if not allowed: return HttpResponseForbidden("Bạn không có quyền xuất báo cáo nghiệp vụ.")
    today=timezone.localdate()
    params=request.GET or {"kind":allowed[0],"start":today.replace(day=1),"end":today}
    if params.get("kind") in REPORTS and not request.user.has_perm(REPORTS[params["kind"]][1]):
        return HttpResponseForbidden("Không được xuất loại báo cáo này.")
    form=ReportForm(params,user=request.user)
    headers=[];rows=[];note=""
    if form.is_valid():
        kind=form.cleaned_data["kind"]
        # Recheck explicitly; no report is selected by client-side UI alone.
        if not request.user.has_perm(REPORTS[kind][1]): return HttpResponseForbidden()
        try: headers,rows,note=report_data(**form.cleaned_data)
        except ValueError as exc: form.add_error(None,str(exc))
        else:
            format=request.GET.get("format","")
            if format in {"csv","xlsx"}:
                title=REPORTS[kind][0];start=form.cleaned_data["start"];end=form.cleaned_data["end"]
                if format=="csv":
                    output=StringIO();writer=csv.writer(output);writer.writerow([title,str(start),str(end)]);writer.writerow([note]);writer.writerow(headers)
                    writer.writerows([[safe_cell(v) for v in row] for row in rows])
                    response=HttpResponse("\ufeff"+output.getvalue(),content_type="text/csv; charset=utf-8")
                else:
                    from openpyxl import Workbook
                    from openpyxl.styles import Font, PatternFill
                    from openpyxl.utils import get_column_letter
                    workbook=Workbook();sheet=workbook.active;sheet.title="Bao cao"
                    sheet.append([title,str(start),str(end)]);sheet.append([note]);sheet.append(headers)
                    for row in rows: sheet.append([safe_cell(v) for v in row])
                    sheet.freeze_panes="A4";sheet.auto_filter.ref=f"A3:{get_column_letter(len(headers))}{max(3,sheet.max_row)}"
                    for cell in sheet[3]: cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="176354")
                    for index in range(1,len(headers)+1): sheet.column_dimensions[get_column_letter(index)].width=25
                    buffer=BytesIO();workbook.save(buffer);response=HttpResponse(buffer.getvalue(),content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                response["Content-Disposition"]=f'attachment; filename="library-{kind}-{start}-{end}.{format}"'
                response["X-Content-Type-Options"]="nosniff"
                record_security_event(request.user,AccountSecurityEvent.Kind.REPORT_EXPORTED,request.user,{"report":kind,"start":str(start),"end":str(end),"format":format,"rows":len(rows)})
                return response
    return render(request,"library/reports.html",{"form":form,"headers":headers,"rows":rows[:100],"row_count":len(rows),"note":note})
