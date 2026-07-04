"""Generic credential/API-key registry. Contract stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeySpec:
    id: str
    env_vars: tuple[str, ...]
    prompt: str
    secret: bool = True
    help_url: str | None = None
    writes_claude_credentials: bool = False


BUILTIN_KEYS: dict[str, KeySpec] = {}


def mask(value: str) -> str:
    raise NotImplementedError
