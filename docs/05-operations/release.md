---
service: mad-cli
domain: backend
section: operations
source_of_truth: repo
---

# Release and versioning

Releases are driven by python-semantic-release from Conventional Commits, and follow the mad-edge versioning policy (CLAUDE.md hard rules 2 and 6).

## `[tool.semantic_release]`

- `version_toml = pyproject.toml:project.version`
- `version_variables = src/mad_cli/__init__.py:__version__`
- `build_command` installs `build` then runs `python -m build`
- `commit_parser = conventional`
- `tag_format = v{version}`
- `major_on_zero = false`
- `upload_to_vcs_release = true`
- branch `main`

## 0.x policy

- `patch_tags = [feat, fix, perf]`
- `minor_tags = []`

On 0.x a `feat` is demoted to a PATCH bump. Minor and major bumps are always deliberate — triggered by a `BREAKING CHANGE:` footer, or by the `release_kind` = `minor` | `major` `workflow_dispatch` input.

## Public scope set

For `feat` / `fix` / `perf`, the public scope set is `{cli, config, templates, deps}`. Internal work (engine refactors, tests, CI) ships as `refactor:` / `chore:` / `test:` and is filtered out of the CHANGELOG.

## Path-gated release trigger

Only changes under `src/mad_cli/**`, `pyproject.toml`, `README.md`, `LICENSE` move the version. Docs, tests and CI do not.

## Publishing

PyPI Trusted Publishing (OIDC, environment `pypi`). A `manual_publish` dispatch escape hatch builds and publishes the current tree.

## Pre-merge preview

Every same-repo PR builds a `.dev<run_id>` and — when `TESTPYPI_ENABLED` — publishes and verifies it on TestPyPI, so the exact built artifact can be `pip install`ed before merge.

## DCO

Every commit is signed off (`git commit -s`) — a required PR check.

See also [05-operations/ci-cd.md](ci-cd.md).
