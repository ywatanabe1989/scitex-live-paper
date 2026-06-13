"""Edge-case coverage for `bundle._load_*` paths.

Closes the 8 missed lines in `bundle.py` that PRs #25 + #16 added
but didn't cover (wrapper-schema invariants on claims.json, provenance
fall-throughs, state.yaml empty-mapping + datetime-auto-coerce paths).

All collaborators are real: real fixture base bundle + per-test
synthetic file overlays in `tmp_path`. No `monkeypatch`, no
`mock.patch`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper.bundle import BundleError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"


def _make_bundle(
    tmp_path: Path,
    *,
    claims_json: str | None = None,
    provenance_yaml: str | None = None,
    state_yaml: str | None = None,
) -> Path:
    """Build a real bundle in `tmp_path`, overlaying file content per test."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("dag.mmd", "manuscript.pdf"):
        (bundle / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle / "figz").mkdir()

    (bundle / "claims.json").write_text(
        claims_json
        if claims_json is not None
        else (BUNDLE_MIN / "claims.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    if provenance_yaml is not None:
        (bundle / "provenance.yaml").write_text(provenance_yaml, encoding="utf-8")
    else:
        (bundle / "provenance.yaml").write_text(
            (BUNDLE_MIN / "provenance.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    if state_yaml is not None:
        (bundle / "state.yaml").write_text(state_yaml, encoding="utf-8")

    return bundle


# ──────────────────────────────────────────────────────────────────
# claims.json wrapper invariants (bundle.py lines 218, 222)
# ──────────────────────────────────────────────────────────────────


def test_claims_wrapper_with_non_list_claims_key_raises(tmp_path):
    # arrange — wrapper form `{"claims": ...}` but with the value
    # being a string rather than a list. Real-world cause: operator
    # typo where they wrote `claims: "data"` in a hand-edited file.
    bundle_path = _make_bundle(
        tmp_path,
        claims_json='{"schema": "scitex-clew.claims/v1", "claims": "should-be-a-list"}',
    )
    # act / assert
    with pytest.raises(BundleError, match=r"'claims' key must hold a list"):
        bundle_module.load(bundle_path)


def test_claims_wrapper_with_non_string_schema_raises(tmp_path):
    # arrange — schema field present but not a string
    bundle_path = _make_bundle(
        tmp_path,
        claims_json='{"schema": 42, "claims": []}',
    )
    # act / assert
    with pytest.raises(BundleError, match=r"'schema' must be a string"):
        bundle_module.load(bundle_path)


def test_claims_wrapper_with_null_schema_is_accepted(tmp_path):
    # arrange — explicit JSON null is documented as "absent"; verify
    # the `is None` branch (no raise; schema_version stays None)
    bundle_path = _make_bundle(
        tmp_path,
        claims_json='{"schema": null, "claims": []}',
    )
    # act
    loaded = bundle_module.load(bundle_path)
    # assert
    assert loaded.schema_version is None
    assert loaded.claims == []


# ──────────────────────────────────────────────────────────────────
# provenance.yaml fall-throughs (bundle.py lines 244, 247, 249)
# ──────────────────────────────────────────────────────────────────


def test_provenance_yaml_empty_returns_empty_dict(tmp_path):
    # arrange — whitespace-only file → empty dict (not BundleError)
    bundle_path = _make_bundle(tmp_path, provenance_yaml="   \n\n")
    # act
    loaded = bundle_module.load(bundle_path)
    # assert
    assert loaded.provenance == {}


def test_provenance_yaml_comments_only_returns_empty_dict(tmp_path):
    # arrange — file has content but yaml.safe_load returns None
    # (comments-only content parses to None)
    bundle_path = _make_bundle(
        tmp_path,
        provenance_yaml="# only a comment\n# nothing else\n",
    )
    # act
    loaded = bundle_module.load(bundle_path)
    # assert — empty dict, not None propagating
    assert loaded.provenance == {}


def test_provenance_yaml_non_mapping_top_level_raises(tmp_path):
    # arrange — a bare list is not a provenance document
    bundle_path = _make_bundle(
        tmp_path,
        provenance_yaml="- one\n- two\n",
    )
    # act / assert
    with pytest.raises(BundleError, match=r"top level must be a mapping"):
        bundle_module.load(bundle_path)


# ──────────────────────────────────────────────────────────────────
# state.yaml fall-throughs (bundle.py line 283 + 320-321)
# ──────────────────────────────────────────────────────────────────


def test_state_yaml_comments_only_falls_back_to_default(tmp_path):
    # arrange — yaml.safe_load returns None on comments-only;
    # loader should drop to the default `PaperState()` rather than
    # raising or carrying None.
    bundle_path = _make_bundle(
        tmp_path,
        state_yaml="# just a comment\n",
    )
    # act
    loaded = bundle_module.load(bundle_path)
    # assert
    assert loaded.paper_state.stage == "preprint"


def test_state_yaml_unquoted_iso_timestamp_coerced_to_string(tmp_path):
    # arrange — `accepted_at: 2026-06-01T10:00:00Z` without quotes
    # parses to a `datetime.datetime` under PyYAML's implicit
    # timestamp tag. Loader must coerce back to an ISO string so the
    # operator-visible PaperState.accepted_at stays a plain str.
    bundle_path = _make_bundle(
        tmp_path,
        state_yaml=(
            "stage: accepted\n"
            "journal: Nature\n"
            "accepted_at: 2026-06-01T10:00:00\n"  # unquoted — auto-parsed
        ),
    )
    # act
    loaded = bundle_module.load(bundle_path)
    # assert — datetime got isoformat()'d
    assert isinstance(loaded.paper_state.accepted_at, str)
    assert loaded.paper_state.accepted_at.startswith("2026-06-01T10:00:00")


def test_state_yaml_unquoted_date_coerced_to_string(tmp_path):
    # arrange — bare date (`2026-06-01`) parses to `datetime.date`
    bundle_path = _make_bundle(
        tmp_path,
        state_yaml=(
            "stage: accepted\n"
            "accepted_at: 2026-06-01\n"  # unquoted — auto-parsed to date
        ),
    )
    # act
    loaded = bundle_module.load(bundle_path)
    # assert — date got isoformat()'d ("2026-06-01")
    assert loaded.paper_state.accepted_at == "2026-06-01"
