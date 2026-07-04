"""``mad start|stop|restart|status|logs|shell [INSTANCE]`` — container lifecycle.

``INSTANCE`` is optional: when omitted it resolves to the single configured
instance (``default_instance``). With zero instances the user is pointed at
``mad install``; with several, the ambiguity is reported so they name one.
"""

import typer

from mad_cli.core.compose import ComposeRunner
from mad_cli.core.instance import (
    Instance,
    InstanceNotFoundError,
    default_instance,
    discover_instances,
    get_instance,
)
from mad_cli.ui.console import console, error, header, info, ok, run_step, warn


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
    error(f"Multiple instances exist ({names}). Name one, e.g. `mad status <INSTANCE>`.")
    raise typer.Exit(1)


def _resolve_runner(name: str | None) -> tuple[Instance, ComposeRunner]:
    instance = _resolve_instance(name)
    return instance, ComposeRunner(instance)


def _url(instance: Instance) -> str | None:
    port = instance.host_port
    return f"http://localhost:{port}" if port is not None else None


def start(
    instance: str | None = typer.Argument(
        None, help="Instance name (optional when exactly one instance exists)."
    ),
) -> None:
    """Build if needed, start the instance, and wait for it to become healthy."""
    inst, runner = _resolve_runner(instance)
    header(f"Starting {inst.name}")
    run_step("Building and starting…", lambda: runner.up(build=True))
    healthy = run_step("Waiting for health…", runner.wait_healthy)
    url = _url(inst)
    if healthy:
        ok(f"{inst.name} is up — {url}" if url else f"{inst.name} is up.")
    else:
        warn(f"{inst.name} started but is not healthy yet. Check `mad status` and `mad logs`.")


def stop(
    instance: str | None = typer.Argument(
        None, help="Instance name (optional when exactly one instance exists)."
    ),
) -> None:
    """Stop the instance and remove its containers."""
    inst, runner = _resolve_runner(instance)
    run_step(f"Stopping {inst.name}…", runner.down)
    ok(f"{inst.name} stopped.")


def restart(
    instance: str | None = typer.Argument(
        None, help="Instance name (optional when exactly one instance exists)."
    ),
) -> None:
    """Restart the instance's containers."""
    inst, runner = _resolve_runner(instance)
    run_step(f"Restarting {inst.name}…", runner.restart)
    ok(f"{inst.name} restarted.")


def status(
    instance: str | None = typer.Argument(
        None, help="Instance name (optional when exactly one instance exists)."
    ),
) -> None:
    """Show container state, a health summary and the instance URL."""
    inst, runner = _resolve_runner(instance)
    header(f"Status — {inst.name}")
    out = runner.ps()
    if isinstance(out, str) and out.strip():
        console.print(out)
    lowered = out.lower() if isinstance(out, str) else ""
    if "unhealthy" in lowered:
        health = "unhealthy"
    elif "healthy" in lowered:
        health = "healthy"
    elif "running" in lowered or " up " in f" {lowered} ":
        health = "running"
    else:
        health = "not running"
    info(f"Health: {health}")
    url = _url(inst)
    if url:
        info(f"URL: {url}")


def logs(
    instance: str | None = typer.Argument(
        None, help="Instance name (optional when exactly one instance exists)."
    ),
) -> None:
    """Follow the instance's container logs."""
    _, runner = _resolve_runner(instance)
    runner.logs(follow=True)


def shell(
    instance: str | None = typer.Argument(
        None, help="Instance name (optional when exactly one instance exists)."
    ),
) -> None:
    """Open an interactive shell inside the running container."""
    _, runner = _resolve_runner(instance)
    runner.shell()
