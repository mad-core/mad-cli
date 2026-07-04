"""Tests for the top-level Typer app: version, help, and command registration."""

from __future__ import annotations

from typer.testing import CliRunner

from mad_cli import __version__
from mad_cli.app import app


def test_version_prints_package_version(cli: CliRunner) -> None:
    result = cli.invoke(app, ["--version"])
    assert result.exit_code == 0
    # --version prints exactly the package version (kept in lock-step by release automation).
    assert result.output.strip() == __version__


def test_no_args_shows_help(cli: CliRunner) -> None:
    result = cli.invoke(app, [])
    # Typer's no_args_is_help exits with click's "no command" code (2).
    assert result.exit_code == 2
    assert "Usage" in result.output
    assert "install" in result.output


def test_help_lists_all_commands(cli: CliRunner) -> None:
    result = cli.invoke(app, ["--help"])
    assert result.exit_code == 0
    commands = ("install", "start", "stop", "restart", "status", "logs", "shell", "list", "info")
    for command in commands:
        assert command in result.output
