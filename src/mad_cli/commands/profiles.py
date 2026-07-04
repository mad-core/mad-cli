"""``mad profiles create|list|show|delete|apply`` — named environment profiles.

A *profile* is a reusable, named set of ``.env`` values (credentials + tuning,
never instance identity) stored under ``config_root()/profiles/<name>.env``. Use
it to stamp consistent config across instances: ``mad profiles apply`` overlays a
profile onto an existing instance's ``.env``, and ``mad install --profile`` feeds
a profile's values as the wizard's defaults.

The engine lives in :mod:`mad_cli.core.profiles`; this module is the Typer
surface, so it never touches the filesystem directly.
"""

from __future__ import annotations

import re
import sys

import typer
from rich.table import Table

from mad_cli.commands._common import is_secret_key
from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import InstanceNotFoundError, get_instance
from mad_cli.core.keyspec import mask
from mad_cli.core.profiles import (
    IDENTITY_KEYS,
    ProfileNotFoundError,
    delete_profile,
    list_profiles,
    load_profile,
    save_profile,
)
from mad_cli.ui.console import console, error, info, ok, warn
from mad_cli.ui.prompts import confirm

profiles_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Manage reusable named environment profiles (credentials + tuning).",
)

# A profile variable name: a shell env-var name (leading underscore allowed so
# keys like _CLAUDE_OAUTH_TOKEN round-trip).
_ENV_KEY_RE = re.compile(r"[A-Z_][A-Z0-9_]*")

# Module-level singleton for the repeatable --set option (a mutable-typed default
# may not be an inline call — flake8-bugbear B008).
_SET_OPTION = typer.Option(
    None,
    "--set",
    metavar="KEY=VALUE",
    help="Set a KEY=VALUE pair in the profile (repeatable).",
)


def _interactive() -> bool:
    """True only when stdin is a TTY, so a prompt will not block."""
    try:
        return sys.stdin.isatty()
    except (ValueError, OSError):
        return False


def _split_set(item: str) -> tuple[str, str]:
    """Split a ``KEY=VALUE`` --set entry, validating the key, or exit."""
    key, sep, value = item.partition("=")
    key = key.strip()
    if not sep or not key:
        error(f"invalid --set {item!r}: expected KEY=VALUE.")
        raise typer.Exit(1)
    if not _ENV_KEY_RE.fullmatch(key):
        error(f"invalid key {key!r}: must match [A-Z_][A-Z0-9_]* (an env-var name).")
        raise typer.Exit(1)
    return key, value


def _resolve_profile(name: str) -> EnvFile:
    """Load profile ``name`` to an :class:`EnvFile`, or exit with a hint."""
    try:
        return load_profile(name)
    except ProfileNotFoundError as exc:
        error(f"Profile {name!r} not found. Run `mad profiles list` to see available profiles.")
        raise typer.Exit(1) from exc


def _display(key: str, value: str, *, reveal: bool) -> str:
    """Mask a secret-looking value unless ``reveal`` is set."""
    if reveal or not value or not is_secret_key(key):
        return value
    return mask(value)


def _print_env(title: str, env: EnvFile, *, reveal: bool) -> None:
    """Print a profile's variables as a table (secret-looking values masked)."""
    table = Table(title=title)
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value")
    for key in env.keys():  # noqa: SIM118 — EnvFile.keys() is its contract API, not a dict
        table.add_row(key, _display(key, env.get(key) or "", reveal=reveal))
    console.print(table)


def _prompt_pairs(env: EnvFile) -> None:
    """Interactive mini-loop to add KEY=VALUE pairs to a new profile."""
    if not confirm("Add environment variables now?", default=False):
        return
    while True:
        key = console.input("[cyan]?[/cyan] Variable name (empty to finish): ").strip()
        if not key:
            break
        if not _ENV_KEY_RE.fullmatch(key):
            warn(f"invalid key {key!r}: must match [A-Z_][A-Z0-9_]*.")
            continue
        # Hide the value only when the key looks like a secret.
        value = console.input(f"[cyan]?[/cyan] Value for {key}: ", password=is_secret_key(key))
        env.set(key, value)
        if not confirm("Add another?", default=False):
            break


