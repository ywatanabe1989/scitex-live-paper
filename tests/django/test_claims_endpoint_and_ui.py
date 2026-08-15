"""No-mocks tests for M2 follow-up — api/claims endpoint + SPA UI.

Two layers:

1. **Backend**: `api/claims` returns claim list + paper_state flags
   the SPA needs to render a Re-verify-button-aware sidebar.
2. **Frontend (asset-content level)**: viewer.js wires the sidebar +
   POST to /api/claim/verify on Re-verify button click; viewer.css
   ships the per-status colour palette.

Real Django test Client + real bundle fixtures + real file IO. No
``monkeypatch``, no ``mock.patch``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("django")

from django.test import Client  # noqa: E402

from scitex_live_paper._django import services  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"  # preprint, re_verify_enabled=False
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"  # accepted, re_verify_enabled=True


@pytest.fixture
def env_snapshot() -> Iterator[None]:
    snap = dict(os.environ)
    try:
        yield
    finally:
        for key in list(os.environ):
            if key not in snap:
                del os.environ[key]
        for key, value in snap.items():
            os.environ[key] = value


@pytest.fixture
def client() -> Client:
    return Client()


def _pin(path: Path) -> None:
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(path)
    services.clear_cache()


# ──────────────────────────────────────────────────────────────────
# Backend: api/claims
# ──────────────────────────────────────────────────────────────────


def test_api_claims_returns_200(client, env_snapshot):
    _pin(BUNDLE_MIN)
    assert client.get("/api/claims").status_code == 200


def test_api_claims_returns_claim_count(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/claims").content)
    # bundle-min ships exactly three claims
    assert body["claim_count"] == 3


def test_api_claims_returns_claims_array_of_correct_length(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/claims").content)
    assert isinstance(body["claims"], list)
    assert len(body["claims"]) == 3


def test_api_claims_carries_re_verify_enabled_false_for_preprint(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/claims").content)
    # bundle-min has no state.yaml → preprint default → no badge → no re-verify
    assert body["re_verify_enabled"] is False
    assert body["pinned_commit"] is None


def test_api_claims_carries_re_verify_enabled_true_for_accepted(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/claims").content)
    # bundle-accepted has stage=accepted + pinned_commit → re_verify True
    assert body["re_verify_enabled"] is True
    assert body["pinned_commit"] == "deadbeefcafef00d12345678"


def test_api_claims_each_claim_has_required_fields(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/claims").content)
    required = {"claim_id", "file_path", "claim_type", "status", "extras"}
    for claim in body["claims"]:
        missing = required - set(claim.keys())
        assert not missing, f"claim missing fields: {missing}"


def test_api_claims_preserves_clew_status_strings(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/claims").content)
    statuses = sorted(c["status"] for c in body["claims"])
    # bundle-min fixture: registered / suspect / verified (clew v1.3
    # vocabulary — the fixture mirrors what clew actually emits)
    assert statuses == ["registered", "suspect", "verified"]


def test_api_claims_carries_extras_for_forward_compat(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/claims").content)
    # bundle-min's claims carry an "anchor" extra field
    found_extras = any(c["extras"] for c in body["claims"])
    assert found_extras


def test_handlers_registry_includes_api_claims():
    from scitex_live_paper._django.handlers import HANDLERS, handle_claims

    assert HANDLERS["api/claims"] is handle_claims


# ──────────────────────────────────────────────────────────────────
# Frontend asset content — viewer.js wires the sidebar + button
# ──────────────────────────────────────────────────────────────────


def _viewer_js() -> str:
    """Concatenated text of every JS module under live_paper/js/."""
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    js_dir = pkg_root / "_django/static/live_paper/js"
    return "\n".join(
        (js_dir / name).read_text(encoding="utf-8")
        for name in (
            "viewer.js",
            "pdf-viewer.js",
            "claims-sidebar.js",
            "reverify-all.js",
            "_utils.js",
        )
    )


def _viewer_css() -> str:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return (pkg_root / "_django/static/live_paper/css/viewer.css").read_text(
        encoding="utf-8",
    )


def test_viewer_js_fetches_api_claims_at_boot():
    text = _viewer_js()
    # The boot path fetches `apiBase + "claims"` after bundle-info
    assert 'apiBase + "claims"' in text


def test_viewer_js_has_render_claims_sidebar():
    text = _viewer_js()
    assert "renderClaimsSidebar" in text


def test_viewer_js_has_render_claim_row():
    text = _viewer_js()
    assert "renderClaimRow" in text


def test_viewer_js_has_reverify_claim_handler():
    text = _viewer_js()
    assert "reverifyClaim" in text


def test_viewer_js_re_verify_visibility_gated_on_re_verify_enabled():
    text = _viewer_js()
    # The button is only appended `if (reVerifyEnabled)` — drafts /
    # preprints get a row without a button
    assert "if (reVerifyEnabled)" in text


def test_viewer_js_reverify_posts_to_claim_verify():
    text = _viewer_js()
    # The fetch call POSTs to `apiBase + "claim/verify"` (matches the
    # handler registered as HANDLERS["api/claim/verify"]).
    assert 'apiBase + "claim/verify"' in text
    assert '"POST"' in text or "'POST'" in text


def test_viewer_js_reverify_sends_json_body_with_claim_id():
    text = _viewer_js()
    assert "claim_id: claimId" in text
    assert "JSON.stringify(body)" in text


def test_viewer_js_reverify_passes_pinned_commit_when_present():
    text = _viewer_js()
    # When the api/claims payload carried a pinned_commit, send it back
    # in the POST body so the handler doesn't have to fall back to
    # bundle.paper_state (avoids a race when the operator passed an
    # override in the response).
    assert "body.pinned_commit = pinnedCommit" in text


def test_viewer_js_reverify_handles_fallback_envelope():
    text = _viewer_js()
    # PR #31's degradation path returns 200 + fallback=true; UI must
    # render the status (stale by default) without treating it as an
    # error
    assert "payload.fallback === true" in text


def test_viewer_js_reverify_shows_verifying_state_on_click():
    text = _viewer_js()
    # The button text flips to "Verifying…" + the badge to "verifying"
    # so the operator sees feedback even on slow networks
    assert "Verifying" in text
    assert '"verifying"' in text


def test_viewer_js_reverify_writes_status_back_to_data_attribute():
    text = _viewer_js()
    # `rowEl.dataset.status = nextStatus` + the badge's data-status
    # drive the per-status CSS border + background.
    assert "rowEl.dataset.status" in text
    assert "statusBadge.dataset.status" in text


def test_viewer_js_reverify_handles_network_error():
    text = _viewer_js()
    # Network failure (offline / DNS) must surface as "error" status,
    # NOT silently swallow.
    assert "network error" in text


def test_viewer_js_reverify_re_enables_button_in_finally():
    text = _viewer_js()
    # Button stays clickable after an error so the operator can retry
    assert "btn.disabled = false" in text


def test_viewer_js_sidebar_uses_aside_element():
    text = _viewer_js()
    # Semantic HTML — the sidebar is an <aside>, not a div, so AT users
    # land on it as a complementary region.
    assert "createElement(\"aside\")" in text


def test_viewer_js_sidebar_mount_id_is_live_paper_claims():
    text = _viewer_js()
    assert '"live-paper-claims"' in text


# ──────────────────────────────────────────────────────────────────
# CSS — per-status palette + the sidebar shape
# ──────────────────────────────────────────────────────────────────


def test_viewer_css_defines_status_colour_custom_properties():
    text = _viewer_css()
    for var in (
        # clew claim-status vocabulary (verify_claim / claims.json)
        "--lp-status-verified",
        "--lp-status-suspect",
        "--lp-status-mismatch",
        "--lp-status-missing",
        "--lp-status-registered",
        "--lp-status-not_found",
        # transient client-side UI states
        "--lp-status-error",
        "--lp-status-verifying",
        # M4 re-review badge vocabulary (separate, paper-level)
        "--lp-status-stale",
        "--lp-status-contradicted",
    ):
        assert var in text, f"missing CSS custom property: {var}"


def test_viewer_css_styles_each_claim_status_via_data_attribute():
    text = _viewer_css()
    # Per-status colours bind via [data-status="..."] so the JS only
    # has to write `dataset.status` — no class swapping needed. The
    # claim palette is clew's verify_claim / claims.json vocabulary,
    # plus the two transient client-side UI states.
    for status in (
        "verified",
        "suspect",
        "mismatch",
        "missing",
        "registered",
        "not_found",
        "verifying",
        "error",
    ):
        assert f'.lp-claim[data-status="{status}"]' in text


def test_viewer_css_styles_claims_sidebar():
    text = _viewer_css()
    assert ".live-paper-claims" in text
    assert ".lp-claims-list" in text
    assert ".lp-claim" in text


def test_viewer_css_styles_reverify_button_disabled_state():
    text = _viewer_css()
    # Cursor flips to `progress` while in flight so the operator
    # doesn't double-click
    assert ".lp-claim-reverify:disabled" in text
    assert "cursor: progress" in text


def test_viewer_css_status_palette_uses_clew_colour_convention():
    text = _viewer_css()
    # Green for verified, amber for suspect, red for mismatch, dark red
    # for missing (own hue per clew palette v1.3), grey for
    # registered/not_found — matches scitex-clew's claim-status palette
    # so the in-viewer chips read the same as the static-site claims.html
    assert "#2ea043" in text  # GitHub-style green
    assert "#d29922" in text  # GitHub-style amber
    assert "#f85149" in text  # GitHub-style red
    assert "#a40e26" in text  # clew v1.3 missing-red (distinct from mismatch)


def test_viewer_css_failed_verification_renders_red_not_uncoloured():
    text = _viewer_css()
    # Regression guard: a mismatch/missing claim (a FAILED verification)
    # must map to a red var, never fall through to the default border.
    # This was the original bug — the palette used a vocabulary clew
    # never emits, so failures rendered uncoloured. Per clew palette
    # v1.3 (clew 0.7.0), missing carries its OWN red, distinct from
    # mismatch.
    #
    # Matched with whitespace-tolerant patterns rather than exact
    # strings: the repo's CSS formatter reflows one-line rules and drops
    # column alignment, and this guard is about which VAR each status
    # resolves to, not how the stylesheet is laid out. The literal form
    # broke purely on reformatting once already.
    assert re.search(
        r'\.lp-claim\[data-status="mismatch"\]\s*\{\s*'
        r"border-left-color:\s*var\(--lp-status-mismatch\)\s*;",
        text,
    )
    assert re.search(
        r'\.lp-claim\[data-status="missing"\]\s*\{\s*'
        r"border-left-color:\s*var\(--lp-status-missing\)\s*;",
        text,
    )
    assert re.search(r"--lp-status-mismatch:\s*#f85149\s*;", text)
    assert re.search(r"--lp-status-missing:\s*#a40e26\s*;", text)


# ──────────────────────────────────────────────────────────────────
# Backward-compat — PR (b) / PR (c) regressions
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_still_defines_pdfviewer_class():
    text = _viewer_js()
    assert "class PDFViewer" in text


def test_viewer_js_still_fetches_bundle_info():
    text = _viewer_js()
    assert 'apiBase + "bundle-info"' in text


def test_viewer_js_still_wires_text_layer():
    text = _viewer_js()
    assert "_renderTextLayer" in text


def test_viewer_js_still_wires_annotation_layer():
    text = _viewer_js()
    assert "_renderAnnotationLayer" in text
