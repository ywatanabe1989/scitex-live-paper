"""Django ``AppConfig`` for the live-paper viewer (mirrors ``scitex_writer._django``).

If ``scitex-app`` is installed, subclass its ``ScitexAppConfig`` so the
hub-side manifest registry picks the app up automatically. Otherwise we
fall back to vanilla ``django.apps.AppConfig`` — the skeleton must still
boot in a standalone Django process without scitex-app installed.
"""

from __future__ import annotations

try:
    from scitex_app._django import ScitexAppConfig  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised when scitex-app absent
    from django.apps import AppConfig as ScitexAppConfig


class LivePaperConfig(ScitexAppConfig):
    """Live-paper viewer Django app.

    The manifest slug ``live-paper`` is what ``scitex-hub`` will look up
    when mounting this app under ``/viewer-v2/`` in M3.
    """

    name = "scitex_live_paper._django"
    label = "scitex_live_paper"
    verbose_name = "SciTeX Live Paper Viewer"
