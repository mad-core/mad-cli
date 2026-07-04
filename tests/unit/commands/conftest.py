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
        self.comments: list[str] = []
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

    def add_comment(self, text: str) -> None:
        self.comments.append(text)

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

    @property
    def env_file(self) -> Path:
        return self.config_dir / ".env"

    @property
    def version_pin(self) -> str | None:
        """Pinned ``MAD_VERSION`` ('' or unset -> ``None``), matching the real Instance."""
        return self.env.get("MAD_VERSION") or None


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
    """Patch the install command adapter and its use-case dependencies.

    The orchestration moved into ``core.usecases.install`` (file writing) and
    ``core.usecases.lifecycle`` (the start), so those internals are patched there;
    the Docker preflight, reconfigure prefill and masked summary stay in the
    command module and are patched there.
    """
    from mad_cli.commands import install as mod
    from mad_cli.core.docker_check import DockerStatus
    from mad_cli.core.instance import InstanceNotFoundError
    from mad_cli.core.usecases import install as uc_install
    from mad_cli.core.usecases import lifecycle as uc_lifecycle

    ns = SimpleNamespace(mod=mod, tmp_path=tmp_path)

    ns.check_docker = MagicMock(return_value=DockerStatus(True, True, True, "27.0.0"))
    monkeypatch.setattr(mod, "check_docker", ns.check_docker)

    ns.install_docker_linux = MagicMock(return_value=True)
    monkeypatch.setattr(mod, "install_docker_linux", ns.install_docker_linux)

    def _no_instance(name: str) -> object:
        raise InstanceNotFoundError(name)

    ns.get_instance = MagicMock(side_effect=_no_instance)
    monkeypatch.setattr(mod, "get_instance", ns.get_instance)

    # EnvFile is used both for the command's scratch extra-keys overlay and by the
    # use case to build the canonical .env.
    monkeypatch.setattr(mod, "EnvFile", FakeEnvFile)
    monkeypatch.setattr(uc_install, "EnvFile", FakeEnvFile)

    ns.instance_dir = MagicMock(side_effect=lambda name: tmp_path / "cfg" / name)
    monkeypatch.setattr(uc_install, "instance_dir", ns.instance_dir)

    ns.write_instance_files = MagicMock()
    monkeypatch.setattr(uc_install, "write_instance_files", ns.write_instance_files)

    ns.write_claude_credentials = MagicMock(
        side_effect=lambda claude_dir, token: Path(claude_dir) / ".credentials.json"
    )
    monkeypatch.setattr(uc_install, "write_claude_credentials", ns.write_claude_credentials)

    ns.mask = MagicMock(side_effect=lambda value: "MASKED")
    monkeypatch.setattr(mod, "mask", ns.mask)

    ns.runner = MagicMock()
    ns.runner.wait_healthy.return_value = True
    ns.ComposeRunner = MagicMock(return_value=ns.runner)
    monkeypatch.setattr(uc_lifecycle, "ComposeRunner", ns.ComposeRunner)

    return ns


@pytest.fixture
def cli_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point ``MAD_CLI_CONFIG_DIR`` at a scratch dir so the real core reads/writes there."""
    root = tmp_path / "config"
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(root))
    return root


@pytest.fixture
def make_real_instance(cli_config_dir: Path, tmp_path: Path) -> Callable[..., Path]:
    """Create a real on-disk instance the unmocked core can discover.

    Writes ``instances/<name>/.env`` under the scratch ``MAD_CLI_CONFIG_DIR`` and
    returns that instance's config directory. ``env`` overrides/extends the base
    keys; ``data_path`` defaults to ``tmp_path/data`` so credential files land in
    a writable place.
    """
    from mad_cli.core.paths import instances_root

    def _make(
        name: str = "default",
        env: dict[str, str] | None = None,
        data_path: Path | None = None,
    ) -> Path:
        data = data_path if data_path is not None else tmp_path / "data"
        values: dict[str, str] = {
            "MAD_INSTANCE": name,
            "MAD_HOST_PORT": "8080",
            "MAD_DATA_PATH": str(data),
        }
        if env:
            values.update(env)
        inst_dir = instances_root() / name
        inst_dir.mkdir(parents=True, exist_ok=True)
        body = "".join(f"{key}={value}\n" for key, value in values.items())
        (inst_dir / ".env").write_text(body, encoding="utf-8")
        return inst_dir

    return _make


@pytest.fixture
def lifecycle_mocks(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Patch the lifecycle runner and expose the resolution module.

    ``ComposeRunner`` is patched in both the use case (start/stop/restart/status)
    and the command adapter (the interactive logs/shell). ``ns.mod`` is the
    resolution module (``core.usecases.instances``) where ``default_instance`` /
    ``get_instance`` / ``discover_instances`` live, so tests patch them there.
    """
    from mad_cli.commands import lifecycle as cmd_mod
    from mad_cli.core.usecases import instances as resolve_mod
    from mad_cli.core.usecases import lifecycle as uc_lifecycle

    ns = SimpleNamespace(mod=resolve_mod)
    ns.runner = MagicMock()
    ns.runner.wait_healthy.return_value = True
    ns.runner.ps.return_value = "mad-web  Up 3 minutes (healthy)"
    ns.ComposeRunner = MagicMock(return_value=ns.runner)
    monkeypatch.setattr(uc_lifecycle, "ComposeRunner", ns.ComposeRunner)
    monkeypatch.setattr(cmd_mod, "ComposeRunner", ns.ComposeRunner)
    return ns
