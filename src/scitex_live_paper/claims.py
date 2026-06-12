"""Public re-export of the claims sidebar renderer.

The implementation lives in :mod:`scitex_live_paper._renderer.claims`;
this thin top-level shim exists so the scaffolded contract from issue #10
(``scitex_live_paper.claims.render_html``) holds and downstream callers
can import from the public namespace without reaching into ``_renderer``.
"""

from __future__ import annotations

from scitex_live_paper._renderer.claims import (
    ClaimsArtifacts,
    render_claims_sidebar,
    render_html,
)

__all__ = ["ClaimsArtifacts", "render_claims_sidebar", "render_html"]
