"""Container lifecycle use cases: start / stop / restart / status.

Each operates on an already-resolved :class:`Instance` (the adapter resolves via
:func:`mad_cli.core.usecases.instances.resolve_instance`, mapping resolution
failures to its own idiom). The interactive streams (``logs`` / ``shell``) stay in
the CLI adapter — they attach the caller's TTY and have no HTTP equivalent.
Everything here is synchronous; the build + health wait blocks in the MVP.
"""

from __future__ import annotations

from dataclasses import dataclass

from mad_cli.core.compose import ComposeRunner
from mad_cli.core.instance import Instance


def instance_url(instance: Instance) -> str | None:
    port = instance.host_port
    return f"http://localhost:{port}" if port is not None else None


@dataclass(frozen=True)
class StartResult:
    instance: Instance
    healthy: bool
    url: str | None


def start(instance: Instance) -> StartResult:
    """Build if needed, start the instance, and await health."""
    runner = ComposeRunner(instance)
    runner.up(build=True)
    healthy = runner.wait_healthy()
    return StartResult(instance=instance, healthy=healthy, url=instance_url(instance))


def stop(instance: Instance) -> None:
    """Stop the instance and remove its containers."""
    ComposeRunner(instance).down()


def restart(instance: Instance) -> None:
    """Restart the instance's containers (down, then up with a rebuild)."""
    ComposeRunner(instance).restart()


@dataclass(frozen=True)
class StatusResult:
    instance: Instance
    ps_text: str
    health: str  # healthy / unhealthy / running / not running
    url: str | None


def _status_health(ps_text: str) -> str:
    lowered = ps_text.lower()
    if "unhealthy" in lowered:
        return "unhealthy"
    if "healthy" in lowered:
        return "healthy"
    if "running" in lowered or " up " in f" {lowered} ":
        return "running"
    return "not running"


def status(instance: Instance) -> StatusResult:
    """Return the container state, a health summary and the instance URL."""
    out = ComposeRunner(instance).ps()
    ps_text = out if isinstance(out, str) else ""
    return StatusResult(
        instance=instance,
        ps_text=ps_text,
        health=_status_health(ps_text),
        url=instance_url(instance),
    )
