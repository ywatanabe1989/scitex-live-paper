"""In-process bundle cache for the live-paper Django app.

``BundleState`` wraps a loaded :class:`scitex_live_paper.bundle.Bundle`
plus the timestamp at which it was loaded. ``get_bundle_state`` keys an
in-process cache by *resolved* bundle path and invalidates entries when:

- the configured TTL has elapsed, OR
- the bundle's ``claims.json`` mtime has changed.

That dual invalidation is enough for the M1 skeleton — local dev only.
The hub mount (M3) will swap this for a multi-tenant lookup keyed by
working-dir, but the dispatcher surface (``BundleState`` shape) stays
stable across the two implementations.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from scitex_live_paper import bundle as bundle_module

logger = logging.getLogger(__name__)

# bundle_path (resolved str) -> (BundleState, last_loaded_at_monotonic, claims_mtime_or_zero)
_cache: Dict[str, Tuple["BundleState", float, float]] = {}

DEFAULT_TTL_SECONDS = 30
_BUNDLE_ENV_KEY = "SCITEX_LIVE_PAPER_BUNDLE"


@dataclass(frozen=True)
class BundleState:
    """A loaded bundle plus the wall-clock at which it was loaded.

    Frozen so handlers cannot mutate cache entries by accident.
    """

    bundle_path: Path
    bundle: bundle_module.Bundle
    loaded_at: float

    @property
    def claim_count(self) -> int:
        return len(self.bundle.claims)


def resolve_bundle_path() -> Path:
    """Return the bundle path pinned for this process.

    Raised as a plain ``RuntimeError`` so the dispatcher surfaces it as a
    500 (rather than passing through a misleading 404).
    """
    raw = os.environ.get(_BUNDLE_ENV_KEY)
    if not raw:
        raise RuntimeError(
            f"environment variable {_BUNDLE_ENV_KEY!r} not set — "
            "the standalone server pins the bundle path on startup; "
            "the hub mount (M3) sets it per-request."
        )
    return Path(raw).expanduser().resolve()


def get_bundle_state(
    bundle_path: str | Path | None = None,
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
) -> BundleState:
    """Return a cached :class:`BundleState` for ``bundle_path``.

    Falls back to :func:`resolve_bundle_path` (env-pinned) when no path
    is passed — that's the normal request-time path.
    """
    path = Path(bundle_path).expanduser().resolve() if bundle_path else resolve_bundle_path()
    key = str(path)
    now = time.monotonic()

    cached = _cache.get(key)
    claims_mtime = _claims_mtime(path)
    if cached is not None:
        state, loaded_at, cached_mtime = cached
        within_ttl = (now - loaded_at) <= ttl_seconds
        mtime_unchanged = cached_mtime == claims_mtime
        if within_ttl and mtime_unchanged:
            return state

    loaded = bundle_module.load(path)
    state = BundleState(bundle_path=path, bundle=loaded, loaded_at=time.time())
    _cache[key] = (state, now, claims_mtime)
    return state


def clear_cache() -> None:
    """Drop the in-process cache (used by tests)."""
    _cache.clear()


def _claims_mtime(path: Path) -> float:
    """Best-effort claims.json mtime — 0.0 if absent (loader will error later)."""
    candidate = path / "claims.json"
    try:
        return candidate.stat().st_mtime
    except OSError:
        return 0.0
