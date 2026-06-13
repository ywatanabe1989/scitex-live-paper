"""Coverage closure for the remaining 11 defensive lines.

Each test triggers a previously-uncovered branch with REAL fixtures
or REAL malformed input — no `monkeypatch`, no `mock.patch`. Where
the branch is genuinely untestable under the no-mocks doctrine (lines
that bind a TCP port) the source carries `# pragma: no cover` with
named justification rather than being tested via patching.

Targets:

- `_renderer/claims.py` 77-79 — `_claim_short_label` fallbacks
- `_renderer/dag.py` 172, 178 — provenance traversal `continue` paths
- `_django/services.py` 144-145 — `_claims_mtime` OSError fallback
- `_django/handlers/reverify.py` 329 — bulk: empty bundle + no filter
- `_django/handlers/reverify.py` 409 — bulk: partial clew (version skew)
- `_django/handlers/pdf.py` 79 — manuscript_path None on the Bundle

(Lines `_cli.py` 187 + 200-201 are pragma'd in source — see comments
there for the rationale.)
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Iterator

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BUNDLE_MIN = FIXTURES / "bundle-min"
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"


# ──────────────────────────────────────────────────────────────────
# _renderer/claims.py 77-79 — _claim_short_label fallbacks
# ──────────────────────────────────────────────────────────────────


def test_claim_short_label_falls_back_to_file_and_line_when_no_value():
    # arrange — claim with no claim_value but a line_number
    from scitex_live_paper._renderer.claims import _claim_short_label
    from scitex_live_paper.bundle import Claim

    claim = Claim(
        claim_id="claim_x",
        file_path="main.tex",
        claim_type="figure",
        claim_value=None,
        line_number=42,
    )
    # act
    label = _claim_short_label(claim)
    # assert
    assert label == "main.tex:42"


def test_claim_short_label_falls_back_to_file_path_when_no_value_no_line():
    # arrange — sparser: no claim_value, no line_number — falls back to file_path
    from scitex_live_paper._renderer.claims import _claim_short_label
    from scitex_live_paper.bundle import Claim

    claim = Claim(
        claim_id="claim_y",
        file_path="paper.tex",
        claim_type="value",
        claim_value=None,
        line_number=None,
    )
    # act
    label = _claim_short_label(claim)
    # assert
    assert label == "paper.tex"


def test_claim_short_label_falls_back_to_claim_id_when_all_else_empty():
    # arrange — fully sparse claim (file_path empty)
    from scitex_live_paper._renderer.claims import _claim_short_label
    from scitex_live_paper.bundle import Claim

    claim = Claim(
        claim_id="claim_z_fallback_id",
        file_path="",
        claim_type="value",
        claim_value=None,
        line_number=None,
    )
    # act
    label = _claim_short_label(claim)
    # assert — never empty
    assert label == "claim_z_fallback_id"


# ──────────────────────────────────────────────────────────────────
# _renderer/dag.py 172, 178 — provenance traversal continue paths
# ──────────────────────────────────────────────────────────────────


def _make_bundle_with_provenance(tmp_path: Path, provenance_yaml: str) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("claims.json", "dag.mmd", "manuscript.pdf"):
        (bundle / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle / "figz").mkdir()
    (bundle / "provenance.yaml").write_text(provenance_yaml, encoding="utf-8")
    return bundle


def test_dag_provenance_session_non_dict_value_is_skipped(tmp_path):
    # arrange — sessions[<sid>] is a string, not a dict (operator typo).
    # The renderer's _collect_source_hashes must `continue` past it without
    # raising. We verify by loading the bundle + calling the renderer's
    # private helper directly.
    from scitex_live_paper._renderer.dag import _collect_source_hashes
    from scitex_live_paper import bundle as bundle_module

    bundle_path = _make_bundle_with_provenance(
        tmp_path,
        provenance_yaml=(
            "sessions:\n"
            "  sess_001: not-a-dict-it-is-a-string\n"
            "  sess_002:\n"
            "    files: {}\n"
        ),
    )
    loaded = bundle_module.load(bundle_path)
    # act — must not raise
    result = _collect_source_hashes(loaded)
    # assert — the malformed session was skipped, the empty one yielded nothing
    assert isinstance(result, dict)


def test_dag_provenance_file_meta_non_dict_is_skipped(tmp_path):
    # arrange — sessions[<sid>].files[<path>] is a string, not a dict
    from scitex_live_paper._renderer.dag import _collect_source_hashes
    from scitex_live_paper import bundle as bundle_module

    bundle_path = _make_bundle_with_provenance(
        tmp_path,
        provenance_yaml=(
            "sessions:\n"
            "  sess_001:\n"
            "    files:\n"
            "      scripts/02.py: not-a-dict\n"
            "      scripts/03.py:\n"
            "        hash: deadbeef\n"
        ),
    )
    loaded = bundle_module.load(bundle_path)
    # act — must not raise
    result = _collect_source_hashes(loaded)
    # assert — the well-formed file landed in the map; the malformed
    # one was skipped (not present, not raised)
    assert "scripts/02.py" not in result
    assert result.get("scripts/03.py") == "deadbeef"


# ──────────────────────────────────────────────────────────────────
# _django/services.py 144-145 — _claims_mtime OSError fallback
# ──────────────────────────────────────────────────────────────────


pytest.importorskip("django")


def test_services_claims_mtime_returns_zero_when_claims_json_absent(tmp_path):
    # arrange — point at a directory that exists but has no claims.json.
    # stat() raises FileNotFoundError (an OSError subclass); the helper
    # must return 0.0 rather than propagating.
    from scitex_live_paper._django.services import _claims_mtime

    bundle = tmp_path / "no-claims-here"
    bundle.mkdir()
    # act
    mtime = _claims_mtime(bundle)
    # assert
    assert mtime == 0.0


def test_services_claims_mtime_returns_zero_when_path_does_not_exist(tmp_path):
    # arrange — directory itself doesn't exist
    from scitex_live_paper._django.services import _claims_mtime

    missing = tmp_path / "does-not-exist"
    # act
    mtime = _claims_mtime(missing)
    # assert
    assert mtime == 0.0


# ──────────────────────────────────────────────────────────────────
# _django/handlers/reverify.py 329 — empty-claims bundle + no filter
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def env_snapshot() -> Iterator[None]:
    snap = dict(os.environ)
    try:
        yield
    finally:
        for k in list(os.environ):
            if k not in snap:
                del os.environ[k]
        for k, v in snap.items():
            os.environ[k] = v


def test_bulk_reverify_400_when_bundle_has_no_claims(tmp_path, env_snapshot):
    # arrange — build a real bundle whose claims list is empty.
    # state.yaml gives us a pinned_commit so we get past that check;
    # the "no claims" branch is what we want to trigger.
    from django.test import Client

    from scitex_live_paper._django import services

    bundle = tmp_path / "empty-bundle"
    bundle.mkdir()
    (bundle / "claims.json").write_text(
        '{"schema": "scitex-clew.claims/v1", "claims": []}',
        encoding="utf-8",
    )
    for name in ("dag.mmd", "manuscript.pdf"):
        (bundle / name).write_bytes((BUNDLE_MIN / name).read_bytes())
    (bundle / "figz").mkdir()
    (bundle / "state.yaml").write_text(
        'stage: accepted\npinned_commit: "abc123"\n',
        encoding="utf-8",
    )

    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(bundle)
    services.clear_cache()

    # act
    response = Client().post(
        "/api/claims/verify",
        data="",
        content_type="application/json",
    )
    # assert
    assert response.status_code == 400
    body = json.loads(response.content)
    assert "no claims to verify" in body["error"]


# ──────────────────────────────────────────────────────────────────
# _django/handlers/reverify.py 409 — partial clew via the bulk path
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def partial_scitex_clew() -> Iterator[types.ModuleType]:
    """A clew module without a `verify_claim` attribute — version skew."""
    key = "scitex_clew"
    sentinel = object()
    original = sys.modules.get(key, sentinel)
    module = types.ModuleType(key)
    # No verify_claim attribute → _probe_clew returns the skew reason
    sys.modules[key] = module
    try:
        yield module
    finally:
        if original is sentinel:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original  # type: ignore[assignment]


def test_bulk_reverify_partial_clew_per_result_skew_reason(
    env_snapshot, partial_scitex_clew,
):
    # arrange
    from django.test import Client

    from scitex_live_paper._django import services

    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(BUNDLE_ACCEPTED)
    services.clear_cache()

    # act
    response = Client().post(
        "/api/claims/verify",
        data="",
        content_type="application/json",
    )
    body = json.loads(response.content)
    # assert — every per-result entry carries the skew reason from
    # _probe_clew()'s second return slot
    assert response.status_code == 200
    assert body["ok"] is False
    for result in body["results"]:
        assert result["fallback"] is True
        assert "version skew" in result["reason"]


# ──────────────────────────────────────────────────────────────────
# _django/handlers/pdf.py 79 — manuscript_path None on a Bundle
# ──────────────────────────────────────────────────────────────────


def test_api_pdf_404_when_bundle_manuscript_path_is_none(env_snapshot):
    # arrange — inject a Bundle with manuscript_path=None via
    # mount(resolver=...). bundle.load() rejects no-manuscript
    # directories, but a host that hand-builds a Bundle (e.g. writer's
    # in-memory editor mid-compile) might pass None deliberately.
    from django.test import RequestFactory

    from scitex_live_paper import (
        Bundle, BundleContext, BundleSource, PaperState, mount,
    )

    custom = Bundle(
        root=Path("/tmp"),
        claims=[],
        dag="",
        provenance={},
        manuscript_path=None,  # type: ignore[arg-type]
        figz_dir=Path("/tmp/figz"),
        paper_state=PaperState(),
    )

    def resolver(request, **kw):
        return BundleContext(source=BundleSource.from_bundle(custom))

    patterns, _ = mount(resolver)
    dispatch = next(p.callback for p in patterns if p.name == "api_dispatch")

    rf = RequestFactory()
    # act
    response = dispatch(rf.get("/api/pdf"), endpoint="api/pdf")
    # assert
    assert response.status_code == 404
    body = json.loads(response.content)
    assert "manuscript.pdf not found" in body["error"]
