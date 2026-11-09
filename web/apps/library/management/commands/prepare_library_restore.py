import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.library.backup import unpack_library_backup


class Command(BaseCommand):
    help = "Stage a verified backup in a new, empty PostgreSQL database for a maintenance cutover."

    def add_arguments(self, parser):
        parser.add_argument("--backup", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        target_url = os.environ.get("LIBRARY_RESTORE_TARGET_URL", "").strip()
        try:
            target = urlsplit(target_url)
            host = target.hostname or ""
            database = unquote(target.path.lstrip("/"))
        except ValueError:
            raise CommandError("The staging database URL is invalid.") from None
        if target.scheme not in {"postgres", "postgresql"} or not host or not database or "-pooler." in host:
            raise CommandError("Set LIBRARY_RESTORE_TARGET_URL to the direct URL of a new PostgreSQL database.")
        if parse_qs(target.query, keep_blank_values=True).keys() - {"sslmode", "channel_binding"}:
            raise CommandError("Remove connection overrides from the staging URL.")
        source = connection.settings_dict
        if connection.vendor != "postgresql":
            raise CommandError("Run this command from the application's PostgreSQL configuration.")
        if host == source["HOST"].replace("-pooler.", ".") and database == source["NAME"]:
            raise CommandError("The staging database must differ from the current application database.")
        output = Path(options["output"]).resolve()
        if any(output.is_relative_to(Path(root).resolve()) for root in (settings.MEDIA_ROOT, settings.STATIC_ROOT)):
            raise CommandError("The staging output must be outside web-served directories.")
        try:
            manifest = unpack_library_backup(options["backup"], output)
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(f"Could not validate the backup archive: {type(exc).__name__}.") from None

        env = os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE="config.restore_staging", LIBRARY_RESTORE_TARGET_URL=target_url,
                   LIBRARY_RESTORE_STAGE_DIR=str(output), PYTHONIOENCODING="utf-8")
        steps = [
            ("check empty target", ["shell", "-c", "from django.db import connection; "
                                    "raise SystemExit(1 if connection.introspection.table_names() else 0)"]),
            ("migrate", ["migrate", "--noinput"]),
            ("clear migration seed data", ["flush", "--noinput"]),
            ("load snapshot", ["loaddata", str(output / "database.json")]),
            ("verify snapshot", ["verify_library_backup", "--manifest", str(manifest),
                                  "--output", str(output / "verification.json")]),
        ]
        for label, arguments in steps:
            result = subprocess.run([sys.executable, "manage.py", *arguments], cwd=settings.BASE_DIR,
                                    env=env, capture_output=True, text=True, encoding="utf-8")
            if result.returncode:
                raise CommandError(
                    f"Staging stopped during {label}. The current database was left in place. "
                    "Use a new empty target and a new output directory for another attempt."
                )
        self.stdout.write(self.style.SUCCESS(
            "Snapshot verified. Switch the web and scheduled jobs to the staged database during maintenance."
        ))
