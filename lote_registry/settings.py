"""
Django settings for the WP4Trust trust-list onboarding app.

Defaults to SQLite for fast launch. Switch to Postgres by setting
`DATABASE_URL=postgres://user:pass@host:port/dbname` in .env.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()
]

# Path-prefix support — when this app is mounted under e.g. /onboarding/ behind nginx,
# set FORCE_SCRIPT_NAME=/onboarding so reverse() and {% url %} include the prefix.
# Empty string at dev time keeps URLs at /.
SCRIPT_NAME = os.environ.get("FORCE_SCRIPT_NAME", "")
if SCRIPT_NAME:
    FORCE_SCRIPT_NAME = SCRIPT_NAME

# Required by Django 4+ for cross-origin POSTs (login, etc.) when behind a TLS proxy.
# Without this the login form returns 403.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# nginx terminates TLS and forwards plain HTTP to this container; tell Django to
# trust the X-Forwarded-Proto / X-Forwarded-Host headers so request.is_secure()
# and absolute URLs reflect the external scheme + host, not the internal one.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "lote_registry.trustlists",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lote_registry.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lote_registry.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{DATA_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    ),
}

AUTH_USER_MODEL = "trustlists.Operator"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# STATIC_URL is NOT auto-prefixed by FORCE_SCRIPT_NAME — must be done explicitly,
# otherwise nginx routes /static/* to the wrong upstream (ms-registry).
STATIC_URL = f"{SCRIPT_NAME}/static/"
STATIC_ROOT = DATA_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth redirect targets are read as literal strings — they bypass FORCE_SCRIPT_NAME,
# so the prefix has to be baked in here too. Otherwise login redirects land outside
# the mount point (e.g. /login/ instead of /onboarding/login/).
LOGIN_URL          = f"{SCRIPT_NAME}/login/"
LOGIN_REDIRECT_URL = f"{SCRIPT_NAME}/dashboard/"
LOGOUT_REDIRECT_URL = f"{SCRIPT_NAME}/login/"

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
