"""Unit tests for the service-mode use case (token, venv bootstrap, rendering).

No real ``systemctl`` / ``launchctl`` and no real venv/pip are ever invoked — the
subprocess seam is mocked so the whole module is exercised offline.
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mad_cli import __version__
from mad_cli.core.usecases import service
from mad_cli.core.usecases.errors import PreconditionError


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "config"
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(root))
    return root


# ── API token ────────────────────────────────────────────────────────────────
def test_ensure_api_token_creates_0600_and_is_idempotent(config_dir: Path) -> None:
    assert service.read_api_token() is None
    token = service.ensure_api_token()
    path = service.api_token_path()

    assert path.is_file()
    assert oct(path.stat().st_mode)[-3:] == "600"
    assert token and service.read_api_token() == token
    # a second call must not rotate the token
    assert service.ensure_api_token() == token


# ── systemd unit rendering ───────────────────────────────────────────────────
def test_render_systemd_unit_execstart_and_restart(config_dir: Path) -> None:
    exec_args = ["/opt/venv/bin/mad", "serve", "--host", "127.0.0.1", "--port", "7373"]
    unit = service.render_systemd_unit(exec_args=exec_args, config_dir=config_dir)

    assert "ExecStart=/opt/venv/bin/mad serve --host 127.0.0.1 --port 7373" in unit
    assert "Restart=on-failure" in unit
    assert f"Environment=MAD_CLI_CONFIG_DIR={config_dir}" in unit
    assert "WantedBy=default.target" in unit


# ── launchd plist rendering ──────────────────────────────────────────────────
def test_render_launchd_plist_is_valid_and_points_at_binary(config_dir: Path) -> None:
    exec_args = ["/opt/venv/bin/mad", "serve", "--host", "127.0.0.1", "--port", "7373"]
    plist_text = service.render_launchd_plist(
        exec_args=exec_args, config_dir=config_dir, log_path=Path("/tmp/mad.log")
    )
    # It must parse as a real plist (equivalent to `plutil -lint`).
    parsed = plistlib.loads(plist_text.encode("utf-8"))

    assert parsed["Label"] == service.LAUNCHD_LABEL
    assert parsed["ProgramArguments"] == exec_args
    assert parsed["EnvironmentVariables"]["MAD_CLI_CONFIG_DIR"] == str(config_dir)
    assert parsed["RunAtLoad"] is True
    assert parsed["KeepAlive"]["SuccessfulExit"] is False


def test_render_service_dispatches_per_platform(config_dir: Path) -> None:
    exec_args = ["/opt/venv/bin/mad", "serve"]
    linux = service.render_service(platform="linux", exec_args=exec_args, config_dir=config_dir)
    darwin = service.render_service(platform="darwin", exec_args=exec_args, config_dir=config_dir)

    assert linux.platform == "linux" and linux.default_path.name == service.SYSTEMD_UNIT_NAME
    assert "ExecStart=" in linux.content
    assert darwin.platform == "darwin" and darwin.default_path.name == service.PLIST_NAME
    assert "<plist" in darwin.content


def test_render_service_rejects_unsupported_platform(config_dir: Path) -> None:
    with pytest.raises(PreconditionError, match="unsupported platform"):
        service.render_service(platform="windows", exec_args=["mad"], config_dir=config_dir)


# ── serve argv / loopback ────────────────────────────────────────────────────
def test_serve_argv_and_loopback() -> None:
    assert service.serve_argv(["/x/mad"], "0.0.0.0", 7444) == [
        "/x/mad",
        "serve",
        "--host",
        "0.0.0.0",
        "--port",
        "7444",
    ]
    assert service.is_loopback("127.0.0.1")
    assert service.is_loopback("localhost")
    assert not service.is_loopback("0.0.0.0")


# ── venv bootstrap (subprocess mocked) ───────────────────────────────────────
def _record_runs(monkeypatch: pytest.MonkeyPatch, *, returncode: int = 0) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(cmd)
        return SimpleNamespace(returncode=returncode, stdout="", stderr="boom")

    monkeypatch.setattr(service.subprocess, "run", fake_run)
    return calls


def test_bootstrap_server_venv_from_wheel_uses_local_artifact(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _record_runs(monkeypatch)
    wheel = Path("/artifacts/mad_cli-0.3.2-py3-none-any.whl")

    venv = service.bootstrap_server_venv(wheel=wheel)

    assert venv == service.server_venv_dir()
    # created a venv with the current interpreter, then pip-installed the wheel[server]
    assert any(cmd[1:3] == ["-m", "venv"] for cmd in calls)
    pip_calls = [c for c in calls if "install" in c]
    assert pip_calls and pip_calls[0][-1] == f"{wheel}[server]"


def test_bootstrap_server_venv_from_pypi_pins_version(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _record_runs(monkeypatch)
    service.bootstrap_server_venv(wheel=None)
    pip_calls = [c for c in calls if "install" in c]
    assert pip_calls[0][-1] == f"mad-cli[server]=={__version__}"


def test_bootstrap_server_venv_pypi_failure_hints_wheel(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # venv creation succeeds, pip install fails
    def fake_run(cmd: list[str], **kwargs: object) -> SimpleNamespace:
        rc = 0 if "venv" in cmd else 1
        return SimpleNamespace(returncode=rc, stdout="", stderr="No matching distribution")

    monkeypatch.setattr(service.subprocess, "run", fake_run)
    with pytest.raises(PreconditionError, match="--wheel"):
        service.bootstrap_server_venv(wheel=None)


def test_ensure_server_runtime_uses_current_env_when_deps_present(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "server_deps_available", lambda: True)
    booted: list[bool] = []
    monkeypatch.setattr(
        service, "bootstrap_server_venv", lambda **kw: booted.append(True) or Path("x")
    )

    launcher, bootstrapped = service.ensure_server_runtime(wheel=None)
    assert bootstrapped is False
    assert booted == []  # no venv provisioned
    assert launcher  # some resolved `mad` argv


def test_ensure_server_runtime_bootstraps_when_wheel_forced(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "server_deps_available", lambda: True)
    seen: list[Path | None] = []
    monkeypatch.setattr(
        service,
        "bootstrap_server_venv",
        lambda *, wheel: seen.append(wheel) or service.server_venv_dir(),
    )
    wheel = Path("/artifacts/mad_cli.whl")

    launcher, bootstrapped = service.ensure_server_runtime(wheel=wheel)
    assert bootstrapped is True
    assert seen == [wheel]
    assert launcher == [str(service.server_venv_mad())]


def test_server_venv_version_reads_installed_version(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pretend the venv python exists and reports a version.
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="0.3.1\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)
    assert service.server_venv_version() == "0.3.1"
