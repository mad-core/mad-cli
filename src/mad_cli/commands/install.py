"""``mad install`` — guided install / reconfiguration of a mad-edge instance.

This is an English port of ``mad/scripts/configure.sh``: it checks Docker,
collects the same parameters (each with a CLI flag that skips its prompt),
renders the instance files through ``mad_cli.core`` and optionally starts the
container. Re-running against an existing instance pre-fills values from its
``.env`` (idempotent reconfiguration).
"""

import os
import platform
import re
import sys
from collections.abc import Callable
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from mad_cli.core.claude_creds import write_claude_credentials
from mad_cli.core.compose import ComposeRunner
from mad_cli.core.docker_check import check_docker, install_docker_linux
from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import Instance, InstanceNotFoundError, get_instance
from mad_cli.core.keyspec import mask
from mad_cli.core.paths import instance_dir
from mad_cli.core.templates import EDGE_PACKAGE, RenderContext, write_instance_files
from mad_cli.ui.console import console, error, header, info, ok, run_step, warn
from mad_cli.ui.prompts import PromptRequiredError, ask, confirm


class _MissingValue(Exception):
    """A required value was not supplied and we cannot interactively prompt."""

    def __init__(self, flag: str) -> None:
        super().__init__(flag)
        self.flag = flag


_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")


def _validate_name(value: str) -> str:
    value = value.strip()
    if not _NAME_RE.fullmatch(value):
        raise ValueError(
            f"invalid instance name {value!r}: use lowercase letters, digits and "
            "hyphens, starting with a letter or digit"
        )
    return value


def _validate_port(value: str) -> str:
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"invalid port {value!r}: must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid port {value!r}: must be between 1 and 65535")
    return str(port)


def _validate_timeout(value: str) -> str:
    try:
        seconds = int(value)
    except ValueError:
        raise ValueError(
            f"invalid timeout {value!r}: must be an integer number of seconds"
        ) from None
    if seconds <= 0:
        raise ValueError(f"invalid timeout {value!r}: must be a positive integer")
    return str(seconds)


def _interactive(assume_yes: bool) -> bool:
    """True only when we may block on a prompt: not --yes and stdin is a TTY."""
    if assume_yes:
        return False
    try:
        return sys.stdin.isatty()
    except (ValueError, OSError):
        return False


def _host_id(getter_name: str) -> int:
    """os.getuid/os.getgid, or 1000 on platforms that lack them (Windows)."""
    getter = getattr(os, getter_name, None)
    return getter() if getter is not None else 1000


def _collect(
    *,
    interactive: bool,
    flag: str | None,
    flag_name: str,
    prompt: str,
    default: str | None = None,
    secret: bool = False,
    validator: Callable[[str], str] | None = None,
    required: bool = False,
) -> str:
    """Resolve a single value from its flag, an interactive prompt, or a default."""
    if flag is not None:
        return validator(flag) if validator is not None else flag
    if interactive:
        try:
            return ask(prompt, default=default, secret=secret, validator=validator)
        except PromptRequiredError as exc:  # pragma: no cover - guarded by isatty()
            raise _MissingValue(flag_name) from exc
    if default is None:
        if required:
            raise _MissingValue(flag_name)
        return ""
    return validator(default) if validator is not None else default


def _ensure_docker(*, assume_yes: bool) -> None:
    header("Checking Docker")
    status = check_docker()
    if not status.docker_present:
        if platform.system() == "Linux":
            if not confirm("Docker was not found. Install it now?", default=True):
                error("Docker is required. Install it from https://docs.docker.com/engine/install/")
                raise typer.Exit(1)
            if not install_docker_linux(assume_yes=assume_yes):
                error("Docker installation did not complete. Re-run once Docker is available.")
                raise typer.Exit(1)
            status = check_docker()
        else:
            error(
                "Docker was not found. Install Docker Desktop "
                "(https://docs.docker.com/desktop/) and re-run `mad install`."
            )
            raise typer.Exit(1)
    if not status.docker_present:
        error("Docker is still not available after installation.")
        raise typer.Exit(1)
    if not status.daemon_running:
        error("The Docker daemon is not running. Start Docker and re-run `mad install`.")
        raise typer.Exit(1)
    if not status.compose_v2:
        error(
            "Docker Compose v2 was not found. Install it: https://docs.docker.com/compose/install/"
        )
        raise typer.Exit(1)
    ok(f"Docker ready — {status.version}" if status.version else "Docker ready")


