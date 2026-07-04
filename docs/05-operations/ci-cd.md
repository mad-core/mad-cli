---
service: mad-cli
domain: backend
section: operations
source_of_truth: repo
---

# CI/CD

Tests do not require Docker (the `docker` marker is deselected).

## `ci.yml`

Runs on push to `main` and on PR to `main`.

- `quality` — `ruff check` and `ruff format --check`; `mypy` strict on `mad_cli.core`.
- `test` — matrix over 3.11 and 3.12: unit tests plus coverage on `mad_cli.core` with `--cov-fail-under=90`, then the full `pytest -q` suite.
- `audit` — `pip-audit --strict --skip-editable .`.
- `build` — needs `quality` and `test`: `python -m build` plus `twine check dist/*`.

## `release.yml`

Runs on push to `main`, path-gated to `src/mad_cli/**`, `pyproject.toml`, `README.md`, `LICENSE`; plus `workflow_dispatch` with inputs `manual_publish` and `release_kind` (`auto`, `minor`, `major`).

- `manual-publish-pypi` — on dispatch with `manual_publish`: OIDC Trusted Publishing to PyPI.
- `release` — python-semantic-release; runs `pytest` first. `force` is set to the `release_kind` when dispatched non-auto.
- `publish-pypi` — when a release was cut: OIDC to PyPI.

## `testpypi-preview.yml`

Runs on PR to `main` and on dispatch; skipped for fork PRs.

- Derive a unique PEP 440 `<base>.dev<run_id>` version, build sdist + wheel, and `twine check`.
- `publish` — to TestPyPI, gated on the repo variable `TESTPYPI_ENABLED == 'true'`, via OIDC Trusted Publishing, environment `testpypi`.
- `verify` — installs the published wheel in a clean venv and imports `mad_cli`, then upserts install instructions on the PR.

## Living-docs workflows

These belong to the documentation system (the living-docs callers):

- `docs-validate.yml` — on PR to `main`: runs the org reusable structure linter (`gen_docs lint`) and gates the PR on zero findings.
- `docs-sync.yml` — on push to `main`: mirrors `docs/` into `mad-core/mad-docs` under `raw/mad-cli/` via a correlated PR. It requires the secrets `DOCS_SYNC_TOKEN` and `ANTHROPIC_API_KEY`.
