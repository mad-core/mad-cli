"""Tests for mad_cli.core.templates."""

from __future__ import annotations

import stat
from pathlib import Path

from mad_cli.core.envfile import EnvFile
from mad_cli.core.templates import RenderContext, render_all, write_instance_files


def _ctx(**overrides: object) -> RenderContext:
    base: dict[str, object] = {
        "instance": "default",
        "host_port": 8080,
        "data_path": Path("/home/mad-data"),
        "timeout_s": 180000,
        "puid": 1000,
        "pgid": 1000,
    }
    base.update(overrides)
    return RenderContext(**base)  # type: ignore[arg-type]


def test_render_pip_install_without_version() -> None:
    out = render_all(_ctx())
    assert '/opt/venv/bin/pip install --no-cache-dir "mad-edge"' in out["Dockerfile"]
    assert "mad-edge:latest" in out["compose.yml"]


def test_render_pip_install_with_version() -> None:
    out = render_all(_ctx(edge_version="1.2.3"))
    assert '/opt/venv/bin/pip install --no-cache-dir "mad-edge==1.2.3"' in out["Dockerfile"]
    assert "mad-edge:1.2.3" in out["compose.yml"]


def test_render_custom_package_and_binary_for_mad_bros() -> None:
    out = render_all(_ctx(edge_package="mad-bros"))
    assert '/opt/venv/bin/pip install --no-cache-dir "mad-bros"' in out["Dockerfile"]
    # mad-bros installs the `mad` console script, not `mad-edge`.
    assert "exec mad serve --host 0.0.0.0 --port 8000" in out["entrypoint.sh"]


def test_entrypoint_default_binary_and_gh_auth() -> None:
    out = render_all(_ctx())
    assert "gh auth login" in out["entrypoint.sh"]
    assert "exec mad-edge serve --host 0.0.0.0 --port 8000" in out["entrypoint.sh"]


def test_entrypoint_preserves_shell_escapes() -> None:
    out = render_all(_ctx())
    # $$ in the template must survive as a single literal $ (not a substitution).
    assert '"${GITHUB_TOKEN:-}"' in out["entrypoint.sh"]


def test_dockerfile_preserves_shell_escapes() -> None:
    out = render_all(_ctx())
    assert "$(dpkg --print-architecture)" in out["Dockerfile"]
    assert "/opt/venv/bin:${PATH}" in out["Dockerfile"]


def test_compose_has_port_and_three_bind_mounts() -> None:
    out = render_all(_ctx(instance="prod", host_port=9000, data_path=Path("/srv/mad")))
    compose = out["compose.yml"]
    assert '"9000:8000"' in compose
    assert "/srv/mad/prod/workspaces:/workspaces" in compose
    assert "/srv/mad/prod/claude:/home/mad/.claude" in compose
    assert "/srv/mad/prod/aws:/home/mad/.aws:ro" in compose


def test_write_instance_files(tmp_path: Path) -> None:
    env = EnvFile.empty()
    env.set("MAD_INSTANCE", "default")
    env.set("MAD_HOST_PORT", "8080")
    write_instance_files(tmp_path, _ctx(), env)

    for name in ("Dockerfile", "compose.yml", "entrypoint.sh", ".env"):
        assert (tmp_path / name).is_file()

    mode = stat.S_IMODE((tmp_path / "entrypoint.sh").stat().st_mode)
    assert mode == 0o755

    saved = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "MAD_INSTANCE=default" in saved
    assert "MAD_HOST_PORT=8080" in saved


def test_write_instance_files_creates_target(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "cfg"
    write_instance_files(target, _ctx(), EnvFile.empty())
    assert (target / "Dockerfile").is_file()
