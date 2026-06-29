"""STX-TQ tests for ``scitex_live_paper.claims.render_html`` (M1 sidebar).

Replaces the importorskip scaffolding stub from PR #13 (issue #10) now
that the renderer lands in this PR. Exercises the public contract:

  - public API on both ``scitex_live_paper.claims`` and
    ``scitex_live_paper._renderer.claims``,
  - artefact paths emitted under *out_dir*,
  - generated HTML uses clew-owned status strings (no parallel enum),
  - per-claim panel shows detail fields,
  - "Re-verify" button is disabled in M1 with a "Coming in M2" tooltip,
  - viewer-jump link uses the ``viewer.html#claim=<id>`` protocol.
"""

from __future__ import annotations

import re
from pathlib import Path

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper import claims as claims_public
from scitex_live_paper._renderer import claims as claims_internal
from scitex_live_paper._renderer.claims import (
    ClaimsArtifacts,
    render_claims_sidebar,
    render_html,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_public_module_exposes_render_html_callable():
    # Arrange / Act
    fn = getattr(claims_public, "render_html", None)
    # Assert
    assert callable(fn)


def test_public_module_exposes_render_claims_sidebar_callable():
    # Arrange / Act
    fn = getattr(claims_public, "render_claims_sidebar", None)
    # Assert
    assert callable(fn)


def test_renderer_subpackage_reexports_render_claims_sidebar():
    # Arrange
    from scitex_live_paper import _renderer as renderer_pkg

    # Act / Assert
    assert callable(getattr(renderer_pkg, "render_claims_sidebar", None))


def test_render_html_is_alias_of_render_claims_sidebar():
    # Arrange / Act / Assert: same call returns equivalent results
    assert claims_internal.render_html is render_html


# ---------------------------------------------------------------------------
# Happy path on the canonical fixture
# ---------------------------------------------------------------------------


def test_render_claims_sidebar_writes_claims_html(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_claims_sidebar(loaded, out)
    # Assert
    assert isinstance(artifacts, ClaimsArtifacts)
    assert artifacts.claims_html == out / "claims.html"
    assert artifacts.claims_html.is_file()


def test_render_claims_sidebar_vendors_css_and_js(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_claims_sidebar(loaded, out)
    # Assert: relative-pathed local assets so file:// renders without CDN
    assert artifacts.css == out / "assets" / "claims.css"
    assert artifacts.js == out / "assets" / "claims.js"
    assert artifacts.css.is_file()
    assert artifacts.js.is_file()


# ---------------------------------------------------------------------------
# Generated HTML contract
# ---------------------------------------------------------------------------


def _read_html(tmp_path: Path) -> str:
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_claims_sidebar(loaded, out)
    return artifacts.claims_html.read_text(encoding="utf-8")


def test_html_lists_every_claim_in_bundle(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: each claim_id from the fixture appears as a row data-attribute
    for cid in (
        "claim_a1b2c3d4e5f6",
        "claim_f6e5d4c3b2a1",
        "claim_999888777666",
    ):
        assert f'data-claim-id="{cid}"' in html


def test_html_marks_status_as_clew_owned_string(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: the raw clew status strings flow through as data-status
    # (NOT a hand-rolled enum) so the CSS palette is the single source.
    assert 'data-status="verified"' in html
    assert 'data-status="stale"' in html
    assert 'data-status="registered"' in html


def test_html_renders_status_dot_per_claim(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: one status dot element per claim row
    assert html.count("lp-status-dot") >= 3


def test_html_includes_per_claim_detail_panel(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: detail panel scaffolding present (panel + dl)
    assert "lp-claim-panel" in html
    assert "lp-claim-detail" in html


def test_html_exposes_producing_script_when_present(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: source_file for the verified claim flows into the panel
    assert "scripts/03_analyze.py" in html


def test_html_exposes_hash_when_present(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert
    assert "deadbeefcafef00d" in html


def test_html_reverify_button_is_disabled_with_m2_tooltip(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: "Re-verify" is a stub in M1 — disabled + tooltip says
    # the live verify lands in M2.
    assert "lp-claim-reverify" in html
    assert "disabled" in html
    assert "Coming in M2" in html


def test_html_jump_link_uses_claim_fragment_protocol(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: same `#claim=<id>` protocol the viewer reads on load
    assert "viewer.html#claim=claim_a1b2c3d4e5f6" in html


def test_html_jump_link_honours_custom_viewer_url(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_claims_sidebar(loaded, out, viewer_url="pdf/viewer.html")
    html = artifacts.claims_html.read_text(encoding="utf-8")
    # Assert
    assert "pdf/viewer.html#claim=claim_a1b2c3d4e5f6" in html


def test_html_shows_total_claim_count_in_subtitle(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert
    assert "3 claims" in html


def test_html_honours_custom_title(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_claims_sidebar(loaded, out, title="My Claims")
    html = artifacts.claims_html.read_text(encoding="utf-8")
    # Assert
    assert "<title>My Claims</title>" in html


# ---------------------------------------------------------------------------
# Empty / idempotent / event-channel
# ---------------------------------------------------------------------------


def test_render_claims_sidebar_handles_empty_claim_list(tmp_path: Path):
    # Arrange: build a bundle with claims.json = []
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text("[]")
    loaded = bundle_module.load(bundle_dir)
    # Act
    artifacts = render_claims_sidebar(loaded, tmp_path / "site")
    html = artifacts.claims_html.read_text(encoding="utf-8")
    # Assert: empty-state message renders, no list elements
    assert "lp-claims-empty" in html
    assert "No claims found" in html


def test_render_claims_sidebar_is_idempotent(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    render_claims_sidebar(loaded, out)
    # Act
    artifacts = render_claims_sidebar(loaded, out, title="Second")
    html = artifacts.claims_html.read_text(encoding="utf-8")
    # Assert: second render wins
    assert "<title>Second</title>" in html


def test_sidebar_js_subscribes_to_live_paper_claim_event(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_claims_sidebar(loaded, out)
    js = artifacts.js.read_text(encoding="utf-8")
    # Assert: documented cross-page event channel must be wired
    assert "live-paper:claim" in js


def test_render_html_alias_returns_equivalent_artifacts(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    via_alias = render_html(loaded, out)
    # Assert
    assert isinstance(via_alias, ClaimsArtifacts)
    assert via_alias.claims_html == out / "claims.html"


# ---------------------------------------------------------------------------
# Vendored CSS palette — clew claim-status vocabulary
# ---------------------------------------------------------------------------


def test_vendored_css_covers_clew_claim_status_palette(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    artifacts = render_claims_sidebar(loaded, tmp_path / "site")
    css = artifacts.css.read_text(encoding="utf-8")
    # Assert: one selector per clew claim status (verify_claim / claims.json)
    for status in ("verified", "partial", "mismatch", "missing", "registered", "not_found"):
        assert f'.lp-status-dot[data-status="{status}"]' in css


def test_vendored_css_failed_verification_renders_red(tmp_path: Path):
    # Regression guard: mismatch/missing (a FAILED verification) must map
    # to the red var — the original bug rendered them uncoloured because
    # the palette used a vocabulary clew never emits.
    loaded = bundle_module.load(BUNDLE_MIN)
    artifacts = render_claims_sidebar(loaded, tmp_path / "site")
    css = artifacts.css.read_text(encoding="utf-8")
    # red hex bound to both failure statuses (whitespace-insensitive)
    assert re.search(r"--lp-status-mismatch:\s*#cf222e;", css)
    assert re.search(r"--lp-status-missing:\s*#cf222e;", css)
    # the dot selector points at the mismatch var, not the default
    assert re.search(
        r'\.lp-status-dot\[data-status="mismatch"\]\s*\{\s*background:\s*var\(--lp-status-mismatch\)',
        css,
    )
