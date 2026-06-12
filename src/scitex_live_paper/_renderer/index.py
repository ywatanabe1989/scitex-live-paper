"""Landing-page renderer for the M1 static site (issue #7).

Emits ``index.html`` — the entry point of the generated site directory.
It links to the three M1 surfaces (viewer / claims / DAG) and shows a
short bundle summary (manuscript filename, total claims, whether the
DAG was embedded).

This module is a **pure renderer**. Like its siblings, it only consumes
``scitex_live_paper.bundle.Bundle`` — it never validates or extends the
claim model. The summary fields are read straight from the loaded
bundle.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "scitex-live-paper index renderer requires Jinja2 — "
        "install the package (or `pip install jinja2`)"
    ) from exc

from scitex_live_paper.bundle import Bundle

__all__ = ["IndexArtifacts", "render_index"]

_RENDERER_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _RENDERER_DIR / "assets"
_TEMPLATES_DIR = _RENDERER_DIR / "templates"
_INDEX_CSS = _ASSETS_DIR / "index.css"


@dataclass(frozen=True)
class IndexArtifacts:
    """Paths of every artefact the index renderer wrote."""

    index_html: Path
    css: Path


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


def render_index(
    bundle: Bundle,
    out_dir: str | Path,
    *,
    title: str | None = None,
    viewer_url: str = "viewer.html",
    claims_url: str = "claims.html",
    dag_url: str = "dag.html",
) -> IndexArtifacts:
    """Render the M1 landing page for *bundle* into *out_dir*.

    Parameters
    ----------
    bundle
        Loaded :class:`scitex_live_paper.bundle.Bundle`.
    out_dir
        Output directory. Created if absent. Existing ``index.html`` is
        overwritten — the renderer is idempotent.
    title
        Optional page title; defaults to ``"Live Paper"``.
    viewer_url, claims_url, dag_url
        Sibling-page relative URLs the landing cards link to (defaults
        match the CLI's sibling-page layout).

    Returns
    -------
    IndexArtifacts
        Resolved paths so the caller (CLI) can confirm what was written.
    """
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)

    css_dest = _copy_into(out_dir, "assets/index.css", _INDEX_CSS)

    env = _jinja_env()
    template = env.get_template("index.html.j2")
    html = template.render(
        title=title or "Live Paper",
        viewer_url=viewer_url,
        claims_url=claims_url,
        dag_url=dag_url,
        css_url="assets/index.css",
        total_claims=len(bundle.claims),
        manuscript_filename=bundle.manuscript_path.name,
        has_dag=bool(bundle.dag and bundle.dag.strip()),
        schema_version=bundle.schema_version or "",
    )
    index_html = out_dir / "index.html"
    index_html.write_text(html, encoding="utf-8")

    return IndexArtifacts(index_html=index_html, css=css_dest)
