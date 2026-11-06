"""Template settings for a future server behind a loopback-only TLS proxy."""
import os
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403

if DEBUG or "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("Production requires DEBUG=False and explicit ALLOWED_HOSTS")
if not CSRF_TRUSTED_ORIGINS or any(not url.startswith("https://") for url in CSRF_TRUSTED_ORIGINS):  # noqa: F405
    raise ImproperlyConfigured("Configure HTTPS CSRF origins for the actual hostname")
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
