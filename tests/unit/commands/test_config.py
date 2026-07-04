"""Tests for ``mad config get|set|unset`` against the real core."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.envfile import EnvFile


def _env(config_dir: Path) -> EnvFile:
    return EnvFile.load(config_dir / ".env")


def test_get_all_masks_secrets(cli: CliRunner, make_real_instance) -> None:
    make_real_instance(env={"GITHUB_TOKEN": "ghp_dontleakme", "GIT_AUTHOR_NAME": "Ada"})
    result = cli.invoke(app, ["config", "get"])
    assert result.exit_code == 0, result.output
    assert "GITHUB_TOKEN" in result.output
    assert "ghp_dontleakme" not in result.output
    # non-secret values are shown verbatim
    assert "Ada" in result.output


def test_get_single_secret_masked_then_revealed(cli: CliRunner, make_real_instance) -> None:
    make_real_instance(env={"GITHUB_TOKEN": "ghp_dontleakme"})

    masked = cli.invoke(app, ["config", "get", "GITHUB_TOKEN"])
    assert masked.exit_code == 0, masked.output
    assert "ghp_dontleakme" not in masked.output

    revealed = cli.invoke(app, ["config", "get", "GITHUB_TOKEN", "--reveal"])
    assert revealed.exit_code == 0, revealed.output
    assert "ghp_dontleakme" in revealed.output


def test_get_missing_key_errors(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    result = cli.invoke(app, ["config", "get", "NOPE"])
    assert result.exit_code != 0
    assert "not set" in result.output


def test_set_plain_value(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance()
    result = cli.invoke(app, ["config", "set", "GIT_AUTHOR_NAME", "Ada Lovelace"])
    assert result.exit_code == 0, result.output
    assert _env(config_dir).get("GIT_AUTHOR_NAME") == "Ada Lovelace"


def test_set_validates_port_range(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance()
    result = cli.invoke(app, ["config", "set", "MAD_HOST_PORT", "70000"])
    assert result.exit_code != 0
    assert "between 1 and 65535" in result.output
    # the invalid value must not be persisted (still the fixture default)
    assert _env(config_dir).get("MAD_HOST_PORT") == "8080"


def test_set_validates_timeout_positive(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    result = cli.invoke(app, ["config", "set", "MAD_AGENT_TIMEOUT_S", "0"])
    assert result.exit_code != 0
    assert "positive" in result.output


def test_set_compose_key_warns_but_writes(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance()
    result = cli.invoke(app, ["config", "set", "MAD_HOST_PORT", "9090"])
    assert result.exit_code == 0, result.output
    assert _env(config_dir).get("MAD_HOST_PORT") == "9090"
    assert "compose.yml" in result.output
    assert "mad restart default" in result.output


def test_unset_removes_key(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance(env={"GITHUB_TOKEN": "ghp_x"})
    result = cli.invoke(app, ["config", "unset", "GITHUB_TOKEN"])
    assert result.exit_code == 0, result.output
    assert _env(config_dir).get("GITHUB_TOKEN") is None


def test_unset_missing_key_is_noop_warning(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    result = cli.invoke(app, ["config", "unset", "NOPE"])
    assert result.exit_code == 0, result.output
    assert "nothing to remove" in result.output


def test_unknown_instance_errors(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    result = cli.invoke(app, ["config", "get", "--instance", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_multiple_instances_require_naming(cli: CliRunner, make_real_instance) -> None:
    make_real_instance(name="web")
    make_real_instance(name="api")
    result = cli.invoke(app, ["config", "get"])
    assert result.exit_code != 0
    assert "web" in result.output
    assert "api" in result.output
