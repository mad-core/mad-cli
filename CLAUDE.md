# CLAUDE.md — mad-cli

Conventions and hard rules for anyone (human or Claude) working in this repo.

## What this project is

**mad-cli** is the operator CLI (`mad` console script) that installs and manages
**mad-edge** containers — the Mad runtime. It renders an instance's `Dockerfile`,
`compose.yml`, `.env` and `entrypoint.sh`, builds the image and drives the container
lifecycle through Docker Compose. It is not the agent runtime; that is `mad-edge`, installed
inside the container.

The package is split into a framework-free engine (`mad_cli.core`) and a Typer/Rich surface
(`mad_cli.commands` / `mad_cli.ui`) wired together by `mad_cli.app`.

## Hard rules — never break these

1. **Sign off every commit (DCO).** Every commit — human- or agent-authored — MUST carry a
   `Signed-off-by` trailer, always produced with `git commit -s`. Org policy, enforced by the
   DCO GitHub App as a required PR check.

2. **Conventional Commits with a closed public scope set.** `feat`/`fix`/`perf` are only for
   changes visible to a consumer of the package and MUST use one of the public scopes
   `{cli, config, templates, deps}`. Everything internal (engine refactors, tests, CI) ships
   as `refactor:`, `chore:` or `test:` and is filtered out of the CHANGELOG.

3. **Layering.** `mad_cli.core` and `mad_cli.templates` NEVER import `typer` or `rich`.
   `mad_cli.commands` / `mad_cli.ui` NEVER touch `subprocess` or the filesystem directly —
   they go through `core`. `mad_cli.core` is `mypy --strict`.

4. **`CONTRACTS.md` is the source of truth for signatures.** The names, module paths and
   signatures it lists MUST NOT change without updating `CONTRACTS.md` in the same PR.

5. **Tests do not require Docker by default.** The `docker` pytest marker is deselected by
   default (`addopts = -m 'not docker'`); everything that shells out to Docker is mocked.
   Plain `pytest -q` must pass on a machine with no Docker daemon.

6. **Versioning follows the mad-edge policy.** `feat` is demoted to a patch tag on 0.x;
   minor/major bumps are always deliberate (`BREAKING CHANGE:` footer or `release_kind`
   dispatch), never auto-derived from counting `feat`s. The release workflow path-gates the
   trigger to `src/mad_cli/**`, `pyproject.toml`, `README.md` and `LICENSE`.

## Layout

- `src/mad_cli/core/` — framework-free engine: paths, `.env` I/O, instance discovery, file
  templating, the Docker Compose runner, Docker detection, credentials, the key registry and
  the PyPI lookup. `mypy --strict`.
- `src/mad_cli/templates/` — packaged `string.Template` sources (`*.tmpl`) for the generated
  instance files. Literal `$` is escaped as `$$`; `${name}` are the render-time placeholders.
- `src/mad_cli/commands/`, `src/mad_cli/ui/`, `src/mad_cli/app.py` — the Typer surface.
- `tests/unit/core/` — unit tests for the engine (no Docker required).

## Commands

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # setup
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/mypy
.venv/bin/pytest -q
.venv/bin/python -m build && .venv/bin/twine check dist/*
```

All of the above must be green before opening a PR. Code, comments, docs and UI are in
English.
