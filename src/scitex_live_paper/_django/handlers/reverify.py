"""``api/claim/verify`` — M2 re-verify endpoint.

Calls ``scitex_clew.verify_claim()`` against the bundle's pinned
commit and returns the resulting :class:`~scitex_clew.VerificationStatus`.
This is the first M2 surface — M1 is the read-only renderer; M2 is the
live re-verify button. The verification badge UI (PR #26) is already
wired against `re_verify_enabled`; this handler is the backend it calls.

Boundary unchanged: ``scitex-clew`` owns the claim model + the verify
operation. This handler is a thin pass-through. When ``scitex-clew``
is not installed the response degrades gracefully — the operator's
SPA button surfaces a clear "not available" status rather than a 500,
so the badge stays meaningful even on a base install.
"""

from __future__ import annotations

import json
import logging
from importlib import import_module
from typing import Any, Mapping, Optional

from django.http import HttpResponse, JsonResponse

from ..services import get_request_bundle_state

logger = logging.getLogger(__name__)

__all__ = ["handle_reverify"]


def handle_reverify(request) -> HttpResponse:
    """Re-verify a single claim against the bundle's pinned commit.

    Request
    -------
    ``POST /api/claim/verify``
    Body (JSON)::

        {
            "claim_id":      "claim_a1b2c3d4e5f6",        # required
            "pinned_commit": "deadbeefcafef00d12345678"   # optional;
                                                           # defaults to
                                                           # bundle.paper_state.pinned_commit
        }

    Response
    --------
    On success (``scitex-clew`` available + commit pin available)::

        {
            "ok": true,
            "claim_id": "...",
            "verified_against": "<commit>",
            "status": "verified" | "stale" | "contradicted",
            "verified_at": "<ISO-8601>",
            "details": {...}                              # passes through
                                                           # what clew returns
        }

    On graceful degradation (``scitex-clew`` not installed)::

        {
            "ok": false,
            "claim_id": "...",
            "status": "stale",
            "reason": "scitex-clew not installed",
            "fallback": true
        }

    Error cases:

    - Non-POST → 405 with ``{"error": "method not allowed"}``
    - Missing / non-mapping body → 400
    - Missing ``claim_id`` → 400
    - No pinned_commit anywhere (body + bundle.paper_state both empty) → 400
    - ``clew.verify_claim()`` raised → 500 with the exception message
    """
    if request.method != "POST":
        return JsonResponse(
            {"error": "method not allowed; POST a JSON body"},
            status=405,
        )

    body = _parse_json_body(request)
    if not isinstance(body, dict):
        return JsonResponse(
            {"error": "request body must be a JSON object"},
            status=400,
        )

    claim_id = body.get("claim_id")
    if not isinstance(claim_id, str) or not claim_id.strip():
        return JsonResponse(
            {"error": "'claim_id' is required and must be a non-empty string"},
            status=400,
        )

    state = get_request_bundle_state(request)
    bundle = state.bundle

    # Resolve pinned_commit: body wins, then bundle.paper_state.
    pinned_commit: Optional[str] = body.get("pinned_commit")
    if not isinstance(pinned_commit, str) or not pinned_commit.strip():
        pinned_commit = bundle.paper_state.pinned_commit
    if not pinned_commit:
        return JsonResponse(
            {
                "error": (
                    "no pinned_commit available — pass one in the body or "
                    "set bundle.paper_state.pinned_commit via state.yaml"
                )
            },
            status=400,
        )

    # Try the real upstream ``scitex-clew`` call. If the package isn't
    # installed, degrade gracefully with an explicit reason so the SPA
    # can keep the badge meaningful instead of showing a 500.
    try:
        clew = import_module("scitex_clew")
    except ImportError:
        logger.info(
            "[re-verify] scitex-clew not installed — degrading claim %s to stale",
            claim_id,
        )
        return JsonResponse(
            {
                "ok": False,
                "claim_id": claim_id,
                "status": "stale",
                "reason": "scitex-clew not installed",
                "fallback": True,
            }
        )

    verify_claim = getattr(clew, "verify_claim", None)
    if not callable(verify_claim):
        # Defensive: an old/partial clew install without the verify
        # entry point — surface the same shape as the no-install path.
        logger.warning(
            "[re-verify] scitex_clew installed but missing verify_claim()",
        )
        return JsonResponse(
            {
                "ok": False,
                "claim_id": claim_id,
                "status": "stale",
                "reason": "scitex-clew has no verify_claim() — version skew",
                "fallback": True,
            }
        )

    try:
        result = verify_claim(
            claim_id=claim_id,
            against=pinned_commit,
            bundle_root=str(bundle.root),
        )
    except Exception as exc:
        logger.exception("[re-verify] clew.verify_claim raised for %s", claim_id)
        return JsonResponse(
            {
                "ok": False,
                "claim_id": claim_id,
                "error": str(exc),
            },
            status=500,
        )

    return JsonResponse(_normalize_result(claim_id, pinned_commit, result))


def _parse_json_body(request) -> Any:
    """Lenient JSON body parser. Returns ``None`` on empty / malformed."""
    if not request.body:
        return None
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return None


def _normalize_result(
    claim_id: str,
    pinned_commit: str,
    result: Any,
) -> Mapping[str, Any]:
    """Shape clew's return value into our stable response envelope.

    Forward-compatible: any extra keys clew returns flow through under
    ``details`` rather than being merged into the top level, so adding
    fields upstream never silently changes the contract this endpoint
    promises.
    """
    if not isinstance(result, dict):
        # Some clew versions may return a dataclass / enum. Stringify.
        return {
            "ok": True,
            "claim_id": claim_id,
            "verified_against": pinned_commit,
            "status": str(result),
            "details": {},
        }

    return {
        "ok": True,
        "claim_id": claim_id,
        "verified_against": pinned_commit,
        "status": str(result.get("status", "")),
        "verified_at": result.get("verified_at"),
        "details": {
            k: v
            for k, v in result.items()
            if k not in {"status", "verified_at"}
        },
    }
