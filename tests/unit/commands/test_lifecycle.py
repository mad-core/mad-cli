"""Tests for ``mad start|stop|restart|status|logs|shell``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.instance import InstanceNotFoundError


def test_start_builds_and_waits_healthy(
    cli: CliRunner, lifecycle_mocks: SimpleNamespace, make_instance, monkeypatch
) -> None:
    inst = make_instance(name="web", host_port=9000)
    monkeypatch.setattr(lifecycle_mocks.mod, "default_instance", lambda: inst)

    result = cli.invoke(app, ["start"])
    assert result.exit_code == 0, result.output
    lifecycle_mocks.runner.up.assert_called_once_with(build=True)
    lifecycle_mocks.runner.wait_healthy.assert_called_once()
    assert "http://localhost:9000" in result.output


def test_logs_follows(
    cli: CliRunner, lifecycle_mocks: SimpleNamespace, make_instance, monkeypatch
) -> None:
    inst = make_instance(name="web")
    monkeypatch.setattr(lifecycle_mocks.mod, "default_instance", lambda: inst)

    result = cli.invoke(app, ["logs"])
    assert result.exit_code == 0, result.output
    lifecycle_mocks.runner.logs.assert_called_once_with(follow=True)


@pytest.mark.parametrize(
    ("command", "method"),
    [
        ("stop", "down"),
        ("restart", "restart"),
        ("status", "ps"),
        ("shell", "shell"),
    ],
)
def test_subcommand_calls_expected_runner_method(
    cli: CliRunner,
    lifecycle_mocks: SimpleNamespace,
    make_instance,
    monkeypatch,
    command: str,
    method: str,
) -> None:
    inst = make_instance(name="web", host_port=9000)
    monkeypatch.setattr(lifecycle_mocks.mod, "default_instance", lambda: inst)

    result = cli.invoke(app, [command])
    assert result.exit_code == 0, result.output
    getattr(lifecycle_mocks.runner, method).assert_called_once()


def test_explicit_instance_is_resolved_by_name(
    cli: CliRunner, lifecycle_mocks: SimpleNamespace, make_instance, monkeypatch
) -> None:
    inst = make_instance(name="api", host_port=9100)
    get_instance = _spy_return(inst)
    monkeypatch.setattr(lifecycle_mocks.mod, "get_instance", get_instance)
    # default_instance must not be consulted when a name is given
    monkeypatch.setattr(
        lifecycle_mocks.mod,
        "default_instance",
        lambda: (_ for _ in ()).throw(AssertionError("default_instance should not be called")),
    )

    result = cli.invoke(app, ["stop", "api"])
    assert result.exit_code == 0, result.output
    assert get_instance.calls == ["api"]
    lifecycle_mocks.runner.down.assert_called_once()


def test_unknown_instance_reports_error(
    cli: CliRunner, lifecycle_mocks: SimpleNamespace, monkeypatch
) -> None:
    def _raise(name: str):
        raise InstanceNotFoundError(name)

    monkeypatch.setattr(lifecycle_mocks.mod, "get_instance", _raise)

    result = cli.invoke(app, ["status", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output
    lifecycle_mocks.runner.ps.assert_not_called()


def test_missing_instance_zero_configured_hints_install(
    cli: CliRunner, lifecycle_mocks: SimpleNamespace, monkeypatch
) -> None:
    monkeypatch.setattr(lifecycle_mocks.mod, "default_instance", lambda: None)
    monkeypatch.setattr(lifecycle_mocks.mod, "discover_instances", lambda: [])

    result = cli.invoke(app, ["status"])
    assert result.exit_code != 0
    assert "mad install" in result.output
    lifecycle_mocks.runner.ps.assert_not_called()


def test_missing_instance_multiple_lists_names(
    cli: CliRunner, lifecycle_mocks: SimpleNamespace, make_instance, monkeypatch
) -> None:
    a = make_instance(name="web")
    b = make_instance(name="api")
    monkeypatch.setattr(lifecycle_mocks.mod, "default_instance", lambda: None)
    monkeypatch.setattr(lifecycle_mocks.mod, "discover_instances", lambda: [a, b])

    result = cli.invoke(app, ["restart"])
    assert result.exit_code != 0
    assert "web" in result.output
    assert "api" in result.output


class _spy_return:
    """A tiny callable that records positional args and returns a fixed value."""

    def __init__(self, value: object) -> None:
        self.value = value
        self.calls: list[str] = []

    def __call__(self, name: str) -> object:
        self.calls.append(name)
        return self.value
