"""No-mocks tests for the embed-mode SPA shell variant.

Host apps (``scitex-hub`` project view, ``scitex-writer`` preview,
``scitex-scholar``) iframe the live-paper viewer into their own page
chrome. The viewer responds to ``?embed=1`` with a stripped-down
template (no header, no subtitle, no status pre) that drops cleanly
into a host iframe.

All collaborators are real:
- Django ``RequestFactory`` builds the request — same lever Django's
  own unit tests use, not a mock.
- The actual template loader walks the real app's
  ``templates/live_paper/`` directory.
"""

from __future__ import annotations

import pytest

pytest.importorskip("django")

from django.test import RequestFactory  # noqa: E402

from scitex_live_paper._django import views  # noqa: E402


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


# ──────────────────────────────────────────────────────────────────
# Default (no query string) — full standalone shell
# ──────────────────────────────────────────────────────────────────


def test_viewer_page_default_returns_full_chrome(rf):
    # arrange
    request = rf.get("/")
    # act
    response = views.viewer_page(request)
    body = response.content.decode("utf-8")
    # assert — standalone shell carries the header + subtitle
    assert response.status_code == 200
    assert "<header" in body
    assert "scitex-clew" in body  # boundary callout in the subtitle


def test_viewer_page_default_omits_embed_data_attribute(rf):
    # arrange
    body = views.viewer_page(rf.get("/")).content.decode("utf-8")
    # assert — only the embed shell carries data-embed-mode
    assert 'data-embed-mode' not in body


def test_viewer_page_default_carries_data_api_base(rf):
    # arrange
    body = views.viewer_page(rf.get("/")).content.decode("utf-8")
    # assert — SPA boot contract preserved
    assert 'data-api-base="/api/"' in body


# ──────────────────────────────────────────────────────────────────
# ?embed=1 — minimal chrome-less shell
# ──────────────────────────────────────────────────────────────────


def test_viewer_page_embed_one_returns_200(rf):
    # arrange / act
    response = views.viewer_page(rf.get("/?embed=1"))
    # assert
    assert response.status_code == 200


def test_viewer_page_embed_one_strips_header(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — no standalone header chrome
    assert "<header" not in body
    assert "Read-only viewer for accepted manuscript bundles." not in body


def test_viewer_page_embed_one_strips_subtitle_text(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — boundary callout copy is part of the standalone subtitle, not the embed
    assert "Claim model owned upstream" not in body


def test_viewer_page_embed_one_carries_data_api_base(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — same SPA boot contract
    assert 'data-api-base="/api/"' in body


def test_viewer_page_embed_one_carries_data_embed_mode(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — JS reads this attribute to suppress its own chrome
    assert 'data-embed-mode="1"' in body


def test_viewer_page_embed_one_carries_root_div(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — SPA mount point still present
    assert 'id="live-paper-root"' in body


def test_viewer_page_embed_one_links_same_css(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — same asset, no separate embed stylesheet to maintain
    assert "live_paper/css/viewer.css" in body


def test_viewer_page_embed_one_links_same_js(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert
    assert "live_paper/js/viewer.js" in body


def test_viewer_page_embed_one_is_cdn_free(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — same vendoring contract as the standalone page
    for marker in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
        assert marker not in body


def test_viewer_page_embed_one_adds_embed_body_class(rf):
    # arrange
    body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert — hosts can use this body class to tune iframe scrollbars / colour
    assert 'class="live-paper-embed"' in body


# ──────────────────────────────────────────────────────────────────
# Embed switch — case-insensitive truthy values, falsy values, absent
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON", "  true  "],
)
def test_embed_mode_truthy_values_select_embed_shell(rf, value):
    # arrange
    request = rf.get(f"/?embed={value}")
    # act
    is_embed = views._is_embed_mode(request)
    # assert
    assert is_embed is True


@pytest.mark.parametrize(
    "value",
    ["0", "false", "False", "no", "off", "", "random-string"],
)
def test_embed_mode_falsy_or_unknown_values_keep_full_chrome(rf, value):
    # arrange
    request = rf.get(f"/?embed={value}")
    # act
    is_embed = views._is_embed_mode(request)
    # assert
    assert is_embed is False


def test_embed_mode_absent_param_keeps_full_chrome(rf):
    # arrange
    request = rf.get("/")
    # act / assert
    assert views._is_embed_mode(request) is False


def test_embed_mode_other_query_params_dont_trigger(rf):
    # arrange — unrelated query params must not trigger embed mode
    body = views.viewer_page(rf.get("/?foo=1&bar=true")).content.decode("utf-8")
    # assert
    assert "<header" in body
    assert 'data-embed-mode' not in body


# ──────────────────────────────────────────────────────────────────
# Default and embed shells stay structurally aligned
# ──────────────────────────────────────────────────────────────────


def test_both_shells_share_live_paper_root_id(rf):
    # arrange — the mount point ID is the contract every host must see
    default_body = views.viewer_page(rf.get("/")).content.decode("utf-8")
    embed_body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert
    assert 'id="live-paper-root"' in default_body
    assert 'id="live-paper-root"' in embed_body


def test_both_shells_share_bundle_info_pre_id(rf):
    # arrange — JS writes the bundle-info JSON into this element regardless
    default_body = views.viewer_page(rf.get("/")).content.decode("utf-8")
    embed_body = views.viewer_page(rf.get("/?embed=1")).content.decode("utf-8")
    # assert
    assert 'id="live-paper-bundle-info"' in default_body
    assert 'id="live-paper-bundle-info"' in embed_body
