"""Tests for ``mad versions`` and ``mad update``.

These exercise the command surface against the *real* core (instances discovered
from ``MAD_CLI_CONFIG_DIR``), mocking only the two things that would touch the
network or Docker: ``ComposeRunner`` and ``core.pypi.latest_version``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.compose import ComposeError


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _write_instance(root: Path, name: str, **env: str) -> Path:
    d = root / "instances" / name
    d.mkdir(parents=True)
    lines = [f"{k}={v}" for k, v in env.items()]
    (d / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


# ── versions ──────────────────────────────────────────────────────────────────


def test_versions_running_vs_stopped(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    _write_instance(config_dir, "web", MAD_HOST_PORT="9000", MAD_VERSION="0.5.0")
    _write_instance(config_dir, "api", MAD_HOST_PORT="9100")  # tracks latest, stopped

    def fake_runner(instance, **kwargs):  # type: ignore[no-untyped-def]
        runner = MagicMock()
        if instance.name == "web":
            runner.exec.return_value = "0.6.0\n"
        else:
            runner.exec.side_effect = ComposeError("no such service")
        return runner

    monkeypatch.setattr(mod, "ComposeRunner", fake_runner)
    monkeypatch.setattr(mod.pypi, "latest_version", lambda package, **kw: "0.6.0")

    result = cli.invoke(app, ["versions"])
    assert result.exit_code == 0, result.output
    # running instance: installed reported, up to date against latest
    assert "0.6.0" in result.output
    assert "up to date" in result.output
    # stopped instance: exec raised -> "not running", pinned column shows "latest"
    assert "not running" in result.output
    assert "latest" in result.output


def test_versions_update_available(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    _write_instance(config_dir, "web", MAD_HOST_PORT="9000")

    runner = MagicMock()
    runner.exec.return_value = "0.5.0\n"
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(return_value=runner))
    monkeypatch.setattr(mod.pypi, "latest_version", lambda package, **kw: "0.6.0")

    result = cli.invoke(app, ["versions", "web"])
    assert result.exit_code == 0, result.output
    assert "update available" in result.output


def test_versions_latest_unknown_shows_question_mark(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    _write_instance(config_dir, "web", MAD_HOST_PORT="9000")

    runner = MagicMock()
    runner.exec.return_value = "0.6.0\n"
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(return_value=runner))
    # PyPI unreachable -> None -> "?" in both Latest and Update columns.
    monkeypatch.setattr(mod.pypi, "latest_version", lambda package, **kw: None)

    result = cli.invoke(app, ["versions", "web"])
    assert result.exit_code == 0, result.output
    assert "?" in result.output


def test_versions_uses_env_edge_package_override(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    _write_instance(config_dir, "web", MAD_HOST_PORT="9000", MAD_EDGE_PACKAGE="mad-bros")

    runner = MagicMock()
    runner.exec.return_value = "0.6.0\n"
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(return_value=runner))
    seen: list[str] = []

    def fake_latest(package: str, **kw: object) -> str:
        seen.append(package)
        return "0.6.0"

    monkeypatch.setattr(mod.pypi, "latest_version", fake_latest)

    result = cli.invoke(app, ["versions", "web"])
    assert result.exit_code == 0, result.output
    assert seen == ["mad-bros"]


def test_versions_unknown_instance_errors(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    monkeypatch.setattr(mod, "ComposeRunner", MagicMock())
    result = cli.invoke(app, ["versions", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_versions_empty_hints_install(cli: CliRunner, config_dir: Path) -> None:
    result = cli.invoke(app, ["versions"])
    assert result.exit_code == 0, result.output
    assert "mad install" in result.output


# ── update ────────────────────────────────────────────────────────────────────


def test_update_pins_version_and_rebuilds_in_order(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    inst_dir = _write_instance(config_dir, "web", MAD_HOST_PORT="9000", MAD_VERSION="")

    runner = MagicMock()
    runner.wait_healthy.return_value = True
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(return_value=runner))

    result = cli.invoke(app, ["update", "web", "--version", "0.7.0"])
    assert result.exit_code == 0, result.output

    # MAD_VERSION is persisted to the real .env
    assert "MAD_VERSION=0.7.0" in (inst_dir / ".env").read_text(encoding="utf-8")

    # build(no_cache=True) -> up() -> wait_healthy(), in that order
    assert [c[0] for c in runner.method_calls] == ["build", "up", "wait_healthy"]
    runner.build.assert_called_once_with(no_cache=True)
    runner.up.assert_called_once_with()
    runner.wait_healthy.assert_called_once()


def test_update_without_version_tracks_latest(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    inst_dir = _write_instance(config_dir, "web", MAD_HOST_PORT="9000", MAD_VERSION="0.5.0")

    runner = MagicMock()
    runner.wait_healthy.return_value = True
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(return_value=runner))

    result = cli.invoke(app, ["update", "web"])
    assert result.exit_code == 0, result.output
    # blank pin means "track latest"
    assert "MAD_VERSION=\n" in (inst_dir / ".env").read_text(encoding="utf-8")
    assert "latest" in result.output


def test_update_unhealthy_exits_nonzero(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    _write_instance(config_dir, "web", MAD_HOST_PORT="9000")

    runner = MagicMock()
    runner.wait_healthy.return_value = False
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(return_value=runner))

    result = cli.invoke(app, ["update", "web"])
    assert result.exit_code != 0
    assert "not healthy" in result.output


def test_update_unknown_instance_errors(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import versions as mod

    monkeypatch.setattr(mod, "ComposeRunner", MagicMock())
    result = cli.invoke(app, ["update", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output
