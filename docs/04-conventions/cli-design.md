---
service: mad-cli
domain: backend
section: conventions
source_of_truth: repo
---

# CLI design conventions

## Typer app shape

The CLI is a Typer application configured so that a bare `mad` prints help
(`no_args_is_help=True`), completion is disabled (`add_completion=False`), and
the app carries a help string. The version is exposed through an eager
`--version` callback: it prints `mad_cli.__version__` and then raises
`typer.Exit()`.

## Instance resolution

A single resolution pattern is shared across the lifecycle, keys, config and
versions commands:

- If a name or `--instance` is given, resolve it via `get_instance`. On a miss,
  emit an error and raise `typer.Exit(1)`, hinting `mad list`.
- Otherwise, fall back to `default_instance()` (the sole instance).
- With zero instances, error and hint `mad install`.
- With several instances, error listing the instance names and asking the user
  to name one.

## Non-interactive contract

Prompt behaviour lives in `ui/prompts.py` and must never block when stdin is not
a TTY (or under `--yes`):

- `ask` returns its default if one exists; otherwise it raises
  `PromptRequiredError`.
- `confirm` returns its default.
- Interactive `ask` re-prompts while a validator raises `ValueError`. The
  validator's return value is the normalised answer.
- `install --yes` short-circuits to flags plus defaults, and if a required value
  is missing it exits 1 naming the flag.

## Secret masking

Every display of a credential is masked:

- `core.keyspec.mask` shows a short prefix/suffix (for example `abcd…yz`) or `…`
  for short values.
- `commands/_common.is_secret_key(key)` treats a key as secret when its name
  contains `TOKEN`, `KEY`, `SECRET` or `PASSWORD`.
- `config get` masks unless `--reveal` is passed.
- `keys list`, `keys info` and the install summary always mask.

## Output helpers

There is a single shared rich `Console` (`ui/console.py`) with status glyph
helpers `info`, `ok`, `warn`, `error` and `header`, plus a `run_step` that shows
a spinner on a real terminal but falls back to a plain line under redirected or
test output (deterministic and non-blocking). `error` only renders; callers
decide whether to exit.

## Restart hint

Mutating commands (keys, config) end with a hint:
`Restart the instance to apply: mad restart <name>`.
