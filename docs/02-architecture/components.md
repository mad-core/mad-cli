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
| `keyspec.py` | `KeySpec` plus the `BUILTIN_KEYS` registry (`claude-oauth`, `anthropic`, `github`, `deepseek`, `linear`, `opencode`); `mask(value)`. |
| `profiles.py` | Named environment profiles stored one file per profile at `config_root()/profiles/<name>.env` (`chmod 600`): `list_profiles`/`load_profile`/`save_profile`/`delete_profile` (raise `ProfileNotFoundError`), name validation (the instance-name rule), and `IDENTITY_KEYS` — the instance-identity keys a profile never carries. |
| `claude_creds.py` | `write_claude_credentials(claude_dir, token)` writes `.credentials.json` (the `claudeAiOauth` format), `chmod 600`. |
| `templates.py` | `RenderContext` plus `render_all()` / `write_instance_files()` render the three packaged `*.tmpl`; `EDGE_PACKAGE` defaults to `mad-edge`; the container start binary is resolved in Python (`mad-edge`, or `mad` for the `mad-bros` package). |
| `compose.py` | `ComposeRunner`: the one module that shells out to Docker. Every argv is scoped `docker compose -p mad-<name> -f <compose.yml> --env-file <.env> <verb>`; methods `up`/`down`/`restart`/`ps`/`logs`/`shell`/`config_check`/`build`/`exec`/`wait_healthy`; `dry_run` records the argv on `last_command` without executing. |
| `docker_check.py` | `check_docker()` returns `DockerStatus(docker_present, daemon_running, compose_v2, version)`, probed via subprocess; `install_docker_linux()` is an opt-in installer via get.docker.com (Linux only). |
| `pypi.py` | `latest_version(package)` via the PyPI JSON API (stdlib `urllib`, 5s timeout, fail-soft to `None`). |

## Engine: `templates/`

Packaged `string.Template` sources. Literal `$` is escaped `$$`; `${name}` are placeholders. Rendered by `core/templates.py`. Never imports `typer`/`rich`.

| Module | Responsibility |
| --- | --- |
| `Dockerfile.tmpl` | The container image definition (base image, apt/npm/pip installs, the mad-edge package, the non-root user). |
| `compose.yml.tmpl` | The Compose service definition (port mapping and bind mounts). |
| `entrypoint.sh.tmpl` | The container entrypoint (authenticate `gh`, then exec the edge serve command). |

## Surface: `commands/`, `ui/`, and `app.py`

The Typer surface. Never touches `subprocess` or the filesystem directly — everything goes through the engine.

`commands/` — the command modules:

| Module | Responsibility |
| --- | --- |
| `install.py` | The guided `mad install` command: install or reconfigure a mad-edge instance. |
| `lifecycle.py` | The lifecycle commands: `start`, `stop`, `restart`, `status`, `logs`, `shell`. |
| `instances.py` | The inventory commands: `list`, `info`, `adopt`. |
| `keys.py` | The `mad keys` sub-app: `set`, `list`, `remove`. |
| `config.py` | The `mad config` sub-app: `get`, `set`, `unset` — the general-purpose `.env` editor. |
| `profiles.py` | The `mad profiles` sub-app: `create`, `list`, `show`, `delete`, `apply` — reusable named environment profiles. |
| `versions.py` | The version commands: `versions` and `update`. |
| `_common.py` | Shared surface helper: `is_secret_key`, the masking helper. |

`ui/` — the shared UI helpers:

| Module | Responsibility |
| --- | --- |
| `console.py` | One shared Rich `Console` plus `info`/`ok`/`warn`/`error`/`header` and the `run_step` spinner. |
| `prompts.py` | `ask`/`confirm` honoring the non-interactive contract (non-TTY: return the default or raise `PromptRequiredError`; interactive `ask` re-prompts while a validator raises `ValueError`). |

`app.py` — the Typer application wiring plus `main()`, the console-script entry point (`mad`); `no_args_is_help=True`, `add_completion=False`, and an eager `--version` that prints `mad_cli.__version__`.

## The boundary

- `core/` and `templates/` never import `typer` or `rich`.
- `commands/` and `ui/` never touch `subprocess` or the filesystem directly — they call into `core`.

This is the layering rule. It is defined and its enforcement explained in [../04-conventions/layering.md](../04-conventions/layering.md), and the core-to-surface integration seam it protects is frozen in `CONTRACTS.md` at the repo root.
