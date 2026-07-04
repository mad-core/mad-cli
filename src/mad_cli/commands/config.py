"""``mad config get|set|unset`` — read and edit an instance's ``.env`` values.

This is the general-purpose ``.env`` editor (``mad keys`` is the credential-aware
front end). Values that look like secrets are masked on read unless ``--reveal``
is passed, and a handful of known keys are validated on write. Keys that were
baked into the rendered ``compose.yml`` at install time (the host port and data
bind) still write to ``.env`` here, but a warning explains that a regenerate is
required for the change to take effect.
"""

from __future__ import annotations

from collections.abc import Callable

import typer
from rich.table import Table

from mad_cli.commands._common import is_secret_key
from mad_cli.core.instance import (
    Instance,
    InstanceNotFoundError,
    default_instance,
    discover_instances,
    get_instance,
)
from mad_cli.core.keyspec import mask
from mad_cli.ui.console import console, error, info, ok, warn

config_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Read and edit an instance's .env configuration.",
)

_INSTANCE_OPTION = typer.Option(
    None, "--instance", "-i", help="Instance name (optional when exactly one instance exists)."
)

# Keys whose value was rendered into compose.yml at install time.
_COMPOSE_KEYS = ("MAD_HOST_PORT", "MAD_DATA_PATH")


def _validate_port(value: str) -> str:
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"invalid MAD_HOST_PORT {value!r}: must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid MAD_HOST_PORT {value!r}: must be between 1 and 65535")
    return str(port)


def _validate_timeout(value: str) -> str:
    try:
        seconds = int(value)
    except ValueError:
        raise ValueError(f"invalid MAD_AGENT_TIMEOUT_S {value!r}: must be an integer") from None
    if seconds <= 0:
        raise ValueError(f"invalid MAD_AGENT_TIMEOUT_S {value!r}: must be a positive integer")
    return str(seconds)


_VALIDATORS: dict[str, Callable[[str], str]] = {
    "MAD_HOST_PORT": _validate_port,
    "MAD_AGENT_TIMEOUT_S": _validate_timeout,
}


def _resolve_instance(name: str | None) -> Instance:
    """Resolve ``name`` (or the sole instance) to an :class:`Instance`, or exit."""
    if name is not None:
        try:
            return get_instance(name)
        except InstanceNotFoundError as exc:
            error(f"Instance {name!r} not found. Run `mad list` to see available instances.")
            raise typer.Exit(1) from exc

    single = default_instance()
    if single is not None:
        return single

    instances = discover_instances()
    if not instances:
        error("No instances found. Run `mad install` first.")
        raise typer.Exit(1)
    names = ", ".join(sorted(inst.name for inst in instances))
    error(f"Multiple instances exist ({names}). Name one with --instance.")
    raise typer.Exit(1)


def _restart_hint(instance: Instance) -> None:
    info(f"Restart the instance to apply: mad restart {instance.name}")


def _display(key: str, value: str, *, reveal: bool) -> str:
    if reveal or not value or not is_secret_key(key):
        return value
    return mask(value)


@config_app.command("get")
def get(
    key: str | None = typer.Argument(None, help="Env key to read. Omit to list every value."),
    instance: str | None = _INSTANCE_OPTION,
    reveal: bool = typer.Option(False, "--reveal", help="Show secret values in full."),
) -> None:
    """Print one ``.env`` value, or the whole file (secrets masked)."""
    inst = _resolve_instance(instance)
    env = inst.env

    if key is None:
        table = Table(title=f".env — {inst.name}")
        table.add_column("Key", style="bold", no_wrap=True)
        table.add_column("Value")
        for name in env.keys():  # noqa: SIM118 — EnvFile.keys() is its contract API, not a dict
            table.add_row(name, _display(name, env.get(name) or "", reveal=reveal))
        console.print(table)
        return

    value = env.get(key)
    if value is None:
        error(f"{key} is not set on {inst.name}.")
        raise typer.Exit(1)
    console.print(_display(key, value, reveal=reveal), markup=False, highlight=False)


@config_app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Env key to write."),
    value: str = typer.Argument(..., help="Value to store."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Set an ``.env`` value, validating a handful of known keys."""
    inst = _resolve_instance(instance)

    validator = _VALIDATORS.get(key)
    if validator is not None:
        try:
            value = validator(value)
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(1) from exc

    inst.env.set(key, value)
    inst.env.save()

    shown = mask(value) if value and is_secret_key(key) else value
    ok(f"Set {key} = {shown} on {inst.name}.")

    if key in _COMPOSE_KEYS:
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
    inst = _resolve_instance(instance)
    if inst.env.get(key) is None:
        warn(f"{key} is not set on {inst.name}; nothing to remove.")
        return
    inst.env.unset(key)
    inst.env.save()
    ok(f"Unset {key} on {inst.name}.")
    _restart_hint(inst)
