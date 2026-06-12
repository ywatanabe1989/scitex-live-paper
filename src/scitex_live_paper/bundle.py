"""Bundle loader for `scitex-live-paper`.

Reads an accepted manuscript bundle directory laid out as:

    bundle/
      manuscript.pdf     (or .tex)
      claims.json        # schema OWNED by scitex-clew (read-only here)
      dag.mmd            # mermaid source string (from clew)
      figz/              # figure blobs (figz / pltz)
      provenance.yaml    # hash-linked artefacts
      state.yaml         # OPTIONAL render-time lifecycle metadata
                         # (preprint / accepted / published, journal,
                         # DOI, pinned re-verify commit). Absent →
                         # defaults to ``PaperState(stage="preprint")``.

Boundary
--------
`scitex-live-paper` is a **thin consumer** of the claim model. We mirror
the fields we need to *render* — id / type / status / hash / source link
— and stash everything else under ``Claim.extras`` so forward-compatible
fields added by ``scitex-clew`` flow through untouched.

The ``state.yaml`` convention is owned by **this** package (render-time
metadata — header label, re-verify pin) and does not extend or modify
the upstream claim / DAG schemas. Hosts can override at render/mount
time via :class:`scitex_live_paper.BundleContext`; the value here is
the bundle's own default.

If a feature requires a new claim field, **open the upstream issue against
``scitex-clew``** — never invent fields here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from ._types import PaperState, PaperStage

__all__ = ["Bundle", "Claim", "load", "BundleError"]


# Keys ``state.yaml`` may carry. Anything else is preserved verbatim
# inside ``PaperState`` via field mapping; truly unknown keys are
# ignored (forward-compatible). Mirrors the cautious approach we use
# for ``Claim.extras``.
_STATE_TYPED_FIELDS = frozenset(
    {
        "stage",
        "journal",
        "doi",
        "accepted_at",
        "pinned_commit",
    }
)

#: Stages the loader accepts in ``state.yaml``. Mirrors
#: :data:`scitex_live_paper.PaperStage` — keep in sync.
_VALID_STAGES = frozenset(
    {"draft", "preprint", "in_review", "accepted", "published"}
)


def _default_paper_state() -> "PaperState":
    """Return :class:`PaperState` default (``stage="preprint"``).

    Lazy import so :mod:`bundle` stays importable without forcing
    :mod:`._types` first (the two re-export through ``__init__``).
    """
    from ._types import PaperState

    return PaperState()


class BundleError(ValueError):
    """Raised when a bundle directory is malformed or missing a required file."""


# Fields we deserialise into typed slots. Anything else from clew's
# Claim.to_dict() flows through into ``Claim.extras`` so future schema
# additions do not break the renderer.
_CLAIM_TYPED_FIELDS = frozenset(
    {
        "claim_id",
        "file_path",
        "line_number",
        "claim_type",
        "claim_value",
        "source_session",
        "source_file",
        "source_hash",
        "registered_at",
        "verified_at",
        "status",
    }
)


@dataclass
class Claim:
    """A traceable assertion, mirrored from ``scitex_clew.Claim``.

    This dataclass **mirrors** the upstream shape; it does not define or
    extend it. Unknown fields are preserved in ``extras`` so a clew
    schema bump does not require a release here.
    """

    claim_id: str
    file_path: str
    claim_type: str
    line_number: int | None = None
    claim_value: str | None = None
    source_session: str | None = None
    source_file: str | None = None
    source_hash: str | None = None
    registered_at: str | None = None
    verified_at: str | None = None
    status: str = "registered"
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        """Lenient deserialiser. Tolerates unknown keys (stashed in ``extras``).

        Raises
        ------
        BundleError
            If a required field (``claim_id`` / ``file_path`` /
            ``claim_type``) is missing.
        """
        if not isinstance(data, dict):
            raise BundleError(f"claim entry must be a mapping, got {type(data).__name__}")
        for required in ("claim_id", "file_path", "claim_type"):
            if required not in data:
                raise BundleError(f"claim entry missing required field: {required!r}")
        typed = {k: v for k, v in data.items() if k in _CLAIM_TYPED_FIELDS}
        extras = {k: v for k, v in data.items() if k not in _CLAIM_TYPED_FIELDS}
        return cls(**typed, extras=extras)


@dataclass
class Bundle:
    """An accepted manuscript bundle, loaded into memory.

    Attributes
    ----------
    root
        Path to the bundle directory itself.
    claims
        Parsed claim list (from ``claims.json``). May be empty.
    dag
        Mermaid source string from ``dag.mmd`` (empty string if absent).
    provenance
        Parsed ``provenance.yaml`` (empty dict if absent).
    manuscript_path
        Path to ``manuscript.pdf`` or ``manuscript.tex`` (whichever exists).
    figz_dir
        Path to ``figz/`` (may not exist on disk; check before use).
    schema_version
        Optional ``"schema"`` value carried from ``claims.json`` (passes
        through for the renderer to display; this package does not
        validate the version).
    paper_state
        Render-time lifecycle metadata loaded from the bundle's
        optional ``state.yaml`` (see :func:`_load_paper_state`). Absent
        file → :class:`PaperState` default (``stage="preprint"``).
        Hosts can override at render/mount time via
        :class:`scitex_live_paper.BundleContext.paper_state`; the value
        here is the bundle's own default.
    """

    root: Path
    claims: list[Claim]
    dag: str
    provenance: dict[str, Any]
    manuscript_path: Path
    figz_dir: Path
    schema_version: str | None = None
    paper_state: "PaperState" = field(default_factory=_default_paper_state)


def _resolve_manuscript(root: Path) -> Path:
    """Locate ``manuscript.pdf`` (preferred) or ``manuscript.tex`` in *root*."""
    pdf = root / "manuscript.pdf"
    if pdf.exists():
        return pdf
    tex = root / "manuscript.tex"
    if tex.exists():
        return tex
    raise BundleError(
        f"no manuscript found in {root} (expected manuscript.pdf or manuscript.tex)"
    )


def _load_claims(path: Path) -> tuple[list[Claim], str | None]:
    """Parse ``claims.json`` leniently.

    Accepts either:
      - a bare list ``[{...}, {...}]`` (clew's natural collection shape), or
      - a wrapper ``{"schema": "...", "claims": [{...}, ...]}``.
    """
    if not path.exists():
        raise BundleError(f"claims.json not found at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleError(f"claims.json is not valid JSON: {exc}") from exc

    if isinstance(raw, list):
        entries, schema_version = raw, None
    elif isinstance(raw, dict) and "claims" in raw:
        if not isinstance(raw["claims"], list):
            raise BundleError("claims.json: 'claims' key must hold a list")
        entries = raw["claims"]
        schema_version = raw.get("schema")
        if schema_version is not None and not isinstance(schema_version, str):
            raise BundleError("claims.json: 'schema' must be a string when present")
    else:
        raise BundleError(
            "claims.json: top level must be a list or a {'claims': [...]} object"
        )

    return [Claim.from_dict(entry) for entry in entries], schema_version


def _load_dag(path: Path) -> str:
    """Read ``dag.mmd`` as text; missing file → empty string (renderer skips DAG view)."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_provenance(path: Path) -> dict[str, Any]:
    """Parse ``provenance.yaml``; missing or empty file → empty dict."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    parsed = yaml.safe_load(text)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise BundleError("provenance.yaml: top level must be a mapping")
    return parsed


def _load_paper_state(path: Path) -> "PaperState":
    """Parse ``state.yaml`` into :class:`PaperState`; absent → preprint default.

    The ``state.yaml`` schema is intentionally tiny — a flat mapping of
    the :class:`PaperState` fields:

    .. code-block:: yaml

       stage: accepted             # required if file present; one of the
                                   # five PaperStage literals.
       journal: Nature             # optional
       doi: 10.1038/s41586-...     # optional
       accepted_at: 2026-06-01...  # optional ISO-8601 string
       pinned_commit: abc123...    # optional, for M2 re-verify

    Unknown keys are ignored (forward-compatible). Malformed values
    raise :class:`BundleError` with a clear message — never silently
    fall back to the default, that would mask operator typos.
    """
    from ._types import PaperState

    if not path.exists():
        return PaperState()

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return PaperState()

    parsed = yaml.safe_load(text)
    if parsed is None:
        return PaperState()
    if not isinstance(parsed, dict):
        raise BundleError("state.yaml: top level must be a mapping")

    stage = parsed.get("stage", "preprint")
    if not isinstance(stage, str):
        raise BundleError(
            f"state.yaml: 'stage' must be a string, got {type(stage).__name__}"
        )
    if stage not in _VALID_STAGES:
        raise BundleError(
            f"state.yaml: unknown stage {stage!r} "
            f"(expected one of {sorted(_VALID_STAGES)!r})"
        )

    # All other fields are optional strings; raise loud if a host writes
    # a non-string-coercible value by accident. ``accepted_at`` is a
    # known footgun: an unquoted ``2026-06-01T10:00:00Z`` parses as a
    # ``datetime`` under YAML's implicit timestamp tag, so we coerce
    # those (and dates) to ISO strings on the way through. Anything
    # else non-string is rejected loudly.
    import datetime as _datetime  # noqa: WPS433 — local: only this branch needs it

    kwargs: dict[str, Any] = {"stage": stage}
    for key in ("journal", "doi", "accepted_at", "pinned_commit"):
        if key not in parsed:
            continue
        value = parsed[key]
        if value is None:
            continue  # explicit null is equivalent to absent
        if isinstance(value, str):
            kwargs[key] = value
            continue
        if isinstance(value, (_datetime.datetime, _datetime.date)):
            # YAML auto-parsed an ISO timestamp / date for us; convert
            # back to its canonical string so the operator-visible form
            # in PaperState stays a plain str.
            kwargs[key] = value.isoformat()
            continue
        raise BundleError(
            f"state.yaml: {key!r} must be a string, got {type(value).__name__}"
        )

    return PaperState(**kwargs)  # type: ignore[arg-type]


def load(path: str | Path) -> Bundle:
    """Load a bundle directory into a :class:`Bundle`.

    Parameters
    ----------
    path
        Directory containing the bundle layout (see module docstring).

    Returns
    -------
    Bundle
        Fully-resolved bundle ready for the renderer.

    Raises
    ------
    BundleError
        If the directory does not exist, or any required member is missing
        / malformed.
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise BundleError(f"bundle path is not a directory: {root}")

    manuscript_path = _resolve_manuscript(root)
    claims, schema_version = _load_claims(root / "claims.json")
    dag = _load_dag(root / "dag.mmd")
    provenance = _load_provenance(root / "provenance.yaml")
    paper_state = _load_paper_state(root / "state.yaml")
    figz_dir = root / "figz"

    return Bundle(
        root=root,
        claims=claims,
        dag=dag,
        provenance=provenance,
        manuscript_path=manuscript_path,
        figz_dir=figz_dir,
        schema_version=schema_version,
        paper_state=paper_state,
    )
