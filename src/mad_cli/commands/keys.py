"""``mad keys set|list|remove`` — manage credentials / API keys in ``.env``.

Thin adapter over :mod:`mad_cli.core.usecases.keys`. A key is a *builtin*
(``github``, ``claude-oauth``, …), whose value fans out to one or more env vars,
or a raw *custom* ``[A-Z][A-Z0-9_]*`` variable. ``claude-oauth`` also materialises
the container credentials file. Values are always masked when shown.
"""

from __future__ import annotations

import typer
from rich.table import Table

from mad_cli.commands._adapt import fail, resolve_or_die
from mad_cli.core.instance import Instance
from mad_cli.core.usecases import keys as uc
from mad_cli.core.usecases.errors import UseCaseError, ValidationError
from mad_cli.ui.console import console, error, info, ok, warn
from mad_cli.ui.prompts import PromptRequiredError, ask

keys_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Manage API keys and tokens stored in an instance's .env.",
)

_INSTANCE_OPTION = typer.Option(
    None, "--instance", "-i", help="Instance name (optional when exactly one instance exists)."
)


def _restart_hint(instance: Instance) -> None:
    info(f"Restart the instance to apply: mad restart {instance.name}")


def _prompt_value(prompt: str, *, secret: bool) -> str:
    try:
        return ask(prompt, secret=secret)
    except PromptRequiredError as exc:
        error("A value is required. Pass it as an argument or run in an interactive terminal.")
        raise typer.Exit(1) from exc


@keys_app.command("set")
def set_key(
    key: str = typer.Argument(
        ..., help="Builtin key id (e.g. github, claude-oauth) or a custom VAR name."
    ),
    value: str | None = typer.Argument(None, help="Value to store. Omit to be prompted."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Store a builtin key (fanned out to its env vars) or a custom variable."""
    inst = resolve_or_die(instance)
    if value is None:
        try:
            prompt, secret = uc.key_prompt(key)
        except ValidationError as exc:
            fail(exc)
        value = _prompt_value(prompt, secret=secret)

    try:
        res = uc.set_key(inst, key, value)
    except UseCaseError as exc:
        fail(exc)

    if res.credentials_path is not None:
        ok(f"Claude credentials → {res.credentials_path}")
    if res.builtin:
        ok(f"Set {res.id} ({', '.join(res.env_vars)}) on {inst.name}.")
    else:
        ok(f"Set {res.id} on {inst.name}.")
    _restart_hint(inst)


@keys_app.command("list")
def list_keys(instance: str | None = _INSTANCE_OPTION) -> None:
    """Show which builtin keys are set (masked) plus any custom secret vars."""
    inst = resolve_or_die(instance)
    view = uc.list_keys(inst)

    table = Table(title=f"Keys — {inst.name}")
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Env vars")
    table.add_column("Status")
    table.add_column("Value")
    for status in view.builtins:
        table.add_row(
            status.id,
            ", ".join(status.env_vars),
            "set" if status.is_set else "unset",
            status.masked,
        )
    console.print(table)

    if view.custom:
        ctable = Table(title="Custom secrets")
        ctable.add_column("Env var", style="bold", no_wrap=True)
        ctable.add_column("Value")
        for secret in view.custom:
            ctable.add_row(secret.key, secret.masked)
        console.print(ctable)


@keys_app.command("remove")
def remove_key(
    key: str = typer.Argument(..., help="Builtin key id or custom VAR name to remove."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Remove a builtin key's env vars (or a custom variable) from ``.env``."""
    inst = resolve_or_die(instance)
    try:
        res = uc.remove_key(inst, key)
    except UseCaseError as exc:
        fail(exc)

    if not res.existed:
        warn(f"{res.id} is not set on {inst.name}; nothing to remove.")
        return

    if res.builtin:
        ok(f"Removed {res.id} ({', '.join(res.env_vars)}) from {inst.name}.")
    else:
        ok(f"Removed {res.id} from {inst.name}.")
    if res.credentials_left is not None:
        warn(f"Claude credentials file left in place on disk: {res.credentials_left}")
    _restart_hint(inst)
