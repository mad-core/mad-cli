"""Tests for ``mad keys set|list|remove`` against the real core.

These drive the unmocked engine: ``MAD_CLI_CONFIG_DIR`` points at a scratch dir
(see ``make_real_instance``), so assertions read the actual ``.env`` and the
Claude credentials file written to disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.envfile import EnvFile


def _env(config_dir: Path) -> EnvFile:
    return EnvFile.load(config_dir / ".env")


def test_set_builtin_fans_out_to_all_env_vars(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance()
    result = cli.invoke(app, ["keys", "set", "github", "ghp_supersecretvalue"])
    assert result.exit_code == 0, result.output

    env = _env(config_dir)
    assert env.get("GITHUB_TOKEN") == "ghp_supersecretvalue"
    assert env.get("GH_TOKEN") == "ghp_supersecretvalue"
    # the plaintext secret is never echoed back
    assert "ghp_supersecretvalue" not in result.output
    assert "mad restart default" in result.output


def test_set_claude_oauth_writes_credentials_0600(
    cli: CliRunner, make_real_instance, tmp_path: Path
) -> None:
    data_path = tmp_path / "data"
    config_dir = make_real_instance(name="web", data_path=data_path)

    result = cli.invoke(app, ["keys", "set", "claude-oauth", "sk-oauth-token-abc", "-i", "web"])
    assert result.exit_code == 0, result.output

    assert _env(config_dir).get("_CLAUDE_OAUTH_TOKEN") == "sk-oauth-token-abc"

    creds = data_path / "web" / "claude" / ".credentials.json"
    assert creds.is_file()
    assert oct(creds.stat().st_mode)[-3:] == "600"
    payload = json.loads(creds.read_text())
    assert payload["claudeAiOauth"]["accessToken"] == "sk-oauth-token-abc"


def test_set_custom_variable_written_verbatim(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance()
    result = cli.invoke(app, ["keys", "set", "MY_CUSTOM_TOKEN", "shhh-value"])
    assert result.exit_code == 0, result.output
    assert _env(config_dir).get("MY_CUSTOM_TOKEN") == "shhh-value"


def test_set_prompts_when_value_omitted(
    cli: CliRunner, make_real_instance, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = make_real_instance()
    from mad_cli.commands import keys as mod

    monkeypatch.setattr(mod, "ask", lambda prompt, secret=False: "prompted-secret")
    result = cli.invoke(app, ["keys", "set", "linear"])
    assert result.exit_code == 0, result.output
    assert _env(config_dir).get("LINEAR_API_KEY") == "prompted-secret"


def test_set_unknown_key_errors(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    # lowercase is neither a builtin id nor a valid custom env-var name
    result = cli.invoke(app, ["keys", "set", "not-a-key", "x"])
    assert result.exit_code != 0
    assert "Unknown key" in result.output


def test_list_masks_secret_values(cli: CliRunner, make_real_instance) -> None:
    make_real_instance(
        env={
            "GITHUB_TOKEN": "ghp_dontleakthisvalue",
            "GH_TOKEN": "ghp_dontleakthisvalue",
            "EXTRA_API_KEY": "custom_dontleak_secret",
            "GIT_AUTHOR_NAME": "Ada Lovelace",
        }
    )
    result = cli.invoke(app, ["keys", "list"])
    assert result.exit_code == 0, result.output
    # builtin listed and shown as set, custom secret surfaced, plaintext never shown
    assert "github" in result.output
    assert "EXTRA_API_KEY" in result.output
    assert "ghp_dontleakthisvalue" not in result.output
    assert "custom_dontleak_secret" not in result.output
    # unset builtins are reported too
    assert "anthropic" in result.output


def test_remove_builtin_clears_all_env_vars(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance(env={"GITHUB_TOKEN": "ghp_x", "GH_TOKEN": "ghp_x"})
    result = cli.invoke(app, ["keys", "remove", "github"])
    assert result.exit_code == 0, result.output
    env = _env(config_dir)
    assert env.get("GITHUB_TOKEN") is None
    assert env.get("GH_TOKEN") is None


def test_remove_claude_oauth_keeps_credentials_file(
    cli: CliRunner, make_real_instance, tmp_path: Path
) -> None:
    data_path = tmp_path / "data"
    make_real_instance(env={"_CLAUDE_OAUTH_TOKEN": "sk-tok"}, data_path=data_path)
    creds = data_path / "default" / "claude" / ".credentials.json"
    creds.parent.mkdir(parents=True, exist_ok=True)
    creds.write_text("{}", encoding="utf-8")

    result = cli.invoke(app, ["keys", "remove", "claude-oauth"])
    assert result.exit_code == 0, result.output
    # env var gone, on-disk credentials untouched, and the user is told where it is
    assert creds.is_file()
    assert "left in place on disk" in result.output
    assert str(creds) in result.output


def test_remove_unset_key_is_a_noop_warning(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    result = cli.invoke(app, ["keys", "remove", "deepseek"])
    assert result.exit_code == 0, result.output
    assert "nothing to remove" in result.output


def test_unknown_instance_errors(cli: CliRunner, make_real_instance) -> None:
    make_real_instance()
    result = cli.invoke(app, ["keys", "list", "--instance", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_no_instances_hints_install(cli: CliRunner, cli_config_dir: Path) -> None:
    # cli_config_dir points at an empty scratch root: no instances configured
    result = cli.invoke(app, ["keys", "list"])
    assert result.exit_code != 0
    assert "mad install" in result.output
