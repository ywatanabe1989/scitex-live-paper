"""No-mocks tests for ``api/pdf`` — ported from scitex_writer's handle_pdf.

The handler serves the bundle's manuscript PDF bytes via Django's
``FileResponse``, with ``?doc_type=`` parameter (for writer adoption)
and ``?download=`` to flip inline preview → attachment.

All collaborators are real: real Django test ``Client``, real
``bundle.load()`` against the in-tree fixtures (``bundle-min`` ships a
placeholder ``manuscript.pdf``; ``bundle-accepted`` mirrors the same).
No ``monkeypatch``, no ``mock.patch``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("django")

from django.test import Client  # noqa: E402

from scitex_live_paper._django import services  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"


@pytest.fixture
def env_snapshot() -> Iterator[None]:
    snap = dict(os.environ)
    try:
        yield
    finally:
        for key in list(os.environ):
            if key not in snap:
                del os.environ[key]
        for key, value in snap.items():
            os.environ[key] = value


@pytest.fixture
def client() -> Client:
    return Client()


def _pin(path: Path) -> None:
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(path)
    services.clear_cache()


# ──────────────────────────────────────────────────────────────────
# Happy path — GET /api/pdf returns the manuscript bytes
# ──────────────────────────────────────────────────────────────────


def test_api_pdf_returns_200(client, env_snapshot):
    _pin(BUNDLE_MIN)
    response = client.get("/api/pdf")
    assert response.status_code == 200


def test_api_pdf_serves_application_pdf_content_type(client, env_snapshot):
    _pin(BUNDLE_MIN)
    response = client.get("/api/pdf")
    assert response["Content-Type"].startswith("application/pdf")


def test_api_pdf_returns_manuscript_bytes(client, env_snapshot):
    _pin(BUNDLE_MIN)
    expected = (BUNDLE_MIN / "manuscript.pdf").read_bytes()
    response = client.get("/api/pdf")
    # FileResponse streams; collect chunks.
    body = b"".join(response.streaming_content)
    assert body == expected


def test_api_pdf_filename_matches_bundle_manuscript_name(client, env_snapshot):
    _pin(BUNDLE_MIN)
    response = client.get("/api/pdf")
    # Inline disposition; filename still set by FileResponse
    disposition = response.get("Content-Disposition", "")
    assert "manuscript.pdf" in disposition


# ──────────────────────────────────────────────────────────────────
# ?download=1 — Content-Disposition: attachment
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "True", "ON"])
def test_api_pdf_download_truthy_sets_attachment(client, env_snapshot, value):
    _pin(BUNDLE_MIN)
    response = client.get(f"/api/pdf?download={value}")
    disposition = response.get("Content-Disposition", "")
    assert "attachment" in disposition
    assert "manuscript.pdf" in disposition


@pytest.mark.parametrize("value", ["0", "false", "no", "", "random"])
def test_api_pdf_download_falsy_stays_inline(client, env_snapshot, value):
    _pin(BUNDLE_MIN)
    response = client.get(f"/api/pdf?download={value}")
    disposition = response.get("Content-Disposition", "")
    assert "attachment" not in disposition


# ──────────────────────────────────────────────────────────────────
# doc_type — manuscript today; supplementary/revision reserved
# ──────────────────────────────────────────────────────────────────


def test_api_pdf_doc_type_manuscript_works(client, env_snapshot):
    _pin(BUNDLE_MIN)
    response = client.get("/api/pdf?doc_type=manuscript")
    assert response.status_code == 200


@pytest.mark.parametrize("doc_type", ["supplementary", "revision"])
def test_api_pdf_supplementary_revision_404_with_clear_message(client, env_snapshot, doc_type):
    # arrange — bundle layout doesn't ship these yet; the handler
    # surfaces a clean 404 + message so callers know it's a layout
    # limitation, not a missing file.
    _pin(BUNDLE_MIN)
    response = client.get(f"/api/pdf?doc_type={doc_type}")
    assert response.status_code == 404
    import json

    body = json.loads(response.content)
    assert doc_type in body["error"]
    assert "not yet supported" in body["error"]


def test_api_pdf_unknown_doc_type_400(client, env_snapshot):
    _pin(BUNDLE_MIN)
    response = client.get("/api/pdf?doc_type=appendix")
    assert response.status_code == 400


# ──────────────────────────────────────────────────────────────────
# HANDLERS registration + dispatcher integration
# ──────────────────────────────────────────────────────────────────


def test_api_pdf_handler_is_registered():
    from scitex_live_paper._django.handlers import HANDLERS, handle_pdf

    assert HANDLERS["api/pdf"] is handle_pdf


def test_api_pdf_dispatcher_routes_pass_through_fileresponse(client, env_snapshot):
    # arrange — dispatcher must NOT re-wrap FileResponse (a subclass of
    # HttpResponse) into JsonResponse. Regression check on PR #22's
    # loud-return fix: HttpResponse instances pass through untouched.
    _pin(BUNDLE_MIN)
    response = client.get("/api/pdf")
    assert response["Content-Type"].startswith("application/pdf")
    # If the dispatcher re-wrapped, content-type would be application/json.


# ──────────────────────────────────────────────────────────────────
# Bundle-context aware: BundleContext.source wins over env (PR #27 path)
# ──────────────────────────────────────────────────────────────────


def test_api_pdf_through_mount_resolver_uses_context_bundle(env_snapshot):
    # arrange — env points at bundle-min, resolver points at bundle-accepted
    from scitex_live_paper import (
        BundleContext, BundleSource, mount,
    )
    from django.test import RequestFactory

    _pin(BUNDLE_MIN)

    def resolver(request, **kw):
        return BundleContext(source=BundleSource.from_directory(BUNDLE_ACCEPTED))

    patterns, _ = mount(resolver)
    dispatch = next(p.callback for p in patterns if p.name == "api_dispatch")

    rf = RequestFactory()

    # act
    response = dispatch(rf.get("/api/pdf"), endpoint="api/pdf")

    # assert — accepted bundle has its own manuscript bytes
    expected = (BUNDLE_ACCEPTED / "manuscript.pdf").read_bytes()
    body = b"".join(response.streaming_content)
    assert body == expected


# ──────────────────────────────────────────────────────────────────
# viewer.html / viewer_embed.html load JS as module
# ──────────────────────────────────────────────────────────────────


def test_viewer_template_loads_viewer_js_as_module(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = client.get("/").content.decode("utf-8")
    assert 'type="module"' in body
    assert "live_paper/js/viewer.js" in body


def test_embed_template_loads_viewer_js_as_module(client, env_snapshot):
    _pin(BUNDLE_MIN)
    body = client.get("/?embed=1").content.decode("utf-8")
    assert 'type="module"' in body
    assert "live_paper/js/viewer.js" in body


# ──────────────────────────────────────────────────────────────────
# viewer.js asset — present, defines PDFViewer, no CDN
# ──────────────────────────────────────────────────────────────────


def _viewer_js_bundle() -> str:
    """Concatenated text of every JS module under live_paper/js/.

    After the module split, viewer logic lives in viewer.js
    (orchestrator) + pdf-viewer.js + claims-sidebar.js +
    reverify-all.js + _utils.js. Tests read the bundle so the
    string-presence assertions stay terse.
    """
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    js_dir = pkg_root / "_django" / "static" / "live_paper" / "js"
    return "\n".join(
        (js_dir / name).read_text(encoding="utf-8")
        for name in (
            "viewer.js",
            "pdf-viewer.js",
            "claims-sidebar.js",
            "reverify-all.js",
            "_utils.js",
        )
    )


def test_viewer_js_defines_pdfviewer_class():
    text = _viewer_js_bundle()
    assert "class PDFViewer" in text


def test_viewer_js_uses_vendored_pdfjs_not_cdn():
    text = _viewer_js_bundle()
    # Vendored relative import — same vendoring contract as PR #19.
    assert "pdf.min.mjs" in text
    for marker in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
        assert marker not in text


def test_viewer_js_calls_api_pdf_endpoint():
    text = _viewer_js_bundle()
    # PDFViewer.load() builds the URL via apiBase + "pdf?doc_type=...".
    assert "\"pdf?doc_type=\"" in text


def test_pdfjs_assets_shipped_in_django_static_tree():
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    pdfjs_dir = pkg_root / "_django" / "static" / "live_paper" / "pdfjs"
    assert pdfjs_dir.is_dir()
    assert (pdfjs_dir / "pdf.min.mjs").is_file()
    assert (pdfjs_dir / "pdf.worker.min.mjs").is_file()
