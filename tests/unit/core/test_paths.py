"""Tests for mad_cli.core.paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from mad_cli.core import paths


def test_config_root_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAD_CLI_CONFIG_DIR", raising=False)
    root = paths.config_root()
    assert root == Path.home() / ".config" / "mad"


def test_config_root_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path))
    assert paths.config_root() == tmp_path
    assert paths.instances_root() == tmp_path / "instances"


def test_config_root_expands_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", "~/somewhere/mad")
    assert paths.config_root() == Path.home() / "somewhere" / "mad"


def test_instance_dir_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path))
    assert paths.instance_dir("prod-1") == tmp_path / "instances" / "prod-1"


@pytest.mark.parametrize("name", ["", "-bad", "Bad", "has space", "under_score", "a/b"])
def test_instance_dir_rejects_bad_names(name: str) -> None:
    with pytest.raises(ValueError, match="invalid instance name"):
        paths.instance_dir(name)
