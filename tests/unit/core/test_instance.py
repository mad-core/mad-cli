"""Tests for mad_cli.core.instance."""

from __future__ import annotations

from pathlib import Path

import pytest

from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import (
    Instance,
    InstanceNotFoundError,
    default_instance,
    discover_instances,
    get_instance,
)


def _write_instance(root: Path, name: str, **env: str) -> Path:
    d = root / "instances" / name
    d.mkdir(parents=True)
    lines = [f"{k}={v}" for k, v in env.items()]
    (d / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def _write_legacy(root: Path, **env: str) -> None:
    lines = [f"{k}={v}" for k, v in env.items()]
    (root / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "compose.yml").write_text("services: {}\n", encoding="utf-8")


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_discovers_multiple_sorted(config_dir: Path) -> None:
    _write_instance(config_dir, "beta", MAD_HOST_PORT="8081")
    _write_instance(config_dir, "alpha", MAD_HOST_PORT="8080")
    instances = discover_instances()
    assert [i.name for i in instances] == ["alpha", "beta"]
    assert all(i.legacy is False for i in instances)


def test_dir_without_env_is_ignored(config_dir: Path) -> None:
    _write_instance(config_dir, "alpha", MAD_HOST_PORT="8080")
    (config_dir / "instances" / "empty").mkdir(parents=True)
    assert [i.name for i in discover_instances()] == ["alpha"]


def test_legacy_top_level_detected(config_dir: Path) -> None:
    _write_legacy(config_dir, MAD_INSTANCE="prod", MAD_HOST_PORT="8080")
    instances = discover_instances()
    assert len(instances) == 1
    legacy = instances[0]
    assert legacy.name == "prod"
    assert legacy.legacy is True
    assert legacy.config_dir == config_dir


def test_legacy_defaults_name_when_unset(config_dir: Path) -> None:
    _write_legacy(config_dir, MAD_HOST_PORT="8080")
    assert discover_instances()[0].name == "default"


def test_get_instance_found(config_dir: Path) -> None:
    _write_instance(config_dir, "alpha", MAD_HOST_PORT="8080")
    assert get_instance("alpha").name == "alpha"


def test_get_instance_missing_raises(config_dir: Path) -> None:
    _write_instance(config_dir, "alpha", MAD_HOST_PORT="8080")
    with pytest.raises(InstanceNotFoundError):
        get_instance("nope")


def test_default_instance_zero(config_dir: Path) -> None:
    assert default_instance() is None


def test_default_instance_one(config_dir: Path) -> None:
    _write_instance(config_dir, "solo", MAD_HOST_PORT="8080")
    solo = default_instance()
    assert solo is not None
    assert solo.name == "solo"


def test_default_instance_two(config_dir: Path) -> None:
    _write_instance(config_dir, "alpha", MAD_HOST_PORT="8080")
    _write_instance(config_dir, "beta", MAD_HOST_PORT="8081")
    assert default_instance() is None


def test_instance_properties() -> None:
    env = EnvFile.empty()
    env.set("MAD_HOST_PORT", "8080")
    env.set("MAD_DATA_PATH", "/home/mad-data")
    env.set("MAD_VERSION", "1.2.3")
    inst = Instance(name="x", config_dir=Path("/cfg"), env=env)
    assert inst.host_port == 8080
    assert inst.data_path == Path("/home/mad-data")
    assert inst.version_pin == "1.2.3"
    assert inst.compose_file == Path("/cfg/compose.yml")
    assert inst.env_file == Path("/cfg/.env")


def test_instance_properties_absent_and_blank() -> None:
    env = EnvFile.empty()
    env.set("MAD_VERSION", "")
    inst = Instance(name="x", config_dir=Path("/cfg"), env=env)
    assert inst.host_port is None
    assert inst.data_path is None
    assert inst.version_pin is None


def test_instance_host_port_non_numeric() -> None:
    env = EnvFile.empty()
    env.set("MAD_HOST_PORT", "not-a-number")
    inst = Instance(name="x", config_dir=Path("/cfg"), env=env)
    assert inst.host_port is None
