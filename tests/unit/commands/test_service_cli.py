"""Tests for the ``mad serve`` / ``mad service`` command adapters.

``--render-to`` writes the unit/plist and touches nothing on the live system, so
these never call systemctl/launchctl. The venv bootstrap is mocked.
"""

from __future__ import annotations

import platform
import plistlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mad_cli.app import app


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "config"
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(root))
    return root


def test_service_install_render_to_writes_service_file(
    cli: CliRunner, config_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "unit.txt"
    result = cli.invoke(app, ["service", "install", "--render-to", str(out), "--port", "7444"])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    content = out.read_text()
    assert "serve" in content and "7444" in content
    # the API token was provisioned as a side effect
    assert (config_dir / "api-token").is_file()

    if platform.system().lower() == "darwin":
        parsed = plistlib.loads(content.encode())  # equivalent to `plutil -lint`
        assert parsed["Label"] == "com.mad-core.mad-cli"
        assert parsed["ProgramArguments"][1] == "serve"
    else:
        assert "ExecStart=" in content and "Restart=on-failure" in content


def test_service_install_wheel_points_unit_at_venv(
    cli: CliRunner, config_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.commands import service as mod

    venv_mad = "/fake/server-venv/bin/mad"
    monkeypatch.setattr(mod.uc, "ensure_server_runtime", lambda *, wheel: ([venv_mad], True))

    out = tmp_path / "unit.txt"
    result = cli.invoke(
        app,
        ["service", "install", "--wheel", str(tmp_path / "w.whl"), "--render-to", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert venv_mad in out.read_text()
    assert "Server venv ready" in result.output


def test_serve_without_extra_or_venv_errors_with_both_hints(
    cli: CliRunner, config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mad_cli.commands import service as mod

    monkeypatch.setattr(mod.uc, "server_deps_available", lambda: False)
    monkeypatch.setattr(mod.uc, "server_venv_exists", lambda: False)

    result = cli.invoke(app, ["serve"])
    assert result.exit_code != 0
    assert "pip install 'mad-cli[server]'" in result.output
    assert "mad service install" in result.output


def test_service_status_reports_absence(cli: CliRunner, config_dir: Path) -> None:
    result = cli.invoke(app, ["service", "status"])
    assert result.exit_code == 0, result.output
    assert "Service file" in result.output
