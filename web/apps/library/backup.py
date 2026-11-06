import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone


EXCLUDED = ["contenttypes", "auth.permission", "sessions", "axes"]


def fingerprint(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_fixture(records):
    result = []
    for record in records:
        record = json.loads(json.dumps(record))
        model = apps.get_model(record["model"])
        for field in model._meta.many_to_many:
            if field.name in record["fields"]:
                record["fields"][field.name].sort(key=lambda value: json.dumps(value, sort_keys=True))
        result.append(record)
    result.sort(key=lambda record: (record["model"], str(record.get("pk"))))
    return hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def export_fixture(path):
    with Path(path).open("w", encoding="utf-8") as stream:
        call_command("dumpdata", exclude=EXCLUDED, use_natural_foreign_keys=True,
                     use_base_manager=True, stdout=stream, verbosity=0)


def create_backup(output, media_root=None):
    if connection.vendor == "postgresql" and connection.in_atomic_block:
        raise ValueError("PostgreSQL backup must start outside an existing transaction")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Backup destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    media_root = Path(media_root or settings.MEDIA_ROOT).resolve()
    if output.is_relative_to(media_root):
        raise ValueError("Backup must be outside MEDIA_ROOT")
    with TemporaryDirectory() as folder:
        fixture = Path(folder) / "database.json"
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            export_fixture(fixture)
        records = json.loads(fixture.read_text(encoding="utf-8"))
        labels = sorted({record["model"] for record in records})
        manifest = {"format": "library-logical-backup-v1", "created_at": timezone.now().isoformat(),
            "django_version": django.get_version(), "excluded": EXCLUDED,
            "counts": {label: sum(record["model"] == label for record in records) for label in labels},
            "fixture_semantic_sha256": canonical_fixture(records), "files": {"database.json": fingerprint(fixture)}}
        created = False
        try:
            archive = ZipFile(output, "x", compression=ZIP_DEFLATED)
            created = True
            with archive:
                archive.write(fixture, "database.json")
                if media_root.exists():
                    for path in sorted(media_root.rglob("*")):
                        if path.is_symlink() or not path.resolve().is_relative_to(media_root):
                            raise ValueError("Media symlinks are not supported")
                        if path.is_file():
                            name = "media/" + path.relative_to(media_root).as_posix()
                            archive.write(path, name)
                            manifest["files"][name] = fingerprint(path)
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        except Exception:
            # Delete only the new archive created by this operation, never an existing backup.
            if created:
                output.unlink(missing_ok=True)
            raise
    return manifest


def restore_rehearsal(backup, output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Restore output must be a new or empty directory")
    with ZipFile(backup) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "library-logical-backup-v1" or "database.json" not in manifest.get("files", {}):
            raise ValueError("Unsupported backup format")
        if manifest.get("django_version") != django.get_version():
            raise ValueError("Use the same Django version as the backup for this rehearsal")
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("Duplicate archive paths")
        for name, expected in manifest["files"].items():
            target = (output / name).resolve()
            if not target.is_relative_to(output) or not (name == "database.json" or name.startswith("media/")):
                raise ValueError("Unsafe archive path")
            with archive.open(name) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise ValueError("Backup checksum mismatch")
        output.mkdir(parents=True, exist_ok=True)
        for name in manifest["files"]:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("xb") as destination:
                import shutil
                shutil.copyfileobj(source, destination)
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    env = os.environ.copy()
    env.update(DJANGO_SETTINGS_MODULE="config.restore_local", LIBRARY_RESTORE_DB=str(output / "restored.sqlite3"),
               DJANGO_SECRET_KEY=secrets.token_urlsafe(48), PYTHONIOENCODING="utf-8")
    # Remove data-migration defaults from this NEW isolated database before
    # loading the exact snapshot. Never flush the source/application database.
    commands = [["migrate", "--noinput"], ["flush", "--noinput"], ["loaddata", str(output / "database.json")],
                ["verify_library_backup", "--manifest", str(manifest_path), "--output", str(output / "verification.json")]]
    for arguments in commands:
        result = subprocess.run([sys.executable, "manage.py", *arguments], cwd=settings.BASE_DIR,
                                env=env, capture_output=True, text=True, encoding="utf-8")
        if result.returncode:
            (output / "restore-error.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            raise ValueError("Restore rehearsal failed; see local restore-error.log")
    return json.loads((output / "verification.json").read_text(encoding="utf-8"))
