"""Adopt use case: migrate the legacy single-instance layout into ``instances/``.

The old layout kept ``compose.yml`` / ``.env`` / ``Dockerfile`` / ``entrypoint.sh``
directly under the config root; the modern layout stores them per instance. Only
those config files move — the instance's data (``MAD_DATA_PATH``) stays put.

Planning and applying are split so the CLI can show the plan and ask for
confirmation before anything moves; the API applies directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mad_cli.core.instance import discover_instances
from mad_cli.core.paths import instance_dir
from mad_cli.core.usecases.errors import ValidationError

# Config files that make up a legacy single-instance layout and move together.
ADOPT_FILES = ("compose.yml", ".env", "Dockerfile", "entrypoint.sh")


@dataclass(frozen=True)
class AdoptPlan:
    name: str
    source: Path
    target: Path
    movable: list[str]


def plan_adopt() -> AdoptPlan | None:
    """Return the pending adoption, or ``None`` when there is no legacy layout.

    Raises :class:`ValidationError` if the legacy instance name cannot be used as
    a target directory.
    """
    legacy = next((i for i in discover_instances() if getattr(i, "legacy", False)), None)
    if legacy is None:
        return None
    source = legacy.config_dir
    try:
        target = instance_dir(legacy.name)
    except ValueError as exc:
        raise ValidationError(f"cannot adopt {legacy.name!r}: {exc}") from exc
    movable = [name for name in ADOPT_FILES if (source / name).exists()]
    return AdoptPlan(name=legacy.name, source=source, target=target, movable=movable)


def apply_adopt(plan: AdoptPlan) -> AdoptPlan:
    """Move the planned config files into ``instances/<name>/``; return the plan."""
    plan.target.mkdir(parents=True, exist_ok=True)
    for name in plan.movable:
        (plan.source / name).rename(plan.target / name)
    return plan
