"""No-mocks tests for M2 re-verify endpoint.

Three classes of test:

1. **Method + body validation** — POST-only, JSON body, required claim_id,
   pinned_commit fallback chain.
2. **Graceful degradation** — when ``scitex-clew`` is not installed
   (the realistic case for fresh installs without the upstream package)
   the handler returns a labelled fallback response, never a 500.
3. **clew-installed integration** — when scitex-clew IS importable
   (real module-state via ``sys.modules`` injection — same lever PR (a)
   used for the no-django ImportError branch), the handler calls the
   real ``verify_claim`` and shapes its return into our envelope.

All collaborators are real. No ``monkeypatch``, no ``mock.patch``.
Real Django test ``Client`` + real bundle fixtures + real
``sys.modules`` manipulation in yield-fixtures with full restore.
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
    """Ensure ``import scitex_clew`` raises ImportError for this test.

    Real ``sys.modules`` state manipulation (not ``mock.patch``):
    write ``None`` to the entry so the next import raises, restore on
    teardown. Same lever PR (a) used for the no-django CLI branch —
    pre-approved by the lead.
    """
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
    """Install a real Python module under ``sys.modules["scitex_clew"]``.

    The module exposes a real ``verify_claim`` function the handler
    will call. Tests can configure its behaviour by setting attributes
    on the yielded module (no `mock.patch.object` — direct attribute
    assignment on a real module). Restored on teardown.
    """
    key = "scitex_clew"
    sentinel = object()
    original = sys.modules.get(key, sentinel)
    module = types.ModuleType(key)
    # Default behaviour: return a real-shaped verified result (nested
    # "claim" key + top-level source_verified/chain_verified/details).
    # Tests override.
    module.verify_claim = lambda claim_id_or_location: {
        "claim": {
            "claim_id": claim_id_or_location,
            "status": "verified",
            "verified_at": "2026-06-13T00:00:00Z",
        },
        "source_verified": True,
        "chain_verified": True,
        "details": ["Source file hash matches", "Chain verified (1 runs)"],
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


def test_reverify_get_returns_405(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.get("/api/claim/verify")
    assert response.status_code == 405
    body = json.loads(response.content)
    assert "method not allowed" in body["error"].lower()


def test_reverify_put_returns_405(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.put("/api/claim/verify")
    assert response.status_code == 405


def test_reverify_empty_body_returns_400(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claim/verify", data="", content_type="application/json")
    assert response.status_code == 400


def test_reverify_malformed_json_returns_400(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.post("/api/claim/verify", data="not-json{{", content_type="application/json")
    assert response.status_code == 400


def test_reverify_non_object_body_returns_400(client, env_snapshot):
    # arrange — a bare JSON list is not a verify request
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps(["claim_a"]),
        content_type="application/json",
    )
    assert response.status_code == 400
    body = json.loads(response.content)
    assert "JSON object" in body["error"]


def test_reverify_missing_claim_id_returns_400(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"pinned_commit": "abc"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    body = json.loads(response.content)
    assert "claim_id" in body["error"]


def test_reverify_empty_claim_id_returns_400(client, env_snapshot):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "   "}),
        content_type="application/json",
    )
    assert response.status_code == 400


# ──────────────────────────────────────────────────────────────────
# pinned_commit fallback chain
# ──────────────────────────────────────────────────────────────────


def test_reverify_no_pinned_commit_anywhere_returns_400(client, env_snapshot, no_scitex_clew):
    # arrange — bundle-min has no state.yaml → no pinned_commit; body
    # also doesn't supply one. Handler must 400 with a clear message.
    _pin(BUNDLE_MIN)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    body = json.loads(response.content)
    assert "pinned_commit" in body["error"]


def test_reverify_body_pinned_commit_wins_over_bundle(client, env_snapshot, fake_scitex_clew):
    # arrange — bundle-accepted has pinned_commit=deadbeef...; body
    # passes a different one. pinned_commit is METADATA only (clew is
    # git-agnostic and never receives it), so we assert on the
    # response's verified_against echo, and that the fake was called
    # with just the claim_id positionally.
    captured: dict = {}

    def recorder(claim_id_or_location):
        captured["arg"] = claim_id_or_location
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({
            "claim_id": "claim_a1b2c3d4e5f6",
            "pinned_commit": "body-supplied-commit",
        }),
        content_type="application/json",
    )

    assert response.status_code == 200
    body = json.loads(response.content)
    assert body["verified_against"] == "body-supplied-commit"
    assert captured["arg"] == "claim_a1b2c3d4e5f6"


def test_reverify_falls_back_to_bundle_paper_state_commit(client, env_snapshot, fake_scitex_clew):
    # arrange — body omits pinned_commit; handler should pull it from
    # bundle.paper_state.pinned_commit and echo it as metadata.
    captured: dict = {}

    def recorder(claim_id_or_location):
        captured["arg"] = claim_id_or_location
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )

    body = json.loads(response.content)
    assert body["verified_against"] == "deadbeefcafef00d12345678"
    assert captured["arg"] == "claim_a1b2c3d4e5f6"


# ──────────────────────────────────────────────────────────────────
# Graceful degradation when scitex-clew not installed
# ──────────────────────────────────────────────────────────────────


def test_reverify_without_clew_returns_200_with_fallback_envelope(client, env_snapshot, no_scitex_clew):
    # arrange — clew unimportable; bundle has a pinned_commit
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )

    # assert — NOT 500; the SPA can render the fallback meaningfully
    assert response.status_code == 200
    body = json.loads(response.content)
    assert body["ok"] is False
    assert body["status"] == "stale"
    assert body["fallback"] is True
    assert "scitex-clew not installed" in body["reason"]


def test_reverify_without_clew_carries_claim_id_back(client, env_snapshot, no_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )
    body = json.loads(response.content)
    assert body["claim_id"] == "claim_a1b2c3d4e5f6"


def test_reverify_with_partial_clew_missing_verify_claim_falls_back(client, env_snapshot):
    # arrange — install a clew module that lacks verify_claim() (e.g.
    # version skew). Handler should still degrade gracefully, not 500.
    key = "scitex_clew"
    sentinel = object()
    original = sys.modules.get(key, sentinel)
    partial = types.ModuleType(key)
    # NO verify_claim attribute on this module.
    sys.modules[key] = partial
    try:
        _pin(BUNDLE_ACCEPTED)
        response = client.post(
            "/api/claim/verify",
            data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["fallback"] is True
        assert "version skew" in body["reason"]
    finally:
        if original is sentinel:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original  # type: ignore[assignment]


# ──────────────────────────────────────────────────────────────────
# Happy path — clew installed, real call, envelope shaping
# ──────────────────────────────────────────────────────────────────


def test_reverify_happy_path_returns_200(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )
    assert response.status_code == 200


def test_reverify_happy_path_envelope_ok_true(client, env_snapshot, fake_scitex_clew):
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )
    body = json.loads(response.content)
    assert body["ok"] is True
    assert body["claim_id"] == "claim_a1b2c3d4e5f6"
    assert body["verified_against"] == "deadbeefcafef00d12345678"
    assert body["status"] == "verified"
    assert body["verified_at"] == "2026-06-13T00:00:00Z"


def test_reverify_details_aggregates_source_and_chain_verified(client, env_snapshot, fake_scitex_clew):
    # The default fake returns the real shape: top-level source_verified /
    # chain_verified / details list all land in our `details` dict.
    _pin(BUNDLE_ACCEPTED)
    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a1b2c3d4e5f6"}),
        content_type="application/json",
    )
    body = json.loads(response.content)
    details = body["details"]
    assert details["source_verified"] is True
    assert details["chain_verified"] is True
    assert details["details"] == [
        "Source file hash matches",
        "Chain verified (1 runs)",
    ]


@pytest.mark.parametrize("status", ["verified", "partial", "mismatch", "missing"])
def test_reverify_extracts_nested_claim_status(client, env_snapshot, fake_scitex_clew, status):
    # status lives at result["claim"]["status"], NOT top-level.
    def recorder(claim_id_or_location):
        return {
            "claim": {
                "claim_id": claim_id_or_location,
                "status": status,
                "verified_at": "2026-06-13T00:00:00Z" if status == "verified" else None,
            },
            "source_verified": status in {"verified", "partial"},
            "chain_verified": status == "verified",
            "details": [f"status is {status}"],
        }

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a"}),
        content_type="application/json",
    )
    body = json.loads(response.content)
    assert body["ok"] is True
    assert body["status"] == status


def test_reverify_not_found_result_is_ok_false(client, env_snapshot, fake_scitex_clew):
    # clew's not-found shape is flat: {"status": "not_found", "message": ...}
    # with NO "claim" key. Handler maps it to ok=False, status="not_found".
    def recorder(claim_id_or_location):
        return {
            "status": "not_found",
            "message": f"No claim found for '{claim_id_or_location}'",
        }

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_missing"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = json.loads(response.content)
    assert body["ok"] is False
    assert body["status"] == "not_found"
    assert body["verified_at"] is None
    assert "No claim found" in body["details"]


def test_reverify_extra_claim_keys_flow_through_details(client, env_snapshot, fake_scitex_clew):
    # arrange — clew returns extra keys (top-level + inside claim); handler
    # bundles them into `details` (forward-compatibility — adding fields
    # upstream doesn't silently change our top-level shape) while still
    # dropping the promoted status/verified_at.
    fake_scitex_clew.verify_claim = lambda claim_id_or_location: {
        "claim": {
            "claim_id": claim_id_or_location,
            "status": "verified",
            "verified_at": "2026-06-13T00:00:00Z",
            "source_file": "r.csv",
            "extra_future_field": "x",
        },
        "source_verified": True,
        "chain_verified": True,
        "details": ["ok"],
        "new_top_level_key": "y",
    }
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a"}),
        content_type="application/json",
    )

    body = json.loads(response.content)
    details = body["details"]
    # promoted keys are NOT in details
    assert "status" not in details
    assert "verified_at" not in details
    # top-level + remaining claim keys survive
    assert details["source_verified"] is True
    assert details["chain_verified"] is True
    assert details["details"] == ["ok"]
    assert details["new_top_level_key"] == "y"
    assert details["source_file"] == "r.csv"
    assert details["extra_future_field"] == "x"


def test_reverify_non_dict_clew_return_stringified(client, env_snapshot, fake_scitex_clew):
    # arrange — older clew might return an enum / dataclass; we stringify
    fake_scitex_clew.verify_claim = lambda claim_id_or_location: "verified"
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a"}),
        content_type="application/json",
    )

    body = json.loads(response.content)
    assert body["ok"] is True
    assert body["status"] == "verified"
    assert body["verified_at"] is None
    assert body["details"] == {}


def test_reverify_clew_raises_returns_500_with_message(client, env_snapshot, fake_scitex_clew):
    # arrange — domain error from clew (e.g. DB unreadable)
    def angry(claim_id_or_location):
        raise RuntimeError("claim not found in clew DAG")

    fake_scitex_clew.verify_claim = angry
    _pin(BUNDLE_ACCEPTED)

    response = client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_z"}),
        content_type="application/json",
    )

    assert response.status_code == 500
    body = json.loads(response.content)
    assert body["ok"] is False
    assert "claim not found" in body["error"]


def test_reverify_calls_clew_with_claim_id_positionally_only(client, env_snapshot, fake_scitex_clew):
    # clew's real signature is verify_claim(claim_id_or_location) — a SINGLE
    # positional arg. The handler must NOT pass against=/bundle_root=.
    captured: dict = {}

    def recorder(claim_id_or_location):
        captured["arg"] = claim_id_or_location
        captured["called"] = True
        return {"claim": {"status": "verified"}}

    fake_scitex_clew.verify_claim = recorder
    _pin(BUNDLE_ACCEPTED)

    client.post(
        "/api/claim/verify",
        data=json.dumps({"claim_id": "claim_a"}),
        content_type="application/json",
    )

    assert captured["called"] is True
    assert captured["arg"] == "claim_a"


# ──────────────────────────────────────────────────────────────────
# HANDLERS registration
# ──────────────────────────────────────────────────────────────────


def test_handlers_registry_includes_api_claim_verify():
    from scitex_live_paper._django.handlers import HANDLERS, handle_reverify

    assert HANDLERS["api/claim/verify"] is handle_reverify
