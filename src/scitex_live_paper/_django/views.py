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


# Truthy query-string values for ``?embed=...``. Anything outside this set
# (or absence of the param) leaves the standalone chrome in place.
_EMBED_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _is_embed_mode(request) -> bool:
    """Whether the request asks for the chrome-less embed shell.

    Selection lever for PR #3: query string ``?embed=1`` (also accepts
    ``true`` / ``yes`` / ``on``, case-insensitive). PR #2's
    ``mount(resolver=...)`` middleware will additionally let hosts set
    ``BundleContext.options.embed_mode=True`` to flip the same switch
    without needing a query string.
    """
    raw = request.GET.get("embed")
    if raw is None:
        return False
    return raw.strip().lower() in _EMBED_TRUTHY


def viewer_page(request) -> HttpResponse:
    """Render the SPA shell.

    Two template variants:

    - ``live_paper/viewer.html`` — full standalone page with header
      chrome (subtitle, scitex-clew boundary callout, status pre block).
      Used by ``scitex-live-paper serve`` when the operator hits it
      directly from a browser.
    - ``live_paper/viewer_embed.html`` — minimal page with no chrome,
      just the ``#live-paper-root`` div + assets. Used when host apps
      (hub project view, writer preview, scholar) iframe the viewer
      into their own page. Selected when ``?embed=1`` is on the URL.

    Both variants carry ``data-api-base`` on the root element so the
    SPA boots identically; the embed shell additionally sets
    ``data-embed-mode="1"`` so the JS can suppress any in-app chrome
    a host doesn't want.
    """
    template = (
        "live_paper/viewer_embed.html"
        if _is_embed_mode(request)
        else "live_paper/viewer.html"
    )
    html = render_to_string(
        template,
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
        if isinstance(payload, HttpResponse):
            return payload
        if not isinstance(payload, Mapping):
            # Loud, named error — never let a handler quietly return a
            # list/None/str and have the operator chase a bare TypeError
            # from deep inside django.http.response.
            raise TypeError(
                f"handler for {endpoint!r} must return a Mapping or "
                f"HttpResponse, got {type(payload).__name__}"
            )
        return JsonResponse(payload)
    except Exception as exc:
        logger.exception("[live-paper] handler %s raised", endpoint)
        return JsonResponse({"error": str(exc)}, status=500)


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
