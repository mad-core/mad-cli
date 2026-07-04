# CHANGELOG


## v0.4.0 (2026-07-04)

### Documentation

- Document named environment profiles
  ([`6bbf294`](https://github.com/mad-core/mad-cli/commit/6bbf294ecf112993235a5a32719f1731b44ebf61))

Update the living-docs for `mad profiles` and `mad install --profile`: cli.md (new profiles command
  family + --profile row), components.md (the new core/profiles.py and commands/profiles.py
  modules), configuration.md (profiles storage + precedence), installation.md (--profile),
  cli-design.md (masking + restart hint), testing-strategy.md (new test modules); regenerate the
  deterministic source-tree/test-tree; re-acknowledge the affected docs.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- Document the HTTP API, service mode and the use-case layer
  ([`a1fc77e`](https://github.com/mad-core/mad-cli/commit/a1fc77ec9941692c70483a92b4bb8c7a5bda687d))

Add docs/03-contracts/http-api.md (routes, bearer auth, always-masked secrets, error mapping, the
  synchronous-MVP limitation) and register it in the manifest. Extend cli.md with `mad serve` / `mad
  service`, README with the `server` extra and the auto-provisioned server venv, and refresh the
  architecture/convention pages for the new use-case layer, the server package, service-mode config
  (api-token, server-venv) and the optional fastapi/uvicorn deps. Regenerate the deterministic
  source/test trees and bump the manifest acknowledgements.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- Re-ack installation.md after server-extra coverage
  ([`a2da5f9`](https://github.com/mad-core/mad-cli/commit/a2da5f9cda21db3af53d4fa8855e6a9e767df135))

The page already documents the [server] extra and mad service flow; its acknowledgement lagged the
  commit that changed its trigger paths.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Features

- **cli**: Local HTTP API with CLI parity and mad service mode
  ([`09f30e1`](https://github.com/mad-core/mad-cli/commit/09f30e16b25a5534f2b87c64e7fa0774cbd9ca69))

Expose every CLI capability over a local HTTP API so a UI/dashboard can build on the same use cases.
  Shipped as an optional `server` extra (fastapi + uvicorn) so the base CLI stays a two-dependency
  package — `import mad_cli.app` never pulls in FastAPI. The FastAPI routes are thin adapters over
  core.usecases, giving OpenAPI for free and parity with the CLI by construction.

Security: binds 127.0.0.1 by default; a bearer token is auto-generated at config_root()/api-token
  (0600) and required on every route except /health; a non-loopback --host prints a loud warning.
  Secret values are always masked on reads — no reveal flag exists on the API.

Service mode: `mad serve` runs the API in the foreground; `mad service
  install|uninstall|status|update` manages a boot-persistent service (systemd user unit on Linux,
  launchd LaunchAgent on macOS) rendered from packaged templates. When the server extra is not
  importable, `mad service install` auto-provisions a dedicated venv under config_root()/server-venv
  (from PyPI, or a local wheel via --wheel) and points ExecStart at it. `--render-to PATH` writes
  the unit/plist without touching systemctl/launchctl.

MVP limitation: install-with-start, start and update run synchronously.

Closes #11

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- **cli**: Named environment profiles for install and config
  ([`bd1131b`](https://github.com/mad-core/mad-cli/commit/bd1131b18aa04db77b77343ad01f0ee7bfff68a0))

Add reusable, named sets of .env values ("profiles") so operators can stamp consistent credentials
  and tuning across instances and servers.

- core/profiles.py: framework-free storage at config_root()/profiles/<name>.env via EnvFile (chmod
  0600), with list/load/save/delete, name validation and the IDENTITY_KEYS set a profile never
  carries (MAD_INSTANCE, MAD_HOST_PORT, PUID, PGID, MAD_DATA_PATH, MAD_VERSION). -
  commands/profiles.py: `mad profiles create|list|show|delete|apply`. create seeds from an instance
  (identity keys excluded) and/or --set KEY=VALUE; show masks secret-looking values; apply overlays
  a profile onto an instance's .env with a restart hint. - install.py: `mad install --profile NAME`
  feeds the profile's values as the wizard defaults (precedence: explicit flag > profile > builtin
  default), merged into the single existing default layer.

Closes #10

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Refactoring

- Extract framework-free use-case layer
  ([`5589ab8`](https://github.com/mad-core/mad-cli/commit/5589ab86c55f6bae64908ba505df153969b36493))

Move the orchestration that lived in commands/*.py into a framework-free use-case layer
  (mad_cli.core.usecases): instances, lifecycle, configvals, keys, versions, adopt and install, plus
  a shared error vocabulary. The Typer commands become thin adapters over these use cases
  (parse/prompt/present only), so the CLI and the forthcoming HTTP API cannot drift.

Secret detection (is_secret_key) and a display_value helper move into core.keyspec so both surfaces
  share one masking rule; commands/_common.py re-exports it. The status-line helpers now escape
  their message text so literal brackets (e.g. an [A-Z][A-Z0-9_]* pattern) are printed verbatim
  instead of being swallowed as rich markup.

The existing command tests stay the behavioural safety net: only the mock targets moved to the new
  module locations; no assertion was weakened. CONTRACTS.md gains the core.usecases + keyspec +
  (upcoming) server sections.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>


## v0.3.2 (2026-07-04)

### Chores

- **ci**: Add living-docs docs-validate and docs-sync caller workflows
  ([`bc1bff6`](https://github.com/mad-core/mad-cli/commit/bc1bff6bca7cddd5b4ed12af8d9d51d8be32ab65))

Thin callers for the shared reusable workflows in mad-core/.github, parameterized with service_slug:
  mad-cli. docs-validate gates each PR to main on a clean docs structure lint; docs-sync mirrors
  docs/ into mad-core/mad-docs under raw/mad-cli/ after merge to main.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Documentation

- Bootstrap and author living-docs tree for mad-cli
  ([`5adb6b3`](https://github.com/mad-core/mad-cli/commit/5adb6b39addbb0c8e5ee359566d3229bf058b8ea))

Add docs/.docs-manifest.yaml (service mad-cli, area backend) and the full /docs tree it declares,
  adapted from the org backend contract to what mad-cli is — an operator CLI with no HTTP/SSE/MCP
  surface and no database:

- 01-overview: passport, context, scope, glossary - 02-architecture: overview, components + the
  deterministic source/test trees - 03-contracts: the CLI command surface (cli.md) and external
  dependencies (the generic api-reference/data-model/events entries do not apply) - 04-conventions:
  cli-design, layering, quality, testing-strategy - 05-operations: installation, configuration,
  ci-cd, release - 06-history: changelog mirrored from the semantic-release CHANGELOG.md

Content is authored faithfully from src/mad_cli, CLAUDE.md, CONTRACTS.md, README.md and the
  workflows. The source/test trees are generated by gen_docs; every entry's acknowledged_at_commit
  is stamped at the CI-callers commit so the structure lint is clean.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- Document persistent session logs and new install options
  ([`16263ae`](https://github.com/mad-core/mad-cli/commit/16263aed5b4b8505f9120304bab896704bae939c))

Reflect the code changes in the living-docs tree and re-acknowledge every page the linter flagged at
  the code commit (4499532):

- 03-contracts/cli.md: new install options (--anthropic-api-key, repeatable --set-key,
  --retention-days, --mcp-allowed-hosts) and the refreshed summary. -
  05-operations/configuration.md: MAD_SESSIONS_DIR, MAD_SESSIONS_RETENTION_DAYS,
  MAD_MCP_ALLOWED_HOSTS, MAD_SSE_HEARTBEAT_S, and the new install paths for the
  anthropic/deepseek/linear/opencode credentials. - 05-operations/installation.md: the sessions bind
  mount (survives rebuilds; existing instances re-run `mad install`) and the extra install knobs. -
  03-contracts/external-dependencies.md: the sessions mount + MAD_SESSIONS_DIR. -
  06-history/changelog.md: mirror the v0.3.0 and v0.3.1 releases.

The remaining flagged pages (components, cli-design, layering, quality, testing-strategy, release)
  needed no content change and are re-acknowledged.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Features

- **cli**: Ask for retention, extra API keys and MCP hosts during install
  ([`4499532`](https://github.com/mad-core/mad-cli/commit/4499532034431e6f0a16846041a0324f2d96600e))

`mad install` now collects several useful mad-edge settings up front so the operator no longer has
  to follow up with `mad config set`:

- --anthropic-api-key (secret, optional): alternative billing to the Claude OAuth token; prompted
  right after the Claude token. Writes ANTHROPIC_API_KEY. - --set-key ID=VALUE (repeatable): a
  builtin registry id (fanned out to its env vars) or a custom [A-Z][A-Z0-9_]* name written
  verbatim. claude-oauth is rejected — it has its own --claude-token. Interactive runs offer the
  same via a mini-loop after the main credentials. - --retention-days (>= 1, optional): writes
  MAD_SESSIONS_RETENTION_DAYS, else a commented reference (unset = keep forever). -
  --mcp-allowed-hosts (optional): writes MAD_MCP_ALLOWED_HOSTS, else a commented reference.
  MAD_SSE_HEARTBEAT_S is always left as a commented reference.

install also creates the per-instance sessions/ data dir and the summary panel now shows the
  sessions path, retention, MCP hosts and the extra keys (masked).

EnvFile grows an additive add_comment() helper so the generated .env can carry documented, inert
  reference lines (get()/keys() ignore them).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- **templates**: Persist session logs via a dedicated bind mount
  ([`799e44e`](https://github.com/mad-core/mad-cli/commit/799e44e554aaa1d1a0cddd784b51a8aa4b9cb4d5))

mad-edge writes its JSONL session logs (its source of truth) under MAD_SESSIONS_DIR (default
  ./sessions inside the container). Because that path was never bind-mounted, a `mad update` rebuild
  destroyed every session.

Add a dedicated `<data_path>/<instance>/sessions:/sessions` bind mount, pin MAD_SESSIONS_DIR to
  /sessions in the compose `environment:` block (forced container-side like MAD_WORKSPACE_DIR, so
  the mount and the variable can never diverge), and create/own /sessions in the Dockerfile's
  non-root user block alongside /workspaces.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>


## v0.3.1 (2026-07-04)

### Bug Fixes

- **templates**: Tolerate host UID/GID collisions when creating the container user
  ([`cc4a022`](https://github.com/mad-core/mad-cli/commit/cc4a0221a462cf2b1627f35e3cdf7a00a7a491e1))

groupadd -g "${PGID}" fails with exit 4 when the host GID already exists in the base image — e.g.
  macOS operators have gid 20, which is Debian's dialout group. Reuse an existing group and allow a
  duplicate UID (useradd -o) instead of failing the build.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>


## v0.3.0 (2026-07-04)

### Features

- **cli**: Add versions, update and adopt; polish list inventory
  ([`534ed68`](https://github.com/mad-core/mad-cli/commit/534ed68a3dd3cfe0c074ed7311bdddb36109c9db))

Add `mad versions [INSTANCE]` (pinned / installed / latest-on-PyPI plus an update-available column),
  `mad update INSTANCE [--version X]` (re-pins MAD_VERSION in the .env and rebuilds from scratch),
  and `mad adopt` (migrates the legacy single-instance layout into instances/<name>/). Refresh `mad
  list` to Name / Port / State / Health / Version with best-effort state and health parsed from
  `docker compose ps`.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>


## v0.2.0 (2026-07-04)

### Features

- **cli**: Add `mad keys` and `mad config` commands
  ([`a525213`](https://github.com/mad-core/mad-cli/commit/a525213af6b5bd6173f9dbcd2308f46af2a3e20c))

Add two Typer sub-apps for v0.2 credential and configuration management, wired into the root app
  with minimal footprint.

`mad keys set|list|remove` manages credentials in an instance's .env: builtin keys from the keyspec
  registry fan a single value out to all their env vars (e.g. github -> GITHUB_TOKEN + GH_TOKEN),
  claude-oauth additionally materialises the container's .credentials.json (chmod 600) under
  <data_path>/<instance>/claude, and arbitrary [A-Z][A-Z0-9_]* names are written verbatim. Values
  are always masked on display; removing claude-oauth leaves the on-disk credentials file in place
  and reports where it is.

`mad config get|set|unset` is the general-purpose .env editor: get masks secret-looking values
  unless --reveal, set validates MAD_HOST_PORT and MAD_AGENT_TIMEOUT_S and warns that compose-baked
  keys need a regenerate to take effect, and every mutation ends with a restart hint.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Testing

- Cover keys/config against the real core
  ([`082ea6a`](https://github.com/mad-core/mad-cli/commit/082ea6a1944d3b8687caa75d41d760c6b4683619))

Add a make_real_instance fixture that writes instances/<name>/.env under a scratch
  MAD_CLI_CONFIG_DIR so the command tests exercise the unmocked engine end to end. Cover the builtin
  fan-out, the claude-oauth credentials file (0600) and its retention on remove, custom vars,
  masking, validation, instance resolution and the empty-config hint.

Also make the --version test version-agnostic: it pinned "0.1.0" and broke when release automation
  bumped __version__ to 0.1.1; it now asserts the output equals the package version.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>


## v0.1.1 (2026-07-04)

### Chores

- Add CI, release and TestPyPI preview workflows
  ([`b33c306`](https://github.com/mad-core/mad-cli/commit/b33c306dd047fd942c014d505633b6834148228c))

- ci.yml: ruff check + format, mypy, pytest on 3.11/3.12 with core coverage, pip-audit and a build +
  twine check gate (no import-linter, no pre-commit) - release.yml: python-semantic-release with
  PyPI trusted publishing, path-gated to src/mad_cli/**, pyproject.toml, README.md and LICENSE -
  testpypi-preview.yml: build/publish a .dev preview to TestPyPI per PR, gated by the
  TESTPYPI_ENABLED variable; verify installs the wheel and imports mad_cli

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- Install build inside the semantic-release container
  ([`2920d47`](https://github.com/mad-core/mad-cli/commit/2920d47a715da7920fe72c9ce1d4f8402460c3b5))

The python-semantic-release action runs build_command in its own container, where the runner's dev
  deps are not installed; plain `python -m build` fails with 'No module named build'. Mirror the
  mad-edge build_command, which installs build first.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Code Style

- Apply ruff format to command modules and tests
  ([`4e9beba`](https://github.com/mad-core/mad-cli/commit/4e9bebad8e2623678f67ba3cd67fc908de718508))

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Documentation

- Add operator README and contributor CLAUDE.md
  ([`4514866`](https://github.com/mad-core/mad-cli/commit/45148660d16f9f84ec2c02c7beadfc8acbcfd633))

README: operator quickstart (pip install mad-cli -> mad install -> mad start), what mad-cli is, the
  v0.1-v0.3 command table, its relationship to mad-edge, the alpha 0.x status and PyPI + CI badges.

CLAUDE.md: project summary and hard rules (DCO sign-off, Conventional Commits with the public scope
  set {cli, config, templates, deps}, the core/commands layering rule, CONTRACTS.md as source of
  truth, Docker-free tests, mad-edge versioning policy).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

### Features

- **cli**: Guided install wizard
  ([`cfdc18f`](https://github.com/mad-core/mad-cli/commit/cfdc18f44762ced51ad495fdf10a32deea9e63a9))

Port mad/scripts/configure.sh to `mad install` with an English UI: Docker preflight (offer install
  on Linux, actionable errors elsewhere), a CLI flag for every parameter that skips its prompt, and
  idempotent reconfiguration that pre-fills defaults from an existing instance's .env. Assemble the
  EnvFile (same keys as the bash script), render the instance files and write the Claude credentials
  through mad_cli.core, then print a masked summary panel and — unless --no-start — build, start and
  wait for health. --yes runs non-interactively and exits cleanly, naming the missing flag, when a
  required value such as --github-token is absent.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- **cli**: Implement framework-free core engine
  ([`282720c`](https://github.com/mad-core/mad-cli/commit/282720c75afc1e5aa0de4403831d1f3e96b2bcfa))

Replace the core contract stubs with working implementations, honouring CONTRACTS.md and keeping
  mad_cli.core free of typer/rich (mypy --strict):

- paths: MAD_CLI_CONFIG_DIR-aware config root + instance name validation - envfile:
  comment/order-preserving .env parser with byte-stable round-trip - instance: modern + legacy
  instance discovery and typed accessors - keyspec: builtin key registry (github fan-out) and safe
  masking - claude_creds: claudeAiOauth credentials file, chmod 0600 - pypi: latest_version via the
  PyPI JSON API (stdlib urllib, fail-soft) - docker_check: docker/daemon/compose-v2 detection +
  opt-in Linux install - compose: instance-scoped docker compose runner with health polling

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- **cli**: Lifecycle/inventory commands, app wiring and tests
  ([`812fcbe`](https://github.com/mad-core/mad-cli/commit/812fcbe9dc723c37ca3ca4b48b5e586964d44ca6))

Add `mad start|stop|restart|status|logs|shell [INSTANCE]` with optional INSTANCE resolution (the
  sole instance via default_instance, else an actionable error that hints `mad install` or lists
  candidates), and the `mad list` / `mad info NAME` inventory commands (best-effort state, secrets
  masked). Wire the Typer app (eager --version callback, no_args_is_help) plus the `mad`
  console-script and `python -m mad_cli` entry points. Cover the whole surface with CliRunner tests
  that mock mad_cli.core throughout, so any un-mocked core call fails loudly.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- **cli**: Rich console and prompt helpers
  ([`80eec20`](https://github.com/mad-core/mad-cli/commit/80eec20d941399637dc74bac08d2c14aa8e83812))

Add the mad-cli presentation layer: a shared rich Console with info/ok/warn/error/header status
  helpers and a run_step spinner, plus ask/confirm prompts that honour the non-interactive contract
  — return the default or raise PromptRequiredError when stdin is not a TTY, and re-prompt while a
  validator raises ValueError. Seed the commands package with its secret-key masking helper.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- **templates**: Render instance files from packaged templates
  ([`940a204`](https://github.com/mad-core/mad-cli/commit/940a20446991cca82769f8accd21c5d95c25360a))

Add the string.Template package data (Dockerfile.tmpl, compose.yml.tmpl, entrypoint.sh.tmpl) and the
  core renderer that fills them. Faithfully ports the
  write_dockerfile/write_compose/write_entrypoint heredocs from the tested configure.sh
  (node:20-slim, gh CLI, claude-code + opencode, /opt/venv, non-root mad user, EXPOSE 8000,
  /openapi.json healthcheck, gh auth login entrypoint).

Deliberate change vs the bash: the pip package is parameterised via RenderContext.edge_package
  (default mad-edge), and the container start binary is resolved in Python (mad-edge, or mad for the
  mad-bros package) and passed as the ${edge_entrypoint} placeholder. Literal $ is escaped as $$ so
  string.Template substitutes only the intended placeholders.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>


## v0.1.0 (2026-07-03)

### Chores

- Add core contract stubs so commands can build in parallel
  ([`0263860`](https://github.com/mad-core/mad-cli/commit/02638602ae9e3b1411664bd03fb4753ebd1bea1f))

Every module under mad_cli.core exists with its frozen CONTRACTS.md signature raising
  NotImplementedError. The commands branch imports and mocks these; the core branch replaces them
  with real implementations.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>

- Scaffold repo with frozen v0.1 interface contracts
  ([`a80a932`](https://github.com/mad-core/mad-cli/commit/a80a932217eba7dccb6f01894c07098a75bba500))

Base skeleton for the mad-cli operator tool: package metadata (hatchling, typer+rich, console script
  `mad`), MIT license, and CONTRACTS.md freezing the core/commands integration surface so the core
  engine and the Typer commands can be built in parallel.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01GWHBALtjHVd176YddWc9YP

Signed-off-by: Jose Salamanca <jose.salamancacoy@gmail.com>
