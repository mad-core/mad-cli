"""docker compose runner — the one module that shells out to Docker.

Ports the lifecycle semantics of the reference ``start.sh``. Every invocation is
scoped to the instance with ``-p mad-<name> -f <compose.yml> --env-file <.env>``
so instances never collide. ``dry_run`` records the argv on
:attr:`ComposeRunner.last_command` without executing anything, which is what the
tests assert against.
"""

from __future__ import annotations

import subprocess
import time

from mad_cli.core.instance import Instance


class ComposeError(Exception):
    """A docker compose invocation failed."""


class ComposeRunner:
    def __init__(self, instance: Instance, *, dry_run: bool = False) -> None:
        self.instance = instance
        self.dry_run = dry_run
        self.last_command: list[str] | None = None

    # ── argv construction ───────────────────────────────────────────────────
    def _base(self) -> list[str]:
        return [
            "docker",
            "compose",
            "-p",
            f"mad-{self.instance.name}",
            "-f",
            str(self.instance.compose_file),
            "--env-file",
            str(self.instance.env_file),
        ]

    def _run(
        self,
        args: list[str],
        *,
        capture: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str] | None:
        cmd = self._base() + args
        self.last_command = cmd
        if self.dry_run:
            return None
        try:
            completed = subprocess.run(cmd, capture_output=capture, text=True, check=False)
        except OSError as exc:
            raise ComposeError(f"failed to run {' '.join(cmd)}: {exc}") from exc
        if check and completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise ComposeError(
                f"`{' '.join(cmd)}` failed (exit {completed.returncode})"
                + (f": {stderr}" if stderr else "")
            )
        return completed

    # ── lifecycle ───────────────────────────────────────────────────────────
    def up(self, build: bool = True, detach: bool = True) -> None:
        args = ["up"]
        if detach:
            args.append("-d")
        if build:
            args.append("--build")
        self._run(args)

    def down(self) -> None:
        self._run(["down"])

    def restart(self) -> None:
        """Stop then start (with a rebuild), matching ``start.sh restart``."""
        self.down()
        self.up()

    def ps(self) -> str:
        completed = self._run(["ps"], capture=True)
        return "" if completed is None else (completed.stdout or "")

    def logs(self, follow: bool = True) -> None:
        args = ["logs"]
        if follow:
            args.append("-f")
        args.append("mad")
        # Interactive stream: no capture, and a Ctrl-C exit is not an error.
        self._run(args, check=False)

    def shell(self) -> None:
        # Interactive: attaches the caller's TTY to `bash` in the service.
        self._run(["exec", "mad", "bash"], check=False)

    def config_check(self) -> None:
        self._run(["config", "-q"])

    def build(self, no_cache: bool = False) -> None:
        args = ["build"]
        if no_cache:
            args.append("--no-cache")
        self._run(args)

    def exec(self, cmd: list[str], capture: bool = True) -> str:
        completed = self._run(["exec", "mad", *cmd], capture=capture)
        if completed is None:
            return ""
        return completed.stdout or "" if capture else ""

    # ── health ──────────────────────────────────────────────────────────────
    def wait_healthy(self, timeout_s: int = 180) -> bool:
        """Poll ``docker inspect`` until the container reports ``healthy``.

        Returns ``True`` as soon as the health status is ``healthy``; returns
        ``False`` if the timeout elapses first. A ``dry_run`` runner reports
        healthy immediately.
        """
        if self.dry_run:
            return True
        container = f"mad-{self.instance.name}"
        interval = 2.0
        deadline = time.monotonic() + timeout_s
        while True:
            if self._inspect_health(container) == "healthy":
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(interval)

    @staticmethod
    def _inspect_health(container: str) -> str | None:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip()
