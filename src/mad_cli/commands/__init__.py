"""Typer command surface for the ``mad`` CLI.

Modules here own the operator-facing UX only; every side effect (docker,
filesystem, templating) is delegated to ``mad_cli.core`` per CONTRACTS.md.
"""
