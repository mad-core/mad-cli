"""Typed request / response models for the v1 HTTP API (OpenAPI for free).

Secret-looking values are only ever carried out masked — the response models are
populated from the use-case layer's already-masked views, and there is no field
(and no query flag) that reveals a full secret.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class InstanceSummaryModel(BaseModel):
    name: str
    legacy: bool
    port: int | None
    state: str
    health: str
    version: str


class EnvItemModel(BaseModel):
    key: str
    value: str = Field(description="Masked when the key looks like a secret.")
    secret: bool


class InstanceInfoModel(BaseModel):
    name: str
    legacy: bool
    config_dir: str
    compose_file: str
    data_path: str | None
    port: int | None
    version: str | None
    env: list[EnvItemModel]


class InstallRequest(BaseModel):
    name: str = "default"
    port: int = 8080
    data_path: str
    timeout_s: int = 600
    github_token: str
    git_name: str = ""
    git_email: str = ""
    claude_token: str = ""
    anthropic_api_key: str = ""
    extra_keys: dict[str, str] = Field(
        default_factory=dict,
        description="Extra API keys as {builtin-id-or-VAR: value}; builtins fan out.",
    )
    retention_days: str = ""
    mcp_allowed_hosts: str = ""
    edge_package: str | None = None
    edge_version: str = ""
    start: bool = False


class InstallResponse(BaseModel):
    name: str
    config_dir: str
    data_dir: str
    port: int
    started: bool
    healthy: bool | None
    url: str | None


class StartResponse(BaseModel):
    name: str
    healthy: bool
    url: str | None


class ActionResponse(BaseModel):
    name: str
    action: str
    ok: bool = True


class StatusResponse(BaseModel):
    name: str
    health: str
    url: str | None
    ps: str


class SetConfigRequest(BaseModel):
    value: str


class SetConfigResponse(BaseModel):
    key: str
    value: str = Field(description="Masked when the key looks like a secret.")
    secret: bool
    compose_baked: bool


class BuiltinKeyModel(BaseModel):
    id: str
    env_vars: list[str]
    is_set: bool
    value: str = Field(description="Masked value, or '-' when unset.")


class CustomSecretModel(BaseModel):
    key: str
    value: str = Field(description="Masked value.")


class KeysResponse(BaseModel):
    builtins: list[BuiltinKeyModel]
    custom: list[CustomSecretModel]


class SetKeyRequest(BaseModel):
    value: str


class SetKeyResponse(BaseModel):
    id: str
    env_vars: list[str]
    builtin: bool
    credentials_written: bool


class VersionRowModel(BaseModel):
    name: str
    legacy: bool
    pinned: str
    installed: str
    latest: str
    update: str


class UpdateRequest(BaseModel):
    version: str | None = None


class UpdateResponse(BaseModel):
    name: str
    target: str
    healthy: bool


class AdoptResponse(BaseModel):
    adopted: bool
    name: str | None = None
    target: str | None = None
    moved: list[str] = Field(default_factory=list)
