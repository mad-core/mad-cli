"""Credential / API-key use cases: set / list / remove.

A key is either a *builtin* from :data:`mad_cli.core.keyspec.BUILTIN_KEYS`
(fanned out to one or more env vars, ``claude-oauth`` also materialising the
container credentials file) or a raw *custom* ``[A-Z][A-Z0-9_]*`` variable.
Values are always masked on read — a full secret is never returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mad_cli.core.claude_creds import write_claude_credentials
from mad_cli.core.instance import Instance
from mad_cli.core.keyspec import BUILTIN_KEYS, KeySpec, is_secret_key, mask
from mad_cli.core.usecases.errors import PreconditionError, ValidationError

# A custom key is written verbatim; it must look like a shell env-var name.
CUSTOM_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]*")


def _unknown_key_error(key: str) -> ValidationError:
    return ValidationError(
        f"Unknown key {key!r}: use a builtin id ({', '.join(BUILTIN_KEYS)}) "
        "or an env-var name matching [A-Z][A-Z0-9_]*."
    )


def key_prompt(key: str) -> tuple[str, bool]:
    """Return ``(prompt_text, secret)`` for interactively collecting ``key``.

    Raises :class:`ValidationError` for an id that is neither a builtin nor a
    valid custom variable, so an adapter never prompts for a bad key.
    """
    spec = BUILTIN_KEYS.get(key)
    if spec is not None:
        return spec.prompt, spec.secret
    if CUSTOM_KEY_RE.fullmatch(key):
        return f"Value for {key}", True
    raise _unknown_key_error(key)


@dataclass(frozen=True)
class SetKeyResult:
    id: str
    env_vars: tuple[str, ...]
    builtin: bool
    credentials_path: Path | None  # set when the Claude credentials file was written


def _claude_creds_path(instance: Instance) -> Path | None:
    if instance.data_path is None:
        return None
    return instance.data_path / instance.name / "claude" / ".credentials.json"


def _set_builtin(instance: Instance, spec: KeySpec, value: str) -> SetKeyResult:
    for var in spec.env_vars:
        instance.env.set(var, value)
    instance.env.save()
    creds: Path | None = None
    if spec.writes_claude_credentials:
        if instance.data_path is None:
            raise PreconditionError(
                "cannot write Claude credentials: MAD_DATA_PATH is not set for this instance"
            )
        creds = write_claude_credentials(instance.data_path / instance.name / "claude", value)
    return SetKeyResult(id=spec.id, env_vars=spec.env_vars, builtin=True, credentials_path=creds)


def set_key(instance: Instance, key: str, value: str) -> SetKeyResult:
    """Store a builtin key (fanned out) or a custom variable.

    Raises :class:`ValidationError` for an unknown id and
    :class:`PreconditionError` when ``claude-oauth`` cannot write its credentials.
    """
    spec = BUILTIN_KEYS.get(key)
    if spec is not None:
        return _set_builtin(instance, spec, value)
    if CUSTOM_KEY_RE.fullmatch(key):
        instance.env.set(key, value)
        instance.env.save()
        return SetKeyResult(id=key, env_vars=(key,), builtin=False, credentials_path=None)
    raise _unknown_key_error(key)


@dataclass(frozen=True)
class BuiltinKeyStatus:
    id: str
    env_vars: tuple[str, ...]
    is_set: bool
    masked: str  # masked value or "-"


@dataclass(frozen=True)
class CustomSecret:
    key: str
    masked: str


@dataclass(frozen=True)
class KeysView:
    builtins: list[BuiltinKeyStatus]
    custom: list[CustomSecret]


def list_keys(instance: Instance) -> KeysView:
    """Return the builtin key statuses (masked) plus any custom secret vars."""
    env = instance.env
    spec_vars = {var for spec in BUILTIN_KEYS.values() for var in spec.env_vars}

    builtins: list[BuiltinKeyStatus] = []
    for spec in BUILTIN_KEYS.values():
        first = next((env.get(var) for var in spec.env_vars if env.get(var)), None)
        builtins.append(
            BuiltinKeyStatus(
                id=spec.id,
                env_vars=spec.env_vars,
                is_set=first is not None,
                masked=mask(first) if first else "-",
            )
        )

    custom = [
        CustomSecret(key=key, masked=mask(env.get(key) or "") if env.get(key) else "-")
        for key in env.keys()  # noqa: SIM118 — EnvFile.keys() is its contract API
        if key not in spec_vars and is_secret_key(key)
    ]
    return KeysView(builtins=builtins, custom=custom)


@dataclass(frozen=True)
class RemoveKeyResult:
    id: str
    env_vars: tuple[str, ...]
    builtin: bool
    existed: bool
    credentials_left: Path | None  # claude-oauth: the on-disk file we left in place


def remove_key(instance: Instance, key: str) -> RemoveKeyResult:
    """Remove a builtin key's env vars (or a custom variable).

    ``existed`` is False when nothing was set (a no-op the adapter reports). The
    ``claude-oauth`` credentials file is intentionally left on disk.
    """
    spec = BUILTIN_KEYS.get(key)
    if spec is not None:
        present = [var for var in spec.env_vars if instance.env.get(var) is not None]
        if not present:
            return RemoveKeyResult(spec.id, spec.env_vars, True, False, None)
        for var in spec.env_vars:
            instance.env.unset(var)
        instance.env.save()
        left: Path | None = None
        if spec.writes_claude_credentials:
            creds = _claude_creds_path(instance)
            if creds is not None and creds.exists():
                left = creds
        return RemoveKeyResult(spec.id, spec.env_vars, True, True, left)
    if CUSTOM_KEY_RE.fullmatch(key):
        if instance.env.get(key) is None:
            return RemoveKeyResult(key, (key,), False, False, None)
        instance.env.unset(key)
        instance.env.save()
        return RemoveKeyResult(key, (key,), False, True, None)
    raise _unknown_key_error(key)
