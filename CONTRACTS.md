# Frozen interface contracts — mad-cli v0.1

These signatures are the integration contract between `mad_cli.core` (framework-free engine) and
`mad_cli.commands` (Typer surface). Implementations may add private helpers, but the names,
module paths, and signatures below MUST NOT change without updating this file in the same PR.

Layering rule: `mad_cli.core` and `mad_cli.templates` never import `typer` or `rich`.
`mad_cli.commands` / `mad_cli.ui` never talk to `subprocess` or the filesystem directly — they go
through `core`.

## mad_cli.core.paths

```python
def config_root() -> Path            # $MAD_CLI_CONFIG_DIR or ~/.config/mad
def instances_root() -> Path         # config_root() / "instances"
def instance_dir(name: str) -> Path  # instances_root() / name  (validates name: [a-z0-9][a-z0-9-]*)
```

## mad_cli.core.envfile

```python
class EnvFile:
    path: Path | None
    @classmethod
    def load(cls, path: Path) -> "EnvFile"      # tolerant parser; preserves comments/order/blank lines
    @classmethod
    def empty(cls) -> "EnvFile"
    def get(self, key: str) -> str | None
    def set(self, key: str, value: str) -> None  # updates in place or appends at end
    def unset(self, key: str) -> None
    def keys(self) -> list[str]
    def save(self, path: Path | None = None) -> None  # round-trips comments/order byte-stable
```

## mad_cli.core.instance

```python
class InstanceNotFoundError(Exception): ...

@dataclass
class Instance:
    name: str
    config_dir: Path          # directory holding compose.yml/.env/Dockerfile/entrypoint.sh
    env: EnvFile
    legacy: bool = False      # True for the old single-instance layout at config_root()
    @property
    def host_port(self) -> int | None       # MAD_HOST_PORT
    @property
    def data_path(self) -> Path | None      # MAD_DATA_PATH
    @property
    def version_pin(self) -> str | None     # MAD_VERSION ('' -> None)
    @property
    def compose_file(self) -> Path
    @property
    def env_file(self) -> Path

def discover_instances() -> list[Instance]   # scan instances/*/.env + legacy top-level compose.yml/.env
def get_instance(name: str) -> Instance      # raises InstanceNotFoundError
def default_instance() -> Instance | None    # the single instance if exactly one exists, else None
```

## mad_cli.core.templates

```python
EDGE_PACKAGE: str = "mad-edge"   # overridable per-render via RenderContext.edge_package

@dataclass
class RenderContext:
    instance: str
    host_port: int
    data_path: Path
    timeout_s: int
    puid: int
    pgid: int
    edge_package: str = EDGE_PACKAGE
    edge_version: str = ""       # '' = latest

def render_all(ctx: RenderContext) -> dict[str, str]
    # {"Dockerfile": ..., "compose.yml": ..., "entrypoint.sh": ...} rendered from mad_cli/templates/*.tmpl

def write_instance_files(target: Path, ctx: RenderContext, env: EnvFile) -> None
    # writes rendered files + env.save(target/".env"); entrypoint.sh gets mode 0755
```

## mad_cli.core.compose

```python
class ComposeError(Exception): ...

class ComposeRunner:
    def __init__(self, instance: Instance, *, dry_run: bool = False) -> None
    # every method shells out: docker compose -p mad-<name> -f <compose.yml> --env-file <.env> ...
    def up(self, build: bool = True, detach: bool = True) -> None
    def down(self) -> None
    def restart(self) -> None
    def ps(self) -> str
    def logs(self, follow: bool = True) -> None          # streams; interactive
    def shell(self) -> None                              # docker compose exec mad bash; interactive
    def config_check(self) -> None                       # docker compose config -q; raises ComposeError
    def build(self, no_cache: bool = False) -> None
    def exec(self, cmd: list[str], capture: bool = True) -> str   # in service 'mad'; raises ComposeError
    def wait_healthy(self, timeout_s: int = 180) -> bool # polls `docker inspect` health status
```

## mad_cli.core.docker_check

```python
@dataclass
class DockerStatus:
    docker_present: bool
    daemon_running: bool
    compose_v2: bool
    version: str | None

def check_docker() -> DockerStatus
def install_docker_linux(assume_yes: bool = False) -> bool   # opt-in, Linux only (get.docker.com)
```

## mad_cli.core.claude_creds

```python
def write_claude_credentials(claude_dir: Path, token: str) -> Path
    # writes claude_dir/.credentials.json in claudeAiOauth format, chmod 600; returns the path
```

## mad_cli.core.keyspec

