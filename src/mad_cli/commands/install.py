"""``mad install`` — guided install / reconfiguration of a mad-edge instance.

Thin adapter over :func:`mad_cli.core.usecases.install.install`: this module owns
the interactive collection (each parameter has a flag that skips its prompt),
the Docker preflight, and the masked summary; the use case owns assembling the
``.env``, rendering the files, creating the data dirs and writing the Claude
credentials. Re-running against an existing instance pre-fills from its ``.env``.
"""

import os
import platform
import sys
from collections.abc import Callable
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from mad_cli.core.docker_check import check_docker, install_docker_linux
from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import Instance, InstanceNotFoundError, get_instance
from mad_cli.core.keyspec import BUILTIN_KEYS, mask
from mad_cli.core.profiles import ProfileNotFoundError, load_profile
from mad_cli.core.templates import EDGE_PACKAGE
from mad_cli.core.usecases import install as uc
from mad_cli.core.usecases import lifecycle as uc_lifecycle
from mad_cli.core.usecases.errors import UseCaseError
from mad_cli.core.usecases.install import (
    InstallParams,
    validate_name,
    validate_port,
    validate_retention,
    validate_timeout,
)
from mad_cli.ui.console import console, error, header, info, ok, run_step, warn
from mad_cli.ui.prompts import PromptRequiredError, ask, confirm


class _MissingValue(Exception):
    """A required value was not supplied and we cannot interactively prompt."""

    def __init__(self, flag: str) -> None:
        super().__init__(flag)
        self.flag = flag


class _KeyError(Exception):
    """An ``--set-key`` / extra-key entry could not be applied (bad id or value)."""


# Module-level singleton for the repeatable --set-key option (a mutable-typed
# default may not be an inline call — see flake8-bugbear B008).
_SET_KEY_OPTION = typer.Option(
    None,
    "--set-key",
    metavar="ID=VALUE",
    help=(
        "Extra API key to store, ID=VALUE (repeatable). ID is a builtin "
        "(deepseek, linear, opencode, github, anthropic) or a custom VAR name."
    ),
)


def _split_set_key(item: str) -> tuple[str, str]:
    """Split an ``ID=VALUE`` --set-key entry, or raise :class:`_KeyError`."""
    ident, sep, value = item.partition("=")
    if not sep:
        raise _KeyError(f"invalid --set-key {item!r}: expected ID=VALUE.")
    return ident.strip(), value


def _apply_key(env: EnvFile, ident: str, value: str, applied: list[str]) -> None:
    """Write a builtin (fanned out) or custom key into ``env`` (a scratch overlay).

    Appends every env var it touched to ``applied``. Rejects ``claude-oauth`` — it
    has its own ``--claude-token`` flag because it also materialises the container
    credentials file — and raises :class:`_KeyError` on a bad id so the caller
    decides whether to abort (flags) or re-prompt (loop).
    """
    spec = BUILTIN_KEYS.get(ident)
    if spec is not None and spec.writes_claude_credentials:
        raise _KeyError(
            f"{ident!r} cannot be set with --set-key; use --claude-token "
            "(it also writes the container credentials file)."
        )
    try:
        applied.extend(uc.apply_extra_key(env, ident, value))
    except UseCaseError as exc:
        raise _KeyError(str(exc)) from exc


def _prompt_extra_keys(env: EnvFile, applied: list[str]) -> None:
    """Interactive mini-loop to add extra API keys after the main credentials."""
    if not confirm(
        "Configure additional API keys now? (deepseek, linear, opencode, or custom)",
        default=False,
    ):
        return
    while True:
        ident = ask("Key id (deepseek, linear, opencode) or a custom VAR name").strip()
        if not ident:
            break
        value = ask(f"Value for {ident}", secret=True)
        try:
            _apply_key(env, ident, value, applied)
        except _KeyError as exc:
            warn(str(exc))
            continue
        if not confirm("Add another?", default=False):
            break


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


