from io import StringIO
import django
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase
from django_otp.plugins.otp_totp.models import TOTPDevice

from .backup import create_backup, restore_rehearsal


class BackupTests(TransactionTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.user = get_user_model().objects.create_user("backup-reader", password="test-password")

    def test_backup_has_manifest_integrity_and_excludes_sessions(self):
        path = self.root / "backup.zip"
        manifest = create_backup(path)
        self.assertIn("auth.user", manifest["counts"])
        self.assertNotIn("sessions.session", manifest["counts"])
        with ZipFile(path) as archive:
            self.assertIn("database.json", archive.namelist())
            self.assertNotIn(".env", archive.namelist())
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            create_backup(path)
        self.assertEqual(before, path.read_bytes())

    def test_full_restore_preserves_security_profile_totp_and_media(self):
        call_command("setup_roles", stdout=StringIO())
        from .models import CirculationMutex
        CirculationMutex.objects.all().delete()
        # An ID gap exposes post_save receivers that incorrectly run during loaddata.
        type(self.user.security_profile).objects.filter(user=self.user).update(id=999)
        TOTPDevice.objects.create(user=self.user, confirmed=True)
        media = self.root / "media"
        media.mkdir()
        (media / "cover.txt").write_text("synthetic cover", encoding="utf-8")
        backup = self.root / "backup.zip"
        create_backup(backup, media)
        try:
            result = restore_rehearsal(backup, self.root / "restored")
        except ValueError:
            # This fixture contains only synthetic accounts, safe for test diagnostics.
            self.fail((self.root / "restored/restore-error.log").read_text(encoding="utf-8"))
        self.assertTrue(result["verified"])
        self.assertEqual(result["foreign_key_errors"], 0)
        self.assertEqual((self.root / "restored/media/cover.txt").read_text(encoding="utf-8"), "synthetic cover")
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_modified_archive_is_rejected_before_restore(self):
        backup = self.root / "backup.zip"
        create_backup(backup)
        changed = self.root / "changed.zip"
        with ZipFile(backup) as old, ZipFile(changed, "x") as new:
            for name in old.namelist():
                new.writestr(name, b"[]" if name == "database.json" else old.read(name))
        with self.assertRaisesMessage(ValueError, "checksum"):
            restore_rehearsal(changed, self.root / "restored")
        self.assertFalse((self.root / "restored").exists())

    def test_path_traversal_is_rejected(self):
        backup = self.root / "unsafe.zip"
        with ZipFile(backup, "x") as archive:
            archive.writestr("manifest.json", json.dumps({"format": "library-logical-backup-v1", "django_version": django.get_version(), "files": {
                "database.json": hashlib.sha256(b"[]").hexdigest(), "../escape.txt": "unused"}}))
            archive.writestr("database.json", "[]")
        with self.assertRaises(ValueError):
            restore_rehearsal(backup, self.root / "restored")
        self.assertFalse((self.root / "escape.txt").exists())

    def test_existing_restore_destination_is_preserved(self):
        folder = self.root / "existing"
        folder.mkdir()
        (folder / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            restore_rehearsal(self.root / "missing.zip", folder)
        self.assertEqual((folder / "keep.txt").read_text(), "keep")
