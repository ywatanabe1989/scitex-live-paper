"""``api/dashboard`` — single round-trip boot payload for the SPA.

Combines what the SPA was previously assembling out of three calls
(``bundle-info`` + ``claims`` + the re-review badge nested under
bundle-info) into one response. Saves two HTTP round-trips on every
viewer boot, which materially affects perceived load latency on the
hub-mounted multi-tenant deployment where the resolver may be doing
DB lookups per request.

The shape is the union of the existing handlers' outputs — no new
fields. Each sub-handler is reused so the dashboard can never drift
from the underlying contracts:

- ``bundle`` → from `core.bundle_info`
- ``claims`` → from `claims.handle_claims`

Existing endpoints stay reachable; nothing about ``bundle-info`` /
``claims`` / ``re_review_badge`` changes. The dashboard endpoint is
additive — old SPA bundles keep working unchanged.
"""

from __future__ import annotations

from typing import Any, Mapping

from .claims import handle_claims
from .core import bundle_info

__all__ = ["handle_dashboard"]


def handle_dashboard(request) -> Mapping[str, Any]:
    """Return the merged ``bundle-info`` + ``claims`` boot payload.

    Response shape::

        {
          "bundle": { ...same shape as api/bundle-info... },
          "claims": { ...same shape as api/claims... }
        }

    Re-review badge lives under ``bundle.re_review_badge`` (unchanged
    from the bundle-info shape). The SPA reads everything from one
    payload + skips the two follow-up fetches.
    """
    return {
        "bundle": bundle_info(request),
        "claims": handle_claims(request),
    }
