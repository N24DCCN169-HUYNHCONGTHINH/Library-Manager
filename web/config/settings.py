from pathlib import Path
import os
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
# Neon CLI writes branch credentials at the repository root when no root .env exists.
load_dotenv(BASE_DIR.parent / ".env.local", override=False)

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in {"1", "true", "yes"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.startswith("replace-with-") or SECRET_KEY == "development-only-change-me":
    if DEBUG:
        SECRET_KEY = "development-only-change-me"
    else:
        raise ImproperlyConfigured("Set a unique DJANGO_SECRET_KEY outside debug mode.")
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

INSTALLED_APPS = [
    "config.admin.LibraryAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "axes",
    "apps.core",
    "apps.library",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.core.middleware.RequirePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.core.context_processors.library_roles",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Lock out only the username/IP pair to avoid blocking every user behind a shared campus IP.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_USE_ATTEMPT_EXPIRATION = True
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_RETRY_AFTER_HEADER = True

database_url = os.getenv("LIBRARY_APP_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
if os.getenv("DJANGO_DB_USE_UNPOOLED", "").lower() in {"1", "true", "yes"}:
    database_url = os.getenv("LIBRARY_MIGRATOR_DATABASE_URL", "").strip() or os.getenv(
        "DATABASE_URL_UNPOOLED", database_url
    ).strip()

if database_url:
    from urllib.parse import parse_qs, unquote, urlparse

    parsed_database_url = urlparse(database_url)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use the postgres:// or postgresql:// scheme.")
    db_options = {key: values[-1] for key, values in parse_qs(parsed_database_url.query).items()}
    db_host = parsed_database_url.hostname or ""
    sslmode = os.getenv("DB_SSLMODE", db_options.get("sslmode", "verify-full")).strip()
    if db_host.lower() not in {"localhost", "127.0.0.1", "::1"} and sslmode not in {"verify-full", "verify-ca"}:
        # Neon URLs may specify sslmode=require; keep certificate and hostname verification enabled.
        if sslmode in {"", "prefer", "require"}:
            sslmode = "verify-full"
        else:
            raise ImproperlyConfigured("Remote PostgreSQL requires DB_SSLMODE=verify-full (or verify-ca).")
    db_options["sslmode"] = sslmode
    sslrootcert = os.getenv("DB_SSLROOTCERT", "").strip()
    if sslrootcert:
        db_options["sslrootcert"] = sslrootcert
    elif sslmode in {"verify-full", "verify-ca"}:
        # Use Mozilla's maintained CA bundle instead of a machine-specific libpq root.crt.
        import certifi

        db_options["sslrootcert"] = certifi.where()
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed_database_url.path.lstrip("/")),
        "USER": unquote(parsed_database_url.username or ""),
        "PASSWORD": unquote(parsed_database_url.password or ""),
        "HOST": db_host,
        "PORT": str(parsed_database_url.port or 5432),
        "CONN_MAX_AGE": 60,
        "OPTIONS": db_options,
    }}
elif os.getenv("DB_ENGINE", "sqlite").lower() == "postgres":
    db_options = {}
    sslmode = os.getenv("DB_SSLMODE", "prefer").strip()
    db_host = os.getenv("DB_HOST", "127.0.0.1").strip().lower()
    if db_host not in {"localhost", "127.0.0.1", "::1"} and sslmode not in {"verify-full", "verify-ca"}:
        raise ImproperlyConfigured("Remote PostgreSQL requires DB_SSLMODE=verify-full (or verify-ca), including shared development databases.")
    if sslmode:
        db_options["sslmode"] = sslmode
    sslrootcert = os.getenv("DB_SSLROOTCERT", "").strip()
    if sslrootcert:
        db_options["sslrootcert"] = sslrootcert
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "library_manager"),
        "USER": os.getenv("DB_USER", "library_app"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": db_host,
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": db_options,
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

if DEBUG:
    EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
else:
    EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        raise ImproperlyConfigured("Do not use the console email backend outside debug mode.")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost" if DEBUG else "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@library.local")
if not DEBUG and (not EMAIL_HOST or DEFAULT_FROM_EMAIL.endswith(".local")):
    raise ImproperlyConfigured("Configure a real EMAIL_HOST and DEFAULT_FROM_EMAIL outside debug mode.")
PASSWORD_RESET_TIMEOUT = 60 * 60
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_AGE", "28800"))
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Enable these behind HTTPS in production configuration.
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "True").lower() in {"1", "true", "yes"}
    SECURE_REFERRER_POLICY = "same-origin"
