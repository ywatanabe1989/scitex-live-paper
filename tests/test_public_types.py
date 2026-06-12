"""No-mocks tests for the reusable-component public surface.

These tests pin the contract :mod:`scitex_live_paper._types` exposes to
host apps (``scitex-writer``, ``scitex-scholar``, ``scitex-hub``). The
underlying implementation will be wired into the renderers / Django
mount by follow-up PRs; this file locks the shapes today so the host
apps can build against a stable target.

All collaborators are real — real :class:`Bundle` loaded from the
in-tree fixture, real :class:`BundleSource` constructors, real
``__post_init__`` defaults. No ``monkeypatch``, no ``mock.patch``.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from scitex_live_paper import (
    Bundle,
    BundleContext,
    BundleError,
    BundleResolver,
    BundleSource,
    Claim,
    PaperStage,
    PaperState,
    RendererOptions,
    bundle as bundle_module,
    RendererTheme,
)

FIXTURE_BUNDLE = (
    Path(__file__).resolve().parent / "fixtures" / "bundle-min"
)


# ──────────────────────────────────────────────────────────────────
# Top-level re-exports — host apps import from `scitex_live_paper`
# ──────────────────────────────────────────────────────────────────


def test_top_level_reexports_bundle_model():
    # arrange / act
    import scitex_live_paper as lp

    # assert — the bundle/Claim model is part of the public surface
    assert lp.Bundle is Bundle
    assert lp.Claim is Claim
    assert lp.BundleError is BundleError


def test_top_level_reexports_render_time_types():
    # arrange / act
    import scitex_live_paper as lp

    # assert — every type the design proposal pinned is importable
    for name in (
        "BundleContext",
        "BundleResolver",
        "BundleSource",
        "PaperStage",
        "PaperState",
        "RendererOptions",
        "RendererTheme",
    ):
        assert hasattr(lp, name), f"top-level package missing public type {name!r}"


def test_all_lists_every_public_type():
    # arrange
    import scitex_live_paper as lp

    # act / assert — anything host apps may import is in __all__
    must_export = {
        "Bundle", "BundleError", "Claim",
        "BundleContext", "BundleResolver", "BundleSource",
        "PaperStage", "PaperState",
        "RendererOptions", "RendererTheme",
    }
    assert must_export <= set(lp.__all__)


# ──────────────────────────────────────────────────────────────────
# PaperState — defaults, header labels, derived flags
# ──────────────────────────────────────────────────────────────────


def test_paper_state_default_is_preprint():
    # arrange / act
    state = PaperState()
    # assert — operator-friendly default per the design report
    assert state.stage == "preprint"


def test_paper_state_is_frozen():
    # arrange
    state = PaperState()
    # act / assert — host apps must not mutate state we hand back to them
    with pytest.raises(Exception):
        state.stage = "accepted"  # type: ignore[misc]


def test_paper_stage_literal_lists_all_five_stages():
    # arrange / act
    stages = set(get_args(PaperStage))
    # assert — the design pinned exactly these five
    assert stages == {"draft", "preprint", "in_review", "accepted", "published"}


@pytest.mark.parametrize(
    "stage, expected",
    [
        ("draft", "Draft"),
        ("preprint", "Preprint"),
        ("in_review", "Under Review"),  # no journal
        ("accepted", "Accepted"),       # no journal
        ("published", "Published"),     # no journal/doi
    ],
)
def test_header_label_default_per_stage(stage, expected):
    # arrange / act
    label = PaperState(stage=stage).header_label()
    # assert
    assert label == expected


def test_header_label_in_review_names_journal():
    # arrange
    state = PaperState(stage="in_review", journal="Nature")
    # act
    label = state.header_label()
    # assert
    assert label == "Under Review at Nature"


def test_header_label_accepted_names_journal():
    # arrange
    state = PaperState(stage="accepted", journal="eLife")
    # act
    label = state.header_label()
    # assert
    assert label == "Accepted by eLife"


def test_header_label_published_with_journal_and_doi():
    # arrange
    state = PaperState(
        stage="published",
        journal="Nature Comm",
        doi="10.1038/s41467-2026-99999",
    )
    # act
    label = state.header_label()
    # assert — bullet separator pins the operator-visible format
    assert label == "Nature Comm · DOI: 10.1038/s41467-2026-99999"


def test_show_verification_badge_off_until_accepted():
    # arrange
    off_stages = ("draft", "preprint", "in_review")
    on_stages = ("accepted", "published")
    # act / assert
    for stage in off_stages:
        assert PaperState(stage=stage).show_verification_badge is False
    for stage in on_stages:
        assert PaperState(stage=stage).show_verification_badge is True


def test_re_verify_requires_accepted_plus_pinned_commit():
    # arrange — accepted without a pinned commit means we cannot re-verify
    accepted_no_commit = PaperState(stage="accepted")
    accepted_with_commit = PaperState(stage="accepted", pinned_commit="abc123")
    preprint_with_commit = PaperState(stage="preprint", pinned_commit="abc123")
    # act / assert
    assert accepted_no_commit.re_verify_enabled is False
    assert accepted_with_commit.re_verify_enabled is True
    assert preprint_with_commit.re_verify_enabled is False


# ──────────────────────────────────────────────────────────────────
# BundleSource — constructors + load() + kind property
# ──────────────────────────────────────────────────────────────────


def test_bundle_source_from_directory_resolves_path(tmp_path):
    # arrange
    rel = tmp_path / "."
    # act
    source = BundleSource.from_directory(rel)
    # assert — resolved, absolute, no trailing /. component
    assert source.directory == tmp_path.resolve()
    assert source.kind == "directory"


def test_bundle_source_from_bundle_keeps_instance():
    # arrange
    real_bundle = bundle_module.load(FIXTURE_BUNDLE)
    # act
    source = BundleSource.from_bundle(real_bundle)
    # assert
    assert source.bundle is real_bundle
    assert source.kind == "bundle"


def test_bundle_source_from_resolver_stores_callable():
    # arrange
    def resolver() -> Bundle:
        return bundle_module.load(FIXTURE_BUNDLE)

    # act
    source = BundleSource.from_resolver(resolver)
    # assert
    assert source.resolver is resolver
    assert source.kind == "resolver"


def test_bundle_source_load_from_directory_calls_real_loader():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    # act — real loader, real fixture
    bundle = source.load()
    # assert — bundle-min ships three claims
    assert len(bundle.claims) == 3
    assert bundle.schema_version == "scitex-clew.claims/v1"


def test_bundle_source_load_from_bundle_returns_same_instance():
    # arrange
    pre_loaded = bundle_module.load(FIXTURE_BUNDLE)
    source = BundleSource.from_bundle(pre_loaded)
    # act
    loaded = source.load()
    # assert
    assert loaded is pre_loaded


def test_bundle_source_load_from_resolver_invokes_callable():
    # arrange
    calls: list[int] = []

    def resolver() -> Bundle:
        calls.append(1)
        return bundle_module.load(FIXTURE_BUNDLE)

    source = BundleSource.from_resolver(resolver)

    # act
    bundle = source.load()

    # assert
    assert len(calls) == 1
    assert isinstance(bundle, Bundle)


def test_bundle_source_load_empty_raises_value_error():
    # arrange — direct __init__ bypasses the constructors; load() must fail loud
    source = BundleSource()
    # act / assert
    with pytest.raises(ValueError, match="no populated slot"):
        source.load()


def test_bundle_source_kind_empty_for_unpopulated():
    # arrange
    source = BundleSource()
    # act / assert
    assert source.kind == "empty"


def test_bundle_resolver_alias_is_callable_type():
    # arrange / act
    def resolver() -> Bundle:
        return bundle_module.load(FIXTURE_BUNDLE)

    # assert — BundleResolver is a Callable alias; the type system accepts our resolver
    # (the meaningful check is runtime — the alias is importable + usable)
    typed: BundleResolver = resolver
    assert typed is resolver


# ──────────────────────────────────────────────────────────────────
# BundleContext — composition + defaults + load_bundle()
# ──────────────────────────────────────────────────────────────────


def test_bundle_context_defaults_paper_state_to_preprint():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    # act
    ctx = BundleContext(source=source)
    # assert
    assert ctx.paper_state.stage == "preprint"


def test_bundle_context_defaults_api_base_to_slash_api():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    # act
    ctx = BundleContext(source=source)
    # assert
    assert ctx.api_base == "/api/"


def test_bundle_context_defaults_options_to_empty_renderer_options():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    # act
    ctx = BundleContext(source=source)
    # assert — __post_init__ supplies a real RendererOptions, not None
    assert isinstance(ctx.options, RendererOptions)
    assert ctx.options.title is None
    assert ctx.options.embed_mode is False


def test_bundle_context_load_bundle_delegates_to_source():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    ctx = BundleContext(source=source)
    # act
    bundle = ctx.load_bundle()
    # assert
    assert len(bundle.claims) == 3


def test_bundle_context_is_frozen():
    # arrange
    ctx = BundleContext(source=BundleSource.from_directory(FIXTURE_BUNDLE))
    # act / assert
    with pytest.raises(Exception):
        ctx.api_base = "/other/"  # type: ignore[misc]


def test_bundle_context_carries_paper_state_through():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    state = PaperState(stage="accepted", journal="eLife", pinned_commit="abc")
    # act
    ctx = BundleContext(source=source, paper_state=state)
    # assert
    assert ctx.paper_state.journal == "eLife"
    assert ctx.paper_state.re_verify_enabled is True


def test_bundle_context_carries_options_through():
    # arrange
    source = BundleSource.from_directory(FIXTURE_BUNDLE)
    opts = RendererOptions(title="My Paper", embed_mode=True, theme="dark")
    # act
    ctx = BundleContext(source=source, options=opts)
    # assert
    assert ctx.options.title == "My Paper"
    assert ctx.options.embed_mode is True
    assert ctx.options.theme == "dark"


# ──────────────────────────────────────────────────────────────────
# RendererOptions — defaults + theme literal
# ──────────────────────────────────────────────────────────────────


def test_renderer_options_defaults_match_design():
    # arrange / act
    opts = RendererOptions()
    # assert
    assert opts.title is None
    assert opts.embed_mode is False
    assert opts.theme == "auto"
    assert opts.extra == {}


def test_renderer_options_is_frozen():
    # arrange
    opts = RendererOptions()
    # act / assert
    with pytest.raises(Exception):
        opts.title = "X"  # type: ignore[misc]


def test_renderer_theme_literal_lists_auto_light_dark():
    # arrange / act
    themes = set(get_args(RendererTheme))
    # assert
    assert themes == {"auto", "light", "dark"}


def test_renderer_options_extra_accepts_arbitrary_mapping():
    # arrange — hosts use this for analytics IDs / tenant labels
    extra = {"tenant": "scitex.ai", "analytics_id": "G-XXX"}
    # act
    opts = RendererOptions(extra=extra)
    # assert
    assert opts.extra == extra
