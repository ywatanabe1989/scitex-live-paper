"""M2 re-verify endpoints — single (``api/claim/verify``) + bulk (``api/claims/verify``).

Both call ``scitex_clew.verify_claim(claim_id_or_location)`` — a single
positional argument — and read the nested ``result["claim"]["status"]``
that clew returns.

clew is git-agnostic: ``verify_claim`` re-hashes the claim's source file
against the CURRENT on-disk state of clew's project (it resolves its DB
via ``SCITEX_CLEW_DB_PATH`` or by walking up to
``.scitex/clew/runtime/db.sqlite``). It does NOT take a commit and does
NOT check out git. ``pinned_commit`` is therefore METADATA only here —
to re-verify against a specific commit, the host/deployment is
responsible for checking out that commit and pointing clew's DB via
``SCITEX_CLEW_DB_PATH`` before serving. These handlers never mutate the
working tree.

Boundary unchanged: ``scitex-clew`` owns the claim model + the verify
operation. These handlers are thin pass-throughs. When ``scitex-clew``
is not installed the response degrades gracefully — the operator's
SPA button surfaces a clear "not available" status rather than a 500,
so the badge stays meaningful even on a base install.

The bulk endpoint shares the same fallback / error envelope per
result, so the SPA's "Re-verify all" button can stream per-claim
status updates as the response comes back.
"""

from __future__ import annotations

import json
import logging
from importlib import import_module
from typing import Any, List, Mapping, Optional

from django.http import HttpResponse, JsonResponse

from ..services import get_request_bundle_state

logger = logging.getLogger(__name__)

__all__ = ["handle_reverify", "handle_reverify_all"]


def handle_reverify(request) -> HttpResponse:
    """Re-verify a single claim via clew's live ``verify_claim``.

    live-paper verifies the claim against the CURRENT on-disk state of
    clew's project. To re-verify against a specific commit, the
    host/deployment is responsible for checking out ``pinned_commit``
    and pointing clew's DB via ``SCITEX_CLEW_DB_PATH`` before serving.
    This handler never mutates the working tree — ``pinned_commit`` is
    accepted and echoed back as ``verified_against`` metadata only, and
    is NOT passed to ``verify_claim``.

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
            "verified_against": "<commit>",               # metadata echo
            "status": "verified" | "partial" | "mismatch" | "missing",
            "verified_at": "<ISO-8601>" | null,           # from claim
            "details": {...}                              # source_verified,
                                                           # chain_verified,
                                                           # details list +
                                                           # rest of claim
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
    # Install scitex-clew via the ``[clew]`` optional extra:
    #   pip install scitex-live-paper[clew]
    try:
        clew = import_module("scitex_clew")
    except ImportError:
        logger.info(
            "[re-verify] scitex-clew not installed — degrading claim %s to stale "
            "(install scitex-live-paper[clew] for live re-verify)",
            claim_id,
        )
        return JsonResponse(
            {
                "ok": False,
                "claim_id": claim_id,
                "status": "stale",
                "reason": "scitex-clew not installed (install scitex-live-paper[clew])",
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
        # clew takes a SINGLE positional arg and verifies against the
        # current on-disk state. pinned_commit is metadata only — the
        # host owns checkout + SCITEX_CLEW_DB_PATH (see module docstring).
        result = verify_claim(claim_id)
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

    clew's real success shape nests the claim under ``result["claim"]``
    (with ``status`` + ``verified_at`` inside it) alongside top-level
    ``source_verified`` / ``chain_verified`` / ``details``. The
    not-found shape is a flat ``{"status": "not_found", "message": ...}``
    with NO ``"claim"`` key.

    Forward-compatible: any extra keys clew returns flow through under
    ``details`` rather than being merged into the top level, so adding
    fields upstream never silently changes the contract this endpoint
    promises. ``verified_against`` is the ``pinned_commit`` metadata
    echo — clew is git-agnostic and never receives it.
    """
    if isinstance(result, dict) and "claim" in result:
        claim = result["claim"]
        if not isinstance(claim, dict):
            claim = {}
        status = str(claim.get("status", ""))
        verified_at = claim.get("verified_at")
        # details = every top-level key except "claim", plus every claim
        # key except the two we promote (status/verified_at). Keep
        # unknown keys for forward-compat.
        details: dict = {k: v for k, v in result.items() if k != "claim"}
        details.update(
            {k: v for k, v in claim.items() if k not in {"status", "verified_at"}}
        )
        return {
            "ok": True,
            "claim_id": claim_id,
            "verified_against": pinned_commit,
            "status": status,
            "verified_at": verified_at,
            "details": details,
        }

    if isinstance(result, dict) and "status" in result:
        # not_found case: flat dict, no "claim" key.
        return {
            "ok": False,
            "claim_id": claim_id,
            "verified_against": pinned_commit,
            "status": str(result.get("status")),
            "verified_at": None,
            "details": result.get("message"),
        }

    # Non-dict (e.g. an enum/dataclass from an old clew). Stringify.
    return {
        "ok": True,
        "claim_id": claim_id,
        "verified_against": pinned_commit,
        "status": str(result),
        "verified_at": None,
        "details": {},
    }


# ──────────────────────────────────────────────────────────────────
# Bulk: ``api/claims/verify``
# ──────────────────────────────────────────────────────────────────


