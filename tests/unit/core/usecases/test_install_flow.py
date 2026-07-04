"""Unit tests for the install use case (env assembly, file writing, optional start).

Drives the real engine over a scratch ``MAD_CLI_CONFIG_DIR``; only the container
runner (Docker) is mocked, as elsewhere in the suite.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mad_cli.core.envfile import EnvFile
from mad_cli.core.usecases import install as uc
from mad_cli.core.usecases.errors import ValidationError


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "config"
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(root))
    return root


def _params(tmp_path: Path, **overrides: object) -> uc.InstallParams:
    base: dict[str, object] = dict(
        name="web",
        port=9000,
        data_path=tmp_path / "data",
        timeout_s=900,
        github_token="ghp_secret",
        puid=1000,
        pgid=1000,
        git_name="Ada",
        git_email="ada@example.com",
        claude_token="claude-xyz",
        start=False,
    )
    base.update(overrides)
    return uc.InstallParams(**base)  # type: ignore[arg-type]


# ── build_env ─────────────────────────────────────────────────────────────────
def test_build_env_writes_base_keys_and_fans_git_identity(tmp_path: Path) -> None:
    env, extra = uc.build_env(_params(tmp_path))
    assert env.get("MAD_INSTANCE") == "web"
    assert env.get("MAD_HOST_PORT") == "9000"
    assert env.get("GITHUB_TOKEN") == env.get("GH_TOKEN") == "ghp_secret"
    assert env.get("GIT_COMMITTER_NAME") == "Ada"
    assert env.get("_CLAUDE_OAUTH_TOKEN") == "claude-xyz"
    assert extra == []


def test_build_env_retention_and_mcp_active_vs_commented(tmp_path: Path) -> None:
    active, _ = uc.build_env(_params(tmp_path, retention_days="30", mcp_allowed_hosts="a.com"))
    assert active.get("MAD_SESSIONS_RETENTION_DAYS") == "30"
    assert active.get("MAD_MCP_ALLOWED_HOSTS") == "a.com"

    inactive, _ = uc.build_env(_params(tmp_path))
    assert inactive.get("MAD_SESSIONS_RETENTION_DAYS") is None
    assert inactive.get("MAD_MCP_ALLOWED_HOSTS") is None
    rendered = inactive.render()
    assert "MAD_SESSIONS_RETENTION_DAYS" in rendered  # left as a commented reference
    assert "MAD_SSE_HEARTBEAT_S" in rendered


def test_build_env_overlays_extra_env(tmp_path: Path) -> None:
    env, extra = uc.build_env(_params(tmp_path, extra_env={"DEEPSEEK_API_KEY": "sk-d"}))
    assert env.get("DEEPSEEK_API_KEY") == "sk-d"
    assert extra == ["DEEPSEEK_API_KEY"]


def test_build_env_anthropic_only_when_present(tmp_path: Path) -> None:
    with_key, _ = uc.build_env(_params(tmp_path, anthropic_api_key="sk-ant"))
    assert with_key.get("ANTHROPIC_API_KEY") == "sk-ant"
    without, _ = uc.build_env(_params(tmp_path))
    assert without.get("ANTHROPIC_API_KEY") is None


# ── apply_extra_key ──────────────────────────────────────────────────────────
def test_apply_extra_key_builtin_custom_and_rejections() -> None:
    env = EnvFile.empty()
    assert uc.apply_extra_key(env, "github", "ghp_x") == ["GITHUB_TOKEN", "GH_TOKEN"]
    assert uc.apply_extra_key(env, "MY_VAR", "v") == ["MY_VAR"]
    assert env.get("GH_TOKEN") == "ghp_x"
    with pytest.raises(ValidationError):
        uc.apply_extra_key(env, "claude-oauth", "x")
    with pytest.raises(ValidationError, match="Unknown|unknown"):
        uc.apply_extra_key(env, "not-a-key", "x")


# ── validators ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("field", "value"),
    [("port", 70000), ("timeout_s", 0), ("name", "Bad Name")],
)
def test_install_validates_inputs(
    config_dir: Path, tmp_path: Path, field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        uc.install(_params(tmp_path, **{field: value}))


# ── install: files, dirs, credentials, optional start ────────────────────────
def test_install_writes_files_dirs_and_credentials(config_dir: Path, tmp_path: Path) -> None:
    result = uc.install(_params(tmp_path))
    cfg = result.config_dir
    for name in ("Dockerfile", "compose.yml", "entrypoint.sh", ".env"):
        assert (cfg / name).is_file(), name
    data = tmp_path / "data" / "web"
    for sub in ("workspaces", "sessions", "aws"):
        assert (data / sub).is_dir(), sub
    assert result.claude_credentials_path is not None
    assert result.claude_credentials_path.is_file()
    assert result.started is False and result.healthy is None


def test_install_without_claude_token_creates_empty_dir(config_dir: Path, tmp_path: Path) -> None:
    result = uc.install(_params(tmp_path, claude_token=""))
    assert result.claude_credentials_path is None
    assert result.claude_dir.is_dir()


def test_install_with_start_builds_and_waits(
    config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = MagicMock()
    runner.wait_healthy.return_value = True
    monkeypatch.setattr(uc, "ComposeRunner", MagicMock(return_value=runner))

    result = uc.install(_params(tmp_path, start=True))
    runner.up.assert_called_once_with(build=True)
    runner.wait_healthy.assert_called_once()
    assert result.started is True
    assert result.healthy is True
    assert result.url == "http://localhost:9000"
