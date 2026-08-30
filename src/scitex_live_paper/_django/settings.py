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

# No database at all. live-paper has no models of its own and every handler
# reads the bundle off disk or delegates to scitex-clew, which owns its own
# store. Django accepts an empty mapping and installs its dummy backend, so
# any accidental ORM call fails loudly here instead of silently succeeding
# against a scratch database that nothing else would ever read.
DATABASES: dict[str, dict[str, str]] = {}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATICFILES_DIRS: list[str] = [str(BASE_DIR / "static")]