def handle_reverify_all(request) -> HttpResponse:
    """Re-verify every claim in the bundle (or a subset) via clew.

    live-paper verifies each claim against the CURRENT on-disk state of
    clew's project. To re-verify against a specific commit, the
    host/deployment is responsible for checking out ``pinned_commit``
    and pointing clew's DB via ``SCITEX_CLEW_DB_PATH`` before serving.
    This handler never mutates the working tree — ``pinned_commit`` is
    accepted and echoed back as ``verified_against`` metadata only, and
    is NOT passed to ``verify_claim``.

    Request
    -------
    ``POST /api/claims/verify``
    Body (JSON; all keys optional)::

        {
            "claim_ids":     ["claim_a", "claim_b", ...]   # filter; omit = all
            "pinned_commit": "<sha>"                       # override for all
        }

    Response
    --------
    ::

        {
            "ok": true | false,
            "verified_against": "<sha>",
            "count": <int>,                  # number of results below
            "results": [
                { ...same envelope as api/claim/verify... },
                ...
            ]
        }

    Top-level ``ok`` is True iff EVERY per-claim result succeeded
    (``result.ok == true``). One fallback or error result flips it to
    False so the SPA can flag the overall sweep as incomplete.

    Errors:

    - Non-POST → 405
    - Body present but not a JSON object → 400
    - ``claim_ids`` present but not a list of strings → 400
    - No pinned_commit anywhere → 400
    - No claims to verify (filter empty after intersection with bundle) → 400

    Per-claim failures (clew raise / unknown claim_id) are folded into
    the per-result envelope with ``ok=false`` — they do NOT 500 the
    bulk call, so a single bad claim doesn't kill the sweep.
    """
    if request.method != "POST":
        return JsonResponse(
            {"error": "method not allowed; POST a JSON body"},
            status=405,
        )

    body = _parse_json_body(request)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return JsonResponse(
            {"error": "request body must be a JSON object"},
            status=400,
        )

    claim_ids_raw = body.get("claim_ids")
    claim_ids_filter: Optional[List[str]]
    if claim_ids_raw is None:
        claim_ids_filter = None
    elif isinstance(claim_ids_raw, list) and all(
        isinstance(x, str) and x.strip() for x in claim_ids_raw
    ):
        claim_ids_filter = list(claim_ids_raw)
    else:
        return JsonResponse(
            {"error": "'claim_ids' must be a list of non-empty strings"},
            status=400,
        )

    state = get_request_bundle_state(request)
    bundle = state.bundle

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

    # Resolve which claims to verify.
    bundle_ids = [c.claim_id for c in bundle.claims]
    if claim_ids_filter is None:
        target_ids = bundle_ids
    else:
        bundle_id_set = set(bundle_ids)
        target_ids = [cid for cid in claim_ids_filter if cid in bundle_id_set]
        # Unknown ids are reported per-result rather than failing the call,
        # so the SPA can show "missing" without losing the other results.
        missing = [cid for cid in claim_ids_filter if cid not in bundle_id_set]
    if not target_ids and (claim_ids_filter is None or not claim_ids_filter):
        return JsonResponse(
            {"error": "bundle has no claims to verify"},
            status=400,
        )

    # Probe clew ONCE up-front; share the fallback decision across the
    # whole sweep so we don't import + raise + log N times.
    clew, clew_fallback_reason = _probe_clew()

    results: List[Mapping[str, Any]] = []
    all_ok = True

    if claim_ids_filter is not None:
        for missing_id in missing:  # noqa: F821 — defined in the else branch above
            results.append(
                {
                    "ok": False,
                    "claim_id": missing_id,
                    "status": "unknown",
                    "reason": "claim_id not found in bundle",
                }
            )
            all_ok = False

    for claim_id in target_ids:
        if clew is None:
            results.append(
                {
                    "ok": False,
                    "claim_id": claim_id,
                    "status": "stale",
                    "reason": clew_fallback_reason,
                    "fallback": True,
                }
            )
            all_ok = False
            continue

        try:
            # SINGLE positional arg; pinned_commit is metadata only.
            raw = clew.verify_claim(claim_id)
            envelope = _normalize_result(claim_id, pinned_commit, raw)
            results.append(envelope)
            # A resolved-but-not_found claim normalizes to ok=False; it
            # must flip the overall sweep to incomplete.
            if not envelope.get("ok", False):
                all_ok = False
        except Exception as exc:
            logger.exception(
                "[re-verify-all] clew.verify_claim raised for %s", claim_id,
            )
            results.append(
                {
                    "ok": False,
                    "claim_id": claim_id,
                    "error": str(exc),
                }
            )
            all_ok = False

    return JsonResponse(
        {
            "ok": all_ok,
            "verified_against": pinned_commit,
            "count": len(results),
            "results": results,
        }
    )


def _probe_clew() -> tuple[Optional[Any], str]:
    """Try to import scitex_clew + locate verify_claim. Returns (module|None, reason).

    Reason strings name the ``[clew]`` extra so the operator can copy
    the install command straight out of the SPA badge / curl output.
    """
    try:
        clew = import_module("scitex_clew")
    except ImportError:
        return None, "scitex-clew not installed (install scitex-live-paper[clew])"
    verify_claim = getattr(clew, "verify_claim", None)
    if not callable(verify_claim):
        return None, "scitex-clew has no verify_claim() — version skew"
    return clew, ""
