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
    RendererOptions,
    RendererTheme,
)
from .bundle import Bundle, BundleError, Claim

__version__ = "0.1.0-alpha"

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
    "RendererOptions",
    "RendererTheme",
    # submodules — kept for back-compat
    "bundle",
    "dag",
]
