---
service: mad-cli
domain: backend
section: conventions
source_of_truth: repo
---

# Layering

The layering rules come from CLAUDE.md hard rule 3 and CONTRACTS.md.

## Boundaries

- `mad_cli.core` and `mad_cli.templates` never import `typer`, `rich` or
  `fastapi`. This includes the use-case layer `mad_cli.core.usecases`, which
  holds the orchestration shared by the CLI and the HTTP API.
- `mad_cli.commands`, `mad_cli.ui` and `mad_cli.server` never touch `subprocess`
  or the filesystem directly; they go through `core`. Note that `core/compose.py`
  is the one module that shells out to Docker, `docker_check`/`pypi` use
  `subprocess`/`urllib`, and `core/usecases/service.py` shells out to
  `python -m venv`/`pip` for the server-venv bootstrap — but they all live in
  `core`.
- `mad_cli.server` is the optional `server` extra: the base CLI never imports it
  (`import mad_cli.app` must not pull in FastAPI), so `mad serve` reaches it
  behind an import guard.

## The use-case layer

Both surfaces are **thin adapters** over `mad_cli.core.usecases`: a Typer command
and a FastAPI route call the exact same use-case function (parse/present only),
so the CLI and the API cannot drift. Use cases return dataclasses and raise
`UseCaseError` subclasses; each adapter maps them to its own idiom
(`typer.Exit(1)` / an HTTP status via `errors.http_status_for`).

## Typing

`mad_cli.core` — including `mad_cli.core.usecases` — is checked under
`mypy --strict` (`[[tool.mypy.overrides]] module = "mad_cli.core.*"`,
`strict = true`). `mad_cli.server` is type-checked in the normal (non-strict)
scope.

## Enforcement

There is no import-linter. The boundary is upheld by code review, mypy, and the
CONTRACTS.md freeze. CONTRACTS.md is the source of truth for the
core↔surface signatures: names, module paths and signatures must not change
without updating CONTRACTS.md in the same PR.

## Rationale

The split lets the framework-free engine, the Typer commands and the HTTP API be
built and tested in parallel. Command tests mock `mad_cli.core`; API tests use
`fastapi.testclient.TestClient`.
