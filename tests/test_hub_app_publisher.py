"""No-mocks tests for the hub-publisher surface.

Pins:
1. `HUB_APP_MANIFEST` shape (pip-package layer) + frozen-view semantics
2. `derive_wrapper_manifest` field mapping (workspace UI v2.0.0 layer)
3. Top-level re-exports importable from `scitex_live_paper`
4. Version sync with `__version__` (regression-lock against a future
   pyproject bump that forgets to flow into the manifest)

Real file IO — no mocks.
"""

from __future__ import annotations

from typing import Mapping

import pytest


# ──────────────────────────────────────────────────────────────────
# Top-level re-exports
# ──────────────────────────────────────────────────────────────────


def test_top_level_reexports_hub_app_manifest():
    import scitex_live_paper as lp

    assert hasattr(lp, "HUB_APP_MANIFEST")
    assert hasattr(lp, "HUB_APP_NAME")
    assert hasattr(lp, "HUB_APP_VERSION")
    assert hasattr(lp, "derive_wrapper_manifest")


def test_hub_publisher_symbols_in_all():
    import scitex_live_paper as lp

    for name in (
        "HUB_APP_MANIFEST",
        "HUB_APP_NAME",
        "HUB_APP_VERSION",
        "derive_wrapper_manifest",
    ):
        assert name in lp.__all__, f"missing from __all__: {name}"


# ──────────────────────────────────────────────────────────────────
# HUB_APP_MANIFEST — pip-package shape
# ──────────────────────────────────────────────────────────────────


def test_manifest_is_mapping():
    from scitex_live_paper import HUB_APP_MANIFEST

    assert isinstance(HUB_APP_MANIFEST, Mapping)


def test_manifest_has_all_required_keys():
    from scitex_live_paper import HUB_APP_MANIFEST

    required = {
        "name",
        "version",
        "display_name",
        "description",
        "category",
        "python_requires",
        "entry_points",
        "requires",
        "upstream",
        "permissions",
    }
    missing = required - set(HUB_APP_MANIFEST.keys())
    assert not missing, f"manifest missing keys: {missing}"


def test_manifest_name_is_pip_distribution_name():
    from scitex_live_paper import HUB_APP_MANIFEST

    assert HUB_APP_MANIFEST["name"] == "scitex-live-paper"


def test_manifest_version_syncs_with_package_version():
    import scitex_live_paper

    assert scitex_live_paper.HUB_APP_MANIFEST["version"] == scitex_live_paper.__version__


def test_manifest_category_is_app():
    from scitex_live_paper import HUB_APP_MANIFEST

    assert HUB_APP_MANIFEST["category"] == "app"


def test_manifest_python_requires_matches_pyproject():
    from scitex_live_paper import HUB_APP_MANIFEST

    # Pinned via the constant — if pyproject's requires-python ever
    # diverges, bump this too.
    assert HUB_APP_MANIFEST["python_requires"] == ">=3.10"


def test_manifest_entry_points_apps_targets_wrapper_urls():
    from scitex_live_paper import HUB_APP_MANIFEST

    eps = HUB_APP_MANIFEST["entry_points"]
    assert eps["scitex_hub.apps"] == "scitex_live_paper_hub_app.urls:urlpatterns"


def test_manifest_entry_points_app_config_targets_upstream_appconfig():
    from scitex_live_paper import HUB_APP_MANIFEST

    eps = HUB_APP_MANIFEST["entry_points"]
    assert eps["scitex_hub.app_config"] == "scitex_live_paper._django.apps:LivePaperConfig"


def test_manifest_requires_lists_pep508_strings():
    from scitex_live_paper import HUB_APP_MANIFEST

    reqs = HUB_APP_MANIFEST["requires"]
    assert any("scitex-live-paper" in r for r in reqs)
    assert any("django" in r for r in reqs)
    assert any("scitex-clew" in r for r in reqs)


def test_manifest_upstream_points_at_pip_package():
    from scitex_live_paper import HUB_APP_MANIFEST

    upstream = HUB_APP_MANIFEST["upstream"]
    assert upstream["package"] == "scitex-live-paper"
    assert upstream["module"] == "scitex_live_paper"


def test_manifest_permissions_starts_empty():
    from scitex_live_paper import HUB_APP_MANIFEST

    # Documented choice — no permissions invented without enforcement
    # points; hub adds `bundle.read` etc. when the surface lands.
    assert list(HUB_APP_MANIFEST["permissions"]) == []


# ──────────────────────────────────────────────────────────────────
# Frozen-view semantics — caller can't mutate the canonical dict
# ──────────────────────────────────────────────────────────────────


def test_manifest_top_level_is_read_only():
    from scitex_live_paper import HUB_APP_MANIFEST

    with pytest.raises(TypeError):
        HUB_APP_MANIFEST["name"] = "evil"  # type: ignore[index]


def test_manifest_entry_points_is_read_only():
    from scitex_live_paper import HUB_APP_MANIFEST

    with pytest.raises(TypeError):
        HUB_APP_MANIFEST["entry_points"]["scitex_hub.apps"] = "evil"  # type: ignore[index]


# ──────────────────────────────────────────────────────────────────
# derive_wrapper_manifest — workspace UI shape (v2.0.0)
# ──────────────────────────────────────────────────────────────────


