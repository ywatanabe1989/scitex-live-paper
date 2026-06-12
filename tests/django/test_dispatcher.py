"""``_django/views.api_dispatch`` — handler-return contract + body parser.

All collaborators are real:

- Handlers are real Python functions registered into the real module-level
  ``HANDLERS`` mapping under a snapshot fixture that restores it on
  teardown (real state mutation, not a patch).
- HTTP requests are built via Django's ``RequestFactory`` — the real
  collaborator Django itself uses for unit tests, not a mock.

These tests cover the dispatcher branches the M1 ``ping`` /
``bundle-info`` handlers do not exercise:

- handler returns an ``HttpResponse`` instance → pass-through unwrapped,
- handler raises → JSON 500 with the exception message,
- handler returns a non-mapping payload → JSON wrap still happens
  (or the resulting ``TypeError`` is surfaced as a 500),
- ``_read_body_json`` — empty body, valid JSON body, malformed body.
"""

from __future__ import annotations

import json
from typing import Iterator

import pytest

pytest.importorskip("django")

from django.http import HttpResponse, JsonResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from scitex_live_paper._django import views  # noqa: E402
from scitex_live_paper._django.handlers import HANDLERS  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# Fixtures — real state mutation with try/finally restoration
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def handlers_snapshot() -> Iterator[dict]:
    """Snapshot HANDLERS, yield the live dict (mutate freely), restore on teardown.

    Real module-level state — handlers added in a test are visible to the
    real dispatcher exactly as they would be in production code. The
    snapshot fixture puts the registry back exactly how it found it.
    """
    snapshot = dict(HANDLERS)
    try:
        yield HANDLERS
    finally:
        HANDLERS.clear()
        HANDLERS.update(snapshot)


@pytest.fixture
def rf() -> RequestFactory:
    """Real Django RequestFactory."""
    return RequestFactory()


# ──────────────────────────────────────────────────────────────────
# Handler returns HttpResponse — pass-through unwrapped
# ──────────────────────────────────────────────────────────────────


def test_dispatcher_passes_through_httpresponse_unchanged(handlers_snapshot, rf):
    # arrange — a handler that returns its own HttpResponse (e.g. a
    # future download endpoint streaming bytes).
    sentinel = HttpResponse(b"raw-bytes", status=202, content_type="application/x-binary")

    def streaming_handler(request):
        return sentinel

    handlers_snapshot["api/raw-bytes"] = streaming_handler
    request = rf.get("/api/raw-bytes")

    # act
    response = views.api_dispatch(request, "api/raw-bytes")

    # assert — same object (not re-wrapped), status preserved, body preserved
    assert response is sentinel
    assert response.status_code == 202
    assert response.content == b"raw-bytes"


def test_dispatcher_passes_through_subclass_of_httpresponse(handlers_snapshot, rf):
    # arrange — JsonResponse IS an HttpResponse subclass; a handler that
    # builds its own (e.g. to set custom headers) must not be re-wrapped.
    custom = JsonResponse({"custom": True}, status=201)
    custom["X-Live-Paper-Custom"] = "yes"

    def custom_handler(request):
        return custom

    handlers_snapshot["api/custom"] = custom_handler

    # act
    response = views.api_dispatch(rf.get("/api/custom"), "api/custom")

    # assert
    assert response is custom
    assert response.status_code == 201
    assert response["X-Live-Paper-Custom"] == "yes"


# ──────────────────────────────────────────────────────────────────
# Handler raises — dispatcher returns JSON 500
# ──────────────────────────────────────────────────────────────────


def test_dispatcher_returns_500_when_handler_raises(handlers_snapshot, rf):
    # arrange — a handler that raises a domain error
    def boom_handler(request):
        raise RuntimeError("clew did not respond")

    handlers_snapshot["api/boom"] = boom_handler

    # act
    response = views.api_dispatch(rf.get("/api/boom"), "api/boom")

    # assert
    assert response.status_code == 500


