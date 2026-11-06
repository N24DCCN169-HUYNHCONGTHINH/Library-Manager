from contextlib import closing
import hashlib
import json
import sqlite3
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.db import connection

from .models import Book


class LegacyMigrationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "legacy.db"
        self.output = self.root / "result"
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript('''
                CREATE TABLE books(id INTEGER, code TEXT, title TEXT, author TEXT, quantity INTEGER, available INTEGER, year INTEGER);
                INSERT INTO books VALUES(1, 'OLD-1', 'Sách cũ', 'Tác giả', 3, 2, 2020);
                CREATE TABLE readers(id INTEGER, code TEXT, name TEXT);
                INSERT INTO readers VALUES(1, 'RD-1', 'PRIVATE-READER-NAME');
                CREATE TABLE borrowings(id INTEGER, book_id INTEGER, reader_id INTEGER, borrow_date TEXT, due_date TEXT, return_date TEXT, fine INTEGER, status TEXT);
                INSERT INTO borrowings VALUES(1, 1, 1, '2026-01-01', '2026-01-15', NULL, 1000, 'Borrowed');
                CREATE TABLE users(id INTEGER, username TEXT, password TEXT);
                INSERT INTO users VALUES(1, 'PRIVATE-USERNAME', 'PRIVATE-PASSWORD');
                CREATE TABLE fine_payments(id INTEGER, amount INTEGER);
                INSERT INTO fine_payments VALUES(1, 500);
            ''')
        self.mapping = self.root / "mapping.json"
        self.mapping.write_text(json.dumps({"books": {"OLD-1": {"material_type": "general", "loan_mode": "home_loan"}}}), encoding="utf-8")

    def run_command(self, **options):
        call_command("migrate_legacy_sqlite", source=str(self.source), output=str(self.output), stdout=StringIO(), **options)
        return json.loads((self.output / "report.json").read_text(encoding="utf-8"))

    def test_dry_run_keeps_source_and_destination_unchanged(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        report = self.run_command()
        self.assertEqual(before, hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(Book.objects.count(), 0)
        self.assertEqual(report["source_totals"]["quantity"], 3)
        self.assertEqual(report["source_totals"]["recorded_fines"], 1000)
        for table, count in report["source_counts"].items():
            self.assertEqual(sum(report["reconciliation"][table].values()), count)
        with closing(sqlite3.connect(self.output / "source-snapshot.sqlite3")) as db:
            self.assertEqual(db.execute("select count(*) from books").fetchone()[0], 1)
            self.assertEqual(db.execute("select amount from fine_payments").fetchone()[0], 500)

    def test_reports_exclude_credentials_and_reader_personal_data(self):
        self.run_command()
        for filename in ("report.json", "report.html"):
            text = (self.output / filename).read_text(encoding="utf-8")
            for secret in ("PRIVATE-PASSWORD", "PRIVATE-USERNAME", "PRIVATE-READER-NAME"):
                self.assertNotIn(secret, text)

    def test_explicit_mapping_makes_only_book_ready(self):
        report = self.run_command(mapping=str(self.mapping))
        self.assertEqual(report["reconciliation"]["books"], {"ready": 1})
        self.assertEqual(report["reconciliation"]["readers"], {"review": 1})
        self.assertEqual(report["destination_created"]["books"], 0)

    def test_dry_run_never_queries_destination_database(self):
        with self.assertNumQueries(0):
            self.run_command(mapping=str(self.mapping))

    def test_invalid_inventory_dates_references_and_money_are_reported(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("update books set available=4")
            db.execute("update borrowings set reader_id=999, due_date='bad', fine=-1")
        report = self.run_command(mapping=str(self.mapping))
        issues = [issue for row in report["records"] for issue in row["issues"]]
        for issue in ("invalid_inventory_totals", "missing_book_or_reader_reference", "invalid_due_date", "invalid_fine_amount"):
            self.assertIn(issue, issues)

    def test_duplicate_codes_and_invalid_policy_are_quarantined(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("insert into books values(2, 'OLD-1', 'Other', '', 1, 1, 2020)")
        self.mapping.write_text(json.dumps({"books": {"OLD-1": {"material_type": "rare", "loan_mode": "home_loan"}}}), encoding="utf-8")
        report = self.run_command(mapping=str(self.mapping))
        self.assertEqual(report["reconciliation"]["books"], {"review": 2})
        self.assertTrue(all("missing_or_duplicate_book_code" in row["issues"] for row in report["records"] if row["table"] == "books"))

    def test_existing_output_is_never_overwritten(self):
        self.run_command()
        before = (self.output / "report.json").read_bytes()
        with self.assertRaises(CommandError):
            self.run_command()
        self.assertEqual(before, (self.output / "report.json").read_bytes())

    def test_missing_or_unsupported_source_rejected(self):
        self.source.unlink()
        with self.assertRaises(CommandError):
            self.run_command()
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("create table books(id integer)")
        with self.assertRaises(CommandError):
            self.run_command()

    @skipUnless(connection.vendor == "sqlite", "The catalog import feature deliberately writes only to local SQLite")
    def test_local_import_is_inactive_and_repeat_does_not_overwrite(self):
        actor = get_user_model().objects.create_superuser("importer", "importer@example.invalid", "test-pass")
        report = self.run_command(mapping=str(self.mapping), apply_catalog=True, username=actor.username)
        book = Book.objects.get(catalog_number="OLD-1")
        self.assertFalse(book.is_active)
        self.assertEqual(book.copies.count(), 0)
        self.assertEqual(report["destination_created"]["books"], 1)
        self.output = self.root / "second"
        report = self.run_command(mapping=str(self.mapping), apply_catalog=True, username=actor.username)
        self.assertEqual(report["reconciliation"]["books"], {"conflict": 1})
        self.assertEqual(Book.objects.count(), 1)

    def test_import_requires_permission_and_rejects_postgres(self):
        user = get_user_model().objects.create_user("reader")
        with self.assertRaises(CommandError):
            self.run_command(mapping=str(self.mapping), apply_catalog=True, username=user.username)
        with patch("apps.library.management.commands.migrate_legacy_sqlite.connection.vendor", "postgresql"):
            with self.assertRaises(CommandError):
                self.run_command(apply_catalog=True)

    @skipUnless(connection.vendor == "sqlite", "The catalog import feature deliberately writes only to local SQLite")
    def test_report_failure_rolls_back_import(self):
        user = get_user_model().objects.create_superuser("importer", "importer@example.invalid", "test-pass")
        with patch("apps.library.management.commands.migrate_legacy_sqlite.write_report", side_effect=OSError("disk full")):
            with self.assertRaises(CommandError):
                self.run_command(mapping=str(self.mapping), apply_catalog=True, username=user.username)
        self.assertEqual(Book.objects.count(), 0)
