"""Config-directory resolution. Contract stub — implemented on feat/scaffold-core."""

from __future__ import annotations

from pathlib import Path


def config_root() -> Path:
    """$MAD_CLI_CONFIG_DIR override or ~/.config/mad."""
    raise NotImplementedError


def instances_root() -> Path:
    raise NotImplementedError


def instance_dir(name: str) -> Path:
    raise NotImplementedError
