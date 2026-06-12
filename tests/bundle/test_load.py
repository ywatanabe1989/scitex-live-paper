"""STX-TQ tests for ``scitex_live_paper.bundle.load``.

These exercise the lenient, thin-consumer behaviour:
  - required clew fields are deserialised into typed slots,
  - unknown clew fields flow through to ``Claim.extras``,
  - the wrapper-vs-list shapes of ``claims.json`` are both accepted,
  - optional members (``dag.mmd``, ``provenance.yaml``, ``figz/``) can be
    absent without failing the load.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper.bundle import Bundle, BundleError, Claim, load

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"


# ---------------------------------------------------------------------------
# Happy path on the canonical fixture
# ---------------------------------------------------------------------------


def test_load_returns_bundle_instance_for_minimal_fixture():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert isinstance(result, Bundle)


def test_load_resolves_manuscript_pdf_when_present():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert result.manuscript_path.name == "manuscript.pdf"
    assert result.manuscript_path.is_file()


def test_load_carries_schema_version_from_claims_json():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert result.schema_version == "scitex-clew.claims/v1"


def test_load_returns_all_claims_from_fixture():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert len(result.claims) == 3


def test_load_typed_claim_fields_are_populated():
    # Arrange
    path = BUNDLE_MIN
    # Act
    first = load(path).claims[0]
    # Assert
    assert first.claim_id == "claim_a1b2c3d4e5f6"
    assert first.claim_type == "figure"
    assert first.status == "verified"
    assert first.source_hash == "deadbeefcafef00d"


def test_load_unknown_claim_fields_flow_through_to_extras():
    # Arrange
    path = BUNDLE_MIN
    # Act
    first = load(path).claims[0]
    # Assert: 'anchor' is renderer metadata not in the typed slots; must survive in extras
    assert "anchor" in first.extras
    assert first.extras["anchor"]["page"] == 3


def test_load_reads_dag_as_mermaid_string():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert result.dag.startswith("graph LR")


def test_load_parses_provenance_yaml_into_mapping():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert result.provenance["schema"] == "scitex-clew.provenance/v1"
    assert "sess_001" in result.provenance["sessions"]


def test_load_returns_figz_dir_path_even_if_empty():
    # Arrange
    path = BUNDLE_MIN
    # Act
    result = load(path)
    # Assert
    assert result.figz_dir == (path.resolve() / "figz")


# ---------------------------------------------------------------------------
# Lenient parsing: alternate shapes
# ---------------------------------------------------------------------------


def test_load_accepts_bare_list_at_top_level_of_claims_json(tmp_path: Path):
    # Arrange: build a bundle whose claims.json is a bare list (no wrapper)
    bundle_dir = _make_minimal_bundle(tmp_path, claims_payload=_one_claim_list())
    # Act
    result = load(bundle_dir)
    # Assert
    assert len(result.claims) == 1
    assert result.schema_version is None


def test_load_preserves_forward_compatible_unknown_top_level_keys(tmp_path: Path):
    # Arrange: future clew schema bump might add e.g. "verifier" alongside "claims"
    bundle_dir = _make_minimal_bundle(
        tmp_path,
        claims_payload={
            "schema": "scitex-clew.claims/v9",
            "verifier": "agentic-journal-2026Q4",
            "claims": _one_claim_list(),
        },
    )
    # Act
    result = load(bundle_dir)
    # Assert: load does not raise and schema version flows through
    assert result.schema_version == "scitex-clew.claims/v9"


def test_load_tolerates_missing_dag_file(tmp_path: Path):
    # Arrange
    bundle_dir = _make_minimal_bundle(tmp_path, include_dag=False)
    # Act
    result = load(bundle_dir)
    # Assert
    assert result.dag == ""


def test_load_tolerates_missing_provenance_file(tmp_path: Path):
    # Arrange
    bundle_dir = _make_minimal_bundle(tmp_path, include_provenance=False)
    # Act
    result = load(bundle_dir)
    # Assert
    assert result.provenance == {}


def test_load_accepts_tex_manuscript_when_pdf_missing(tmp_path: Path):
    # Arrange
    bundle_dir = _make_minimal_bundle(tmp_path, manuscript_kind="tex")
    # Act
    result = load(bundle_dir)
    # Assert
    assert result.manuscript_path.suffix == ".tex"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_load_raises_when_path_is_not_a_directory(tmp_path: Path):
    # Arrange
    not_a_dir = tmp_path / "nope"
    # Act / Assert
    with pytest.raises(BundleError, match="not a directory"):
        load(not_a_dir)


def test_load_raises_when_manuscript_missing(tmp_path: Path):
    # Arrange: bundle directory with claims.json but no manuscript
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "claims.json").write_text(json.dumps(_one_claim_list()))
    # Act / Assert
    with pytest.raises(BundleError, match="no manuscript"):
        load(bundle_dir)


def test_load_raises_when_claims_json_missing(tmp_path: Path):
    # Arrange
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    # Act / Assert
    with pytest.raises(BundleError, match="claims.json not found"):
        load(bundle_dir)


def test_load_raises_on_invalid_json(tmp_path: Path):
    # Arrange
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text("{not json")
    # Act / Assert
    with pytest.raises(BundleError, match="not valid JSON"):
        load(bundle_dir)


def test_load_raises_on_unexpected_claims_top_level_shape(tmp_path: Path):
    # Arrange: claims.json with no list and no 'claims' key
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text(json.dumps({"schema": "x"}))
    # Act / Assert
    with pytest.raises(BundleError, match="top level"):
        load(bundle_dir)


def test_load_raises_when_required_claim_field_missing(tmp_path: Path):
    # Arrange: a claim missing 'claim_id'
    bad_claim = {"file_path": "main.tex", "claim_type": "figure"}
    bundle_dir = _make_minimal_bundle(tmp_path, claims_payload=[bad_claim])
    # Act / Assert
    with pytest.raises(BundleError, match="claim_id"):
        load(bundle_dir)


# ---------------------------------------------------------------------------
# Claim.from_dict — unit
# ---------------------------------------------------------------------------


def test_claim_from_dict_round_trips_required_fields():
    # Arrange
    payload = {
        "claim_id": "claim_x",
        "file_path": "main.tex",
        "claim_type": "figure",
    }
    # Act
    claim = Claim.from_dict(payload)
    # Assert
    assert claim.claim_id == "claim_x"
    assert claim.extras == {}


def test_claim_from_dict_raises_on_non_mapping_input():
    # Arrange
    payload = ["claim_x", "main.tex", "figure"]
    # Act / Assert
    with pytest.raises(BundleError, match="mapping"):
        Claim.from_dict(payload)  # type: ignore[arg-type]


def test_bundle_module_exposes_public_api():
    # Arrange
    expected = {"Bundle", "BundleError", "Claim", "load"}
    # Act
    public = set(bundle_module.__all__)
    # Assert
    assert expected.issubset(public)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _one_claim_list() -> list[dict]:
    return [
        {
            "claim_id": "claim_x",
            "file_path": "main.tex",
            "line_number": 1,
            "claim_type": "figure",
            "status": "verified",
        }
    ]


def _make_minimal_bundle(
    tmp_path: Path,
    *,
    claims_payload=None,
    include_dag: bool = True,
    include_provenance: bool = True,
    manuscript_kind: str = "pdf",
) -> Path:
    """Construct a fresh bundle directory under *tmp_path* for negative-path tests."""
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    if manuscript_kind == "pdf":
        (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    elif manuscript_kind == "tex":
        (bundle_dir / "manuscript.tex").write_text(r"\documentclass{article}")
    else:  # pragma: no cover - defensive
        raise ValueError(manuscript_kind)
    payload = claims_payload if claims_payload is not None else _one_claim_list()
    (bundle_dir / "claims.json").write_text(json.dumps(payload))
    if include_dag:
        (bundle_dir / "dag.mmd").write_text("graph LR\n  A --> B\n")
    if include_provenance:
        (bundle_dir / "provenance.yaml").write_text("schema: test\n")
    return bundle_dir
