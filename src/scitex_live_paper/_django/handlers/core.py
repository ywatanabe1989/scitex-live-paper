"""Core handlers — ``ping`` and ``bundle-info``.

Both return plain mappings; the dispatcher wraps them in ``JsonResponse``.

``bundle_info`` goes through :func:`scitex_live_paper._django.services.get_bundle_state`,
which goes through ``scitex_live_paper.bundle.load()``. The handler does
not parse ``claims.json`` directly — that would re-document the upstream
clew schema, which is the one thing this package must never do.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..services import get_bundle_state


def ping(request) -> Mapping[str, Any]:
    """Liveness probe.

    Used by the SPA shell at boot to confirm the API base is reachable.
    """
    return {"ok": True, "app": "scitex-live-paper"}


def bundle_info(request) -> Mapping[str, Any]:
    """Summary of the bundle pinned by ``SCITEX_LIVE_PAPER_BUNDLE``.

    Returns:

    - ``claim_count`` — number of claims in ``claims.json``
    - ``schema`` — the ``"schema"`` key carried by ``claims.json``
      (owned by ``scitex-clew``; mirrored here, never validated)
    - ``manuscript`` — filename of ``manuscript.pdf`` or ``.tex``
    - ``dag_present`` — whether ``dag.mmd`` was non-empty
    - ``bundle_path`` — resolved absolute path of the loaded bundle
    - ``paper_state`` — render-time lifecycle metadata: ``stage``,
      ``header_label``, ``journal``, ``doi``, ``accepted_at``,
      ``pinned_commit``, ``show_verification_badge``,
      ``re_verify_enabled``. Drives the embed-mode SPA chrome.
    """
    state = get_bundle_state()
    bundle = state.bundle
    manuscript_name = (
        bundle.manuscript_path.name
        if bundle.manuscript_path is not None
        else None
    )
    ps = bundle.paper_state
    return {
        "claim_count": state.claim_count,
        "schema": bundle.schema_version,
        "manuscript": manuscript_name,
        "dag_present": bool(bundle.dag.strip()),
        "bundle_path": str(state.bundle_path),
        "paper_state": {
            "stage": ps.stage,
            "header_label": ps.header_label(),
            "journal": ps.journal,
            "doi": ps.doi,
            "accepted_at": ps.accepted_at,
            "pinned_commit": ps.pinned_commit,
            "show_verification_badge": ps.show_verification_badge,
            "re_verify_enabled": ps.re_verify_enabled,
        },
    }
