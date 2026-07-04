---
service: mad-cli
domain: backend
section: conventions
source_of_truth: repo
---

# Testing strategy

## Layout

Tests live under `tests/unit/{core,commands,ui}/` (unit only; there is no
integration or e2e tree). Core tests exercise the engine directly; command tests
use Typer's `CliRunner`.

## Docker-free contract

Per CLAUDE.md hard rule 5, the `docker` marker is deselected by default
(`addopts = -m 'not docker'`). Everything that shells out to Docker is mocked, so
a plain `pytest -q` passes on a machine with no Docker daemon.

## Mocking core

Command tests mock `mad_cli.core` throughout, so any un-mocked core call fails
loudly. A `make_real_instance` fixture writes `instances/<name>/.env` under a
scratch `MAD_CLI_CONFIG_DIR` to exercise the unmocked engine end-to-end for keys,
config and profiles.

## Compose dry run

`ComposeRunner(dry_run=True)` records the argv on `last_command`, so tests assert
the built command without executing Docker.

## Coverage and timeout

A 90% floor on `mad_cli.core` is enforced in CI (`--cov-fail-under=90`). The
per-test timeout is 15s.

## Test modules present

- `tests/unit/core/test_{claude_creds,compose,docker_check,envfile,instance,keyspec,paths,profiles,pypi,templates}.py`
- `tests/unit/commands/test_{app,config,install,instances,keys,lifecycle,profiles,versions}.py`
  (plus `conftest.py`)
- `tests/unit/ui/test_prompts.py`

See [02-architecture/test-tree.md](../02-architecture/test-tree.md) for the exact
tree.
