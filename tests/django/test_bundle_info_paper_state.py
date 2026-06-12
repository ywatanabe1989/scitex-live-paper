"""No-mocks tests for `bundle-info` surfacing PaperState.

PR (4) extends the `api/bundle-info` payload with a `paper_state`
sub-dict so the embed-mode SPA can render the header label /
verification badge without needing a separate endpoint.

All collaborators are real: real Django test Client, real `bundle.load()`
against the in-tree fixtures (`bundle-min` for preprint default,
`bundle-accepted` for eLife-accepted). No `monkeypatch`, no `mock.patch`.
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
    """Restore os.environ after the test (real state, no monkeypatch)."""
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


def _set_bundle(path: Path) -> None:
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(path)
    services.clear_cache()


# ──────────────────────────────────────────────────────────────────
# bundle-min (preprint default)
# ──────────────────────────────────────────────────────────────────


def test_bundle_info_preprint_carries_paper_state_dict(client, env_snapshot):
    _set_bundle(BUNDLE_MIN)
    body = json.loads(client.get("/api/bundle-info").content)
    assert "paper_state" in body
    assert isinstance(body["paper_state"], dict)


def test_bundle_info_preprint_stage_is_preprint(client, env_snapshot):
    _set_bundle(BUNDLE_MIN)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["stage"] == "preprint"


def test_bundle_info_preprint_header_label_is_preprint(client, env_snapshot):
    _set_bundle(BUNDLE_MIN)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["header_label"] == "Preprint"


def test_bundle_info_preprint_badge_hidden_and_reverify_disabled(client, env_snapshot):
    _set_bundle(BUNDLE_MIN)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["show_verification_badge"] is False
    assert body["paper_state"]["re_verify_enabled"] is False


def test_bundle_info_preprint_journal_doi_null(client, env_snapshot):
    _set_bundle(BUNDLE_MIN)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["journal"] is None
    assert body["paper_state"]["doi"] is None
    assert body["paper_state"]["pinned_commit"] is None


# ──────────────────────────────────────────────────────────────────
# bundle-accepted (accepted @ eLife)
# ──────────────────────────────────────────────────────────────────


def test_bundle_info_accepted_stage(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["stage"] == "accepted"


def test_bundle_info_accepted_header_label_names_journal(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["header_label"] == "Accepted by eLife"


def test_bundle_info_accepted_carries_journal_doi_pinned_commit(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    ps = body["paper_state"]
    assert ps["journal"] == "eLife"
    assert ps["doi"] == "10.7554/eLife.99999"
    assert ps["pinned_commit"] == "deadbeefcafef00d12345678"


def test_bundle_info_accepted_carries_accepted_at(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["accepted_at"] == "2026-06-01T10:00:00Z"


def test_bundle_info_accepted_badge_visible_and_reverify_enabled(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["paper_state"]["show_verification_badge"] is True
    assert body["paper_state"]["re_verify_enabled"] is True


# ──────────────────────────────────────────────────────────────────
# Regression: existing bundle-info fields unchanged
# ──────────────────────────────────────────────────────────────────


def test_bundle_info_still_carries_claim_count(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["claim_count"] == 3


def test_bundle_info_still_carries_schema(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["schema"] == "scitex-clew.claims/v1"


def test_bundle_info_still_carries_manuscript_and_dag_present(client, env_snapshot):
    _set_bundle(BUNDLE_ACCEPTED)
    body = json.loads(client.get("/api/bundle-info").content)
    assert body["manuscript"] == "manuscript.pdf"
    assert body["dag_present"] is True
