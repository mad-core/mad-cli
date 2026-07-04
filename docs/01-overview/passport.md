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
| interface profile | cli (no http, no sse, no mcp) |
| console script | `mad` (also `python -m mad_cli`) |
| language | Python (>= 3.11) |
| packaging | hatchling |
| distribution | PyPI `mad-cli` |
| status | Alpha (0.x) |
| current version | 0.2.0 |
| runtime deps | typer, rich |
| license | MIT |

## Section registry

This repo declares these optional doc sections:

- overview
- architecture
- contracts
- conventions
- operations
- history

Some generic backend sections are intentionally omitted:

- No `api-reference` / `data-model` / `events`: a CLI has no HTTP app object and no persistence, so there is nothing to reference, model, or emit.
- No `decisions` / `rfcs` / `user-manuals` sections: `CONTRACTS.md` is the frozen interface record, and the command reference in `03-contracts/cli.md` serves the operator directly.
