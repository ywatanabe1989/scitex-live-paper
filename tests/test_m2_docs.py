"""Regression locks for the M2 runbook + README status sync.

Cheap doc-content assertions so a future README rewrite doesn't
accidentally drop the M2-shipped status (the lifecycle the operator
relies on when reading "what's done?").

Real file IO — no mocks, no monkeypatch.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────
# Runbook exists + pins the operator-facing facts
# ──────────────────────────────────────────────────────────────────


def test_m2_runbook_exists():
    assert (ROOT / "docs/dev/m2-reverify-runbook.md").is_file()


def test_runbook_names_the_clew_extra():
    text = _read("docs/dev/m2-reverify-runbook.md")
    assert "scitex-live-paper[clew" in text


def test_runbook_documents_both_verify_endpoints():
    text = _read("docs/dev/m2-reverify-runbook.md")
    assert "api/claim/verify" in text
    assert "api/claims/verify" in text


def test_runbook_documents_re_verify_enabled_gate():
    text = _read("docs/dev/m2-reverify-runbook.md")
    assert "re_verify_enabled" in text


def test_runbook_documents_graceful_degradation():
    text = _read("docs/dev/m2-reverify-runbook.md")
    assert "fallback" in text
    assert "stale" in text


def test_runbook_documents_hub_mount_resolver():
    text = _read("docs/dev/m2-reverify-runbook.md")
    assert "mount(resolver=" in text
    assert "hub_resolver" in text


# ──────────────────────────────────────────────────────────────────
# README pins M1+M2 as shipped
# ──────────────────────────────────────────────────────────────────


def test_readme_no_longer_says_pre_alpha_scaffold():
    text = _read("README.md")
    assert "pre-alpha scaffold" not in text


def test_readme_marks_m1_shipped():
    text = _read("README.md")
    # The roadmap row for M1
    assert "M1" in text and "shipped" in text


def test_readme_marks_m2_shipped():
    text = _read("README.md")
    assert "M2" in text and "shipped" in text


def test_readme_links_to_m2_runbook():
    text = _read("README.md")
    assert "docs/dev/m2-reverify-runbook.md" in text


# ──────────────────────────────────────────────────────────────────
# Dev quickstart cross-references the runbook
# ──────────────────────────────────────────────────────────────────


def test_dev_quickstart_links_to_m2_runbook():
    text = _read("docs/dev-quickstart.md")
    assert "dev/m2-reverify-runbook.md" in text
