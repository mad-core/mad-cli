"""Latest-version lookup via the PyPI JSON API (urllib, stdlib only)."""

from __future__ import annotations

import json
import urllib.request

_PYPI_JSON = "https://pypi.org/pypi/{package}/json"


def latest_version(package: str, timeout_s: float = 5.0) -> str | None:
    """Return the latest published version of ``package`` on PyPI, or ``None``.

    Any failure — unknown package (404), network error, timeout or malformed
    payload — yields ``None`` rather than raising, so callers can degrade
    gracefully when offline.
    """
    url = _PYPI_JSON.format(package=package)
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            raw = response.read()
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    info = data.get("info") if isinstance(data, dict) else None
    if not isinstance(info, dict):
        return None
    version = info.get("version")
    return version if isinstance(version, str) else None
