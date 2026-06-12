"""End-to-end render via a real subprocess — catches console-script /
entry-point regressions the in-process tests cannot.

These tests shell out to ``python -m scitex_live_paper._cli render ...``
and assert on the *real* exit code + the *real* files that land on
disk. No mocks, no patches — just subprocess + file IO. This is the
closest CI gets to what the operator will run by hand in the morning.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_BUNDLE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "bundle-min"
)


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m scitex_live_paper._cli` with the given args."""
    return subprocess.run(
        [sys.executable, "-m", "scitex_live_paper._cli", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


# ──────────────────────────────────────────────────────────────────
# `python -m scitex_live_paper._cli` — module-runnable entry point
# (covers the `if __name__ == "__main__": sys.exit(main())` branch).
# ──────────────────────────────────────────────────────────────────


def test_module_runnable_help_exits_zero():
    # arrange / act
    result = _run_cli("--help")
    # assert
    assert result.returncode == 0, result.stderr
    assert "scitex-live-paper" in result.stdout.lower()


def test_module_runnable_render_help_exits_zero():
    # arrange / act
    result = _run_cli("render", "--help")
    # assert
    assert result.returncode == 0, result.stderr
    assert "BUNDLE_PATH" in result.stdout
    assert "--out" in result.stdout


# ──────────────────────────────────────────────────────────────────
# `render <fixture-bundle> --out <tmp>` — real end-to-end
# ──────────────────────────────────────────────────────────────────


def test_render_subprocess_exits_zero_against_fixture_bundle(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    result = _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"


def test_render_subprocess_emits_index_html(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — landing page lands at the documented location
    assert (out / "index.html").is_file()


def test_render_subprocess_emits_all_four_pages(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — the four pages pinned by issue #7
    for page in ("index.html", "viewer.html", "claims.html", "dag.html"):
        assert (out / page).is_file(), f"missing: {page}"


def test_render_subprocess_copies_claims_json_unchanged(tmp_path):
    # arrange
    out = tmp_path / "site"
    original = json.loads((FIXTURE_BUNDLE / "claims.json").read_text(encoding="utf-8"))

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — read-only copy, byte-for-byte JSON equivalence
    copied = json.loads((out / "claims.json").read_text(encoding="utf-8"))
    assert copied == original


def test_render_subprocess_copies_manuscript_pdf(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert
    assert (out / "manuscript.pdf").is_file()
    assert (out / "manuscript.pdf").stat().st_size > 0


def test_render_subprocess_vendors_pdfjs_assets(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — no CDN; assets live under site/assets/pdfjs/
    pdfjs = out / "assets" / "pdfjs"
    assert pdfjs.is_dir()
    assert any(pdfjs.iterdir())


def test_render_subprocess_vendors_mermaid_assets(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert
    mermaid = out / "assets" / "mermaid"
    assert mermaid.is_dir()
    assert any(mermaid.iterdir())


def test_render_subprocess_pages_contain_no_cdn_references(tmp_path):
    # arrange
    out = tmp_path / "site"
    forbidden = ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com")

    # act
    _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — every emitted HTML page must be CDN-free per #7
    for page in ("index.html", "viewer.html", "claims.html", "dag.html"):
        text = (out / page).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{page} references {marker}"


def test_render_subprocess_idempotent_on_second_run(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act — render twice in the same dir
    first = _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))
    second = _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — both exit 0; site directory still well-formed
    assert first.returncode == 0
    assert second.returncode == 0
    assert (out / "index.html").is_file()


def test_render_subprocess_reports_output_paths_on_stdout(tmp_path):
    # arrange
    out = tmp_path / "site"

    # act
    result = _run_cli("render", str(FIXTURE_BUNDLE), "--out", str(out))

    # assert — CLI prints the relative page paths so the user can copy-click
    assert "index.html" in result.stdout
    assert "viewer.html" in result.stdout
    assert "claims.html" in result.stdout
    assert "dag.html" in result.stdout


# ──────────────────────────────────────────────────────────────────
# Error paths — real exit codes, real stderr
# ──────────────────────────────────────────────────────────────────


def test_render_subprocess_nonzero_exit_for_missing_bundle(tmp_path):
    # arrange
    out = tmp_path / "site"
    # act
    result = _run_cli("render", str(tmp_path / "no-such-bundle"), "--out", str(out))
    # assert
    assert result.returncode != 0


def test_render_subprocess_nonzero_exit_for_malformed_bundle(tmp_path):
    # arrange — bundle dir exists but claims.json is unparseable
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "claims.json").write_text("not json {", encoding="utf-8")
    out = tmp_path / "site"

    # act
    result = _run_cli("render", str(bad), "--out", str(out))

    # assert — loader raises BundleError → CLI ClickException → non-zero exit
    assert result.returncode != 0


def test_render_subprocess_unknown_subcommand_exits_nonzero():
    # arrange / act
    result = _run_cli("not-a-subcommand")
    # assert
    assert result.returncode != 0
