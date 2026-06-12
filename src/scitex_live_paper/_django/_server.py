"""Standalone server entry for ``scitex-live-paper serve``.

Pins the bundle path for the process via the ``SCITEX_LIVE_PAPER_BUNDLE``
env var (handlers read it through :func:`services.resolve_bundle_path`)
and hands control to Django's ``runserver``. ``--noreload`` is used so
the env var the parent process set sticks across the dev loop.

The Django command runner is *injectable* (``runner`` kwarg) so tests
exercise the real env-pinning + ``django.setup()`` path without binding
a TCP port. The default runner is ``django.core.management.call_command``
— the real production collaborator.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765

#: Type alias for the Django management-command runner the server
#: delegates to. ``runserver`` is the only command the M1 surface needs;
#: signature is intentionally broad so M2 / M3 can extend without API
#: churn here.
CommandRunner = Callable[..., object]


def _default_runner(*args: object, **kwargs: object) -> object:
    """Real production runner — thin wrapper around ``call_command``.

    Defined as a module-level function (not an inline lambda) so the
    import is lazy: callers that don't reach ``serve()`` never pay the
    Django import cost.
    """
    from django.core.management import call_command  # noqa: WPS433

    return call_command(*args, **kwargs)


def serve(
    bundle_path: str | Path,
    *,
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
    runner: Optional[CommandRunner] = None,
) -> None:
    """Boot a standalone Django dev server pinned to ``bundle_path``.

    Sets ``DJANGO_SETTINGS_MODULE`` (via ``setdefault`` — respects a
    parent process's pin) and ``SCITEX_LIVE_PAPER_BUNDLE`` (always
    overwritten — this *is* the contract), runs ``django.setup()``,
    then delegates to ``runner`` (default: real
    ``call_command``). Blocks until the server is stopped (Ctrl-C).

    M3 will replace this with a real WSGI mount on ``scitex-hub`` —
    keep the surface tiny.
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

    django.setup()
    logger.info(
        "[live-paper] serving %s on http://%s:%d/", resolved, host, port,
    )
    (runner or _default_runner)("runserver", f"{host}:{port}", "--noreload")
