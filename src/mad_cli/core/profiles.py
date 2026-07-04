"""Named environment profiles — reusable sets of ``.env`` values.

A *profile* is a named, reusable set of environment variables an operator can
stamp onto instances. It carries **credentials and tuning**, never an instance's
identity: the keys that name one specific instance (its port, data path, name,
uid/gid and version pin — :data:`IDENTITY_KEYS`) are deliberately excluded, so a
profile can be applied across many instances without collision.

Profiles are stored one file per profile at ``config_root()/profiles/<name>.env``
in the same :class:`~mad_cli.core.envfile.EnvFile` format as an instance's
``.env``, ``chmod 600`` because they may hold secrets. The name follows the same
rule as an instance name (``[a-z0-9][a-z0-9-]*``) so it is safe as a filename.
"""

from __future__ import annotations

import re
from pathlib import Path

from mad_cli.core.envfile import EnvFile
from mad_cli.core.paths import config_root

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Instance-identity keys a profile must never carry: each names one specific
# instance, not the reusable credentials/tuning a profile is for. Excluded when
# seeding a profile from an instance (`mad profiles create --from-instance`).
IDENTITY_KEYS: tuple[str, ...] = (
    "MAD_INSTANCE",
    "MAD_HOST_PORT",
    "PUID",
    "PGID",
    "MAD_DATA_PATH",
    "MAD_VERSION",
)


class ProfileNotFoundError(Exception):
    """Raised when a named profile does not exist under the config root."""


def profiles_root() -> Path:
    """Return the directory that holds one ``<name>.env`` file per profile."""
    return config_root() / "profiles"


def _validate_name(name: str) -> str:
    """Return ``name`` if it is a valid profile name, else raise ``ValueError``."""
    if not _NAME_RE.match(name):
        raise ValueError(f"invalid profile name {name!r}: must match [a-z0-9][a-z0-9-]*")
    return name


def profile_path(name: str) -> Path:
    """Return the storage path for profile ``name`` (validates the name)."""
    return profiles_root() / f"{_validate_name(name)}.env"


def list_profiles() -> list[str]:
    """Return every stored profile name, sorted (empty when none exist)."""
    root = profiles_root()
    if not root.is_dir():
        return []
    return sorted(p.stem for p in root.iterdir() if p.is_file() and p.suffix == ".env")


def load_profile(name: str) -> EnvFile:
    """Load profile ``name`` or raise :class:`ProfileNotFoundError`."""
    path = profile_path(name)
    if not path.is_file():
        raise ProfileNotFoundError(name)
    return EnvFile.load(path)


def save_profile(name: str, env: EnvFile) -> Path:
    """Write ``env`` to profile ``name`` (``chmod 600``); return its path.

    The ``profiles/`` directory is created if needed. The file may hold secrets,
    so it is written with owner-only permissions.
    """
    path = profile_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    env.save(path)
    path.chmod(0o600)
    return path


def delete_profile(name: str) -> None:
    """Delete profile ``name`` or raise :class:`ProfileNotFoundError`."""
    path = profile_path(name)
    if not path.is_file():
        raise ProfileNotFoundError(name)
    path.unlink()
