"""Service-mode use cases: the API token, the dedicated server venv and the
systemd unit / launchd plist rendering.

The base CLI is a two-dependency package, so ``mad serve`` / ``mad service`` must
not assume the ``server`` extra is importable. When it is not, ``mad service
install`` bootstraps a dedicated virtualenv under ``config_root()/server-venv`` and
installs ``mad-cli[server]`` into it (pinned to the running CLI's version, or from
a local wheel via ``--wheel``); the rendered unit/plist then points ``ExecStart``
at ``<venv>/bin/mad serve``. When the extra *is* importable, the current
interpreter's ``mad`` is used and no venv is created.

Everything here is framework-free (no typer / rich / fastapi). Activating the unit
(``systemctl`` / ``launchctl``) is the caller's business; this module only renders
files and provisions the runtime.
"""

from __future__ import annotations

import importlib.util
import os
import secrets
import shlex
import string
import subprocess
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from mad_cli import __version__
from mad_cli.core.paths import config_root
from mad_cli.core.usecases.errors import PreconditionError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7373
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

LAUNCHD_LABEL = "com.mad-core.mad-cli"
SYSTEMD_UNIT_NAME = "mad-cli.service"
PLIST_NAME = f"{LAUNCHD_LABEL}.plist"

_SERVER_MODULES = ("fastapi", "uvicorn")


# ── API token ────────────────────────────────────────────────────────────────
def api_token_path() -> Path:
    """Path of the bearer token file (``config_root()/api-token``)."""
    return config_root() / "api-token"


def read_api_token() -> str | None:
    """Return the stored bearer token, or ``None`` when it does not exist."""
    path = api_token_path()
    if not path.is_file():
        return None
    token = path.read_text(encoding="utf-8").strip()
    return token or None


def ensure_api_token() -> str:
    """Return the bearer token, generating a fresh 0600 one on first use."""
    existing = read_api_token()
    if existing is not None:
        return existing
    token = secrets.token_urlsafe(32)
    path = api_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    path.chmod(0o600)
    return token


# ── server-extra detection & the dedicated venv ──────────────────────────────
def server_deps_available() -> bool:
    """True when the ``server`` extra (fastapi + uvicorn) is importable here."""
    return all(importlib.util.find_spec(mod) is not None for mod in _SERVER_MODULES)


def server_venv_dir() -> Path:
    """The dedicated server virtualenv directory (``config_root()/server-venv``)."""
    return config_root() / "server-venv"


