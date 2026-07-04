"""Registry of the credentials / API keys an operator can store in ``.env``.

Each :class:`KeySpec` maps one logical secret to the environment variable(s) it
is written to. Some secrets fan out to several variables that must carry the
same value (``github`` -> ``GITHUB_TOKEN`` + ``GH_TOKEN``); ``claude-oauth`` is
special-cased because, besides landing in ``.env``, it is materialised into the
container's Claude credentials file (see :mod:`mad_cli.core.claude_creds`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeySpec:
    id: str
    env_vars: tuple[str, ...]
    prompt: str
    secret: bool = True
    help_url: str | None = None
    writes_claude_credentials: bool = False


BUILTIN_KEYS: dict[str, KeySpec] = {
    "claude-oauth": KeySpec(
        id="claude-oauth",
        env_vars=("_CLAUDE_OAUTH_TOKEN",),
        prompt="Claude OAuth token (run `claude setup-token` on a logged-in machine)",
        help_url="https://docs.anthropic.com/en/docs/claude-code",
        writes_claude_credentials=True,
    ),
    "anthropic": KeySpec(
        id="anthropic",
        env_vars=("ANTHROPIC_API_KEY",),
        prompt="Anthropic API key (sk-ant-…)",
        help_url="https://console.anthropic.com/settings/keys",
    ),
    "github": KeySpec(
        id="github",
        env_vars=("GITHUB_TOKEN", "GH_TOKEN"),
        prompt="GitHub personal access token (ghp_…)",
        help_url="https://github.com/settings/tokens",
    ),
    "deepseek": KeySpec(
        id="deepseek",
        env_vars=("DEEPSEEK_API_KEY",),
        prompt="DeepSeek API key",
        help_url="https://platform.deepseek.com/api_keys",
    ),
    "linear": KeySpec(
        id="linear",
        env_vars=("LINEAR_API_KEY",),
        prompt="Linear API key",
        help_url="https://linear.app/settings/api",
    ),
    "opencode": KeySpec(
        id="opencode",
        env_vars=("OPENCODE_API_KEY",),
        prompt="OpenCode API key",
        help_url="https://opencode.ai/docs",
    ),
}


def mask(value: str) -> str:
    """Return a display-safe masking of ``value``.

    Long secrets keep a short prefix and suffix (``"sk-a…f3"``); anything short
    enough that a prefix/suffix would leak most of it is fully hidden.
    """
    if not value:
        return ""
    if len(value) <= 8:
        return "…"
    return f"{value[:4]}…{value[-2:]}"


# Substrings that mark an env key as holding a secret whose value must be masked
# before it is shown to a human or returned over the API.
_SECRET_HINTS = ("TOKEN", "KEY", "SECRET", "PASSWORD")


def is_secret_key(key: str) -> bool:
    """True if ``key`` looks like it holds a credential (masked on display)."""
    upper = key.upper()
    return any(hint in upper for hint in _SECRET_HINTS)


def display_value(key: str, value: str, *, reveal: bool = False) -> str:
    """Return ``value`` for display: masked when it looks secret, else verbatim.

    ``reveal=True`` returns the raw value (the CLI ``--reveal`` path); the HTTP
    API never passes it, so secret-looking values are always masked there.
    """
    if reveal or not value or not is_secret_key(key):
        return value
    return mask(value)
