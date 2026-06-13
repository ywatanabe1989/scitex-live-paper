"""scitex-hub plugin publishing surface.

Single-source-of-truth manifest metadata for `scitex_live_paper` so
the hub-side wrapper app (`scitex_live_paper_hub_app`) can derive its
workspace UI `manifest.json` instead of hand-filling 30+ keys.
Mirrors the two-layer pattern landed by `scitex-agentic-journal`
(PRs #34/#35/#36) so all live-paper-consuming hub wrappers share the
same drift-prevention contract.

Public surface (re-exported from the top-level package):

- ``HUB_APP_MANIFEST`` — frozen pip-package-shape metadata dict.
- ``HUB_APP_NAME`` / ``HUB_APP_VERSION`` — convenience constants.
- ``derive_wrapper_manifest(*, label, subtitle, schema_version)`` —
  maps the pip shape into the scitex-hub manifest v2.0.0 UI shape.
"""

from __future__ import annotations

from ._derive_wrapper_manifest import derive_wrapper_manifest
from ._manifest import HUB_APP_MANIFEST, HUB_APP_NAME, HUB_APP_VERSION

__all__ = [
    "HUB_APP_MANIFEST",
    "HUB_APP_NAME",
    "HUB_APP_VERSION",
    "derive_wrapper_manifest",
]
