---
date: 2026-01-15
scope: repo instructions + conventions relevant to feature work
---

# Repo conventions research (2026-01-15)

This note captures the repo’s hard rules and conventions that are relevant while implementing the “copilot multi-persona CLI wrapper” feature (or adjacent work).

## Instruction / convention sources (exact paths)

### Repo-level Copilot/agent instruction
- `/workspaces/copilot-cli-terminal/.github/copilot-instructions.md`
  - Hard rule: **Do not proceed** unless `AGENTS.md` exists at repository root.
  - Observed state: `AGENTS.md` exists (requirement satisfied).
  - Note: this file does **not** contain any “Prompt Files Search Process” section or explicit workspace search restrictions.

### Repo conventions
- `/workspaces/copilot-cli-terminal/AGENTS.md`
  - Primary source for Python layout, dependency tooling, and dev workflow conventions.

### “ApplyTo” instruction files (workspace)
- `/workspaces/copilot-cli-terminal/.agent/instructions/prompt.instructions.md` (applyTo: `**/*.prompt.md`)
- `/workspaces/copilot-cli-terminal/.agent/instructions/bash/bash.instructions.md` (applyTo: `**/*.sh`)
- `/workspaces/copilot-cli-terminal/.agent/instructions/bash/bash.md` (referenced by `bash.instructions.md`)
- `/workspaces/copilot-cli-terminal/.agent/instructions/bicep/bicep.instructions.md` (applyTo: `**/infra/**/*.bicep`)
  - References additional required files (present):
    - `/workspaces/copilot-cli-terminal/.agent/instructions/bicep/bicep.md`
    - `/workspaces/copilot-cli-terminal/.agent/instructions/bicep/bicep-standards.md`

### `.github/instructions/**`
- Not present in this repo (directory does not exist), so no additional `.github/instructions/*` “applyTo” rules apply.

## Hard rules and conventions to follow

### Copilot / agent gating rule
- If `AGENTS.md` is missing at repo root, the agent must ask the user to run `/setup:agents-md-creation` and must not proceed until `AGENTS.md` exists.

### Python project conventions (from `AGENTS.md`)
- Source code placement: **Any source code should be added under `src/`**.
- Dependency management: use `uv` (see `pyproject.toml` / `uv.lock`).
  - Install deps: `uv sync`
  - Run app: `uv run python src/app.py`
- Environment variables:
  - Copy `.env-sample` to `.env`; `.env` is gitignored and must not be committed.
  - `.env` discovery in `src/load_env.py`: checks `.env` in CWD and `../.env`.
- Testing:
  - No test framework configured; if adding tests, prefer `pytest` under `tests/`.
- Lint/format:
  - Use `ruff`:
    - `uv sync --group dev`
    - `uv run ruff check .`
    - `uv run ruff format .`

### Prompt file conventions (apply when creating `**/*.prompt.md`)
- Include frontmatter fields: `description`, `mode` (`ask`/`edit`/`agent`), and `tools` (least-privilege).
- Model declaration should generally be omitted unless there’s a technical dependency (e.g., context window requirement).
- Prefer `.github/prompts/` placement and kebab-case names ending in `.prompt.md`.
- Prompt body should be structured and explicit (inputs, workflow, outputs, validation).

### Bash conventions (apply when creating `**/*.sh`)
- The `bash.instructions.md` file is explicit: you must read and follow `/workspaces/copilot-cli-terminal/.agent/instructions/bash/bash.md`.
- Key bash requirements from `bash.md`:
  - Start scripts with `#!/usr/bin/env bash`.
  - Enable strict mode: `set -e` and `set -o pipefail`.
  - Validate required inputs/env vars before use and emit clear error messages.
  - Quote variables consistently to avoid word splitting / injection.
  - Provide consistent `log()` and `err()` patterns; optionally debug mode (`set -x`).
  - Use readable command invocation: line continuations for fixed args; arrays for conditional args.

## Search restrictions (and how this research complied)

### What the repo instructions say
- `/workspaces/copilot-cli-terminal/.github/copilot-instructions.md` contains **no** “Prompts Files Search Process” and **no** explicit workspace search restrictions (no required include patterns, no forbidden paths).

### How this research complied anyway (conservative approach)
- Used **targeted reads** only:
  - `list_dir` on `/workspaces/copilot-cli-terminal/.github` and `/workspaces/copilot-cli-terminal/.agent/instructions`.
  - `read_file` on the exact instruction/convention files listed above.
  - `file_search` only to locate the exact output doc path before overwriting it.
- Avoided broad workspace searching (no `grep_search` / `semantic_search`) since the task was limited to a small, known set of files.

### Concrete guidance for future searches (recommended include patterns)
- If you do need to search in a future subtask, keep it scoped with `includePattern` to avoid dragging the full workspace:
  - For repo instructions: `includePattern: ".github/**"`
  - For agent instructions: `includePattern: ".agent/instructions/**"`
  - For Python code: `includePattern: "src/**"`
  - For docs/specs: `includePattern: "docs/**"`

## Implications for the multi-persona CLI wrapper feature

- Any new/modified Python modules should live under `src/` (likely `src/copilot_multi/`).
- New dependencies should be reflected via `uv` workflow (update `pyproject.toml`, then run `uv sync`; `uv.lock` will update accordingly).
- If adding tests, prefer `pytest` and create a `tests/` tree (the repo currently has no test harness).
- If adding shell helpers (e.g., `tmux` install scripts), they must comply with the bash guidelines in `/workspaces/copilot-cli-terminal/.agent/instructions/bash/bash.md`.
- If adding prompt files to automate workflows, follow the frontmatter + structure conventions in `/workspaces/copilot-cli-terminal/.agent/instructions/prompt.instructions.md`.