def _print_summary(result: uc.InstallResult, *, extra_key_vars: list[str]) -> None:
    env = result.env
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("key", style="bold cyan", no_wrap=True)
    table.add_column("value")
    table.add_row("Instance", result.name)
    table.add_row("Port", str(result.port))
    table.add_row("Data path", str(result.data_dir))
    table.add_row("Sessions", str(result.data_dir / result.name / "sessions"))
    table.add_row("Timeout", f"{result.timeout_s}s")
    retention = env.get("MAD_SESSIONS_RETENTION_DAYS")
    table.add_row("Session retention", f"{retention} days" if retention else "keep forever")
    table.add_row("Config dir", str(result.config_dir))

    shown: set[str] = set()
    for key in ("GITHUB_TOKEN", "_CLAUDE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
        value = env.get(key)
        if value:
            table.add_row(key, mask(value))
        shown.add(key)
    shown.add("GH_TOKEN")  # fanned out from GITHUB_TOKEN; shown once above
    for var in extra_key_vars:
        if var in shown:
            continue
        shown.add(var)
        value = env.get(var)
        if value:
            table.add_row(var, mask(value))

    mcp = env.get("MAD_MCP_ALLOWED_HOSTS")
    table.add_row("MCP allowed hosts", mcp if mcp else "disabled")
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
    anthropic_api_key: str | None = typer.Option(
        None,
        "--anthropic-api-key",
        help="Anthropic API key (optional — alternative billing to the Claude OAuth token).",
    ),
    set_key: list[str] | None = _SET_KEY_OPTION,
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Named profile whose values seed the wizard defaults (flags still win).",
    ),
    retention_days: str | None = typer.Option(
        None,
        "--retention-days",
        help="Session log retention in days, >= 1 (omit to keep session logs forever).",
    ),
    mcp_allowed_hosts: str | None = typer.Option(
        None,
        "--mcp-allowed-hosts",
        help="MCP allowed hosts for DNS-rebinding protection (comma-separated).",
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
            validator=validate_name,
        )

        existing: Instance | None
        try:
            existing = get_instance(name_value)
        except InstanceNotFoundError:
            existing = None
        if existing is not None:
            warn(f"Instance {name_value!r} already exists — values pre-filled from its .env.")

        # Default layer feeding every prompt: an existing instance's .env
        # pre-fills a reconfiguration, then a --profile overlays its reusable
        # credentials/tuning on top (a profile never carries instance identity).
        # Explicit flags still win — they short-circuit `prior` in `_collect`.
        defaults = EnvFile.empty()
        if existing is not None:
            for key in existing.env.keys():  # noqa: SIM118 — EnvFile.keys() is its API
                value = existing.env.get(key)
                if value is not None:
                    defaults.set(key, value)
        if profile is not None:
            try:
                profile_env = load_profile(profile)
            except ProfileNotFoundError as exc:
                error(f"Profile {profile!r} not found. Run `mad profiles list` to see profiles.")
                raise typer.Exit(1) from exc
            for key in profile_env.keys():  # noqa: SIM118 — EnvFile.keys() is its API
                value = profile_env.get(key)
                if value is not None:
                    defaults.set(key, value)

        def prior(key: str, fallback: str | None) -> str | None:
            current = defaults.get(key)
            if current:
                return current
            return fallback

        port_value = _collect(
            interactive=interactive,
            flag=port,
            flag_name="--port",
            prompt="Host port",
            default=prior("MAD_HOST_PORT", "8080"),
            validator=validate_port,
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
            validator=validate_timeout,
        )
        retention_value = _collect(
            interactive=interactive,
            flag=retention_days,
            flag_name="--retention-days",
            prompt="Session log retention in days (empty = keep forever)",
            default=prior("MAD_SESSIONS_RETENTION_DAYS", ""),
            validator=validate_retention,
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
        anthropic_value = _collect(
            interactive=interactive,
            flag=anthropic_api_key,
            flag_name="--anthropic-api-key",
            prompt=(
                "Anthropic API key (optional — alternative billing to the Claude "
                "OAuth token, Enter to skip)"
            ),
            default=prior("ANTHROPIC_API_KEY", ""),
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
        mcp_hosts_value = _collect(
            interactive=interactive,
            flag=mcp_allowed_hosts,
            flag_name="--mcp-allowed-hosts",
            prompt=(
                "MCP allowed hosts for DNS-rebinding protection "
                "(comma-separated, Enter to leave disabled)"
            ),
            default=prior("MAD_MCP_ALLOWED_HOSTS", None),
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

    # Extra API keys: --set-key flags first (abort on a bad entry), then the
    # interactive mini-loop (re-prompts on a bad entry). Collected into a scratch
    # env overlay (builtins fanned out), then flattened to {VAR: value}.
    scratch = EnvFile.empty()
    extra_key_vars: list[str] = []
    try:
        for item in set_key or []:
            ident, value = _split_set_key(item)
            _apply_key(scratch, ident, value, extra_key_vars)
    except _KeyError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc
    if interactive:
        _prompt_extra_keys(scratch, extra_key_vars)
    extra_env = {var: scratch.get(var) or "" for var in scratch.keys()}  # noqa: SIM118

    params = InstallParams(
        name=name_value,
        port=int(port_value),
        data_path=Path(data_value).expanduser(),
        timeout_s=int(timeout_value),
        github_token=github_value,
        puid=_host_id("getuid"),
        pgid=_host_id("getgid"),
        git_name=git_name_value,
        git_email=git_email_value,
        claude_token=claude_value,
        anthropic_api_key=anthropic_value,
        extra_env=extra_env,
        retention_days=retention_value,
        mcp_allowed_hosts=mcp_hosts_value or "",
        edge_package=edge_package_value,
        edge_version=edge_version_value,
        start=False,  # the CLI starts separately below (so the summary prints first)
    )

    header("Writing configuration")
    try:
        result = uc.install(params)
    except UseCaseError as exc:
        error(str(exc))
        raise typer.Exit(1) from exc
    ok(f"Instance files → {result.config_dir}")
    if result.claude_credentials_path is not None:
        ok(f"Claude credentials → {result.claude_credentials_path}")
    else:
        warn(f"Claude credentials directory left empty: {result.claude_dir}")

    _print_summary(result, extra_key_vars=extra_key_vars)

    if no_start:
        hint = "mad start" if name_value == "default" else f"mad start {name_value}"
        info(f"Configuration written. Start the container later with `{hint}` (--no-start).")
        return

    instance = Instance(name=result.name, config_dir=result.config_dir, env=result.env)
    header("Starting mad-edge")
    res = run_step("Building and starting the container…", lambda: uc_lifecycle.start(instance))
    if res.healthy:
        ok(f"Mad is up — API/MCP on {res.url}" if res.url else "Mad is up.")
    else:
        warn("Container started but is not healthy yet. Check `mad status` and `mad logs`.")
