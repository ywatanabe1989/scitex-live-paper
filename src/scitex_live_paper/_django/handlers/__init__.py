"""Handler registry for the live-paper SPA dispatcher.

The ``HANDLERS`` mapping is the *single source of truth* for what the
``<path:endpoint>`` catch-all in ``views.api_dispatch`` will route.

- ``api/ping``         — liveness probe
- ``api/bundle-info``  — bundle summary + paper_state
- ``api/claims``       — full claim list + re_verify_enabled flag (SPA sidebar)
- ``api/pdf``          — bundle manuscript PDF bytes (ported from
                         ``scitex_writer/_django/handlers/compile.py:handle_pdf``;
                         see ``docs/research/writer-pdf-viewer-findings.md``)
- ``api/claim/verify`` — M2 re-verify endpoint (calls ``scitex_clew.verify_claim``
                         against ``bundle.paper_state.pinned_commit``;
                         degrades gracefully when clew is not installed)

Extend this dict when new endpoints land; do NOT inline endpoint
logic in ``views.py``.
"""

from __future__ import annotations

from typing import Callable, Dict

from .claims import handle_claims
from .core import bundle_info, ping
from .pdf import handle_pdf
from .reverify import handle_reverify

HandlerFn = Callable[..., object]

# fmt: off
HANDLERS: Dict[str, HandlerFn] = {
    "api/ping":          ping,
    "api/bundle-info":   bundle_info,
    "api/claims":        handle_claims,
    "api/pdf":           handle_pdf,
    "api/claim/verify":  handle_reverify,
}
# fmt: on

__all__ = [
    "HANDLERS",
    "ping",
    "bundle_info",
    "handle_claims",
    "handle_pdf",
    "handle_reverify",
]
