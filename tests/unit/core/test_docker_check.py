"""Tests for mad_cli.core.docker_check."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from mad_cli.core import docker_check as dc


def _cp(cmd: list[str], returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")


def test_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd == ["docker", "--version"]:
            return _cp(cmd, 0, "Docker version 27.0.0\n")
        return _cp(cmd, 0)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    status = dc.check_docker()
    assert status.docker_present is True
    assert status.daemon_running is True
    assert status.compose_v2 is True
    assert status.version == "Docker version 27.0.0"


def test_no_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd == ["docker", "--version"]:
            return _cp(cmd, 0, "Docker version 27.0.0\n")
        if cmd == ["docker", "info"]:
            return _cp(cmd, 1)
        return _cp(cmd, 0)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    status = dc.check_docker()
    assert status.docker_present is True
    assert status.daemon_running is False
    assert status.compose_v2 is True


def test_no_compose_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd == ["docker", "--version"]:
            return _cp(cmd, 0, "Docker version 27.0.0\n")
        if cmd == ["docker", "compose", "version"]:
            return _cp(cmd, 1)
        return _cp(cmd, 0)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    status = dc.check_docker()
    assert status.compose_v2 is False
    assert status.daemon_running is True


def test_docker_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    status = dc.check_docker()
    assert status.docker_present is False
    assert status.daemon_running is False
    assert status.compose_v2 is False
    assert status.version is None


class _FakeResponse:
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return b"#!/bin/sh\necho install\n"


def test_install_docker_linux_skips_non_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc.platform, "system", lambda: "Darwin")
    assert dc.install_docker_linux() is False


def test_install_docker_linux_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc.platform, "system", lambda: "Linux")
    monkeypatch.setattr(dc.urllib.request, "urlopen", lambda url, timeout=30: _FakeResponse())
    monkeypatch.setattr(dc.os.environ, "get", lambda *a: "mad")

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    assert dc.install_docker_linux(assume_yes=True) is True


def test_install_docker_linux_failure_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc.platform, "system", lambda: "Linux")
    monkeypatch.setattr(dc.urllib.request, "urlopen", lambda url, timeout=30: _FakeResponse())

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    assert dc.install_docker_linux() is False
