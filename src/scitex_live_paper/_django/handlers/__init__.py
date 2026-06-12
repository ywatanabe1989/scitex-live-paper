"""Handler registry for the live-paper SPA dispatcher.

The ``HANDLERS`` mapping is the *single source of truth* for what the
``<path:endpoint>`` catch-all in ``views.api_dispatch`` will route.

M1 ships two core handlers (``ping``, ``bundle-info``). M2 will add the
claim re-verify endpoint (``api/claim/<id>/verify``) — extend this dict
when those land; do NOT inline endpoint logic in ``views.py``.
"""

from __future__ import annotations

from typing import Callable, Dict

from .core import bundle_info, ping

HandlerFn = Callable[..., object]

# fmt: off
HANDLERS: Dict[str, HandlerFn] = {
    "api/ping":         ping,
    "api/bundle-info":  bundle_info,
}
# fmt: on

__all__ = ["HANDLERS", "ping", "bundle_info"]
