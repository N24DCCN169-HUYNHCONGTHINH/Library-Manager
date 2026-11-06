"""Explicit opt-in PostgreSQL QA endpoint. Never inherits the live URL."""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values

if len(sys.argv) < 2 or sys.argv[1] != "test":
    raise ImproperlyConfigured("config.qa is restricted to manage.py test; do not use it to serve the application")
root = Path(__file__).resolve().parents[2]
values = dotenv_values(root / "web" / ".env.qa.local")
qa_url = (values.get("LIBRARY_QA_DATABASE_URL") or "").strip()
parsed = urlparse(qa_url)
expected_host = "ep-cool-sea-a127a2za.ap-southeast-1.aws.neon.tech"
if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname != expected_host or parsed.path != "/neondb":
    raise ImproperlyConfigured("QA URL must use the confirmed direct QA endpoint and neondb")
for filename in (root / ".env.local", root / "web" / ".env"):
    live = dotenv_values(filename)
    for key in ("LIBRARY_APP_DATABASE_URL", "LIBRARY_MIGRATOR_DATABASE_URL", "DATABASE_URL", "DATABASE_URL_UNPOOLED"):
        live_host = urlparse(live.get(key) or "").hostname
        if live_host and live_host.replace("-pooler", "") == expected_host:
            raise ImproperlyConfigured("Refusing QA: endpoint matches a live configuration")
os.environ.update(DJANGO_DEBUG="True", DJANGO_SECRET_KEY="qa-test-only-not-for-serving-public-traffic-918267",
                  DJANGO_DB_USE_UNPOOLED="0", LIBRARY_APP_DATABASE_URL=qa_url,
                  LIBRARY_MIGRATOR_DATABASE_URL=" ", DATABASE_URL=" ", DATABASE_URL_UNPOOLED=" ",
                  DJANGO_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
from .settings import *  # noqa: E402,F403

DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
DATABASES["default"]["TEST"] = {"NAME": "test_library_day11"}  # noqa: F405
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
