"""Small presentation helpers shared across commands."""

from __future__ import annotations

# Substrings that mark an env key as holding a secret whose value must be masked
# before it is shown to a human.
_SECRET_HINTS = ("TOKEN", "KEY", "SECRET", "PASSWORD")


def is_secret_key(key: str) -> bool:
    """True if ``key`` looks like it holds a credential."""
    upper = key.upper()
    return any(hint in upper for hint in _SECRET_HINTS)