```python
@dataclass(frozen=True)
class KeySpec:
    id: str                      # e.g. "anthropic"
    env_vars: tuple[str, ...]    # e.g. ("GITHUB_TOKEN", "GH_TOKEN") — same value fanned out
    prompt: str
    secret: bool = True
    help_url: str | None = None
    writes_claude_credentials: bool = False   # True only for claude-oauth

BUILTIN_KEYS: dict[str, KeySpec]  # claude-oauth, anthropic, github, deepseek, linear, opencode
def mask(value: str) -> str       # "sk-a…f3" style masking, safe for short strings
```

## mad_cli.core.pypi

```python
def latest_version(package: str, timeout_s: float = 5.0) -> str | None   # pypi JSON API via urllib
```

## mad_cli.core.profiles

```python
class ProfileNotFoundError(Exception): ...

IDENTITY_KEYS: tuple[str, ...]   # instance-identity keys a profile never carries:
                                 # MAD_INSTANCE, MAD_HOST_PORT, PUID, PGID, MAD_DATA_PATH, MAD_VERSION

def profiles_root() -> Path            # config_root() / "profiles"
def profile_path(name: str) -> Path    # profiles_root()/<name>.env (validates name: [a-z0-9][a-z0-9-]*)
def list_profiles() -> list[str]       # stored profile names, sorted (empty when none)
def load_profile(name: str) -> EnvFile # raises ProfileNotFoundError
def save_profile(name: str, env: EnvFile) -> Path  # writes profiles/<name>.env, chmod 0600; returns path
def delete_profile(name: str) -> None  # raises ProfileNotFoundError
```

## mad_cli.ui.console / mad_cli.ui.prompts

```python
console: rich.console.Console
def info(msg: str) -> None; def ok(msg: str) -> None; def warn(msg: str) -> None; def error(msg: str) -> None; def header(msg: str) -> None

def ask(text: str, default: str | None = None, secret: bool = False,
        validator: Callable[[str], str] | None = None) -> str   # validator raises ValueError to re-prompt
def confirm(text: str, default: bool = True) -> bool
# Non-TTY/--yes mode: prompts must not block; ask() returns default or raises PromptRequiredError.
class PromptRequiredError(Exception): ...
```

## mad_cli.app / commands (Typer surface, v0.1)

```python
# mad_cli.app
app: typer.Typer      # no_args_is_help=True; version_option prints mad_cli.__version__
def main() -> None    # console-script entry point

# commands.install  → `mad install`
#   options: --name --port --data-path --github-token --claude-token --git-name --git-email
#            --timeout --edge-package --edge-version --profile --yes --no-start
#   --profile NAME: a profile's values seed the wizard defaults (explicit flag > profile > builtin).
# commands.lifecycle → `mad start|stop|restart|status|logs|shell [INSTANCE]`
#   INSTANCE optional when exactly one instance exists (default_instance()).
# commands.instances → `mad list`, `mad info NAME`
# commands.profiles  → `mad profiles create|list|show|delete|apply` (add_typer name="profiles")
# commands.service   → `mad serve`, `mad service install|uninstall|status|update`
```

## mad_cli.core.usecases (framework-free use-case layer, v0.4)

The orchestration shared by the Typer commands and the FastAPI routes. Framework-free
(no `typer`/`rich`/`fastapi`), `mypy --strict`. Single-instance operations take an
already-resolved `Instance`; the adapter resolves it (mapping resolution failures to its
own idiom) via `instances.resolve_instance`. Expected failures are raised as
`errors.UseCaseError` subclasses.

