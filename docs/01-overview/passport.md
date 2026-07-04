---
service: mad-cli
domain: backend
section: overview
source_of_truth: repo
---
# Passport

A one-page service card for mad-cli.

| Field | Value |
| --- | --- |
| service | mad-cli |
| domain | backend |
| role | operator CLI that installs and manages mad-edge containers |
| interface profile | cli + http (the HTTP API is an optional extra; no sse, no mcp) |
| console script | `mad` (also `python -m mad_cli`) |
| language | Python (>= 3.11) |
| packaging | hatchling |
| distribution | PyPI `mad-cli` |
| status | Alpha (0.x) |
| current version | 0.3.2 |
| runtime deps | typer, rich (base); fastapi, uvicorn (the optional `server` extra) |
| license | MIT |

## Section registry

This repo declares these optional doc sections:

- overview
- architecture
- contracts
- conventions
- operations
- history

The command surface (`03-contracts/cli.md`) and the optional HTTP API (`03-contracts/http-api.md`) are the operator-facing contracts.

Some generic backend sections are intentionally omitted:

- No `data-model` / `events`: mad-cli has no persistence layer and emits no events. The HTTP API is a stateless adapter over the same use cases the CLI drives; it stores nothing beyond the per-instance `.env`.
- No `decisions` / `rfcs` / `user-manuals` sections: `CONTRACTS.md` is the frozen interface record, and the reference pages in `03-contracts/` serve the operator directly.
