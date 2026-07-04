"""``mad versions [INSTANCE]`` and ``mad update INSTANCE`` — version reporting and upgrades.

``versions`` renders, per instance, the pinned ``MAD_VERSION`` (or ``latest``), the
version installed inside the running container (best effort), the latest release on
PyPI and whether an update is available. ``update`` re-pins ``MAD_VERSION`` in the
instance ``.env`` and rebuilds the container from scratch, mirroring the lifecycle
feedback of ``mad start``.
"""

from __future__ import annotations

import typer
from rich.table import Table

from mad_cli.core import pypi
from mad_cli.core.compose import ComposeError, ComposeRunner
from mad_cli.core.instance import (
    Instance,
    InstanceNotFoundError,
    discover_instances,
    get_instance,
)
from mad_cli.core.templates import EDGE_PACKAGE
from mad_cli.ui.console import console, error, header, info, ok, run_step, warn

_NOT_RUNNING = "not running"
_UNKNOWN = "?"


def _label(instance: Instance) -> str:
    """Instance name, tagged ``(legacy)`` for the old single-instance layout."""
    return f"{instance.name} (legacy)" if getattr(instance, "legacy", False) else instance.name


def _edge_package(instance: Instance) -> str:
    """The PyPI package to check: ``MAD_EDGE_PACKAGE`` from the .env, else the default."""
    return instance.env.get("MAD_EDGE_PACKAGE") or EDGE_PACKAGE


def _installed_version(instance: Instance) -> str:
    """Version reported by ``mad`` inside the container, or ``"not running"``.

    Runs a throwaway ``python -c`` in the ``mad`` service; a ``ComposeError`` (the
    container is stopped or Docker is unavailable) degrades to ``"not running"``.
    """
    try:
        out = ComposeRunner(instance).exec(["python", "-c", "import mad; print(mad.__version__)"])
    except ComposeError:
        return _NOT_RUNNING
    return out.strip() or _NOT_RUNNING


def _version_tuple(version: str) -> tuple[int, ...]:
    """Best-effort ``(major, minor, patch, …)`` tuple for ordering, no new deps.

    Each dot-separated segment contributes its leading run of digits (``"1.2.3rc1"``
    → ``(1, 2, 3)``); a segment with no leading digit contributes ``0``.
    """
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
    """Compare the installed version against the latest on PyPI."""
    if latest is None or installed in (_NOT_RUNNING, _UNKNOWN):
        return _UNKNOWN
    if _version_tuple(installed) >= _version_tuple(latest):
        return "up to date"
    return "update available"


def versions(
    instance: str | None = typer.Argument(
        None, help="Instance name (reports on every instance when omitted)."
    ),
) -> None:
    """Show pinned / installed / latest versions and whether an update is available."""
    if instance is not None:
        try:
            targets = [get_instance(instance)]
        except InstanceNotFoundError as exc:
            error(f"Instance {instance!r} not found. Run `mad list` to see available instances.")
            raise typer.Exit(1) from exc
    else:
        targets = discover_instances()
        if not targets:
            info("No instances yet. Run `mad install` to create one.")
            return

    table = Table(title="mad versions")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Pinned")
    table.add_column("Installed")
    table.add_column("Latest on PyPI")
    table.add_column("Update")

    latest_cache: dict[str, str | None] = {}
    for inst in targets:
        installed = _installed_version(inst)
        package = _edge_package(inst)
        if package not in latest_cache:
            latest_cache[package] = pypi.latest_version(package)
        latest = latest_cache[package]
        table.add_row(
            _label(inst),
            inst.version_pin or "latest",
            installed,
            latest if latest is not None else _UNKNOWN,
            _update_status(installed, latest),
        )
    console.print(table)


def update(
    instance: str = typer.Argument(..., help="Instance name."),
    version: str | None = typer.Option(
        None, "--version", help="Version to pin (omit or blank to track latest)."
    ),
) -> None:
    """Re-pin ``MAD_VERSION`` and rebuild the instance from scratch."""
    try:
        inst = get_instance(instance)
    except InstanceNotFoundError as exc:
        error(f"Instance {instance!r} not found. Run `mad list` to see available instances.")
        raise typer.Exit(1) from exc

    pin = version or ""
    inst.env.set("MAD_VERSION", pin)
    inst.env.save(inst.env_file)

    target = pin or "latest"
    header(f"Updating {inst.name} → {target}")
    runner = ComposeRunner(inst)
    run_step("Rebuilding image (no cache)…", lambda: runner.build(no_cache=True))
    run_step("Starting container…", lambda: runner.up())
    healthy = run_step("Waiting for health…", runner.wait_healthy)
    if healthy:
        ok(f"{inst.name} updated to {target}.")
    else:
        warn(f"{inst.name} rebuilt but is not healthy yet. Check `mad status` and `mad logs`.")
        raise typer.Exit(1)
