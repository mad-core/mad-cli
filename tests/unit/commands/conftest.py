"""Shared fakes and fixtures for the command-surface tests.

Every test mocks ``mad_cli.core`` — the real stubs raise ``NotImplementedError``,
so any un-mocked call fails loudly (which is what we want). The fakes here stand
in for ``EnvFile`` and ``Instance`` where a behaving object is easier than a mock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give rich a wide, deterministic width so table cells are never cropped."""
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setenv("NO_COLOR", "1")


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


class FakeEnvFile:
    """Dict-backed stand-in for ``mad_cli.core.envfile.EnvFile``."""

    def __init__(self, data: dict[str, str] | None = None) -> None:
        self.data: dict[str, str] = dict(data or {})
        self.path: Path | None = None

    @classmethod
    def empty(cls) -> FakeEnvFile:
        return cls()

    @classmethod
    def load(cls, path: Path) -> FakeEnvFile:
        return cls()

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value

    def unset(self, key: str) -> None:
        self.data.pop(key, None)

    def keys(self) -> list[str]:
        return list(self.data)

    def save(self, path: Path | None = None) -> None:
        return None


@dataclass
class FakeInstance:
    """Behaving stand-in for ``mad_cli.core.instance.Instance``."""

    name: str = "default"
    host_port: int | None = 8080
    data_path: Path | None = Path("/data/default")
    config_dir: Path = Path("/cfg/default")
    compose_file: Path = Path("/cfg/default/compose.yml")
    env: FakeEnvFile = field(default_factory=FakeEnvFile)
    legacy: bool = False


@pytest.fixture
def make_env() -> Callable[..., FakeEnvFile]:
    def _make(data: dict[str, str] | None = None) -> FakeEnvFile:
        return FakeEnvFile(data)

    return _make


@pytest.fixture
def make_instance() -> Callable[..., FakeInstance]:
    def _make(**kwargs: object) -> FakeInstance:
        return FakeInstance(**kwargs)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def install_mocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    """Patch every core dependency of ``mad_cli.commands.install`` for the happy path."""
    from mad_cli.commands import install as mod
    from mad_cli.core.docker_check import DockerStatus
    from mad_cli.core.instance import InstanceNotFoundError

    ns = SimpleNamespace(mod=mod, tmp_path=tmp_path)

    ns.check_docker = MagicMock(return_value=DockerStatus(True, True, True, "27.0.0"))
    monkeypatch.setattr(mod, "check_docker", ns.check_docker)

    ns.install_docker_linux = MagicMock(return_value=True)
    monkeypatch.setattr(mod, "install_docker_linux", ns.install_docker_linux)

    def _no_instance(name: str) -> object:
        raise InstanceNotFoundError(name)

    ns.get_instance = MagicMock(side_effect=_no_instance)
    monkeypatch.setattr(mod, "get_instance", ns.get_instance)

    monkeypatch.setattr(mod, "EnvFile", FakeEnvFile)

    ns.instance_dir = MagicMock(side_effect=lambda name: tmp_path / "cfg" / name)
    monkeypatch.setattr(mod, "instance_dir", ns.instance_dir)

    ns.write_instance_files = MagicMock()
    monkeypatch.setattr(mod, "write_instance_files", ns.write_instance_files)

    ns.write_claude_credentials = MagicMock(
        side_effect=lambda claude_dir, token: Path(claude_dir) / ".credentials.json"
    )
    monkeypatch.setattr(mod, "write_claude_credentials", ns.write_claude_credentials)

    ns.mask = MagicMock(side_effect=lambda value: "MASKED")
    monkeypatch.setattr(mod, "mask", ns.mask)

    ns.runner = MagicMock()
    ns.runner.wait_healthy.return_value = True
    ns.ComposeRunner = MagicMock(return_value=ns.runner)
    monkeypatch.setattr(mod, "ComposeRunner", ns.ComposeRunner)

    return ns


@pytest.fixture
def lifecycle_mocks(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Patch ``ComposeRunner`` in the lifecycle module and hand back the shared runner."""
    from mad_cli.commands import lifecycle as mod

    ns = SimpleNamespace(mod=mod)
    ns.runner = MagicMock()
    ns.runner.wait_healthy.return_value = True
    ns.runner.ps.return_value = "mad-web  Up 3 minutes (healthy)"
    ns.ComposeRunner = MagicMock(return_value=ns.runner)
    monkeypatch.setattr(mod, "ComposeRunner", ns.ComposeRunner)
    return ns
