---
service: mad-cli
domain: backend
section: history
source_of_truth: repo
---

# Changelog

This page mirrors the semantic-release `CHANGELOG.md` at the repo root (consumer-facing, grouped per release) and is not a raw git log.

## v0.3.1 (2026-07-04)

### Bug Fixes

- **templates**: Tolerate host UID/GID collisions when creating the container user ([`cc4a022`](https://github.com/mad-core/mad-cli/commit/cc4a0221a462cf2b1627f35e3cdf7a00a7a491e1)) — `groupadd -g "${PGID}"` fails with exit 4 when the host GID already exists in the base image (e.g. macOS gid 20 is Debian's `dialout` group). Reuse an existing group and allow a duplicate UID (`useradd -o`) instead of failing the build.

## v0.3.0 (2026-07-04)

### Features

- **cli**: Add versions, update and adopt; polish list inventory ([`534ed68`](https://github.com/mad-core/mad-cli/commit/534ed68a3dd3cfe0c074ed7311bdddb36109c9db)) — Add `mad versions [INSTANCE]` (pinned / installed / latest-on-PyPI plus an update-available column), `mad update INSTANCE [--version X]` (re-pins `MAD_VERSION` in the `.env` and rebuilds from scratch), and `mad adopt` (migrates the legacy single-instance layout into `instances/<name>/`). Refresh `mad list` to Name / Port / State / Health / Version with best-effort state and health parsed from `docker compose ps`.

## v0.2.0 (2026-07-04)

### Features

- **cli**: Add `mad keys` and `mad config` commands ([`a525213`](https://github.com/mad-core/mad-cli/commit/a525213af6b5bd6173f9dbcd2308f46af2a3e20c)) — Two Typer sub-apps for v0.2 credential and configuration management, wired into the root app. `mad keys set|list|remove` manages credentials in an instance's `.env` (builtin keys fan one value out to their env vars, e.g. `github` → `GITHUB_TOKEN` + `GH_TOKEN`; `claude-oauth` also materialises `.credentials.json` chmod 600; arbitrary `[A-Z][A-Z0-9_]*` names written verbatim; values always masked). `mad config get|set|unset` is the general-purpose `.env` editor (masks secret-looking values unless `--reveal`, validates `MAD_HOST_PORT` and `MAD_AGENT_TIMEOUT_S`, warns that compose-baked keys need a regenerate, restart hint on every mutation).

### Testing

- Cover keys/config against the real core ([`082ea6a`](https://github.com/mad-core/mad-cli/commit/082ea6a1944d3b8687caa75d41d760c6b4683619)) — Add a `make_real_instance` fixture writing `instances/<name>/.env` under a scratch `MAD_CLI_CONFIG_DIR` so command tests exercise the unmocked engine. Make the `--version` test version-agnostic (assert output equals the package version).

## v0.1.1 (2026-07-04)

### Chores

- Add CI, release and TestPyPI preview workflows ([`b33c306`](https://github.com/mad-core/mad-cli/commit/b33c306dd047fd942c014d505633b6834148228c)) — `ci.yml` (ruff + format, mypy, pytest 3.11/3.12 with core coverage, pip-audit, build + twine check); `release.yml` (python-semantic-release with PyPI Trusted Publishing, path-gated); `testpypi-preview.yml` (per-PR `.dev` preview to TestPyPI gated by `TESTPYPI_ENABLED`; verify installs the wheel and imports `mad_cli`).
- Install build inside the semantic-release container ([`2920d47`](https://github.com/mad-core/mad-cli/commit/2920d47a715da7920fe72c9ce1d4f8402460c3b5)) — semantic-release runs `build_command` in its own container without the runner's dev deps; mirror the mad-edge `build_command` which installs `build` first.

### Code Style

- Apply ruff format to command modules and tests ([`4e9beba`](https://github.com/mad-core/mad-cli/commit/4e9bebad8e2623678f67ba3cd67fc908de718508))

### Documentation

- Add operator README and contributor CLAUDE.md ([`4514866`](https://github.com/mad-core/mad-cli/commit/45148660d16f9f84ec2c02c7beadfc8acbcfd633)) — README: operator quickstart, what mad-cli is, the v0.1–v0.3 command table, its relationship to mad-edge, alpha status, badges. CLAUDE.md: project summary and hard rules (DCO, Conventional Commits with the public scope set `{cli, config, templates, deps}`, the core/commands layering rule, CONTRACTS.md as source of truth, Docker-free tests, mad-edge versioning policy).

### Features

- **cli**: Guided install wizard ([`cfdc18f`](https://github.com/mad-core/mad-cli/commit/cfdc18f44762ced51ad495fdf10a32deea9e63a9)) — Port `configure.sh` to `mad install` with an English UI: Docker preflight, a CLI flag for every parameter that skips its prompt, idempotent reconfiguration pre-filling from an existing instance's `.env`, render the instance files, write Claude credentials, print a masked summary and (unless `--no-start`) build/start/wait for health. `--yes` runs non-interactively and names a missing required flag.
- **cli**: Implement framework-free core engine ([`282720c`](https://github.com/mad-core/mad-cli/commit/282720c75afc1e5aa0de4403831d1f3e96b2bcfa)) — Real implementations honouring CONTRACTS.md, `mad_cli.core` free of typer/rich (mypy `--strict`): paths, envfile (byte-stable round-trip), instance (modern + legacy discovery), keyspec (github fan-out, masking), claude_creds (0600), pypi (fail-soft), docker_check (+ opt-in Linux install), compose (instance-scoped runner with health polling).
- **cli**: Lifecycle/inventory commands, app wiring and tests ([`812fcbe`](https://github.com/mad-core/mad-cli/commit/812fcbe9dc723c37ca3ca4b48b5e586964d44ca6)) — `mad start|stop|restart|status|logs|shell [INSTANCE]` with optional-instance resolution, and `mad list` / `mad info NAME`. Wire the Typer app (eager `--version`, `no_args_is_help`) plus the `mad` and `python -m mad_cli` entry points; CliRunner tests mocking `mad_cli.core`.
- **cli**: Rich console and prompt helpers ([`80eec20`](https://github.com/mad-core/mad-cli/commit/80eec20d941399637dc74bac08d2c14aa8e83812)) — The presentation layer: a shared rich Console with info/ok/warn/error/header and a `run_step` spinner, plus ask/confirm honouring the non-interactive contract (default or `PromptRequiredError` off a TTY; re-prompt while a validator raises `ValueError`). Seed the commands package's secret-key masking helper.
- **templates**: Render instance files from packaged templates ([`940a204`](https://github.com/mad-core/mad-cli/commit/940a20446991cca82769f8accd21c5d95c25360a)) — The `string.Template` package data (`Dockerfile.tmpl`, `compose.yml.tmpl`, `entrypoint.sh.tmpl`) and the core renderer. Ports the `configure.sh` heredocs (node:20-slim, gh CLI, claude-code + opencode, /opt/venv, non-root mad user, EXPOSE 8000, /openapi.json healthcheck, gh auth entrypoint). The pip package is parameterised via `RenderContext.edge_package` (default `mad-edge`); the start binary is resolved in Python (mad-edge, or mad for mad-bros).

## v0.1.0 (2026-07-03)

### Chores

- Add core contract stubs so commands can build in parallel ([`0263860`](https://github.com/mad-core/mad-cli/commit/02638602ae9e3b1411664bd03fb4753ebd1bea1f)) — Every `mad_cli.core` module exists with its frozen CONTRACTS.md signature raising `NotImplementedError`, so the commands branch can import and mock them.
- Scaffold repo with frozen v0.1 interface contracts ([`a80a932`](https://github.com/mad-core/mad-cli/commit/a80a932217eba7dccb6f01894c07098a75bba500)) — Base skeleton: package metadata (hatchling, typer+rich, console script `mad`), MIT license, and CONTRACTS.md freezing the core/commands integration surface.
