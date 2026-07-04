"""docker compose runner (shell-out, one module owns subprocess). Contract stub."""

from __future__ import annotations

from mad_cli.core.instance import Instance


class ComposeError(Exception):
    """A docker compose invocation failed."""


class ComposeRunner:
    def __init__(self, instance: Instance, *, dry_run: bool = False) -> None:
        self.instance = instance
        self.dry_run = dry_run

    def up(self, build: bool = True, detach: bool = True) -> None:
        raise NotImplementedError

    def down(self) -> None:
        raise NotImplementedError

    def restart(self) -> None:
        raise NotImplementedError

    def ps(self) -> str:
        raise NotImplementedError

    def logs(self, follow: bool = True) -> None:
        raise NotImplementedError

    def shell(self) -> None:
        raise NotImplementedError

    def config_check(self) -> None:
        raise NotImplementedError

    def build(self, no_cache: bool = False) -> None:
        raise NotImplementedError

    def exec(self, cmd: list[str], capture: bool = True) -> str:
        raise NotImplementedError

    def wait_healthy(self, timeout_s: int = 180) -> bool:
        raise NotImplementedError
