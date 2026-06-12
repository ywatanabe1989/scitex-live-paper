"""Claims sidebar HTML renderer (issue #5).

Emits a standalone ``claims.html`` site page that lists every claim from
the bundle's ``claims.json`` with its ``scitex_clew.VerificationStatus``
colour, plus an expandable per-claim panel showing status / hash /
producing-script link / disabled "Re-verify" stub (the live verify lands
in M2).

Boundary
--------
The colour mapping is **owned upstream by ``scitex-clew``**. This module
deliberately does *not* hard-code a parallel enum: it labels each row
with the canonical clew status string (``verified`` / ``stale`` /
``failed`` / ``registered`` / ...) and lets the CSS look the colour up
via ``data-status="<value>"``. If a new status appears, only the CSS
needs a new selector — no Python change here. If the palette itself
needs to change, raise that upstream in ``scitex-clew``.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "scitex-live-paper claims renderer requires Jinja2 — "
        "install the package (or `pip install jinja2`)"
    ) from exc

from scitex_live_paper.bundle import Bundle, Claim

__all__ = [
    "ClaimsArtifacts",
    "render_claims_sidebar",
    "render_html",
]

_RENDERER_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _RENDERER_DIR / "assets"
_TEMPLATES_DIR = _RENDERER_DIR / "templates"
_CLAIMS_CSS = _ASSETS_DIR / "claims.css"
_CLAIMS_JS = _ASSETS_DIR / "claims.js"


@dataclass(frozen=True)
class ClaimsArtifacts:
    """Paths of every artefact the claims renderer wrote."""

    claims_html: Path
    css: Path
    js: Path


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "htm", "xml"]),
        keep_trailing_newline=True,
    )


def _claim_short_label(claim: Claim) -> str:
    """Pick a short, render-friendly label for the sidebar row.

    Falls back through claim_value → file_path:line → claim_id so the row
    is never empty even on a sparsely-populated claim.
    """
    if claim.claim_value:
        # Trim long values so the sidebar list stays scannable; the full
        # value lives in the expanded per-claim panel.
        value = claim.claim_value.strip().splitlines()[0]
        return value[:80] + ("…" if len(value) > 80 else "")
    if claim.line_number is not None:
        return f"{claim.file_path}:{claim.line_number}"
    return claim.file_path or claim.claim_id


def _copy_into(out_dir: Path, rel_dest: str, source: Path) -> Path:
    dest = out_dir / rel_dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return dest


def render_claims_sidebar(
    bundle: Bundle,
    out_dir: str | Path,
    *,
    title: str | None = None,
    viewer_url: str = "viewer.html",
) -> ClaimsArtifacts:
    """Render the M1 claims sidebar page for *bundle* into *out_dir*.

    Parameters
    ----------
    bundle
        Loaded :class:`scitex_live_paper.bundle.Bundle`.
    out_dir
        Output directory. Created if absent. Existing files at the
        canonical paths are overwritten — the renderer is idempotent.
    title
        Optional page title; defaults to ``"Live Paper — Claims"``.
    viewer_url
        URL of the viewer page (default ``"viewer.html"`` for the
        sibling-page layout the CLI emits — issue #7). Used to build
        click-to-jump links from sidebar rows.

    Returns
    -------
    ClaimsArtifacts
        Resolved paths so the CLI can wire ``index.html`` without
        re-deriving them.
    """
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)

    css_dest = _copy_into(out_dir, "assets/claims.css", _CLAIMS_CSS)
    js_dest = _copy_into(out_dir, "assets/claims.js", _CLAIMS_JS)

    # Pre-shape claims for the template. We DO NOT redefine status;
    # we pass the raw clew status string through as data-status so the
    # CSS palette (one selector per status) is the only place colours live.
    rows = [
        {
            "claim_id": c.claim_id,
            "status": c.status or "registered",
            "label": _claim_short_label(c),
            "file_path": c.file_path,
            "line_number": c.line_number,
            "claim_type": c.claim_type,
            "claim_value": c.claim_value or "",
            "source_session": c.source_session or "",
            "source_file": c.source_file or "",
            "source_hash": c.source_hash or "",
            "registered_at": c.registered_at or "",
            "verified_at": c.verified_at or "",
        }
        for c in bundle.claims
    ]

    env = _jinja_env()
    template = env.get_template("claims.html.j2")
    html = template.render(
        title=title or "Live Paper — Claims",
        claims=rows,
        viewer_url=viewer_url,
        css_url="assets/claims.css",
        js_url="assets/claims.js",
        total_claims=len(rows),
    )
    claims_html = out_dir / "claims.html"
    claims_html.write_text(html, encoding="utf-8")

    return ClaimsArtifacts(
        claims_html=claims_html,
        css=css_dest,
        js=js_dest,
    )


# ---------------------------------------------------------------------------
# Compat alias
# ---------------------------------------------------------------------------


def render_html(bundle: Bundle, out_dir: str | Path, **kwargs) -> ClaimsArtifacts:
    """Alias of :func:`render_claims_sidebar`.

    The PR #13 test scaffolding (issue #10) pinned ``render_html`` as the
    expected public callable for this module; keep it as a thin alias so
    the scaffolded contract continues to hold and downstream callers can
    pick whichever name they prefer.
    """
    return render_claims_sidebar(bundle, out_dir, **kwargs)
