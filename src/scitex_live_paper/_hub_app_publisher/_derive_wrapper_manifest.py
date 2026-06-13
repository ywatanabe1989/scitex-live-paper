"""``derive_wrapper_manifest`` — pip-shape → hub-workspace-UI shape.

Maps :data:`HUB_APP_MANIFEST` into the scitex-hub `manifest.json`
v2.0.0 UI shape so the wrapper app
(`scitex_live_paper_hub_app/manifest.json`) is generated rather than
hand-filled. Single source of truth: the pip-shape constant.

Mapping:

- ``name``                → ``name`` (the wrapper's stable id)
- ``version``             → ``version``
- ``display_name``        → ``label``
- ``description``         → ``subtitle`` (first sentence),
                            ``about`` (full text),
                            ``description`` (full text)
- ``requires`` (PEP 508)  → ``dependencies.python`` (a list with the
                            ``python>=<py_req>`` entry prepended, then
                            each distribution name with its PEP 508
                            specifier stripped — the hub UI surfaces
                            these as chips, not pin metadata)
- ``permissions``         → ``privileges`` (per the v2.0.0 schema
                            rename; identical semantics)
- ``upstream``, ``category``, ``entry_points``, ``python_requires``
                          → dropped (internal to the publishing
                            layer; the hub UI doesn't surface them)

Callers can override ``label`` / ``subtitle`` to customize per
wrapper without forking the manifest:

.. code-block:: python

    from scitex_live_paper import derive_wrapper_manifest

    manifest = derive_wrapper_manifest(
        label="Live Paper",
        subtitle="Mounted under apps/live-paper/<paper_id>/",
    )
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from ._manifest import HUB_APP_MANIFEST


def derive_wrapper_manifest(
    *,
    label: Optional[str] = None,
    subtitle: Optional[str] = None,
    schema_version: str = "2.0.0",
) -> dict:
    """Map :data:`HUB_APP_MANIFEST` to a hub-side workspace manifest.

    Parameters
    ----------
    label
        Override the workspace tile title. Defaults to
        ``HUB_APP_MANIFEST["display_name"]``.
    subtitle
        Override the short tagline shown under the title. Defaults
        to the first sentence of the description.
    schema_version
        Hub manifest schema version to declare. Defaults to ``"2.0.0"``
        (current schema as of the agentic-journal landing).

    Returns
    -------
    dict
        Plain dict the wrapper can dump straight into
        ``manifest.json``.
    """
    description = str(HUB_APP_MANIFEST.get("description", ""))
    derived_subtitle = subtitle or _first_sentence(description)

    # dependencies.python = `python>=<py_req>` + stripped requires
    python_req = str(HUB_APP_MANIFEST.get("python_requires", "")).strip()
    python_deps: list[str] = []
    if python_req:
        # PEP 508 form for the Python interpreter itself
        python_deps.append(f"python{python_req}")
    python_deps.extend(
        _strip_pep508_versions(tuple(HUB_APP_MANIFEST.get("requires", ())))
    )

    return {
        "schema_version": schema_version,
        "name": HUB_APP_MANIFEST["name"],
        "version": HUB_APP_MANIFEST["version"],
        "label": label or HUB_APP_MANIFEST.get("display_name", ""),
        "subtitle": derived_subtitle,
        "about": description,
        "description": description,
        "dependencies": {
            "python": python_deps,
        },
        # v2.0.0 renamed `permissions` to `privileges`; mirror the
        # rename so the wrapper doesn't carry the old key in lockstep.
        "privileges": list(HUB_APP_MANIFEST.get("permissions", ())),
    }


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


_FIRST_SENTENCE_RE = re.compile(r"^(.+?[.!?])(?:\s|$)")


def _first_sentence(text: str) -> str:
    """Return the first sentence of ``text`` (best-effort).

    "First sentence" = up to the first ``.`` / ``!`` / ``?`` followed
    by whitespace OR end-of-string. Falls back to the trimmed full
    text if no terminator is present.
    """
    text = text.strip()
    if not text:
        return ""
    match = _FIRST_SENTENCE_RE.match(text)
    if match is None:
        return text
    return match.group(1).strip()


_PEP508_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*")


def _strip_pep508_versions(reqs: Mapping[int, Any] | tuple[str, ...]) -> list[str]:
    """Strip the version specifier off each PEP 508 requirement string.

    ``"scitex-clew>=0.1.0"`` → ``"scitex-clew"``. Used to populate
    the v2.0.0 ``dependencies.python`` list (which the hub UI shows
    as chips — not pin metadata).
    """
    out: list[str] = []
    for req in reqs:
        name_match = _PEP508_NAME_RE.match(req)
        if name_match is None:
            continue
        out.append(name_match.group(0))
    return out
