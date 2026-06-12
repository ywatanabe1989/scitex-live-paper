"""PDF.js viewer page renderer (issue #4).

Emits the static ``viewer.html`` + sibling assets that load the manuscript
PDF in a vendored PDF.js build and overlay clickable claim-anchor regions
read from ``claims.json``.

Boundary
--------
This module is a **pure renderer**. It does:

  - render the HTML template,
  - copy the vendored PDF.js bundle, the viewer CSS / JS, the manuscript
    PDF, and ``claims.json`` into the output site directory,
  - return the path of the generated ``viewer.html``.

It does **not** validate the claim schema or invent new fields — the
claim model is owned upstream by ``scitex-clew`` (see ``scitex_live_paper.bundle``).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

try:  # Jinja2 is a project dep; the explicit guard keeps the import error
    # actionable when the dev forgot ``pip install -e .``.
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "scitex-live-paper viewer renderer requires Jinja2 — "
        "install the package (or `pip install jinja2`)"
    ) from exc

from scitex_live_paper.bundle import Bundle

__all__ = ["PDFJS_VERSION", "ViewerArtifacts", "render_viewer"]

# Vendored PDF.js build version (see _renderer/assets/pdfjs/README.md).
PDFJS_VERSION = "4.7.76"

_RENDERER_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _RENDERER_DIR / "assets"
_TEMPLATES_DIR = _RENDERER_DIR / "templates"
_PDFJS_DIR = _ASSETS_DIR / "pdfjs"
_VIEWER_CSS = _ASSETS_DIR / "viewer.css"
_VIEWER_JS = _ASSETS_DIR / "viewer.js"
_PDFJS_MAIN = "pdf.min.mjs"
_PDFJS_WORKER = "pdf.worker.min.mjs"

_OUTPUT_LAYOUT = {
    # destination path RELATIVE to out_dir → source path
    "viewer.html": None,  # written from template, sentinel
    "manuscript.pdf": None,  # populated from bundle.manuscript_path
    "claims.json": None,  # populated from bundle.root / "claims.json"
    "assets/viewer.css": _VIEWER_CSS,
    "assets/viewer.js": _VIEWER_JS,
    f"assets/pdfjs/{_PDFJS_MAIN}": _PDFJS_DIR / _PDFJS_MAIN,
    f"assets/pdfjs/{_PDFJS_WORKER}": _PDFJS_DIR / _PDFJS_WORKER,
}


@dataclass(frozen=True)
class ViewerArtifacts:
    """The paths the renderer wrote, returned so callers can wire the CLI."""

    viewer_html: Path
    manuscript_pdf: Path
    claims_json: Path
    css: Path
    js: Path
    pdfjs_main: Path
    pdfjs_worker: Path


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "htm", "xml"]),
        keep_trailing_newline=True,
    )


def _copy_into(out_dir: Path, rel_dest: str, source: Path) -> Path:
    dest = out_dir / rel_dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return dest


def render_viewer(
    bundle: Bundle,
    out_dir: str | Path,
    *,
    title: str | None = None,
) -> ViewerArtifacts:
    """Render the M1 PDF.js viewer page for *bundle* into *out_dir*.

    Parameters
    ----------
    bundle
        Loaded :class:`scitex_live_paper.bundle.Bundle`.
    out_dir
        Output directory. Created if it does not exist. Existing files at
        the canonical paths (``viewer.html`` / ``assets/...``) are
        overwritten so the renderer is idempotent.
    title
        Optional page title; defaults to ``"Live Paper — Viewer"``.

    Returns
    -------
    ViewerArtifacts
        Resolved paths of every artefact written, so the caller (CLI) can
        wire ``index.html`` links without re-deriving them.
    """
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    (out_dir / "assets" / "pdfjs").mkdir(exist_ok=True)

    # 1. Copy the static, file-sourced artefacts.
    css_dest = _copy_into(out_dir, "assets/viewer.css", _VIEWER_CSS)
    js_dest = _copy_into(out_dir, "assets/viewer.js", _VIEWER_JS)
    pdfjs_main_dest = _copy_into(
        out_dir, f"assets/pdfjs/{_PDFJS_MAIN}", _PDFJS_DIR / _PDFJS_MAIN
    )
    pdfjs_worker_dest = _copy_into(
        out_dir, f"assets/pdfjs/{_PDFJS_WORKER}", _PDFJS_DIR / _PDFJS_WORKER
    )

    # 2. Copy the bundle's manuscript and claims.json (read-only consumers).
    if bundle.manuscript_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"viewer expects a PDF manuscript, got {bundle.manuscript_path.suffix!r} "
            f"(.tex bundles need an upstream LaTeX → PDF step)"
        )
    manuscript_dest = _copy_into(
        out_dir, "manuscript.pdf", bundle.manuscript_path
    )
    claims_dest = _copy_into(
        out_dir, "claims.json", bundle.root / "claims.json"
    )

    # 3. Render the HTML template.
    env = _jinja_env()
    template = env.get_template("viewer.html.j2")
    html = template.render(
        title=title or "Live Paper — Viewer",
        pdf_url="manuscript.pdf",
        claims_url="claims.json",
        pdfjs_url=f"assets/pdfjs/{_PDFJS_MAIN}",
        pdfjs_worker_url=f"assets/pdfjs/{_PDFJS_WORKER}",
        css_url="assets/viewer.css",
        js_url="assets/viewer.js",
        pdfjs_version=PDFJS_VERSION,
    )
    viewer_html = out_dir / "viewer.html"
    viewer_html.write_text(html, encoding="utf-8")

    return ViewerArtifacts(
        viewer_html=viewer_html,
        manuscript_pdf=manuscript_dest,
        claims_json=claims_dest,
        css=css_dest,
        js=js_dest,
        pdfjs_main=pdfjs_main_dest,
        pdfjs_worker=pdfjs_worker_dest,
    )
