"""No-mocks tests for the optional ``state.yaml`` bundle convention.

The renderer reads ``state.yaml`` (if present) into ``Bundle.paper_state``
so the header label, verification-badge visibility, and the M2 re-verify
pin all flow from the bundle's own metadata. Absent file → defaults to
``PaperState(stage="preprint")`` so legacy bundles without ``state.yaml``
keep working unchanged.

Schema ownership note: ``state.yaml`` is **render-time** metadata owned
by this package — it does NOT extend the upstream claim / DAG schemas
(those stay in ``scitex-clew``). Hosts can override at render/mount
time via ``BundleContext.paper_state``; the value on the bundle is the
bundle's own default.

All collaborators are real: real on-disk fixtures (``bundle-min/`` for
the absent-state path, ``bundle-accepted/`` for the populated path),
real :func:`scitex_live_paper.bundle.load`. No mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_live_paper import PaperState, bundle as bundle_module
from scitex_live_paper.bundle import BundleError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"  # has NO state.yaml
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"  # has state.yaml


# ──────────────────────────────────────────────────────────────────
# state.yaml ABSENT — preprint default
# ──────────────────────────────────────────────────────────────────


def test_bundle_min_defaults_to_preprint_when_state_yaml_absent():
    # arrange
    assert not (BUNDLE_MIN / "state.yaml").exists()  # sanity
    # act
    bundle = bundle_module.load(BUNDLE_MIN)
    # assert — absent state.yaml → PaperState() default → stage="preprint"
    assert bundle.paper_state.stage == "preprint"


def test_bundle_min_default_paper_state_has_no_journal_or_doi():
    # arrange / act
    bundle = bundle_module.load(BUNDLE_MIN)
    # assert
    assert bundle.paper_state.journal is None
    assert bundle.paper_state.doi is None
    assert bundle.paper_state.pinned_commit is None


def test_bundle_min_default_paper_state_no_verification_badge():
    # arrange / act
    bundle = bundle_module.load(BUNDLE_MIN)
    # assert — preprint = no badge
    assert bundle.paper_state.show_verification_badge is False
    assert bundle.paper_state.re_verify_enabled is False


# ──────────────────────────────────────────────────────────────────
# state.yaml PRESENT — bundle-accepted fixture
# ──────────────────────────────────────────────────────────────────


def test_bundle_accepted_loads_stage_from_state_yaml():
    # arrange
    assert (BUNDLE_ACCEPTED / "state.yaml").exists()  # sanity
    # act
    bundle = bundle_module.load(BUNDLE_ACCEPTED)
    # assert
    assert bundle.paper_state.stage == "accepted"


def test_bundle_accepted_loads_journal_from_state_yaml():
    # arrange / act
    bundle = bundle_module.load(BUNDLE_ACCEPTED)
    # assert
    assert bundle.paper_state.journal == "eLife"


def test_bundle_accepted_loads_doi_from_state_yaml():
    # arrange / act
    bundle = bundle_module.load(BUNDLE_ACCEPTED)
    # assert
    assert bundle.paper_state.doi == "10.7554/eLife.99999"


def test_bundle_accepted_loads_pinned_commit_from_state_yaml():
    # arrange / act
    bundle = bundle_module.load(BUNDLE_ACCEPTED)
    # assert
    assert bundle.paper_state.pinned_commit == "deadbeefcafef00d12345678"


def test_bundle_accepted_state_drives_verification_badge_visibility():
    # arrange / act
    state = bundle_module.load(BUNDLE_ACCEPTED).paper_state
    # assert — accepted → badge visible
    assert state.show_verification_badge is True


def test_bundle_accepted_state_enables_re_verify():
    # arrange / act
    state = bundle_module.load(BUNDLE_ACCEPTED).paper_state
    # assert — accepted + pinned_commit → re-verify enabled
    assert state.re_verify_enabled is True


def test_bundle_accepted_header_label_names_journal():
    # arrange / act
    state = bundle_module.load(BUNDLE_ACCEPTED).paper_state
    # assert
    assert state.header_label() == "Accepted by eLife"


# ──────────────────────────────────────────────────────────────────
# state.yaml malformed — loud BundleError
# ──────────────────────────────────────────────────────────────────


def _make_bundle_with_state(tmp_path: Path, state_yaml_text: str) -> Path:
    """Build a real bundle dir backed by bundle-min + custom state.yaml."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    # Mirror the minimum required files from bundle-min.
    for name in ("claims.json", "dag.mmd", "provenance.yaml", "manuscript.pdf"):
        (bundle / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle / "figz").mkdir()
    (bundle / "state.yaml").write_text(state_yaml_text, encoding="utf-8")
    return bundle


