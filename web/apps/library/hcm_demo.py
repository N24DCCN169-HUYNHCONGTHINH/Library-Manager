"""Clearly synthetic application records alongside a separately sourced directory."""
import html
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import ReaderProfile
from .models import (Book, BookCopy, CirculationPolicy, Fine, FinePayment, LibraryBranch,
                     Loan, LoanEvent, Reservation, ReservationNotification)


def directory():
    return json.loads((settings.BASE_DIR / "legacy" / "hcm-libraries.json").read_text(encoding="utf-8"))


def build_dataset():
    data = {"id": "HCM-SYNTHETIC-V1", "synthetic": True, "date": timezone.localdate().isoformat(),
            "notice": "Sách, tác giả, mã vạch, độc giả và giao dịch hoàn toàn mô phỏng. Không phải dữ liệu/tồn kho của thư viện thật. Các cơ sở demo thuộc hệ thống thử nghiệm, không đại diện quan hệ chi nhánh của thư viện thật.",
            "branches": [], "books": [], "copies": [], "readers": [], "loans": [], "reservations": []}
    topics = ["Lập trình Python", "Kỹ năng nghiên cứu", "Cơ sở dữ liệu", "Văn hóa đô thị", "Lịch sử Việt Nam",
              "Kinh tế học", "Toán ứng dụng", "Kỹ năng đọc", "Giáo dục học", "Tư liệu tham khảo"]
    for i, library in enumerate(directory()["libraries"], 1):
        branch = f"DEMO-HCM-{i:02}"
        data["branches"].append({"code": branch, "name": f"MÔ PHỎNG TP.HCM — cơ sở {i:02}", "reference_library": library["id"]})
        for j, topic in enumerate(topics, 1):
            code = f"DEMO-HCM-B{i:02}{j:02}"
            data["books"].append({"code": code, "title": f"[MÔ PHỎNG] {topic} — bộ {i:02}",
                "authors": f"Nhóm biên soạn mô phỏng {i:02}", "material_type": "reference" if j == 10 else "general",
                "loan_mode": "in_library_only" if j == 10 else "home_loan"})
            for k in range(1, 4):
                data["copies"].append({"barcode": f"{code}-C{k}", "book": code, "branch": branch,
                    "status": "on_loan" if j == 1 else ("on_hold" if j == 3 and k == 1 else ("inventory_review" if j == 3 else "available"))})
        for k in range(1, 7):
            n = (i - 1) * 6 + k
            data["readers"].append({"username": f"hcm_demo_{n:02}", "reader_number": f"DEMO-HCM-R{n:03}",
                "name": f"Độc giả mô phỏng {n:02}", "email": f"hcm-demo-{n:02}@example.invalid",
                "reader_type": ["student", "faculty", "employee"][(k - 1) % 3],
                "scenario": ["mượn bình thường", "sắp đến hạn để thử gia hạn", "quá hạn, có nợ",
                             "đang chờ đặt trước", "đã trả, còn nợ một phần", "sẵn sàng nhận giữ chỗ"][k - 1]})
        for k in range(1, 4):
            n = (i - 1) * 6 + k
            data["loans"].append({"reader": f"DEMO-HCM-R{n:03}", "barcode": f"DEMO-HCM-B{i:02}01-C{k}",
                "status": "open", "due_days_from_seed": [13, 1, -3][k - 1], "fine": 3000 if k == 3 else 0, "paid": 0})
        data["loans"].append({"reader": f"DEMO-HCM-R{(i-1)*6+5:03}", "barcode": f"DEMO-HCM-B{i:02}02-C1",
            "status": "returned", "due_days_from_seed": -4, "fine": 2000, "paid": 1000})
        data["reservations"] += [
            {"reader": f"DEMO-HCM-R{(i-1)*6+4:03}", "book": f"DEMO-HCM-B{i:02}01", "status": "waiting", "barcode": None},
            {"reader": f"DEMO-HCM-R{(i-1)*6+6:03}", "book": f"DEMO-HCM-B{i:02}03", "status": "ready", "barcode": f"DEMO-HCM-B{i:02}03-C1"}]
    data["counts"] = {key: len(data[key]) for key in ("branches", "books", "copies", "readers", "loans", "reservations")}
    data["counts"].update(fines=sum(bool(r["fine"]) for r in data["loans"]), payments=sum(bool(r["paid"]) for r in data["loans"]))
    return data