def test_derive_returns_plain_dict():
    from scitex_live_paper import derive_wrapper_manifest

    assert isinstance(derive_wrapper_manifest(), dict)


def test_derive_schema_version_defaults_to_2_0_0():
    from scitex_live_paper import derive_wrapper_manifest

    assert derive_wrapper_manifest()["schema_version"] == "2.0.0"


def test_derive_schema_version_overridable():
    from scitex_live_paper import derive_wrapper_manifest

    assert derive_wrapper_manifest(schema_version="2.1.0")["schema_version"] == "2.1.0"


def test_derive_carries_name_and_version_from_manifest():
    from scitex_live_paper import HUB_APP_MANIFEST, derive_wrapper_manifest

    out = derive_wrapper_manifest()
    assert out["name"] == HUB_APP_MANIFEST["name"]
    assert out["version"] == HUB_APP_MANIFEST["version"]


def test_derive_label_defaults_to_display_name():
    from scitex_live_paper import HUB_APP_MANIFEST, derive_wrapper_manifest

    assert derive_wrapper_manifest()["label"] == HUB_APP_MANIFEST["display_name"]


def test_derive_label_override_wins():
    from scitex_live_paper import derive_wrapper_manifest

    assert derive_wrapper_manifest(label="Live Paper")["label"] == "Live Paper"


def test_derive_subtitle_defaults_to_first_sentence():
    from scitex_live_paper import HUB_APP_MANIFEST, derive_wrapper_manifest

    description = HUB_APP_MANIFEST["description"]
    out = derive_wrapper_manifest()
    # First sentence ends with the first period — must be a prefix of description
    assert out["subtitle"]
    assert description.startswith(out["subtitle"])


def test_derive_subtitle_override_wins():
    from scitex_live_paper import derive_wrapper_manifest

    assert (
        derive_wrapper_manifest(subtitle="Mounted under apps/live-paper/")["subtitle"]
        == "Mounted under apps/live-paper/"
    )


def test_derive_about_and_description_are_full_text():
    from scitex_live_paper import HUB_APP_MANIFEST, derive_wrapper_manifest

    out = derive_wrapper_manifest()
    assert out["about"] == HUB_APP_MANIFEST["description"]
    assert out["description"] == HUB_APP_MANIFEST["description"]


def test_derive_dependencies_python_prepends_python_requires():
    from scitex_live_paper import derive_wrapper_manifest

    deps = derive_wrapper_manifest()["dependencies"]["python"]
    # First entry encodes the Python interpreter requirement
    assert deps[0] == "python>=3.10"


def test_derive_dependencies_python_strips_pep508_specifiers():
    from scitex_live_paper import derive_wrapper_manifest

    deps = derive_wrapper_manifest()["dependencies"]["python"]
    # After the `python>=...` prefix, the entries are bare distribution
    # names — version specifiers stripped per the hub UI chip surface.
    assert "scitex-live-paper" in deps
    assert "django" in deps
    assert "scitex-clew" in deps
    # No version specifier should remain on any entry
    for entry in deps[1:]:
        for spec_char in ("=", "<", ">", "!", "~"):
            assert spec_char not in entry, f"version spec leaked: {entry!r}"


def test_derive_privileges_mirrors_permissions():
    from scitex_live_paper import HUB_APP_MANIFEST, derive_wrapper_manifest

    out = derive_wrapper_manifest()
    assert out["privileges"] == list(HUB_APP_MANIFEST["permissions"])


def test_first_sentence_helper_handles_empty_string():
    # Direct unit-style test on the private helper to cover the
    # early-return branch (line 121 of _derive_wrapper_manifest.py).
    from scitex_live_paper._hub_app_publisher._derive_wrapper_manifest import (
        _first_sentence,
    )

    assert _first_sentence("") == ""
    assert _first_sentence("   ") == ""


def test_first_sentence_helper_falls_back_when_no_terminator():
    # No `.` / `!` / `?` — return the trimmed full text (line 124).
    from scitex_live_paper._hub_app_publisher._derive_wrapper_manifest import (
        _first_sentence,
    )

    assert _first_sentence("a label with no terminator") == "a label with no terminator"


def test_strip_pep508_versions_helper_skips_unparseable_entry():
    # Direct unit-style test on the private helper to cover the
    # `continue` branch (line 142). Operator-typo input that doesn't
    # start with an alphanumeric distribution name should be skipped
    # rather than landing as a garbage chip.
    from scitex_live_paper._hub_app_publisher._derive_wrapper_manifest import (
        _strip_pep508_versions,
    )

    # ">=0.1.0" has no leading distribution name → skipped
    assert _strip_pep508_versions((">=0.1.0", "scitex-clew>=0.1.0")) == ["scitex-clew"]


def test_derive_drops_category_upstream_entry_points_python_requires():
    from scitex_live_paper import derive_wrapper_manifest

    out = derive_wrapper_manifest()
    # Per the hub-side reconciliation: these are publishing-layer
    # internals + the workspace UI doesn't surface them.
    assert "category" not in out
    assert "upstream" not in out
    assert "entry_points" not in out
    assert "python_requires" not in out
    # `permissions` (old key) shouldn't appear either — v2.0.0
    # renamed to `privileges`.
    assert "permissions" not in out
