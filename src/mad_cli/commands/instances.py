"""``mad list``, ``mad info NAME`` and ``mad adopt`` — instance inventory and migration.

Thin adapter over :mod:`mad_cli.core.usecases.instances` and
:mod:`mad_cli.core.usecases.adopt`.
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from mad_cli.commands._adapt import fail
from mad_cli.core.keyspec import mask
from mad_cli.core.usecases import adopt as uc_adopt
from mad_cli.core.usecases import instances as uc
from mad_cli.core.usecases.errors import NotFoundError, UseCaseError
from mad_cli.ui.console import console, error, header, info, ok, warn
from mad_cli.ui.prompts import confirm


def list_() -> None:
    """List configured instances with their port, state, health and pinned version."""
    rows = uc.list_instances()
    if not rows:
        info("No instances yet. Run `mad install` to create one.")
        return

    table = Table(title="mad instances")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Port")
    table.add_column("State")
    table.add_column("Health")
    table.add_column("Version")
    for row in rows:
        label = f"{row.name} (legacy)" if row.legacy else row.name
        table.add_row(
            label,
            str(row.port) if row.port is not None else "-",
            row.state,
            row.health,
            row.version,
        )
    console.print(table)


def info_cmd(name: str = typer.Argument(..., help="Instance name.")) -> None:
    """Show an instance's paths and its .env values (secrets masked)."""
    try:
        details = uc.instance_info(name)
    except NotFoundError:
        error(f"Instance {name!r} not found. Run `mad list` to see available instances.")
        raise typer.Exit(1) from None

    paths = Table(show_header=False, box=None, pad_edge=False)
    paths.add_column("key", style="bold cyan", no_wrap=True)
    paths.add_column("value")
    paths.add_row("Config dir", str(details.config_dir))
    paths.add_row("Compose file", str(details.compose_file))
    paths.add_row("Data path", str(details.data_path) if details.data_path else "-")
    console.print(Panel(paths, title=f"Instance {details.name}", border_style="cyan", expand=False))

    env_table = Table(title=".env")
    env_table.add_column("Key", style="bold", no_wrap=True)
    env_table.add_column("Value")
    for item in details.env:
        shown = mask(item.value) if item.value and item.secret else item.value
        env_table.add_row(item.key, shown)
    console.print(env_table)


def adopt() -> None:
    """Migrate the legacy single-instance layout into ``instances/<name>/``."""
    try:
        plan = uc_adopt.plan_adopt()
    except UseCaseError as exc:
        fail(exc)
    if plan is None:
        info("Nothing to adopt — no legacy single-instance layout found.")
        return

    header(f"Adopt legacy instance {plan.name!r}")
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("from", style="bold cyan")
    table.add_column("arrow")
    table.add_column("to")
    for name in plan.movable:
        table.add_row(str(plan.source / name), "→", str(plan.target / name))
    console.print(table)
    info("Data (MAD_DATA_PATH) is not moved — only the config files above are relocated.")
    warn(
        f"The Compose project name changes from the legacy layout to mad-{plan.name}. "
        f"If the legacy container is still running, stop it first with "
        f"`docker compose -f {plan.source / 'compose.yml'} down` (this command does not)."
    )

    if not confirm(f"Move {len(plan.movable)} file(s) into {plan.target}?", default=True):
        info("Adoption cancelled.")
        return

    uc_adopt.apply_adopt(plan)
    ok(f"Adopted {plan.name!r} → {plan.target}")
