"""The optional local HTTP API (the ``server`` extra).

Nothing here is imported by the base CLI (``mad_cli.app``); it is reached only via
``mad serve`` behind an import guard, so ``pip install mad-cli`` never pulls in
FastAPI/uvicorn. The routes are thin adapters over :mod:`mad_cli.core.usecases`,
exactly like the Typer commands, so the CLI and the API can never drift.

See :func:`mad_cli.server.app.create_app` for the FastAPI factory.
"""

from mad_cli.server.app import create_app

__all__ = ["create_app"]
