"""Minimal Django settings for the standalone live-paper server.

Used by ``_server.serve`` and ``tests/django/`` so the Django app boots
without a parent project. Hub-side mount in M3 ignores this file — the
hub injects its own settings and uses ``_standalone_urls`` only as a
last-resort dev entry.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "scitex-live-paper-standalone-dev-key-not-for-production",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0", "testserver"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "scitex_live_paper._django",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "scitex_live_paper._django._standalone_urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# No DATABASES entry on purpose. This skeleton declares no models and no
# migrations, and never opens a connection, so Django's own empty default
# is the honest configuration — declaring a database here would announce a
# dependency the app does not have. A host project that mounts these views
# supplies its own database settings.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATICFILES_DIRS: list[str] = [str(BASE_DIR / "static")]