@profiles_app.command("create")
def create(
    name: str = typer.Argument(..., help="Profile name ([a-z0-9][a-z0-9-]*)."),
    from_instance: str | None = typer.Option(
        None,
        "--from-instance",
        help="Seed the profile from an instance's .env (identity keys excluded).",
    ),
    set_: list[str] | None = _SET_OPTION,
) -> None:
    """Create a profile, empty or seeded from an instance, plus optional KEY=VALUEs."""
    if name in list_profiles():
        error(f"Profile {name!r} already exists. Delete it first or pick another name.")
        raise typer.Exit(1)

    env = EnvFile.empty()

    if from_instance is not None:
        try:
            source = get_instance(from_instance)
        except InstanceNotFoundError as exc:
            error(f"Instance {from_instance!r} not found. Run `mad list` to see instances.")
            raise typer.Exit(1) from exc
        for key in source.env.keys():  # noqa: SIM118 — EnvFile.keys() is its contract API
            if key in IDENTITY_KEYS:
                continue
            value = source.env.get(key)
            if value is not None:
                env.set(key, value)

    for item in set_ or []:
        key, value = _split_set(item)
        env.set(key, value)

    if _interactive():
        _prompt_pairs(env)

    try:
        path = save_profile(name, env)
    except ValueError as exc:  # invalid name
        error(str(exc))
        raise typer.Exit(1) from exc

    ok(f"Created profile {name!r} ({len(env.keys())} variable(s)) → {path}")
    if env.keys():
        _print_env(f"Profile — {name}", env, reveal=False)
    info(f"Apply it to an instance with: mad profiles apply {name} <instance>")


@profiles_app.command("list")
def list_(  # noqa: A001 — command name; the Typer name is "list"
) -> None:
    """List every stored profile with its variable count."""
    names = list_profiles()
    if not names:
        info("No profiles yet. Create one with `mad profiles create NAME`.")
        return
    table = Table(title="Profiles")
    table.add_column("Profile", style="bold cyan", no_wrap=True)
    table.add_column("Variables", justify="right")
    for name in names:
        env = load_profile(name)
        table.add_row(name, str(len(env.keys())))
    console.print(table)


@profiles_app.command("show")
def show(
    name: str = typer.Argument(..., help="Profile to display."),
    reveal: bool = typer.Option(False, "--reveal", help="Show secret values in full."),
) -> None:
    """Print a profile's variables (secret-looking values masked)."""
    env = _resolve_profile(name)
    if not env.keys():
        info(f"Profile {name!r} is empty.")
        return
    _print_env(f"Profile — {name}", env, reveal=reveal)


@profiles_app.command("delete")
def delete(
    name: str = typer.Argument(..., help="Profile to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete a profile (asks for confirmation unless --yes)."""
    if name not in list_profiles():
        error(f"Profile {name!r} not found. Run `mad profiles list` to see available profiles.")
        raise typer.Exit(1)
    if not yes and not confirm(f"Delete profile {name!r}?", default=False):
        info("Aborted; nothing was deleted.")
        return
    delete_profile(name)
    ok(f"Deleted profile {name!r}.")


@profiles_app.command("apply")
def apply(
    name: str = typer.Argument(..., help="Profile to apply."),
    instance: str = typer.Argument(..., help="Instance to overlay the profile onto."),
) -> None:
    """Overlay a profile's variables onto an instance's ``.env``."""
    profile = _resolve_profile(name)
    try:
        inst = get_instance(instance)
    except InstanceNotFoundError as exc:
        error(f"Instance {instance!r} not found. Run `mad list` to see available instances.")
        raise typer.Exit(1) from exc

    applied = 0
    for key in profile.keys():  # noqa: SIM118 — EnvFile.keys() is its contract API
        value = profile.get(key)
        if value is not None:
            inst.env.set(key, value)
            applied += 1
    inst.env.save()

    ok(f"Applied {applied} variable(s) from profile {name!r} to instance {inst.name!r}.")
    info(f"Restart the instance to apply: mad restart {inst.name}")
