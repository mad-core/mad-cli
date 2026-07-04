""".env parser/writer that preserves comments, ordering and blank lines.

A pure ``load`` then ``save`` round-trips the file byte-for-byte. Mutations
(:meth:`EnvFile.set`, :meth:`EnvFile.unset`) touch only the affected line:
``set`` rewrites an existing assignment in place or appends a new one at the
end, and ``unset`` drops the assignment line, leaving every comment and blank
line untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class _Line:
    """One physical line of the file.

    ``kind`` is ``"kv"`` for an assignment, ``"comment"`` for a ``#`` line and
    ``"blank"`` otherwise. ``text`` is the exact rendered line; ``key``/``value``
    are populated only for ``kv`` lines.
    """

    kind: str
    text: str
    key: str | None = None
    value: str | None = None


def _parse_kv(line: str) -> tuple[str, str] | None:
    """Return ``(key, value)`` if ``line`` is an assignment, else ``None``."""
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    if key.startswith("export "):
        key = key[len("export ") :]
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return key, value


class EnvFile:
    """Comment- and order-preserving representation of a ``.env`` file."""

    path: Path | None

    def __init__(self) -> None:
        self.path = None
        self._lines: list[_Line] = []
        self._final_newline: bool = False

    # ── constructors ────────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: Path) -> EnvFile:
        """Parse ``path`` tolerantly, preserving its exact layout."""
        obj = cls()
        obj.path = path
        obj._parse(path.read_text(encoding="utf-8"))
        return obj

    @classmethod
    def empty(cls) -> EnvFile:
        """Return a fresh, path-less, empty env file."""
        return cls()

    def _parse(self, text: str) -> None:
        self._lines = []
        if text == "":
            self._final_newline = False
            return
        self._final_newline = text.endswith("\n")
        body = text[:-1] if self._final_newline else text
        for raw in body.split("\n"):
            parsed = _parse_kv(raw)
            if parsed is not None:
                key, value = parsed
                self._lines.append(_Line("kv", raw, key=key, value=value))
            elif raw.lstrip().startswith("#"):
                self._lines.append(_Line("comment", raw))
            else:
                self._lines.append(_Line("blank", raw))

    # ── accessors ───────────────────────────────────────────────────────────
    def get(self, key: str) -> str | None:
        """Return the value of ``key`` (first assignment wins), else ``None``."""
        for line in self._lines:
            if line.kind == "kv" and line.key == key:
                return line.value
        return None

    def set(self, key: str, value: str) -> None:
        """Set ``key`` to ``value``, rewriting in place or appending at the end."""
        for line in self._lines:
            if line.kind == "kv" and line.key == key:
                line.value = value
                line.text = f"{key}={value}"
                return
        self._lines.append(_Line("kv", f"{key}={value}", key=key, value=value))

    def unset(self, key: str) -> None:
        """Remove every assignment of ``key`` (no-op if absent)."""
        self._lines = [line for line in self._lines if not (line.kind == "kv" and line.key == key)]

    def add_comment(self, text: str) -> None:
        """Append a comment line (used to leave documented, inactive references).

        ``text`` is written verbatim; a leading ``#`` is added if missing. The
        line is inert — it never shadows an assignment and :meth:`get`/:meth:`keys`
        ignore it — so it round-trips as a plain reference in the generated file.
        """
        rendered = text if text.lstrip().startswith("#") else f"# {text}"
        self._lines.append(_Line("comment", rendered))

    def keys(self) -> list[str]:
        """Return the assignment keys in file order."""
        return [line.key for line in self._lines if line.kind == "kv" and line.key is not None]

    # ── serialisation ───────────────────────────────────────────────────────
    def render(self) -> str:
        """Return the file contents as a single string."""
        body = "\n".join(line.text for line in self._lines)
        if self._final_newline:
            return body + "\n"
        return body

    def save(self, path: Path | None = None) -> None:
        """Write the file to ``path`` (or the loaded path) byte-stably."""
        target = path or self.path
        if target is None:
            raise ValueError("no path to save to; pass an explicit path")
        target.write_text(self.render(), encoding="utf-8")
        self.path = target
