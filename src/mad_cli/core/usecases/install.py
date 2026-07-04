"""Install / reconfigure use case: params -> .env -> files -> dirs -> (start).

The deterministic heart of ``mad install`` and ``POST /v1/instances``. Given a
fully-resolved :class:`InstallParams` (the CLI does the interactive collection and
Docker preflight; the API takes them from the request body), it assembles the
``.env``, renders the instance files, creates the data directories (including
``sessions/``), writes the Claude credentials file and, unless ``start`` is
false, builds and starts the container. No prompting, no Docker preflight, no
presentation — those belong to the adapters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from mad_cli.core.claude_creds import write_claude_credentials
from mad_cli.core.compose import ComposeRunner
from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import Instance
from mad_cli.core.keyspec import BUILTIN_KEYS
from mad_cli.core.paths import instance_dir
from mad_cli.core.templates import EDGE_PACKAGE, RenderContext, write_instance_files
from mad_cli.core.usecases.errors import ValidationError

_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
# A custom extra key is written verbatim; it must look like a shell env-var name.
_CUSTOM_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]*")


# ── validators (shared with the CLI's interactive prompts) ───────────────────
def validate_name(value: str) -> str:
    value = value.strip()
    if not _NAME_RE.fullmatch(value):
        raise ValidationError(
            f"invalid instance name {value!r}: use lowercase letters, digits and "
            "hyphens, starting with a letter or digit"
        )
    return value


def validate_port(value: str) -> str:
    try:
        port = int(value)
    except ValueError:
        raise ValidationError(f"invalid port {value!r}: must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValidationError(f"invalid port {value!r}: must be between 1 and 65535")
    return str(port)


def validate_timeout(value: str) -> str:
    try:
        seconds = int(value)
    except ValueError:
        raise ValidationError(f"invalid timeout {value!r}: must be an integer") from None
    if seconds <= 0:
        raise ValidationError(f"invalid timeout {value!r}: must be a positive integer")
    return str(seconds)


def validate_retention(value: str) -> str:
    """A retention: a positive integer number of days, or empty (keep forever)."""
    value = value.strip()
    if not value:
        return ""
    try:
        days = int(value)
    except ValueError:
        raise ValidationError(
            f"invalid retention {value!r}: must be a positive integer of days, or empty"
        ) from None
    if days < 1:
        raise ValidationError(
            f"invalid retention {value!r}: must be >= 1 (or empty to keep forever)"
        )
    return str(days)


def apply_extra_key(env: EnvFile, ident: str, value: str) -> list[str]:
    """Write a builtin (fanned out) or custom extra key into ``env``.

    Returns the env vars it touched. Rejects ``claude-oauth`` (it also
    materialises the credentials file — set it as the dedicated Claude token) and
    raises :class:`ValidationError` for an unknown id. The message is neutral; the
    CLI adds its ``--claude-token`` hint before delegating here.
    """
    spec = BUILTIN_KEYS.get(ident)
    if spec is not None:
        if spec.writes_claude_credentials:
            raise ValidationError(
                f"{ident!r} cannot be set as an extra key; provide the Claude token directly."
            )
        for var in spec.env_vars:
            env.set(var, value)
        return list(spec.env_vars)
    if _CUSTOM_KEY_RE.fullmatch(ident):
        env.set(ident, value)
        return [ident]
    raise ValidationError(
        f"unknown key {ident!r}: use a builtin id ({', '.join(BUILTIN_KEYS)}) "
        "or an env-var name matching [A-Z][A-Z0-9_]*."
    )


@dataclass
class InstallParams:
    """Fully-resolved install inputs (post prompting / request parsing)."""

    name: str
    port: int
    data_path: Path
    timeout_s: int
    github_token: str
    puid: int
    pgid: int
    git_name: str = ""
    git_email: str = ""
    claude_token: str = ""
    anthropic_api_key: str = ""
    # Extra API keys as a flat {ENV_VAR: value} overlay (already fanned out by the
    # adapter via :func:`apply_extra_key`); written verbatim after the base keys.
    extra_env: dict[str, str] = field(default_factory=dict)
    retention_days: str = ""  # "" = keep forever
    mcp_allowed_hosts: str = ""  # "" = disabled
    edge_package: str = EDGE_PACKAGE
    edge_version: str = ""
    start: bool = True


@dataclass(frozen=True)
class InstallResult:
    """Outcome of an install for the adapter to present."""

    name: str
    config_dir: Path
    data_dir: Path
    port: int
    timeout_s: int
    env: EnvFile
    extra_key_vars: list[str]
    claude_credentials_path: Path | None
    claude_dir: Path
    started: bool
    healthy: bool | None
    url: str | None


def build_env(params: InstallParams) -> tuple[EnvFile, list[str]]:
    """Assemble the ``.env`` for ``params``; return it and the extra-key vars.

    Split out so it can be unit-tested and reused; validates the extra keys,
    raising :class:`ValidationError` on a bad entry (before any file is written).
    """
    env = EnvFile.empty()
    env.set("MAD_INSTANCE", params.name)
    env.set("MAD_HOST_PORT", str(params.port))
    env.set("MAD_VERSION", params.edge_version)
    env.set("PUID", str(params.puid))
    env.set("PGID", str(params.pgid))
    env.set("MAD_DATA_PATH", str(params.data_path))
    env.set("GITHUB_TOKEN", params.github_token)
    env.set("GH_TOKEN", params.github_token)
    env.set("GIT_AUTHOR_NAME", params.git_name)
    env.set("GIT_AUTHOR_EMAIL", params.git_email)
    env.set("GIT_COMMITTER_NAME", params.git_name)
    env.set("GIT_COMMITTER_EMAIL", params.git_email)
    env.set("MAD_AGENT_TIMEOUT_S", str(params.timeout_s))
    env.set("_CLAUDE_OAUTH_TOKEN", params.claude_token)
    if params.anthropic_api_key:
        env.set("ANTHROPIC_API_KEY", params.anthropic_api_key)

    extra_vars: list[str] = []
    for var, value in params.extra_env.items():
        env.set(var, value)
        extra_vars.append(var)

    # Session-log retention: a value activates it; otherwise a documented,
    # inactive reference so the operator knows the knob exists (keep forever).
    if params.retention_days:
        env.set("MAD_SESSIONS_RETENTION_DAYS", params.retention_days)
    else:
        env.add_comment(
            "MAD_SESSIONS_RETENTION_DAYS=  # session log retention in days; unset = keep forever"
        )
    # MCP DNS-rebinding protection: commented reference when left disabled.
    if params.mcp_allowed_hosts:
        env.set("MAD_MCP_ALLOWED_HOSTS", params.mcp_allowed_hosts)
    else:
        env.add_comment(
            "MAD_MCP_ALLOWED_HOSTS=  # comma-separated allowed hosts; unset = protection disabled"
        )
    # SSE keep-alive heartbeat is never prompted — leave it as a reference knob.
    if env.get("MAD_SSE_HEARTBEAT_S") is None:
        env.add_comment("MAD_SSE_HEARTBEAT_S=  # SSE keep-alive heartbeat in seconds")
    return env, extra_vars


def install(params: InstallParams) -> InstallResult:
    """Write an instance's files and data dirs, and optionally start it.

    Validates ``params`` (name / port / timeout / retention) and the extra keys,
    then renders the files, creates ``workspaces/`` ``sessions/`` ``aws/``
    ``claude/`` under the data path, writes the Claude credentials when a token is
    given and — unless ``params.start`` is false — builds and awaits health.
    """
    name = validate_name(params.name)
    validate_port(str(params.port))
    validate_timeout(str(params.timeout_s))
    validate_retention(params.retention_days)

    env, extra_vars = build_env(params)

    ctx = RenderContext(
        instance=name,
        host_port=params.port,
        data_path=params.data_path,
        timeout_s=params.timeout_s,
        puid=params.puid,
        pgid=params.pgid,
        edge_package=params.edge_package,
        edge_version=params.edge_version,
    )
    config_dir = instance_dir(name)
    write_instance_files(config_dir, ctx, env)

    instance_data = params.data_path / name
    (instance_data / "workspaces").mkdir(parents=True, exist_ok=True)
    (instance_data / "sessions").mkdir(parents=True, exist_ok=True)
    (instance_data / "aws").mkdir(parents=True, exist_ok=True)
    claude_dir = instance_data / "claude"
    creds: Path | None = None
    if params.claude_token:
        creds = write_claude_credentials(claude_dir, params.claude_token)
    else:
        claude_dir.mkdir(parents=True, exist_ok=True)

    started = False
    healthy: bool | None = None
    url: str | None = None
    if params.start:
        instance = Instance(name=name, config_dir=config_dir, env=env)
        runner = ComposeRunner(instance)
        runner.up(build=True)
        healthy = runner.wait_healthy()
        started = True
        url = f"http://localhost:{params.port}"

    return InstallResult(
        name=name,
        config_dir=config_dir,
        data_dir=params.data_path,
        port=params.port,
        timeout_s=params.timeout_s,
        env=env,
        extra_key_vars=extra_vars,
        claude_credentials_path=creds,
        claude_dir=claude_dir,
        started=started,
        healthy=healthy,
        url=url,
    )
