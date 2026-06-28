"""No-mocks tests for M2 bulk re-verify endpoint + Re-verify-all UI.

Real Django test Client + real bundle fixtures + real `sys.modules`
injection of a `types.ModuleType` instance under `"scitex_clew"`
(same pattern PR #31 used for the single endpoint). No
``monkeypatch``, no ``mock.patch``.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("django")

from django.test import Client  # noqa: E402

from scitex_live_paper._django import services  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"


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


@pytest.fixture
def no_scitex_clew() -> Iterator[None]:
    """Force ``import scitex_clew`` to raise ImportError."""
    key = "scitex_clew"
    sentinel = object()
    original = sys.modules.get(key, sentinel)
    sys.modules[key] = None  # type: ignore[assignment]
    try:
        yield
    finally:
        if original is sentinel:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original  # type: ignore[assignment]


@pytest.fixture
def fake_scitex_clew() -> Iterator[types.ModuleType]:
    """Install a real Python module under ``sys.modules['scitex_clew']``."""
    key = "scitex_clew"
    sentinel = object()
    original = sys.modules.get(key, sentinel)
    module = types.ModuleType(key)
    module.verify_claim = lambda claim_id_or_location: {
        "claim": {
            "claim_id": claim_id_or_location,
            "status": "verified",
            "verified_at": "2026-06-13T00:00:00Z",
        },
        "source_verified": True,
        "chain_verified": True,
        "details": ["Source file hash matches"],
    }
    sys.modules[key] = module
    try:
        yield module
    finally:
        if original is sentinel:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original  # type: ignore[assignment]


# ──────────────────────────────────────────────────────────────────
# Method + body validation
# ──────────────────────────────────────────────────────────────────


def test_bulk_get_returns_405(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    assert client.get("/api/claims/verify").status_code == 405


def test_bulk_empty_body_defaults_to_all_claims(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data="",
        content_type="application/json",
    )
    body = json.loads(response.content)
    assert response.status_code == 200
    # bundle-accepted ships 3 claims
    assert body["count"] == 3
    assert len(body["results"]) == 3


def test_bulk_no_body_at_all_defaults_to_all_claims(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claims/verify", data=None, content_type="application/json")
    assert response.status_code == 200


def test_bulk_non_object_body_returns_400(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data=json.dumps([1, 2]),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_bulk_claim_ids_not_a_list_returns_400(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data=json.dumps({"claim_ids": "claim_a"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_bulk_claim_ids_with_non_string_returns_400(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data=json.dumps({"claim_ids": ["claim_a", 42]}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_bulk_claim_ids_with_empty_string_returns_400(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data=json.dumps({"claim_ids": ["claim_a", "  "]}),
        content_type="application/json",
    )
    assert response.status_code == 400


# ──────────────────────────────────────────────────────────────────
# pinned_commit fallback
# ──────────────────────────────────────────────────────────────────


def test_bulk_no_pinned_commit_anywhere_returns_400(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_MIN)  # no state.yaml → no pinned_commit
    response = client.post(
        "/api/claims/verify",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_bulk_body_pinned_commit_wins_over_bundle(client, env_snapshot, fake_scitex_clew):
    # pinned_commit is METADATA only (clew is git-agnostic); assert on the
    # response echo, and that the fake was called with just the claim_id.
    captured: list[str] = []

    def recorder(claim_id_or_location):
        captured.append(claim_id_or_location)
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claims/verify",
        data=json.dumps({"pinned_commit": "body-commit"}),
        content_type="application/json",
    )

    body = json.loads(response.content)
    assert body["verified_against"] == "body-commit"
    # the fake was called once per claim with the claim_id positionally
    assert len(captured) == 3
    assert all(isinstance(c, str) and c for c in captured)


def test_bulk_falls_back_to_bundle_paper_state_commit(client, env_snapshot, fake_scitex_clew):
    captured: list[str] = []

    def recorder(claim_id_or_location):
        captured.append(claim_id_or_location)
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post("/api/claims/verify", data="", content_type="application/json")

    body = json.loads(response.content)
    assert body["verified_against"] == "deadbeefcafef00d12345678"
    assert len(captured) == 3


# ──────────────────────────────────────────────────────────────────
# claim_ids filter — subset, unknown ids
# ──────────────────────────────────────────────────────────────────


def test_bulk_filter_verifies_only_requested_ids(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data=json.dumps({"claim_ids": ["claim_a1b2c3d4e5f6"]}),
        content_type="application/json",
    )
    body = json.loads(response.content)
    # Single claim verified
    verified = [r for r in body["results"] if r.get("ok") is True]
    assert len(verified) == 1
    assert verified[0]["claim_id"] == "claim_a1b2c3d4e5f6"


def test_bulk_unknown_filter_id_returns_per_result_failure(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claims/verify",
        data=json.dumps({"claim_ids": ["claim_a1b2c3d4e5f6", "claim_does_not_exist"]}),
        content_type="application/json",
    )
    body = json.loads(response.content)
    # One verified result + one missing entry
    by_id = {r["claim_id"]: r for r in body["results"]}
    assert by_id["claim_a1b2c3d4e5f6"]["ok"] is True
    assert by_id["claim_does_not_exist"]["ok"] is False
    assert "not found in bundle" in by_id["claim_does_not_exist"]["reason"]
    # Top-level ok = False because one entry failed
    assert body["ok"] is False


# ──────────────────────────────────────────────────────────────────
# clew availability — full sweep & per-claim envelope
# ──────────────────────────────────────────────────────────────────


def test_bulk_without_clew_returns_per_result_fallback(client, env_snapshot, no_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)
    assert response.status_code == 200
    assert body["ok"] is False
    # All three claims should carry the fallback envelope
    for result in body["results"]:
        assert result["ok"] is False
        assert result["fallback"] is True
        assert result["status"] == "stale"
        assert "scitex-clew not installed" in result["reason"]


def test_bulk_happy_path_returns_top_level_ok_true(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)
    assert body["ok"] is True
    assert all(r["ok"] is True for r in body["results"])


def test_bulk_happy_path_carries_verified_against(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)
    assert body["verified_against"] == "deadbeefcafef00d12345678"


def test_bulk_clew_raises_one_does_not_500_the_sweep(client, env_snapshot, fake_scitex_clew):
    def picky(claim_id_or_location):
        if claim_id_or_location == "claim_f6e5d4c3b2a1":
            raise RuntimeError("simulated clew failure")
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = picky
    _pin(BUNDLE_ACCEPTED)

    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)

    assert response.status_code == 200  # NOT 500
    assert body["ok"] is False
    by_id = {r["claim_id"]: r for r in body["results"]}
    assert by_id["claim_f6e5d4c3b2a1"]["ok"] is False
    assert "simulated clew failure" in by_id["claim_f6e5d4c3b2a1"]["error"]
    assert by_id["claim_a1b2c3d4e5f6"]["ok"] is True
    assert by_id["claim_999888777666"]["ok"] is True


def test_bulk_not_found_result_flips_sweep_to_incomplete(client, env_snapshot, fake_scitex_clew):
    # clew resolves the claim but reports not_found (flat shape, no "claim"
    # key) for one claim → that per-result is ok=False, and the overall
    # sweep ok flips to False even though no exception was raised.
    def recorder(claim_id_or_location):
        if claim_id_or_location == "claim_f6e5d4c3b2a1":
            return {
                "status": "not_found",
                "message": f"No claim found for '{claim_id_or_location}'",
            }
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)

    assert response.status_code == 200
    assert body["ok"] is False
    by_id = {r["claim_id"]: r for r in body["results"]}
    assert by_id["claim_f6e5d4c3b2a1"]["ok"] is False
    assert by_id["claim_f6e5d4c3b2a1"]["status"] == "not_found"
    assert by_id["claim_a1b2c3d4e5f6"]["ok"] is True


def test_bulk_per_result_envelope_carries_nested_status_and_details(
    client, env_snapshot, fake_scitex_clew
):
    # Per-result envelope matches the single endpoint: nested status +
    # details aggregation (source_verified/chain_verified/details list).
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)
    for result in body["results"]:
        assert result["status"] == "verified"
        assert result["verified_at"] == "2026-06-13T00:00:00Z"
        assert result["verified_against"] == "deadbeefcafef00d12345678"
        assert result["details"]["source_verified"] is True
        assert result["details"]["chain_verified"] is True
        assert result["details"]["details"] == ["Source file hash matches"]


def test_bulk_count_matches_results_length(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claims/verify", data="", content_type="application/json")
    body = json.loads(response.content)
    assert body["count"] == len(body["results"])


# ──────────────────────────────────────────────────────────────────
# HANDLERS registration
# ──────────────────────────────────────────────────────────────────


def test_handlers_registry_includes_api_claims_verify():
    from scitex_live_paper._django.handlers import HANDLERS, handle_reverify_all

    assert HANDLERS["api/claims/verify"] is handle_reverify_all


# ──────────────────────────────────────────────────────────────────
# Frontend module split — refactor regression
# ──────────────────────────────────────────────────────────────────


def _js_bundle_text() -> str:
    """Concatenated text of every JS module under live_paper/js/."""
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    js_dir = pkg_root / "_django/static/live_paper/js"
    parts = []
    for name in (
        "viewer.js",
        "pdf-viewer.js",
        "claims-sidebar.js",
        "reverify-all.js",
        "_utils.js",
    ):
        parts.append((js_dir / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def _module_file(name: str) -> Path:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return pkg_root / "_django/static/live_paper/js" / name


def test_module_files_all_exist():
    for name in ("viewer.js", "pdf-viewer.js", "claims-sidebar.js", "reverify-all.js", "_utils.js"):
        assert _module_file(name).is_file(), f"missing module: {name}"


def test_viewer_js_imports_from_split_modules():
    text = _module_file("viewer.js").read_text(encoding="utf-8")
    assert 'from "./_utils.js"' in text
    assert 'from "./pdf-viewer.js"' in text
    assert 'from "./claims-sidebar.js"' in text


def test_pdf_viewer_exports_pdfviewer_class():
    text = _module_file("pdf-viewer.js").read_text(encoding="utf-8")
    assert "export class PDFViewer" in text


def test_claims_sidebar_exports_render_claims_sidebar():
    text = _module_file("claims-sidebar.js").read_text(encoding="utf-8")
    assert "export function renderClaimsSidebar" in text


def test_reverify_all_exports_render_button():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    assert "export function renderReverifyAllButton" in text


# ──────────────────────────────────────────────────────────────────
# Bulk UI wiring (reverify-all.js source)
# ──────────────────────────────────────────────────────────────────


def test_reverify_all_button_posts_to_claims_verify():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    assert 'apiBase + "claims/verify"' in text


def test_reverify_all_button_flips_rows_to_verifying_first():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    # Immediate feedback before the network round-trip
    assert '"verifying"' in text


def test_reverify_all_walks_results_per_claim():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    # Walks the response's per-claim envelopes
    assert "payload.results" in text


def test_reverify_all_handles_fallback_envelope():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    assert "result.fallback === true" in text


def test_reverify_all_handles_network_error():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    assert "network error" in text


def test_reverify_all_re_enables_per_claim_buttons_in_finally():
    text = _module_file("reverify-all.js").read_text(encoding="utf-8")
    # On finally, re-enable per-claim buttons so the operator can retry
    # individual rows
    assert "b.disabled = false" in text
