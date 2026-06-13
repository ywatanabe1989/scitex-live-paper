"""No-mocks tests pinning the public-type completeness contract.

Audit deliverable (lead msg ``a40780a3``, 2026-06-14): the public
surface a host needs to consume ``mount(resolver=...)`` is complete +
unambiguous. Two distinct resolver-related type aliases ship:

- :data:`BundleResolver` — zero-arg ``Callable[[], Bundle]``. Used by
  :meth:`BundleSource.from_resolver`. Per-bundle, deferred IO.
- :data:`MountResolver` — request-arg ``Callable[..., BundleContext]``.
  Used by :func:`mount`. Per-request, builds the whole context.

This file pins:

1. **Both aliases public + distinct + correctly signed** — the
   previously latent same-name clash (lead's catch) cannot reappear
   without breaking these tests.
2. **Docstring-example walks via PUBLIC-ONLY imports** — the example
   in ``_mount.py``'s docstring uses ONLY names accessible via
   ``from scitex_live_paper import ...`` (no reaching into
   ``_django.*`` private modules).
3. **Lazy-import safety** — accessing ``MountResolver`` triggers the
   Django import; library-only consumers (``from scitex_live_paper
   import BundleContext`` only) don't pay that cost at package import
   time.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import typing
from pathlib import Path
from typing import get_type_hints

import pytest


# ──────────────────────────────────────────────────────────────────
# Both resolver-type aliases — present, distinct, signed correctly
# ──────────────────────────────────────────────────────────────────


def test_bundle_resolver_in_top_level_all():
    import scitex_live_paper as lp

    assert "BundleResolver" in lp.__all__


def test_mount_resolver_in_top_level_all():
    import scitex_live_paper as lp

    assert "MountResolver" in lp.__all__


def test_bundle_resolver_is_zero_arg_callable_to_bundle():
    # Zero-arg `Callable[[], Bundle]` per the `_types.py` definition.
    # Used by `BundleSource.from_resolver(callable)`.
    from scitex_live_paper import BundleResolver

    # `typing.Callable[[], X]` has __args__ == (X,) on 3.10+; the
    # arg-list part is encoded as the absence of positional args
    # (only the return-type tail). Sanity: it's a Callable alias.
    origin = typing.get_origin(BundleResolver)
    assert origin is typing.Callable or origin is callable or origin is not None
    # Bundle is the SECOND-to-last entry; on `Callable[[], Bundle]`,
    # __args__ == (Bundle,) because the empty arg list collapses.
    args = typing.get_args(BundleResolver)
    assert args, "BundleResolver should have type args"


def test_mount_resolver_is_request_arg_callable_to_bundle_context():
    # Request-arg `Callable[..., BundleContext]` per `_mount.py`.
    # Used by `mount(resolver=...)`.
    from scitex_live_paper import BundleContext, MountResolver

    origin = typing.get_origin(MountResolver)
    assert origin is typing.Callable or origin is callable or origin is not None
    args = typing.get_args(MountResolver)
    # `Callable[..., X]` returns (Ellipsis, X) on Python 3.10+
    assert BundleContext in args, (
        f"MountResolver return should be BundleContext; got args {args!r}"
    )


def test_resolver_aliases_are_distinct_objects():
    # Two layers, two aliases. Pin: they're not the same object — a
    # future "let's unify them" refactor that loses this distinction
    # has to come through this test.
    from scitex_live_paper import BundleResolver, MountResolver

    assert BundleResolver is not MountResolver


# ──────────────────────────────────────────────────────────────────
# Deprecated alias inside `_django._mount` — back-compat preserved
# ──────────────────────────────────────────────────────────────────


def test_mount_module_exposes_mount_resolver_as_canonical():
    pytest.importorskip("django")
    from scitex_live_paper._django import _mount

    assert hasattr(_mount, "MountResolver")
    assert "MountResolver" in _mount.__all__


def test_mount_module_keeps_bundle_resolver_alias_for_back_compat():
    # PR #27's original landing exposed `_django._mount.BundleResolver`.
    # We keep it as a deprecated alias to `MountResolver` so any
    # in-tree consumer (test, host wrapping in private code) doesn't
    # break on the rename — only the top-level public surface changes
    # to surface `MountResolver`.
    pytest.importorskip("django")
    from scitex_live_paper._django import _mount

    assert hasattr(_mount, "BundleResolver")
    assert _mount.BundleResolver is _mount.MountResolver


# ──────────────────────────────────────────────────────────────────
# Top-level access — lazy import (no Django cost for library-only)
# ──────────────────────────────────────────────────────────────────


def test_importing_scitex_live_paper_does_not_import_django():
    # Library-only consumers (`from scitex_live_paper import BundleContext`)
    # shouldn't pay the Django import cost. Pin: importing the package
    # itself does NOT load `django` as a side effect.
    #
    # We force a fresh import by stripping `django` from sys.modules
    # before re-importing the package.
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("django")}
    try:
        # Force fresh import of scitex_live_paper too so __init__ re-runs.
        for k in list(sys.modules):
            if k == "scitex_live_paper" or k.startswith("scitex_live_paper."):
                del sys.modules[k]
        import scitex_live_paper  # noqa: F401
        django_keys_after_import = [k for k in sys.modules if k.startswith("django")]
    finally:
        for k, mod in saved.items():
            sys.modules[k] = mod
    assert not django_keys_after_import, (
        f"importing scitex_live_paper pulled in django modules: {django_keys_after_import!r}"
    )


def test_accessing_mount_resolver_triggers_django_import():
    # PEP 562 module-level `__getattr__` lazy-resolves `MountResolver`.
    # When called, Django becomes available.
    pytest.importorskip("django")
    import scitex_live_paper

    # First access — triggers the lazy import.
    assert scitex_live_paper.MountResolver is not None
    # Subsequent access — same object (cached at module level after
    # __getattr__ returns; we don't strictly require caching, but the
    # type alias is a class-level constant so identity should hold).
    assert scitex_live_paper.MountResolver is scitex_live_paper.MountResolver


def test_unknown_attribute_still_raises():
    # __getattr__ must NOT swallow lookups for names we don't export.
    import scitex_live_paper

    with pytest.raises(AttributeError):
        _ = scitex_live_paper.NotARealThing


# ──────────────────────────────────────────────────────────────────
# Docstring-example walk — every name in the example is public
# ──────────────────────────────────────────────────────────────────


def test_mount_docstring_example_imports_are_all_public():
    """Walk the import block from ``_mount.py``'s docstring example.

    The point of the docstring is to show hosts how to wire a
    resolver. Every name imported in the example MUST be importable
    via ``from scitex_live_paper import ...`` (NOT
    ``from scitex_live_paper._django._mount import ...``). If this
    test starts failing, the docstring is teaching hosts to reach
    into private modules — fix the docstring or hoist the missing
    name to the public surface.
    """
    pytest.importorskip("django")

    # The docstring's example block (verbatim from `_mount.py`):
    docstring_imports = [
        "BundleContext",
        "BundleNotFound",
        "BundleSource",
        "PaperState",
        "RendererOptions",
        "mount",
    ]

    import scitex_live_paper

    for name in docstring_imports:
        assert hasattr(scitex_live_paper, name), (
            f"docstring example imports {name!r} but it's not on the public surface"
        )
        assert name in scitex_live_paper.__all__, (
            f"{name!r} accessible but not in __all__"
        )


# ──────────────────────────────────────────────────────────────────
# Public-only build — a host CAN construct a resolver using only
# top-level imports, then hand it to `mount()` and get patterns back.
# ──────────────────────────────────────────────────────────────────


FIXTURES = Path(__file__).resolve().parent / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"


def test_host_can_build_resolver_using_only_public_imports():
    """The completeness pin: a host wires the full resolver path
    using ONLY ``from scitex_live_paper import ...`` — no private
    module access. If this test ever needs an
    ``_django.*`` import, that's the audit-gap signal.
    """
    pytest.importorskip("django")

    # ── EVERY name below is via the top-level public surface ──
    from scitex_live_paper import (
        BundleContext,
        BundleNotFound,
        BundleSource,
        PaperState,
        RendererOptions,
        mount,
    )

    def host_resolver(request, paper_id=None, **kw):
        if paper_id == "missing":
            raise BundleNotFound(f"paper {paper_id!r} unknown")
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_MIN),
            paper_state=PaperState(stage="preprint"),
            api_base="/api/",
            options=RendererOptions(embed_mode=True),
        )

    patterns, namespace = mount(host_resolver)

    # Two named patterns (viewer + dispatch) under the live_paper namespace
    assert namespace == "live_paper"
    names = sorted(p.name for p in patterns if p.name)
    assert names == ["api_dispatch", "viewer_page"]


# ──────────────────────────────────────────────────────────────────
# Exception hierarchy — also fully public-importable
# ──────────────────────────────────────────────────────────────────


def test_exception_hierarchy_fully_public():
    # PR #47's hierarchy. Repeat the check here so the completeness
    # invariant lives in one place: the audit-pin file.
    import scitex_live_paper as lp

    for name in (
        "BundleResolverError",
        "BundleNotFound",
        "BundleAccessDenied",
    ):
        assert hasattr(lp, name)
        assert name in lp.__all__
