# mad-cli

[![PyPI](https://img.shields.io/pypi/v/mad-cli.svg)](https://pypi.org/project/mad-cli/)
[![CI](https://github.com/mad-core/mad-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/mad-core/mad-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/mad-cli.svg)](https://pypi.org/project/mad-cli/)

**Operator CLI for [Mad](https://github.com/mad-core).** `mad-cli` installs, runs and
manages **mad-edge** containers — the Mad runtime that provisions isolated workspaces and
launches autonomous coding agents (Claude Code, OpenCode, …) against your repositories.

`mad-cli` is the thing an operator installs on a server or a Raspberry Pi. It does **not**
run agents itself: it generates a `Dockerfile`, a `compose.yml` and a `.env`, builds the
image and drives the container lifecycle through Docker Compose. The agent runtime lives in
the [`mad-edge`](https://pypi.org/project/mad-edge/) package, which is installed *inside* the
container.

> **Alpha (0.x).** Interfaces may change between minor releases. Pin a version in production.

## Quickstart

```bash
pip install mad-cli

# Guided install: generates the config, builds the image, starts the container.
mad install

# Day-to-day lifecycle.
mad start        # build + up (detached)
mad status       # container state + API health
mad logs         # follow logs
mad stop         # stop, keeping workspace data on the host
```

`mad install` walks you through the instance name, host port, data path, GitHub token,
git identity and Claude OAuth token, then writes everything under `~/.config/mad` (override
with `MAD_CLI_CONFIG_DIR`) and starts the container. Once it is healthy the Mad HTTP/MCP API
is available on the port you chose.

## Commands

The surface grows across the early minor releases; everything below the current line is
planned.

| Command | Since | What it does |
|---|---|---|
| `mad install` | v0.1 | Guided setup: render config, build image, start the container. |
| `mad start` / `stop` / `restart` | v0.1 | Container lifecycle (`up --build` / `down` / `down`+`up`). |
| `mad status` | v0.1 | Container state and API health for an instance. |
| `mad logs` | v0.1 | Follow container logs. |
| `mad shell` | v0.1 | Open an interactive `bash` shell inside the container. |
| `mad list` | v0.2 | List every configured instance. |
| `mad info NAME` | v0.2 | Show one instance's resolved config. |
| `mad keys` | v0.2 | Set, rotate and mask API keys / tokens in `.env`. |
| `mad config` | v0.2 | Read and edit `.env` values safely. |
| `mad versions` / `update` | v0.3 | Show the latest published mad-edge and rebuild onto it. |

Instance-scoped commands take an optional `INSTANCE` argument; when exactly one instance is
configured it is used by default.

## How it relates to mad-edge

| | `mad-cli` (this package) | `mad-edge` |
|---|---|---|
| Runs on | the operator's host | inside the container |
| Console script | `mad` | `mad-edge` (server) |
| Role | install & lifecycle management | the agent runtime / HTTP + MCP API |
| Talks to | Docker, the filesystem, PyPI | Claude Code, OpenCode, GitHub, workspaces |

`mad-cli` pins or tracks the mad-edge version through the generated `Dockerfile`; the
container installs `mad-edge` from PyPI at build time. Version bumps follow the mad-edge
versioning policy.

## License

[MIT](LICENSE).
