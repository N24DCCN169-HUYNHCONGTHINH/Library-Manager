from contextlib import closing
"""Read-only legacy extraction and an isolated, reviewable staging package."""
import hashlib
import html
import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from django.core.exceptions import ValidationError

from .models import Book


CORE_COLUMNS = {
    "books": {"id", "code", "title", "author", "quantity", "available"},
    "readers": {"id", "code", "name"},
    "borrowings": {"id", "book_id", "reader_id", "borrow_date", "due_date", "return_date", "fine", "status"},
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def integer(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("not an integer")
    return value


def extract(source, output, mapping):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise ValueError("Không tìm thấy tệp SQLite nguồn.")
    if output == source.parent or output in source.parents:
        raise ValueError("Chọn thư mục kết quả riêng, khác thư mục dữ liệu nguồn.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Thư mục kết quả phải trống để không ghi đè lần chạy trước.")
    if not isinstance(mapping, dict) or set(mapping) - {"books"} or not isinstance(mapping.get("books", {}), dict):
        raise ValueError("Mapping phải có dạng {books: {mã sách: {material_type, loan_mode}}}.")
    before = digest(source)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        # Work against a consistent snapshot, including committed WAL contents.
        with closing(sqlite3.connect(":memory:")) as snapshot:
            original.backup(snapshot)
            snapshot.row_factory = sqlite3.Row
            tables = [row[0] for row in snapshot.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            for table, columns in CORE_COLUMNS.items():
                if table not in tables:
                    raise ValueError("Thiếu bảng nguồn bắt buộc: " + table)
                actual = {row[1] for row in snapshot.execute('PRAGMA table_info("' + table + '")')}
                if not columns <= actual:
                    raise ValueError("Cấu trúc bảng nguồn chưa được hỗ trợ: " + table)
            rows = {table: [dict(row) for row in snapshot.execute('SELECT * FROM "' + table.replace('"', '""') + '"')]
                    for table in tables}
            output.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(output / "source-snapshot.sqlite3")) as backup:
                snapshot.backup(backup)
    records = []
    book_ids = {row["id"] for row in rows["books"]}
    reader_ids = {row["id"] for row in rows["readers"]}
    book_codes = Counter(row.get("code") for row in rows["books"])
    reader_codes = Counter(row.get("code") for row in rows["readers"])
    for table, items in rows.items():
        for index, row in enumerate(items):
            record = {"table": table, "source_id": row.get("id", index + 1),
                      "status": "review", "issues": [], "normalized": None}
            issues = record["issues"]
            if table == "books":
                code = row.get("code")
                if not code or book_codes[code] != 1:
                    issues.append("missing_or_duplicate_book_code")
                try:
                    quantity, available = integer(row["quantity"]), integer(row["available"])
                    if not 0 <= available <= quantity:
                        raise ValueError()
                except ValueError:
                    issues.append("invalid_inventory_totals")
                entry = mapping.get("books", {}).get(code)
                if not isinstance(entry, dict) or set(entry) != {"material_type", "loan_mode"}:
                    issues.append("material_type_and_loan_mode_need_mapping")
                else:
                    data = {"catalog_number": code, "title": row.get("title"), "authors": row.get("author") or "",
                        "subjects": row.get("category") or "", "publisher": row.get("publisher") or "",
                        "publication_year": row.get("year"), "edition": row.get("edition") or "",
                        "material_type": entry["material_type"], "loan_mode": entry["loan_mode"], "is_active": False}
                    book = Book(**data)
                    # Validate fields without accessing the destination database.
                    try:
                        book.clean_fields(exclude=["created_by", "updated_by"])
                        year = data["publication_year"]
                        if year is not None and (not isinstance(year, int) or not 1 <= year <= date.today().year + 1):
                            raise ValueError()
                        if data["material_type"] in {"rare", "periodical", "thesis"} and data["loan_mode"] != "in_library_only":
                            raise ValueError()
                    except (ValidationError, ValueError, TypeError):
                        issues.append("invalid_book_metadata_or_policy")
                    record["normalized"] = data
                if not issues:
                    record["status"] = "ready"
                record["inventory_note"] = "physical_barcodes_require_inventory_review"
            elif table == "readers":
                if not row.get("code") or reader_codes[row.get("code")] != 1:
                    issues.append("missing_or_duplicate_reader_code")
                issues.append("reader_type_account_link_and_membership_require_review")
            elif table == "borrowings":
                if row["book_id"] not in book_ids or row["reader_id"] not in reader_ids:
                    issues.append("missing_book_or_reader_reference")
                for field in ("borrow_date", "due_date"):
                    try:
                        date.fromisoformat(row.get(field) or "")
                    except (ValueError, TypeError):
                        issues.append("invalid_" + field)
                if not any(issue.startswith("invalid_") for issue in issues):
                    if row["due_date"] < row["borrow_date"]:
                        issues.append("due_date_precedes_borrow_date")
                if row.get("return_date"):
                    try:
                        returned = date.fromisoformat(row["return_date"])
                        if returned < date.fromisoformat(row["borrow_date"]):
                            raise ValueError()
                    except (ValueError, TypeError):
                        issues.append("invalid_return_date")
                try:
                    if integer(row["fine"]) < 0:
                        raise ValueError()
                except ValueError:
                    issues.append("invalid_fine_amount")
                issues.append("physical_copy_policy_snapshot_and_financial_evidence_require_review")
            elif table == "users":
                record["status"] = "skipped"
                issues.append("legacy_credentials_not_imported_use_account_invitation")
            else:
                issues.append("legacy_table_preserved_in_snapshot_requires_mapping")
            records.append(record)
    after = digest(source)
    if before != after:
        raise ValueError("Tệp nguồn thay đổi trong lúc chạy. Không nhập dữ liệu; chạy lại khi desktop đã đóng.")
    report = {"version": 1, "mode": "dry-run", "source_sha256": before,
        "snapshot_sha256": digest(output / "source-snapshot.sqlite3"), "source_unchanged": True,
        "source_counts": {table: len(items) for table, items in rows.items()},
        "source_totals": {
            "quantity": sum(row["quantity"] for row in rows["books"] if isinstance(row["quantity"], int)),
            "available": sum(row["available"] for row in rows["books"] if isinstance(row["available"], int)),
            "recorded_fines": sum(row["fine"] for row in rows["borrowings"] if isinstance(row["fine"], int)),
            "borrowing_statuses": dict(Counter(str(row.get("status")) for row in rows["borrowings"])),
        }, "records": records, "destination_created": {"books": 0, "copies": 0, "readers": 0, "loans": 0, "payments": 0}}
    return report


def write_report(report, output):
    output = Path(output)
    for table, count in report["source_counts"].items():
        statuses = Counter(row["status"] for row in report["records"] if row["table"] == table)
        assert sum(statuses.values()) == count
    report["reconciliation"] = {table: dict(Counter(row["status"] for row in report["records"] if row["table"] == table))
                                for table in report["source_counts"]}
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    escape = lambda value: html.escape(str(value))
    labels = {
        "material_type_and_loan_mode_need_mapping": "Cần xác nhận loại tài liệu và hình thức mượn cho đầu sách.",
        "missing_or_duplicate_book_code": "Thiếu hoặc trùng mã đầu sách.",
        "invalid_inventory_totals": "Số lượng/tồn sẵn sàng không hợp lệ.",
        "invalid_book_metadata_or_policy": "Thông tin sách hoặc chính sách mượn không hợp lệ.",
        "missing_or_duplicate_reader_code": "Thiếu hoặc trùng mã độc giả.",
        "reader_type_account_link_and_membership_require_review": "Cần đối chiếu loại độc giả, tài khoản và hiệu lực/xác minh thẻ.",
        "missing_book_or_reader_reference": "Lượt mượn tham chiếu sách hoặc độc giả không tồn tại.",
        "invalid_borrow_date": "Ngày mượn thiếu hoặc không hợp lệ.",
        "invalid_due_date": "Ngày đến hạn thiếu hoặc không hợp lệ.",
        "invalid_return_date": "Ngày trả không hợp lệ hoặc trước ngày mượn.",
        "due_date_precedes_borrow_date": "Ngày đến hạn trước ngày mượn.",
        "invalid_fine_amount": "Số tiền phạt không hợp lệ.",
        "physical_copy_policy_snapshot_and_financial_evidence_require_review": "Cần đối chiếu bản vật lý, chính sách lịch sử và căn cứ tiền phạt/thu tiền.",
        "legacy_credentials_not_imported_use_account_invitation": "Không nhập tài khoản/mật khẩu cũ; cần dùng quy trình mời tài khoản.",
        "legacy_table_preserved_in_snapshot_requires_mapping": "Đã giữ nguyên trong bản sao; cần quy tắc chuyển dữ liệu riêng.",
        "destination_code_exists_not_overwritten": "Mã đã tồn tại ở đích; không ghi đè.",
    }
    lines = ["<!doctype html><html lang='vi'><meta charset='utf-8'><title>Đối soát chuyển thử SQLite</title>",
        "<style>body{font:16px Segoe UI;margin:40px;max-width:1100px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px;text-align:left}</style>",
        "<h1>Đối soát chuyển thử SQLite</h1>", "<p>Chế độ: " + escape(report["mode"]) + " · Tệp nguồn giữ nguyên.</p>",
        "<p>Snapshot chứa dữ liệu gốc, cần giữ cục bộ và không gửi/commit công khai. Báo cáo không chứa mật khẩu hoặc hồ sơ độc giả.</p>",
        "<h2>Tổng theo bảng</h2><table><tr><th>Bảng</th><th>Nguồn</th><th>Kết quả phân loại</th></tr>"]
    for table, count in report["source_counts"].items():
        lines.append(f"<tr><td>{escape(table)}</td><td>{count}</td><td>{escape(report['reconciliation'][table])}</td></tr>")
    lines += ["</table><p>ready: đủ để nhập đầu sách; review: chờ đối chiếu; skipped: không chuyển; imported: đã nhập; conflict: trùng mã đích, không ghi đè.</p>",
        "<h2>Tổng số nguồn</h2><pre>" + escape(json.dumps(report["source_totals"], ensure_ascii=False, indent=2)) + "</pre>",
        "<h2>Đã tạo ở đích</h2><pre>" + escape(report["destination_created"]) + "</pre>",
        "<h2>Danh sách bản ghi</h2><table><tr><th>Bảng</th><th>ID nguồn</th><th>Kết quả</th><th>Lý do</th></tr>"]
    for row in report["records"]:
        reason = " ".join(labels.get(issue, issue) for issue in row["issues"])
        cells = (row["table"], row["source_id"], row["status"], reason)
        lines.append("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in cells) + "</tr>")
    lines.append("</table></html>")
    (output / "report.html").write_text("\n".join(lines), encoding="utf-8")
