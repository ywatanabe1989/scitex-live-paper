"""``HUB_APP_MANIFEST`` — pip-package-shape metadata for the hub publisher.

The single source of truth for how `scitex-live-paper` represents
itself to `scitex-hub`'s plugin registry. Mirrors the shape
`scitex-agentic-journal` shipped in PR #34: a frozen dict the
wrapper app reads through :func:`derive_wrapper_manifest` to build
its `manifest.json` v2.0.0.

Schema (all keys flat at the top level):

- ``name``           — pip name, used as the wrapper's stable id
- ``version``        — pinned to :data:`scitex_live_paper.__version__`
- ``display_name``   — short human title (workspace tile / breadcrumb)
- ``description``    — one-paragraph product description
- ``category``       — hub-side taxonomy slot (``"app"``)
- ``python_requires`` — minimum runtime
- ``entry_points``   — ``{"scitex_hub.apps": "<target>"}`` for the
                        hub's plugin discovery; see EP-SHAPE NOTE
- ``requires``       — PEP 508 specifier strings the wrapper deps on
- ``upstream``       — ``{"package": ..., "module": ...}`` pointing
                        back at this pip package
- ``permissions``    — list of permission strings the app needs

EP-SHAPE NOTE
-------------
``entry_points["scitex_hub.apps"]`` points at the wrapper's
``urls:urlpatterns`` per the hub registry contract (matches the
scitex-agentic-journal pattern; confirmed with proj-scitex-hub).
The wrapper module-name convention is ``<upstream>_hub_app`` so
live-paper's wrapper is ``scitex_live_paper_hub_app``.

The orthogonal ``entry_points["scitex_hub.app_config"]`` exposes the
Django ``AppConfig`` separately — URL surface vs Django-internal
model registration are different axes; we ship both keys so a host
that wants either can pick the right one without overloading a
single EP name.

PERMISSIONS NOTE
----------------
Empty list intentionally. Live-paper reads the bundle directory
through the standard host filesystem; if the hub later carves out a
``bundle.read`` permission for fine-grained mounts, add it here.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Any

from .. import __version__ as _pkg_version

HUB_APP_NAME: str = "scitex-live-paper"
HUB_APP_VERSION: str = _pkg_version


# A read-only view (``MappingProxyType``) keeps callers from accidentally
# mutating the canonical metadata at runtime — the wrapper SHOULD copy
# before mutating if it wants to override a field.
HUB_APP_MANIFEST: Mapping[str, Any] = MappingProxyType(
    {
        "name": HUB_APP_NAME,
        "version": HUB_APP_VERSION,
        "display_name": "SciTeX Live Paper",
        "description": (
            "Interactive, AI-verifiable live rendering of research "
            "manuscripts. Renders an accepted manuscript bundle as a "
            "PDF.js viewer + claims sidebar + DAG navigator + "
            "verification badge. Consumer of the scitex-clew claim "
            "model (mirrors clew's schema; never extends it)."
        ),
        "category": "app",
        "python_requires": ">=3.10",
        "entry_points": MappingProxyType(
            {
                # URL surface — what the hub registry's F0+F1 loader
                # imports + caches as the wrapper's urlpatterns.
                # Matches scitex-agentic-journal's choice.
                "scitex_hub.apps": (
                    "scitex_live_paper_hub_app.urls:urlpatterns"
                ),
                # Orthogonal axis — the Django AppConfig (model
                # registration, ready() hooks). Exposed so a host
                # that wants either surface can pick without
                # overloading the `apps` key.
                "scitex_hub.app_config": (
                    "scitex_live_paper._django.apps:LivePaperConfig"
                ),
            }
        ),
        # PEP 508 — the wrapper's installer reads these to pull the
        # right pins. `[django]` extra deps live here so the wrapper
        # doesn't need to re-spell the version range.
        "requires": (
            "scitex-live-paper>=0.1.0",
            "django>=4.2",
            "scitex-clew>=0.1.0",
        ),
        "upstream": MappingProxyType(
            {
                "package": "scitex-live-paper",
                "module": "scitex_live_paper",
            }
        ),
        # Empty starter list — hub may carve out a `bundle.read`
        # permission later; add it here when that lands.
        "permissions": (),
    }
)
