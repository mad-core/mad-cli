---
service: mad-cli
domain: backend
section: operations
source_of_truth: repo
---

# Installing and running mad-cli

## Install the CLI

Install from PyPI:

```
pip install mad-cli
```

Requirements:

- Python >= 3.11 (tested on 3.11 and 3.12; Linux and macOS).
- Installing mad-cli pulls only `typer` and `rich`.

The package provides the `mad` console script, which can also be run as `python -m mad_cli`.

Docker is NOT needed to install the CLI, but it IS needed at runtime to actually run an instance.

## From source (contributors)

```
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

Then use `ruff`, `mypy`, `pytest` and `build`. See [04-conventions/quality.md](../04-conventions/quality.md).

## First run

Run the guided installer:

```
mad install
```

This renders the instance files under `~/.config/mad/instances/<name>/` (or under `$MAD_CLI_CONFIG_DIR`), creates the per-instance data directories (`workspaces/`, `sessions/`, `aws/`, `claude/` under `<data_path>/<instance>/`), and — unless `--no-start` is passed — builds and starts the container.

The `sessions/` directory is bind-mounted to `/sessions` in the container and pinned there via `MAD_SESSIONS_DIR`, so mad-edge's JSONL session logs (its source of truth) live on the host and survive a rebuild (`mad update`). Existing instances created before this change should re-run `mad install` (idempotent) to adopt the mount.

`mad install` can optionally collect a few extra mad-edge settings up front so you do not need follow-up `mad config set` calls: an alternative `--anthropic-api-key`, additional registry/custom keys via repeatable `--set-key ID=VALUE`, session-log retention via `--retention-days`, and MCP allowed hosts via `--mcp-allowed-hosts`. Omitted knobs are left as commented references in the `.env`.

Use `--yes` to run it non-interactively.

After install, manage the instance with:

```
mad start
mad status
```

## Alpha (0.x)

mad-cli is in alpha. Pin a version in production; interfaces may change between minor releases.

## Host CLI vs the provisioned instance

There are two distinct things:

- Installing mad-cli — a host-side install of the `mad` command.
- What mad-cli then provisions — the mad-edge container image, built from the Dockerfile that the CLI generates.

For the full command surface, see [03-contracts/cli.md](../03-contracts/cli.md).
