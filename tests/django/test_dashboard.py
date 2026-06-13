"""No-mocks tests for the merged ``api/dashboard`` boot endpoint.

`api/dashboard` is a thin wrapper that calls the existing
`bundle-info` + `claims` handlers and returns their outputs under
`bundle` and `claims` keys. Saves the SPA two round-trips at boot.

Tests check both halves of the merged payload + verify the merged
shape matches the underlying endpoints exactly (so the dashboard
can never drift from the contracts it wraps).

Real Django test Client + real bundle fixtures. No
``monkeypatch``, no ``mock.patch``.
"""

from __future__ import annotations

import json
import os
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
        for k in list(os.environ):
            if k not in snap:
                del os.environ[k]
        for k, v in snap.items():
            os.environ[k] = v


@pytest.fixture
def client() -> Client:
    return Client()


def _pin(path: Path) -> None:
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(path)
    services.clear_cache()


# ──────────────────────────────────────────────────────────────────
# Endpoint shape
# ──────────────────────────────────────────────────────────────────


def test_api_dashboard_returns_200(client, env_snapshot):
    _pin(BUNDLE_MIN)
    assert client.get("/api/dashboard").status_code == 200


def test_api_dashboard_returns_bundle_key(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/dashboard").content)
    assert "bundle" in body
    assert isinstance(body["bundle"], dict)


def test_api_dashboard_returns_claims_key(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/dashboard").content)
    assert "claims" in body
    assert isinstance(body["claims"], dict)


# ──────────────────────────────────────────────────────────────────
# Merged shape matches the underlying endpoints exactly
# ──────────────────────────────────────────────────────────────────


def test_dashboard_bundle_matches_bundle_info_endpoint(client, env_snapshot):
    _pin(BUNDLE_MIN)
    bundle_info = json.loads(client.get("/api/bundle-info").content)
    dashboard = json.loads(client.get("/api/dashboard").content)
    assert dashboard["bundle"] == bundle_info


def test_dashboard_claims_matches_claims_endpoint(client, env_snapshot):
    _pin(BUNDLE_MIN)
    claims_only = json.loads(client.get("/api/claims").content)
    dashboard = json.loads(client.get("/api/dashboard").content)
    assert dashboard["claims"] == claims_only


# ──────────────────────────────────────────────────────────────────
# Carries paper_state + re_verify_enabled + claim count
# ──────────────────────────────────────────────────────────────────


def test_dashboard_carries_paper_state_under_bundle(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/dashboard").content)
    ps = body["bundle"]["paper_state"]
    assert ps["stage"] == "accepted"
    assert ps["journal"] == "eLife"
    assert ps["re_verify_enabled"] is True


def test_dashboard_carries_re_verify_enabled_under_claims(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/dashboard").content)
    assert body["claims"]["re_verify_enabled"] is True
    assert body["claims"]["pinned_commit"] == "deadbeefcafef00d12345678"


def test_dashboard_claim_count_matches_array_length(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = json.loads(client.get("/api/dashboard").content)
    assert body["claims"]["claim_count"] == 3
    assert len(body["claims"]["claims"]) == 3


def test_dashboard_includes_re_review_badge_null_when_absent(client, env_snapshot):
    # arrange — env-pinned path has no BundleContext, no badge
    _pin(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/dashboard").content)
    assert body["bundle"]["re_review_badge"] is None


# ──────────────────────────────────────────────────────────────────
# BundleContext (M4) badge surfaces via mount(resolver=...)
# ──────────────────────────────────────────────────────────────────


def test_dashboard_surfaces_re_review_badge_via_mount(env_snapshot):
    from django.test import RequestFactory
    from scitex_live_paper import (
        BundleContext, BundleSource, ReReviewBadge, mount,
    )

    badge = ReReviewBadge(
        status="verified",
        reviewer="agentic-journal-v3",
    )

    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_ACCEPTED),
            re_review_badge=badge,
        )

    patterns, _ = mount(resolver)
    dispatch = next(p.callback for p in patterns if p.name == "api_dispatch")
    response = dispatch(
        RequestFactory().get("/api/dashboard"),
        endpoint="api/dashboard",
    )
    body = json.loads(response.content)
    assert body["bundle"]["re_review_badge"]["status"] == "verified"
    assert body["bundle"]["re_review_badge"]["reviewer"] == "agentic-journal-v3"


# ──────────────────────────────────────────────────────────────────
# HANDLERS registration
# ──────────────────────────────────────────────────────────────────


def test_handlers_registry_includes_api_dashboard():
    from scitex_live_paper._django.handlers import HANDLERS, handle_dashboard

    assert HANDLERS["api/dashboard"] is handle_dashboard


# ──────────────────────────────────────────────────────────────────
# Existing endpoints unchanged (regression — additive PR)
# ──────────────────────────────────────────────────────────────────


def test_existing_bundle_info_endpoint_still_reachable(client, env_snapshot):
    _pin(BUNDLE_MIN)
    assert client.get("/api/bundle-info").status_code == 200


def test_existing_claims_endpoint_still_reachable(client, env_snapshot):
    _pin(BUNDLE_MIN)
    assert client.get("/api/claims").status_code == 200


def test_existing_ping_endpoint_still_reachable(client, env_snapshot):
    _pin(BUNDLE_MIN)
    assert client.get("/api/ping").status_code == 200
