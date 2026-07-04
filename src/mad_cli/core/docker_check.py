"""Docker / daemon / compose-v2 detection and opt-in Linux install.

Everything is probed through ``subprocess`` (not ``shutil.which``) so the whole
module can be exercised in tests with a single ``subprocess.run`` double.
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass


@dataclass
class DockerStatus:
    docker_present: bool
    daemon_running: bool
    compose_v2: bool
    version: str | None


def _capture(cmd: list[str]) -> str | None:
    """Run ``cmd``; return trimmed stdout on success, ``None`` otherwise."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip()


def _ok(cmd: list[str]) -> bool:
    """Return ``True`` when ``cmd`` exits 0."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return False
    return result.returncode == 0


def check_docker() -> DockerStatus:
    """Probe for the docker binary, a running daemon and Compose v2."""
    version = _capture(["docker", "--version"])
    if version is None:
        return DockerStatus(
            docker_present=False,
            daemon_running=False,
            compose_v2=False,
            version=None,
        )
    return DockerStatus(
        docker_present=True,
        daemon_running=_ok(["docker", "info"]),
        compose_v2=_ok(["docker", "compose", "version"]),
        version=version,
    )


def install_docker_linux(assume_yes: bool = False) -> bool:
    """Install Docker on Linux via the official ``get.docker.com`` script.

    Returns ``True`` on success. The interactive confirmation lives in the
    command layer; ``assume_yes`` is accepted for symmetry and does not change
    the (already opted-in) behaviour here. Never touches non-Linux hosts.
    """
    if platform.system() != "Linux":
        return False
    script_path = ""
    try:
        with urllib.request.urlopen("https://get.docker.com", timeout=30) as response:
            script = response.read()
        with tempfile.NamedTemporaryFile("wb", suffix=".sh", delete=False) as handle:
            handle.write(script)
            script_path = handle.name
        subprocess.run(["sh", script_path], check=True)
        subprocess.run(["sudo", "systemctl", "enable", "--now", "docker"], check=True)
        user = os.environ.get("USER", "")
        if user:
            subprocess.run(["sudo", "usermod", "-aG", "docker", user], check=False)
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    finally:
        if script_path and os.path.exists(script_path):
            os.unlink(script_path)
