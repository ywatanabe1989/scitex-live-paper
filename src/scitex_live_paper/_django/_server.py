"""Standalone server entry for ``scitex-live-paper serve``.

Pins the bundle path for the process via the ``SCITEX_LIVE_PAPER_BUNDLE``
env var (handlers read it through :func:`services.resolve_bundle_path`)
and hands control to Django's ``runserver``. ``--noreload`` is used so
the env var the parent process set sticks across the dev loop.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765


def serve(
    bundle_path: str | Path,
    *,
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
) -> None:
    """Boot a standalone Django dev server pinned to ``bundle_path``.

    Sets ``DJANGO_SETTINGS_MODULE`` and ``SCITEX_LIVE_PAPER_BUNDLE`` then
    calls ``django.setup()`` + ``runserver``. Blocks until the server is
    stopped (Ctrl-C). M3 will replace this with a real WSGI mount on
    ``scitex-hub`` — keep the surface tiny.
    """
    resolved = Path(bundle_path).expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(
            f"bundle path is not a directory: {resolved}"
        )

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "scitex_live_paper._django.settings",
    )
    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(resolved)

    import django  # noqa: WPS433 — lazy so non-django installs still import this file
    from django.core.management import call_command

    django.setup()
    logger.info(
        "[live-paper] serving %s on http://%s:%d/", resolved, host, port,
    )
    call_command("runserver", f"{host}:{port}", "--noreload")
