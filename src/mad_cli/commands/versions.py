"""``mad versions [INSTANCE]`` and ``mad update INSTANCE`` — versions and upgrades.

Thin adapter over :mod:`mad_cli.core.usecases.versions`. ``versions`` renders, per
instance, the pinned / installed / latest-on-PyPI versions and whether an update
is available; ``update`` re-pins ``MAD_VERSION`` and rebuilds from scratch.
"""

from __future__ import annotations

import typer
from rich.table import Table

from mad_cli.commands._adapt import resolve_or_die
from mad_cli.core.usecases import versions as uc
from mad_cli.core.usecases.errors import NotFoundError
from mad_cli.ui.console import console, error, header, info, ok, run_step, warn


def versions(
    instance: str | None = typer.Argument(
        None, help="Instance name (reports on every instance when omitted)."
    ),
) -> None:
    """Show pinned / installed / latest versions and whether an update is available."""
    try:
        rows = uc.versions(instance)
    except NotFoundError:
        error(f"Instance {instance!r} not found. Run `mad list` to see available instances.")
        raise typer.Exit(1) from None

    if not rows:
        info("No instances yet. Run `mad install` to create one.")
        return

    table = Table(title="mad versions")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Pinned")
    table.add_column("Installed")
    table.add_column("Latest on PyPI")
    table.add_column("Update")
    for row in rows:
        label = f"{row.name} (legacy)" if row.legacy else row.name
        table.add_row(label, row.pinned, row.installed, row.latest, row.update)
    console.print(table)


def update(
    instance: str = typer.Argument(..., help="Instance name."),
    version: str | None = typer.Option(
        None, "--version", help="Version to pin (omit or blank to track latest)."
    ),
) -> None:
    """Re-pin ``MAD_VERSION`` and rebuild the instance from scratch."""
    inst = resolve_or_die(instance)
    header(f"Updating {inst.name} → {version or 'latest'}")
    res = run_step("Rebuilding image (no cache) and starting…", lambda: uc.update(inst, version))
    if res.healthy:
        ok(f"{inst.name} updated to {res.target}.")
    else:
        warn(f"{inst.name} rebuilt but is not healthy yet. Check `mad status` and `mad logs`.")
        raise typer.Exit(1)