```python
# usecases.errors
class UseCaseError(Exception): ...
class ValidationError(UseCaseError, ValueError): ...     # 400 / exit 1 (also a ValueError)
class NotFoundError(UseCaseError): ...                    # 404 / exit 1
class ConflictError(UseCaseError): ...                    # 409
class AmbiguousInstanceError(UseCaseError): ...           # 409 / exit 1
class PreconditionError(UseCaseError): ...                # 412 / exit 1
def http_status_for(exc: UseCaseError) -> int

# usecases.instances
def resolve_instance(name: str | None) -> Instance   # NotFoundError / AmbiguousInstanceError
def state_health(instance: Instance) -> tuple[str, str]        # best-effort (state, health)
def list_instances() -> list[InstanceSummary]
def instance_info(name: str) -> InstanceInfo                   # NotFoundError
@dataclass(frozen=True) class InstanceSummary:  name, legacy, port, state, health, version
@dataclass(frozen=True) class EnvItem:          key, value, secret; def display(*, reveal=False)
@dataclass(frozen=True) class InstanceInfo:     name, legacy, config_dir, compose_file,
#                                               data_path, port, version, env: list[EnvItem]

# usecases.lifecycle  (each takes a resolved Instance)
def start(instance: Instance) -> StartResult          # runner.up(build=True) + wait_healthy()
def stop(instance: Instance) -> None
def restart(instance: Instance) -> None
def status(instance: Instance) -> StatusResult
def instance_url(instance: Instance) -> str | None

# usecases.configvals  (each takes a resolved Instance)
COMPOSE_KEYS: tuple[str, ...]                          # MAD_HOST_PORT, MAD_DATA_PATH
def list_config(instance: Instance) -> list[EnvItem]
def get_config(instance: Instance, key: str) -> EnvItem                        # NotFoundError
def set_config(instance: Instance, key: str, value: str) -> tuple[EnvItem, bool]  # ValidationError
def unset_config(instance: Instance, key: str) -> bool                         # existed?

# usecases.keys  (each takes a resolved Instance)
CUSTOM_KEY_RE: re.Pattern                              # [A-Z][A-Z0-9_]*
def key_prompt(key: str) -> tuple[str, bool]           # (prompt, secret); ValidationError
def set_key(instance: Instance, key: str, value: str) -> SetKeyResult   # Validation/Precondition
def list_keys(instance: Instance) -> KeysView
def remove_key(instance: Instance, key: str) -> RemoveKeyResult

# usecases.versions
def versions(name: str | None) -> list[VersionRow]     # None = all; NotFoundError for a named miss
def update(instance: Instance, version: str | None) -> UpdateResult

# usecases.adopt
def plan_adopt() -> AdoptPlan | None                   # None = no legacy layout; ValidationError
def apply_adopt(plan: AdoptPlan) -> AdoptPlan

# usecases.install
@dataclass class InstallParams:  name port data_path timeout_s github_token puid pgid
#   git_name git_email claude_token anthropic_api_key extra_env:{VAR:value}
#   retention_days mcp_allowed_hosts edge_package edge_version start
def validate_name/validate_port/validate_timeout/validate_retention(value: str) -> str
def apply_extra_key(env: EnvFile, ident: str, value: str) -> list[str]   # fan out; ValidationError
def build_env(params: InstallParams) -> tuple[EnvFile, list[str]]
def install(params: InstallParams) -> InstallResult    # writes files+dirs+creds, optional start

# usecases.service  (framework-free; never runs systemctl/launchctl)
DEFAULT_HOST = "127.0.0.1"; DEFAULT_PORT = 7373
def api_token_path() -> Path                           # config_root()/api-token
def ensure_api_token() -> str                          # 0600, generated once
def read_api_token() -> str | None
def server_deps_available() -> bool                    # fastapi + uvicorn importable
def server_venv_dir() -> Path; def server_venv_mad() -> Path; def server_venv_exists() -> bool
def bootstrap_server_venv(*, wheel: Path | None = None) -> Path   # venv + pip install [server]
def ensure_server_runtime(*, wheel: Path | None = None) -> tuple[list[str], bool]
def serve_argv(launcher: list[str], host: str, port: int) -> list[str]
def render_systemd_unit(*, exec_args, config_dir) -> str
def render_launchd_plist(*, exec_args, config_dir, log_path) -> str
def render_service(*, platform, exec_args, config_dir) -> RenderedService   # PreconditionError
```

## mad_cli.core.keyspec (added in v0.4)

```python
def is_secret_key(key: str) -> bool                    # masks TOKEN/KEY/SECRET/PASSWORD keys
def display_value(key: str, value: str, *, reveal: bool = False) -> str
```

## mad_cli.server (the `server` optional extra, v0.4)

Nothing here is imported by the base CLI; reached only via `mad serve` behind an import
guard. Routes are thin adapters over `core.usecases`.

```python
def create_app() -> fastapi.FastAPI    # OpenAPI at /openapi.json

# GET  /health                                   (no auth) -> {status, version}
# Every /v1 route requires  Authorization: Bearer <config_root()/api-token>  (401 otherwise):
# GET    /v1/instances                            list
# POST   /v1/instances                            install (201; body = InstallRequest)
# GET    /v1/instances/{name}                     info (env masked)
# POST   /v1/instances/{name}/start|stop|restart  lifecycle (synchronous MVP)
# GET    /v1/instances/{name}/status              container state + health
# GET    /v1/instances/{name}/config              list (masked)
# PUT    /v1/instances/{name}/config/{key}        set (body {value}); DELETE unset
# GET    /v1/instances/{name}/keys                list (masked)
# PUT    /v1/instances/{name}/keys/{key_id}       set (body {value}); DELETE remove
# GET    /v1/instances/{name}/versions            version report
# POST   /v1/instances/{name}/update              re-pin + rebuild (body {version})
# POST   /v1/adopt                                migrate the legacy layout
# Secret values are NEVER returned in clear (no reveal flag exists on the API).
```
