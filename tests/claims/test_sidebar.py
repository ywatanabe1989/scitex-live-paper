"""STX-TQ scaffolding for ``scitex_live_paper.claims`` (sidebar HTML generator).

The claims sidebar module lands in M1 (roadmap issue #5). Until then this
file exists so the test layout follows the per-module convention and the
CI matrix lights up a clear "not yet implemented" signal rather than
silent absence.

When ``scitex_live_paper.claims`` exists, replace the importorskip stub
below with real STX-TQ tests (one behaviour per function, AAA blocks).
"""

from __future__ import annotations

import pytest


def test_claims_module_scaffolding_is_discoverable():
    # Arrange / Act: discovery is the behaviour under test
    # Assert
    assert True


def test_claims_sidebar_renderer_exposes_render_html_callable():
    # Skipped until issue #5 lands the renderer. Kept here so the
    # interface contract is captured in code, not just in the issue.
    sidebar = pytest.importorskip(
        "scitex_live_paper.claims",
        reason="claims sidebar renderer not implemented yet (issue #5)",
    )
    assert callable(getattr(sidebar, "render_html", None))
