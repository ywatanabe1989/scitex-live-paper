"""No-mocks tests for PR #4 — `Bundle.paper_state` wired into the renderers.

PR #5 landed `Bundle.paper_state` from the bundle's optional
`state.yaml`. This PR makes the renderers actually flex on it:

- Landing page header carries the stage label
  (``"Preprint"`` / ``"Accepted by eLife"`` / ``"Nature · DOI ..."``).
- Verification badge is visible only when ``show_verification_badge`` is True.
- Landing page meta dl exposes stage / journal / doi / pinned_commit.
- `bundle-info` API surfaces the full `paper_state` dict.

All collaborators are real: on-disk fixtures (``bundle-min`` for
preprint, ``bundle-accepted`` for eLife), real `bundle.load()`, real
Jinja2 render. No `monkeypatch`, no `unittest.mock`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper._renderer.index import render_index

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"  # absent state.yaml → preprint default
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"  # accepted at eLife


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _render(tmp_path: Path, bundle_path: Path) -> str:
    """Render the landing page and return the emitted HTML body."""
    bundle = bundle_module.load(bundle_path)
    artifacts = render_index(bundle, tmp_path / "site")
    return artifacts.index_html.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────
# Preprint default (bundle-min has no state.yaml)
# ──────────────────────────────────────────────────────────────────


def test_landing_page_preprint_carries_data_paper_stage_preprint(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    assert 'data-paper-stage="preprint"' in body


def test_landing_page_preprint_shows_preprint_label(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    assert "Preprint" in body


def test_landing_page_preprint_hides_verification_badge(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    assert "lp-verification-badge" not in body


def test_landing_page_preprint_meta_shows_stage_preprint(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    # `lp-paper-state-meta` is the dd that carries the stage in the meta dl
    assert 'class="lp-paper-state-meta"' in body
    assert ">preprint<" in body


def test_landing_page_preprint_meta_omits_journal_dt(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    assert "<dt>Journal</dt>" not in body
    assert "<dt>DOI</dt>" not in body
    assert "<dt>Re-verify pin</dt>" not in body


# ──────────────────────────────────────────────────────────────────
# Accepted bundle (bundle-accepted has state.yaml @ eLife)
# ──────────────────────────────────────────────────────────────────


def test_landing_page_accepted_carries_data_paper_stage_accepted(tmp_path):
    body = _render(tmp_path, BUNDLE_ACCEPTED)
    assert 'data-paper-stage="accepted"' in body


def test_landing_page_accepted_shows_accepted_by_journal_label(tmp_path):
    body = _render(tmp_path, BUNDLE_ACCEPTED)
    assert "Accepted by eLife" in body


def test_landing_page_accepted_shows_verification_badge(tmp_path):
    body = _render(tmp_path, BUNDLE_ACCEPTED)
    assert "lp-verification-badge" in body
    # Re-verify enabled because state.yaml carries a pinned_commit.
    assert 'data-re-verify-enabled="true"' in body


def test_landing_page_accepted_meta_lists_journal(tmp_path):
    body = _render(tmp_path, BUNDLE_ACCEPTED)
    assert "<dt>Journal</dt>" in body
    assert "eLife" in body


def test_landing_page_accepted_meta_lists_doi(tmp_path):
    body = _render(tmp_path, BUNDLE_ACCEPTED)
    assert "<dt>DOI</dt>" in body
    assert "10.7554/eLife.99999" in body


def test_landing_page_accepted_meta_lists_pinned_commit(tmp_path):
    body = _render(tmp_path, BUNDLE_ACCEPTED)
    assert "<dt>Re-verify pin</dt>" in body
    assert "deadbeefcafef00d12345678" in body


# ──────────────────────────────────────────────────────────────────
# Verification badge: shown iff PaperState.show_verification_badge
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "stage, badge_shown",
    [
        ("draft", False),
        ("preprint", False),
        ("in_review", False),
        ("accepted", True),
        ("published", True),
    ],
)
def test_verification_badge_visibility_per_stage(tmp_path, stage, badge_shown):
    # arrange — synthesize a bundle with a given stage via state.yaml
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    for name in ("claims.json", "dag.mmd", "provenance.yaml", "manuscript.pdf"):
        (bundle_dir / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle_dir / "figz").mkdir()
    (bundle_dir / "state.yaml").write_text(f"stage: {stage}\n", encoding="utf-8")

    # act
    body = _render(tmp_path, bundle_dir)

    # assert
    if badge_shown:
        assert "lp-verification-badge" in body
    else:
        assert "lp-verification-badge" not in body


# ──────────────────────────────────────────────────────────────────
# Verification badge: re_verify_enabled flag carried to data attribute
# ──────────────────────────────────────────────────────────────────


def test_verification_badge_re_verify_disabled_without_pinned_commit(tmp_path):
    # arrange — accepted but no pinned_commit → badge visible, re-verify off
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    for name in ("claims.json", "dag.mmd", "provenance.yaml", "manuscript.pdf"):
        (bundle_dir / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle_dir / "figz").mkdir()
    (bundle_dir / "state.yaml").write_text(
        "stage: accepted\njournal: Nature\n",
        encoding="utf-8",
    )

    body = _render(tmp_path, bundle_dir)

    assert "lp-verification-badge" in body
    assert 'data-re-verify-enabled="false"' in body


# ──────────────────────────────────────────────────────────────────
# Published stage with DOI + journal — header label composition
# ──────────────────────────────────────────────────────────────────


def test_published_stage_header_label_joins_journal_and_doi(tmp_path):
    # arrange
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    for name in ("claims.json", "dag.mmd", "provenance.yaml", "manuscript.pdf"):
        (bundle_dir / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle_dir / "figz").mkdir()
    (bundle_dir / "state.yaml").write_text(
        'stage: published\njournal: Nature\ndoi: "10.1038/x"\n',
        encoding="utf-8",
    )

    body = _render(tmp_path, bundle_dir)

    # assert — header_label composition per PaperState.header_label
    assert "Nature · DOI: 10.1038/x" in body


# ──────────────────────────────────────────────────────────────────
# Regression: existing index sections still rendered
# ──────────────────────────────────────────────────────────────────


def test_landing_page_still_links_to_viewer_claims_dag(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    assert "viewer.html" in body
    assert "claims.html" in body
    assert "dag.html" in body


def test_landing_page_still_shows_manuscript_filename(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    assert "manuscript.pdf" in body


def test_landing_page_still_shows_total_claim_count(tmp_path):
    body = _render(tmp_path, BUNDLE_MIN)
    # bundle-min ships three claims
    assert ">3<" in body or " 3 claims" in body
