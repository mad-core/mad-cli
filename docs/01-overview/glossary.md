---
service: mad-cli
domain: backend
section: overview
source_of_truth: repo
---
# Glossary

One term, one definition.

| Term | Definition |
| --- | --- |
| instance | One mad-edge container plus its config directory (`compose.yml`, `.env`, `Dockerfile`, `entrypoint.sh`). The modern layout keeps one directory per instance under `~/.config/mad/instances/<name>/`. |
| config root | `~/.config/mad` (or `$MAD_CLI_CONFIG_DIR`); holds `instances/`. |
| legacy (single-instance) layout | The old layout that kept the four config files directly at the config root. `mad adopt` migrates it into `instances/<name>/`. |
| .env | The per-instance environment file mad-cli writes and edits. A comment- and order-preserving parser gives it a byte-stable round-trip. |
| compose project | `mad-<name>`, the Docker Compose project name each instance is scoped to (`-p mad-<name>`), so instances never collide. |
| edge package | The PyPI package installed inside the container (default `mad-edge`; the `mad-bros` variant's server script is `mad`). Overridable per instance. |
| key / builtin key | A credential stored in `.env`. A builtin key (from the key registry) fans one value out to one or more env vars (e.g. `github` produces `GITHUB_TOKEN` + `GH_TOKEN`). Builtins: `claude-oauth`, `anthropic`, `github`, `deepseek`, `linear`, `opencode`. |
| pin (MAD_VERSION) | The mad-edge version an instance is pinned to (blank tracks latest). |
| data path (MAD_DATA_PATH) | The host directory holding each instance's `workspaces/`, `claude/`, and `aws/` bind mounts. |
