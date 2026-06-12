"""Handler registry for the live-paper SPA dispatcher.

The ``HANDLERS`` mapping is the *single source of truth* for what the
``<path:endpoint>`` catch-all in ``views.api_dispatch`` will route.

- ``api/ping``        — liveness probe
- ``api/bundle-info`` — bundle summary + paper_state
- ``api/pdf``         — bundle manuscript PDF bytes (ported from
                        ``scitex_writer/_django/handlers/compile.py:handle_pdf``;
                        see ``docs/research/writer-pdf-viewer-findings.md``)

M2 will add the claim re-verify endpoint (``api/claim/<id>/verify``) —
extend this dict when those land; do NOT inline endpoint logic in
``views.py``.
"""

from __future__ import annotations

from typing import Callable, Dict

from .core import bundle_info, ping
from .pdf import handle_pdf

HandlerFn = Callable[..., object]

# fmt: off
HANDLERS: Dict[str, HandlerFn] = {
    "api/ping":         ping,
    "api/bundle-info":  bundle_info,
    "api/pdf":          handle_pdf,
}
# fmt: on

__all__ = ["HANDLERS", "ping", "bundle_info", "handle_pdf"]
