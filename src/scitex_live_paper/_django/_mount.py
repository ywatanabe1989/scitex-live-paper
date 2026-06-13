"""Per-request ``BundleContext`` injection for multi-tenant hub mounts.

The standalone server pins a single bundle for the whole process via
``SCITEX_LIVE_PAPER_BUNDLE``. Host apps that mount this Django app
under ``scitex-hub`` need per-request bundle resolution — the same
process serves many papers, each tied to a different bundle, with the
host's own auth / project context deciding which one.

``mount(resolver=...)`` is that lever. It returns a URL include-able
2-tuple whose patterns mirror :mod:`._django.urls` but each view runs
inside a closure that calls the host-supplied resolver, stashes the
result on ``request.live_paper_context``, then dispatches to the
underlying view. Handlers read the bundle through
:func:`services.get_request_bundle_state`, which prefers the
context when present and falls back to the env-pinned path otherwise.

Contract (pinned for hub F0+F1 dispatcher to lift against):

- **Per-request invocation**: the resolver is called once per
  request, synchronously, before the view runs. No caching at the
  mount layer — the resolver is the cache point if one is wanted.
- **Kwarg flow**: every URL kwarg captured by the host's ``path()``
  mount is forwarded as a keyword arg. For the API dispatcher path,
  the captured ``endpoint`` kwarg is also forwarded (so resolvers
  that route on it can read it without us double-binding).
- **Request stash**: on success the resolver's return value is set
  as ``request.live_paper_context``. Handlers downstream prefer this
  attribute over the env-pinned path.
- **Exception → HTTP status** (resolver MAY raise
  :class:`scitex_live_paper.BundleResolverError` subclasses to signal
  outcome without a 500 + traceback):

  ===========================  ========
  Exception                    Status
  ===========================  ========
  :class:`BundleNotFound`           404
  :class:`BundleAccessDenied`       403
  :class:`BundleResolverError`      500
  ===========================  ========

  Any other subclass of ``BundleResolverError`` falls back to ``500``.
  Non-``BundleResolverError`` exceptions PROPAGATE unchanged — Django's
  default 500 handler renders them. This keeps the contract narrow:
  hosts opt-in to status mapping by subclassing the right exception.

- **Synchronous only**: async resolvers are out of scope for the M4
  path; the contract is sync-only today.

Usage (host side)::

    from django.urls import include, path
    from scitex_live_paper import (
        BundleContext, BundleNotFound, BundleSource, PaperState,
        RendererOptions, mount,
    )

    def hub_resolver(request, paper_id, **url_kwargs) -> BundleContext:
        project = request.user.current_project
        try:
            bundle = load_paper(paper_id, project.id)
        except KeyError as exc:
            raise BundleNotFound(f"paper {paper_id!r} not in {project!r}") from exc
        return BundleContext(
            source=BundleSource.from_resolver(lambda: bundle),
            paper_state=PaperState.from_db(paper_id),
            api_base=request.path.rsplit("/", 1)[0] + "/",
            options=RendererOptions(embed_mode=True),
        )

    urlpatterns = [
        path("apps/live-paper/<paper_id>/", include(mount(resolver=hub_resolver))),
    ]
"""

from __future__ import annotations

from typing import Any, Callable, Tuple

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.urls import path

from .._types import (
    BundleAccessDenied,
    BundleContext,
    BundleNotFound,
    BundleResolverError,
)
from . import views

__all__ = ["BundleResolver", "mount"]

#: A host-supplied callable that produces a :class:`BundleContext` for
#: the current request. URL kwargs flow through as keyword args; the
#: ``**url_kwargs`` form keeps the contract forward-compatible.
BundleResolver = Callable[..., BundleContext]


def _resolver_error_to_response(exc: BundleResolverError) -> HttpResponse:
    """Translate a :class:`BundleResolverError` to the documented HTTP status.

    Bodies are short, non-templated strings so they're stable across
    Django versions and don't leak host implementation details. Hosts
    that want richer error pages can wrap the live-paper mount with
    their own middleware (Django runs middleware AFTER our wrapper
    returns the response).
    """
    if isinstance(exc, BundleNotFound):
        return HttpResponseNotFound(str(exc) or "bundle not found")
    if isinstance(exc, BundleAccessDenied):
        return HttpResponseForbidden(str(exc) or "bundle access denied")
    # Base class or unknown subclass — last-resort 500 with the
    # exception message (NOT a traceback). The narrow contract keeps
    # hosts from accidentally leaking internals.
    return HttpResponse(
        str(exc) or "bundle resolver error",
        status=500,
        content_type="text/plain; charset=utf-8",
    )


def _wrap_viewer_page(resolver: BundleResolver) -> Callable[..., Any]:
    """Wrap :func:`views.viewer_page` so the resolver runs first."""

    def wrapped(request, **url_kwargs):
        try:
            request.live_paper_context = resolver(request, **url_kwargs)
        except BundleResolverError as exc:
            return _resolver_error_to_response(exc)
        return views.viewer_page(request)

    wrapped.__name__ = "live_paper_viewer_page"
    return wrapped


def _wrap_api_dispatch(resolver: BundleResolver) -> Callable[..., Any]:
    """Wrap :func:`views.api_dispatch` so the resolver runs first."""

    def wrapped(request, endpoint, **url_kwargs):
        try:
            # Pass endpoint through so resolvers that route on it can use it
            # without us double-binding the kwarg on the dispatcher call.
            request.live_paper_context = resolver(
                request, endpoint=endpoint, **url_kwargs,
            )
        except BundleResolverError as exc:
            return _resolver_error_to_response(exc)
        return views.api_dispatch(request, endpoint=endpoint)

    wrapped.__name__ = "live_paper_api_dispatch"
    return wrapped


def mount(resolver: BundleResolver) -> Tuple[list, str]:
    """Build URL patterns that inject a per-request :class:`BundleContext`.

    Parameters
    ----------
    resolver
        Host-supplied callable invoked per request. Must return a
        :class:`BundleContext`. Receives the Django ``request`` plus
        every URL kwarg captured by the host's ``path()`` mount.

    Returns
    -------
    (patterns, app_namespace)
        2-tuple suitable for ``include()``. ``app_namespace`` is
        ``"live_paper"`` so reverses (``reverse("live_paper:viewer_page")``,
        ``reverse("live_paper:api_dispatch", kwargs={"endpoint": "api/ping"})``)
        work identically under the standalone server and under a hub
        mount.
    """
    patterns = [
        path("", _wrap_viewer_page(resolver), name="viewer_page"),
        path("<path:endpoint>", _wrap_api_dispatch(resolver), name="api_dispatch"),
    ]
    return patterns, "live_paper"
