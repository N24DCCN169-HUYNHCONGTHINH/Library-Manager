from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .lifecycle import issue_account_invitation, record_security_event
from .models import AccountSecurityEvent, ReaderProfile
from .roles import PRIVILEGED
from .reader_forms import ReaderHistoryDateForm, ReaderInvitationForm, ReaderProfileForm
from .views import staff_mfa_required


@staff_mfa_required
def reader_list(request):
    if not request.user.has_perm("core.view_readerprofile"):
        return HttpResponseForbidden("Bạn không được cấp quyền xem hồ sơ độc giả.")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    profiles = ReaderProfile.objects.select_related("user").order_by("reader_number", "pk")
    if query:
        profiles = profiles.filter(Q(reader_number__icontains=query) | Q(user__username__icontains=query)
                                   | Q(user__email__icontains=query) | Q(user__first_name__icontains=query)
                                   | Q(user__last_name__icontains=query))
    if status in ReaderProfile.Status.values:
        profiles = profiles.filter(status=status)
    else:
        status = ""
    return render(request, "core/reader_list.html", {
        "page_obj": Paginator(profiles, 25).get_page(request.GET.get("page")),
        "query": query, "selected_status": status, "statuses": ReaderProfile.Status.choices,
    })


@staff_mfa_required
def reader_add(request):
    if not (request.user.has_perm("core.add_readerprofile") and (request.user.has_perm("core.issue_account_invitation") or request.user.has_perm("core.invite_reader"))):
        return HttpResponseForbidden("Bạn không được cấp quyền tạo độc giả và gửi lời mời.")
    form = ReaderInvitationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            issue_account_invitation(actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionError) as exc:
            form.add_error(None, str(exc))
        except IntegrityError:
            form.add_error(None, "Tên đăng nhập hoặc mã bạn đọc vừa được sử dụng. Hãy kiểm tra lại.")
        else:
            messages.success(request, "Đã tạo độc giả chờ kích hoạt và gửi lời mời đặt mật khẩu. Thẻ cần được xác minh riêng.")
            return redirect("reader_list")
    return render(request, "core/reader_form.html", {"form": form})


@staff_mfa_required
def reader_detail(request, reader_id):
    if not request.user.has_perm("core.view_readerprofile"):
        return HttpResponseForbidden("Bạn không được cấp quyền xem hồ sơ độc giả.")
    profile = get_object_or_404(ReaderProfile.objects.select_related("user"), pk=reader_id)
    return render(request, "core/reader_detail.html", {
        "profile": profile, **reader_history(request, profile),
    })


@staff_mfa_required
def reader_edit(request, reader_id):
    if not request.user.has_perm("core.change_readerprofile"):
        return HttpResponseForbidden("Bạn không được cấp quyền sửa hồ sơ độc giả.")
    can_verify = request.user.has_perm("core.verify_reader_membership") and (
        request.user.is_superuser or request.user.groups.filter(name__in=PRIVILEGED).exists()
    )
    with transaction.atomic():
        profiles = ReaderProfile.objects.all()
        if request.method == "POST":
            profiles = profiles.select_for_update()
        profile = get_object_or_404(profiles, pk=reader_id)
        if request.method == "POST" and request.POST.get("action") == "verify_membership":
            if not can_verify:
                return HttpResponseForbidden("Bạn không được cấp quyền xác minh hồ sơ.")
            if not profile.membership_verified or not profile.membership_verified_at:
                profile.membership_verified = True
                profile.membership_verified_at = timezone.now()
                profile.membership_verified_by = request.user
                profile.verification_method = "staff_review"
                profile.save(update_fields=[
                    "membership_verified", "membership_verified_at", "membership_verified_by",
                    "verification_method", "updated_at",
                ])
                record_security_event(
                    profile.user, AccountSecurityEvent.Kind.MEMBERSHIP_VERIFIED, request.user,
                    {"reader_number": profile.reader_number, "method": profile.verification_method},
                    reason="Đã đối chiếu hồ sơ và thẻ bạn đọc",
                )
            messages.success(request, "Đã xác minh hồ sơ độc giả.")
            return redirect("reader_edit", reader_id=profile.pk)
        fields = ("reader_number", "reader_type", "valid_from", "valid_until", "status")
        before = {name: str(getattr(profile, name)) for name in fields}
        form = ReaderProfileForm(request.POST if request.method == "POST" else None, instance=profile,
                                 can_suspend=request.user.has_perm("core.suspend_reader"),
                                 can_reactivate=request.user.has_perm("library.manage_reader_restrictions"))
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    profile = form.save()
                    after = {name: str(getattr(profile, name)) for name in fields}
                    record_security_event(profile.user, AccountSecurityEvent.Kind.MEMBERSHIP_CHANGED,
                                          request.user, {
                                              "before": before, "after": after,
                                              "updated_personal_fields": [
                                                  field for field in form.changed_data if field in {
                                                      "address", "citizen_id", "citizen_id_issued_on",
                                                      "contact_email", "phone_number",
                                                  }
                                              ],
                                          },
                                          reason=form.cleaned_data["reason"])
            except IntegrityError:
                form.add_error("reader_number", "Mã bạn đọc vừa được sử dụng. Hãy chọn mã khác.")
            else:
                messages.success(request, "Đã cập nhật hồ sơ độc giả.")
                return redirect("reader_detail", reader_id=profile.pk)
    return render(request, "core/reader_form.html", {
        "form": form, "profile": profile, "can_verify": can_verify, **reader_history(request, profile),
    })


