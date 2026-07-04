---
service: mad-cli
domain: backend
section: architecture
source_of_truth: repo
---
# Components

A module-by-module responsibilities reference, grouped by layer. This document names what each module is for and where the boundary between layers sits; it does not restate signatures — those are frozen in `CONTRACTS.md` at the repo root.

## Engine: `core/`

The framework-free engine. Never imports `typer`/`rich`; type-checked with `mypy --strict`.

| Module | Responsibility |
| --- | --- |
| `paths.py` | Config-root resolution: `config_root()` = `$MAD_CLI_CONFIG_DIR` or `~/.config/mad`; `instances_root()` = `config_root()/instances`; `instance_dir(name)` validates the name against `[a-z0-9][a-z0-9-]*`. |
| `envfile.py` | `EnvFile`: a tolerant `.env` parser that preserves comments, order, and blank lines, with a byte-stable round-trip and `get`/`set`/`unset`/`keys`/`save`. |
| `instance.py` | The `Instance` dataclass (name, config_dir, env, legacy) with typed accessors — `host_port` (`MAD_HOST_PORT`), `data_path` (`MAD_DATA_PATH`), `version_pin` (`MAD_VERSION`), `compose_file`, `env_file`; `discover_instances()` (modern `instances/*/.env` first, then the legacy top-level layout); `get_instance(name)` (raises `InstanceNotFoundError`); `default_instance()` (the sole instance, else `None`). |
| `keyspec.py` | `KeySpec` plus the `BUILTIN_KEYS` registry (`claude-oauth`, `anthropic`, `github`, `deepseek`, `linear`, `opencode`); `mask(value)`, `is_secret_key(key)` (masks `*TOKEN*`/`*KEY*`/`*SECRET*`/`*PASSWORD*` keys) and `display_value(key, value, *, reveal)`. |
| `profiles.py` | Named environment profiles stored one file per profile at `config_root()/profiles/<name>.env` (`chmod 600`): `list_profiles`/`load_profile`/`save_profile`/`delete_profile` (raise `ProfileNotFoundError`), name validation (the instance-name rule), and `IDENTITY_KEYS` — the instance-identity keys a profile never carries. |
| `claude_creds.py` | `write_claude_credentials(claude_dir, token)` writes `.credentials.json` (the `claudeAiOauth` format), `chmod 600`. |
| `templates.py` | `RenderContext` plus `render_all()` / `write_instance_files()` render the three packaged instance `*.tmpl`; `EDGE_PACKAGE` defaults to `mad-edge`; the container start binary is resolved in Python (`mad-edge`, or `mad` for the `mad-bros` package). |
| `compose.py` | `ComposeRunner`: the one module that shells out to Docker. Every argv is scoped `docker compose -p mad-<name> -f <compose.yml> --env-file <.env> <verb>`; methods `up`/`down`/`restart`/`ps`/`logs`/`shell`/`config_check`/`build`/`exec`/`wait_healthy`; `dry_run` records the argv on `last_command` without executing. |
| `docker_check.py` | `check_docker()` returns `DockerStatus(docker_present, daemon_running, compose_v2, version)`, probed via subprocess; `install_docker_linux()` is an opt-in installer via get.docker.com (Linux only). |
| `pypi.py` | `latest_version(package)` via the PyPI JSON API (stdlib `urllib`, 5s timeout, fail-soft to `None`). |

## Engine: `core/usecases/`

The framework-free **use-case layer** — the orchestration shared by the Typer commands and the HTTP routes, so the two surfaces cannot drift. Never imports `typer`/`rich`/`fastapi`; `mypy --strict`. Each function takes primitives (or a resolved `Instance`) and returns dataclasses, raising `errors.UseCaseError` subclasses for expected failures.

| Module | Responsibility |
| --- | --- |
| `errors.py` | The failure vocabulary (`ValidationError`, `NotFoundError`, `ConflictError`, `AmbiguousInstanceError`, `PreconditionError`) plus `http_status_for()` for the API adapter. |
| `instances.py` | `resolve_instance()`, `list_instances()`, `instance_info()`, `state_health()`, and the `EnvItem` view (masking-aware). |
| `lifecycle.py` | `start`/`stop`/`restart`/`status` over a resolved `Instance`. |
| `configvals.py` | `.env` get/set/unset with validation and the compose-baked-key flag. |
| `keys.py` | Credential set/list/remove (builtin fan-out, custom vars, claude-oauth credentials). |
| `versions.py` | The version report and `update` (re-pin + rebuild). |
| `adopt.py` | `plan_adopt()` / `apply_adopt()` for the legacy layout migration. |
| `install.py` | `InstallParams` → `.env` assembly, file rendering, data dirs, credentials, optional start; the shared validators and `apply_extra_key`. |
| `service.py` | The API token, the dedicated `server-venv` bootstrap, launcher resolution, and the systemd-unit / launchd-plist rendering. Never runs `systemctl`/`launchctl`. |

