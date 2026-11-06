"""Local HTTPS rehearsal: real secure cookies, no outbound email or public listeners."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[2]
target = os.environ.get("LIBRARY_HTTPS_DB")
if not target or not Path(target).is_file():
    raise RuntimeError("LIBRARY_HTTPS_DB must point to the isolated restored SQLite database")
key_path = root / "work" / "day10" / "local-https.key"
key_path.parent.mkdir(parents=True, exist_ok=True)
try:
    with key_path.open("x", encoding="utf-8") as stream:
        stream.write(secrets.token_urlsafe(48))
except FileExistsError:
    pass
os.environ["DJANGO_SECRET_KEY"] = key_path.read_text(encoding="utf-8").strip()
os.environ["DJANGO_DEBUG"] = "False"
os.environ["DB_ENGINE"] = "sqlite"
os.environ["DJANGO_DB_USE_UNPOOLED"] = "0"
for key in ("LIBRARY_APP_DATABASE_URL", "LIBRARY_MIGRATOR_DATABASE_URL", "DATABASE_URL", "DATABASE_URL_UNPOOLED"):
    os.environ[key] = " "
os.environ["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
os.environ["DJANGO_CSRF_TRUSTED_ORIGINS"] = "https://localhost:9443"
os.environ["DJANGO_EMAIL_BACKEND"] = "django.core.mail.backends.locmem.EmailBackend"
os.environ["EMAIL_HOST"] = "localhost"
os.environ["DEFAULT_FROM_EMAIL"] = "demo@example.invalid"
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": Path(target).resolve()}}
MEDIA_ROOT = Path(target).resolve().parent / "media"
SESSION_COOKIE_NAME = "library_local_https_session"
CSRF_COOKIE_NAME = "library_local_https_csrf"
# Local rehearsal intentionally does not set long-lived HSTS for localhost.
SECURE_HSTS_SECONDS = 0
