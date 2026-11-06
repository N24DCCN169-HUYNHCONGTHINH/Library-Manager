"""Render deployment behind its managed HTTPS edge."""
import os
os.environ.setdefault("DJANGO_EMAIL_BACKEND", "apps.core.email_backend.ResendEmailBackend")
from django.core.exceptions import ImproperlyConfigured
from .production import *  # noqa: F403

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise ImproperlyConfigured("Render requires persistent PostgreSQL, not SQLite.")

import os
import re

# Render's assigned URL must work before custom-domain DNS is configured.
render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
if render_host:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.onrender\.com", render_host):
        raise ImproperlyConfigured("Invalid Render hostname.")
    ALLOWED_HOSTS = list(ALLOWED_HOSTS)  # noqa: F405
    CSRF_TRUSTED_ORIGINS = list(CSRF_TRUSTED_ORIGINS)  # noqa: F405
    if render_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_host)
    origin = "https://" + render_host
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
if EMAIL_BACKEND != "apps.core.email_backend.ResendEmailBackend" or not RESEND_API_KEY:  # noqa: F405
    raise ImproperlyConfigured("Render requires the Resend HTTPS backend and RESEND_API_KEY.")