## Engine: `templates/`

Packaged `string.Template` sources. Literal `$` is escaped `$$`; `${name}` are placeholders. Rendered by `core/templates.py`. Never imports `typer`/`rich`.

| Module | Responsibility |
| --- | --- |
| `Dockerfile.tmpl` | The container image definition (base image, apt/npm/pip installs, the mad-edge package, the non-root user). |
| `compose.yml.tmpl` | The Compose service definition (port mapping and bind mounts). |
| `entrypoint.sh.tmpl` | The container entrypoint (authenticate `gh`, then exec the edge serve command). |
| `mad-cli.service.tmpl` | The systemd **user** unit for `mad serve` (rendered by `core/usecases/service.py`). |
| `com.mad-core.mad-cli.plist.tmpl` | The launchd LaunchAgent plist for `mad serve` (macOS). |

## Surface: `commands/`, `ui/`, and `app.py`

The Typer surface. Thin adapters over `core.usecases`; never touch `subprocess` or the filesystem directly — everything goes through the engine.

`commands/` — the command modules:

| Module | Responsibility |
| --- | --- |
| `install.py` | The guided `mad install` command (collection + Docker preflight + summary over `usecases.install`). |
| `lifecycle.py` | The lifecycle commands: `start`, `stop`, `restart`, `status`, `logs`, `shell`. |
| `instances.py` | The inventory commands: `list`, `info`, `adopt`. |
| `keys.py` | The `mad keys` sub-app: `set`, `list`, `remove`. |
| `config.py` | The `mad config` sub-app: `get`, `set`, `unset` — the general-purpose `.env` editor. |
| `profiles.py` | The `mad profiles` sub-app: `create`, `list`, `show`, `delete`, `apply` — reusable named environment profiles. |
| `versions.py` | The version commands: `versions` and `update`. |
| `service.py` | `mad serve` and the `mad service install\|uninstall\|status\|update` sub-app. |
| `_adapt.py` | Shared adapter helpers: `resolve_or_die`, `die`, `fail` — map `UseCaseError` to the CLI idiom. |
| `_common.py` | Re-exports `is_secret_key` from `core.keyspec` (masking now lives in the engine). |

`ui/` — the shared UI helpers:

| Module | Responsibility |
| --- | --- |
| `console.py` | One shared Rich `Console` plus `info`/`ok`/`warn`/`error`/`header` and the `run_step` spinner. |
| `prompts.py` | `ask`/`confirm` honoring the non-interactive contract (non-TTY: return the default or raise `PromptRequiredError`; interactive `ask` re-prompts while a validator raises `ValueError`). |

`app.py` — the Typer application wiring plus `main()`, the console-script entry point (`mad`); `no_args_is_help=True`, `add_completion=False`, and an eager `--version` that prints `mad_cli.__version__`. It also registers `mad serve` and the `mad service` sub-app.

## Surface: `server/` (the optional `server` extra)

The HTTP adapter, reached only via `mad serve` behind an import guard — nothing here is imported by the base CLI, so `pip install mad-cli` never pulls in FastAPI/uvicorn. Routes are thin adapters over `core.usecases`, exactly like the Typer commands.

| Module | Responsibility |
| --- | --- |
| `app.py` | `create_app()` — the FastAPI factory: `/health` (no auth) plus the `/v1` router, and one exception handler mapping `UseCaseError` → HTTP status. |
| `auth.py` | The bearer-token dependency (constant-time compare against `config_root()/api-token`; 401/503). |
| `models.py` | Typed Pydantic request/response models (OpenAPI for free); secret values are only ever carried masked. |

## The boundary

- `core/` (incl. `core/usecases/`) and `templates/` never import `typer`, `rich` or `fastapi`.
- `commands/`, `ui/` and `server/` never touch `subprocess` or the filesystem directly — they call into `core`.
- `server/` is an optional extra: the base CLI never imports it.

This is the layering rule. It is defined and its enforcement explained in [../04-conventions/layering.md](../04-conventions/layering.md), and the core-to-surface integration seam it protects is frozen in `CONTRACTS.md` at the repo root.
