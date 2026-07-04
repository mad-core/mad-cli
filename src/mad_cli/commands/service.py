"""``mad serve`` and ``mad service install|uninstall|status|update`` — service mode.

``serve`` runs the HTTP API in the foreground (uvicorn). ``service`` manages a
boot-persistent background service: a systemd **user** unit on Linux, a launchd
LaunchAgent on macOS. When the ``server`` extra is not importable, ``service
install`` auto-provisions a dedicated venv under ``config_root()/server-venv`` and
points the unit at it — the base CLI never needs FastAPI installed.

Thin adapter over :mod:`mad_cli.core.usecases.service`. Activating the unit
(``systemctl`` / ``launchctl``) happens only for a real install; ``--render-to``
writes the file and touches nothing on the live system (used by tests and the E2E).
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import typer

from mad_cli import __version__
from mad_cli.commands._adapt import fail
from mad_cli.core.paths import config_root
from mad_cli.core.usecases import service as uc
from mad_cli.core.usecases.errors import UseCaseError
from mad_cli.ui.console import error, header, info, ok, warn

service_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Install/manage the mad HTTP API as a boot-persistent background service.",
)

_HOST_OPTION = typer.Option(uc.DEFAULT_HOST, "--host", help="Bind address (default: 127.0.0.1).")
_PORT_OPTION = typer.Option(uc.DEFAULT_PORT, "--port", help="Bind port (default: 7373).")
_WHEEL_OPTION = typer.Option(
    None,
    "--wheel",
    "--from",
    help="Provision the server venv from this local wheel/sdist instead of PyPI.",
)
_RENDER_TO_OPTION = typer.Option(
    None,
    "--render-to",
    help="Write the unit/plist to PATH and stop — do not touch systemctl/launchctl.",
)


def _warn_public_bind(host: str) -> None:
    if uc.is_loopback(host):
        return
    bar = "!" * 68
    warn(bar)
    warn(f"Binding to {host} exposes the mad API BEYOND localhost.")
    warn("Anyone who can reach this address and holds the bearer token can control")
    warn("your instances (start/stop, config, keys). Put it behind a firewall/VPN.")
    warn(bar)


def _platform() -> str:
    return platform.system().lower()


# ── mad serve ─────────────────────────────────────────────────────────────────
def serve(host: str = _HOST_OPTION, port: int = _PORT_OPTION) -> None:
    """Run the HTTP API in the foreground (Ctrl-C to stop)."""
    uc.ensure_api_token()  # create the token file on first run
    _warn_public_bind(host)

    if uc.server_deps_available():
        import uvicorn  # noqa: PLC0415 — optional dependency, imported on demand

        from mad_cli.server import create_app  # lazy: only when the extra is present

        app = create_app()
        header("mad API")
        info(f"Listening on http://{host}:{port}")
        info(f"Bearer token: {uc.api_token_path()} (send as `Authorization: Bearer <token>`)")
        uvicorn.run(app, host=host, port=port, log_level="info")
        return

    if uc.server_venv_exists():
        argv = uc.serve_argv([str(uc.server_venv_mad())], host, port)
        info("The server extra is not in this environment — handing off to the dedicated venv.")
        os.execv(argv[0], argv)  # replace this process; never returns
        return

    error(
        "The HTTP API needs the 'server' extra. Install it with "
        "`pip install 'mad-cli[server]'`, or run `mad service install` "
        "(it auto-provisions a dedicated environment for you)."
    )
    raise typer.Exit(1)


# ── mad service install / uninstall / status / update ─────────────────────────
def _activate(platform_name: str, unit_path: Path) -> None:
    """Enable + start the freshly installed service (real installs only)."""
    if platform_name == "linux":
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", uc.SYSTEMD_UNIT_NAME], check=True
            )
        except (OSError, subprocess.SubprocessError) as exc:
            warn(f"Could not activate the systemd unit automatically: {exc}")
            return
        ok("Enabled and started (systemctl --user enable --now).")
        info(
            "To survive logout/reboot without an active session, run: loginctl enable-linger $USER"
        )
    elif platform_name == "darwin":
        try:
            subprocess.run(["launchctl", "load", str(unit_path)], check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            warn(f"Could not load the LaunchAgent automatically: {exc}")
            return
        ok("Loaded (launchctl load).")


@service_app.command("install")
def install(
    host: str = _HOST_OPTION,
    port: int = _PORT_OPTION,
    wheel: Path | None = _WHEEL_OPTION,
    render_to: Path | None = _RENDER_TO_OPTION,
) -> None:
    """Render the service file (and provision the server venv if needed)."""
    uc.ensure_api_token()
    system = _platform()

    header("Provisioning the server runtime")
    try:
        launcher, bootstrapped = uc.ensure_server_runtime(wheel=wheel)
    except UseCaseError as exc:
        fail(exc)
    if bootstrapped:
        ok(f"Server venv ready → {uc.server_venv_dir()}")
    else:
        info("Using the current environment's `mad` (the server extra is already installed).")

    exec_args = uc.serve_argv(launcher, host, port)
    try:
        rendered = uc.render_service(platform=system, exec_args=exec_args, config_dir=config_root())
    except UseCaseError as exc:
        fail(exc)

    target = render_to if render_to is not None else rendered.default_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered.content, encoding="utf-8")
    ok(f"Service file → {target}")

    if render_to is not None:
        info("Rendered only (--render-to) — systemctl/launchctl were not touched.")
        return
    _activate(rendered.platform, rendered.default_path)


@service_app.command("uninstall")
def uninstall() -> None:
    """Stop and remove the installed service file."""
    system = _platform()
    try:
        rendered_path = uc.systemd_unit_path() if system == "linux" else uc.launchd_plist_path()
    except Exception:  # noqa: BLE001 - defensive; unsupported platform
        info("No supported service manager on this platform.")
        return
    if not rendered_path.exists():
        info("No service file installed; nothing to remove.")
        return
    if system == "linux":
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", uc.SYSTEMD_UNIT_NAME], check=False
            )
        except (OSError, subprocess.SubprocessError) as exc:
            warn(f"Could not stop the unit: {exc}")
    elif system == "darwin":
        try:
            subprocess.run(["launchctl", "unload", str(rendered_path)], check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            warn(f"Could not unload the LaunchAgent: {exc}")
    rendered_path.unlink()
    ok(f"Removed {rendered_path}. The server venv (if any) was left in place.")


@service_app.command("status")
def status() -> None:
    """Report the service file, the server venv and version alignment."""
    system = _platform()
    path = uc.systemd_unit_path() if system == "linux" else uc.launchd_plist_path()
    header("mad service status")
    info(f"Platform: {system}")
    info(f"Service file: {path} ({'present' if path.exists() else 'absent'})")

    if uc.server_venv_exists():
        venv_version = uc.server_venv_version()
        ok(f"Server venv: {uc.server_venv_dir()} (mad-cli {venv_version or 'unknown'})")
        if venv_version is not None and venv_version != __version__:
            warn(
                f"Server venv runs mad-cli {venv_version} but this CLI is {__version__}. "
                "Run `mad service update` to realign."
            )
    elif uc.server_deps_available():
        info("Server venv: not provisioned (the current environment has the server extra).")
    else:
        info("Server venv: not provisioned. `mad service install` will create one.")


@service_app.command("update")
def update(wheel: Path | None = _WHEEL_OPTION) -> None:
    """Reinstall ``mad-cli[server]`` into the server venv at the CLI's version."""
    header("Updating the server venv")
    try:
        uc.bootstrap_server_venv(wheel=wheel)
    except UseCaseError as exc:
        fail(exc)
    ok(f"Server venv realigned to mad-cli {__version__} → {uc.server_venv_dir()}")
