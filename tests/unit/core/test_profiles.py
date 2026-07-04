"""Tests for mad_cli.core.profiles against the real filesystem."""

from __future__ import annotations

from pathlib import Path

import pytest

from mad_cli.core import profiles
from mad_cli.core.envfile import EnvFile


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _env(**values: str) -> EnvFile:
    env = EnvFile.empty()
    for key, value in values.items():
        env.set(key, value)
    return env


def test_profiles_root_under_config_root(config_dir: Path) -> None:
    assert profiles.profiles_root() == config_dir / "profiles"


def test_save_then_load_round_trips_values(config_dir: Path) -> None:
    profiles.save_profile("prod", _env(GITHUB_TOKEN="ghp_x", MAD_AGENT_TIMEOUT_S="900"))
    loaded = profiles.load_profile("prod")
    assert loaded.get("GITHUB_TOKEN") == "ghp_x"
    assert loaded.get("MAD_AGENT_TIMEOUT_S") == "900"


def test_save_returns_path_and_creates_directory(config_dir: Path) -> None:
    path = profiles.save_profile("prod", _env(A="1"))
    assert path == config_dir / "profiles" / "prod.env"
    assert path.is_file()


def test_save_sets_owner_only_permissions(config_dir: Path) -> None:
    path = profiles.save_profile("secretful", _env(ANTHROPIC_API_KEY="sk-ant-x"))
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_list_profiles_sorted(config_dir: Path) -> None:
    profiles.save_profile("beta", _env(A="1"))
    profiles.save_profile("alpha", _env(A="1"))
    assert profiles.list_profiles() == ["alpha", "beta"]


def test_list_profiles_empty_when_none(config_dir: Path) -> None:
    assert profiles.list_profiles() == []


def test_list_ignores_non_env_files(config_dir: Path) -> None:
    profiles.save_profile("real", _env(A="1"))
    (config_dir / "profiles" / "notes.txt").write_text("ignore me\n", encoding="utf-8")
    assert profiles.list_profiles() == ["real"]


def test_load_missing_raises(config_dir: Path) -> None:
    with pytest.raises(profiles.ProfileNotFoundError):
        profiles.load_profile("ghost")


def test_delete_removes_profile(config_dir: Path) -> None:
    profiles.save_profile("temp", _env(A="1"))
    profiles.delete_profile("temp")
    assert profiles.list_profiles() == []


def test_delete_missing_raises(config_dir: Path) -> None:
    with pytest.raises(profiles.ProfileNotFoundError):
        profiles.delete_profile("ghost")


@pytest.mark.parametrize("name", ["", "-bad", "Bad", "has space", "under_score", "a/b"])
def test_profile_path_rejects_bad_names(name: str) -> None:
    with pytest.raises(ValueError, match="invalid profile name"):
        profiles.profile_path(name)


def test_save_rejects_bad_name(config_dir: Path) -> None:
    with pytest.raises(ValueError, match="invalid profile name"):
        profiles.save_profile("Bad Name", _env(A="1"))


def test_identity_keys_are_the_instance_identity_set() -> None:
    assert profiles.IDENTITY_KEYS == (
        "MAD_INSTANCE",
        "MAD_HOST_PORT",
        "PUID",
        "PGID",
        "MAD_DATA_PATH",
        "MAD_VERSION",
    )
