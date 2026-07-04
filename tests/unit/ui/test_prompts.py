"""Tests for the prompt helpers' non-interactive contract and validator loop."""

from __future__ import annotations

import pytest

from mad_cli.ui import prompts
from mad_cli.ui.prompts import PromptRequiredError, ask, confirm


@pytest.fixture
def non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "_stdin_is_tty", lambda: False)


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompts, "_stdin_is_tty", lambda: True)


def test_ask_returns_default_when_non_interactive(non_tty: None) -> None:
    assert ask("Instance name", default="default") == "default"


def test_ask_raises_when_required_and_non_interactive(non_tty: None) -> None:
    with pytest.raises(PromptRequiredError):
        ask("GitHub token")


def test_ask_rejects_invalid_default_when_non_interactive(non_tty: None) -> None:
    def _validate(value: str) -> str:
        raise ValueError("nope")

    with pytest.raises(PromptRequiredError):
        ask("Port", default="bad", validator=_validate)


def test_confirm_returns_default_when_non_interactive(non_tty: None) -> None:
    assert confirm("Proceed?", default=False) is False
    assert confirm("Proceed?", default=True) is True


def test_ask_reprompts_until_validator_accepts(tty: None, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["bad", "also-bad", "42"])
    monkeypatch.setattr(prompts.Prompt, "ask", staticmethod(lambda *a, **k: next(answers)))

    def _validate(value: str) -> str:
        if not value.isdigit():
            raise ValueError(f"not a number: {value}")
        return f"n={value}"

    assert ask("Port", validator=_validate) == "n=42"
