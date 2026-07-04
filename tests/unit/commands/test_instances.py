"""Tests for ``mad list`` and ``mad info``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.instance import InstanceNotFoundError


def test_list_empty_hints_install(cli: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    from mad_cli.commands import instances as mod

    monkeypatch.setattr(mod, "discover_instances", lambda: [])
    result = cli.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "mad install" in result.output


def test_list_renders_both_instances(
    cli: CliRunner, make_instance, make_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.commands import instances as mod

    web = make_instance(name="web", host_port=9000, data_path=Path("/data/web"))
    api = make_instance(name="api", host_port=9100, data_path=Path("/data/api"), legacy=True)
    monkeypatch.setattr(mod, "discover_instances", lambda: [web, api])
    # docker unavailable -> state is best-effort "unknown", must not crash the table
    monkeypatch.setattr(mod, "ComposeRunner", MagicMock(side_effect=RuntimeError("no docker")))

    result = cli.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "web" in result.output
    assert "api" in result.output
    assert "legacy" in result.output
    assert "unknown" in result.output


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
    monkeypatch.setattr(mod, "get_instance", lambda name: inst)
    monkeypatch.setattr(mod, "mask", lambda value: "sk-masked-xx")

    result = cli.invoke(app, ["info", "web"])
    assert result.exit_code == 0, result.output
    assert "GITHUB_TOKEN" in result.output
    assert "ghp_supersecretvalue" not in result.output
    assert "sk-masked-xx" in result.output
    # non-secret values are shown verbatim
    assert "Ada Lovelace" in result.output


def test_info_unknown_instance_errors(
    cli: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.commands import instances as mod

    def _raise(name: str):
        raise InstanceNotFoundError(name)

    monkeypatch.setattr(mod, "get_instance", _raise)
    result = cli.invoke(app, ["info", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output