def test_state_yaml_unknown_stage_raises_bundle_error(tmp_path):
    # arrange
    bundle_path = _make_bundle_with_state(tmp_path, "stage: pre-publication\n")
    # act / assert — operator typo must fail loud, not silently default
    with pytest.raises(BundleError, match="unknown stage"):
        bundle_module.load(bundle_path)


def test_state_yaml_non_string_stage_raises_bundle_error(tmp_path):
    # arrange
    bundle_path = _make_bundle_with_state(tmp_path, "stage: 42\n")
    # act / assert
    with pytest.raises(BundleError, match="'stage' must be a string"):
        bundle_module.load(bundle_path)


def test_state_yaml_non_mapping_top_level_raises_bundle_error(tmp_path):
    # arrange — a bare list is not a state document
    bundle_path = _make_bundle_with_state(tmp_path, "- accepted\n")
    # act / assert
    with pytest.raises(BundleError, match="top level must be a mapping"):
        bundle_module.load(bundle_path)


def test_state_yaml_non_string_journal_raises_bundle_error(tmp_path):
    # arrange
    bundle_path = _make_bundle_with_state(
        tmp_path,
        "stage: accepted\njournal: 42\n",
    )
    # act / assert
    with pytest.raises(BundleError, match="'journal' must be a string"):
        bundle_module.load(bundle_path)


# ──────────────────────────────────────────────────────────────────
# state.yaml minimal valid — only stage, other fields default to None
# ──────────────────────────────────────────────────────────────────


def test_state_yaml_minimal_valid_drops_to_preprint(tmp_path):
    # arrange
    bundle_path = _make_bundle_with_state(tmp_path, "stage: preprint\n")
    # act
    state = bundle_module.load(bundle_path).paper_state
    # assert
    assert state.stage == "preprint"
    assert state.journal is None
    assert state.doi is None


def test_state_yaml_empty_file_falls_back_to_default(tmp_path):
    # arrange — whitespace-only file
    bundle_path = _make_bundle_with_state(tmp_path, "   \n")
    # act
    state = bundle_module.load(bundle_path).paper_state
    # assert — empty → default, not BundleError
    assert state.stage == "preprint"


def test_state_yaml_with_null_optional_fields_treated_as_absent(tmp_path):
    # arrange — explicit YAML null is equivalent to leaving the key out
    bundle_path = _make_bundle_with_state(
        tmp_path,
        "stage: accepted\njournal: null\ndoi: null\n",
    )
    # act
    state = bundle_module.load(bundle_path).paper_state
    # assert
    assert state.stage == "accepted"
    assert state.journal is None
    assert state.doi is None


def test_state_yaml_ignores_unknown_keys(tmp_path):
    # arrange — forward-compat: hosts may add private metadata to state.yaml
    bundle_path = _make_bundle_with_state(
        tmp_path,
        "stage: preprint\nhost_internal_key: anything\n",
    )
    # act — must not raise
    state = bundle_module.load(bundle_path).paper_state
    # assert
    assert state.stage == "preprint"


# ──────────────────────────────────────────────────────────────────
# Every valid stage parses
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "stage",
    ["draft", "preprint", "in_review", "accepted", "published"],
)
def test_state_yaml_accepts_every_valid_stage(tmp_path, stage):
    # arrange
    bundle_path = _make_bundle_with_state(tmp_path, f"stage: {stage}\n")
    # act
    state = bundle_module.load(bundle_path).paper_state
    # assert
    assert state.stage == stage


# ──────────────────────────────────────────────────────────────────
# Bundle dataclass surface — new field shape
# ──────────────────────────────────────────────────────────────────


def test_bundle_paper_state_field_defaults_to_preprint_via_factory():
    # arrange — instantiate Bundle without supplying paper_state
    from scitex_live_paper import Bundle

    bundle = Bundle(
        root=BUNDLE_MIN,
        claims=[],
        dag="",
        provenance={},
        manuscript_path=BUNDLE_MIN / "manuscript.pdf",
        figz_dir=BUNDLE_MIN / "figz",
    )
    # act / assert — factory default kicks in
    assert isinstance(bundle.paper_state, PaperState)
    assert bundle.paper_state.stage == "preprint"


def test_bundle_paper_state_field_carries_explicit_value():
    # arrange
    from scitex_live_paper import Bundle

    explicit = PaperState(stage="published", journal="Nature", doi="10.x")
    bundle = Bundle(
        root=BUNDLE_MIN,
        claims=[],
        dag="",
        provenance={},
        manuscript_path=BUNDLE_MIN / "manuscript.pdf",
        figz_dir=BUNDLE_MIN / "figz",
        paper_state=explicit,
    )
    # act / assert
    assert bundle.paper_state is explicit
