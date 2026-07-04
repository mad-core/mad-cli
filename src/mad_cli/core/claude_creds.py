"""Claude OAuth credentials file (``claudeAiOauth`` format, ``chmod 600``).

Ports ``write_claude_credentials`` from the reference ``configure.sh``: the file
that the ``claude-code`` CLI reads from ``~/.claude/.credentials.json`` inside the
container, so the agent authenticates without an interactive login.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_claude_credentials(claude_dir: Path, token: str) -> Path:
    """Write ``claude_dir/.credentials.json`` and return its path.

    The directory is created if needed and the file is ``chmod 600`` because it
    holds a bearer token.
    """
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / ".credentials.json"
    payload = {
        "claudeAiOauth": {
            "accessToken": token,
            "expiresAt": 9999999999999,
            "scopes": ["user:inference", "user:profile"],
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path
