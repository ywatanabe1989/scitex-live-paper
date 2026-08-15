"""STX-TQ tests for the clew 1.4 ``unsourced`` status fold.

clew 0.8.1 (claims.json 1.4) adds a new resting claim status,
``unsourced``. Per the operator decision it shares the amber
"questionable" bucket with ``suspect`` instead of getting its own row.

The fold is a COLOUR-LAYER ALIAS, not a status normalize, and these
tests pin BOTH halves of it -- because either half passing alone is a
bug that looks like success:

  - the colour folds to amber/suspect, AND
  - the literal word "unsourced" still reaches the operator's screen.

A naive implementation (rewriting the status to "suspect" at ingest, the
way legacy "partial" is rewritten) would satisfy a colour-only test
while silently destroying the distinction the operator asked to keep.

The last group guards the coarse-palette regression. clew ships a
SECOND, coarse ``display_color``/``display_group`` palette that buckets
mismatch+missing into "failed" and registered into "suspect". Colouring
from it would revert the v1.3 palette (PR #51): registered grey would
turn amber and missing would lose its own hue. These tests fail loudly
if that ever happens.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper._cli import _KNOWN_CLAIM_STATUSES
from scitex_live_paper._django.handlers.reverify import _normalize_result
from scitex_live_paper._renderer.claims import render_claims_sidebar

_TESTS_DIR = Path(__file__).resolve().parents[1]
_SRC = _TESTS_DIR.parent / "src" / "scitex_live_paper"

BUNDLE_MIN = _TESTS_DIR / "fixtures" / "bundle-min"

CLAIMS_CSS = (_SRC / "_renderer" / "assets" / "claims.css").read_text(encoding="utf-8")
VIEWER_JS = (_SRC / "_renderer" / "assets" / "viewer.js").read_text(encoding="utf-8")
SPA_CSS = (
    _SRC / "_django" / "static" / "live_paper" / "css" / "viewer.css"
).read_text(encoding="utf-8")

# The alias both stylesheets must carry. An alias rather than a repeated
# literal, so the fold tracks suspect through any future hue change.
ALIAS_RE = r"--lp-status-unsourced:\s*var\(--lp-status-suspect\)\s*;"

# clew's own fine palette gives `unsourced` this hue. We deliberately do
# NOT use it -- the operator asked for a single amber bucket, so its
# appearance would mean someone wired up clew's per-status hue and
# quietly un-did the fold.
CLEW_UNSOURCED_HUE = "#b26a00"

_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _declarations_only(css: str) -> str:
    """Strip CSS comments, leaving only what the browser acts on.

    The stylesheets deliberately NAME clew's unsourced hue in a comment,
    to record that we chose not to use it. The regression guard is about
    a hue being APPLIED, so it must look at declarations only -- a
    mention in prose is documentation, not a palette change.
    """
    return _CSS_COMMENT_RE.sub("", css)


CLAIMS_CSS_DECLS = _declarations_only(CLAIMS_CSS)
SPA_CSS_DECLS = _declarations_only(SPA_CSS)


def _bundle_with_unsourced_claim(tmp_path: Path) -> Path:
    """Copy the canonical fixture and append one ``unsourced`` claim."""
    root = tmp_path / "bundle-unsourced"
    shutil.copytree(BUNDLE_MIN, root)
    claims_path = root / "claims.json"
    data = json.loads(claims_path.read_text(encoding="utf-8"))
    data["claims"].append(
        {
            "claim_id": "claim_unsourced0001",
            "file_path": "main.tex",
            "line_number": 210,
            "claim_type": "value",
            "claim_value": "d = 0.42",
            "source_session": None,
            "source_file": None,
            "source_hash": None,
            # clew 1.4 also adds a per-claim `grounded` flag; it must
            # survive as an extra rather than breaking the load.
            "grounded": False,
            "status": "unsourced",
        }
    )
    claims_path.write_text(json.dumps(data), encoding="utf-8")
    return root


def _render(tmp_path: Path) -> str:
    root = _bundle_with_unsourced_claim(tmp_path)
    loaded = bundle_module.load(root)
    artifacts = render_claims_sidebar(loaded, tmp_path / "site")
    return artifacts.claims_html.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Half 1 -- the colour folds to amber
# ---------------------------------------------------------------------------


def test_static_css_aliases_unsourced_to_the_suspect_var():
    # Arrange
    pattern = ALIAS_RE
    # Act
    found = re.search(pattern, CLAIMS_CSS)
    # Assert
    assert found is not None


def test_spa_css_aliases_unsourced_to_the_suspect_var():
    # Arrange: the dark theme's suspect hex need not equal the static
    # renderer's, which is precisely why this is an alias
    pattern = ALIAS_RE
    # Act
    found = re.search(pattern, SPA_CSS)
    # Assert
    assert found is not None


def test_static_css_colours_the_status_dot_for_unsourced():
    # Arrange
    selector = '.lp-status-dot[data-status="unsourced"]'
    # Act
    present = selector in CLAIMS_CSS
    # Assert
    assert present


def test_static_css_colours_the_detail_row_for_unsourced():
    # Arrange
    selector = '.lp-claim-detail dd[data-status="unsourced"]'
    # Act
    present = selector in CLAIMS_CSS
    # Assert
    assert present


def test_spa_css_colours_the_claim_border_for_unsourced():
    # Arrange
    selector = '.lp-claim[data-status="unsourced"]'
    # Act
    present = selector in SPA_CSS
    # Assert
    assert present


def test_spa_css_colours_the_status_pill_for_unsourced():
    # Arrange
    selector = '.lp-claim-status[data-status="unsourced"]'
    # Act
    present = selector in SPA_CSS
    # Assert
    assert present


def test_viewer_js_maps_unsourced_onto_the_suspect_class():
    # Arrange: quote-agnostic -- the formatter normalizes quoting, and
    # the contract here is the mapping. Without this entry classFor()
    # returns "" and an unsourced overlay anchor draws unstyled.
    pattern = r"""unsourced:\s*["']lp-status-suspect["']"""
    # Act
    found = re.search(pattern, VIEWER_JS)
    # Assert
    assert found is not None


# ---------------------------------------------------------------------------
# Half 2 -- the word "unsourced" survives to the screen
# ---------------------------------------------------------------------------


def test_loader_does_not_normalize_unsourced_away(tmp_path: Path):
    # Arrange
    root = _bundle_with_unsourced_claim(tmp_path)
    # Act
    loaded = bundle_module.load(root)
    statuses = {c.claim_id: c.status for c in loaded.claims}
    # Assert: unlike legacy "partial", this status survives ingest
    assert statuses["claim_unsourced0001"] == "unsourced"


def test_rendered_detail_row_shows_the_literal_word_unsourced(tmp_path: Path):
    # Arrange
    pattern = r'<dd data-status="unsourced">\s*unsourced\s*</dd>'
    # Act
    html = _render(tmp_path)
    # Assert: colour folds, word does not. If this fails while the
    # colour tests pass, someone normalized the status instead of
    # aliasing the hue.
    assert re.search(pattern, html) is not None


def test_rendered_status_label_is_not_relabelled_as_suspect(tmp_path: Path):
    # Arrange: the fixture contains exactly one genuinely-suspect claim,
    # so the unsourced one must not have joined it
    pattern = '<dd data-status="suspect">'
    # Act
    html = _render(tmp_path)
    # Assert
    assert html.count(pattern) == 1


def test_clew_grounded_field_survives_as_an_extra(tmp_path: Path):
    # Arrange: clew 1.4's per-claim `grounded` is additive, so
    # Claim.extras absorbs it rather than the loader rejecting the row
    root = _bundle_with_unsourced_claim(tmp_path)
    # Act
    loaded = bundle_module.load(root)
    claim = next(c for c in loaded.claims if c.claim_id == "claim_unsourced0001")
    # Assert
    assert claim.extras.get("grounded") is False


# ---------------------------------------------------------------------------
# The live re-verify path must agree with the rendered bundle
# ---------------------------------------------------------------------------


def test_reverify_passes_unsourced_through_verbatim():
    # Arrange: clew's nested success shape carrying the new status
    result = {"claim": {"status": "unsourced", "verified_at": None}}
    # Act
    shaped = _normalize_result("claim_unsourced0001", "abc123", result)
    # Assert: NOT rewritten to "suspect" -- otherwise a live re-verify
    # would disagree with the rendered sidebar for the very same claim
    assert shaped["status"] == "unsourced"


def test_reverify_still_normalizes_legacy_partial():
    # Arrange: the genuine rename must keep being normalized; this is
    # the contrast that makes the unsourced pass-through deliberate
    result = {"claim": {"status": "partial", "verified_at": None}}
    # Act
    shaped = _normalize_result("claim_x", "abc123", result)
    # Assert
    assert shaped["status"] == "suspect"


# ---------------------------------------------------------------------------
# CLI validation vocabulary
# ---------------------------------------------------------------------------


def test_cli_accepts_unsourced_as_a_resting_status():
    # Arrange
    status = "unsourced"
    # Act
    known = status in _KNOWN_CLAIM_STATUSES
    # Assert
    assert known


def test_cli_still_rejects_not_found_as_a_resting_status():
    # Arrange: not_found is a lookup verdict, never a claims.json status
    status = "not_found"
    # Act
    known = status in _KNOWN_CLAIM_STATUSES
    # Assert
    assert not known


# ---------------------------------------------------------------------------
# Coarse-palette regression guards
# ---------------------------------------------------------------------------


def test_static_css_never_applies_clews_own_unsourced_hue():
    # Arrange
    hue = CLEW_UNSOURCED_HUE
    # Act
    present = hue in CLAIMS_CSS_DECLS.lower()
    # Assert
    assert not present


def test_spa_css_never_applies_clews_own_unsourced_hue():
    # Arrange
    hue = CLEW_UNSOURCED_HUE
    # Act
    present = hue in SPA_CSS_DECLS.lower()
    # Assert
    assert not present


def test_registered_stays_grey_in_static_css():
    # Arrange: the coarse palette buckets registered -> suspect, so if
    # we ever colour from display_color this turns amber
    pattern = r"--lp-status-registered:\s*#6e7781\s*;"
    # Act
    found = re.search(pattern, CLAIMS_CSS)
    # Assert
    assert found is not None


def test_registered_stays_grey_in_spa_css():
    # Arrange
    pattern = r"--lp-status-registered:\s*#6e7681\s*;"
    # Act
    found = re.search(pattern, SPA_CSS)
    # Assert
    assert found is not None


def test_missing_keeps_its_own_dark_red_in_static_css():
    # Arrange: the coarse palette folds missing into "failed" alongside
    # mismatch; v1.3 gives it its own hue
    pattern = r"--lp-status-missing:\s*#a40e26\s*;"
    # Act
    found = re.search(pattern, CLAIMS_CSS)
    # Assert
    assert found is not None


def test_missing_keeps_its_own_dark_red_in_spa_css():
    # Arrange
    pattern = r"--lp-status-missing:\s*#a40e26\s*;"
    # Act
    found = re.search(pattern, SPA_CSS)
    # Assert
    assert found is not None


def test_m4_badge_still_defines_its_own_vocabulary():
    # Arrange: guards the next test from passing vacuously if the
    # selectors are ever renamed
    pattern = r"\.lp-re-review-badge\[data-status=\"([^\"]+)\"\]"
    # Act
    badge_statuses = set(re.findall(pattern, SPA_CSS))
    # Assert
    assert "verified" in badge_statuses


def test_unsourced_never_leaks_into_the_m4_badge_vocabulary():
    # Arrange: {verified, concerns, contradicted, stale} is a SEPARATE
    # paper-level vocabulary; unsourced is a claim status
    pattern = r"\.lp-re-review-badge\[data-status=\"([^\"]+)\"\]"
    # Act
    badge_statuses = set(re.findall(pattern, SPA_CSS))
    # Assert
    assert "unsourced" not in badge_statuses
