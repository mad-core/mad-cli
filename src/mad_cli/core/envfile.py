""".env parser/writer that preserves comments and ordering. Contract stub."""

from __future__ import annotations

from pathlib import Path


class EnvFile:
    path: Path | None

    @classmethod
    def load(cls, path: Path) -> "EnvFile":
        raise NotImplementedError

    @classmethod
    def empty(cls) -> "EnvFile":
        raise NotImplementedError

    def get(self, key: str) -> str | None:
        raise NotImplementedError

    def set(self, key: str, value: str) -> None:
        raise NotImplementedError

    def unset(self, key: str) -> None:
        raise NotImplementedError

    def keys(self) -> list[str]:
        raise NotImplementedError

    def save(self, path: Path | None = None) -> None:
        raise NotImplementedError
