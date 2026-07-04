"""Version-reporting and update use cases.

``versions`` reports, per instance, the pinned / installed / latest-on-PyPI
versions and whether an update is available. ``update`` re-pins ``MAD_VERSION``
and rebuilds from scratch (synchronous in the MVP). Shared by ``mad versions`` /
``mad update`` and the ``/v1/instances/{name}/versions`` + ``/update`` routes.
"""

from __future__ import annotations

from dataclasses import dataclass

from mad_cli.core import pypi
from mad_cli.core.compose import ComposeError, ComposeRunner
from mad_cli.core.instance import Instance, InstanceNotFoundError, discover_instances, get_instance
from mad_cli.core.templates import EDGE_PACKAGE
from mad_cli.core.usecases.errors import NotFoundError

NOT_RUNNING = "not running"
UNKNOWN = "?"


def _edge_package(instance: Instance) -> str:
    """The PyPI package to check: ``MAD_EDGE_PACKAGE`` from the .env, else default."""
    return instance.env.get("MAD_EDGE_PACKAGE") or EDGE_PACKAGE


def _installed_version(instance: Instance) -> str:
    """Version reported by ``mad`` inside the container, or ``"not running"``."""
    try:
        out = ComposeRunner(instance).exec(["python", "-c", "import mad; print(mad.__version__)"])
    except ComposeError:
        return NOT_RUNNING
    return out.strip() or NOT_RUNNING


def _version_tuple(version: str) -> tuple[int, ...]:
    """Best-effort ordering tuple: each dotted segment's leading digit run."""
    parts: list[int] = []
    for chunk in version.split("."):
        digits = ""
        for char in chunk:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _update_status(installed: str, latest: str | None) -> str:
    if latest is None or installed in (NOT_RUNNING, UNKNOWN):
        return UNKNOWN
    if _version_tuple(installed) >= _version_tuple(latest):
        return "up to date"
    return "update available"


@dataclass(frozen=True)
class VersionRow:
    name: str
    legacy: bool
    pinned: str  # the pin, or "latest"
    installed: str
    latest: str  # latest on PyPI, or "?"
    update: str  # up to date / update available / ?


def versions(name: str | None) -> list[VersionRow]:
    """Report version state for ``name`` (or every instance when ``None``).

    Raises :class:`NotFoundError` for a named instance that does not exist; an
    empty list means no instances are configured.
    """
    if name is not None:
        try:
            targets = [get_instance(name)]
        except InstanceNotFoundError as exc:
            raise NotFoundError(f"instance {name!r} not found") from exc
    else:
        targets = discover_instances()

    rows: list[VersionRow] = []
    latest_cache: dict[str, str | None] = {}
    for inst in targets:
        installed = _installed_version(inst)
        package = _edge_package(inst)
        if package not in latest_cache:
            latest_cache[package] = pypi.latest_version(package)
        latest = latest_cache[package]
        rows.append(
            VersionRow(
                name=inst.name,
                legacy=bool(getattr(inst, "legacy", False)),
                pinned=inst.version_pin or "latest",
                installed=installed,
                latest=latest if latest is not None else UNKNOWN,
                update=_update_status(installed, latest),
            )
        )
    return rows


@dataclass(frozen=True)
class UpdateResult:
    instance: Instance
    target: str  # the pin applied, or "latest"
    healthy: bool


def update(instance: Instance, version: str | None) -> UpdateResult:
    """Re-pin ``MAD_VERSION`` and rebuild the instance from scratch.

    The returned ``healthy`` flag lets the adapter decide how to signal a
    not-yet-healthy rebuild (the CLI exits non-zero; the API reports it in the
    body).
    """
    pin = version or ""
    instance.env.set("MAD_VERSION", pin)
    instance.env.save(instance.env_file)

    runner = ComposeRunner(instance)
    runner.build(no_cache=True)
    runner.up()
    healthy = runner.wait_healthy()
    return UpdateResult(instance=instance, target=pin or "latest", healthy=healthy)
