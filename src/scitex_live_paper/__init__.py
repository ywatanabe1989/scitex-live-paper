"""SciTeX Live Paper — interactive, AI-verifiable live rendering of research manuscripts.

The renderer is a **reusable component** consumed by multiple host apps
(``scitex-writer``, ``scitex-scholar``, ``scitex-hub``). The same engine
flexes for preprint, peer-reviewed, and accepted papers via the
:class:`PaperState` dataclass.

Public surface (stable):

- :class:`Bundle` / :class:`Claim` / :class:`BundleError` — bundle model
  (mirrors the upstream ``scitex-clew`` schema; never extends it).
- :class:`PaperState` / :data:`PaperStage` — render-time lifecycle metadata.
- :class:`BundleSource` — source abstraction (directory / Bundle instance /
  resolver callable). Hosts that already have a bundle in memory or a
  DB-backed lookup hand in a source rather than writing to disk.
- :class:`BundleContext` — per-render / per-request context the renderer
  reads (source + paper_state + api_base + options).
- :class:`RendererOptions` — display-time knobs (title, embed_mode, theme).

See README.md for the dependency graph and roadmap.
"""

from . import bundle, dag
from ._types import (
    BundleContext,
    BundleResolver,
    BundleSource,
    PaperStage,
    PaperState,
    ReReviewBadge,
    ReReviewStatus,
    RendererOptions,
    RendererTheme,
)
from .bundle import Bundle, BundleError, Claim

__version__ = "0.1.0"

# Hub-publisher surface — single source of truth for how live-paper
# represents itself to scitex-hub's plugin registry. Mirrors the
# 2-layer pattern landed by scitex-agentic-journal so wrapper apps
# under hub can derive their workspace UI manifest instead of
# hand-filling 30+ keys.
from ._hub_app_publisher import (
    HUB_APP_MANIFEST,
    HUB_APP_NAME,
    HUB_APP_VERSION,
    derive_wrapper_manifest,
)


def mount(resolver):
    """Build URL patterns that inject a per-request :class:`BundleContext`.

    Thin wrapper around :func:`scitex_live_paper._django._mount.mount`
    — lazy-imports Django so consumers that only need the library
    surface (``from scitex_live_paper import BundleContext, PaperState``)
    don't pay the Django import cost. Requires the ``[django]`` extra.

    Returns a 2-tuple ``(patterns, "live_paper")`` suitable for
    ``django.urls.include()``::

        from django.urls import include, path
        from scitex_live_paper import mount

        urlpatterns = [
            path("apps/live-paper/<paper_id>/",
                 include(mount(resolver=hub_resolver))),
        ]
    """
    from ._django._mount import mount as _mount  # local: lazy import

    return _mount(resolver)


__all__ = [
    "__version__",
    # bundle model — owned upstream by scitex-clew, mirrored here
    "Bundle",
    "BundleError",
    "Claim",
    # render-time types — the reusable-component public surface
    "BundleContext",
    "BundleResolver",
    "BundleSource",
    "PaperStage",
    "PaperState",
    "ReReviewBadge",
    "ReReviewStatus",
    "RendererOptions",
    "RendererTheme",
    # Django mount helper (lazy-imports Django on call)
    "mount",
    # Hub-publisher surface — manifest + helper for hub-side wrappers
    "HUB_APP_MANIFEST",
    "HUB_APP_NAME",
    "HUB_APP_VERSION",
    "derive_wrapper_manifest",
    # submodules — kept for back-compat
    "bundle",
    "dag",
]
