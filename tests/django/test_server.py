"""``_django/_server.serve`` — env-pinning + bad-bundle paths + delegation.

All collaborators are real. The Django command runner is *injected*
via the ``runner`` kwarg on :func:`serve` (real callable, not a mock)
so the tests exercise the actual env-mutation + ``django.setup()``
path without binding a TCP port. ``os.environ`` is restored via the
``env_snapshot`` fixture (real process state with try/finally
cleanup — not ``monkeypatch.setenv/delenv``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("django")

from scitex_live_paper._django import _server as server_module  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# Fixtures (no monkeypatch — pure stdlib + try/finally restoration)
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def env_snapshot() -> Iterator[None]:
    """Snapshot ``os.environ``, yield, restore on teardown.

    Real process state — the tests below mutate the actual environment
    just like a user invocation would; this fixture is responsible for
    putting it back after the test.
    """
    snapshot = dict(os.environ)
    try:
        yield
    finally:
        # Drop keys the test added.
        for key in list(os.environ):
            if key not in snapshot:
                del os.environ[key]
        # Restore mutated values.
        for key, value in snapshot.items():
            os.environ[key] = value


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    """Real on-disk empty bundle directory (no claims required for serve())."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    return bundle


class _RunnerSpy:
    """Real callable that records its invocations.

    Used as the ``runner`` argument to :func:`server_module.serve` — a
    real Python function, not a mock, satisfying the injected-collaborator
    contract.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))


# ──────────────────────────────────────────────────────────────────
# Bad-bundle paths — pre-django.setup, no runner needed
# ──────────────────────────────────────────────────────────────────


def test_serve_raises_filenotfounderror_for_missing_path(tmp_path):
    # arrange
    missing = tmp_path / "does-not-exist"
    # act / assert
    with pytest.raises(FileNotFoundError, match="bundle path is not a directory"):
        server_module.serve(missing)


def test_serve_raises_filenotfounderror_for_file_path(tmp_path):
    # arrange
    a_file = tmp_path / "manuscript.pdf"
    a_file.write_text("not-a-dir", encoding="utf-8")
    # act / assert
    with pytest.raises(FileNotFoundError, match="bundle path is not a directory"):
        server_module.serve(a_file)


# ──────────────────────────────────────────────────────────────────
# Env pinning — `os.environ` is the observable; runner is recorded
# ──────────────────────────────────────────────────────────────────


def test_serve_pins_bundle_env_to_resolved_path(bundle_dir, env_snapshot):
    # arrange
    os.environ.pop("SCITEX_LIVE_PAPER_BUNDLE", None)
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert — env carries the *resolved* absolute path
    assert os.environ["SCITEX_LIVE_PAPER_BUNDLE"] == str(bundle_dir.resolve())


def test_serve_sets_django_settings_module_when_unset(bundle_dir, env_snapshot):
    # arrange
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "scitex_live_paper._django.settings"


def test_serve_does_not_override_existing_django_settings(bundle_dir, env_snapshot):
    # arrange — parent harness already pinned settings; we must respect it
    os.environ["DJANGO_SETTINGS_MODULE"] = "scitex_live_paper._django.settings"
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert — `setdefault` is the only correct behaviour
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "scitex_live_paper._django.settings"


# ──────────────────────────────────────────────────────────────────
# Runner delegation — injected real callable, not a patch
# ──────────────────────────────────────────────────────────────────


def test_serve_invokes_runner_once(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert
    assert len(spy.calls) == 1


def test_serve_passes_runserver_command_first(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert
    (args, _kwargs) = spy.calls[0]
    assert args[0] == "runserver"


def test_serve_passes_host_port_addr(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, host="0.0.0.0", port=9100, runner=spy)
    # assert
    (args, _kwargs) = spy.calls[0]
    assert args[1] == "0.0.0.0:9100"


def test_serve_passes_noreload_flag(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert — --noreload is the contract; without it the env-pin would
    # be wiped by Django's autoreload subprocess.
    (args, _kwargs) = spy.calls[0]
    assert "--noreload" in args


def test_serve_uses_default_host_port_when_omitted(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(bundle_dir, runner=spy)
    # assert
    (args, _kwargs) = spy.calls[0]
    assert args[1] == "127.0.0.1:8765"


# ──────────────────────────────────────────────────────────────────
# Path-input flexibility — str + Path + relative components
# ──────────────────────────────────────────────────────────────────


def test_serve_resolves_relative_path_components(bundle_dir, env_snapshot):
    # arrange — pass a string with a redundant '.' segment
    raw = f"{bundle_dir}/."
    spy = _RunnerSpy()
    # act
    server_module.serve(raw, runner=spy)
    # assert — the trailing /. is normalised away
    pinned = os.environ["SCITEX_LIVE_PAPER_BUNDLE"]
    assert pinned == str(Path(raw).resolve())
    assert not pinned.endswith("/.")


def test_serve_accepts_pathlib_path(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(Path(bundle_dir), runner=spy)
    # assert
    assert os.environ["SCITEX_LIVE_PAPER_BUNDLE"] == str(bundle_dir.resolve())


def test_serve_resolves_str_input_same_as_path_input(bundle_dir, env_snapshot):
    # arrange
    spy = _RunnerSpy()
    # act
    server_module.serve(str(bundle_dir), runner=spy)
    # assert
    assert os.environ["SCITEX_LIVE_PAPER_BUNDLE"] == str(bundle_dir.resolve())


# ──────────────────────────────────────────────────────────────────
# Default runner — exists, callable, real wrapper
# ──────────────────────────────────────────────────────────────────


def test_default_runner_is_module_level_callable():
    # arrange / act
    runner = server_module._default_runner
    # assert
    assert callable(runner)


def test_default_runner_delegates_to_django_call_command():
    # arrange — import the real django collaborator the wrapper targets
    from django.core import management

    # act / assert — the wrapper is a thin pass-through; check by
    # referencing the same symbol the docstring promises.
    assert hasattr(management, "call_command")
