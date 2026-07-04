"""``mad list``, ``mad info NAME`` and ``mad adopt`` — instance inventory and migration."""

import typer
from rich.panel import Panel
from rich.table import Table

from mad_cli.commands._common import is_secret_key
from mad_cli.core.compose import ComposeRunner
from mad_cli.core.instance import Instance, InstanceNotFoundError, discover_instances, get_instance
from mad_cli.core.keyspec import mask
from mad_cli.core.paths import instance_dir
from mad_cli.ui.console import console, error, header, info, ok, warn
from mad_cli.ui.prompts import confirm

# Config files that make up a legacy single-instance layout and move together on adopt.
_ADOPT_FILES = ("compose.yml", ".env", "Dockerfile", "entrypoint.sh")


def _state_health(instance: Instance) -> tuple[str, str]:
    """Best-effort ``(state, health)`` parsed from ``docker compose ps``.

    Health is read from the ``ps`` text (``(healthy)`` / ``(unhealthy)``) rather than
    ``wait_healthy`` because the latter blocks/polls until healthy — unsuitable for a
    read-only listing. When ``ps`` carries no health token (older engines, a stopped
    container, or a service without a healthcheck) health degrades to ``"-"``, and any
    failure to reach Docker leaves state ``"unknown"`` so the table still renders.
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


def list_() -> None:
    """List configured instances with their port, state, health and pinned version.

    ``State``/``Health`` are best-effort (see :func:`_state_health`); ``Version`` is the
    pinned ``MAD_VERSION`` from the .env, or ``latest`` when it tracks the latest release.
    """
    instances = discover_instances()
    if not instances:
        info("No instances yet. Run `mad install` to create one.")
        return

    table = Table(title="mad instances")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Port")
    table.add_column("State")
    table.add_column("Health")
    table.add_column("Version")
    for inst in instances:
        label = f"{inst.name} (legacy)" if getattr(inst, "legacy", False) else inst.name
        port = inst.host_port
        state, health = _state_health(inst)
        table.add_row(
            label,
            str(port) if port is not None else "-",
            state,
            health,
            inst.version_pin or "latest",
        )
    console.print(table)


def adopt() -> None:
    """Migrate the legacy single-instance layout into ``instances/<name>/``.

    The old layout kept ``compose.yml`` / ``.env`` / ``Dockerfile`` / ``entrypoint.sh``
    directly under the config root; the modern layout stores them per instance. This
    moves those files and nothing else — the instance's data (``MAD_DATA_PATH``) stays
    put. Because the Compose project name is derived from the layout, a still-running
    legacy container should be stopped with the old compose file first (see the warning).
    """
    legacy = next((inst for inst in discover_instances() if getattr(inst, "legacy", False)), None)
    if legacy is None:
        info("Nothing to adopt — no legacy single-instance layout found.")
        return

    source = legacy.config_dir
    try:
        target = instance_dir(legacy.name)
    except ValueError as exc:
        error(f"Cannot adopt {legacy.name!r}: {exc}")
        raise typer.Exit(1) from exc

    movable = [name for name in _ADOPT_FILES if (source / name).exists()]

    header(f"Adopt legacy instance {legacy.name!r}")
    plan = Table(show_header=False, box=None, pad_edge=False)
    plan.add_column("from", style="bold cyan")
    plan.add_column("arrow")
    plan.add_column("to")
    for name in movable:
        plan.add_row(str(source / name), "→", str(target / name))
    console.print(plan)
    info("Data (MAD_DATA_PATH) is not moved — only the config files above are relocated.")
    warn(
        f"The Compose project name changes from the legacy layout to mad-{legacy.name}. "
        f"If the legacy container is still running, stop it first with "
        f"`docker compose -f {source / 'compose.yml'} down` (this command does not)."
    )

    if not confirm(f"Move {len(movable)} file(s) into {target}?", default=True):
        info("Adoption cancelled.")
        return

    target.mkdir(parents=True, exist_ok=True)
    for name in movable:
        (source / name).rename(target / name)
    ok(f"Adopted {legacy.name!r} → {target}")


def info_cmd(name: str = typer.Argument(..., help="Instance name.")) -> None:
    """Show an instance's paths and its .env values (secrets masked)."""
    try:
        instance = get_instance(name)
    except InstanceNotFoundError as exc:
        error(f"Instance {name!r} not found. Run `mad list` to see available instances.")
        raise typer.Exit(1) from exc

    paths = Table(show_header=False, box=None, pad_edge=False)
    paths.add_column("key", style="bold cyan", no_wrap=True)
    paths.add_column("value")
    paths.add_row("Config dir", str(instance.config_dir))
    paths.add_row("Compose file", str(instance.compose_file))
    paths.add_row("Data path", str(instance.data_path) if instance.data_path else "-")
    console.print(
        Panel(paths, title=f"Instance {instance.name}", border_style="cyan", expand=False)
    )

    env = instance.env
    env_table = Table(title=".env")
    env_table.add_column("Key", style="bold", no_wrap=True)
    env_table.add_column("Value")
    for key in env.keys():  # noqa: SIM118 — EnvFile is not a dict; .keys() is its contract API
        value = env.get(key) or ""
        shown = mask(value) if value and is_secret_key(key) else value
        env_table.add_row(key, shown)
    console.print(env_table)
