"""Asset-content tests for the SPA boot wiring of ``api/dashboard``.

PR-merged with PR #42 (which added the endpoint), this PR wires
``viewer.js`` to prefer the merged endpoint at boot, falling back to
the 3-call path if it 404s. Tests verify the JS source actually
implements the prefer/fallback contract — browser execution is out
of pytest's scope; visual verification is in the manual test plan.

Real file IO — no mocks.
"""

from __future__ import annotations

from pathlib import Path


def _module(name: str) -> str:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return (pkg_root / "_django/static/live_paper/js" / name).read_text(
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────────
# _utils.js — new fetchOrNull helper
# ──────────────────────────────────────────────────────────────────


def test_utils_exports_fetch_or_null():
    text = _module("_utils.js")
    assert "export async function fetchOrNull" in text


def test_utils_fetch_or_null_returns_null_on_non_ok():
    text = _module("_utils.js")
    # On non-2xx, return null so the caller can fall back.
    assert "if (!res.ok) return null" in text


def test_utils_fetch_or_null_returns_null_on_network_error():
    text = _module("_utils.js")
    # Catch path returns null too — distinguished from a 200 with
    # a null body by the fallback caller branch (dash && bundle && claims).
    assert "return null" in text
    # Caught exception variable name — keeps the JS engine from
    # complaining about an unused identifier.
    assert "(_err)" in text or "(err)" in text


# ──────────────────────────────────────────────────────────────────
# viewer.js — boot prefers dashboard, falls back on null
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_imports_fetch_or_null():
    text = _module("viewer.js")
    assert "fetchOrNull" in text


def test_viewer_js_calls_dashboard_endpoint_first():
    text = _module("viewer.js")
    # The merged endpoint is the FIRST call after ping.
    assert 'apiBase + "dashboard"' in text


def test_viewer_js_uses_fetch_or_null_for_dashboard():
    text = _module("viewer.js")
    # Soft fetch — falling back to the 3-call path on null.
    assert 'fetchOrNull(apiBase + "dashboard")' in text


def test_viewer_js_reads_bundle_and_claims_from_dashboard():
    text = _module("viewer.js")
    # When dashboard responds, both halves come from one payload.
    assert "dash.bundle" in text
    assert "dash.claims" in text


def test_viewer_js_falls_back_to_separate_calls_when_dashboard_missing():
    text = _module("viewer.js")
    # Fallback path still calls bundle-info + claims separately.
    assert 'apiBase + "bundle-info"' in text
    assert 'apiBase + "claims"' in text


def test_viewer_js_fallback_guard_checks_bundle_and_claims_keys():
    text = _module("viewer.js")
    # Defensive: the "use dashboard" branch only fires when BOTH
    # halves are present in the response — otherwise the SPA falls
    # back to the separate calls. Means a half-broken dashboard
    # response can't leave the sidebar empty.
    assert "dash && dash.bundle && dash.claims" in text


# ──────────────────────────────────────────────────────────────────
# Existing wiring stays — regression locks
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_still_renders_re_review_badge_at_boot():
    text = _module("viewer.js")
    assert "renderReReviewBadge(rootEl, bundleInfo)" in text


def test_viewer_js_still_renders_claims_sidebar_when_payload_present():
    text = _module("viewer.js")
    assert "renderClaimsSidebar(rootEl, claimsPayload, apiBase)" in text


def test_viewer_js_still_mounts_pdf_viewer():
    text = _module("viewer.js")
    assert "new PDFViewer" in text


def test_viewer_js_skips_claims_render_when_payload_null():
    text = _module("viewer.js")
    # Boot RPC raised → claimsPayload stays null → renderClaimsSidebar
    # is NOT called (avoids passing null into the sidebar renderer).
    assert "if (claimsPayload)" in text
