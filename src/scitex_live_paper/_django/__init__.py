"""`scitex_live_paper._django` — Django app skeleton for M3 hub mount.

This skeleton mirrors the SPA-shell + ``<path:endpoint>`` ``api_dispatch``
pattern used by ``scitex_writer._django`` (and locally implementable via
``figrecipe._django``). Read-only: claim re-verify endpoints arrive in M2;
the actual mount under ``scitex-hub`` ``/viewer-v2/`` is M3 proper.

Boundary unchanged: every handler that needs claim/DAG data goes through
``scitex_live_paper.bundle.load()`` — the claim schema is owned upstream
by ``scitex-clew``.
"""

default_app_config = "scitex_live_paper._django.apps.LivePaperConfig"
