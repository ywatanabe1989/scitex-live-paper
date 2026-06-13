"""Command-line entry point for `scitex-live-paper` (issue #7).

Exposes ``scitex-live-paper render <bundle> --out <site>`` — the M1
end-to-end loop that takes an accepted manuscript bundle and emits a
self-contained static site directory (viewer + claims + DAG + landing
page + vendored assets). The generated site opens straight from
``file://`` — no server required.

The CLI is the thin glue layer: it loads the bundle and calls each
sibling renderer in turn. All claim / DAG semantics live upstream in
``scitex-clew``; this module never invents or validates fields.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import click
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "scitex-live-paper CLI requires click — install the package "
        "(or `pip install click>=8.0`)"
    ) from exc

from scitex_live_paper import bundle as bundle_module
from scitex_live_paper._renderer.claims import render_claims_sidebar
from scitex_live_paper._renderer.dag import render_dag
from scitex_live_paper._renderer.index import render_index
from scitex_live_paper._renderer.viewer import render_viewer

__all__ = ["RenderResult", "render_site", "cli", "main"]


@dataclass(frozen=True)
class RenderResult:
    """Resolved paths of the four pages the site emits.

    The vendored asset paths are intentionally NOT part of the contract
    — callers should look up ``out_dir / "assets" / ...`` if needed.
    """

    out_dir: Path
    index_html: Path
    viewer_html: Path
    claims_html: Path
    dag_html: Path


def render_site(
    bundle_path: str | Path,
    out_dir: str | Path,
    *,
    title: str | None = None,
) -> RenderResult:
    """Render a bundle directory into a self-contained static site.

    Parameters
    ----------
    bundle_path
        Path to the accepted manuscript bundle directory (see
        :mod:`scitex_live_paper.bundle` for the expected layout).
    out_dir
        Output directory. Created if absent. Existing pages are
        overwritten — the render is idempotent.
    title
        Optional shared page title; defaults to ``"Live Paper"`` for the
        landing page and ``"Live Paper — <surface>"`` for the others.

    Returns
    -------
    RenderResult
        Resolved paths of the four emitted pages.
    """
    loaded = bundle_module.load(bundle_path)
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    viewer = render_viewer(
        loaded,
        out_dir,
        title=title or "Live Paper — Viewer",
    )
    claims = render_claims_sidebar(
        loaded,
        out_dir,
        title=title or "Live Paper — Claims",
    )
    dag = render_dag(
        loaded,
        out_dir,
        title=title or "Live Paper — DAG",
    )
    index = render_index(
        loaded,
        out_dir,
        title=title,
    )

    return RenderResult(
        out_dir=out_dir,
        index_html=index.index_html,
        viewer_html=viewer.viewer_html,
        claims_html=claims.claims_html,
        dag_html=dag.dag_html,
    )


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="scitex-live-paper — emit a static live-paper site from an accepted bundle.",
)
@click.version_option(
    package_name="scitex-live-paper",
    prog_name="scitex-live-paper",
)
def cli() -> None:
    """Top-level ``scitex-live-paper`` group."""


@cli.command("render")
@click.argument(
    "bundle_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
    help="Output directory for the generated static site.",
)
@click.option(
    "--title",
    default=None,
    help="Optional shared page title (defaults to 'Live Paper').",
)
def render_cmd(bundle_path: str, out_dir: str, title: str | None) -> None:
    """Render BUNDLE_PATH into a self-contained static site under --out."""
    try:
        result = render_site(bundle_path, out_dir, title=title)
    except bundle_module.BundleError as exc:
        # Surface bundle-layout errors with a clean exit code (no traceback).
        raise click.ClickException(str(exc)) from exc

    click.echo(f"rendered → {result.out_dir}")
    click.echo(f"  index    : {result.index_html.relative_to(result.out_dir)}")
    click.echo(f"  viewer   : {result.viewer_html.relative_to(result.out_dir)}")
    click.echo(f"  claims   : {result.claims_html.relative_to(result.out_dir)}")
    click.echo(f"  dag      : {result.dag_html.relative_to(result.out_dir)}")


@cli.command("serve")
@click.argument(
    "bundle_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Interface to bind the dev server to.",
)
@click.option(
    "--port",
    default=8765,
    show_default=True,
    type=int,
    help="Port to bind the dev server to.",
)
def serve_cmd(bundle_path: str, host: str, port: int) -> None:
    """Run the standalone Django dev server pinned to BUNDLE_PATH.

    Requires the ``[django]`` extra. The viewer mounts at ``/`` and the
    catch-all API dispatcher mounts at ``/<endpoint>`` (e.g. ``/api/ping``,
    ``/api/bundle-info``).
    """
    try:
        from scitex_live_paper._django._server import serve as _serve  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only without [django]
        raise click.ClickException(
            "the `serve` command requires the [django] extra — "
            "install with: pip install 'scitex-live-paper[django]'"
        ) from exc
    # pragma: no cover reason — `_serve(...)` is `_server.serve()`
    # with no injected runner, which calls Django's `runserver` and
    # binds a TCP port. No-mocks doctrine prohibits patching
    # call_command for a coverage hit; this line only fires from the
    # live `scitex-live-paper serve` CLI.
    _serve(bundle_path, host=host, port=port)  # pragma: no cover


@cli.command("info")
@click.argument(
    "bundle_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit a JSON object instead of the human-readable summary.",
)
def info_cmd(bundle_path: str, as_json: bool) -> None:
    """Print a one-screen sanity summary of BUNDLE_PATH.

    Operator-facing pre-flight check: load the bundle (without rendering
    anything) and report claim count + status palette, paper_state stage
    + journal + DOI + pinned_commit, manuscript filename, whether the
    DAG is embedded, and the claims.json schema version. ``BundleError``
    surfaces as a clean CLI exit (no traceback).

    Pass ``--json`` to emit a stable machine-parseable summary
    (suitable for ``scitex-live-paper info bundle | jq``).
    """
    try:
        bundle = bundle_module.load(bundle_path)
    except bundle_module.BundleError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = _bundle_info_summary(bundle)

    if as_json:
        import json as _json

        click.echo(_json.dumps(payload, indent=2, sort_keys=True))
        return

    _print_human_summary(payload)


def _bundle_info_summary(bundle: "bundle_module.Bundle") -> dict:
    """Build the payload both the human + JSON branches render."""
    from collections import Counter

    palette = Counter(c.status for c in bundle.claims)
    ps = bundle.paper_state
    return {
        "bundle_path": str(bundle.root),
        "manuscript": bundle.manuscript_path.name if bundle.manuscript_path else None,
        "schema_version": bundle.schema_version,
        "claim_count": len(bundle.claims),
        "status_palette": dict(palette),
        "dag_present": bool(bundle.dag and bundle.dag.strip()),
        "paper_state": {
            "stage": ps.stage,
            "header_label": ps.header_label(),
            "journal": ps.journal,
            "doi": ps.doi,
            "accepted_at": ps.accepted_at,
            "pinned_commit": ps.pinned_commit,
            "show_verification_badge": ps.show_verification_badge,
            "re_verify_enabled": ps.re_verify_enabled,
        },
    }


def _print_human_summary(payload: dict) -> None:
    """Render the one-screen operator summary."""
    click.echo(f"bundle    : {payload['bundle_path']}")
    click.echo(f"manuscript: {payload['manuscript'] or '(missing)'}")
    if payload["schema_version"]:
        click.echo(f"schema    : {payload['schema_version']}")
    click.echo(f"claims    : {payload['claim_count']}")
    if payload["status_palette"]:
        # Sort so output is stable across runs.
        items = sorted(payload["status_palette"].items())
        chips = " · ".join(f"{count} {status}" for status, count in items)
        click.echo(f"            {chips}")
    click.echo(f"dag       : {'embedded' if payload['dag_present'] else 'absent'}")
    ps = payload["paper_state"]
    click.echo("paper_state")
    click.echo(f"  stage         : {ps['stage']}")
    click.echo(f"  header_label  : {ps['header_label']}")
    if ps["journal"]:
        click.echo(f"  journal       : {ps['journal']}")
    if ps["doi"]:
        click.echo(f"  doi           : {ps['doi']}")
    if ps["accepted_at"]:
        click.echo(f"  accepted_at   : {ps['accepted_at']}")
    if ps["pinned_commit"]:
        click.echo(f"  pinned_commit : {ps['pinned_commit']}")
    click.echo(
        f"  badge visible : {ps['show_verification_badge']} · "
        f"re-verify : {ps['re_verify_enabled']}"
    )


def main(argv: list[str] | None = None) -> int:
    """Entrypoint used by the ``[project.scripts]`` declaration.

    Returns the exit code so callers can ``sys.exit(main())`` cleanly.
    """
    try:
        cli.main(args=argv, standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except SystemExit as exc:  # pragma: no cover
        # Defensive — click(standalone_mode=False) is supposed to
        # surface UsageError + ClickException without `sys.exit()`,
        # but plugins / hooks can raise SystemExit unrelated to click.
        # When that happens (rare), preserve the exit code so the
        # console-script returns the same value to the shell.
        return int(exc.code) if exc.code is not None else 0  # pragma: no cover
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via console_scripts
    sys.exit(main())