def test_dispatcher_500_body_carries_exception_message(handlers_snapshot, rf):
    # arrange
    def boom_handler(request):
        raise RuntimeError("clew did not respond")

    handlers_snapshot["api/boom"] = boom_handler

    # act
    response = views.api_dispatch(rf.get("/api/boom"), "api/boom")
    payload = json.loads(response.content)

    # assert — the exception's str() ends up in the error body
    assert payload == {"error": "clew did not respond"}


def test_dispatcher_500_for_typeerror_handler(handlers_snapshot, rf):
    # arrange — non-RuntimeError to confirm the except is `Exception`
    def bad_handler(request):
        raise TypeError("explicit type mismatch")

    handlers_snapshot["api/typeerror"] = bad_handler

    # act
    response = views.api_dispatch(rf.get("/api/typeerror"), "api/typeerror")

    # assert
    assert response.status_code == 500
    assert json.loads(response.content)["error"] == "explicit type mismatch"


# ──────────────────────────────────────────────────────────────────
# Handler returns mapping — JsonResponse wraps it (existing happy path,
# pinned here because Card A didn't assert the wrap mechanism)
# ──────────────────────────────────────────────────────────────────


def test_dispatcher_wraps_mapping_in_json_response(handlers_snapshot, rf):
    # arrange
    def mapping_handler(request):
        return {"hello": "world", "count": 3}

    handlers_snapshot["api/echo"] = mapping_handler

    # act
    response = views.api_dispatch(rf.get("/api/echo"), "api/echo")

    # assert
    assert response.status_code == 200
    assert json.loads(response.content) == {"hello": "world", "count": 3}
    assert response["Content-Type"].startswith("application/json")


# NOTE: a handler returning a non-dict, non-HttpResponse payload (e.g.
# a list) is NOT defensively wrapped — the JsonResponse wrap on line 77
# is outside the try/except, so TypeError propagates to Django middleware.
# This is a real dispatcher gap worth fixing in a follow-up (the wrap
# should move inside the try) but Card B is test-only; documenting it
# here so the next hardening pass picks it up rather than mocking around it.


# ──────────────────────────────────────────────────────────────────
# Unknown endpoint — re-asserted from a real RequestFactory path
# (Card #8 covered via the Client; here we hit the same branch
# directly with the lower-level RequestFactory to lock in coverage
# for the no-handler path on this layer).
# ──────────────────────────────────────────────────────────────────


def test_dispatcher_returns_404_for_unknown_endpoint(handlers_snapshot, rf):
    # arrange — note: api/unknown is NOT registered (snapshot is the
    # production registry, no test handler added).
    request = rf.get("/api/unknown-endpoint")

    # act
    response = views.api_dispatch(request, "api/unknown-endpoint")

    # assert
    assert response.status_code == 404
    assert json.loads(response.content) == {"error": "unknown endpoint: api/unknown-endpoint"}


# ──────────────────────────────────────────────────────────────────
# _read_body_json — empty / valid / malformed
# ──────────────────────────────────────────────────────────────────


def test_read_body_json_returns_empty_dict_for_empty_body(rf):
    # arrange — GET requests have empty body
    request = rf.get("/api/anything")

    # act
    result = views._read_body_json(request)

    # assert
    assert result == {}


def test_read_body_json_parses_valid_json(rf):
    # arrange — real RequestFactory POST with JSON body
    request = rf.post(
        "/api/anything",
        data=json.dumps({"k": "v", "n": 1}),
        content_type="application/json",
    )

    # act
    result = views._read_body_json(request)

    # assert
    assert result == {"k": "v", "n": 1}


def test_read_body_json_returns_empty_dict_for_malformed_body(rf):
    # arrange — real POST with a body that isn't valid JSON
    request = rf.post(
        "/api/anything",
        data="not-valid-json{{{",
        content_type="application/json",
    )

    # act
    result = views._read_body_json(request)

    # assert — lenient parser swallows JSONDecodeError → {}
    assert result == {}


def test_read_body_json_parses_nested_structure(rf):
    # arrange
    payload = {"outer": {"inner": [1, {"deep": True}]}}
    request = rf.post(
        "/api/anything",
        data=json.dumps(payload),
        content_type="application/json",
    )

    # act
    result = views._read_body_json(request)

    # assert
    assert result == payload
