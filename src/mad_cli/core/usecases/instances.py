"""Instance inventory use cases: resolve, list (with state/health) and info.

Shared by ``mad list`` / ``mad info`` and the ``/v1/instances`` routes. The
state/health probe is best-effort — Docker being unreachable degrades the row to
``unknown``/``-`` rather than raising, so a listing always renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mad_cli.core.compose import ComposeRunner
from mad_cli.core.instance import (
    Instance,
    InstanceNotFoundError,
    default_instance,
    discover_instances,
    get_instance,
)
from mad_cli.core.keyspec import display_value, is_secret_key
from mad_cli.core.usecases.errors import AmbiguousInstanceError, NotFoundError


def resolve_instance(name: str | None) -> Instance:
    """Resolve ``name`` (or the sole instance) to an :class:`Instance`.

    Raises :class:`NotFoundError` when a named instance is missing or none are
    configured, and :class:`AmbiguousInstanceError` when several exist and none
    was named. The messages are adapter-agnostic; the CLI appends its own hints.
    """
    if name is not None:
        try:
            return get_instance(name)
        except InstanceNotFoundError as exc:
            raise NotFoundError(f"instance {name!r} not found") from exc

    single = default_instance()
    if single is not None:
        return single

    instances = discover_instances()
    if not instances:
        raise NotFoundError("no instances configured")
    names = ", ".join(sorted(inst.name for inst in instances))
    raise AmbiguousInstanceError(f"multiple instances exist ({names}); name one")


def state_health(instance: Instance) -> tuple[str, str]:
    """Best-effort ``(state, health)`` parsed from ``docker compose ps``.

    Health is read from the ``ps`` text rather than ``wait_healthy`` (which
    blocks). A missing token degrades to ``"-"``; any failure to reach Docker
    leaves state ``"unknown"`` so callers still render.
    """
    try:
        out = ComposeRunner(instance).ps()
    except Exception:  # docker missing/erroring — inventory must still render
        return "unknown", "-"
    if not isinstance(out, str):
        return "unknown", "-"
    lowered = out.lower()
    state = "running" if "running" in lowered or " up " in f" {lowered} " else "stopped"
    if "unhealthy" in lowered:
        health = "unhealthy"
    elif "healthy" in lowered:
        health = "healthy"
    else:
        health = "-"
    return state, health


@dataclass(frozen=True)
class InstanceSummary:
    """One row of the instance inventory."""

    name: str
    legacy: bool
    port: int | None
    state: str
    health: str
    version: str  # the pinned MAD_VERSION, or "latest" when it tracks latest


def list_instances() -> list[InstanceSummary]:
    """Return a summary row per configured instance (state/health best-effort)."""
    rows: list[InstanceSummary] = []
    for inst in discover_instances():
        state, health = state_health(inst)
        rows.append(
            InstanceSummary(
                name=inst.name,
                legacy=bool(getattr(inst, "legacy", False)),
                port=inst.host_port,
                state=state,
                health=health,
                version=inst.version_pin or "latest",
            )
        )
    return rows


@dataclass(frozen=True)
class EnvItem:
    """One ``.env`` assignment, tagged as secret-looking or not."""

    key: str
    value: str
    secret: bool

    def display(self, *, reveal: bool = False) -> str:
        """The value as it should be shown (masked unless ``reveal``)."""
        return display_value(self.key, self.value, reveal=reveal)


@dataclass(frozen=True)
class InstanceInfo:
    """An instance's resolved paths plus its ``.env`` items."""

    name: str
    legacy: bool
    config_dir: Path
    compose_file: Path
    data_path: Path | None
    port: int | None
    version: str | None
    env: list[EnvItem]


def _env_items(instance: Instance) -> list[EnvItem]:
    env = instance.env
    return [
        EnvItem(key=key, value=env.get(key) or "", secret=is_secret_key(key))
        for key in env.keys()  # noqa: SIM118 — EnvFile.keys() is its contract API
    ]


def instance_info(name: str) -> InstanceInfo:
    """Return the resolved paths and ``.env`` items for the named instance.

    Raises :class:`NotFoundError` when the instance does not exist.
    """
    try:
        instance = get_instance(name)
    except InstanceNotFoundError as exc:
        raise NotFoundError(f"instance {name!r} not found") from exc
    return InstanceInfo(
        name=instance.name,
        legacy=bool(getattr(instance, "legacy", False)),
        config_dir=instance.config_dir,
        compose_file=instance.compose_file,
        data_path=instance.data_path,
        port=instance.host_port,
        version=instance.version_pin,
        env=_env_items(instance),
    )
