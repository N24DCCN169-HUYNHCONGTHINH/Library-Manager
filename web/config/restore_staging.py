"""Dedicated PostgreSQL configuration for staging a recovery snapshot."""
import os
from pathlib import Path

target = os.environ["LIBRARY_RESTORE_TARGET_URL"]
os.environ["LIBRARY_APP_DATABASE_URL"] = target
os.environ["DJANGO_DB_USE_UNPOOLED"] = "0"
from .settings import *  # noqa: E402,F403

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = Path(os.environ["LIBRARY_RESTORE_STAGE_DIR"]) / "media"
