"""STX-TQ tests for the ``_django`` skeleton — issue #8 done-when checks.

AAA blocks. Each test pins the input, runs the action, then asserts on
the response. The only branch that needs the real bundle pinned in env
is ``bundle-info``; ``ping`` and the SPA shell work without one.
"""

from __future__ import annotations

import json

import pytest


# ──────────────────────────────────────────────────────────────────
# viewer_page (SPA shell)
# ──────────────────────────────────────────────────────────────────


def test_viewer_page_returns_200(client):
    # arrange
    url = "/"
    # act
    response = client.get(url)
    # assert
    assert response.status_code == 200


def test_viewer_page_contains_data_api_base_attribute(client):
    # arrange
    url = "/"
    # act
    response = client.get(url)
    # assert
    body = response.content.decode("utf-8")
    assert 'data-api-base="/api/"' in body


def test_viewer_page_references_scitex_clew_boundary(client):
    # arrange
    url = "/"
    # act
    body = client.get(url).content.decode("utf-8")
    # assert
    assert "scitex-clew" in body


# ──────────────────────────────────────────────────────────────────
# api/ping
# ──────────────────────────────────────────────────────────────────


def test_api_ping_returns_200(client):
    # arrange
    url = "/api/ping"
    # act
    response = client.get(url)
    # assert
    assert response.status_code == 200


def test_api_ping_returns_ok_true(client):
    # arrange
    url = "/api/ping"
    # act
    payload = json.loads(client.get(url).content)
    # assert
    assert payload == {"ok": True, "app": "scitex-live-paper"}


# ──────────────────────────────────────────────────────────────────
# api/bundle-info
# ──────────────────────────────────────────────────────────────────


def test_api_bundle_info_returns_200(client, bundle_env):
    # arrange
    url = "/api/bundle-info"
    # act
    response = client.get(url)
    # assert
    assert response.status_code == 200


def test_api_bundle_info_reports_three_claims(client, bundle_env):
    # arrange
    url = "/api/bundle-info"
    # act
    payload = json.loads(client.get(url).content)
    # assert — bundle-min ships exactly three claims
    assert payload["claim_count"] == 3


def test_api_bundle_info_carries_clew_schema_version(client, bundle_env):
    # arrange
    url = "/api/bundle-info"
    # act
    payload = json.loads(client.get(url).content)
    # assert — schema string owned by scitex-clew, mirrored verbatim
    assert payload["schema"] == "scitex-clew.claims/v1"


def test_api_bundle_info_reports_manuscript_pdf(client, bundle_env):
    # arrange
    url = "/api/bundle-info"
    # act
    payload = json.loads(client.get(url).content)
    # assert
    assert payload["manuscript"] == "manuscript.pdf"


def test_api_bundle_info_reports_dag_present(client, bundle_env):
    # arrange
    url = "/api/bundle-info"
    # act
    payload = json.loads(client.get(url).content)
    # assert — bundle-min ships a non-empty dag.mmd
    assert payload["dag_present"] is True


def test_api_bundle_info_resolves_absolute_bundle_path(client, bundle_env):
    # arrange
    url = "/api/bundle-info"
    # act
    payload = json.loads(client.get(url).content)
    # assert
    assert payload["bundle_path"].endswith("bundle-min")


def test_api_bundle_info_without_env_returns_500(client, monkeypatch):
    # arrange
    from scitex_live_paper._django import services

    monkeypatch.delenv("SCITEX_LIVE_PAPER_BUNDLE", raising=False)
    services.clear_cache()
    # act
    response = client.get("/api/bundle-info")
    # assert — services.resolve_bundle_path raises RuntimeError → dispatcher 500
    assert response.status_code == 500


# ──────────────────────────────────────────────────────────────────
# HANDLERS registry + dispatcher
# ──────────────────────────────────────────────────────────────────


def test_handlers_registry_lists_known_endpoints():
    # arrange
    from scitex_live_paper._django.handlers import HANDLERS

    # act
    keys = set(HANDLERS.keys())
    # assert
    assert {"api/ping", "api/bundle-info"} <= keys


def test_handlers_registry_values_are_callables():
    # arrange
    from scitex_live_paper._django.handlers import HANDLERS

    # act / assert
    for endpoint, fn in HANDLERS.items():
        assert callable(fn), f"{endpoint!r} → non-callable"


def test_unknown_endpoint_returns_404(client):
    # arrange
    url = "/api/does-not-exist"
    # act
    response = client.get(url)
    # assert
    assert response.status_code == 404


def test_unknown_endpoint_returns_json_error_body(client):
    # arrange
    url = "/api/does-not-exist"
    # act
    payload = json.loads(client.get(url).content)
    # assert
    assert "error" in payload
    assert "does-not-exist" in payload["error"]


# ──────────────────────────────────────────────────────────────────
# services cache behaviour
# ──────────────────────────────────────────────────────────────────


def test_services_cache_reuses_state_within_ttl(bundle_env):
    # arrange
    from scitex_live_paper._django import services

    # act
    first = services.get_bundle_state()
    second = services.get_bundle_state()
    # assert — same object id implies the in-process cache hit
    assert first is second


def test_services_resolve_bundle_path_raises_without_env(monkeypatch):
    # arrange
    from scitex_live_paper._django import services

    monkeypatch.delenv("SCITEX_LIVE_PAPER_BUNDLE", raising=False)
    # act / assert
    with pytest.raises(RuntimeError, match="SCITEX_LIVE_PAPER_BUNDLE"):
        services.resolve_bundle_path()


# ──────────────────────────────────────────────────────────────────
# Manifest + apps
# ──────────────────────────────────────────────────────────────────


def test_manifest_slug_is_live_paper():
    # arrange
    from importlib import resources

    # act
    data = json.loads(
        resources.files("scitex_live_paper._django")
        .joinpath("manifest.json")
        .read_text(encoding="utf-8")
    )
    # assert
    assert data["slug"] == "live-paper"


def test_apps_config_exposes_correct_name():
    # arrange
    from scitex_live_paper._django.apps import LivePaperConfig

    # act / assert
    assert LivePaperConfig.name == "scitex_live_paper._django"
    assert LivePaperConfig.label == "scitex_live_paper"


# ──────────────────────────────────────────────────────────────────
# CLI `serve` subcommand surface
# ──────────────────────────────────────────────────────────────────


def test_cli_top_level_help_lists_serve():
    # arrange
    from click.testing import CliRunner

    from scitex_live_paper._cli import cli

    # act
    result = CliRunner().invoke(cli, ["--help"])
    # assert
    assert result.exit_code == 0
    assert "serve" in result.output


def test_cli_serve_help_describes_django_extra():
    # arrange
    from click.testing import CliRunner

    from scitex_live_paper._cli import cli

    # act
    result = CliRunner().invoke(cli, ["serve", "--help"])
    # assert
    assert result.exit_code == 0
    assert "django" in result.output.lower() or "[django]" in result.output
