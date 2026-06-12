"""No-mocks tests for ``scitex_live_paper.mount(resolver=...)``.

PR (2) — the final card in the reusable-component sequence. Host apps
(``scitex-hub``, ``scitex-writer``, ``scitex-scholar``) mount the
Django app under their own URL prefix and inject a per-request
``BundleContext`` via a resolver callable. This file pins the
contract host apps will build against.

All collaborators are real — real ``RequestFactory`` requests, real
``HANDLERS`` (with snapshot fixtures for transient entries), real
``BundleSource.from_directory``/``from_bundle`` constructors, real
on-disk fixtures (``bundle-min`` for preprint, ``bundle-accepted``
for the lifecycle test). No ``monkeypatch``, no ``unittest.mock``,
no ``mock.patch``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("django")

from django.test import Client, RequestFactory  # noqa: E402

import scitex_live_paper as lp  # noqa: E402
from scitex_live_paper import (  # noqa: E402
    BundleContext,
    BundleSource,
    PaperState,
    RendererOptions,
    mount,
)
from scitex_live_paper._django import services, views  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def env_snapshot() -> Iterator[None]:
    """Restore ``os.environ`` after the test (real state, no monkeypatch)."""
    snap = dict(os.environ)
    try:
        yield
    finally:
        for key in list(os.environ):
            if key not in snap:
                del os.environ[key]
        for key, value in snap.items():
            os.environ[key] = value


# ──────────────────────────────────────────────────────────────────
# Top-level re-export — `from scitex_live_paper import mount`
# ──────────────────────────────────────────────────────────────────


def test_mount_is_importable_from_top_level_package():
    # arrange / act / assert
    assert callable(lp.mount)


def test_mount_is_in_all():
    # arrange
    # act / assert
    assert "mount" in lp.__all__


# ──────────────────────────────────────────────────────────────────
# `mount(resolver)` shape — patterns + namespace
# ──────────────────────────────────────────────────────────────────


def test_mount_returns_two_tuple_for_include():
    # arrange
    def resolver(request, **kw):
        return BundleContext(source=BundleSource.from_directory(BUNDLE_MIN))

    # act
    result = mount(resolver)

    # assert — Django's include() accepts (patterns, app_namespace)
    assert isinstance(result, tuple)
    assert len(result) == 2
    patterns, app_namespace = result
    assert isinstance(patterns, list)
    assert app_namespace == "live_paper"


def test_mount_returns_viewer_page_and_api_dispatch_patterns():
    # arrange
    def resolver(request, **kw):
        return BundleContext(source=BundleSource.from_directory(BUNDLE_MIN))

    # act
    patterns, _ = mount(resolver)

    # assert — two patterns, named for the standard reverses
    names = sorted(p.name for p in patterns if p.name)
    assert names == ["api_dispatch", "viewer_page"]


# ──────────────────────────────────────────────────────────────────
# Resolver injection — BundleContext landing on request
# ──────────────────────────────────────────────────────────────────


def test_resolver_runs_per_request_and_sets_live_paper_context(rf):
    # arrange
    captured: dict = {}
    context = BundleContext(source=BundleSource.from_directory(BUNDLE_MIN))

    def resolver(request, **url_kwargs):
        captured["request"] = request
        captured["kwargs"] = url_kwargs
        return context

    patterns, _ = mount(resolver)
    viewer_view = next(p.callback for p in patterns if p.name == "viewer_page")

    request = rf.get("/")

    # act
    response = viewer_view(request)

    # assert — resolver got the request, context landed on request
    assert response.status_code == 200
    assert captured["request"] is request
    assert getattr(request, "live_paper_context") is context


def test_resolver_receives_url_kwargs(rf):
    # arrange — hub's resolver expects paper_id as a kwarg from the URL
    captured: dict = {}

    def resolver(request, **url_kwargs):
        captured["kwargs"] = url_kwargs
        return BundleContext(source=BundleSource.from_directory(BUNDLE_MIN))

    patterns, _ = mount(resolver)
    viewer_view = next(p.callback for p in patterns if p.name == "viewer_page")

    # act — simulate URL kwargs being passed in by Django's resolver
    viewer_view(rf.get("/"), paper_id="abc123", project_id="proj-9")

    # assert
    assert captured["kwargs"] == {"paper_id": "abc123", "project_id": "proj-9"}


def test_api_dispatch_wrapper_passes_endpoint_to_resolver(rf):
    # arrange — hub may want to route on endpoint inside the resolver
    captured: dict = {}

    def resolver(request, **url_kwargs):
        captured["kwargs"] = url_kwargs
        return BundleContext(source=BundleSource.from_directory(BUNDLE_MIN))

    patterns, _ = mount(resolver)
    dispatch_view = next(p.callback for p in patterns if p.name == "api_dispatch")

    # act
    dispatch_view(rf.get("/api/ping"), endpoint="api/ping", paper_id="x")

    # assert — resolver gets both endpoint and the URL kwarg
    assert captured["kwargs"] == {"endpoint": "api/ping", "paper_id": "x"}


# ──────────────────────────────────────────────────────────────────
# BundleContext drives bundle resolution in handlers
# ──────────────────────────────────────────────────────────────────


def test_bundle_info_reads_from_resolver_context(rf, env_snapshot):
    # arrange — env env var deliberately points at preprint, resolver
    # points at accepted; resolver must win.
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(BUNDLE_MIN)
    services.clear_cache()

    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_ACCEPTED),
        )

    patterns, _ = mount(resolver)
    dispatch_view = next(p.callback for p in patterns if p.name == "api_dispatch")

    # act
    response = dispatch_view(rf.get("/api/bundle-info"), endpoint="api/bundle-info")
    body = json.loads(response.content)

    # assert — accepted bundle's paper_state surfaced
    assert response.status_code == 200
    assert body["paper_state"]["stage"] == "accepted"
    assert body["paper_state"]["journal"] == "eLife"


def test_bundle_info_falls_back_to_env_when_no_context(env_snapshot):
    # arrange — no mount(), env pinning is the only source
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(BUNDLE_ACCEPTED)
    services.clear_cache()

    client = Client()

    # act
    response = client.get("/api/bundle-info")
    body = json.loads(response.content)

    # assert — accepted bundle from env still flows through
    assert response.status_code == 200
    assert body["paper_state"]["stage"] == "accepted"


def test_bundle_info_uses_from_bundle_source(rf):
    # arrange — hosts that already have an in-memory Bundle (writer's editor)
    # hand it in via BundleSource.from_bundle.
    from scitex_live_paper import bundle as bundle_module

    pre_loaded = bundle_module.load(BUNDLE_ACCEPTED)

    def resolver(request, **kw):
        return BundleContext(source=BundleSource.from_bundle(pre_loaded))

    patterns, _ = mount(resolver)
    dispatch_view = next(p.callback for p in patterns if p.name == "api_dispatch")

    # act
    response = dispatch_view(rf.get("/api/bundle-info"), endpoint="api/bundle-info")
    body = json.loads(response.content)

    # assert
    assert body["paper_state"]["stage"] == "accepted"
    assert body["paper_state"]["doi"] == "10.7554/eLife.99999"


def test_bundle_info_uses_from_resolver_callable(rf):
    # arrange — DB / S3 / multi-tenant lookup idiom
    calls: list[int] = []

    def lazy_load():
        from scitex_live_paper import bundle as bundle_module

        calls.append(1)
        return bundle_module.load(BUNDLE_MIN)

    def resolver(request, **kw):
        return BundleContext(source=BundleSource.from_resolver(lazy_load))

    patterns, _ = mount(resolver)
    dispatch_view = next(p.callback for p in patterns if p.name == "api_dispatch")

    # act
    response = dispatch_view(rf.get("/api/bundle-info"), endpoint="api/bundle-info")

    # assert — resolver-callable was invoked
    assert response.status_code == 200
    assert len(calls) == 1


# ──────────────────────────────────────────────────────────────────
# BundleContext drives viewer_page (api_base + embed_mode)
# ──────────────────────────────────────────────────────────────────


def test_viewer_page_with_context_api_base_overrides_default(rf):
    # arrange — host mounts under `/apps/live-paper/<id>/` so api_base
    # should become `/apps/live-paper/<id>/api/`
    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_MIN),
            api_base="/apps/live-paper/abc/api/",
        )

    patterns, _ = mount(resolver)
    viewer_view = next(p.callback for p in patterns if p.name == "viewer_page")

    # act
    body = viewer_view(rf.get("/")).content.decode("utf-8")

    # assert — SPA fetches the host-mounted prefix, not /api/
    assert 'data-api-base="/apps/live-paper/abc/api/"' in body
    assert 'data-api-base="/api/"' not in body


def test_viewer_page_with_context_embed_mode_true_uses_embed_shell(rf):
    # arrange — host sets embed_mode without a query string
    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_MIN),
            options=RendererOptions(embed_mode=True),
        )

    patterns, _ = mount(resolver)
    viewer_view = next(p.callback for p in patterns if p.name == "viewer_page")

    # act
    body = viewer_view(rf.get("/")).content.decode("utf-8")

    # assert — embed shell selected; no standalone header
    assert 'data-embed-mode="1"' in body
    assert "<header" not in body


def test_viewer_page_query_string_still_wins_even_without_context(rf):
    # arrange — pre-mount (no resolver) regression: ?embed=1 still flips
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")

    # assert
    assert 'data-embed-mode="1"' in body


def test_viewer_page_query_string_overrides_context_options_false(rf):
    # arrange — ?embed=1 OR context.embed_mode → embed shell; this asserts
    # the OR semantics (context says False but query says True → embed).
    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_MIN),
            options=RendererOptions(embed_mode=False),
        )

    patterns, _ = mount(resolver)
    viewer_view = next(p.callback for p in patterns if p.name == "viewer_page")

    # act
    body = viewer_view(rf.get("/?embed=1")).content.decode("utf-8")

    # assert
    assert 'data-embed-mode="1"' in body


def test_viewer_page_default_without_context_unchanged(rf):
    # arrange — regression: no context → default shell + /api/ base
    body = views.viewer_page(rf.get("/")).content.decode("utf-8")

    # assert
    assert 'data-api-base="/api/"' in body
    assert "<header" in body
    assert 'data-embed-mode' not in body


# ──────────────────────────────────────────────────────────────────
# Resolver errors propagate to JSON 500
# ──────────────────────────────────────────────────────────────────


def test_resolver_raising_inside_api_dispatch_propagates(rf):
    # arrange
    def angry_resolver(request, **kw):
        raise RuntimeError("clew lookup failed")

    patterns, _ = mount(angry_resolver)
    dispatch_view = next(p.callback for p in patterns if p.name == "api_dispatch")

    # act / assert — the resolver runs BEFORE the dispatcher's try/except;
    # so it propagates. Hosts can wrap with their own middleware to
    # surface a controlled error response.
    with pytest.raises(RuntimeError, match="clew lookup failed"):
        dispatch_view(rf.get("/api/ping"), endpoint="api/ping")


# ──────────────────────────────────────────────────────────────────
# Services — get_request_bundle_state surface
# ──────────────────────────────────────────────────────────────────


def test_get_request_bundle_state_uses_context_source(rf):
    # arrange
    request = rf.get("/")
    request.live_paper_context = BundleContext(
        source=BundleSource.from_directory(BUNDLE_ACCEPTED),
    )

    # act
    state = services.get_request_bundle_state(request)

    # assert
    assert state.bundle.paper_state.stage == "accepted"
    assert state.bundle.paper_state.journal == "eLife"


def test_get_request_bundle_state_falls_back_to_env_without_context(rf, env_snapshot):
    # arrange — request lacks live_paper_context; env is pinned
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(BUNDLE_MIN)
    services.clear_cache()
    request = rf.get("/")

    # act
    state = services.get_request_bundle_state(request)

    # assert — fell back to env-pinned bundle-min
    assert state.bundle.paper_state.stage == "preprint"
