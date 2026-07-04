"""Expected, user-facing failures raised by the use-case layer.

These are the vocabulary the adapters translate. The CLI turns any of them into
an ``error(...)`` line plus ``typer.Exit(1)``; the HTTP API maps each subclass to
a status code (see :data:`HTTP_STATUS`). They carry a human-readable message and
never wrap a stack trace the operator should not see.
"""

from __future__ import annotations


class UseCaseError(Exception):
    """Base class for expected failures surfaced to the operator."""


class ValidationError(UseCaseError, ValueError):
    """An input was malformed or out of range (bad port, unknown key id, …).

    Also a :class:`ValueError` so it satisfies the ``ui.prompts.ask`` validator
    contract (raise ``ValueError`` to re-prompt): the same validators back the
    interactive prompts and the non-interactive / HTTP paths.
    """


class NotFoundError(UseCaseError):
    """A referenced instance, key or value does not exist."""


class ConflictError(UseCaseError):
    """The requested state clashes with what already exists (instance exists)."""


class AmbiguousInstanceError(UseCaseError):
    """No instance was named and the target could not be inferred (0 or >1)."""


class PreconditionError(UseCaseError):
    """A precondition is unmet (Docker missing, no data path, health failed)."""


# Adapter hint: use-case error -> HTTP status. The CLI ignores this and exits 1.
HTTP_STATUS: dict[type[UseCaseError], int] = {
    ValidationError: 400,
    NotFoundError: 404,
    ConflictError: 409,
    AmbiguousInstanceError: 409,
    PreconditionError: 412,
}


def http_status_for(exc: UseCaseError) -> int:
    """Return the HTTP status code for ``exc`` (500 if unmapped)."""
    for cls in type(exc).__mro__:
        status = HTTP_STATUS.get(cls)
        if status is not None:
            return status
    return 500
