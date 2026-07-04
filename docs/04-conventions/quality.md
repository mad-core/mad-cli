---
service: mad-cli
domain: backend
section: conventions
source_of_truth: repo
---

# Quality gates

Each gate below traces to `pyproject.toml` or `ci.yml`.

## ruff

Line length 100; `src = ["src", "tests"]`; lint select = `E`, `F`, `I`, `UP`,
`B`, `SIM`. Run `ruff check .` and `ruff format --check .`.

## mypy

`python_version = 3.11`, `mypy_path = src`, `packages = ["mad_cli"]`, with a
strict override on `mad_cli.core.*`. Run `mypy`.

## pip-audit

`pip-audit --strict --skip-editable .` (dependency vulnerability audit).

## pytest

`timeout = 15`. Markers: `docker` is deselected by default via
`addopts = -m 'not docker'`; `testpaths = ["tests"]`.

## Packaging gate

`python -m build` then `twine check dist/*`.

## CI jobs

From `ci.yml`:

- `quality` (ruff + mypy).
- `test` (matrix 3.11/3.12): unit plus coverage on `mad_cli.core` with
  `--cov-fail-under=90`, then the full `pytest -q`.
- `audit` (pip-audit).
- `build` (needs quality + test).

Everything must be green before a PR. Code, comments, docs and UI are in
English.
