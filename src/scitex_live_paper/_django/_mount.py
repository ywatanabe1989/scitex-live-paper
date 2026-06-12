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

Usage (host side)::

    from django.urls import include, path
    from scitex_live_paper import (
        BundleContext, BundleSource, PaperState, RendererOptions, mount,
    )

    def hub_resolver(request, paper_id, **url_kwargs) -> BundleContext:
        project = request.user.current_project
        return BundleContext(
            source=BundleSource.from_resolver(
                lambda: load_paper(paper_id, project.id),
            ),
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

from django.urls import path

from .._types import BundleContext
from . import views

__all__ = ["BundleResolver", "mount"]

#: A host-supplied callable that produces a :class:`BundleContext` for
#: the current request. URL kwargs flow through as keyword args; the
#: ``**url_kwargs`` form keeps the contract forward-compatible.
BundleResolver = Callable[..., BundleContext]


def _wrap_viewer_page(resolver: BundleResolver) -> Callable[..., Any]:
    """Wrap :func:`views.viewer_page` so the resolver runs first."""

    def wrapped(request, **url_kwargs):
        request.live_paper_context = resolver(request, **url_kwargs)
        return views.viewer_page(request)

    wrapped.__name__ = "live_paper_viewer_page"
    return wrapped


def _wrap_api_dispatch(resolver: BundleResolver) -> Callable[..., Any]:
    """Wrap :func:`views.api_dispatch` so the resolver runs first."""

    def wrapped(request, endpoint, **url_kwargs):
        # Pass endpoint through so resolvers that route on it can use it
        # without us double-binding the kwarg on the dispatcher call.
        request.live_paper_context = resolver(
            request, endpoint=endpoint, **url_kwargs,
        )
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
