"""HTML renderers for `scitex-live-paper` (M1).

This subpackage emits the static surfaces consumed by the M1 viewer:

  - :mod:`scitex_live_paper._renderer.viewer` — PDF.js page + anchor overlay.
  - :mod:`scitex_live_paper._renderer.claims` — claims sidebar list + per-claim panel.
  - (later milestones) :mod:`...dag`.

Assets are vendored in :mod:`scitex_live_paper._renderer.assets` so the
generated site has **no CDN dependency**.
"""

from __future__ import annotations

from . import claims, viewer
from .claims import render_claims_sidebar, render_html
from .viewer import render_viewer

__all__ = [
    "claims",
    "viewer",
    "render_claims_sidebar",
    "render_html",
    "render_viewer",
]
