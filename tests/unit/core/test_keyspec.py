"""Tests for mad_cli.core.keyspec."""

from __future__ import annotations

import pytest

from mad_cli.core.keyspec import BUILTIN_KEYS, mask


def test_builtin_keys_present() -> None:
    assert set(BUILTIN_KEYS) >= {
        "claude-oauth",
        "anthropic",
        "github",
        "deepseek",
        "linear",
        "opencode",
    }


def test_github_fans_out_to_both_tokens() -> None:
    assert BUILTIN_KEYS["github"].env_vars == ("GITHUB_TOKEN", "GH_TOKEN")


def test_only_claude_oauth_writes_credentials() -> None:
    assert BUILTIN_KEYS["claude-oauth"].writes_claude_credentials is True
    for key_id, spec in BUILTIN_KEYS.items():
        if key_id != "claude-oauth":
            assert spec.writes_claude_credentials is False


def test_key_id_matches_dict_key() -> None:
    for key_id, spec in BUILTIN_KEYS.items():
        assert spec.id == key_id


def test_mask_long_value_keeps_prefix_and_suffix() -> None:
    masked = mask("sk-ant-secret-value-1234f3")
    assert masked == "sk-a…f3"
    assert "secret" not in masked


def test_mask_short_value_hides_everything() -> None:
    for value in ["abc", "abcdef", "12345678"]:
        masked = mask(value)
        assert value not in masked
        assert masked == "…"


def test_mask_empty_value() -> None:
    assert mask("") == ""


@pytest.mark.parametrize("value", ["ghp_supersecrettoken", "sk-ant-abcdefghijklmnop"])
def test_mask_never_leaks_full_value(value: str) -> None:
    assert value not in mask(value)
