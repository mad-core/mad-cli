"""Config-directory resolution for mad-cli.

All paths derive from :func:`config_root`, which honours the ``MAD_CLI_CONFIG_DIR``
environment override and otherwise falls back to ``~/.config/mad``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def config_root() -> Path:
    """Return the mad-cli config root.

    ``$MAD_CLI_CONFIG_DIR`` overrides the default ``~/.config/mad``.
    """
    override = os.environ.get("MAD_CLI_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "mad"


def instances_root() -> Path:
    """Return the directory that holds one sub-directory per instance."""
    return config_root() / "instances"


def instance_dir(name: str) -> Path:
    """Return the config directory for ``name``.

    The name must match ``[a-z0-9][a-z0-9-]*`` so it is safe to use as a
    directory name, a Docker Compose project suffix and a container name.
    """
    if not _NAME_RE.match(name):
        raise ValueError(f"invalid instance name {name!r}: must match [a-z0-9][a-z0-9-]*")
    return instances_root() / name
