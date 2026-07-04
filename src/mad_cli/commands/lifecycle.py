"""``mad start|stop|restart|status|logs|shell [INSTANCE]`` — container lifecycle.

Thin adapter over :mod:`mad_cli.core.usecases.lifecycle`. ``INSTANCE`` is optional:
when omitted it resolves to the single configured instance; with zero the user is
pointed at ``mad install``, with several the ambiguity is reported. ``logs`` and
``shell`` attach the caller's TTY and stay here (no HTTP equivalent).
"""

from __future__ import annotations

import typer

from mad_cli.commands._adapt import resolve_or_die
from mad_cli.core.compose import ComposeRunner
from mad_cli.core.usecases import lifecycle as uc
from mad_cli.ui.console import console, header, info, ok, run_step, warn

_INSTANCE_ARG = typer.Argument(
    None, help="Instance name (optional when exactly one instance exists)."
)


def start(instance: str | None = _INSTANCE_ARG) -> None:
    """Build if needed, start the instance, and wait for it to become healthy."""
    inst = resolve_or_die(instance)
    header(f"Starting {inst.name}")
    res = run_step("Building and starting…", lambda: uc.start(inst))
    if res.healthy:
        ok(f"{inst.name} is up — {res.url}" if res.url else f"{inst.name} is up.")
    else:
        warn(f"{inst.name} started but is not healthy yet. Check `mad status` and `mad logs`.")


def stop(instance: str | None = _INSTANCE_ARG) -> None:
    """Stop the instance and remove its containers."""
    inst = resolve_or_die(instance)
    run_step(f"Stopping {inst.name}…", lambda: uc.stop(inst))
    ok(f"{inst.name} stopped.")


def restart(instance: str | None = _INSTANCE_ARG) -> None:
    """Restart the instance's containers."""
    inst = resolve_or_die(instance)
    run_step(f"Restarting {inst.name}…", lambda: uc.restart(inst))
    ok(f"{inst.name} restarted.")


def status(instance: str | None = _INSTANCE_ARG) -> None:
    """Show container state, a health summary and the instance URL."""
    inst = resolve_or_die(instance)
    header(f"Status — {inst.name}")
    res = uc.status(inst)
    if res.ps_text.strip():
        console.print(res.ps_text)
    info(f"Health: {res.health}")
    if res.url:
        info(f"URL: {res.url}")


def logs(instance: str | None = _INSTANCE_ARG) -> None:
    """Follow the instance's container logs."""
    inst = resolve_or_die(instance)
    ComposeRunner(inst).logs(follow=True)


def shell(instance: str | None = _INSTANCE_ARG) -> None:
    """Open an interactive shell inside the running container."""
    inst = resolve_or_die(instance)
    ComposeRunner(inst).shell()
