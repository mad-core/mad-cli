"""Small presentation helpers shared across commands.

Secret detection now lives in the framework-free engine
(:func:`mad_cli.core.keyspec.is_secret_key`) so the HTTP surface and the CLI
share one masking rule; it is re-exported here for the command modules.
"""

from __future__ import annotations

from mad_cli.core.keyspec import is_secret_key

__all__ = ["is_secret_key"]
