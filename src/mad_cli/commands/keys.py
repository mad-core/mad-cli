"""``mad keys set|list|remove`` — manage credentials / API keys in ``.env``.

A key is either a *builtin* registered in :data:`mad_cli.core.keyspec.BUILTIN_KEYS`
(``github``, ``claude-oauth``, …), whose value fans out to one or more env vars
with the same value, or a raw *custom* env-var name (``[A-Z][A-Z0-9_]*``) written
verbatim. ``claude-oauth`` additionally materialises the container's Claude
credentials file. Values are always masked when shown — a full secret is never
printed.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.table import Table

from mad_cli.commands._common import is_secret_key
from mad_cli.core.claude_creds import write_claude_credentials
from mad_cli.core.instance import (
    Instance,
    InstanceNotFoundError,
    default_instance,
    discover_instances,
    get_instance,
)
from mad_cli.core.keyspec import BUILTIN_KEYS, KeySpec, mask
from mad_cli.ui.console import console, error, info, ok, warn
from mad_cli.ui.prompts import PromptRequiredError, ask

keys_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Manage API keys and tokens stored in an instance's .env.",
)

# A custom key is written verbatim; it must look like a shell env-var name.
_CUSTOM_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]*")

_INSTANCE_OPTION = typer.Option(
    None, "--instance", "-i", help="Instance name (optional when exactly one instance exists)."
)


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


def _claude_creds_path(instance: Instance) -> Path | None:
    """The Claude credentials file path for ``instance`` (``None`` if no data path)."""
    if instance.data_path is None:
        return None
    return instance.data_path / instance.name / "claude" / ".credentials.json"


def _prompt_value(prompt: str, *, secret: bool) -> str:
    try:
        return ask(prompt, secret=secret)
    except PromptRequiredError as exc:
        error("A value is required. Pass it as an argument or run in an interactive terminal.")
        raise typer.Exit(1) from exc


def _set_builtin(instance: Instance, spec: KeySpec, value: str | None) -> None:
    if value is None:
        value = _prompt_value(spec.prompt, secret=spec.secret)
    for var in spec.env_vars:
        instance.env.set(var, value)
    instance.env.save()

    if spec.writes_claude_credentials:
        if instance.data_path is None:
            error("Cannot write Claude credentials: MAD_DATA_PATH is not set for this instance.")
            raise typer.Exit(1)
        claude_dir = instance.data_path / instance.name / "claude"
        creds = write_claude_credentials(claude_dir, value)
        ok(f"Claude credentials → {creds}")

    ok(f"Set {spec.id} ({', '.join(spec.env_vars)}) on {instance.name}.")
    _restart_hint(instance)


def _set_custom(instance: Instance, key: str, value: str | None) -> None:
    if value is None:
        # Custom keys are treated as secret by default — safest when unknown.
        value = _prompt_value(f"Value for {key}", secret=True)
    instance.env.set(key, value)
    instance.env.save()
    ok(f"Set {key} on {instance.name}.")
    _restart_hint(instance)


@keys_app.command("set")
def set_key(
    key: str = typer.Argument(
        ..., help="Builtin key id (e.g. github, claude-oauth) or a custom VAR name."
    ),
    value: str | None = typer.Argument(None, help="Value to store. Omit to be prompted."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Store a builtin key (fanned out to its env vars) or a custom variable."""
    inst = _resolve_instance(instance)
    spec = BUILTIN_KEYS.get(key)
    if spec is not None:
        _set_builtin(inst, spec, value)
    elif _CUSTOM_KEY_RE.fullmatch(key):
        _set_custom(inst, key, value)
    else:
        error(
            f"Unknown key {key!r}. Use a builtin id ({', '.join(BUILTIN_KEYS)}) "
            "or an env-var name matching [A-Z][A-Z0-9_]*."
        )
        raise typer.Exit(1)


@keys_app.command("list")
def list_keys(instance: str | None = _INSTANCE_OPTION) -> None:
    """Show which builtin keys are set (masked) plus any custom secret vars."""
    inst = _resolve_instance(instance)
    env = inst.env
    spec_vars = {var for spec in BUILTIN_KEYS.values() for var in spec.env_vars}

    table = Table(title=f"Keys — {inst.name}")
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Env vars")
    table.add_column("Status")
    table.add_column("Value")
    for spec in BUILTIN_KEYS.values():
        values = [env.get(var) for var in spec.env_vars]
        first = next((v for v in values if v), None)
        status = "set" if first else "unset"
        shown = mask(first) if first else "-"
        table.add_row(spec.id, ", ".join(spec.env_vars), status, shown)
    console.print(table)

    custom = [
        key
        for key in env.keys()  # noqa: SIM118 — EnvFile.keys() is its contract API, not a dict
        if key not in spec_vars and is_secret_key(key)
    ]
    if custom:
        ctable = Table(title="Custom secrets")
        ctable.add_column("Env var", style="bold", no_wrap=True)
        ctable.add_column("Value")
        for key in custom:
            value = env.get(key) or ""
            ctable.add_row(key, mask(value) if value else "-")
        console.print(ctable)


@keys_app.command("remove")
def remove_key(
    key: str = typer.Argument(..., help="Builtin key id or custom VAR name to remove."),
    instance: str | None = _INSTANCE_OPTION,
) -> None:
    """Remove a builtin key's env vars (or a custom variable) from ``.env``."""
    inst = _resolve_instance(instance)
    spec = BUILTIN_KEYS.get(key)

    if spec is not None:
        present = [var for var in spec.env_vars if inst.env.get(var) is not None]
        if not present:
            warn(f"{spec.id} is not set on {inst.name}; nothing to remove.")
            return
        for var in spec.env_vars:
            inst.env.unset(var)
        inst.env.save()
        ok(f"Removed {spec.id} ({', '.join(spec.env_vars)}) from {inst.name}.")
        if spec.writes_claude_credentials:
            creds = _claude_creds_path(inst)
            if creds is not None and creds.exists():
                warn(f"Claude credentials file left in place on disk: {creds}")
        _restart_hint(inst)
    elif _CUSTOM_KEY_RE.fullmatch(key):
        if inst.env.get(key) is None:
            warn(f"{key} is not set on {inst.name}; nothing to remove.")
            return
        inst.env.unset(key)
        inst.env.save()
        ok(f"Removed {key} from {inst.name}.")
        _restart_hint(inst)
    else:
        error(
            f"Unknown key {key!r}. Use a builtin id ({', '.join(BUILTIN_KEYS)}) "
            "or an env-var name matching [A-Z][A-Z0-9_]*."
        )
        raise typer.Exit(1)
