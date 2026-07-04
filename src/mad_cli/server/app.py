"""FastAPI application factory for the v1 local API.

Every ``/v1`` route is a thin adapter over :mod:`mad_cli.core.usecases` — the same
functions the Typer commands call — guarded by the bearer-token dependency. The
use-case error vocabulary is mapped to HTTP status codes by a single exception
handler, so the routes stay declarative.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from mad_cli import __version__
from mad_cli.core.envfile import EnvFile
from mad_cli.core.instance import Instance, InstanceNotFoundError, get_instance
from mad_cli.core.templates import EDGE_PACKAGE
from mad_cli.core.usecases import adopt as uc_adopt
from mad_cli.core.usecases import configvals as uc_config
from mad_cli.core.usecases import install as uc_install
from mad_cli.core.usecases import instances as uc_instances
from mad_cli.core.usecases import keys as uc_keys
from mad_cli.core.usecases import lifecycle as uc_lifecycle
from mad_cli.core.usecases import versions as uc_versions
from mad_cli.core.usecases.errors import NotFoundError, UseCaseError, http_status_for
from mad_cli.server import models as m
from mad_cli.server.auth import require_token


def _host_id(getter_name: str) -> int:
    getter = getattr(os, getter_name, None)
    return getter() if getter is not None else 1000


def _instance(name: str) -> Instance:
    """Resolve a path ``{name}`` to an :class:`Instance` or raise 404 via the handler."""
    try:
        return get_instance(name)
    except InstanceNotFoundError:
        raise NotFoundError(f"instance {name!r} not found") from None


def _build_router() -> APIRouter:
    router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])

    # ── instances ────────────────────────────────────────────────────────────
    @router.get("/instances", response_model=list[m.InstanceSummaryModel], tags=["instances"])
    def list_instances() -> list[m.InstanceSummaryModel]:
        return [
            m.InstanceSummaryModel(
                name=row.name,
                legacy=row.legacy,
                port=row.port,
                state=row.state,
                health=row.health,
                version=row.version,
            )
            for row in uc_instances.list_instances()
        ]

    @router.post(
        "/instances",
        response_model=m.InstallResponse,
        status_code=201,
        tags=["instances"],
    )
    def install_instance(req: m.InstallRequest) -> m.InstallResponse:
        scratch = EnvFile.empty()
        for ident, value in req.extra_keys.items():
            uc_install.apply_extra_key(scratch, ident, value)
        extra_env = {var: scratch.get(var) or "" for var in scratch.keys()}  # noqa: SIM118
        params = uc_install.InstallParams(
            name=req.name,
            port=req.port,
            data_path=Path(req.data_path),
            timeout_s=req.timeout_s,
            github_token=req.github_token,
            puid=_host_id("getuid"),
            pgid=_host_id("getgid"),
            git_name=req.git_name,
            git_email=req.git_email,
            claude_token=req.claude_token,
            anthropic_api_key=req.anthropic_api_key,
            extra_env=extra_env,
            retention_days=req.retention_days,
            mcp_allowed_hosts=req.mcp_allowed_hosts,
            edge_package=req.edge_package or EDGE_PACKAGE,
            edge_version=req.edge_version,
            start=req.start,
        )
        result = uc_install.install(params)
        return m.InstallResponse(
            name=result.name,
            config_dir=str(result.config_dir),
            data_dir=str(result.data_dir),
            port=result.port,
            started=result.started,
            healthy=result.healthy,
            url=result.url,
        )

    @router.get("/instances/{name}", response_model=m.InstanceInfoModel, tags=["instances"])
    def instance_info(name: str) -> m.InstanceInfoModel:
        info = uc_instances.instance_info(name)
        return m.InstanceInfoModel(
            name=info.name,
            legacy=info.legacy,
            config_dir=str(info.config_dir),
            compose_file=str(info.compose_file),
            data_path=str(info.data_path) if info.data_path else None,
            port=info.port,
            version=info.version,
            env=[m.EnvItemModel(key=i.key, value=i.display(), secret=i.secret) for i in info.env],
        )

    # ── lifecycle ─────────────────────────────────────────────────────────────
    @router.post("/instances/{name}/start", response_model=m.StartResponse, tags=["lifecycle"])
    def start(name: str) -> m.StartResponse:
        inst = _instance(name)
        res = uc_lifecycle.start(inst)
        return m.StartResponse(name=inst.name, healthy=res.healthy, url=res.url)

    @router.post("/instances/{name}/stop", response_model=m.ActionResponse, tags=["lifecycle"])
    def stop(name: str) -> m.ActionResponse:
        inst = _instance(name)
        uc_lifecycle.stop(inst)
        return m.ActionResponse(name=inst.name, action="stop")

    @router.post("/instances/{name}/restart", response_model=m.ActionResponse, tags=["lifecycle"])
    def restart(name: str) -> m.ActionResponse:
        inst = _instance(name)
        uc_lifecycle.restart(inst)
        return m.ActionResponse(name=inst.name, action="restart")

    @router.get("/instances/{name}/status", response_model=m.StatusResponse, tags=["lifecycle"])
    def status(name: str) -> m.StatusResponse:
        inst = _instance(name)
        res = uc_lifecycle.status(inst)
        return m.StatusResponse(name=inst.name, health=res.health, url=res.url, ps=res.ps_text)

    # ── config ────────────────────────────────────────────────────────────────
    @router.get("/instances/{name}/config", response_model=list[m.EnvItemModel], tags=["config"])
    def get_config(name: str) -> list[m.EnvItemModel]:
        inst = _instance(name)
        return [
            m.EnvItemModel(key=i.key, value=i.display(), secret=i.secret)
            for i in uc_config.list_config(inst)
        ]

    @router.put(
        "/instances/{name}/config/{key}", response_model=m.SetConfigResponse, tags=["config"]
    )
    def set_config(name: str, key: str, body: m.SetConfigRequest) -> m.SetConfigResponse:
        inst = _instance(name)
        item, compose_baked = uc_config.set_config(inst, key, body.value)
        return m.SetConfigResponse(
            key=item.key, value=item.display(), secret=item.secret, compose_baked=compose_baked
        )

    @router.delete(
        "/instances/{name}/config/{key}", response_model=m.ActionResponse, tags=["config"]
    )
    def unset_config(name: str, key: str) -> m.ActionResponse:
        inst = _instance(name)
        existed = uc_config.unset_config(inst, key)
        if not existed:
            raise NotFoundError(f"{key} is not set on {inst.name}")
        return m.ActionResponse(name=inst.name, action=f"unset {key}")

    # ── keys ──────────────────────────────────────────────────────────────────
    @router.get("/instances/{name}/keys", response_model=m.KeysResponse, tags=["keys"])
    def list_keys(name: str) -> m.KeysResponse:
        inst = _instance(name)
        view = uc_keys.list_keys(inst)
        return m.KeysResponse(
            builtins=[
                m.BuiltinKeyModel(
                    id=s.id, env_vars=list(s.env_vars), is_set=s.is_set, value=s.masked
                )
                for s in view.builtins
            ],
            custom=[m.CustomSecretModel(key=c.key, value=c.masked) for c in view.custom],
        )

    @router.put("/instances/{name}/keys/{key_id}", response_model=m.SetKeyResponse, tags=["keys"])
    def set_key(name: str, key_id: str, body: m.SetKeyRequest) -> m.SetKeyResponse:
        inst = _instance(name)
        res = uc_keys.set_key(inst, key_id, body.value)
        return m.SetKeyResponse(
            id=res.id,
            env_vars=list(res.env_vars),
            builtin=res.builtin,
            credentials_written=res.credentials_path is not None,
        )

    @router.delete(
        "/instances/{name}/keys/{key_id}", response_model=m.ActionResponse, tags=["keys"]
    )
    def remove_key(name: str, key_id: str) -> m.ActionResponse:
        inst = _instance(name)
        res = uc_keys.remove_key(inst, key_id)
        if not res.existed:
            raise NotFoundError(f"{res.id} is not set on {inst.name}")
        return m.ActionResponse(name=inst.name, action=f"remove {res.id}")

    # ── versions ──────────────────────────────────────────────────────────────
    @router.get("/instances/{name}/versions", response_model=m.VersionRowModel, tags=["versions"])
    def versions(name: str) -> m.VersionRowModel:
        rows = uc_versions.versions(name)
        row = rows[0]
        return m.VersionRowModel(
            name=row.name,
            legacy=row.legacy,
            pinned=row.pinned,
            installed=row.installed,
            latest=row.latest,
            update=row.update,
        )

    @router.post("/instances/{name}/update", response_model=m.UpdateResponse, tags=["versions"])
    def update(name: str, body: m.UpdateRequest) -> m.UpdateResponse:
        inst = _instance(name)
        res = uc_versions.update(inst, body.version)
        return m.UpdateResponse(name=inst.name, target=res.target, healthy=res.healthy)

    # ── adopt ─────────────────────────────────────────────────────────────────
    @router.post("/adopt", response_model=m.AdoptResponse, tags=["adopt"])
    def adopt() -> m.AdoptResponse:
        plan = uc_adopt.plan_adopt()
        if plan is None:
            return m.AdoptResponse(adopted=False)
        uc_adopt.apply_adopt(plan)
        return m.AdoptResponse(
            adopted=True, name=plan.name, target=str(plan.target), moved=plan.movable
        )

    return router


def create_app() -> FastAPI:
    """Build the FastAPI application (the OpenAPI schema is generated from it)."""
    app = FastAPI(
        title="mad-cli local API",
        version=__version__,
        summary="Operator API mirroring the mad CLI (instances, lifecycle, config, keys).",
    )

    @app.exception_handler(UseCaseError)
    async def _handle_usecase_error(request: Request, exc: UseCaseError) -> JSONResponse:
        return JSONResponse(status_code=http_status_for(exc), content={"detail": str(exc)})

    @app.get("/health", response_model=m.HealthResponse, tags=["meta"])
    def health() -> m.HealthResponse:
        return m.HealthResponse(status="ok", version=__version__)

    app.include_router(_build_router())
    return app
