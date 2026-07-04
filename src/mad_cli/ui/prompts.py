"""Interactive prompt helpers built on ``rich.prompt``.

Contract (CONTRACTS.md):

* ``ask`` re-prompts while ``validator`` raises ``ValueError``; the validator's
  return value is the normalised answer.
* In a non-interactive context (stdin is not a TTY) prompts MUST NOT block:
  ``ask`` returns ``default`` when one exists, otherwise raises
  ``PromptRequiredError``; ``confirm`` returns its ``default``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from rich.prompt import Confirm, Prompt

from mad_cli.ui.console import console, error


class PromptRequiredError(Exception):
    """A value was required but no default was available and we cannot prompt."""


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty()
    except (ValueError, OSError):  # detached / closed stdin
        return False


def ask(
    text: str,
    default: str | None = None,
    secret: bool = False,
    validator: Callable[[str], str] | None = None,
) -> str:
    """Ask for a single string value.

    ``validator`` receives the raw input and returns the normalised value; it
    raises ``ValueError`` (whose message is shown) to trigger a re-prompt.
    """
    if not _stdin_is_tty():
        if default is None:
            raise PromptRequiredError(text)
        if validator is not None:
            try:
                return validator(default)
            except ValueError as exc:  # a bad default is not recoverable here
                raise PromptRequiredError(str(exc)) from exc
        return default

    prompt_text = f"[cyan]?[/cyan] {text}"
    while True:
        if default is not None:
            raw = Prompt.ask(
                prompt_text,
                console=console,
                password=secret,
                show_default=not secret,
                default=default,
            )
        else:
            raw = Prompt.ask(
                prompt_text,
                console=console,
                password=secret,
                show_default=not secret,
            )
        if validator is None:
            return raw
        try:
            return validator(raw)
        except ValueError as exc:
            error(str(exc))


def confirm(text: str, default: bool = True) -> bool:
    """Yes/no confirmation. Returns ``default`` when stdin is not a TTY."""
    if not _stdin_is_tty():
        return default
    return Confirm.ask(f"[cyan]?[/cyan] {text}", console=console, default=default)
