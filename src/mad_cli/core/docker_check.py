"""Docker/daemon/compose-v2 detection and opt-in Linux install. Contract stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DockerStatus:
    docker_present: bool
    daemon_running: bool
    compose_v2: bool
    version: str | None


def check_docker() -> DockerStatus:
    raise NotImplementedError


def install_docker_linux(assume_yes: bool = False) -> bool:
    raise NotImplementedError
