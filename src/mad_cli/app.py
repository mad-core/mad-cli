"""Typer application wiring and the ``mad`` console-script entry point."""

import typer

from mad_cli import __version__
from mad_cli.commands import config as config_cmd
from mad_cli.commands import install as install_cmd
from mad_cli.commands import instances as instances_cmd
from mad_cli.commands import keys as keys_cmd
from mad_cli.commands import lifecycle as lifecycle_cmd

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Mad operator CLI — install and manage mad-edge containers.",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the mad-cli version and exit.",
    ),
) -> None:
    """Mad operator CLI — install and manage mad-edge containers."""


# ── install ──────────────────────────────────────────────────────────────────
app.command("install")(install_cmd.install)

# ── lifecycle ────────────────────────────────────────────────────────────────
app.command("start")(lifecycle_cmd.start)
app.command("stop")(lifecycle_cmd.stop)
app.command("restart")(lifecycle_cmd.restart)
app.command("status")(lifecycle_cmd.status)
app.command("logs")(lifecycle_cmd.logs)
app.command("shell")(lifecycle_cmd.shell)

# ── inventory ────────────────────────────────────────────────────────────────
app.command("list")(instances_cmd.list_)
app.command("info")(instances_cmd.info_cmd)

# ── keys & config ─────────────────────────────────────────────────────────────
app.add_typer(keys_cmd.keys_app, name="keys")
app.add_typer(config_cmd.config_app, name="config")


def main() -> None:
    """Console-script entry point (``mad``)."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
