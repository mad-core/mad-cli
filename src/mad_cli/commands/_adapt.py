"""Shared CLI adapter helpers: instance resolution and use-case error mapping.

The command modules are thin adapters over :mod:`mad_cli.core.usecases`; this maps
the framework-free :class:`~mad_cli.core.usecases.errors.UseCaseError` vocabulary
onto the CLI idiom (an ``error(...)`` line plus ``typer.Exit(1)``) with the
operator-facing hints (``mad install`` / ``mad list``).
"""

from __future__ import annotations

from typing import NoReturn

import typer

from mad_cli.core.instance import Instance
from mad_cli.core.usecases import instances as uc_instances
from mad_cli.core.usecases.errors import AmbiguousInstanceError, NotFoundError, UseCaseError
from mad_cli.ui.console import error


def die(msg: str) -> NoReturn:
    """Print an error and exit non-zero."""
    error(msg)
    raise typer.Exit(1)


def fail(exc: UseCaseError) -> NoReturn:
    """Render a use-case failure verbatim and exit non-zero."""
    die(str(exc))


def resolve_or_die(name: str | None) -> Instance:
    """Resolve ``name`` (or the sole instance) or exit with an actionable hint."""
    try:
        return uc_instances.resolve_instance(name)
    except NotFoundError:
        if name is not None:
            die(f"Instance {name!r} not found. Run `mad list` to see available instances.")
        die("No instances found. Run `mad install` first.")
    except AmbiguousInstanceError as exc:
        die(str(exc))
