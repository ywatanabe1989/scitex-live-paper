"""Tests that pin the release metadata so it can't drift silently.

If the version in `pyproject.toml`, `__version__`, and `CHANGELOG.md`
ever disagree, the next release would ship with mixed signals (the
PyPI tarball at one version, the package's `__version__` at another).
These checks lock all three together.

Real file IO — no mocks.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib  # py3.11+
except ImportError:  # pragma: no cover - py3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    raw = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return tomllib.loads(raw)["project"]["version"]


def _package_version() -> str:
    import scitex_live_paper

    return scitex_live_paper.__version__


def _changelog_text() -> str:
    return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_pyproject_version_matches_package_version():
    assert _pyproject_version() == _package_version()


def test_pyproject_version_appears_in_changelog():
    assert f"## [{_pyproject_version()}]" in _changelog_text()


def test_pyproject_version_is_not_pre_release():
    version = _pyproject_version()
    assert not re.search(r"-(alpha|beta|rc|dev)", version), (
        f"version {version!r} still carries a pre-release suffix"
    )


def test_pyproject_version_follows_semver():
    version = _pyproject_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"version {version!r} doesn't match SemVer X.Y.Z"
    )


def test_changelog_has_unreleased_section():
    assert "## [Unreleased]" in _changelog_text()


def test_changelog_documents_public_surface_policy():
    assert "documented public surface" in _changelog_text()


def test_changelog_lists_every_documented_subsystem():
    text = _changelog_text()
    for needle in (
        "M1",
        "Reusable component",
        "M2 live re-verify",
        "Writer PDF viewer dogfood",
        "M4 prep",
        "Operator CLI",
        "Documentation",
        "Coverage",
        "Schema ownership boundary",
    ):
        assert needle in text, f"changelog 0.1.0 block missing section: {needle}"


def test_changelog_carries_alpha_section_for_history():
    assert "## [0.1.0-alpha]" in _changelog_text()
