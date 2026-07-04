---
service: mad-cli
domain: backend
section: contracts
source_of_truth: repo
---
# External Dependencies

The third parties mad-cli relies on, and their quirks and failure modes.

## Python runtime dependencies

- `typer >= 0.12`
- `rich >= 13.7`

## Docker CLI and Docker Compose v2

mad-cli shells out to `docker` and `docker compose`; it does not use a Docker SDK.

- **Detection** lives in `docker_check.py`, which probes `docker --version`, `docker info`, and `docker compose version`.
- **The compose runner argv** is scoped: `docker compose -p mad-<name> -f compose.yml --env-file .env <verb>`.
- **Health** is read with `docker inspect --format {{.State.Health.Status}}`.
- **Opt-in install:** on Linux, `mad install` can install Docker via get.docker.com (opt-in).
- **Errors:** a non-zero compose command raises `ComposeError` (the stderr is scrubbed into the message). Missing Docker, a stopped daemon, or missing Compose v2 produce actionable errors that stop `install`.

## PyPI

1. mad-cli itself is `pip install`ed from PyPI.
2. The latest mad-edge version is looked up via `https://pypi.org/pypi/<package>/json` (stdlib `urllib`, 5s timeout, fail-soft to `None`, shown as `?`).

## The rendered container image

Produced from the packaged templates:

- Base image `node:20-slim`.
- apt installs `ca-certificates`, `curl`, `git`, `gnupg`, `python3` (plus `venv` and `pip`), and the `gh` CLI.
- npm installs `@anthropic-ai/claude-code` and `opencode-ai`.
- A venv at `/opt/venv` pip-installs the edge package (`mad-edge` by default, pinned or latest).
- A non-root `mad` user (`PUID`/`PGID`).
- `EXPOSE 8000`.
- A `HEALTHCHECK` that curls `/openapi.json`.
- The entrypoint authenticates `gh` with `GITHUB_TOKEN`, then execs `<edge-entrypoint> serve --host 0.0.0.0 --port 8000`.
- `compose.yml` maps `host_port:8000` and bind-mounts `data_path/<instance>/{workspaces, claude, aws:ro}`.

## mad-edge relationship

mad-cli pins or tracks the mad-edge version through the generated Dockerfile; the container installs mad-edge from PyPI at build time.

## Failure modes

- Docker missing, daemon down, or Compose v2 missing → actionable errors (they stop `install`).
- PyPI offline → the latest-version lookup fails soft to `None`, shown as `?`.
- A non-zero compose command → `ComposeError` (stderr scrubbed into the message).
