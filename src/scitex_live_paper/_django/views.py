"""Views for the live-paper Django app.

Two surfaces:

- ``viewer_page`` — renders the SPA shell template with a ``data-api-base``
  attribute the frontend reads at boot.
- ``api_dispatch`` — single catch-all that looks the ``endpoint`` up in
  the ``HANDLERS`` registry. Unknown endpoints → JSON 404.

Handlers take ``(request)`` and return a JSON-serialisable mapping, which
this dispatcher wraps in a ``JsonResponse``. The bundle they read is
pinned per-process by ``SCITEX_LIVE_PAPER_BUNDLE`` env (set by
``_server.serve``) and cached behind ``services.get_bundle_state``.

The whole shape mirrors ``scitex_writer._django`` (which mirrors
``figrecipe._django``): one SPA shell + one dispatcher + a HANDLERS dict.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt

from .handlers import HANDLERS

logger = logging.getLogger(__name__)

# Surfaces the handlers are allowed to return. ``HttpResponse`` instances
# pass through untouched; mappings get wrapped in ``JsonResponse``.
HandlerReturn = Any
HandlerFn = Callable[..., HandlerReturn]


def viewer_page(request) -> HttpResponse:
    """Render the SPA shell.

    The shell carries ``data-api-base="/api/"`` on the root element so the
    same template works both under the standalone server (root mount) and
    under the hub mount (``/viewer-v2/`` prefix, served via ``include()``).
    """
    html = render_to_string(
        "live_paper/viewer.html",
        {"api_base": "api/"},
        request=request,
    )
    return HttpResponse(html)


@csrf_exempt
def api_dispatch(request, endpoint: str) -> HttpResponse:
    """Dispatch ``GET /<endpoint>`` (and POST) to the matching handler.

    Returns a clean JSON 404 when the endpoint is not registered — this
    keeps the unknown-endpoint contract explicit so the M2 / M3 wiring
    can rely on it.
    """
    handler: HandlerFn | None = HANDLERS.get(endpoint)
    if handler is None:
        return JsonResponse(
            {"error": f"unknown endpoint: {endpoint}"},
            status=404,
        )

    try:
        payload = handler(request)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("[live-paper] handler %s raised", endpoint)
        return JsonResponse({"error": str(exc)}, status=500)

    if isinstance(payload, HttpResponse):
        return payload
    return JsonResponse(payload)


def _read_body_json(request) -> Mapping[str, Any]:
    """Lenient body parser exposed for handlers that need POST input.

    Unused by the M1 skeleton's two handlers, but the contract lives here
    so M2 handlers (which DO take body input) inherit a stable shape.
    """
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return {}
