import csv
from collections import Counter
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
    start = forms.DateField(label="Từ ngày", widget=forms.DateInput(format="%Y-%m-%d",attrs={"type":"date"}))
    end = forms.DateField(label="Đến ngày", widget=forms.DateInput(format="%Y-%m-%d",attrs={"type":"date"}))
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

def report_indicators(kind, rows):
    indicators = []
    if kind == "circulation":
        statuses = Counter(row[-1] for row in rows)
        indicators = [
            ("Lượt mượn trong kỳ", len(rows), "#,##0"),
            ("Đang mượn", statuses["Đang mượn"], "#,##0"),
            ("Đã trả", statuses["Đã trả"], "#,##0"),
            ("Đã báo mất", statuses["Đã báo mất"], "#,##0"),
        ]
    elif kind == "summary":
        values_by_label = {label: value for label, value, _ in rows}
        indicators = [
            ("Lượt mượn trong kỳ", values_by_label["Lượt mượn"], "#,##0"),
            ("Lượt trả trong kỳ", values_by_label["Lượt trả"], "#,##0"),
            ("Tiền thu trong kỳ", values_by_label["Tiền đã thu (VND)"], '#,##0 "₫"'),
        ]
    return indicators


def excel_report(kind, title, start, end, headers, rows, note):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    widths = {
        "inventory": (17, 38, 25, 18, 23, 17, 24, 16, 17),
        "circulation": (13, 19, 38, 18, 21, 21, 21, 24),
        "summary": (33, 20, 57),
    }
    date_columns = {"inventory": (9,), "circulation": (5, 6, 7)}.get(kind, ())
    date_pattern = "%d/%m/%Y" if kind == "inventory" else "%d/%m/%Y %H:%M"
    status_column = {"inventory": 7, "circulation": 8}.get(kind)
    status_colors = {
        "Sẵn sàng": ("DCFCE7", "166534"),
        "Đã trả": ("DCFCE7", "166534"),
        "Đang mượn": ("FEF3C7", "854D0E"),
        "Đang giữ chỗ": ("DBEAFE", "1E40AF"),
        "Hư hỏng": ("F3E8FF", "6B21A8"),
        "Đang xem xét tình trạng": ("F3E8FF", "6B21A8"),
        "Đã mất": ("FEE2E2", "991B1B"),
        "Đã báo mất": ("FEE2E2", "991B1B"),
    }

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title.replace(" / ", " - ")
    title_color, accent, tint = {
        "inventory": ("123E35", "176354", "E8F3EE"),
        "circulation": ("183250", "234F7C", "EAF2FB"),
        "summary": ("392C53", "604780", "F1ECF8"),
    }[kind]
    sheet.sheet_properties.tabColor = accent
    sheet.sheet_view.showGridLines = False
    last_column = get_column_letter(len(headers))
    for index, width in enumerate(widths[kind], 1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    sheet.merge_cells(f"A1:{last_column}1")
    sheet["A1"] = f"LIBRARY HUB  |  {title.upper()}"
    sheet["A1"].font = Font(name="Calibri", size=20, bold=True, color="FFFFFF")
    sheet["A1"].fill = PatternFill("solid", fgColor=title_color)
    sheet["A1"].alignment = Alignment(vertical="center", indent=1)
    sheet.row_dimensions[1].height = 40

    sheet.merge_cells(f"A2:{last_column}2")
    sheet["A2"] = f"Kỳ báo cáo  {start:%d/%m/%Y} – {end:%d/%m/%Y}  ·  {len(rows):,} dòng\n{note}"
    sheet["A2"].font = Font(name="Calibri", size=11, color="294C43")
    sheet["A2"].fill = PatternFill("solid", fgColor=tint)
    sheet["A2"].alignment = Alignment(vertical="center", wrap_text=True, indent=1)
    sheet.row_dimensions[2].height = 43

    indicators = report_indicators(kind, rows)
    header_row = 3
    if indicators:
        span = len(headers) // len(indicators)
        for index, (label, value, number_format) in enumerate(indicators):
            first = index * span + 1
            last = first + span - 1
            for row_number, content in ((4, label), (5, value)):
                if span > 1:
                    sheet.merge_cells(start_row=row_number, start_column=first, end_row=row_number, end_column=last)
                cell = sheet.cell(row_number, first, content)
                cell.fill = PatternFill("solid", fgColor=tint)
                cell.font = Font(name="Calibri", size=19 if row_number == 5 else 10, bold=True, color=accent)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                if row_number == 5:
                    cell.number_format = number_format
        for row_number, height in ((3, 9), (4, 30), (5, 32), (6, 10)):
            sheet.row_dimensions[row_number].height = height
        header_row = 7

    for column, label in enumerate(headers, 1):
        sheet.cell(header_row, column, label)
    sheet.row_dimensions[header_row].height = 27
    sheet.freeze_panes = f"A{header_row + 1}"
    header_fill = PatternFill("solid", fgColor=accent)
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for cell in sheet[header_row]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fills = [PatternFill("solid", fgColor=color) for color in ("FFFFFF", "F2F7F5")]
    body_font = Font(name="Calibri", size=11, color="18342E")
    numeric_font = Font(name="Calibri", size=12, bold=True, color=accent)
    status_styles = {
        label: (PatternFill("solid", fgColor=background), Font(name="Calibri", bold=True, color=ink))
        for label, (background, ink) in status_colors.items()
    }
    text_alignment = Alignment(vertical="center", wrap_text=True, indent=1)
    centered = Alignment(vertical="center", horizontal="center", wrap_text=True)
    for row_number, row in enumerate(rows, header_row + 1):
        values = [safe_cell(value) for value in row]
        for column in date_columns:
            value = values[column - 1]
            values[column - 1] = datetime.strptime(value, date_pattern) if value else None
        sheet.append(values)
        lines = max(
            (len(value) // max(1, width - 4) + 1 for value, width in zip(values, widths[kind]) if isinstance(value, str)),
            default=1,
        )
        sheet.row_dimensions[row_number].height = min(120, 10 + 15 * lines)
        for cell in sheet[row_number]:
            cell.fill = fills[row_number % 2]
            cell.font = body_font
            cell.alignment = text_alignment
            if cell.column in date_columns:
                cell.number_format = "dd/mm/yyyy" if kind == "inventory" else "dd/mm/yyyy hh:mm"
                cell.alignment = centered
            elif kind == "summary" and cell.column == 2:
                cell.font = numeric_font
                cell.number_format = '#,##0 "₫"' if "(VND)" in row[0] else "#,##0"
            elif cell.column == status_column and cell.value in status_styles:
                cell.fill, cell.font = status_styles[cell.value]
                cell.alignment = centered

    sheet.auto_filter.ref = f"A{header_row}:{last_column}{sheet.max_row}"
    sheet.print_title_rows = f"1:{header_row}"
    sheet.print_options.horizontalCentered = True
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape" if kind != "summary" else "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.oddFooter.left.text = "Library Hub"
    sheet.oddFooter.right.text = "Trang &P / &N"

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@never_cache
@staff_mfa_required
def reports(request):
    allowed=[key for key,(_,perm) in REPORTS.items() if request.user.has_perm(perm)]
    if not allowed: return HttpResponseForbidden("Bạn không có quyền xuất báo cáo nghiệp vụ.")
    today=timezone.localdate()
    params={"kind":allowed[0],"start":today.replace(day=1),"end":today}
    params.update(request.GET.dict())
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
            if format == "print":
                record_security_event(
                    request.user, AccountSecurityEvent.Kind.REPORT_EXPORTED, request.user,
                    {"report": kind, "start": str(form.cleaned_data["start"]), "end": str(form.cleaned_data["end"]),
                     "format": "print", "rows": min(len(rows), 100)},
                )
                return render(request, "library/report_print.html", {
                    **form.cleaned_data, "title": REPORTS[kind][0], "headers": headers,
                    "rows": rows[:100], "row_count": len(rows), "note": note,
                    "indicators": report_indicators(kind, rows),
                })
            if format in {"csv","xlsx"}:
                title=REPORTS[kind][0];start=form.cleaned_data["start"];end=form.cleaned_data["end"]
                if format=="csv":
                    output=StringIO();writer=csv.writer(output);writer.writerow([title,str(start),str(end)]);writer.writerow([note]);writer.writerow(headers)
                    writer.writerows([[safe_cell(v) for v in row] for row in rows])
                    response=HttpResponse("\ufeff"+output.getvalue(),content_type="text/csv; charset=utf-8")
                else:
                    response = HttpResponse(
                        excel_report(kind, title, start, end, headers, rows, note),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                response["Content-Disposition"]=f'attachment; filename="library-{kind}-{start}-{end}.{format}"'
                response["X-Content-Type-Options"]="nosniff"
                record_security_event(request.user,AccountSecurityEvent.Kind.REPORT_EXPORTED,request.user,{"report":kind,"start":str(start),"end":str(end),"format":format,"rows":len(rows)})
                return response
    return render(request,"library/reports.html",{"form":form,"headers":headers,"rows":rows[:100],"row_count":len(rows),"note":note})
