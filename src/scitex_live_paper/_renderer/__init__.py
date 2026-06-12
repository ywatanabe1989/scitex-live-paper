"""HTML renderers for `scitex-live-paper` (M1).

This subpackage emits the static surfaces consumed by the M1 viewer:

  - :mod:`scitex_live_paper._renderer.viewer` — PDF.js page + anchor overlay.
  - :mod:`scitex_live_paper._renderer.claims` — claims sidebar list + per-claim panel.
  - :mod:`scitex_live_paper._renderer.dag` — mermaid DAG navigator + click-to-claim.

Assets are vendored in :mod:`scitex_live_paper._renderer.assets` so the
generated site has **no CDN dependency**.
"""

from __future__ import annotations

from . import claims, dag, viewer
from .claims import render_claims_sidebar
from .dag import render_dag
from .viewer import render_viewer

__all__ = [
    "claims",
    "dag",
    "viewer",
    "render_claims_sidebar",
    "render_dag",
    "render_viewer",
]
