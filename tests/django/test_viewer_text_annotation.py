"""Tests for PR (c) — text-layer + annotation-layer + native Ctrl-F find.

These features close the gap writer's pdf-viewer.ts EXPLICITLY left
open (per its own docstring: "Minimal: no text-layer, no annotation-layer,
no find."). With text-layer enabled, the browser's native Ctrl-F walks
the invisible glyph spans and highlights matches — so "find" is free
once text-layer is wired.

Browser-side execution is out of pytest's scope; these tests verify
the JS / CSS source actually wires the PDF.js TextLayer +
AnnotationLayer APIs and ships the supporting CSS. The visual
verification is in the PR's manual test plan.

All collaborators are real — file IO against the installed package's
static tree. No ``monkeypatch``, no ``mock.patch``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _viewer_js() -> str:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return (pkg_root / "_django/static/live_paper/js/viewer.js").read_text(
        encoding="utf-8",
    )


def _viewer_css() -> str:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return (pkg_root / "_django/static/live_paper/css/viewer.css").read_text(
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────────
# Text layer — drives native Ctrl-F + text selection
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_calls_get_text_content():
    # arrange / act
    text = _viewer_js()
    # assert — `page.getTextContent()` is the PDF.js entry for text
    # extraction; no other API gives us text-layer input.
    assert "getTextContent" in text


def test_viewer_js_has_render_text_layer_helper():
    # arrange / act
    text = _viewer_js()
    # assert — internal helper that owns the text-layer DOM
    assert "_renderTextLayer" in text


def test_viewer_js_probes_textlayer_class_with_fallback():
    # arrange / act
    text = _viewer_js()
    # assert — modern PDF.js (5.x) exposes a `TextLayer` class; older
    # builds expose `renderTextLayer()`. Viewer probes both so we work
    # across PDF.js versions without forcing a bundle update.
    assert "pdfjs.TextLayer" in text
    assert "pdfjs.renderTextLayer" in text


def test_viewer_js_passes_textContentSource_to_textlayer():
    # arrange / act
    text = _viewer_js()
    # assert — both APIs take `textContentSource` per PDF.js 5.x
    # rename of the old `textContent` parameter.
    assert "textContentSource" in text


# ──────────────────────────────────────────────────────────────────
# Annotation layer — links, form fields
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_calls_get_annotations():
    # arrange / act
    text = _viewer_js()
    # assert
    assert "getAnnotations" in text


def test_viewer_js_has_render_annotation_layer_helper():
    # arrange / act
    text = _viewer_js()
    # assert
    assert "_renderAnnotationLayer" in text


def test_viewer_js_uses_annotation_layer_class_when_available():
    # arrange / act
    text = _viewer_js()
    # assert — uses the official class; degrades gracefully when absent
    assert "pdfjs.AnnotationLayer" in text


def test_viewer_js_annotation_layer_opens_external_links_in_blank():
    # arrange / act
    text = _viewer_js()
    # assert — externalLinkTarget=2 is PDF.js's BLANK constant; we set
    # it so a click on a PDF-internal link opens a new tab instead of
    # navigating the host iframe away from the live paper.
    assert "externalLinkTarget" in text


def test_viewer_js_skips_annotation_layer_when_empty():
    # arrange / act
    text = _viewer_js()
    # assert — pages with no annotations don't append an empty
    # `<div class="annotationLayer">` (kept DOM clean for embed hosts).
    assert "annotations || annotations.length === 0" in text \
        or "annotations.length === 0" in text


# ──────────────────────────────────────────────────────────────────
# Per-page wrapper — text + annotation overlays share the canvas
# coordinate space
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_wraps_each_page_in_relative_div():
    # arrange / act
    text = _viewer_js()
    # assert — overlays use `position:absolute` referenced against the
    # page wrapper's `position:relative`; without the wrapper the
    # overlays would float against the document root.
    assert 'pageWrap.style.position = "relative"' in text


def test_viewer_js_tags_page_wrap_with_data_page_number():
    # arrange / act
    text = _viewer_js()
    # assert — exposes the page number to host JS / E2E tests
    assert "pageWrap.dataset.pageNumber" in text


# ──────────────────────────────────────────────────────────────────
# CSS contract — overlays positioned + selection styled
# ──────────────────────────────────────────────────────────────────


def test_viewer_css_styles_text_layer():
    # arrange / act
    text = _viewer_css()
    # assert — invisible glyph spans require explicit positioning +
    # `color: transparent` + a low opacity to align with the canvas.
    assert ".textLayer" in text
    assert "position: absolute" in text


def test_viewer_css_styles_text_selection_color():
    # arrange / act
    text = _viewer_css()
    # assert — the ::selection rule gives the browser-native selection
    # / find highlight a brand colour instead of the OS default.
    assert "::selection" in text


def test_viewer_css_styles_annotation_layer_with_pointer_events_none():
    # arrange / act
    text = _viewer_css()
    # assert — annotationLayer host has pointer-events:none; child
    # `section` elements get pointer-events:auto so only the actual
    # link rects are clickable.
    assert ".annotationLayer" in text
    assert "pointer-events: none" in text


def test_viewer_css_styles_link_annotation_anchor():
    # arrange / act
    text = _viewer_css()
    # assert
    assert "linkAnnotation" in text


# ──────────────────────────────────────────────────────────────────
# Backward-compat regression — PR (b)'s contract still holds
# ──────────────────────────────────────────────────────────────────


def test_viewer_js_still_defines_pdfviewer_class():
    text = _viewer_js()
    assert "class PDFViewer" in text


def test_viewer_js_still_calls_api_pdf_endpoint():
    text = _viewer_js()
    assert '"pdf?doc_type="' in text


def test_viewer_js_still_uses_vendored_pdfjs():
    text = _viewer_js()
    assert "pdf.min.mjs" in text
    for marker in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
        assert marker not in text


def test_viewer_js_still_exposes_window_pdfviewer_global():
    text = _viewer_js()
    # Hosts that adopt drive the viewer programmatically via this global
    assert "window.LivePaperPDFViewer" in text
