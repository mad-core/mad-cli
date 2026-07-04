"""``mad list`` and ``mad info NAME`` — instance inventory."""

import typer
from rich.panel import Panel
from rich.table import Table

from mad_cli.commands._common import is_secret_key
from mad_cli.core.compose import ComposeRunner
from mad_cli.core.instance import Instance, InstanceNotFoundError, discover_instances, get_instance
from mad_cli.core.keyspec import mask
from mad_cli.ui.console import console, error, info


def _state(instance: Instance) -> str:
    """Best-effort container state from ``docker compose ps`` (``unknown`` on any failure)."""
    try:
        out = ComposeRunner(instance).ps()
    except Exception:  # docker missing/erroring — inventory must still render
        return "unknown"
    if not isinstance(out, str):
        return "unknown"
    lowered = out.lower()
    if "unhealthy" in lowered:
        return "unhealthy"
    if "healthy" in lowered:
        return "healthy"
    if "running" in lowered or " up " in f" {lowered} ":
        return "running"
    return "stopped"


def list_() -> None:
    """List configured instances with their port, data path and state."""
    instances = discover_instances()
    if not instances:
        info("No instances yet. Run `mad install` to create one.")
        return

    table = Table(title="mad instances")
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Port")
    table.add_column("Data path")
    table.add_column("State")
    for inst in instances:
        label = f"{inst.name} (legacy)" if getattr(inst, "legacy", False) else inst.name
        port = inst.host_port
        data = inst.data_path
        table.add_row(
            label,
            str(port) if port is not None else "-",
            str(data) if data is not None else "-",
            _state(inst),
        )
    console.print(table)


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
