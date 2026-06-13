"""No-mocks tests for the ``scitex-live-paper hub-manifest`` subcommand.

Pins:
1. Subcommand registration + ``--help`` documents the flags
2. Default JSON output is indented + sorted (stable VCS diffs)
3. ``--compact`` switches to single-line JSON
4. ``--label`` / ``--subtitle`` / ``--schema-version`` overrides win
5. Output, with no overrides, matches :func:`derive_wrapper_manifest`
6. Output is ready to redirect into ``manifest.json`` — no chrome,
   no leading log lines, just JSON.

Real CliRunner + real derive_wrapper_manifest — no mocks.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from scitex_live_paper._cli import cli


# ──────────────────────────────────────────────────────────────────
# Subcommand registration + help
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_subcommand_is_registered():
    assert "hub-manifest" in cli.commands


def test_top_level_help_lists_hub_manifest():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "hub-manifest" in result.output


def test_hub_manifest_help_documents_flags():
    result = CliRunner().invoke(cli, ["hub-manifest", "--help"])
    assert result.exit_code == 0
    for flag in ("--label", "--subtitle", "--schema-version", "--compact"):
        assert flag in result.output, f"--help missing flag: {flag}"


def test_hub_manifest_help_mentions_redirect_example():
    # The whole point of the subcommand: redirect into manifest.json.
    # The help text should make that idiom discoverable.
    result = CliRunner().invoke(cli, ["hub-manifest", "--help"])
    assert "manifest.json" in result.output


# ──────────────────────────────────────────────────────────────────
# Default output — indented, sorted, JSON, exit 0
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_exits_zero():
    result = CliRunner().invoke(cli, ["hub-manifest"])
    assert result.exit_code == 0


def test_hub_manifest_default_output_is_valid_json():
    result = CliRunner().invoke(cli, ["hub-manifest"])
    # Must parse cleanly so the user can `... > manifest.json` and
    # downstream `json.load()` callers don't choke.
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)


def test_hub_manifest_default_output_is_indented():
    result = CliRunner().invoke(cli, ["hub-manifest"])
    # Indented JSON spans many lines; compact would be exactly one.
    line_count = sum(1 for ln in result.output.splitlines() if ln.strip())
    assert line_count > 5, "default output should be indented (multi-line)"


def test_hub_manifest_default_output_is_sorted():
    result = CliRunner().invoke(cli, ["hub-manifest"])
    parsed = json.loads(result.output)
    # Hash keys must round-trip in sorted order so VCS diffs are
    # stable across versions of Python / dict insertion order.
    top_keys = list(parsed.keys())
    assert top_keys == sorted(top_keys)


def test_hub_manifest_default_output_matches_derive():
    from scitex_live_paper import derive_wrapper_manifest

    result = CliRunner().invoke(cli, ["hub-manifest"])
    parsed = json.loads(result.output)
    assert parsed == derive_wrapper_manifest()


# ──────────────────────────────────────────────────────────────────
# --compact — single-line JSON for inline embedding
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_compact_is_single_line():
    result = CliRunner().invoke(cli, ["hub-manifest", "--compact"])
    assert result.exit_code == 0
    # Trim the trailing newline click.echo adds; the payload itself
    # should be exactly one line.
    payload = result.output.rstrip("\n")
    assert "\n" not in payload


def test_hub_manifest_compact_is_still_valid_json():
    result = CliRunner().invoke(cli, ["hub-manifest", "--compact"])
    assert json.loads(result.output) == json.loads(
        CliRunner().invoke(cli, ["hub-manifest"]).output
    )


# ──────────────────────────────────────────────────────────────────
# Per-wrapper overrides win
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_label_override_wins():
    result = CliRunner().invoke(cli, ["hub-manifest", "--label", "Live Paper"])
    parsed = json.loads(result.output)
    assert parsed["label"] == "Live Paper"


def test_hub_manifest_subtitle_override_wins():
    result = CliRunner().invoke(
        cli,
        ["hub-manifest", "--subtitle", "Mounted under apps/live-paper/"],
    )
    parsed = json.loads(result.output)
    assert parsed["subtitle"] == "Mounted under apps/live-paper/"


def test_hub_manifest_schema_version_override_wins():
    result = CliRunner().invoke(
        cli,
        ["hub-manifest", "--schema-version", "2.1.0"],
    )
    parsed = json.loads(result.output)
    assert parsed["schema_version"] == "2.1.0"


def test_hub_manifest_default_schema_version_is_2_0_0():
    result = CliRunner().invoke(cli, ["hub-manifest"])
    parsed = json.loads(result.output)
    assert parsed["schema_version"] == "2.0.0"


# ──────────────────────────────────────────────────────────────────
# Output is redirect-ready — no log chrome, no banner
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_output_starts_with_brace():
    # If we printed a banner / progress line above the JSON, redirect
    # into manifest.json would produce an invalid file. Pin: stdout
    # starts with `{` — nothing before it.
    result = CliRunner().invoke(cli, ["hub-manifest"])
    assert result.output.lstrip().startswith("{")


def test_hub_manifest_output_ends_after_closing_brace():
    result = CliRunner().invoke(cli, ["hub-manifest"])
    # Last non-blank line is the closing brace.
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert lines[-1].rstrip() == "}"
