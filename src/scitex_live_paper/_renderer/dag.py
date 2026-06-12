"""DAG navigator HTML renderer (issue #6).

Emits a standalone ``dag.html`` site page that renders the bundle's
``dag.mmd`` mermaid string with vendored mermaid, then wires click
handlers so Claim nodes open the matching claim panel via the same
``live-paper:claim`` event channel used by the PDF viewer (#4) and the
claims sidebar (#5).

Boundary
--------
The DAG structure and the node-class taxonomy are **owned upstream by
``scitex-clew``**. This renderer just paints what the bundle's ``dag.mmd``
already encodes — it does not add, rewrite, or normalise nodes. If a new
node class is needed (or an existing one needs a different colour), raise
the change upstream in ``scitex-clew`` and refresh the fixture; the
renderer follows.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "scitex-live-paper dag renderer requires Jinja2 — "
        "install the package (or `pip install jinja2`)"
    ) from exc

from scitex_live_paper.bundle import Bundle

__all__ = [
    "MERMAID_VERSION",
    "DagArtifacts",
    "render_dag",
    "render_html",
]

# Vendored mermaid UMD bundle version (see assets/mermaid/README.md).
MERMAID_VERSION = "10.9.4"

_RENDERER_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _RENDERER_DIR / "assets"
_TEMPLATES_DIR = _RENDERER_DIR / "templates"
_MERMAID_DIR = _ASSETS_DIR / "mermaid"
_MERMAID_MAIN = "mermaid.min.js"
_DAG_CSS = _ASSETS_DIR / "dag.css"
_DAG_JS = _ASSETS_DIR / "dag.js"


@dataclass(frozen=True)
class DagArtifacts:
    """Paths of every artefact the DAG renderer wrote."""

    dag_html: Path
    css: Path
    js: Path
    mermaid_main: Path


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


def render_dag(
    bundle: Bundle,
    out_dir: str | Path,
    *,
    title: str | None = None,
    viewer_url: str = "viewer.html",
    claims_url: str = "claims.html",
) -> DagArtifacts:
    """Render the M1 DAG navigator page for *bundle* into *out_dir*.

    Parameters
    ----------
    bundle
        Loaded :class:`scitex_live_paper.bundle.Bundle`. Reads
        ``bundle.dag`` for the mermaid source and the provenance map
        for ``source_hash`` lookup on Source / Processing nodes.
    out_dir
        Output directory. Created if absent. Existing files are
        overwritten — the renderer is idempotent.
    title
        Optional page title; defaults to ``"Live Paper — DAG"``.
    viewer_url
        Used when click-through links jump to the PDF viewer.
    claims_url
        Used when click-through links jump to the claims sidebar.

    Returns
    -------
    DagArtifacts
        Resolved paths so the CLI (#7) can wire ``index.html``.
    """
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    (out_dir / "assets" / "mermaid").mkdir(exist_ok=True)

    css_dest = _copy_into(out_dir, "assets/dag.css", _DAG_CSS)
    js_dest = _copy_into(out_dir, "assets/dag.js", _DAG_JS)
    mermaid_dest = _copy_into(
        out_dir, f"assets/mermaid/{_MERMAID_MAIN}", _MERMAID_DIR / _MERMAID_MAIN
    )

    # Provenance hash lookup: source_file -> source_hash. This lets the
    # DAG overlay show "script + hash" for Source / Processing nodes
    # without re-walking the provenance graph in JavaScript.
    provenance_map = _collect_source_hashes(bundle)

    env = _jinja_env()
    template = env.get_template("dag.html.j2")
    html = template.render(
        title=title or "Live Paper — DAG",
        # mermaid expects the raw graph source; pass it through verbatim.
        # NB: the template wraps it in a <pre class="mermaid"> block which
        # mermaid.init() picks up on DOMContentLoaded.
        dag_source=bundle.dag or "graph LR\n  empty[\"no dag.mmd in bundle\"]",
        has_dag=bool(bundle.dag and bundle.dag.strip()),
        css_url="assets/dag.css",
        js_url="assets/dag.js",
        mermaid_url=f"assets/mermaid/{_MERMAID_MAIN}",
        mermaid_version=MERMAID_VERSION,
        viewer_url=viewer_url,
        claims_url=claims_url,
        provenance_map=provenance_map,
    )
    dag_html = out_dir / "dag.html"
    dag_html.write_text(html, encoding="utf-8")

    return DagArtifacts(
        dag_html=dag_html,
        css=css_dest,
        js=js_dest,
        mermaid_main=mermaid_dest,
    )


def _collect_source_hashes(bundle: Bundle) -> dict[str, str]:
    """Build a ``{source_file: source_hash}`` map from the bundle.

    Sources of truth, in order:
      1. The claims list — each claim already carries ``source_file`` +
         ``source_hash`` from clew.
      2. The provenance graph — ``sessions[<sess>].files[<path>].hash``
         shape, if present. Lenient: missing branches are skipped.
    """
    out: dict[str, str] = {}
    for c in bundle.claims:
        if c.source_file and c.source_hash:
            out.setdefault(c.source_file, c.source_hash)

    sessions = bundle.provenance.get("sessions") if bundle.provenance else None
    if isinstance(sessions, dict):
        for _sid, sess in sessions.items():
            if not isinstance(sess, dict):
                continue
            files = sess.get("files")
            if not isinstance(files, dict):
                continue
            for path, meta in files.items():
                if not isinstance(meta, dict):
                    continue
                hsh = meta.get("hash")
                if isinstance(hsh, str) and path not in out:
                    out[path] = hsh
    return out


# ---------------------------------------------------------------------------
# Compat alias
# ---------------------------------------------------------------------------


def render_html(bundle: Bundle, out_dir: str | Path, **kwargs) -> DagArtifacts:
    """Alias of :func:`render_dag`.

    The PR #13 test scaffolding (issue #10) pinned ``render_html`` as
    the expected public callable for this module; keep it as a thin
    alias so the scaffolded contract continues to hold.
    """
    return render_dag(bundle, out_dir, **kwargs)
