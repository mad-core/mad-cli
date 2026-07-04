"""``mad config get|set|unset`` — read and edit an instance's ``.env`` values.

Thin adapter over :mod:`mad_cli.core.usecases.configvals` — the general-purpose
``.env`` editor (``mad keys`` is the credential-aware front end). Secret-looking
values are masked on read unless ``--reveal`` is passed, and a handful of known
keys are validated on write.
"""

from __future__ import annotations

import typer
from rich.table import Table

from mad_cli.commands._adapt import fail, resolve_or_die
from mad_cli.core.instance import Instance
from mad_cli.core.usecases import configvals as uc
from mad_cli.core.usecases.errors import NotFoundError, ValidationError
from mad_cli.ui.console import console, error, info, ok, warn

config_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Read and edit an instance's .env configuration.",
)

_INSTANCE_OPTION = typer.Option(
    None, "--instance", "-i", help="Instance name (optional when exactly one instance exists)."
)


def _restart_hint(instance: Instance) -> None:
    info(f"Restart the instance to apply: mad restart {instance.name}")


@config_app.command("get")
def get(
    key: str | None = typer.Argument(None, help="Env key to read. Omit to list every value."),
    instance: str | None = _INSTANCE_OPTION,
    reveal: bool = typer.Option(False, "--reveal", help="Show secret values in full."),
) -> None:
    """Print one ``.env`` value, or the whole file (secrets masked)."""
    inst = resolve_or_die(instance)

    if key is None:
        table = Table(title=f".env — {inst.name}")
        table.add_column("Key", style="bold", no_wrap=True)
        table.add_column("Value")
        for item in uc.list_config(inst):
            table.add_row(item.key, item.display(reveal=reveal))
        console.print(table)
        return

    try:
        item = uc.get_config(inst, key)
    except NotFoundError:
        error(f"{key} is not set on {inst.name}.")
        raise typer.Exit(1) from None
    console.print(item.display(reveal=reveal), markup=False, highlight=False)


@config_app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Env key to write."),
    value: str = typer.Argument(..., help="Value to store."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Set an ``.env`` value, validating a handful of known keys."""
    inst = resolve_or_die(instance)
    try:
        item, compose_baked = uc.set_config(inst, key, value)
    except ValidationError as exc:
        fail(exc)

    ok(f"Set {key} = {item.display()} on {inst.name}.")
    if compose_baked:
        warn(
            f"{key} was baked into compose.yml at install time. This updates .env only; "
            "a port/bind change needs the instance regenerated (v0.3+) to take effect."
        )
    _restart_hint(inst)


@config_app.command("unset")
def unset(
    key: str = typer.Argument(..., help="Env key to remove."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Remove a key from the instance's ``.env``."""
    inst = resolve_or_die(instance)
    if not uc.unset_config(inst, key):
        warn(f"{key} is not set on {inst.name}; nothing to remove.")
        return
    ok(f"Unset {key} on {inst.name}.")
    _restart_hint(inst)
