"""Tests for mad_cli.core.compose."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from mad_cli.core import compose as compose_mod
from mad_cli.core.compose import ComposeError, ComposeRunner
from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import Instance


def _runner(tmp_path: Path, *, dry_run: bool = False, name: str = "alpha") -> ComposeRunner:
    inst = Instance(name=name, config_dir=tmp_path, env=EnvFile.empty())
    return ComposeRunner(inst, dry_run=dry_run)


def _base(tmp_path: Path, name: str = "alpha") -> list[str]:
    return [
        "docker",
        "compose",
        "-p",
        f"mad-{name}",
        "-f",
        str(tmp_path / "compose.yml"),
        "--env-file",
        str(tmp_path / ".env"),
    ]


def test_up_argv(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.up()
    assert runner.last_command == _base(tmp_path) + ["up", "-d", "--build"]


def test_up_without_build_or_detach(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.up(build=False, detach=False)
    assert runner.last_command == _base(tmp_path) + ["up"]


def test_down_argv(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.down()
    assert runner.last_command == _base(tmp_path) + ["down"]


def test_build_no_cache_argv(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.build(no_cache=True)
    assert runner.last_command == _base(tmp_path) + ["build", "--no-cache"]


def test_logs_and_shell_target_service(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.logs()
    assert runner.last_command == _base(tmp_path) + ["logs", "-f", "mad"]
    runner.shell()
    assert runner.last_command == _base(tmp_path) + ["exec", "mad", "bash"]


def test_exec_argv(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.exec(["ls", "-la"])
    assert runner.last_command == _base(tmp_path) + ["exec", "mad", "ls", "-la"]


def test_config_check_argv(tmp_path: Path) -> None:
    runner = _runner(tmp_path, dry_run=True)
    runner.config_check()
    assert runner.last_command == _base(tmp_path) + ["config", "-q"]


def test_restart_runs_down_then_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    _runner(tmp_path).restart()
    assert [c[len(_base(tmp_path)) :] for c in calls] == [["down"], ["up", "-d", "--build"]]


def test_exec_capture_false_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="ignored", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    assert _runner(tmp_path).exec(["true"], capture=False) == ""


def test_exec_captures_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="hello\n", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    assert _runner(tmp_path).exec(["echo", "hello"]) == "hello\n"


def test_ps_returns_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="NAME  STATUS\n", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    runner = _runner(tmp_path)
    assert runner.ps() == "NAME  STATUS\n"
    assert captured["cmd"] == _base(tmp_path) + ["ps"]


def test_nonzero_returncode_raises_compose_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    runner = _runner(tmp_path)
    with pytest.raises(ComposeError, match="boom"):
        runner.down()


def test_missing_docker_binary_raises_compose_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    runner = _runner(tmp_path)
    with pytest.raises(ComposeError):
        runner.up()


def test_wait_healthy_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="healthy\n", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(compose_mod.time, "sleep", lambda _s: None)
    runner = _runner(tmp_path)
    assert runner.wait_healthy(timeout_s=5) is True


def test_wait_healthy_times_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls["n"] += 1
        return subprocess.CompletedProcess(cmd, 0, stdout="starting\n", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(compose_mod.time, "sleep", lambda _s: None)
    runner = _runner(tmp_path)
    assert runner.wait_healthy(timeout_s=0) is False
    assert calls["n"] >= 1


def test_wait_healthy_inspect_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="healthy\n", stderr="")

    monkeypatch.setattr(compose_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(compose_mod.time, "sleep", lambda _s: None)
    runner = _runner(tmp_path, name="prod")
    runner.wait_healthy(timeout_s=1)
    assert captured["cmd"] == [
        "docker",
        "inspect",
        "--format",
        "{{.State.Health.Status}}",
        "mad-prod",
    ]


def test_wait_healthy_dry_run_is_true(tmp_path: Path) -> None:
    assert _runner(tmp_path, dry_run=True).wait_healthy() is True