def export_dataset(output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValidationError("Thư mục kết quả phải trống.")
    output.mkdir(parents=True, exist_ok=True)
    real, demo = directory(), build_dataset()
    for name, data in [("libraries-real.json", real), ("demo-dataset.json", demo)]:
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    e = lambda value: html.escape(str(value))
    lines = ["<!doctype html><html lang='vi'><meta charset='utf-8'><title>Dữ liệu thư viện TP.HCM</title>",
        "<style>body{font:16px Segoe UI;margin:40px;max-width:1100px}td,th{border:1px solid #ccc;padding:10px}table{border-collapse:collapse}h1,h2{color:#18366f}</style>",
        "<h1>Bộ dữ liệu thư viện TP.HCM</h1><h2>1. Danh mục thực tế có nguồn</h2><p>" + e(real["scope"]) + "</p>",
        "<p>Đối chiếu ngày " + real["verified_on"] + ". Trường trống nghĩa là chưa xác minh.</p>"]
    for library in real["libraries"]:
        lines += ["<h3>" + e(library["name"]) + "</h3><p>" + e(library.get("address") or library.get("address_note")) + "</p>",
            "<p>Dịch vụ công bố: " + e(", ".join(library["services"]) or "Chưa tổng hợp trong bộ này") + "</p>",
            "<p>Nguồn: " + " · ".join('<a href="' + e(url) + '">' + e(url) + '</a>' for url in library["sources"]) + "</p>"]
    lines += ["<h2>2. Bộ mô phỏng để chạy ứng dụng</h2><p>" + e(demo["notice"]) + "</p><p>" + e(demo["counts"]) + "</p>",
        "<p>Mọi tài khoản demo ban đầu không có mật khẩu dùng được; đặt mật khẩu bằng changepassword trước khi đăng nhập. Email .invalid không nhận thư thật.</p>",
        "<h3>Tài khoản và kịch bản</h3><table><tr><th>Tên đăng nhập</th><th>Mã bạn đọc</th><th>Kịch bản</th></tr>"]
    for reader in demo["readers"]:
        lines.append("<tr>" + "".join("<td>" + e(reader[key]) + "</td>" for key in ("username", "reader_number", "scenario")) + "</tr>")
    lines.append("</table></html>")
    (output / "index.html").write_text("\n".join(lines), encoding="utf-8")
    return demo


@transaction.atomic
def seed_dataset(actor, data):
    if not actor.is_active or not actor.has_perm("library.add_book") or not actor.has_perm("core.add_readerprofile"):
        raise ValidationError("Cần tài khoản quản lý có quyền thêm sách và độc giả.")
    User = get_user_model()
    # Refuse all collisions, including partial previous runs; never reset user data.
    if (LibraryBranch.objects.filter(code__in=[r["code"] for r in data["branches"]]).exists()
        or Book.objects.filter(catalog_number__in=[r["code"] for r in data["books"]]).exists()
        or BookCopy.objects.filter(barcode__in=[r["barcode"] for r in data["copies"]]).exists()
        or ReaderProfile.objects.filter(reader_number__in=[r["reader_number"] for r in data["readers"]]).exists()
        or User.objects.filter(username__in=[r["username"] for r in data["readers"]]).exists()):
        raise ValidationError("Mã demo đã tồn tại; dừng để không ghi trùng hoặc ghi đè. Bộ dữ liệu đã nạp có thể tiếp tục dùng.")
    group = Group.objects.get(name="reader")
    now, today = timezone.localtime(), timezone.localdate()
    policies = {}
    for reader_type in ("student", "faculty", "employee"):
        policies[reader_type] = CirculationPolicy.objects.create(reader_type=reader_type, material_type="general",
            version=900001, effective_from=today - timedelta(days=366), effective_until=today - timedelta(days=1),
            max_active_loans=5 if reader_type == "student" else 10, loan_days=14 if reader_type == "student" else 30,
            created_by=actor)
    # Historical demo-only policies do not change which policy the live desk selects today.
    branches = {r["code"]: LibraryBranch.objects.create(code=r["code"], name=r["name"],
        address="Địa điểm mô phỏng, không phải địa chỉ thư viện thật") for r in data["branches"]}
    books = {r["code"]: Book.objects.create(catalog_number=r["code"], title=r["title"], authors=r["authors"],
        material_type=r["material_type"], loan_mode=r["loan_mode"], subjects="Dữ liệu mô phỏng TP.HCM",
        created_by=actor, updated_by=actor) for r in data["books"]}
    copies = {r["barcode"]: BookCopy.objects.create(book=books[r["book"]], branch=branches[r["branch"]],
        barcode=r["barcode"], status=r["status"], shelf_location="DEMO-A1", created_by=actor) for r in data["copies"]}
    readers = {}
    for r in data["readers"]:
        user = User.objects.create_user(r["username"], email=r["email"], first_name=r["name"])
        user.groups.add(group)
        profile = ReaderProfile.objects.create(user=user, reader_number=r["reader_number"], reader_type=r["reader_type"],
            valid_from=today - timedelta(days=30), valid_until=today + timedelta(days=365), membership_verified=True,
            membership_verified_at=now, membership_verified_by=actor, verification_method="synthetic_demo")
        readers[r["reader_number"]] = profile
    for index, r in enumerate(data["loans"], 1):
        reader, copy = readers[r["reader"]], copies[r["barcode"]]
        policy = policies[reader.reader_type]
        loan = Loan.objects.create(reader=reader, copy=copy, policy=policy, status=r["status"],
            reader_type_snapshot=reader.reader_type, material_type_snapshot="general", policy_version_snapshot=policy.version,
            max_loans_snapshot=policy.max_active_loans, overdue_rate_snapshot=1000, overdue_cap_snapshot=30000,
            loaned_at=now+timedelta(days=r["due_days_from_seed"]-policy.loan_days),
            due_at=(now+timedelta(days=r["due_days_from_seed"])).replace(hour=23, minute=59, second=0, microsecond=0),
            returned_at=now-timedelta(days=2) if r["status"] == "returned" else None,
            returned_by=actor if r["status"] == "returned" else None, created_by=actor)
        LoanEvent.objects.create(loan=loan, event_type="demo_seed", actor=actor, reason="Dữ liệu hoàn toàn mô phỏng HCM-SYNTHETIC-V1")
        if r["fine"]:
            fine = Fine.objects.create(loan=loan, rate_per_day=1000, cap_amount=30000, accrued_amount=r["fine"],
                accrued_days=r["fine"] // 1000, status="due" if r["status"] == "returned" else "accruing")
            if r["paid"]:
                FinePayment.objects.create(fine=fine, kind="payment", amount=r["paid"], created_by=actor,
                    receipt_number=f"DEMO-HCM-PT-{index:03}", reason="Khoản thu mô phỏng, không phải tiền thật")
    for r in data["reservations"]:
        ready = r["status"] == "ready"
        reservation = Reservation.objects.create(reader=readers[r["reader"]], book=books[r["book"]], status=r["status"],
            copy=copies.get(r["barcode"]), ready_at=now if ready else None, expires_at=now+timedelta(hours=48) if ready else None)
        if ready:
            ReservationNotification.objects.create(reservation=reservation, last_error="Dữ liệu demo: email .invalid, không gửi thư thật.")
    return data["counts"]
