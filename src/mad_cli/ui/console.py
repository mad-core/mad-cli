"""Shared rich console and consistently-styled status helpers.

The single module-level :data:`console` is the one place output is written, so
every command shares the same width, theme and capture behaviour. The helpers
below add a coloured status glyph so ``info``/``ok``/``warn``/``error`` read the
same everywhere.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from rich.console import Console

_T = TypeVar("_T")

# A single shared console. No explicit ``file`` is passed so rich resolves
# ``sys.stdout`` lazily at print time — this is what lets test runners that
# redirect stdout (e.g. Typer's CliRunner) capture our output.
console = Console()


def info(msg: str) -> None:
    """Neutral progress message."""
    console.print(f"[cyan]▸[/cyan] {msg}", soft_wrap=True)


def ok(msg: str) -> None:
    """Success message."""
    console.print(f"[green]✓[/green] {msg}", soft_wrap=True)


def warn(msg: str) -> None:
    """Non-fatal warning."""
    console.print(f"[yellow]![/yellow] {msg}", soft_wrap=True)


def error(msg: str) -> None:
    """Error message. Rendering only — callers decide whether to exit."""
    console.print(f"[red]✗[/red] {msg}", soft_wrap=True)


def header(msg: str) -> None:
    """Bold section header, preceded by a blank line."""
    console.print(f"\n[bold]{msg}[/bold]", soft_wrap=True)


def run_step(message: str, func: Callable[[], _T]) -> _T:
    """Run ``func`` under a spinner on a real terminal, or plainly otherwise.

    Falling back to a plain ``info`` line keeps output deterministic and
    non-blocking under test runners and redirected pipes (no live display).
    """
    if console.is_terminal:
        with console.status(message, spinner="dots"):
            return func()
    info(message)
    return func()
