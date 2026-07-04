"""HTTP API tests via ``fastapi.testclient.TestClient``.

Cover auth (on/off/wrong), the OpenAPI schema, non-interactive install, masking on
every read (the full secret must never appear in any response), lifecycle against a
mocked runner, and the config/keys/versions/update/adopt surface. Docker is mocked;
the engine runs for real over a scratch ``MAD_CLI_CONFIG_DIR``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

DUMMY_GH = "ghp_dummy_do_not_leak_value"
DUMMY_CLAUDE = "claude-oauth-dummy-do-not-leak"


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    monkeypatch.setenv("MAD_CLI_CONFIG_DIR", str(tmp_path / "config"))
    from mad_cli.core.usecases import service

    token = service.ensure_api_token()
    from mad_cli.server import create_app

    client = TestClient(create_app())
    return SimpleNamespace(
        client=client,
        token=token,
        tmp_path=tmp_path,
        auth={"Authorization": f"Bearer {token}"},
    )


def _install_body(tmp_path: Path, **over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "web",
        "port": 9000,
        "data_path": str(tmp_path / "data"),
        "github_token": DUMMY_GH,
        "claude_token": DUMMY_CLAUDE,
        "start": False,
    }
    body.update(over)
    return body


def _create(api: SimpleNamespace, **over: object) -> None:
    resp = api.client.post(
        "/v1/instances", json=_install_body(api.tmp_path, **over), headers=api.auth
    )
    assert resp.status_code == 201, resp.text


# ── health & auth ─────────────────────────────────────────────────────────────
def test_health_needs_no_auth(api: SimpleNamespace) -> None:
    resp = api.client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_protected_route_requires_bearer(api: SimpleNamespace) -> None:
    assert api.client.get("/v1/instances").status_code == 401
    assert (
        api.client.get("/v1/instances", headers={"Authorization": "Bearer nope"}).status_code == 401
    )
    assert api.client.get("/v1/instances", headers=api.auth).status_code == 200


def test_openapi_is_generated_with_routes(api: SimpleNamespace) -> None:
    resp = api.client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for route in (
        "/health",
        "/v1/instances",
        "/v1/instances/{name}",
        "/v1/instances/{name}/start",
        "/v1/instances/{name}/config/{key}",
        "/v1/instances/{name}/keys/{key_id}",
        "/v1/instances/{name}/versions",
        "/v1/instances/{name}/update",
        "/v1/adopt",
    ):
        assert route in paths, route


# ── install + masking ─────────────────────────────────────────────────────────
def test_install_creates_files_on_disk(api: SimpleNamespace) -> None:
    _create(api)
    cfg = api.tmp_path / "config" / "instances" / "web"
    assert (cfg / "compose.yml").is_file()
    assert (cfg / ".env").is_file()
    assert (api.tmp_path / "data" / "web" / "sessions").is_dir()


def test_list_and_info_never_leak_full_secrets(api: SimpleNamespace) -> None:
    _create(api)

    listing = api.client.get("/v1/instances", headers=api.auth)
    assert listing.status_code == 200
    assert [i["name"] for i in listing.json()] == ["web"]

    info = api.client.get("/v1/instances/web", headers=api.auth)
    assert info.status_code == 200
    body = info.text
    assert DUMMY_GH not in body  # masked
    gh = next(i for i in info.json()["env"] if i["key"] == "GITHUB_TOKEN")
    assert gh["secret"] is True and gh["value"] != DUMMY_GH


def test_config_get_masks_and_put_delete(api: SimpleNamespace) -> None:
    _create(api)

    cfg = api.client.get("/v1/instances/web/config", headers=api.auth)
    assert cfg.status_code == 200
    assert DUMMY_GH not in cfg.text

    # PUT a secret-looking value comes back masked; the raw value never appears
    put = api.client.put(
        "/v1/instances/web/config/EXTRA_TOKEN",
        json={"value": "supersecretvalue123"},
        headers=api.auth,
    )
    assert put.status_code == 200, put.text
    assert put.json()["secret"] is True
    assert "supersecretvalue123" not in put.text

    # a compose-baked key is flagged
    baked = api.client.put(
        "/v1/instances/web/config/MAD_HOST_PORT", json={"value": "9100"}, headers=api.auth
    )
    assert baked.json()["compose_baked"] is True

    # invalid value -> 400
    bad = api.client.put(
        "/v1/instances/web/config/MAD_HOST_PORT", json={"value": "70000"}, headers=api.auth
    )
    assert bad.status_code == 400

    deleted = api.client.delete("/v1/instances/web/config/EXTRA_TOKEN", headers=api.auth)
    assert deleted.status_code == 200
    missing = api.client.delete("/v1/instances/web/config/NOPE", headers=api.auth)
    assert missing.status_code == 404


def test_keys_put_get_masked_and_delete(api: SimpleNamespace) -> None:
    _create(api)

    put = api.client.put(
        "/v1/instances/web/keys/github", json={"value": "ghp_rotate_me_secret"}, headers=api.auth
    )
    assert put.status_code == 200, put.text
    assert set(put.json()["env_vars"]) == {"GITHUB_TOKEN", "GH_TOKEN"}

    keys = api.client.get("/v1/instances/web/keys", headers=api.auth)
    assert keys.status_code == 200
    assert "ghp_rotate_me_secret" not in keys.text  # masked
    github = next(k for k in keys.json()["builtins"] if k["id"] == "github")
    assert github["is_set"] is True

    removed = api.client.delete("/v1/instances/web/keys/github", headers=api.auth)
    assert removed.status_code == 200
    # removing an unset key -> 404
    assert api.client.delete("/v1/instances/web/keys/deepseek", headers=api.auth).status_code == 404

    # unknown key id -> 400
    assert (
        api.client.put(
            "/v1/instances/web/keys/not-a-key", json={"value": "x"}, headers=api.auth
        ).status_code
        == 400
    )


# ── lifecycle (runner mocked) ─────────────────────────────────────────────────
def test_lifecycle_start_stop_call_runner(
    api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create(api)
    from mad_cli.core.usecases import lifecycle as uc_lifecycle

    runner = MagicMock()
    runner.wait_healthy.return_value = True
    runner.ps.return_value = "mad-web Up (healthy)"
    monkeypatch.setattr(uc_lifecycle, "ComposeRunner", MagicMock(return_value=runner))

    start = api.client.post("/v1/instances/web/start", headers=api.auth)
    assert start.status_code == 200
    assert start.json()["healthy"] is True
    runner.up.assert_called_once_with(build=True)

    stop = api.client.post("/v1/instances/web/stop", headers=api.auth)
    assert stop.status_code == 200
    runner.down.assert_called_once()

    status = api.client.get("/v1/instances/web/status", headers=api.auth)
    assert status.status_code == 200
    assert status.json()["health"] == "healthy"


def test_unknown_instance_is_404(api: SimpleNamespace) -> None:
    assert api.client.get("/v1/instances/ghost", headers=api.auth).status_code == 404
    assert api.client.post("/v1/instances/ghost/start", headers=api.auth).status_code == 404


# ── versions / update / adopt ─────────────────────────────────────────────────
def test_versions_and_update(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    _create(api)
    from mad_cli.core.usecases import versions as uc_versions

    runner = MagicMock()
    runner.exec.return_value = "0.5.0\n"
    runner.wait_healthy.return_value = True
    monkeypatch.setattr(uc_versions, "ComposeRunner", MagicMock(return_value=runner))
    monkeypatch.setattr(uc_versions.pypi, "latest_version", lambda pkg, **kw: "0.6.0")

    versions = api.client.get("/v1/instances/web/versions", headers=api.auth)
    assert versions.status_code == 200
    assert versions.json()["update"] == "update available"

    updated = api.client.post(
        "/v1/instances/web/update", json={"version": "0.6.0"}, headers=api.auth
    )
    assert updated.status_code == 200
    assert updated.json() == {"name": "web", "target": "0.6.0", "healthy": True}
    runner.build.assert_called_once_with(no_cache=True)


def test_adopt_with_no_legacy_reports_not_adopted(api: SimpleNamespace) -> None:
    resp = api.client.post("/v1/adopt", headers=api.auth)
    assert resp.status_code == 200
    assert resp.json()["adopted"] is False
