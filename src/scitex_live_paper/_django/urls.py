"""URL patterns for the live-paper Django app.

Two routes — the SPA shell at the app root and a catch-all
``<path:endpoint>`` that delegates into the ``HANDLERS`` registry. This
mirrors ``scitex_writer._django.urls`` so the hub mount in M3 stays a
one-line ``include()``.
"""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "live_paper"

urlpatterns = [
    path("", views.viewer_page, name="viewer_page"),
    # M5 foundational slice — canonical DOI URL surface. MUST appear
    # before the `<path:endpoint>` catch-all so DOI hits don't fall
    # through to `api_dispatch`. The `path:` converter allows DOI
    # suffixes with slashes (e.g. `10.1000/foo.bar/v2`).
    path("doi/<path:doi>/", views.doi_landing, name="doi_landing"),
    path("<path:endpoint>", views.api_dispatch, name="api_dispatch"),
]
