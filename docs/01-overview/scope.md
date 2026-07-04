---
service: mad-cli
domain: backend
section: overview
source_of_truth: repo
---
# Scope and non-goals

mad-cli is an operator CLI with a tightly bounded job. Understanding what it does *not* do is as important as what it does.

## Non-goals

mad-cli:

- NEVER runs agents.
- NEVER parses LLM output.
- NEVER manages an agent loop.
- NEVER talks to the agent runtime's API.

All of that is entirely mad-edge's job, inside the container.

Further:

- It does not itself expose an HTTP or MCP API.
- It does not own or persist agent data. The container's data lives on host bind mounts under the data path, owned by the operator.
- It manages secrets only to the extent of writing them into the instance `.env` and the Claude credentials file.

## What mad-cli does

Its job is bounded to:

- Check Docker.
- Collect configuration.
- Render the instance files: `Dockerfile`, `compose.yml`, `.env`, and `entrypoint.sh`.
- Build the image.
- Drive the container lifecycle: `up`, `down`, `restart`, `ps`, `logs`, `exec`, and `health`.
