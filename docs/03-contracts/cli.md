---
service: mad-cli
domain: backend
section: contracts
source_of_truth: repo
---
# CLI Command Reference

The complete `mad` command surface — the operator-facing contract. Every command, argument, option, and default below is drawn from the Typer definitions.

## Instance resolution (shared rule)

Wherever a command takes an optional `INSTANCE` argument or a `--instance` / `-i` option, it is optional when exactly one instance exists (that sole instance is used by default); otherwise you must name it. With zero instances the command errors with a hint to run `mad install`; with several, it errors listing the instance names.

## Global

`mad` is a Typer application. Running it with no arguments prints help.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `--version` | — | Print the version and exit (eager). |
| (no arguments) | — | `no_args_is_help`: bare `mad` prints help. |

## install

`mad install` — install or reconfigure a mad-edge instance.

Each option is optional, and supplying its flag skips the matching interactive prompt. Re-running against an existing instance pre-fills defaults from its `.env`.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `--name` | `default` | Instance name. |
| `--port` | `8080` | Host port. |
| `--data-path` | `~/mad-data` | Host data path. |
| `--timeout` | `600` | Agent wall-clock seconds. |
| `--github-token` | required | Agent clones/pushes/PRs. |
| `--git-name` | — | Git author name. |
| `--git-email` | — | Git author email. |
| `--claude-token` | — | Claude OAuth token; run `claude setup-token`. |
| `--anthropic-api-key` | — | Anthropic API key (secret, optional — alternative billing to the Claude OAuth token). Prompted right after the Claude token. Writes `ANTHROPIC_API_KEY`. |
| `--set-key ID=VALUE` | — (repeatable) | Extra API key. `ID` is a builtin registry id (fanned out to its env vars) or a custom `[A-Z][A-Z0-9_]*` VAR name (written verbatim). `claude-oauth` is rejected here — it has its own `--claude-token`. In interactive mode a mini-loop offers the same after the main credentials. |
| `--profile NAME` | — | Named profile whose values seed the wizard defaults. Precedence is explicit flag > profile > built-in default; a profile never carries instance identity (see `mad profiles`). An unknown profile exits 1. |
| `--retention-days` | — (omit = keep forever) | Session-log retention in days (integer ≥ 1). When given, writes `MAD_SESSIONS_RETENTION_DAYS`; otherwise it is left as a commented reference. |
| `--mcp-allowed-hosts` | — (blank = disabled) | Comma-separated MCP allowed hosts for DNS-rebinding protection. When given, writes `MAD_MCP_ALLOWED_HOSTS`; otherwise left as a commented reference. |
| `--edge-package` | (hidden) | Override the mad-edge package name. |
| `--edge-version` | — (blank = latest) | Pin mad-edge. |
| `--yes` / `-y` | — | Non-interactive: use flags + defaults, never prompt. |
| `--no-start` | — | Write config but don't start. |

Behaviour: Docker preflight (offers to install on Linux, an actionable error elsewhere); writes the instance files under the config dir; creates the data dirs (`workspaces/`, `sessions/`, `aws/`, `claude/`); writes Claude credentials if a token was given; leaves commented references for the un-prompted `.env` knobs (`MAD_SESSIONS_RETENTION_DAYS`, `MAD_MCP_ALLOWED_HOSTS`, `MAD_SSE_HEARTBEAT_S`) when they are not set; prints a masked summary (instance, port, data path, sessions path, timeout, session retention, extra keys, MCP hosts); and unless `--no-start`, builds, starts, and waits for health. In `--yes` / non-TTY mode a missing required value (for example `--github-token`) exits 1 naming the flag.

## Lifecycle

Each lifecycle command takes an optional `INSTANCE` argument (see the shared instance-resolution rule).

| Command | Purpose |
| --- | --- |
| `mad start [INSTANCE]` | Build if needed, then up (detached) and wait for health. |
| `mad stop [INSTANCE]` | Down (stop and remove the containers). |
| `mad restart [INSTANCE]` | Down, then up (rebuild). |
| `mad status [INSTANCE]` | Container state, health summary, and URL. |
| `mad logs [INSTANCE]` | Follow the container logs (interactive). |
| `mad shell [INSTANCE]` | Open an interactive `bash` inside the container. |

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `INSTANCE` | sole instance | Which instance to act on (optional per the shared rule). |

