"""Tests for ``mad list`` and ``mad info``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.instance import InstanceNotFoundError


def test_list_empty_hints_install(cli: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    from mad_cli.core.usecases import instances as mod

    monkeypatch.setattr(mod, "discover_instances", lambda: [])
    result = cli.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "mad install" in result.output


def test_list_renders_both_instances(
    cli: CliRunner, make_instance, make_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.core.usecases import instances as mod

    web = make_instance(name="web", host_port=9000, env=make_env({"MAD_VERSION": "0.6.0"}))
    api = make_instance(name="api", host_port=9100, legacy=True)
    monkeypatch.setattr(mod, "discover_instances", lambda: [web, api])
    # docker unavailable -> state is best-effort "unknown", must not crash the table
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(side_effect=RuntimeError("no docker")))

    result = cli.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "web" in result.output
    assert "api" in result.output
    assert "legacy" in result.output
    # new columns: State/Health degrade gracefully when Docker is unreachable
    for column in ("State", "Health", "Version"):
        assert column in result.output
    assert "unknown" in result.output  # state
    # Version column: pinned version for web, "latest" for the unpinned legacy instance
    assert "0.6.0" in result.output
    assert "latest" in result.output


def test_info_masks_secret_env_values(
    cli: CliRunner, make_instance, make_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.commands import instances as mod

    env = make_env(
        {
            "MAD_INSTANCE": "web",
            "GITHUB_TOKEN": "ghp_supersecretvalue",
            "GIT_AUTHOR_NAME": "Ada Lovelace",
        }
    )
    inst = make_instance(
        name="web",
        env=env,
        config_dir=Path("/cfg/web"),
        compose_file=Path("/cfg/web/compose.yml"),
        data_path=Path("/data/web"),
    )
    # instance_info resolves via the use case; masking is applied by the command.
    from mad_cli.core.usecases import instances as uc_mod

    monkeypatch.setattr(uc_mod, "get_instance", lambda name: inst)
    monkeypatch.setattr(mod, "mask", lambda value: "sk-masked-xx")

    result = cli.invoke(app, ["info", "web"])
    assert result.exit_code == 0, result.output
    assert "GITHUB_TOKEN" in result.output
    assert "ghp_supersecretvalue" not in result.output
    assert "sk-masked-xx" in result.output
    # non-secret values are shown verbatim
    assert "Ada Lovelace" in result.output


def test_info_unknown_instance_errors(cli: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    from mad_cli.core.usecases import instances as mod

    def _raise(name: str):
        raise InstanceNotFoundError(name)

    monkeypatch.setattr(mod, "get_instance", _raise)
    result = cli.invoke(app, ["info", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


# ── adopt ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _write_legacy(root: Path, name: str) -> None:
    """Write a legacy single-instance layout directly at the config root."""
    (root / ".env").write_text(f"MAD_INSTANCE={name}\nMAD_HOST_PORT=8080\n", encoding="utf-8")
    (root / "compose.yml").write_text("services: {}\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (root / "entrypoint.sh").write_text("#!/bin/sh\n", encoding="utf-8")


def test_adopt_moves_files_and_clears_legacy(cli: CliRunner, config_dir: Path) -> None:
    from mad_cli.core.instance import discover_instances

    _write_legacy(config_dir, "prod")
    # Before: the sole instance is the legacy top-level layout.
    before = discover_instances()
    assert [(i.name, i.legacy) for i in before] == [("prod", True)]

    result = cli.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.output

    target = config_dir / "instances" / "prod"
    for name in ("compose.yml", ".env", "Dockerfile", "entrypoint.sh"):
        assert (target / name).is_file(), f"{name} was not moved"
        assert not (config_dir / name).exists(), f"{name} left behind"

    # After: the instance is discovered from instances/prod and is no longer legacy.
    after = discover_instances()
    assert [(i.name, i.legacy) for i in after] == [("prod", False)]


def test_adopt_warns_about_data_and_project_rename(cli: CliRunner, config_dir: Path) -> None:
    _write_legacy(config_dir, "prod")
    result = cli.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.output
    assert "MAD_DATA_PATH" in result.output
    assert "docker compose" in result.output


def test_adopt_without_legacy_reports_nothing(cli: CliRunner, config_dir: Path) -> None:
    result = cli.invoke(app, ["adopt"])
    assert result.exit_code == 0, result.output
    assert "Nothing to adopt" in result.output