def reader_history(request, profile):
    from apps.library.models import Book, DamageCase, Fine, FinePayment, Loan, LoanEvent, LoanNotification

    loans = profile.loans.select_related("copy__book").defer("copy__book__cover_image")
    sections = {
        "loans": ("Mượn / trả", "library.view_loan", loans.order_by("-loaned_at", "-pk")),
        "overdue": ("Quá hạn", "library.view_loan", loans.filter(
            Q(status=Loan.Status.OPEN, due_at__lt=timezone.now())
            | Q(returned_at__gt=F("due_at"))
            | Q(long_overdue_review_at__isnull=False)
            | Q(fine__accrued_days__gt=0)
        ).order_by("-due_at", "-pk")),
        "events": ("Nhật ký phiếu", "library.view_loanevent", LoanEvent.objects.filter(
            loan__reader=profile,
        ).select_related("actor").order_by("-occurred_at", "-pk")),
        "reservations": ("Đặt trước", "library.view_reservation", profile.reservations.select_related(
            "book",
        ).defer("book__cover_image").order_by("-created_at", "-pk")),
        "fines": ("Khoản phạt", "library.view_fine", Fine.objects.filter(
            loan__reader=profile,
        ).prefetch_related("transactions").order_by("-calculated_at", "-pk")),
        "payments": ("Biên nhận phạt", "library.view_finepayment", FinePayment.objects.filter(
            fine__loan__reader=profile,
        ).select_related("fine").order_by("-created_at", "-pk")),
        "damage": ("Mất / hỏng và bồi thường", "library.view_damagecase", DamageCase.objects.filter(
            loan__reader=profile,
        ).select_related("loan__copy__book").defer("loan__copy__book__cover_image").order_by("-reported_at", "-pk")),
        "notices": ("Nhắc hạn", "library.view_loannotification", LoanNotification.objects.filter(
            loan__reader=profile,
        ).order_by("-created_at", "-pk")),
        "restrictions": ("Hạn chế mượn", "library.view_readerrestriction", profile.restrictions.order_by("-created_at", "-pk")),
        "account": ("Tài khoản và thẻ", "core.view_accountsecurityevent", AccountSecurityEvent.objects.filter(
            subject_id=profile.user_id,
        ).select_related("actor").order_by("-occurred_at", "-pk")),
    }
    allowed = {key: (label, rows) for key, (label, permission, rows) in sections.items()
               if request.user.has_perm(permission)}
    selected = request.GET.get("history", "loans" if "loans" in allowed else "")
    date_form = ReaderHistoryDateForm(request.GET)
    start = end = None
    if date_form.is_valid():
        start = date_form.cleaned_data["date_from"]
        end = date_form.cleaned_data["date_to"]
    date_fields = {
        "loans": "loaned_at", "overdue": "loaned_at", "events": "occurred_at",
        "reservations": "created_at", "fines": "calculated_at", "payments": "created_at",
        "damage": "reported_at", "notices": "created_at", "restrictions": "created_at",
        "account": "occurred_at",
    }

    def in_date_range(rows, field):
        if start:
            rows = rows.filter(**{f"{field}__date__gte": start})
        if end:
            rows = rows.filter(**{f"{field}__date__lte": end})
        return rows

    if selected in allowed:
        label, rows = allowed[selected]
        allowed[selected] = (label, in_date_range(rows, date_fields[selected]))
    today = timezone.localdate()
    month_index = today.year * 12 + today.month - 1
    six_month_start = today.replace(year=(month_index - 5) // 12, month=(month_index - 5) % 12 + 1, day=1)
    page = Paginator(allowed[selected][1], 20).get_page(request.GET.get("history_page")) if selected in allowed else None
    overview = {}
    if selected == "loans" and page is not None:
        related = []
        if "fines" in allowed or "payments" in allowed:
            related.append("fine__transactions")
        if "damage" in allowed:
            related.append("damage_cases")
        page.object_list = page.object_list.prefetch_related(*related)
        if "restrictions" in allowed:
            overview["history_restrictions"] = Paginator(in_date_range(allowed["restrictions"][1], "created_at"), 10).get_page(
                request.GET.get("restriction_page")
            )
        loans = in_date_range(loans, "loaned_at")
        monthly_loans = loans if start or end else loans.filter(loaned_at__date__gte=six_month_start)
        monthly_rows = monthly_loans.order_by().annotate(month=TruncMonth("loaned_at")).values("month").annotate(total=Count("pk"))
        monthly_counts = {row["month"].year * 12 + row["month"].month - 1: row["total"] for row in monthly_rows}
        first_month = start.year * 12 + start.month - 1 if start else min(monthly_counts, default=month_index)
        last_month = end.year * 12 + end.month - 1 if end else month_index
        if not start and not end:
            first_month = month_index - 5
        months = range(first_month, last_month + 1) if 0 <= last_month - first_month < 24 else sorted(monthly_counts)
        overview["history_monthly"] = [
            (f"{index % 12 + 1:02}/{index // 12}", monthly_counts.get(index, 0)) for index in months
        ]
        material_labels = dict(Book.MaterialType.choices)
        materials = loans.order_by().values("material_type_snapshot").annotate(total=Count("pk")).order_by("-total", "material_type_snapshot")
        material_colors = {
            "general": "returned", "reference": "blue", "textbook": "open",
            "rare": "damaged", "periodical": "reminder", "thesis": "lost",
        }
        overview["history_materials"] = [
            (material_labels.get(row["material_type_snapshot"], "Chưa phân loại"), row["total"],
             material_colors.get(row["material_type_snapshot"], "lost"))
            for row in materials
        ]
        outcomes = loans.aggregate(
            on_time=Count("pk", filter=Q(status=Loan.Status.RETURNED, returned_at__lte=F("due_at"))),
            late=Count("pk", filter=Q(status=Loan.Status.RETURNED, returned_at__gt=F("due_at"))),
            overdue=Count("pk", filter=Q(status=Loan.Status.OPEN, due_at__lt=timezone.now())),
            lost=Count("pk", filter=Q(status=Loan.Status.LOST)),
        )
        overview["history_outcomes"] = [
            ("Trả đúng hạn", outcomes["on_time"], "returned"),
            ("Trả trễ", outcomes["late"], "overdue"),
            ("Đang quá hạn", outcomes["overdue"], "overdue"),
            ("Đã báo mất", outcomes["lost"], "lost"),
        ]
        for name in ("monthly", "materials", "outcomes"):
            overview[f"history_{name}_max"] = max((entry[1] for entry in overview[f"history_{name}"]), default=1) or 1
    return {
        **overview,
        "history_now": timezone.now(),
        "history_date_form": date_form,
        "history_date_filtered": bool(start or end),
        "history_quick_ranges": [
            ("30 ngày", (today - timedelta(days=29)).isoformat()),
            ("90 ngày", (today - timedelta(days=89)).isoformat()),
            ("6 tháng", six_month_start.isoformat()),
        ],
        "history_today": today.isoformat(),
        "history_sections": [(key, label) for key, (label, _) in allowed.items()],
        "history_selected": selected if page is not None else "",
        "history_page": page,
        "history_label": allowed[selected][0] if page is not None else "",
    }
