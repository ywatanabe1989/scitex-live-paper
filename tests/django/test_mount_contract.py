"""No-mocks tests for the ``mount(resolver=...)`` contract pin.

Separate from ``test_mount_resolver.py`` (which pins the success-path
shape — kwarg flow, request stash, BundleContext landing). This file
pins the **error-path** + **exception-hierarchy** contract that
``proj-scitex-hub``'s F0+F1 dispatcher (msg b450c456) will lift
against.

Contract pinned here:

1. The :class:`BundleResolverError` hierarchy is importable from the
   top-level package + listed in ``__all__``.
2. :class:`BundleNotFound` is a :class:`BundleResolverError`.
3. :class:`BundleAccessDenied` is a :class:`BundleResolverError`.
4. ``mount(resolver=...)``'s viewer wrapper translates each subclass
   to the documented HTTP status (404 / 403 / 500), with the
   exception message in the response body.
5. The api-dispatch wrapper does the same translation.
6. Unknown subclasses of :class:`BundleResolverError` fall back to
   500 (catch-all).
7. Non-:class:`BundleResolverError` exceptions PROPAGATE unchanged
   (Django's default 500 handler renders them — the mount layer
   stays narrow).
8. On error, ``request.live_paper_context`` is NOT set (no half-baked
   state leaks to downstream handlers).
9. On success, the resolver is invoked exactly once per request.

All collaborators are real — :class:`RequestFactory` requests, real
:class:`BundleSource`, real on-disk fixtures. No ``monkeypatch``, no
``unittest.mock``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("django")

from django.test import RequestFactory  # noqa: E402

import scitex_live_paper as lp  # noqa: E402
from scitex_live_paper import (  # noqa: E402
    BundleAccessDenied,
    BundleContext,
    BundleNotFound,
    BundleResolverError,
    BundleSource,
    mount,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


def _viewer_view():
    """Return the viewer-page view wrapped by a no-op resolver.

    Used by tests that need to swap the resolver per case (we
    re-mount with the case-specific resolver inside each test).
    """
    raise NotImplementedError  # not used — kept as a documentation anchor


# ──────────────────────────────────────────────────────────────────
# Exception hierarchy — public surface + subclassing
# ──────────────────────────────────────────────────────────────────


def test_bundle_resolver_error_is_top_level_importable():
    assert lp.BundleResolverError is BundleResolverError


def test_bundle_not_found_is_top_level_importable():
    assert lp.BundleNotFound is BundleNotFound


def test_bundle_access_denied_is_top_level_importable():
    assert lp.BundleAccessDenied is BundleAccessDenied


def test_resolver_error_classes_listed_in_all():
    for name in ("BundleResolverError", "BundleNotFound", "BundleAccessDenied"):
        assert name in lp.__all__, f"missing from __all__: {name}"


def test_bundle_not_found_subclasses_bundle_resolver_error():
    assert issubclass(BundleNotFound, BundleResolverError)


def test_bundle_access_denied_subclasses_bundle_resolver_error():
    assert issubclass(BundleAccessDenied, BundleResolverError)


def test_bundle_resolver_error_is_an_exception():
    # Sanity — must be raisable + catchable as a normal exception.
    assert issubclass(BundleResolverError, Exception)


def test_distinct_from_bundle_load_error():
    # ``BundleError`` (raised by ``bundle.load()``) is a separate
    # error family. Pin: they don't share a base class — keeping
    # the resolver layer narrow.
    assert not issubclass(BundleResolverError, lp.BundleError)
    assert not issubclass(lp.BundleError, BundleResolverError)


# ──────────────────────────────────────────────────────────────────
# Viewer-path: BundleResolverError → HTTP status mapping
# ──────────────────────────────────────────────────────────────────


def _viewer_view_with(resolver):
    """Build the mount, return the viewer-page view callable."""
    patterns, _ = mount(resolver)
    return next(p.callback for p in patterns if p.name == "viewer_page")


def _dispatch_view_with(resolver):
    """Build the mount, return the api-dispatch view callable."""
    patterns, _ = mount(resolver)
    return next(p.callback for p in patterns if p.name == "api_dispatch")


def test_viewer_bundle_not_found_returns_404(rf):
    def resolver(request, **kw):
        raise BundleNotFound("paper 'pap-9' not in project 'proj-x'")

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 404
    assert b"paper 'pap-9' not in project 'proj-x'" in response.content


def test_viewer_bundle_access_denied_returns_403(rf):
    def resolver(request, **kw):
        raise BundleAccessDenied("user lacks bundle.read on this project")

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 403
    assert b"user lacks bundle.read on this project" in response.content


def test_viewer_base_bundle_resolver_error_returns_500(rf):
    def resolver(request, **kw):
        raise BundleResolverError("transient resolver failure")

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 500
    assert b"transient resolver failure" in response.content


def test_viewer_unknown_subclass_falls_back_to_500(rf):
    # Any subclass NOT in the {NotFound, AccessDenied} table maps to
    # 500 (catch-all). Hosts can introduce custom subclasses without
    # us breaking — they just get the safe default.
    class CustomTimeoutError(BundleResolverError):
        pass

    def resolver(request, **kw):
        raise CustomTimeoutError("upstream DB timed out")

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 500
    assert b"upstream DB timed out" in response.content


def test_viewer_non_resolver_error_propagates(rf):
    # Non-``BundleResolverError`` exceptions are NOT translated.
    # They propagate so Django's default 500 handler can render
    # them (gives operators a real traceback in dev / sentry in
    # prod). Keeps the contract narrow.
    def resolver(request, **kw):
        raise RuntimeError("not a resolver error — bug in the resolver")

    with pytest.raises(RuntimeError, match="not a resolver error"):
        _viewer_view_with(resolver)(rf.get("/"))


# ──────────────────────────────────────────────────────────────────
# api_dispatch-path: same translation contract
# ──────────────────────────────────────────────────────────────────


def test_dispatch_bundle_not_found_returns_404(rf):
    def resolver(request, **kw):
        raise BundleNotFound("paper 'xyz' unknown")

    response = _dispatch_view_with(resolver)(
        rf.get("/api/bundle-info"), endpoint="api/bundle-info",
    )

    assert response.status_code == 404
    assert b"paper 'xyz' unknown" in response.content


def test_dispatch_bundle_access_denied_returns_403(rf):
    def resolver(request, **kw):
        raise BundleAccessDenied("project access denied")

    response = _dispatch_view_with(resolver)(
        rf.get("/api/bundle-info"), endpoint="api/bundle-info",
    )

    assert response.status_code == 403
    assert b"project access denied" in response.content


def test_dispatch_base_bundle_resolver_error_returns_500(rf):
    def resolver(request, **kw):
        raise BundleResolverError("transient resolver failure")

    response = _dispatch_view_with(resolver)(
        rf.get("/api/bundle-info"), endpoint="api/bundle-info",
    )

    assert response.status_code == 500
    assert b"transient resolver failure" in response.content


def test_dispatch_non_resolver_error_propagates(rf):
    def resolver(request, **kw):
        raise ValueError("bug — not a resolver error")

    with pytest.raises(ValueError, match="bug — not a resolver error"):
        _dispatch_view_with(resolver)(
            rf.get("/api/ping"), endpoint="api/ping",
        )


# ──────────────────────────────────────────────────────────────────
# Empty / fallback messages — body never blank
# ──────────────────────────────────────────────────────────────────


def test_viewer_empty_message_uses_default_text(rf):
    # When the host raises with no message, the response body falls
    # back to a stable default (so the body is never empty — a blank
    # body confuses curl-based smoke checks).
    def resolver(request, **kw):
        raise BundleNotFound()

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 404
    assert response.content  # non-empty default body


def test_viewer_empty_message_access_denied_uses_default_text(rf):
    def resolver(request, **kw):
        raise BundleAccessDenied()

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 403
    assert response.content


def test_viewer_empty_message_base_error_uses_default_text(rf):
    def resolver(request, **kw):
        raise BundleResolverError()

    response = _viewer_view_with(resolver)(rf.get("/"))

    assert response.status_code == 500
    assert response.content


# ──────────────────────────────────────────────────────────────────
# Request-stash semantics — no leak on error path
# ──────────────────────────────────────────────────────────────────


def test_viewer_does_not_set_live_paper_context_on_error(rf):
    # On the error path the resolver never returned a context, so
    # ``request.live_paper_context`` MUST NOT be set. Downstream
    # handlers that look it up should fall back to the env-pinned
    # path (or 404 if the env is also unset).
    def resolver(request, **kw):
        raise BundleNotFound()

    request = rf.get("/")
    _viewer_view_with(resolver)(request)

    assert not hasattr(request, "live_paper_context")


def test_dispatch_does_not_set_live_paper_context_on_error(rf):
    def resolver(request, **kw):
        raise BundleAccessDenied()

    request = rf.get("/api/ping")
    _dispatch_view_with(resolver)(request, endpoint="api/ping")

    assert not hasattr(request, "live_paper_context")


# ──────────────────────────────────────────────────────────────────
# Per-request invocation — exactly once on success
# ──────────────────────────────────────────────────────────────────


def test_viewer_resolver_called_exactly_once_per_request(rf):
    # Pin: the mount layer does NOT cache. Hosts that want caching
    # build it into the resolver itself.
    calls = {"n": 0}

    def resolver(request, **kw):
        calls["n"] += 1
        return BundleContext(source=BundleSource.from_directory(BUNDLE_MIN))

    view = _viewer_view_with(resolver)
    view(rf.get("/"))
    view(rf.get("/"))
    view(rf.get("/"))

    assert calls["n"] == 3


# ──────────────────────────────────────────────────────────────────
# Cross-class catch — `except BundleResolverError` catches subclasses
# ──────────────────────────────────────────────────────────────────


def test_base_class_catches_all_subclasses():
    # Sanity at the Python level — the mount-wrapper relies on this.
    # If it ever breaks (rare — only if someone changes the bases),
    # the mapping logic still works but the catch-all path won't fire.
    for subclass in (BundleNotFound, BundleAccessDenied):
        try:
            raise subclass("test")
        except BundleResolverError as exc:
            assert isinstance(exc, subclass)
        else:  # pragma: no cover - defensive
            pytest.fail(f"{subclass.__name__} not caught by BundleResolverError")
