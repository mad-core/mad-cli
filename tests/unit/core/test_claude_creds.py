"""Tests for mad_cli.core.claude_creds."""

from __future__ import annotations

import json
import stat
from pathlib import Path

from mad_cli.core.claude_creds import write_claude_credentials


def test_writes_credentials_json(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    path = write_claude_credentials(claude_dir, "tok-123")
    assert path == claude_dir / ".credentials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["claudeAiOauth"]["accessToken"] == "tok-123"
    assert data["claudeAiOauth"]["scopes"] == ["user:inference", "user:profile"]


def test_credentials_file_is_chmod_600(tmp_path: Path) -> None:
    path = write_claude_credentials(tmp_path / "claude", "tok-123")
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_creates_missing_directory(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "claude"
    path = write_claude_credentials(nested, "tok")
    assert path.exists()
