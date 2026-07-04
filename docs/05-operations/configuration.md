---
service: mad-cli
domain: backend
section: operations
source_of_truth: repo
---

# Configuration keys

This page lists key NAMES and their purposes only. Values are never shown here, and secret-looking keys are masked in the CLI. There are two layers of configuration.

## Layer A — mad-cli's own host-side setting

- `MAD_CLI_CONFIG_DIR` — overrides the default config root `~/.config/mad` (read by `core.paths`).

## Layer B — per-instance `.env` keys

These are the keys mad-cli writes and manages in `~/.config/mad/instances/<name>/.env`. Most are assembled by `mad install`.

| Key | Purpose | Secret? |
| --- | --- | --- |
| `MAD_INSTANCE` | The instance name. | No |
| `MAD_HOST_PORT` | Host port mapped to container port 8000 (validated 1–65535; baked into `compose.yml` at install time, so a change needs the instance regenerated). | No |
| `MAD_DATA_PATH` | Host data root holding per-instance workspaces/claude/aws mounts (also baked into `compose.yml`). | No |
| `MAD_VERSION` | Pinned mad-edge version (blank = latest). | No |
| `MAD_AGENT_TIMEOUT_S` | Agent wall-clock timeout in seconds (validated positive integer). | No |
| `MAD_SESSIONS_DIR` | Container-side path for mad-edge's session logs. Pinned to `/sessions` in the generated `compose.yml` (not written to `.env`), matching the dedicated `<data_path>/<instance>/sessions` bind mount so the mount and the variable cannot diverge. | No |
| `MAD_SESSIONS_RETENTION_DAYS` | Session-log retention in days (integer ≥ 1). Written by `mad install --retention-days`; left as a commented reference when omitted (unset = keep session logs forever). | No |
| `MAD_MCP_ALLOWED_HOSTS` | Comma-separated MCP allowed hosts for DNS-rebinding protection. Written by `mad install --mcp-allowed-hosts`; left as a commented reference when omitted (unset = protection disabled). | No |
| `MAD_SSE_HEARTBEAT_S` | SSE keep-alive heartbeat in seconds. Never prompted; `mad install` leaves it as a commented reference for the operator to enable by hand. | No |
| `PUID` | Host uid for the container's non-root user. | No |
| `PGID` | Host gid for the container's non-root user. | No |
| `GIT_AUTHOR_NAME` | Git identity for the agent's commits. | No |
| `GIT_AUTHOR_EMAIL` | Git identity for the agent's commits. | No |
| `GIT_COMMITTER_NAME` | Git identity for the agent's commits. | No |
| `GIT_COMMITTER_EMAIL` | Git identity for the agent's commits. | No |
| `GITHUB_TOKEN` | GitHub token (fanned out from the `github` key) for agent clones/pushes/PRs. | Yes |
| `GH_TOKEN` | GitHub token (fanned out from the `github` key) for agent clones/pushes/PRs. | Yes |
| `_CLAUDE_OAUTH_TOKEN` | Claude OAuth token; also materialised into `<data_path>/<instance>/claude/.credentials.json` (chmod 600). | Yes |
| `MAD_EDGE_PACKAGE` | Optional; overrides the PyPI package checked/installed (default `mad-edge`). | No |
| `ANTHROPIC_API_KEY` | Registry credential (anthropic), set via `mad install --anthropic-api-key` or `mad keys set`. | Yes |
| `DEEPSEEK_API_KEY` | Registry credential (deepseek), set via `mad install --set-key deepseek=…` or `mad keys set`. | Yes |
| `LINEAR_API_KEY` | Registry credential (linear), set via `mad install --set-key linear=…` or `mad keys set`. | Yes |
| `OPENCODE_API_KEY` | Registry credential (opencode), set via `mad install --set-key opencode=…` or `mad keys set`. | Yes |

## Editing

- `mad config get|set|unset` — general-purpose `.env` editor.
- `mad keys set|list|remove` — credential-aware editor.

Notes on behaviour:

- Secret-looking keys (name contains `TOKEN`, `KEY`, `SECRET` or `PASSWORD`) are masked on display unless `--reveal` is passed.
- The compose-baked keys (`MAD_HOST_PORT`, `MAD_DATA_PATH`) write to `.env` but warn that a regenerate is required to take effect.
- Every mutation ends with a restart hint.
