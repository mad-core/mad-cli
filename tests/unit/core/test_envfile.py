"""Tests for mad_cli.core.envfile."""

from __future__ import annotations

from pathlib import Path

import pytest

from mad_cli.core.envfile import EnvFile

SAMPLE = """\
# Mad config — do not commit
MAD_INSTANCE=default

# github
GITHUB_TOKEN=ghp_abc
GH_TOKEN=ghp_abc
MAD_HOST_PORT=8080
"""


def test_round_trip_is_byte_stable(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text(SAMPLE, encoding="utf-8")
    env = EnvFile.load(src)
    dst = tmp_path / "out.env"
    env.save(dst)
    assert dst.read_bytes() == src.read_bytes()


def test_round_trip_without_trailing_newline(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text("A=1\nB=2", encoding="utf-8")
    env = EnvFile.load(src)
    dst = tmp_path / "out.env"
    env.save(dst)
    assert dst.read_bytes() == b"A=1\nB=2"


def test_get(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text(SAMPLE, encoding="utf-8")
    env = EnvFile.load(src)
    assert env.get("MAD_HOST_PORT") == "8080"
    assert env.get("MAD_INSTANCE") == "default"
    assert env.get("MISSING") is None


def test_get_strips_matched_quotes(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text('NAME="Jose Salamanca"\n', encoding="utf-8")
    env = EnvFile.load(src)
    assert env.get("NAME") == "Jose Salamanca"


def test_set_in_place_preserves_layout(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text(SAMPLE, encoding="utf-8")
    env = EnvFile.load(src)
    env.set("MAD_HOST_PORT", "9090")
    assert env.get("MAD_HOST_PORT") == "9090"
    rendered = env.render()
    # Comments and ordering are untouched; only the value changed.
    assert "# github" in rendered
    assert rendered.index("MAD_INSTANCE") < rendered.index("GITHUB_TOKEN")
    assert "MAD_HOST_PORT=9090" in rendered
    assert "MAD_HOST_PORT=8080" not in rendered


def test_set_new_key_appends_at_end(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text(SAMPLE, encoding="utf-8")
    env = EnvFile.load(src)
    env.set("NEW_KEY", "value")
    assert env.keys()[-1] == "NEW_KEY"
    assert env.render().rstrip().endswith("NEW_KEY=value")


def test_unset_removes_only_the_assignment(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text(SAMPLE, encoding="utf-8")
    env = EnvFile.load(src)
    env.unset("GH_TOKEN")
    keys = env.keys()
    assert env.get("GH_TOKEN") is None
    assert "GH_TOKEN" not in keys
    assert "# github" in env.render()
    assert "GITHUB_TOKEN=ghp_abc" in env.render()


def test_unset_missing_is_noop(tmp_path: Path) -> None:
    env = EnvFile.empty()
    env.set("A", "1")
    env.unset("DOES_NOT_EXIST")
    assert env.keys() == ["A"]


def test_empty_and_keys_order() -> None:
    env = EnvFile.empty()
    env.set("Z", "1")
    env.set("A", "2")
    env.set("M", "3")
    assert env.keys() == ["Z", "A", "M"]


def test_add_comment_is_inert_reference() -> None:
    env = EnvFile.empty()
    env.set("A", "1")
    env.add_comment("B=  # a documented but inactive knob")
    env.add_comment("# already hashed stays as-is")
    # A comment never becomes an assignment: get()/keys() ignore it entirely.
    assert env.get("B") is None
    assert env.keys() == ["A"]
    rendered = env.render()
    assert "# B=  # a documented but inactive knob" in rendered
    assert "# already hashed stays as-is" in rendered


def test_add_comment_round_trips_as_comment(tmp_path: Path) -> None:
    env = EnvFile.empty()
    env.set("A", "1")
    env.add_comment("MAD_SSE_HEARTBEAT_S=  # heartbeat seconds")
    dst = tmp_path / ".env"
    env.save(dst)
    reloaded = EnvFile.load(dst)
    # The reference line reloads as a comment, not as a set key.
    assert reloaded.get("MAD_SSE_HEARTBEAT_S") is None
    assert reloaded.keys() == ["A"]


def test_save_without_path_raises() -> None:
    env = EnvFile.empty()
    env.set("A", "1")
    with pytest.raises(ValueError, match="no path to save"):
        env.save()


def test_empty_file_round_trips(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text("", encoding="utf-8")
    env = EnvFile.load(src)
    assert env.keys() == []
    dst = tmp_path / "out.env"
    env.save(dst)
    assert dst.read_bytes() == b""


def test_save_uses_loaded_path(tmp_path: Path) -> None:
    src = tmp_path / ".env"
    src.write_text("A=1\n", encoding="utf-8")
    env = EnvFile.load(src)
    env.set("A", "2")
    env.save()
    assert src.read_text(encoding="utf-8") == "A=2\n"
