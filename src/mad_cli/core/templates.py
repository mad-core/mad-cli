"""Instance file rendering (Dockerfile / compose.yml / entrypoint.sh / .env).

Ports the ``write_dockerfile`` / ``write_compose`` / ``write_entrypoint`` heredocs
from the reference ``configure.sh`` to packaged ``string.Template`` files. The one
deliberate change: the pip package is parameterised via
:attr:`RenderContext.edge_package` (default ``"mad-edge"``), and because
``string.Template`` has no conditionals the container's start binary is resolved
here in Python — ``mad-edge`` normally, but ``mad`` for the ``mad-bros`` package,
which still installs the ``mad`` console script.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from mad_cli.core.envfile import EnvFile

EDGE_PACKAGE: str = "mad-edge"

# Rendered output name -> packaged template name.
_TEMPLATES: dict[str, str] = {
    "Dockerfile": "Dockerfile.tmpl",
    "compose.yml": "compose.yml.tmpl",
    "entrypoint.sh": "entrypoint.sh.tmpl",
}


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


def _entrypoint_binary(edge_package: str) -> str:
    """Console script that starts the server for ``edge_package``.

    ``mad-bros`` ships its server as the ``mad`` script; every other package
    (``mad-edge`` and forks) exposes ``mad-edge``.
    """
    return "mad" if edge_package == "mad-bros" else "mad-edge"


def _load_template(template_name: str) -> string.Template:
    text = resources.files("mad_cli.templates").joinpath(template_name).read_text(encoding="utf-8")
    return string.Template(text)


def render_all(ctx: RenderContext) -> dict[str, str]:
    """Render the three instance files from the packaged templates."""
    version_spec = f"=={ctx.edge_version}" if ctx.edge_version else ""
    mapping = {
        "instance": ctx.instance,
        "host_port": str(ctx.host_port),
        "data_path": str(ctx.data_path),
        "timeout_s": str(ctx.timeout_s),
        "puid": str(ctx.puid),
        "pgid": str(ctx.pgid),
        "edge_package": ctx.edge_package,
        "edge_version_spec": version_spec,
        "image_tag": ctx.edge_version or "latest",
        "edge_entrypoint": _entrypoint_binary(ctx.edge_package),
    }
    return {
        out_name: _load_template(tmpl_name).substitute(mapping)
        for out_name, tmpl_name in _TEMPLATES.items()
    }


def write_instance_files(target: Path, ctx: RenderContext, env: EnvFile) -> None:
    """Render into ``target`` and save ``env`` as ``target/.env``.

    ``entrypoint.sh`` is made executable (mode ``0o755``); the ``.env`` is written
    through :meth:`EnvFile.save` so its comments and ordering survive.
    """
    target.mkdir(parents=True, exist_ok=True)
    rendered = render_all(ctx)
    (target / "Dockerfile").write_text(rendered["Dockerfile"], encoding="utf-8")
    (target / "compose.yml").write_text(rendered["compose.yml"], encoding="utf-8")
    entrypoint = target / "entrypoint.sh"
    entrypoint.write_text(rendered["entrypoint.sh"], encoding="utf-8")
    entrypoint.chmod(0o755)
    env.save(target / ".env")
