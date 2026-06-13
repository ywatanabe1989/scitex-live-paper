"""No-mocks tests for the ``scitex-live-paper info`` subcommand.

Operator-facing pre-flight check: load a bundle and print a one-screen
summary (or a `--json` machine-parseable blob). The path uses the real
``bundle.load()`` against on-disk fixtures — no mocks, no patches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_live_paper._cli import cli

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"


# ──────────────────────────────────────────────────────────────────
# `info` subcommand registration + --help
# ──────────────────────────────────────────────────────────────────


def test_info_subcommand_is_registered():
    assert "info" in cli.commands


def test_top_level_help_lists_info():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "info" in result.output


def test_info_help_documents_bundle_argument():
    result = CliRunner().invoke(cli, ["info", "--help"])
    assert result.exit_code == 0
    assert "BUNDLE_PATH" in result.output
    assert "--json" in result.output


def test_info_rejects_missing_bundle_path():
    result = CliRunner().invoke(cli, ["info", "/does-not-exist-anywhere-99"])
    assert result.exit_code != 0


def test_info_rejects_file_path_for_bundle(tmp_path):
    f = tmp_path / "not-a-dir.txt"
    f.write_text("x", encoding="utf-8")
    result = CliRunner().invoke(cli, ["info", str(f)])
    assert result.exit_code != 0


# ──────────────────────────────────────────────────────────────────
# Human-readable output (default)
# ──────────────────────────────────────────────────────────────────


def test_info_bundle_min_exits_zero():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    assert result.exit_code == 0, result.output


def test_info_bundle_min_prints_manuscript_filename():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    assert "manuscript.pdf" in result.output


def test_info_bundle_min_prints_claim_count():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    # bundle-min ships 3 claims
    assert "claims    : 3" in result.output


def test_info_bundle_min_prints_status_palette():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    # bundle-min mixes registered / stale / verified
    for label in ("registered", "stale", "verified"):
        assert label in result.output


def test_info_bundle_min_prints_dag_embedded():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    assert "dag       : embedded" in result.output


def test_info_bundle_min_prints_paper_state_section():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    assert "paper_state" in result.output
    assert "stage         : preprint" in result.output
    assert "header_label  : Preprint" in result.output


def test_info_bundle_min_omits_optional_fields_when_absent():
    # bundle-min has no state.yaml → no journal / DOI / pinned_commit
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    for absent_field in ("journal       :", "doi           :", "pinned_commit :"):
        assert absent_field not in result.output


def test_info_bundle_accepted_prints_journal_and_doi():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_ACCEPTED)])
    assert result.exit_code == 0, result.output
    assert "journal       : eLife" in result.output
    assert "10.7554/eLife.99999" in result.output


def test_info_bundle_accepted_prints_pinned_commit():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_ACCEPTED)])
    assert "deadbeefcafef00d12345678" in result.output


def test_info_bundle_accepted_shows_badge_visible_true():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_ACCEPTED)])
    assert "badge visible : True" in result.output
    assert "re-verify : True" in result.output


def test_info_bundle_min_shows_badge_hidden_false():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN)])
    assert "badge visible : False" in result.output


# ──────────────────────────────────────────────────────────────────
# --json output
# ──────────────────────────────────────────────────────────────────


def test_info_json_exits_zero():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"])
    assert result.exit_code == 0, result.output


def test_info_json_is_valid_parseable_json():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"])
    payload = json.loads(result.output)
    assert isinstance(payload, dict)


def test_info_json_carries_required_keys():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"])
    payload = json.loads(result.output)
    required = {
        "bundle_path",
        "manuscript",
        "schema_version",
        "claim_count",
        "status_palette",
        "dag_present",
        "paper_state",
    }
    missing = required - set(payload.keys())
    assert not missing, f"missing keys: {missing}"


def test_info_json_status_palette_counts():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"])
    palette = json.loads(result.output)["status_palette"]
    assert palette == {"registered": 1, "stale": 1, "verified": 1}


def test_info_json_paper_state_nested_block():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_ACCEPTED), "--json"])
    ps = json.loads(result.output)["paper_state"]
    assert ps["stage"] == "accepted"
    assert ps["journal"] == "eLife"
    assert ps["doi"] == "10.7554/eLife.99999"
    assert ps["pinned_commit"] == "deadbeefcafef00d12345678"
    assert ps["show_verification_badge"] is True
    assert ps["re_verify_enabled"] is True


def test_info_json_dag_present_true():
    result = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"])
    payload = json.loads(result.output)
    assert payload["dag_present"] is True


def test_info_json_output_is_stable_across_runs():
    # Sort_keys=True + Counter ordering → stable output the operator
    # can diff between runs.
    first = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"]).output
    second = CliRunner().invoke(cli, ["info", str(BUNDLE_MIN), "--json"]).output
    assert first == second


# ──────────────────────────────────────────────────────────────────
# Error paths — BundleError surfaces as ClickException
# ──────────────────────────────────────────────────────────────────


def test_info_malformed_claims_json_exits_nonzero(tmp_path):
    # arrange — bundle dir with unparseable claims.json
    bad = tmp_path / "bad-bundle"
    bad.mkdir()
    (bad / "claims.json").write_text("not json {", encoding="utf-8")
    (bad / "manuscript.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (bad / "figz").mkdir()
    # act
    result = CliRunner().invoke(cli, ["info", str(bad)])
    # assert — clean CLI exit; no traceback in output
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_info_missing_manuscript_exits_nonzero(tmp_path):
    bad = tmp_path / "no-manuscript"
    bad.mkdir()
    (bad / "claims.json").write_text(
        '{"schema":"scitex-clew.claims/v1","claims":[]}',
        encoding="utf-8",
    )
    (bad / "figz").mkdir()
    result = CliRunner().invoke(cli, ["info", str(bad)])
    assert result.exit_code != 0