def _print_summary(
    *,
    env: EnvFile,
    name: str,
    port: int,
    data_dir: Path,
    timeout: int,
    config_dir: Path,
) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("key", style="bold cyan", no_wrap=True)
    table.add_column("value")
    table.add_row("Instance", name)
    table.add_row("Port", str(port))
    table.add_row("Data path", str(data_dir))
    table.add_row("Timeout", f"{timeout}s")
    table.add_row("Config dir", str(config_dir))
    for key in ("GITHUB_TOKEN", "_CLAUDE_OAUTH_TOKEN"):
        value = env.get(key)
        if value:
            table.add_row(key, mask(value))
    console.print(Panel(table, title="Configuration complete", border_style="green", expand=False))


def install(
    name: str | None = typer.Option(None, "--name", help="Instance name (default: default)."),
    port: str | None = typer.Option(None, "--port", help="Host port to expose (default: 8080)."),
    data_path: str | None = typer.Option(
        None, "--data-path", help="Host data directory (default: ~/mad-data)."
    ),
    timeout: str | None = typer.Option(
        None, "--timeout", help="Agent wall-clock timeout in seconds (default: 600)."
    ),
    github_token: str | None = typer.Option(
        None, "--github-token", help="GitHub token for agent clones, pushes and PRs."
    ),
    git_name: str | None = typer.Option(
        None, "--git-name", help="Git author/committer name for the agent's commits."
    ),
    git_email: str | None = typer.Option(
        None, "--git-email", help="Git author/committer email for the agent's commits."
    ),
    claude_token: str | None = typer.Option(
        None,
        "--claude-token",
        help="Claude OAuth token — run `claude setup-token` on any machine with Claude Code.",
    ),
    edge_package: str | None = typer.Option(
        None, "--edge-package", hidden=True, help="Override the mad-edge package name."
    ),
    edge_version: str | None = typer.Option(
        None, "--edge-version", help="Pin the mad-edge version (blank = latest)."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Non-interactive: use flags and defaults, never prompt."
    ),
    no_start: bool = typer.Option(
        False, "--no-start", help="Write configuration but do not start the container."
    ),
) -> None:
    """Install or reconfigure a mad-edge instance."""
    header("Mad installer")
    info("Writes an instance configuration and, unless --no-start, launches its container.")

    _ensure_docker(assume_yes=yes)

    interactive = _interactive(yes)

    try:
        name_value = _collect(
            interactive=interactive,
            flag=name,
            flag_name="--name",
            prompt="Instance name",
            default="default",
            validator=_validate_name,
        )

        existing: Instance | None
        try:
            existing = get_instance(name_value)
        except InstanceNotFoundError:
            existing = None
        if existing is not None:
            warn(f"Instance {name_value!r} already exists — values pre-filled from its .env.")

        def prior(key: str, fallback: str | None) -> str | None:
            if existing is not None:
                current = existing.env.get(key)
                if current:
                    return current
            return fallback

        port_value = _collect(
            interactive=interactive,
            flag=port,
            flag_name="--port",
            prompt="Host port",
            default=prior("MAD_HOST_PORT", "8080"),
            validator=_validate_port,
        )
        data_value = _collect(
            interactive=interactive,
            flag=data_path,
            flag_name="--data-path",
            prompt="Host data path",
            default=prior("MAD_DATA_PATH", str(Path.home() / "mad-data")),
        )
        timeout_value = _collect(
            interactive=interactive,
            flag=timeout,
            flag_name="--timeout",
            prompt="Agent timeout (seconds)",
            default=prior("MAD_AGENT_TIMEOUT_S", "600"),
            validator=_validate_timeout,
        )
        github_value = _collect(
            interactive=interactive,
            flag=github_token,
            flag_name="--github-token",
            prompt="GitHub token (used for agent clones, pushes and PRs)",
            default=prior("GITHUB_TOKEN", None),
            secret=True,
            required=True,
        )
        git_name_value = _collect(
            interactive=interactive,
            flag=git_name,
            flag_name="--git-name",
            prompt="Git author name",
            default=prior("GIT_AUTHOR_NAME", ""),
        )
        git_email_value = _collect(
            interactive=interactive,
            flag=git_email,
            flag_name="--git-email",
            prompt="Git author email",
            default=prior("GIT_AUTHOR_EMAIL", ""),
        )
        claude_value = _collect(
            interactive=interactive,
            flag=claude_token,
            flag_name="--claude-token",
            prompt="Claude OAuth token (run `claude setup-token` and paste it here)",
            default=prior("_CLAUDE_OAUTH_TOKEN", ""),
            secret=True,
        )
        edge_package_value = _collect(
            interactive=interactive,
            flag=edge_package,
            flag_name="--edge-package",
            prompt="mad-edge package",
            default=EDGE_PACKAGE,
        )
        edge_version_value = _collect(
            interactive=interactive,
            flag=edge_version,
            flag_name="--edge-version",
            prompt="mad-edge version pin (blank = latest)",
            default=prior("MAD_VERSION", ""),
        )
    except _MissingValue as exc:
        error(
            f"Missing required value: provide {exc.flag} "
            "(required in --yes / non-interactive mode)."
        )
        raise typer.Exit(1) from exc

    if not git_name_value or not git_email_value:
        warn(
            "No git identity set — the agent's commits may be rejected. Use --git-name/--git-email."
        )
    if not claude_value:
        warn("No Claude token set — the container starts but agents cannot authenticate.")

    data_dir = Path(data_value).expanduser()
    port_int = int(port_value)
    timeout_int = int(timeout_value)
    puid = _host_id("getuid")
    pgid = _host_id("getgid")

    env = EnvFile.empty()
    env.set("MAD_INSTANCE", name_value)
    env.set("MAD_HOST_PORT", port_value)
    env.set("MAD_VERSION", edge_version_value)
    env.set("PUID", str(puid))
    env.set("PGID", str(pgid))
    env.set("MAD_DATA_PATH", str(data_dir))
    env.set("GITHUB_TOKEN", github_value)
    env.set("GH_TOKEN", github_value)
    env.set("GIT_AUTHOR_NAME", git_name_value)
    env.set("GIT_AUTHOR_EMAIL", git_email_value)
    env.set("GIT_COMMITTER_NAME", git_name_value)
    env.set("GIT_COMMITTER_EMAIL", git_email_value)
    env.set("MAD_AGENT_TIMEOUT_S", timeout_value)
    env.set("_CLAUDE_OAUTH_TOKEN", claude_value)

    ctx = RenderContext(
        instance=name_value,
        host_port=port_int,
        data_path=data_dir,
        timeout_s=timeout_int,
        puid=puid,
        pgid=pgid,
        edge_package=edge_package_value,
        edge_version=edge_version_value,
    )

    config_dir = instance_dir(name_value)
    header("Writing configuration")
    write_instance_files(config_dir, ctx, env)
    ok(f"Instance files → {config_dir}")

    instance_data = data_dir / name_value
    (instance_data / "workspaces").mkdir(parents=True, exist_ok=True)
    (instance_data / "aws").mkdir(parents=True, exist_ok=True)
    claude_dir = instance_data / "claude"
    if claude_value:
        creds = write_claude_credentials(claude_dir, claude_value)
        ok(f"Claude credentials → {creds}")
    else:
        claude_dir.mkdir(parents=True, exist_ok=True)
        warn(f"Claude credentials directory left empty: {claude_dir}")

    _print_summary(
        env=env,
        name=name_value,
        port=port_int,
        data_dir=data_dir,
        timeout=timeout_int,
        config_dir=config_dir,
    )

    if no_start:
        hint = "mad start" if name_value == "default" else f"mad start {name_value}"
        info(f"Configuration written. Start the container later with `{hint}` (--no-start).")
        return

    instance = Instance(name=name_value, config_dir=config_dir, env=env)
    runner = ComposeRunner(instance)
    header("Starting mad-edge")
    run_step("Building and starting the container…", lambda: runner.up(build=True))
    healthy = run_step("Waiting for the container to become healthy…", runner.wait_healthy)
    if healthy:
        ok(f"Mad is up — API/MCP on http://localhost:{port_int}")
    else:
        warn("Container started but is not healthy yet. Check `mad status` and `mad logs`.")
