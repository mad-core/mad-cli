"""Tests for mad_cli.core.pypi."""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from mad_cli.core import pypi


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def test_latest_version_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"info": {"version": "1.4.2"}}).encode("utf-8")

    def fake_urlopen(url: str, timeout: float = 5.0) -> _FakeResponse:
        return _FakeResponse(payload)

    monkeypatch.setattr(pypi.urllib.request, "urlopen", fake_urlopen)
    assert pypi.latest_version("mad-edge") == "1.4.2"


def test_latest_version_404_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: float = 5.0) -> Any:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(pypi.urllib.request, "urlopen", fake_urlopen)
    assert pypi.latest_version("does-not-exist") is None


def test_latest_version_timeout_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: float = 5.0) -> Any:
        raise TimeoutError("timed out")

    monkeypatch.setattr(pypi.urllib.request, "urlopen", fake_urlopen)
    assert pypi.latest_version("mad-edge") is None


def test_latest_version_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: float = 5.0) -> _FakeResponse:
        return _FakeResponse(b"not json")

    monkeypatch.setattr(pypi.urllib.request, "urlopen", fake_urlopen)
    assert pypi.latest_version("mad-edge") is None


def test_latest_version_missing_info(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"nope": {}}).encode("utf-8")

    def fake_urlopen(url: str, timeout: float = 5.0) -> _FakeResponse:
        return _FakeResponse(payload)

    monkeypatch.setattr(pypi.urllib.request, "urlopen", fake_urlopen)
    assert pypi.latest_version("mad-edge") is None
