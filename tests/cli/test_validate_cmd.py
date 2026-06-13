"""No-mocks tests for the ``scitex-live-paper validate`` subcommand.

Real `CliRunner` + real bundle fixtures + per-test synthetic bundles
written to `tmp_path` for the issue-triggering paths. No
`monkeypatch`, no `mock.patch`.
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


def _make_bundle(
    tmp_path: Path,
    *,
    claims_json: str | None = None,
    state_yaml: str | None = None,
) -> Path:
    """Build a real bundle dir in `tmp_path`, overlaying claims.json / state.yaml."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("dag.mmd", "manuscript.pdf", "provenance.yaml"):
        (bundle / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle / "figz").mkdir()
    (bundle / "claims.json").write_text(
        claims_json
        if claims_json is not None
        else (BUNDLE_MIN / "claims.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    if state_yaml is not None:
        (bundle / "state.yaml").write_text(state_yaml, encoding="utf-8")
    return bundle


# ──────────────────────────────────────────────────────────────────
# Registration + help
# ──────────────────────────────────────────────────────────────────


def test_validate_subcommand_is_registered():
    assert "validate" in cli.commands


def test_top_level_help_lists_validate():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.output


def test_validate_help_documents_bundle_argument():
    result = CliRunner().invoke(cli, ["validate", "--help"])
    assert result.exit_code == 0
    assert "BUNDLE_PATH" in result.output


def test_validate_rejects_missing_path():
    result = CliRunner().invoke(cli, ["validate", "/does-not-exist-anywhere-zz"])
    assert result.exit_code != 0


# ──────────────────────────────────────────────────────────────────
# Happy paths (the in-tree fixtures must validate clean)
# ──────────────────────────────────────────────────────────────────


def test_validate_bundle_min_is_clean():
    result = CliRunner().invoke(cli, ["validate", str(BUNDLE_MIN)])
    assert result.exit_code == 0, result.output
    assert "no issues found" in result.output


def test_validate_bundle_accepted_is_clean():
    result = CliRunner().invoke(cli, ["validate", str(BUNDLE_ACCEPTED)])
    assert result.exit_code == 0, result.output
    assert "no issues found" in result.output


# ──────────────────────────────────────────────────────────────────
# Claim integrity
# ──────────────────────────────────────────────────────────────────


def test_validate_flags_duplicate_claim_ids(tmp_path):
    # arrange — two claims with the same claim_id
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": [
            {
                "claim_id": "claim_dup",
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "verified",
            },
            {
                "claim_id": "claim_dup",  # same id, different file
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "verified",
            },
        ],
    }
    bundle = _make_bundle(tmp_path, claims_json=json.dumps(claims))
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code != 0
    assert "duplicate claim_id" in result.output
    assert "claim_dup" in result.output


def test_validate_flags_unknown_status(tmp_path):
    # arrange — operator typo: "verfied" instead of "verified"
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": [
            {
                "claim_id": "claim_a",
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "verfied",
            },
        ],
    }
    bundle = _make_bundle(tmp_path, claims_json=json.dumps(claims))
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code != 0
    assert "unknown status" in result.output
    assert "'verfied'" in result.output


def test_validate_flags_non_hex_source_hash(tmp_path):
    # arrange — source_hash with non-hex chars
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": [
            {
                "claim_id": "claim_a",
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "verified",
                "source_hash": "ZZZZ-not-hex",
            },
        ],
    }
    bundle = _make_bundle(tmp_path, claims_json=json.dumps(claims))
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code != 0
    assert "source_hash" in result.output
    assert "doesn't look hex-shaped" in result.output


def test_validate_accepts_valid_hex_source_hash(tmp_path):
    # arrange — well-shaped sha-like hex
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": [
            {
                "claim_id": "claim_a",
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "verified",
                "source_hash": "deadbeef1234abcd",
            },
        ],
    }
    bundle = _make_bundle(tmp_path, claims_json=json.dumps(claims))
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code == 0, result.output


def test_validate_null_source_hash_is_not_flagged(tmp_path):
    # arrange — source_hash absent (None) is fine; only non-None
    # non-hex values are flagged
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": [
            {
                "claim_id": "claim_a",
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "verified",
                "source_hash": None,
            },
        ],
    }
    bundle = _make_bundle(tmp_path, claims_json=json.dumps(claims))
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code == 0, result.output