## Inventory

### `mad list`

List every configured instance.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| (none) | — | Prints a table with columns Name, Port, State, Health, Version. State/health are best-effort; legacy instances are tagged `(legacy)`. |

### `mad info NAME`

Show an instance's paths and `.env` values.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `NAME` | required | Which instance to describe. |

Shows the paths (config dir, compose file, data path) plus the `.env` values, with secrets masked.

### `mad adopt`

Migrate the legacy single-instance layout into `instances/<name>/`.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| (none) | — | Moves `compose.yml` / `.env` / `Dockerfile` / `entrypoint.sh`; the data path is NOT moved. Warns that the compose project name changes and to stop the legacy container first, and asks for confirmation. |

## Versions

### `mad versions [INSTANCE]`

Report the version state of one or all instances.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `INSTANCE` | all instances | Which instance to report; when omitted, reports every instance. |

Prints a table with columns Name / Pinned / Installed / Latest on PyPI / Update. Installed is the version reported by `mad` inside the running container (best-effort; `not running` when stopped). Latest comes from the PyPI JSON API.

### `mad update INSTANCE`

Re-pin and rebuild an instance.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `INSTANCE` | required | Which instance to update. |
| `--version` | — (omit or blank = track latest) | Pin `MAD_VERSION`. |

Re-pins `MAD_VERSION` in `.env` and rebuilds from scratch (`build --no-cache`, up, wait for health).

## keys

`mad keys` is a sub-app that prints help with no subcommand. Every subcommand takes `--instance` / `-i` (see the shared instance-resolution rule). `keys` is the credential-aware front end over the `.env`.

### `mad keys set KEY [VALUE]`

Set a credential.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `KEY` | required | A builtin id (`claude-oauth`, `anthropic`, `github`, `deepseek`, `linear`, `opencode`) or a custom VAR name matching `[A-Z][A-Z0-9_]*`. |
| `VALUE` | prompted (masked) when omitted | The value to set. |
| `--instance` / `-i` | sole instance | Which instance. |

A builtin fans one value out to its env var(s); `claude-oauth` additionally writes the container's `.credentials.json` (`chmod 600`). Ends with a restart hint.

### `mad keys list`

List the keys.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `--instance` / `-i` | sole instance | Which instance. |

Prints a table of the builtin keys (id, env vars, set/unset, masked value) plus any custom secret vars.

### `mad keys remove KEY`

Remove a key.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `KEY` | required | A builtin id (removes its env vars) or a custom var. |
| `--instance` / `-i` | sole instance | Which instance. |

Removing `claude-oauth` leaves the on-disk credentials file in place and reports its path.

## config

`mad config` is a sub-app that prints help with no subcommand — the general-purpose `.env` editor (`keys` is the credential-aware front end). Every subcommand takes `--instance` / `-i` (see the shared instance-resolution rule).

### `mad config get [KEY]`

Print a value or the whole `.env`.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `KEY` | all keys | Print one value; when omitted, print the whole `.env` as a table. |
| `--reveal` | — | Show secret-looking values unmasked (masked by default). |
| `--instance` / `-i` | sole instance | Which instance. |

### `mad config set KEY VALUE`

Write a value.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `KEY` | required | The key to write. |
| `VALUE` | required | The value to write. |
| `--instance` / `-i` | sole instance | Which instance. |

Validates `MAD_HOST_PORT` (1–65535) and `MAD_AGENT_TIMEOUT_S` (positive integer); warns that compose-baked keys (`MAD_HOST_PORT`, `MAD_DATA_PATH`) need the instance regenerated to take effect; ends with a restart hint.

### `mad config unset KEY`

Remove a key.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `KEY` | required | The key to remove. |
| `--instance` / `-i` | sole instance | Which instance. |

## profiles

`mad profiles` is a sub-app that prints help with no subcommand. A *profile* is a reusable, named set of `.env` values (credentials + tuning, never instance identity) stored at `~/.config/mad/profiles/<name>.env` (`chmod 600`). The name follows the instance-name rule `[a-z0-9][a-z0-9-]*`.

