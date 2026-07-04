"""Instance file rendering (Dockerfile/compose/entrypoint/.env). Contract stub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mad_cli.core.envfile import EnvFile

EDGE_PACKAGE: str = "mad-edge"


@dataclass
class RenderContext:
    instance: str
    host_port: int
    data_path: Path
    timeout_s: int
    puid: int
    pgid: int
    edge_package: str = EDGE_PACKAGE
    edge_version: str = ""  # '' = latest


def render_all(ctx: RenderContext) -> dict[str, str]:
    """Render {"Dockerfile", "compose.yml", "entrypoint.sh"} from packaged templates."""
    raise NotImplementedError


def write_instance_files(target: Path, ctx: RenderContext, env: EnvFile) -> None:
    raise NotImplementedError
