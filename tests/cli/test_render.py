"""STX-TQ scaffolding for ``scitex_live_paper._cli`` (``scitex-live-paper render``).

The CLI module lands in M1 (roadmap issue #7). Until then this file
exists so the test layout follows the per-module convention and the CI
matrix surfaces a clear "not yet implemented" signal rather than silent
absence.

When ``scitex_live_paper._cli`` exists, replace the importorskip stubs
below with real STX-TQ tests (one behaviour per function, AAA blocks).
"""

from __future__ import annotations

import pytest


def test_cli_module_scaffolding_is_discoverable():
    # Arrange / Act: discovery is the behaviour under test
    # Assert
    assert True


def test_cli_module_exposes_main_callable():
    # Skipped until issue #7 lands the CLI. The pyproject entry point
    # already references ``scitex_live_paper._cli:main`` so the
    # expected callable is fixed.
    cli = pytest.importorskip(
        "scitex_live_paper._cli",
        reason="CLI not implemented yet (issue #7)",
    )
    assert callable(getattr(cli, "main", None))
