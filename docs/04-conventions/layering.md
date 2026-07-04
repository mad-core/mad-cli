---
service: mad-cli
domain: backend
section: conventions
source_of_truth: repo
---

# Layering

The layering rules come from CLAUDE.md hard rule 3 and CONTRACTS.md.

## Boundaries

- `mad_cli.core` and `mad_cli.templates` never import `typer` or `rich`.
- `mad_cli.commands` and `mad_cli.ui` never touch `subprocess` or the
  filesystem directly; they go through `core`. Note that `core/compose.py` is
  the one module that shells out to Docker, and `docker_check` and `pypi` use
  `subprocess`/`urllib`, but they all live in `core`.

## Typing

`mad_cli.core` is checked under `mypy --strict`
(`[[tool.mypy.overrides]] module = "mad_cli.core.*"`, `strict = true`).

## Enforcement

There is no import-linter. The boundary is upheld by code review, mypy, and the
CONTRACTS.md freeze. CONTRACTS.md is the source of truth for the
core↔commands signatures: names, module paths and signatures must not change
without updating CONTRACTS.md in the same PR.

## Rationale

The split lets the framework-free engine and the Typer commands be built and
tested in parallel. Command tests mock `mad_cli.core`.
