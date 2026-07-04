"""Tests for ``mad install`` — the install/reconfigure wizard."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.docker_check import DockerStatus


def _happy_args(tmp_path: Path) -> list[str]:
    return [
        "install",
        "--yes",
        "--name",
        "web",
        "--port",
        "9000",
        "--data-path",
        str(tmp_path / "data"),
        "--timeout",
        "900",
        "--github-token",
        "ghp_secrettoken",
        "--git-name",
        "Ada Lovelace",
        "--git-email",
        "ada@example.com",
        "--claude-token",
        "claude-oauth-xyz",
        "--edge-version",
        "1.2.3",
    ]


def test_install_happy_path_writes_files_and_starts(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    result = cli.invoke(app, _happy_args(install_mocks.tmp_path))
    assert result.exit_code == 0, result.output

    # instance files rendered with the right target, context and env
    install_mocks.write_instance_files.assert_called_once()
    target, ctx, env = install_mocks.write_instance_files.call_args.args
    assert target == install_mocks.tmp_path / "cfg" / "web"
    assert ctx.instance == "web"
    assert ctx.host_port == 9000
    assert ctx.timeout_s == 900
    assert ctx.edge_version == "1.2.3"

    assert env.data["MAD_INSTANCE"] == "web"
    assert env.data["MAD_HOST_PORT"] == "9000"
    assert env.data["MAD_VERSION"] == "1.2.3"
    assert env.data["MAD_DATA_PATH"] == str(install_mocks.tmp_path / "data")
    assert env.data["GITHUB_TOKEN"] == "ghp_secrettoken"
    assert env.data["GH_TOKEN"] == "ghp_secrettoken"
    assert env.data["GIT_AUTHOR_NAME"] == "Ada Lovelace"
    assert env.data["GIT_AUTHOR_EMAIL"] == "ada@example.com"
    assert env.data["GIT_COMMITTER_NAME"] == "Ada Lovelace"
    assert env.data["GIT_COMMITTER_EMAIL"] == "ada@example.com"
    assert env.data["MAD_AGENT_TIMEOUT_S"] == "900"
    assert env.data["_CLAUDE_OAUTH_TOKEN"] == "claude-oauth-xyz"

    # claude credentials written to <data>/<name>/claude with the token
    install_mocks.write_claude_credentials.assert_called_once()
    claude_dir, token = install_mocks.write_claude_credentials.call_args.args
    assert claude_dir == install_mocks.tmp_path / "data" / "web" / "claude"
    assert token == "claude-oauth-xyz"

    # container started + health awaited
    install_mocks.ComposeRunner.assert_called_once()
    install_mocks.runner.up.assert_called_once_with(build=True)
    install_mocks.runner.wait_healthy.assert_called_once()

    # secrets never leak; the URL is surfaced
    assert "ghp_secrettoken" not in result.output
    assert "http://localhost:9000" in result.output


def test_install_no_start_skips_container(cli: CliRunner, install_mocks: SimpleNamespace) -> None:
    args = _happy_args(install_mocks.tmp_path) + ["--no-start"]
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output

    install_mocks.write_instance_files.assert_called_once()
    install_mocks.ComposeRunner.assert_not_called()
    install_mocks.runner.up.assert_not_called()


def test_install_yes_without_github_token_fails(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    result = cli.invoke(app, ["install", "--yes"])
    assert result.exit_code != 0
    assert "--github-token" in result.output
    install_mocks.write_instance_files.assert_not_called()


def test_install_aborts_when_docker_missing(
    cli: CliRunner,
    install_mocks: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_mocks.check_docker.return_value = DockerStatus(False, False, False, None)
    # Decline any offer to install so the outcome is platform-independent.
    monkeypatch.setattr(install_mocks.mod, "confirm", lambda *a, **k: False)

    result = cli.invoke(app, ["install", "--yes", "--github-token", "ghp_x"])
    assert result.exit_code != 0
    assert "Docker" in result.output
    install_mocks.write_instance_files.assert_not_called()


def test_install_creates_sessions_data_dir(cli: CliRunner, install_mocks: SimpleNamespace) -> None:
    result = cli.invoke(app, _happy_args(install_mocks.tmp_path) + ["--no-start"])
    assert result.exit_code == 0, result.output
    assert (install_mocks.tmp_path / "data" / "web" / "sessions").is_dir()


def test_install_retention_days_flag_writes_env(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    args = _happy_args(install_mocks.tmp_path) + ["--no-start", "--retention-days", "30"]
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    assert env.data["MAD_SESSIONS_RETENTION_DAYS"] == "30"


def test_install_without_retention_leaves_it_inactive(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    result = cli.invoke(app, _happy_args(install_mocks.tmp_path) + ["--no-start"])
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    # Not written as an active assignment; only left as a commented reference.
    assert "MAD_SESSIONS_RETENTION_DAYS" not in env.data
    assert any("MAD_SESSIONS_RETENTION_DAYS" in c for c in env.comments)


def test_install_anthropic_api_key_flag_writes_env(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    args = _happy_args(install_mocks.tmp_path) + [
        "--no-start",
        "--anthropic-api-key",
        "sk-ant-secret",
    ]
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    assert env.data["ANTHROPIC_API_KEY"] == "sk-ant-secret"
    assert "sk-ant-secret" not in result.output  # masked in the summary


def test_install_set_key_builtin_fans_out_via_registry(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    args = _happy_args(install_mocks.tmp_path) + ["--no-start", "--set-key", "deepseek=sk-x"]
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    assert env.data["DEEPSEEK_API_KEY"] == "sk-x"


def test_install_set_key_custom_var_written_verbatim(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    args = _happy_args(install_mocks.tmp_path) + ["--no-start", "--set-key", "MI_VAR=v"]
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    assert env.data["MI_VAR"] == "v"


def test_install_set_key_claude_oauth_is_rejected(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    args = _happy_args(install_mocks.tmp_path) + ["--no-start", "--set-key", "claude-oauth=x"]
    result = cli.invoke(app, args)
    assert result.exit_code != 0
    assert "claude-oauth" in result.output
    assert "--claude-token" in result.output
    install_mocks.write_instance_files.assert_not_called()


def test_install_mcp_allowed_hosts_flag_writes_env(
    cli: CliRunner, install_mocks: SimpleNamespace
) -> None:
    args = _happy_args(install_mocks.tmp_path) + [
        "--no-start",
        "--mcp-allowed-hosts",
        "a.com,b.com",
    ]
    result = cli.invoke(app, args)
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    assert env.data["MAD_MCP_ALLOWED_HOSTS"] == "a.com,b.com"


def test_prompt_extra_keys_loop_adds_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    from mad_cli.commands import install as mod
    from mad_cli.core.envfile import EnvFile

    confirms = iter([True, True, False])  # configure? -> add first -> add another? -> stop
    asks = iter(["deepseek", "sk-d", "linear", "sk-l"])
    monkeypatch.setattr(mod, "confirm", lambda *a, **k: next(confirms))
    monkeypatch.setattr(mod, "ask", lambda *a, **k: next(asks))

    env = EnvFile.empty()
    applied: list[str] = []
    mod._prompt_extra_keys(env, applied)

    assert env.get("DEEPSEEK_API_KEY") == "sk-d"
    assert env.get("LINEAR_API_KEY") == "sk-l"
    assert applied == ["DEEPSEEK_API_KEY", "LINEAR_API_KEY"]


def test_prompt_extra_keys_loop_rejects_then_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    from mad_cli.commands import install as mod
    from mad_cli.core.envfile import EnvFile

    # claude-oauth is rejected in-loop (warn + re-prompt), then a custom var lands.
    confirms = iter([True, False])
    asks = iter(["claude-oauth", "x", "MYVAR", "v"])
    monkeypatch.setattr(mod, "confirm", lambda *a, **k: next(confirms))
    monkeypatch.setattr(mod, "ask", lambda *a, **k: next(asks))

    env = EnvFile.empty()
    applied: list[str] = []
    mod._prompt_extra_keys(env, applied)

    assert env.get("_CLAUDE_OAUTH_TOKEN") is None
    assert env.get("MYVAR") == "v"
    assert applied == ["MYVAR"]


def test_install_reconfigure_prefills_from_existing_env(
    cli: CliRunner,
    install_mocks: SimpleNamespace,
    make_env,
    make_instance,
) -> None:
    # An existing instance supplies defaults, so --yes without --github-token
    # succeeds by reusing the stored token.
    existing = make_instance(
        name="web",
        env=make_env(
            {
                "MAD_HOST_PORT": "7777",
                "GITHUB_TOKEN": "ghp_existing",
                "MAD_DATA_PATH": str(install_mocks.tmp_path / "data"),
            }
        ),
    )
    install_mocks.get_instance.side_effect = None
    install_mocks.get_instance.return_value = existing

    result = cli.invoke(app, ["install", "--yes", "--name", "web", "--no-start"])
    assert result.exit_code == 0, result.output

    _, _, env = install_mocks.write_instance_files.call_args.args
    assert env.data["MAD_HOST_PORT"] == "7777"
    assert env.data["GITHUB_TOKEN"] == "ghp_existing"
    assert "already exists" in result.output
