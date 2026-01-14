# Template - Python

This repository is a small, intentionally minimal Python template you can use as the starting point for new repos.

It’s designed to be a quick workflow to get started while keeping the day-0 developer experience solid (devcontainer support, modern dependency management, and a place for agent instructions).

## What this template includes

- Python 3.12 devcontainer setup
- `uv` for dependency management (`pyproject.toml` + `uv.lock`)
- A tiny runnable entrypoint (`src/app.py`) that loads environment variables from `.env` via `python-dotenv`
- `AGENTS.md` for coding-agent guidance

## Using this repo as a template

Typical workflow:

1. Create a new repository from this template (GitHub: “Use this template”).
2. Update project metadata in `pyproject.toml` (name/description).
3. Replace the sample app code under `src/` with your real project.
4. Update `AGENTS.md` and this README to reflect the new repo’s purpose.

## Setup

This repo uses `uv`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Run

```bash
uv run python src/app.py
```

## Linting and formatting

This template includes `ruff`.

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format .
```

## Environment variables

- Copy `.env-sample` to `.env` and fill in values as needed.
- `.env` is gitignored.

```bash
cp .env-sample .env
```

## Copilot / AI Assisted workflow

This template includes an `.agent/` directory containing reusable prompt “commands” and standards you can use with GitHub Copilot (and other coding agents).

- `.agent/commands/`: ready-to-run prompts for common tasks, for example:
	- `setup/`: repo bootstrap tasks (e.g. creating `AGENTS.md`)
	- `project/`: planning prompts (e.g. sprint planning)
	- `docs/`: documentation prompts (e.g. creating ADRs)
- `.agent/standards/`: templates and standards for consistent artifacts (ADRs, feature specs, task plans)
- `.agent/instructions/`: “apply-to” instructions that guide how agents write certain file types (e.g. Bash and Bicep)

If you base a new repository on this template, treat `.agent/` as a starting library: keep what helps your team, remove what doesn’t, and add org-specific workflows over time.
