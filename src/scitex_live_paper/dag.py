"""Public re-export of the DAG navigator renderer.

The implementation lives in :mod:`scitex_live_paper._renderer.dag`; this
thin top-level shim exists so the scaffolded contract from issue #10
(``scitex_live_paper.dag.render_html``) holds and downstream callers can
import from the public namespace without reaching into ``_renderer``.
"""

from __future__ import annotations

from scitex_live_paper._renderer.dag import (
    MERMAID_VERSION,
    DagArtifacts,
    render_dag,
    render_html,
)

__all__ = ["MERMAID_VERSION", "DagArtifacts", "render_dag", "render_html"]