def _venv_bin_dir(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def server_venv_mad() -> Path:
    """The ``mad`` console script inside the dedicated server venv."""
    exe = "mad.exe" if os.name == "nt" else "mad"
    return _venv_bin_dir(server_venv_dir()) / exe


def server_venv_exists() -> bool:
    """True when the dedicated server venv has a usable ``mad`` binary."""
    return server_venv_mad().exists()


def _run(cmd: list[str]) -> None:
    """Run ``cmd``; raise :class:`PreconditionError` with captured output on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise PreconditionError(f"failed to run {' '.join(cmd)}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise PreconditionError(
            f"`{' '.join(cmd)}` failed (exit {result.returncode})"
            + (f": {detail}" if detail else "")
        )


def bootstrap_server_venv(*, wheel: Path | None = None) -> Path:
    """Create ``config_root()/server-venv`` and install ``mad-cli[server]`` into it.

    From ``wheel`` (a local wheel/sdist, extras appended) when given — no network,
    exact artifact — otherwise ``mad-cli[server]==<running version>`` from PyPI. A
    PyPI failure raises :class:`PreconditionError` hinting at ``--wheel``.
    """
    venv_dir = server_venv_dir()
    _run([sys.executable, "-m", "venv", str(venv_dir)])
    pip = str(_venv_bin_dir(venv_dir) / ("pip.exe" if os.name == "nt" else "pip"))
    target = f"{wheel}[server]" if wheel is not None else f"mad-cli[server]=={__version__}"
    try:
        _run([pip, "install", target])
    except PreconditionError:
        if wheel is None:
            raise PreconditionError(
                "could not install 'mad-cli[server]' from PyPI into the server venv; "
                "retry with --wheel PATH pointing at a local wheel or sdist"
            ) from None
        raise
    return venv_dir


def server_venv_version() -> str | None:
    """Return the ``mad_cli`` version installed in the server venv, or ``None``."""
    python = _venv_bin_dir(server_venv_dir()) / ("python.exe" if os.name == "nt" else "python")
    if not python.exists():
        return None
    try:
        out = subprocess.run(
            [str(python), "-c", "import mad_cli; print(mad_cli.__version__)"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return (out.stdout or "").strip() or None


# ── launcher resolution ──────────────────────────────────────────────────────
def _mad_launcher() -> list[str]:
    """Robustly resolve the current interpreter's ``mad`` launcher argv.

    Prefers the console script next to ``sys.executable`` (works inside a venv
    regardless of ``PATH``), then ``PATH``, falling back to ``python -m mad_cli``.
    """
    import shutil

    candidate = Path(sys.executable).with_name("mad.exe" if os.name == "nt" else "mad")
    if candidate.exists():
        return [str(candidate)]
    found = shutil.which("mad")
    if found:
        return [found]
    return [sys.executable, "-m", "mad_cli"]


def ensure_server_runtime(*, wheel: Path | None = None) -> tuple[list[str], bool]:
    """Return ``(mad launcher argv, bootstrapped)`` for a server-capable ``mad``.

    With ``wheel`` given, or when the ``server`` extra is not importable in the
    current interpreter, a dedicated venv is provisioned and its ``mad`` is
    returned; otherwise the current interpreter's ``mad`` is used unchanged.
    """
    if wheel is None and server_deps_available():
        return _mad_launcher(), False
    bootstrap_server_venv(wheel=wheel)
    return [str(server_venv_mad())], True


def serve_argv(launcher: list[str], host: str, port: int) -> list[str]:
    """Build the ``mad serve`` argv from a launcher and bind address."""
    return [*launcher, "serve", "--host", host, "--port", str(port)]


def is_loopback(host: str) -> bool:
    """True when ``host`` binds only the loopback interface."""
    return host in LOOPBACK_HOSTS


# ── unit / plist rendering ───────────────────────────────────────────────────
def _load_template(name: str) -> string.Template:
    text = resources.files("mad_cli.templates").joinpath(name).read_text(encoding="utf-8")
    return string.Template(text)


def render_systemd_unit(*, exec_args: list[str], config_dir: Path) -> str:
    """Render the systemd **user** unit. ``ExecStart`` is a single command line."""
    return _load_template("mad-cli.service.tmpl").substitute(
        exec_start=shlex.join(exec_args),
        config_dir=str(config_dir),
    )


def render_launchd_plist(*, exec_args: list[str], config_dir: Path, log_path: Path) -> str:
    """Render the launchd LaunchAgent plist (``ProgramArguments`` as a string array)."""
    program_arguments = "\n".join(
        f"        <string>{xml_escape(arg)}</string>" for arg in exec_args
    )
    return _load_template(f"{PLIST_NAME}.tmpl").substitute(
        label=LAUNCHD_LABEL,
        program_arguments=program_arguments,
        config_dir=str(config_dir),
        log_path=str(log_path),
    )


def systemd_unit_path() -> Path:
    """Default install path of the systemd user unit."""
    return Path.home() / ".config" / "systemd" / "user" / SYSTEMD_UNIT_NAME


def launchd_plist_path() -> Path:
    """Default install path of the launchd LaunchAgent plist."""
    return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME


def default_log_path() -> Path:
    """Default log file for the launchd service."""
    return config_root() / "mad-cli.serve.log"


@dataclass(frozen=True)
class RenderedService:
    platform: str  # "linux" | "darwin"
    default_path: Path
    content: str
    exec_args: list[str]


def render_service(
    *,
    platform: str,
    exec_args: list[str],
    config_dir: Path,
) -> RenderedService:
    """Render the platform's service file and report its default install path.

    Raises :class:`PreconditionError` on an unsupported platform (only Linux
    systemd-user and macOS launchd are supported).
    """
    if platform == "linux":
        content = render_systemd_unit(exec_args=exec_args, config_dir=config_dir)
        return RenderedService("linux", systemd_unit_path(), content, exec_args)
    if platform == "darwin":
        content = render_launchd_plist(
            exec_args=exec_args, config_dir=config_dir, log_path=default_log_path()
        )
        return RenderedService("darwin", launchd_plist_path(), content, exec_args)
    raise PreconditionError(
        f"unsupported platform {platform!r}: `mad service` supports Linux (systemd) and macOS "
        "(launchd) only. Use `mad serve` to run in the foreground."
    )
