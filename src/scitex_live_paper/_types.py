"""Public types for the live-paper renderer's reusable-component surface.

The renderer is consumed by multiple host apps (``scitex-writer``,
``scitex-scholar``, ``scitex-hub``) — each of them embeds the same
viewer. To keep that "one viewer, used everywhere" contract clean,
the types every host imports from us live here. **Library surface
only — no behaviour change yet.** Renderers + the Django mount will
be wired through these in follow-up PRs.

Importable from the top-level package::

    from scitex_live_paper import (
        BundleSource, BundleContext, PaperState, RendererOptions,
    )

Schema authorship boundary is unchanged: ``scitex-clew`` owns the
claim model, ``scitex-writer`` owns the bundle layout, this package
just renders. ``PaperState`` is *render-time* state — what label to
show in the header, which re-verify commit to pin against — not a
claim-model extension.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Mapping,
    Optional,
    Union,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .bundle import Bundle

__all__ = [
    "PaperStage",
    "PaperState",
    "BundleSource",
    "BundleContext",
    "RendererOptions",
]


# ──────────────────────────────────────────────────────────────────
# PaperState — render-time paper lifecycle stage
# ──────────────────────────────────────────────────────────────────


#: The five lifecycle stages the renderer flexes for. Authored upstream
#: (in the bundle's ``state.yaml`` once that lands in PR #5) or
#: supplied by the host app at mount/render time. Host override wins.
PaperStage = Literal[
    "draft",         # writer's editable preview — no badge, claims in-flux
    "preprint",      # public preprint — claims vs HEAD
    "in_review",     # under review at <journal> — claims pinned
    "accepted",      # green/orange/red badge, re-verify vs pinned_commit
    "published",     # <journal> · DOI <doi>, full status
]


@dataclass(frozen=True)
class PaperState:
    """Render-time lifecycle metadata for a single paper.

    Drives header label, verification badge visibility, and the commit
    the re-verify button targets (M2). Defaults to ``"preprint"`` so
    the renderer is operator-friendly when a host forgets to specify.
    """

    stage: PaperStage = "preprint"
    journal: Optional[str] = None
    doi: Optional[str] = None
    accepted_at: Optional[str] = None  # ISO-8601
    pinned_commit: Optional[str] = None

    def header_label(self) -> str:
        """Operator-facing label for the page header.

        Renderers use this as the canonical short string ("Preprint",
        "Accepted by Nature", etc.). Hosts may override entirely via
        ``RendererOptions.title``.
        """
        if self.stage == "draft":
            return "Draft"
        if self.stage == "preprint":
            return "Preprint"
        if self.stage == "in_review":
            return f"Under Review at {self.journal}" if self.journal else "Under Review"
        if self.stage == "accepted":
            return f"Accepted by {self.journal}" if self.journal else "Accepted"
        if self.stage == "published":
            parts = [self.journal] if self.journal else []
            if self.doi:
                parts.append(f"DOI: {self.doi}")
            return " · ".join(parts) if parts else "Published"
        # Defensive — Literal exhaustiveness is enforced by the type system,
        # so this branch only fires if a future stage is added.
        return self.stage  # pragma: no cover

    @property
    def show_verification_badge(self) -> bool:
        """Verification badge is visible from ``accepted`` onward."""
        return self.stage in {"accepted", "published"}

    @property
    def re_verify_enabled(self) -> bool:
        """Re-verify is M2 surface; gated on a pinned commit being available."""
        return self.stage in {"accepted", "published"} and self.pinned_commit is not None


# ──────────────────────────────────────────────────────────────────
# BundleSource — abstraction over where the bundle bytes live
# ──────────────────────────────────────────────────────────────────


# What a "bundle provider" callable returns when invoked. The contract
# is "give me a Bundle"; the resolver may load lazily, fetch from a
# DB, or unpack from S3 — the renderer doesn't care.
BundleResolver = Callable[[], "Bundle"]


@dataclass(frozen=True)
class BundleSource:
    """A source the renderer can load a :class:`Bundle` from.

    Three constructors, chosen to fit each host app's reality:

    - :meth:`from_directory` — local filesystem path (CLI / standalone server / fixture tests).
    - :meth:`from_bundle` — an already-loaded :class:`Bundle` instance (writer's in-memory editor).
    - :meth:`from_resolver` — a callable that returns a :class:`Bundle` on demand
      (hub/scholar DB-backed lookups, multi-tenant resolution).

    Exactly one of the three slots is populated; the others are ``None``.
    Hosts that need their own loading semantics build a resolver and
    hand it in — the renderer never reaches back into host internals.
    """

    directory: Optional[Path] = None
    bundle: Optional["Bundle"] = None
    resolver: Optional[BundleResolver] = None

    # ── Constructors ──────────────────────────────────────────────

    @classmethod
    def from_directory(cls, path: Union[str, Path]) -> "BundleSource":
        """Source backed by a local filesystem bundle directory."""
        return cls(directory=Path(path).expanduser().resolve())

    @classmethod
    def from_bundle(cls, bundle: "Bundle") -> "BundleSource":
        """Source backed by an already-loaded :class:`Bundle`.

        Used by host apps that maintain their own bundle in memory
        (e.g. writer's editor) and want to render without round-tripping
        through disk.
        """
        return cls(bundle=bundle)

    @classmethod
    def from_resolver(cls, resolver: BundleResolver) -> "BundleSource":
        """Source backed by a callable that returns a :class:`Bundle` on demand.

        The resolver is invoked once per :meth:`load`. Hosts can wrap
        DB lookups, S3 fetches, or in-memory caches behind this surface.
        """
        return cls(resolver=resolver)

    # ── Resolution ────────────────────────────────────────────────

    def load(self) -> "Bundle":
        """Materialise the :class:`Bundle` this source points at.

        Lazy in the directory case (calls :func:`bundle.load`), eager
        in the bundle case (returns the instance), explicit in the
        resolver case (invokes the callable).

        Raises
        ------
        ValueError
            If the source is empty (constructed via ``__init__`` with
            no fields populated — use a constructor).
        """
        # Local import to dodge circulars — bundle imports nothing
        # from this module, but this module re-exports through __init__.
        from . import bundle as bundle_module

        if self.directory is not None:
            return bundle_module.load(self.directory)
        if self.bundle is not None:
            return self.bundle
        if self.resolver is not None:
            return self.resolver()
        raise ValueError(
            "BundleSource has no populated slot — construct via "
            "BundleSource.from_directory / from_bundle / from_resolver."
        )

    @property
    def kind(self) -> Literal["directory", "bundle", "resolver", "empty"]:
        """Which constructor produced this source — handy for logging + tests."""
        if self.directory is not None:
            return "directory"
        if self.bundle is not None:
            return "bundle"
        if self.resolver is not None:
            return "resolver"
        return "empty"


# ──────────────────────────────────────────────────────────────────
# BundleContext — per-render bundle + state + display options
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BundleContext:
    """Per-render / per-request context the renderer reads.

    A host app constructs this and hands it to the renderer (library
    mode) or the Django mount (via ``request.live_paper_context``,
    set by the ``mount(resolver=...)`` middleware that PR #2 will add).

    Renderers that need the bundle bytes call :meth:`load` on the
    source; renderers that need only metadata read ``paper_state``
    directly without forcing a load.
    """

    source: BundleSource
    paper_state: PaperState = field(default_factory=PaperState)
    api_base: str = "/api/"
    options: "RendererOptions" = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # ``RendererOptions`` carries renderer-display knobs; default to
        # an empty options object so hosts can construct minimally.
        if self.options is None:
            # frozen-dataclass workaround
            object.__setattr__(self, "options", RendererOptions())

    def load_bundle(self) -> "Bundle":
        """Materialise the underlying :class:`Bundle` (calls :meth:`source.load`)."""
        return self.source.load()


# ──────────────────────────────────────────────────────────────────
# RendererOptions — display-time knobs
# ──────────────────────────────────────────────────────────────────


#: Visual themes the SPA shell supports. ``"auto"`` follows the host's
#: ``prefers-color-scheme`` media query; explicit values pin one theme.
RendererTheme = Literal["auto", "light", "dark"]


@dataclass(frozen=True)
class RendererOptions:
    """Display-time renderer knobs hosts can pass at render/mount time.

    All optional; defaults reproduce the M1 standalone behaviour.

    Attributes
    ----------
    title
        Page title override. ``None`` → derive from ``PaperState.header_label()``.
    embed_mode
        ``True`` strips the full-page chrome (header + nav) and emits a
        bare ``<div id="live-paper-root">`` for iframe / component embeds.
        Wiring lands in PR #3.
    theme
        Visual theme — ``"auto"`` (default), ``"light"``, or ``"dark"``.
    extra
        Free-form mapping for host-app-specific knobs (e.g. analytics IDs).
        Renderers ignore unknown keys; hosts can use it to flow data
        through to their own templates without our explicit schema.
    """

    title: Optional[str] = None
    embed_mode: bool = False
    theme: RendererTheme = "auto"
    extra: Mapping[str, Any] = field(default_factory=dict)
