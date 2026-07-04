---
service: mad-cli
domain: backend
section: contracts
source_of_truth: repo
---
# HTTP API Reference (v1)

The local HTTP API mirrors the `mad` CLI over HTTP so a UI/dashboard (and later remote fleet management) can build on the exact same use cases. It ships as the optional `server` extra (`pip install 'mad-cli[server]'`) so the base CLI stays a two-dependency package; the routes are thin adapters over `mad_cli.core.usecases`, the same functions the Typer commands call, so the two surfaces cannot drift.

The FastAPI app (`mad_cli.server.create_app()`) publishes an OpenAPI schema at `GET /openapi.json` and interactive docs at `/docs`.

## Running it

- `mad serve [--host --port]` runs the API in the foreground (uvicorn). Default bind `127.0.0.1:7373`.
- `mad service install` installs it as a boot-persistent background service (systemd user unit / launchd LaunchAgent) — see [`cli.md`](cli.md#service-mode-http-api).

When the `server` extra is not importable, `mad service install` auto-provisions a dedicated venv under `config_root()/server-venv` (from PyPI, or a local wheel via `--wheel`) and points the service at it — the operator never has to install FastAPI into their main environment.

## Authentication

Every route except `GET /health` requires a bearer token:

```
Authorization: Bearer <token>
```

The token is auto-generated on the first `mad serve` / `mad service install` and stored at `config_root()/api-token` (mode `0600`). A missing or wrong token is a **401**; a server with no token file is a **503**. The comparison is constant-time.

The API binds `127.0.0.1` by default. A non-loopback `--host` prints a loud warning; put it behind a firewall/VPN — anyone who can reach the address and holds the token can control your instances.

## Secrets

Secret-looking values (`*TOKEN*`, `*KEY*`, `*SECRET*`, `*PASSWORD*`) are **always** returned masked (`ghp_…f3`). There is no reveal flag on the API — a full secret is never sent over the wire, on any route.

## Endpoints

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Liveness (no auth). Returns `{status, version}`. |
| `GET /v1/instances` | List instances (name, port, state, health, version). |
| `POST /v1/instances` | Non-interactive install (201). Body mirrors the `mad install` flags. |
| `GET /v1/instances/{name}` | Instance paths + `.env` (masked). |
| `POST /v1/instances/{name}/start` | Build if needed, start, wait for health. |
| `POST /v1/instances/{name}/stop` | Stop and remove the containers. |
| `POST /v1/instances/{name}/restart` | Restart the containers. |
| `GET /v1/instances/{name}/status` | Container state, health summary, URL. |
| `GET /v1/instances/{name}/config` | List `.env` values (masked). |
| `PUT /v1/instances/{name}/config/{key}` | Set a value (body `{value}`); validated known keys. |
| `DELETE /v1/instances/{name}/config/{key}` | Unset a value (404 if absent). |
| `GET /v1/instances/{name}/keys` | Builtin key status + custom secrets (masked). |
| `PUT /v1/instances/{name}/keys/{id}` | Set a key (body `{value}`); builtins fan out. |
| `DELETE /v1/instances/{name}/keys/{id}` | Remove a key (404 if unset). |
| `GET /v1/instances/{name}/versions` | Pinned / installed / latest / update status. |
| `POST /v1/instances/{name}/update` | Re-pin `MAD_VERSION` and rebuild (body `{version}`). |
| `POST /v1/adopt` | Migrate the legacy single-instance layout. |

### Error mapping

Use-case failures map to status codes: `ValidationError → 400`, `NotFoundError → 404`, `ConflictError`/`AmbiguousInstanceError → 409`, `PreconditionError → 412`. The body is `{"detail": "<message>"}`.

## MVP limitations

Long operations — install with `start=true`, `start`, and `update` — run **synchronously**: the request blocks until the Docker build and health wait finish (potentially minutes). Background jobs / async status polling are a future enhancement (tracked separately). Clients should use a generous timeout for these routes.