# ──────────────────────────────────────────────────────────────────
# PaperState sanity
# ──────────────────────────────────────────────────────────────────


def test_validate_flags_accepted_stage_without_pinned_commit(tmp_path):
    # arrange — accepted at journal but no pinned_commit
    bundle = _make_bundle(
        tmp_path,
        state_yaml="stage: accepted\njournal: Nature\n",
    )
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code != 0
    assert "no pinned_commit" in result.output
    assert "re-verify is ungated" in result.output


def test_validate_flags_published_stage_without_pinned_commit(tmp_path):
    bundle = _make_bundle(
        tmp_path,
        state_yaml='stage: published\njournal: eLife\ndoi: "10.x/y"\n',
    )
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    assert result.exit_code != 0
    assert "no pinned_commit" in result.output


def test_validate_does_not_flag_preprint_without_pinned_commit(tmp_path):
    # preprint stages don't need a pinned commit — re-verify is gated off
    bundle = _make_bundle(tmp_path, state_yaml="stage: preprint\n")
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    assert result.exit_code == 0


def test_validate_accepted_with_pinned_commit_is_clean(tmp_path):
    bundle = _make_bundle(
        tmp_path,
        state_yaml=(
            "stage: accepted\n"
            "journal: Nature\n"
            'pinned_commit: "deadbeef1234"\n'
        ),
    )
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    assert result.exit_code == 0


# ──────────────────────────────────────────────────────────────────
# Multi-issue + exit code semantics
# ──────────────────────────────────────────────────────────────────


def test_validate_reports_multiple_issues_and_exits_count(tmp_path):
    # arrange — two distinct issues
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": [
            {
                "claim_id": "claim_a",
                "file_path": "main.tex",
                "claim_type": "value",
                "status": "weird",  # issue 1: unknown status
                "source_hash": "ZZZZ",  # issue 2: non-hex
            },
        ],
    }
    bundle = _make_bundle(
        tmp_path,
        claims_json=json.dumps(claims),
        state_yaml="stage: accepted\njournal: Nature\n",  # issue 3: accepted no pin
    )
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert
    assert result.exit_code == 3
    assert "3 issues found" in result.output


def test_validate_exit_code_capped_at_125(tmp_path):
    # arrange — synthesize many duplicate-claim issues
    claims = {
        "schema": "scitex-clew.claims/v1",
        "claims": (
            [
                {
                    "claim_id": "claim_a",
                    "file_path": "main.tex",
                    "claim_type": "value",
                    "status": "verified",
                }
            ]
            + [
                {
                    "claim_id": "claim_a",  # duplicate
                    "file_path": "main.tex",
                    "claim_type": "value",
                    "status": "verified",
                }
                for _ in range(140)
            ]
        ),
    }
    bundle = _make_bundle(tmp_path, claims_json=json.dumps(claims))
    # act
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # assert — POSIX-friendly cap; the report still names every issue
    assert result.exit_code == 125
    assert "140 issues found" in result.output


# ──────────────────────────────────────────────────────────────────
# BundleError surfaces cleanly
# ──────────────────────────────────────────────────────────────────


def test_validate_malformed_claims_json_exits_nonzero(tmp_path):
    bad = tmp_path / "bad-bundle"
    bad.mkdir()
    (bad / "claims.json").write_text("not json {", encoding="utf-8")
    (bad / "manuscript.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (bad / "figz").mkdir()
    result = CliRunner().invoke(cli, ["validate", str(bad)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


# ──────────────────────────────────────────────────────────────────
# Issue grammar (singular vs plural)
# ──────────────────────────────────────────────────────────────────


def test_looks_hex_rejects_empty_string():
    # arrange — direct unit-style call to the helper covers the
    # `if not value` short-circuit (the loader could leave an empty
    # string in source_hash if a clew schema variant ever wrote ""
    # rather than null).
    from scitex_live_paper._cli import _looks_hex

    # act / assert
    assert _looks_hex("") is False
    assert _looks_hex("deadbeef") is True
    assert _looks_hex("ZZZ") is False


def test_validate_single_issue_uses_singular_grammar(tmp_path):
    bundle = _make_bundle(
        tmp_path,
        state_yaml="stage: accepted\njournal: Nature\n",
    )
    result = CliRunner().invoke(cli, ["validate", str(bundle)])
    # "1 issue found" — singular
    assert "1 issue found" in result.output
    assert "1 issues" not in result.output
