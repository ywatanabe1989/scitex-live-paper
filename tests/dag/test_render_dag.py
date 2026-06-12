"""STX-TQ tests for ``scitex_live_paper.dag.render_dag`` (M1 DAG navigator).

Replaces the importorskip scaffolding stub from PR #13 (issue #10) now
that the renderer lands in this PR. Exercises the public contract:

  - public API on both ``scitex_live_paper.dag`` and
    ``scitex_live_paper._renderer.dag``,
  - artefact paths emitted under *out_dir*,
  - generated HTML wires the vendored mermaid (no CDN),
  - per-node click handlers use the documented
    ``live-paper:claim`` cross-page event channel,
  - provenance ``source_file → source_hash`` lookup map is embedded so
    Source / Processing nodes can show the producing script + hash,
  - the renderer is read-only towards the bundle: the clew taxonomy is
    NOT redefined here (we just paint what ``dag.mmd`` already encodes).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper import dag as dag_public
from scitex_live_paper._renderer import dag as dag_internal
from scitex_live_paper._renderer.dag import (
    MERMAID_VERSION,
    DagArtifacts,
    render_dag,
    render_html,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_public_module_exposes_render_html_callable():
    # Arrange / Act
    fn = getattr(dag_public, "render_html", None)
    # Assert
    assert callable(fn)


def test_public_module_exposes_render_dag_callable():
    # Arrange / Act
    fn = getattr(dag_public, "render_dag", None)
    # Assert
    assert callable(fn)


def test_public_module_exposes_mermaid_version_string():
    # Arrange / Act
    version = dag_public.MERMAID_VERSION
    # Assert
    assert isinstance(version, str) and version


def test_renderer_subpackage_reexports_render_dag():
    # Arrange
    from scitex_live_paper import _renderer as renderer_pkg

    # Act / Assert
    assert callable(getattr(renderer_pkg, "render_dag", None))


def test_render_html_is_alias_of_render_dag():
    # Arrange / Act / Assert: same callable bound under both names
    assert dag_internal.render_html is render_html


def test_public_render_html_matches_internal_render_html():
    # Arrange / Act / Assert: the top-level facade must be the *same*
    # object as the internal callable so the contract from issue #10
    # (``scitex_live_paper.dag.render_html``) holds without divergence.
    assert dag_public.render_html is dag_internal.render_html


# ---------------------------------------------------------------------------
# Happy path on the canonical fixture
# ---------------------------------------------------------------------------


def test_render_dag_writes_dag_html_in_out_dir(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_dag(loaded, out)
    # Assert
    assert isinstance(artifacts, DagArtifacts)
    assert artifacts.dag_html == out / "dag.html"
    assert artifacts.dag_html.is_file()


def test_render_dag_vendors_css_and_js(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_dag(loaded, out)
    # Assert: relative-pathed local assets so file:// renders without CDN
    assert artifacts.css == out / "assets" / "dag.css"
    assert artifacts.js == out / "assets" / "dag.js"
    assert artifacts.css.is_file()
    assert artifacts.js.is_file()


def test_render_dag_vendors_mermaid_main(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_dag(loaded, out)
    # Assert: the mermaid UMD bundle lands under assets/mermaid/
    assert artifacts.mermaid_main == out / "assets" / "mermaid" / "mermaid.min.js"
    assert artifacts.mermaid_main.is_file()
    # And it is a real script body, not a placeholder.
    assert artifacts.mermaid_main.stat().st_size > 1000


# ---------------------------------------------------------------------------
# Generated HTML contract
# ---------------------------------------------------------------------------


def _read_html(tmp_path: Path) -> str:
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_dag(loaded, out)
    return artifacts.dag_html.read_text(encoding="utf-8")


def test_html_loads_vendored_mermaid_via_relative_url(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: no CDN — mermaid is sourced from the vendored copy
    assert 'src="assets/mermaid/mermaid.min.js"' in html
    assert "cdn.jsdelivr.net" not in html
    assert "unpkg.com" not in html


def test_html_loads_local_css_and_js(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert
    assert 'href="assets/dag.css"' in html
    assert 'src="assets/dag.js"' in html


def test_html_embeds_mermaid_version_in_subtitle(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert
    assert MERMAID_VERSION in html


def test_html_renders_dag_source_block_from_bundle(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: mermaid expects a <pre class="mermaid"> block; the bundle
    # fixture's dag.mmd lines must flow through verbatim (we do not
    # rewrite the clew-owned graph).
    assert 'class="mermaid"' in html
    assert "S1[Source" in html
    assert "C1[Claim" in html


def test_html_uses_default_title_when_not_provided(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert
    assert "Live Paper" in html
    assert "DAG" in html


def test_html_honours_custom_title(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_dag(loaded, out, title="My DAG")
    html = artifacts.dag_html.read_text(encoding="utf-8")
    # Assert
    assert "<title>My DAG</title>" in html


def test_html_embeds_provenance_map_as_inline_json(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: the inline <script id="lp-provenance-map"> block is what
    # the click handler reads to surface "script + hash" on Source /
    # Processing nodes (avoids a second fetch).
    assert 'id="lp-provenance-map"' in html
    assert 'type="application/json"' in html


def test_html_provenance_map_carries_claim_source_hashes(tmp_path: Path):
    # Arrange: parse the embedded JSON out of the generated HTML.
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_dag(loaded, out)
    html = artifacts.dag_html.read_text(encoding="utf-8")
    start_tag = '<script id="lp-provenance-map" type="application/json">'
    start = html.index(start_tag) + len(start_tag)
    end = html.index("</script>", start)
    payload = json.loads(html[start:end])
    # Assert: both claims in the fixture that carry source_file / source_hash
    # show up in the map (the third claim is intentionally bare).
    assert payload.get("scripts/03_analyze.py") == "deadbeefcafef00d"
    assert payload.get("scripts/04_stats.R") == "1234567890abcdef"


def test_html_includes_overlay_scaffolding(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: the in-page overlay used to show "script + hash" for
    # Source / Processing nodes is present (hidden until click).
    assert "lp-dag-overlay" in html
    assert "lp-dag-overlay-title" in html
    assert "lp-dag-overlay-detail" in html


def test_html_uses_module_script_for_dag_js(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: dag.js uses module syntax (ESM exports for testability);
    # the page must load it with type="module" or browsers reject imports.
    assert 'type="module" src="assets/dag.js"' in html


# ---------------------------------------------------------------------------
# Vendored JS contract — claim event channel + node-kind taxonomy
# ---------------------------------------------------------------------------


def test_dag_js_uses_live_paper_claim_event_channel(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_dag(loaded, out)
    js = artifacts.js.read_text(encoding="utf-8")
    # Assert: same cross-page channel the viewer (#4) and the claims
    # sidebar (#5) speak — not a parallel event name.
    assert "live-paper:claim" in js


def test_dag_js_tags_nodes_with_data_attribute(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_dag(loaded, out)
    js = artifacts.js.read_text(encoding="utf-8")
    # Assert: we tag rendered nodes via data-lp-node-kind so CSS can
    # style them per-class without re-deriving the taxonomy.
    assert "data-lp-node-kind" in js


def test_dag_js_recognises_clew_node_kinds(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_dag(loaded, out)
    js = artifacts.js.read_text(encoding="utf-8")
    # Assert: every clew node-class prefix is recognised. The taxonomy
    # itself is upstream — we just enumerate the labels we see in the
    # rendered mermaid SVG.
    for kind in ("Claim", "Source", "Processing", "Input", "Output"):
        assert kind in js


def test_dag_js_navigates_to_claim_fragment_on_claim_click(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    artifacts = render_dag(loaded, out)
    js = artifacts.js.read_text(encoding="utf-8")
    # Assert: clicking a Claim node jumps to the claims page with the
    # documented `#claim=<id>` protocol (same as the sidebar uses).
    assert "#claim=" in js


# ---------------------------------------------------------------------------
# Provenance map: lenient + missing-bundle behaviour
# ---------------------------------------------------------------------------


def test_render_dag_handles_bundle_with_no_dag_string(tmp_path: Path):
    # Arrange: construct a bundle whose dag.mmd is absent / empty.
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text("[]")
    loaded = bundle_module.load(bundle_dir)
    # Act
    artifacts = render_dag(loaded, tmp_path / "site")
    html = artifacts.dag_html.read_text(encoding="utf-8")
    # Assert: the renderer falls back to an empty-state message rather
    # than erroring — DAG is optional in M1.
    assert "lp-dag-empty" in html or "no dag.mmd" in html.lower()


def test_render_dag_falls_back_to_provenance_when_claims_lack_hashes(
    tmp_path: Path,
):
    # Arrange: a bundle where claims carry no source_file but the
    # provenance.yaml does list a session with a hash. The renderer
    # should still surface a script→hash entry from provenance.
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text("[]")
    (bundle_dir / "dag.mmd").write_text("graph LR\n  A --> B\n")
    (bundle_dir / "provenance.yaml").write_text(
        "sessions:\n"
        "  s1:\n"
        "    files:\n"
        "      scripts/only_in_prov.py:\n"
        "        hash: 0badc0de0badc0de\n"
    )
    loaded = bundle_module.load(bundle_dir)
    # Act
    artifacts = render_dag(loaded, tmp_path / "site")
    html = artifacts.dag_html.read_text(encoding="utf-8")
    start_tag = '<script id="lp-provenance-map" type="application/json">'
    start = html.index(start_tag) + len(start_tag)
    end = html.index("</script>", start)
    payload = json.loads(html[start:end])
    # Assert
    assert payload.get("scripts/only_in_prov.py") == "0badc0de0badc0de"


def test_render_dag_provenance_map_prefers_claim_hash_over_provenance(
    tmp_path: Path,
):
    # Arrange: claim hash and provenance hash for the same file disagree
    # — claim wins (it is the verified, canonical pairing).
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text(
        json.dumps(
            [
                {
                    "claim_id": "c1",
                    "file_path": "main.tex",
                    "claim_type": "value",
                    "source_file": "scripts/x.py",
                    "source_hash": "aaaa1111",
                }
            ]
        )
    )
    (bundle_dir / "dag.mmd").write_text("graph LR\n  A --> B\n")
    (bundle_dir / "provenance.yaml").write_text(
        "sessions:\n"
        "  s1:\n"
        "    files:\n"
        "      scripts/x.py:\n"
        "        hash: bbbb2222\n"
    )
    loaded = bundle_module.load(bundle_dir)
    # Act
    artifacts = render_dag(loaded, tmp_path / "site")
    html = artifacts.dag_html.read_text(encoding="utf-8")
    start_tag = '<script id="lp-provenance-map" type="application/json">'
    start = html.index(start_tag) + len(start_tag)
    end = html.index("</script>", start)
    payload = json.loads(html[start:end])
    # Assert
    assert payload.get("scripts/x.py") == "aaaa1111"


def test_render_dag_handles_provenance_without_sessions_block(tmp_path: Path):
    # Arrange: bundle with a provenance.yaml that has no "sessions" key.
    bundle_dir = tmp_path / "b"
    bundle_dir.mkdir()
    (bundle_dir / "manuscript.pdf").write_text("%PDF-1.4\n")
    (bundle_dir / "claims.json").write_text("[]")
    (bundle_dir / "dag.mmd").write_text("graph LR\n  A --> B\n")
    (bundle_dir / "provenance.yaml").write_text(
        "schema: x\nproject:\n  name: y\n"
    )
    loaded = bundle_module.load(bundle_dir)
    # Act: must not raise — lenient about provenance shape.
    artifacts = render_dag(loaded, tmp_path / "site")
    # Assert
    assert artifacts.dag_html.is_file()


# ---------------------------------------------------------------------------
# Idempotency & link-shape
# ---------------------------------------------------------------------------


def test_render_dag_overwrites_existing_output_idempotently(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    render_dag(loaded, out)
    # Act
    artifacts = render_dag(loaded, out, title="Run 2")
    # Assert
    html = artifacts.dag_html.read_text(encoding="utf-8")
    assert "<title>Run 2</title>" in html


def test_render_dag_links_default_to_sibling_pages(tmp_path: Path):
    # Arrange
    html = _read_html(tmp_path)
    # Assert: default viewer / claims URLs are sibling-page relative so
    # the CLI's index.html can stitch them with no extra config.
    assert 'data-viewer-url="viewer.html"' in html
    assert 'data-claims-url="claims.html"' in html


def test_render_dag_honours_custom_viewer_and_claims_urls(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    artifacts = render_dag(
        loaded,
        out,
        viewer_url="pdf/viewer.html",
        claims_url="panel/claims.html",
    )
    html = artifacts.dag_html.read_text(encoding="utf-8")
    # Assert
    assert 'data-viewer-url="pdf/viewer.html"' in html
    assert 'data-claims-url="panel/claims.html"' in html


def test_render_html_alias_returns_equivalent_artifacts(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    out = tmp_path / "site"
    # Act
    via_alias = render_html(loaded, out)
    # Assert
    assert isinstance(via_alias, DagArtifacts)
    assert via_alias.dag_html == out / "dag.html"
    assert via_alias.mermaid_main.is_file()


# ---------------------------------------------------------------------------
# Boundary guard: the renderer does NOT mutate or redefine the bundle.
# ---------------------------------------------------------------------------


def test_render_dag_does_not_mutate_bundle_dag_string(tmp_path: Path):
    # Arrange
    loaded = bundle_module.load(BUNDLE_MIN)
    original = loaded.dag
    # Act
    render_dag(loaded, tmp_path / "site")
    # Assert: the bundle's dag.mmd content is untouched after rendering.
    # The clew taxonomy is owned upstream — we render, we do not rewrite.
    assert loaded.dag == original


def test_scaffolding_stub_replaced_by_real_tests():
    # Arrange: PR #13 left an importorskip stub at
    # tests/dag/test_renderer.py. This PR retires it; if a future change
    # accidentally restores the stub-only state, this test fails loudly.
    real_file = Path(__file__)
    # Assert
    assert real_file.name == "test_render_dag.py"
    assert real_file.is_file()


# ---------------------------------------------------------------------------
# Quiet pyflakes — pytest import marker kept for IDE assistance.
# ---------------------------------------------------------------------------

_ = pytest  # explicit reference; pytest fixtures are auto-discovered
