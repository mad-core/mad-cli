"""Framework-free use-case layer — the shared core of the CLI and the HTTP API.

Every operator capability lives here as a plain function that takes primitive
inputs, drives :mod:`mad_cli.core`, and returns dataclasses (never ``typer``,
``rich`` or ``fastapi`` objects). The Typer commands and the FastAPI routes are
thin adapters over these functions, so the two surfaces can never drift.

Expected, user-facing failures are raised as :class:`~mad_cli.core.usecases.errors.UseCaseError`
subclasses; each adapter maps them to its own idiom (``typer.Exit(1)`` / an HTTP
status code).
"""
