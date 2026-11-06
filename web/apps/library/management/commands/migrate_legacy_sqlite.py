import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.library.legacy_migration import extract, write_report
from apps.library.models import Book


class Command(BaseCommand):
    help = "Snapshot legacy SQLite read-only; report reconciliation and review issues. Optional local catalog trial."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--mapping", help="JSON containing explicit per-book material_type and loan_mode")
        parser.add_argument("--apply-catalog", action="store_true")
        parser.add_argument("--username")

    def handle(self, *args, **options):
        try:
            actor = None
            if options["apply_catalog"]:
                if connection.vendor != "sqlite":
                    raise CommandError("Chuyển thử chỉ được ghi vào SQLite cục bộ, không ghi PostgreSQL dùng chung.")
                target = Path(connection.settings_dict["NAME"]).resolve()
                if target == Path(options["source"]).resolve():
                    raise CommandError("Nguồn và đích không được là cùng tệp.")
                actor = get_user_model().objects.filter(username=options["username"], is_active=True).first()
                if not actor or not actor.has_perm("library.add_book"):
                    raise CommandError("Cần --username của tài khoản hoạt động có quyền thêm sách ở DB đích.")
            mapping = json.loads(Path(options["mapping"]).read_text(encoding="utf-8")) if options["mapping"] else {}
            report = extract(options["source"], options["output"], mapping)
            if actor:
                with transaction.atomic():
                    for row in report["records"]:
                        if row["status"] != "ready":
                            continue
                        data = row["normalized"]
                        if Book.objects.filter(catalog_number=data["catalog_number"]).exists():
                            row["status"] = "conflict"
                            row["issues"].append("destination_code_exists_not_overwritten")
                            continue
                        book = Book(**data, created_by=actor, updated_by=actor)
                        book.full_clean()
                        book.save()
                        row["status"] = "imported"
                        row["destination_id"] = book.pk
                        report["destination_created"]["books"] += 1
                    report["mode"] = "local-catalog-trial"
                    write_report(report, options["output"])
            else:
                write_report(report, options["output"])
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError("Chuyển thử không hoàn tất; không dùng kết quả làm bản nghiệm thu. " + type(exc).__name__) from exc
        self.stdout.write(self.style.SUCCESS("Created snapshot and reconciliation report: " + str(Path(options["output"]).resolve() / "report.html")))
        self.stdout.write("Unreviewed credentials, physical copies, readers, loans and payments were not imported.")
