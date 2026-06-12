"""HTML renderers for `scitex-live-paper` (M1).

This subpackage emits the static surfaces consumed by the M1 viewer:

  - :mod:`scitex_live_paper._renderer.viewer` — PDF.js page + anchor overlay.
  - (later milestones) :mod:`...claims`, :mod:`...dag`.

Assets are vendored in :mod:`scitex_live_paper._renderer.assets` so the
generated site has **no CDN dependency**.
"""

from __future__ import annotations

from . import viewer
from .viewer import render_viewer

__all__ = ["viewer", "render_viewer"]
