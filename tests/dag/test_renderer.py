"""STX-TQ scaffolding for ``scitex_live_paper.dag`` (mermaid DAG renderer).

The DAG renderer module lands in M1 (roadmap issue #6). Until then this
file exists so the test layout follows the per-module convention and
the CI matrix surfaces a clear "not yet implemented" signal.

When ``scitex_live_paper.dag`` exists, replace the importorskip stub
below with real STX-TQ tests (one behaviour per function, AAA blocks).
"""

from __future__ import annotations

import pytest


def test_dag_module_scaffolding_is_discoverable():
    # Arrange / Act: discovery is the behaviour under test
    # Assert
    assert True


def test_dag_renderer_exposes_render_html_callable():
    # Skipped until issue #6 lands the renderer. Kept here so the
    # interface contract is captured in code, not just in the issue.
    dag = pytest.importorskip(
        "scitex_live_paper.dag",
        reason="DAG renderer not implemented yet (issue #6)",
    )
    assert callable(getattr(dag, "render_html", None))
