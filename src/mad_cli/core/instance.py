"""Instance model and filesystem discovery. Contract stub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mad_cli.core.envfile import EnvFile


class InstanceNotFoundError(Exception):
    """Raised when a named instance does not exist under the config root."""


@dataclass
class Instance:
    name: str
    config_dir: Path
    env: EnvFile
    legacy: bool = False

    @property
    def host_port(self) -> int | None:
        raise NotImplementedError

    @property
    def data_path(self) -> Path | None:
        raise NotImplementedError

    @property
    def version_pin(self) -> str | None:
        raise NotImplementedError

    @property
    def compose_file(self) -> Path:
        raise NotImplementedError

    @property
    def env_file(self) -> Path:
        raise NotImplementedError


def discover_instances() -> list[Instance]:
    raise NotImplementedError


def get_instance(name: str) -> Instance:
    raise NotImplementedError


def default_instance() -> Instance | None:
    raise NotImplementedError
