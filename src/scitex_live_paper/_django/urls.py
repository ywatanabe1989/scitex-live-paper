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
    path("<path:endpoint>", views.api_dispatch, name="api_dispatch"),
]
