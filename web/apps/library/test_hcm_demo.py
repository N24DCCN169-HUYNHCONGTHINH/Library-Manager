import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from apps.core.models import ReaderProfile
from .hcm_demo import build_dataset, directory, export_dataset, seed_dataset
from .models import Book, BookCopy, Fine, FinePayment, LibraryBranch, Loan, Reservation, CirculationPolicy


class HCMDemoTests(TestCase):
    def setUp(self):
        call_command("setup_roles", stdout=StringIO())
        self.actor = get_user_model().objects.create_superuser("dataset-manager", "test@example.invalid", "test-pass")

    def test_export_has_sources_and_separate_synthetic_data(self):
        with TemporaryDirectory() as folder:
            with self.assertNumQueries(0):
                data = export_dataset(folder)
            self.assertEqual(data["counts"]["books"], 60)
            real = json.loads((Path(folder) / "libraries-real.json").read_text(encoding="utf-8"))
            self.assertEqual(len(real["libraries"]), 6)
            self.assertTrue(all(library["sources"] for library in real["libraries"]))
            self.assertTrue(data["synthetic"])
            self.assertTrue((Path(folder) / "index.html").exists())
            with self.assertRaises(ValidationError):
                export_dataset(folder)

    def test_seed_consistent_inventory_and_private_synthetic_readers(self):
        seed_dataset(self.actor, build_dataset())
        for model, expected in [(Book, 60), (BookCopy, 180), (ReaderProfile, 36), (Loan, 24),
                                (Reservation, 12), (Fine, 12), (FinePayment, 6), (LibraryBranch, 6)]:
            self.assertEqual(model.objects.count(), expected)
        self.assertEqual(BookCopy.objects.filter(status="on_loan").count(), Loan.objects.filter(status="open").count())
        for loan in Loan.objects.filter(status="open"):
            self.assertEqual(loan.copy.status, "on_loan")
        for reservation in Reservation.objects.filter(status="ready"):
            self.assertEqual(reservation.copy.status, "on_hold")
        for profile in ReaderProfile.objects.select_related("user"):
            self.assertFalse(profile.user.has_usable_password())
            self.assertFalse(profile.user.is_staff)
            self.assertTrue(profile.user.email.endswith("@example.invalid"))
            self.assertEqual(list(profile.user.groups.values_list("name", flat=True)), ["reader"])
        self.assertEqual(sum(fine.balance for fine in Fine.objects.all()), 24000)

    def test_existing_records_are_preserved_and_reseed_is_rejected(self):
        old = Book.objects.create(catalog_number="EXISTING", title="Keep", created_by=self.actor, updated_by=self.actor)
        seed_dataset(self.actor, build_dataset())
        with self.assertRaises(ValidationError):
            seed_dataset(self.actor, build_dataset())
        old.refresh_from_db()
        self.assertEqual(old.title, "Keep")
        self.assertEqual(Book.objects.count(), 61)

    def test_failed_seed_rolls_back_everything(self):
        with patch("apps.library.hcm_demo.Loan.objects.create", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                seed_dataset(self.actor, build_dataset())
        self.assertEqual(Book.objects.count(), 0)
        self.assertEqual(ReaderProfile.objects.count(), 0)
        self.assertEqual(LibraryBranch.objects.count(), 0)
        self.assertEqual(CirculationPolicy.objects.count(), 0)

    def test_reader_cannot_seed(self):
        user = get_user_model().objects.create_user("reader-only")
        with self.assertRaises(ValidationError):
            seed_dataset(user, build_dataset())
