"""``api/claims`` — list of claims for the SPA sidebar.

Returns the bundle's claim list in JSON form so the SPA's claims
sidebar (M2 Re-verify button surface) doesn't have to round-trip
through ``bundle-info``'s catch-all summary. Mirrors what the
static-site claims renderer (``_renderer/claims.py``) emits, but
through the live Django mount + ``request.live_paper_context``
(PR #27) so multi-tenant hub deployments work without per-handler
branching.

Schema ownership boundary unchanged: this handler is a thin
projection of ``bundle.claims`` (which is itself a mirror of
``scitex_clew.Claim``). We do NOT re-document or extend the claim
schema.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..services import get_request_bundle_state

__all__ = ["handle_claims"]


def handle_claims(request) -> Mapping[str, Any]:
    """Return the bundle's claim list + paper-state re-verify flags.

    Response shape::

        {
          "claim_count": <int>,
          "re_verify_enabled": <bool>,        # from PaperState — gates the
                                              # Re-verify button visibility
          "pinned_commit": <str | null>,      # what re-verify pins against
          "claims": [
            {
              "claim_id":      "...",
              "file_path":     "...",
              "claim_type":    "figure" | "statistic" | "value" | "...",
              "claim_value":   "..." | null,
              "line_number":   <int> | null,
              "status":        "registered" | "verified" | "stale" | "contradicted",
              "source_session": "..." | null,
              "source_file":   "..." | null,
              "source_hash":   "..." | null,
              "registered_at": "..." | null,
              "verified_at":   "..." | null,
              "extras":        {...}          # forward-compat passthrough
            },
            ...
          ]
        }

    Forward-compatible: ``extras`` is the same passthrough slot
    ``bundle.Claim`` uses for unknown fields. The SPA shows what it
    understands and ignores the rest.
    """
    state = get_request_bundle_state(request)
    bundle = state.bundle

    return {
        "claim_count": len(bundle.claims),
        "re_verify_enabled": bundle.paper_state.re_verify_enabled,
        "pinned_commit": bundle.paper_state.pinned_commit,
        "claims": [
            {
                "claim_id": c.claim_id,
                "file_path": c.file_path,
                "claim_type": c.claim_type,
                "claim_value": c.claim_value,
                "line_number": c.line_number,
                "status": c.status,
                "source_session": c.source_session,
                "source_file": c.source_file,
                "source_hash": c.source_hash,
                "registered_at": c.registered_at,
                "verified_at": c.verified_at,
                "extras": c.extras,
            }
            for c in bundle.claims
        ],
    }
