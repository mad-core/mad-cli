# CHANGELOG


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
