---
service: mad-cli
domain: backend
section: meta
source_of_truth: repo
---
# mad-cli docs

This `/docs` tree is the structured, faithful documentation for mad-cli. Its structure is declared in `docs/.docs-manifest.yaml`, and its source is pure Markdown. A downstream pipeline — `docs-sync` → `mad-core/mad-docs` under `raw/mad-cli/` — owns presentation, so do not add presentation syntax here (keep the source plain and portable).

## Sections

| Section | Holds |
| --- | --- |
| 01-overview | What mad-cli is, its context (upstream/downstream systems), scope and non-goals, and the glossary. |
| 02-architecture | Internal structure and components, plus the generated source and test trees. |
| 03-contracts | The CLI command surface and external dependencies. |
| 04-conventions | CLI design, package layering, quality gates, and testing strategy. |
| 05-operations | Installing mad-cli, configuration keys, CI/CD, and release. |
| 06-history | The changelog, mirrored from the release `CHANGELOG.md`. |

## Notes

- `source-tree.md` and `test-tree.md` carry a GENERATED marker and are re-created by `gen_docs`. Do not hand-edit them.
- Each manifest entry declares one of three doc kinds — deterministic, heuristic, or manual — so readers and tooling know how a page is produced and maintained.
