import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from apps.library.backup import canonical_fixture, export_fixture


class Command(BaseCommand):
    help = "Compare a restored isolated SQLite database against a logical backup manifest."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        if connection.vendor != "sqlite" and settings.SETTINGS_MODULE != "config.restore_staging":
            raise CommandError("Verification requires an isolated restore database.")
        manifest = json.loads(Path(options["manifest"]).read_text(encoding="utf-8"))
        with TemporaryDirectory() as folder:
            fixture = Path(folder) / "actual.json"
            export_fixture(fixture)
            records = json.loads(fixture.read_text(encoding="utf-8"))
        counts = {label: sum(record["model"] == label for record in records) for label in {row["model"] for row in records}}
        fk_errors = []
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_key_check")
                fk_errors = cursor.fetchall()
        else:
            connection.check_constraints()
        result = {"verified": counts == manifest["counts"] and not fk_errors
            and canonical_fixture(records) == manifest["fixture_semantic_sha256"],
            "counts": counts, "foreign_key_errors": len(fk_errors)}
        Path(options["output"]).write_text(json.dumps(result, indent=2), encoding="utf-8")
        if not result["verified"]:
            raise CommandError("Restored data does not match manifest")
        self.stdout.write("Counts, application data and foreign keys verified.")
