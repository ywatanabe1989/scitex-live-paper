"""No-mocks tests for the M4 paper-level re-review badge.

Verifies:
1. `ReReviewBadge` + `ReReviewStatus` are importable from the top-level
   package + are in `__all__`.
2. `BundleContext.re_review_badge` is an optional field (default `None`).
3. `api/bundle-info` surfaces the badge when present, `null` when absent.
4. The badge field flows through `mount(resolver=...)` correctly.
5. SPA JS / CSS source ships the rendering surface.

All collaborators are real — real Django test Client, real fixtures,
real BundleContext objects. No `monkeypatch`, no `mock.patch`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, get_args

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BUNDLE_ACCEPTED = FIXTURES / "bundle-accepted"


# ──────────────────────────────────────────────────────────────────
# Top-level re-export contract
# ──────────────────────────────────────────────────────────────────


def test_re_review_badge_importable_from_top_level():
    import scitex_live_paper as lp

    assert hasattr(lp, "ReReviewBadge")
    assert hasattr(lp, "ReReviewStatus")


def test_re_review_badge_in_all():
    import scitex_live_paper as lp

    assert "ReReviewBadge" in lp.__all__
    assert "ReReviewStatus" in lp.__all__


# ──────────────────────────────────────────────────────────────────
# ReReviewStatus + ReReviewBadge dataclass contract
# ──────────────────────────────────────────────────────────────────


def test_re_review_status_literal_lists_four_stages():
    from scitex_live_paper import ReReviewStatus

    stages = set(get_args(ReReviewStatus))
    assert stages == {"verified", "concerns", "contradicted", "stale"}


def test_re_review_badge_status_required():
    from scitex_live_paper import ReReviewBadge

    badge = ReReviewBadge(status="verified")
    assert badge.status == "verified"


def test_re_review_badge_all_other_fields_default_to_none():
    from scitex_live_paper import ReReviewBadge

    badge = ReReviewBadge(status="stale")
    assert badge.last_reviewed_at is None
    assert badge.reviewer is None
    assert badge.log_url is None
    assert badge.notes is None


def test_re_review_badge_is_frozen():
    from scitex_live_paper import ReReviewBadge

    badge = ReReviewBadge(status="verified")
    with pytest.raises(Exception):
        badge.status = "stale"  # type: ignore[misc]


def test_re_review_badge_carries_all_fields():
    from scitex_live_paper import ReReviewBadge

    badge = ReReviewBadge(
        status="concerns",
        last_reviewed_at="2026-06-13T03:00:00Z",
        reviewer="agentic-journal-v3",
        log_url="https://journal.scitex.ai/reviews/abc",
        notes="One claim's effect size shrinks under the new control.",
    )
    assert badge.status == "concerns"
    assert badge.reviewer == "agentic-journal-v3"
    assert "scitex.ai" in badge.log_url


# ──────────────────────────────────────────────────────────────────
# BundleContext.re_review_badge field
# ──────────────────────────────────────────────────────────────────


def test_bundle_context_re_review_badge_defaults_to_none():
    from scitex_live_paper import BundleContext, BundleSource

    ctx = BundleContext(source=BundleSource.from_directory(BUNDLE_ACCEPTED))
    assert ctx.re_review_badge is None


def test_bundle_context_carries_re_review_badge_through():
    from scitex_live_paper import BundleContext, BundleSource, ReReviewBadge

    badge = ReReviewBadge(status="verified", reviewer="agentic-journal-v3")
    ctx = BundleContext(
        source=BundleSource.from_directory(BUNDLE_ACCEPTED),
        re_review_badge=badge,
    )
    assert ctx.re_review_badge is badge
    assert ctx.re_review_badge.status == "verified"


# ──────────────────────────────────────────────────────────────────
# bundle-info handler surfaces the badge
# ──────────────────────────────────────────────────────────────────


pytest.importorskip("django")


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


def test_bundle_info_returns_null_re_review_badge_when_absent(env_snapshot):
    # arrange — env-pinned path (no BundleContext, no badge)
    from django.test import Client
    from scitex_live_paper._django import services

    os.environ["SCITEX_LIVE_PAPER_BUNDLE"] = str(BUNDLE_ACCEPTED)
    services.clear_cache()
    # act
    body = json.loads(Client().get("/api/bundle-info").content)
    # assert
    assert "re_review_badge" in body
    assert body["re_review_badge"] is None


def test_bundle_info_surfaces_re_review_badge_via_mount_resolver(env_snapshot):
    # arrange
    from django.test import RequestFactory
    from scitex_live_paper import (
        BundleContext, BundleSource, ReReviewBadge, mount,
    )

    badge = ReReviewBadge(
        status="verified",
        reviewer="agentic-journal-v3",
        last_reviewed_at="2026-06-13T03:00:00Z",
        log_url="https://journal.scitex.ai/reviews/r-123",
        notes="No issues found in the second pass.",
    )

    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_ACCEPTED),
            re_review_badge=badge,
        )

    patterns, _ = mount(resolver)
    dispatch = next(p.callback for p in patterns if p.name == "api_dispatch")

    # act
    response = dispatch(
        RequestFactory().get("/api/bundle-info"),
        endpoint="api/bundle-info",
    )
    body = json.loads(response.content)
    # assert
    assert body["re_review_badge"] is not None
    surfaced = body["re_review_badge"]
    assert surfaced["status"] == "verified"
    assert surfaced["reviewer"] == "agentic-journal-v3"
    assert surfaced["last_reviewed_at"] == "2026-06-13T03:00:00Z"
    assert surfaced["log_url"].startswith("https://journal.scitex.ai")
    assert surfaced["notes"]


@pytest.mark.parametrize(
    "status",
    ["verified", "concerns", "contradicted", "stale"],
)
def test_bundle_info_each_status_flows_through(env_snapshot, status):
    # arrange
    from django.test import RequestFactory
    from scitex_live_paper import (
        BundleContext, BundleSource, ReReviewBadge, mount,
    )

    def resolver(request, **kw):
        return BundleContext(
            source=BundleSource.from_directory(BUNDLE_ACCEPTED),
            re_review_badge=ReReviewBadge(status=status),
        )

    patterns, _ = mount(resolver)
    dispatch = next(p.callback for p in patterns if p.name == "api_dispatch")
    # act
    response = dispatch(
        RequestFactory().get("/api/bundle-info"),
        endpoint="api/bundle-info",
    )
    # assert
    body = json.loads(response.content)
    assert body["re_review_badge"]["status"] == status


# ──────────────────────────────────────────────────────────────────
# SPA UI source — JS module + CSS palette
# ──────────────────────────────────────────────────────────────────


def _js_module(name: str) -> str:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return (pkg_root / "_django/static/live_paper/js" / name).read_text(encoding="utf-8")


def _viewer_css() -> str:
    import scitex_live_paper

    pkg_root = Path(scitex_live_paper.__file__).resolve().parent
    return (pkg_root / "_django/static/live_paper/css/viewer.css").read_text(encoding="utf-8")


def test_re_review_badge_js_module_exists_and_exports():
    text = _js_module("re-review-badge.js")
    assert "export function renderReReviewBadge" in text


def test_viewer_js_orchestrator_imports_re_review_badge():
    text = _js_module("viewer.js")
    assert 'from "./re-review-badge.js"' in text
    # After the dashboard-wire PR, the boot reads bundle from a
    # variable (`bundleInfo`) populated by either dashboard or the
    # fallback — match the call site without re-pinning the literal
    # argument name.
    assert "renderReReviewBadge(rootEl, " in text


def test_re_review_badge_js_reads_payload_field():
    text = _js_module("re-review-badge.js")
    assert "re_review_badge" in text
    assert "badge.status" in text


def test_re_review_badge_js_renders_optional_fields():
    text = _js_module("re-review-badge.js")
    # Reviewer / timestamp / notes / log link are all optional surfaces.
    for needle in ("reviewer", "last_reviewed_at", "notes", "log_url"):
        assert needle in text, f"missing field render: {needle}"


def test_re_review_badge_js_target_blank_on_log_link():
    text = _js_module("re-review-badge.js")
    # Operator clicks the log link from inside an iframe — open in
    # a new tab so the host page doesn't navigate away.
    assert 'target = "_blank"' in text or 'target="_blank"' in text


def test_viewer_css_styles_re_review_badge():
    text = _viewer_css()
    assert ".lp-re-review-badge" in text
    # Per-status border-left mirrors the M2 chip palette
    for status in ("verified", "stale", "contradicted", "concerns"):
        assert f'data-status="{status}"' in text


def test_viewer_css_styles_re_review_badge_label_and_log_link():
    text = _viewer_css()
    assert ".lp-re-review-badge-label" in text
    assert ".lp-re-review-badge-log" in text