### `mad profiles create NAME`

Create a profile, empty or seeded from an instance, plus optional `KEY=VALUE` pairs.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `NAME` | required | Profile name (`[a-z0-9][a-z0-9-]*`). Errors if it already exists. |
| `--from-instance INST` | — | Seed from an instance's `.env`. The instance-identity keys (`MAD_INSTANCE`, `MAD_HOST_PORT`, `PUID`, `PGID`, `MAD_DATA_PATH`, `MAD_VERSION`) are always excluded; credentials and tuning are copied. |
| `--set KEY=VALUE` | — (repeatable) | Set a variable in the profile. `KEY` must match `[A-Z_][A-Z0-9_]*`. |

On a real terminal, after applying `--set`, an optional mini-loop offers to add more `KEY=VALUE` pairs interactively (the value is hidden only for secret-looking keys). The created profile is printed with secret-looking values masked.

### `mad profiles list`

List every stored profile with its variable count. Hints `mad profiles create` when there are none.

### `mad profiles show NAME`

Print a profile's variables (secret-looking values masked).

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `NAME` | required | Profile to display. A missing profile exits 1. |
| `--reveal` | — | Show secret values in full (masked by default). |

### `mad profiles delete NAME`

Delete a profile.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `NAME` | required | Profile to delete. A missing profile exits 1. |
| `--yes` / `-y` | — | Skip the confirmation prompt. Without it, a non-TTY run aborts (nothing deleted). |

### `mad profiles apply NAME INSTANCE`

Overlay a profile's variables onto an instance's `.env` (each profile key is set on the instance), then print a restart hint. A missing profile or instance exits 1.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `NAME` | required | Profile to apply. |
| `INSTANCE` | required | Instance to overlay onto. |

The `--profile` flag on `mad install` seeds the wizard defaults from a profile (explicit flag > profile > built-in default).

## Service mode (HTTP API)

The local HTTP API lives in the optional `server` extra (`pip install 'mad-cli[server]'`). The base CLI stays a two-dependency package; the commands below are always present, but `mad serve` needs the extra (or a provisioned server venv). See [`http-api.md`](http-api.md) for the API surface and auth.

### `mad serve`

Run the HTTP API in the foreground (uvicorn). Generates the bearer token at `config_root()/api-token` (mode 0600) on first run.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address. A non-loopback value prints a loud warning. |
| `--port` | `7373` | Bind port. |

If the `server` extra is not importable in the current environment it hands off to `config_root()/server-venv/bin/mad serve` when that venv exists; otherwise it errors with a hint offering both `pip install 'mad-cli[server]'` and `mad service install`.

### `mad service install`

Render the boot-persistent service file — a systemd **user** unit on Linux (`~/.config/systemd/user/mad-cli.service`), a launchd LaunchAgent on macOS (`~/Library/LaunchAgents/com.mad-core.mad-cli.plist`). When the `server` extra is not importable (or `--wheel` is passed) it first provisions a dedicated venv under `config_root()/server-venv` and points `ExecStart` at it; otherwise `ExecStart` uses the current `mad`.

| Option/Arg | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address baked into the unit. |
| `--port` | `7373` | Bind port baked into the unit. |
| `--wheel` / `--from` | — | Provision the server venv from a local wheel/sdist (no PyPI). Forces venv provisioning even when the extra is present. |
| `--render-to PATH` | — | Write the unit/plist to `PATH` and stop — never touches `systemctl`/`launchctl` (used by tests and the E2E). |

Without `--render-to` it writes to the default path and activates (`systemctl --user daemon-reload && enable --now`, printing a `loginctl enable-linger` hint; or `launchctl load`).

### `mad service uninstall` / `status` / `update`

| Command | Purpose |
| --- | --- |
| `mad service uninstall` | Stop and remove the installed unit/plist. The server venv is left in place. |
| `mad service status` | Report the service file, whether the server venv exists and whether its `mad-cli` version matches this CLI (warns on drift). |
| `mad service update [--wheel PATH]` | Reinstall `mad-cli[server]` into the server venv at this CLI's version. |
