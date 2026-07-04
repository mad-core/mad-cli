"""Instance model and filesystem discovery.

An *instance* is one mad-edge container plus its config directory
(``compose.yml`` / ``.env`` / ``Dockerfile`` / ``entrypoint.sh``). The modern
layout stores one instance per directory under ``config_root()/instances/``;
the legacy single-instance layout kept those files directly at ``config_root()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mad_cli.core import paths
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
        """Host port from ``MAD_HOST_PORT`` (``None`` if unset/non-numeric)."""
        raw = self.env.get("MAD_HOST_PORT")
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    @property
    def data_path(self) -> Path | None:
        """Host data root from ``MAD_DATA_PATH`` (``None`` if unset)."""
        raw = self.env.get("MAD_DATA_PATH")
        if not raw:
            return None
        return Path(raw)

    @property
    def version_pin(self) -> str | None:
        """Pinned mad-edge version from ``MAD_VERSION`` ('' -> ``None``)."""
        raw = self.env.get("MAD_VERSION")
        if not raw:
            return None
        return raw

    @property
    def compose_file(self) -> Path:
        return self.config_dir / "compose.yml"

    @property
    def env_file(self) -> Path:
        return self.config_dir / ".env"


def _load(config_dir: Path, name: str, *, legacy: bool) -> Instance:
    env = EnvFile.load(config_dir / ".env")
    return Instance(name=name, config_dir=config_dir, env=env, legacy=legacy)


def discover_instances() -> list[Instance]:
    """Return every configured instance.

    Modern instances (``instances/<name>/.env``) come first, sorted by name; a
    directory without a ``.env`` is ignored. A legacy top-level layout
    (``config_root()/compose.yml`` + ``.env``) is appended with ``legacy=True``,
    its name taken from ``MAD_INSTANCE`` (default ``"default"``).
    """
    found: list[Instance] = []

    root = paths.instances_root()
    if root.is_dir():
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            if child.is_dir() and (child / ".env").is_file():
                found.append(_load(child, child.name, legacy=False))

    config_root = paths.config_root()
    if (config_root / ".env").is_file() and (config_root / "compose.yml").is_file():
        legacy = _load(config_root, "default", legacy=True)
        name = legacy.env.get("MAD_INSTANCE")
        if name:
            legacy.name = name
        found.append(legacy)

    return found


def get_instance(name: str) -> Instance:
    """Return the instance called ``name`` or raise :class:`InstanceNotFoundError`."""
    for instance in discover_instances():
        if instance.name == name:
            return instance
    raise InstanceNotFoundError(name)


def default_instance() -> Instance | None:
    """Return the sole instance when exactly one exists, else ``None``."""
    instances = discover_instances()
    if len(instances) == 1:
        return instances[0]
    return None
