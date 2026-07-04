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
#            --timeout --edge-package --edge-version --yes --no-start
# commands.lifecycle → `mad start|stop|restart|status|logs|shell [INSTANCE]`
#   INSTANCE optional when exactly one instance exists (default_instance()).
# commands.instances → `mad list`, `mad info NAME`
```
