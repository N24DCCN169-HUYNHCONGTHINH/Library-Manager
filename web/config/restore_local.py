"""Isolated restore rehearsal. Never inherits remote database URLs."""
import os
from pathlib import Path

target = os.environ.get("LIBRARY_RESTORE_DB")
if not target:
    raise RuntimeError("LIBRARY_RESTORE_DB is required")
os.environ["DJANGO_DEBUG"] = "True"
os.environ["DB_ENGINE"] = "sqlite"
os.environ["DJANGO_DB_USE_UNPOOLED"] = "0"
for key in ("LIBRARY_APP_DATABASE_URL", "LIBRARY_MIGRATOR_DATABASE_URL", "DATABASE_URL", "DATABASE_URL_UNPOOLED"):
    os.environ[key] = " "
os.environ["DJANGO_EMAIL_BACKEND"] = "django.core.mail.backends.locmem.EmailBackend"
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": Path(target).resolve()}}
MEDIA_ROOT = Path(target).resolve().parent / "media"
