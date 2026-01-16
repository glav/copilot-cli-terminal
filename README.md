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

## Copilot multi-persona CLI (MVP)

This repo includes an MVP terminal tool that launches a 4-persona workflow using `tmux` panes (Linux-only).

This tool orchestrates panes and shared context files; it does not replace the underlying GitHub Copilot CLI.

Not AWS Copilot: this project targets **GitHub Copilot CLI** (the standalone `copilot` command), not the AWS “copilot” CLI.

### Prereqs

- `tmux` installed and available on `PATH`
- GitHub Copilot CLI (`copilot`) installed and authenticated

Debian/Ubuntu (including many devcontainers):

```bash
sudo apt-get update
sudo apt-get install -y tmux
```

### Install GitHub Copilot CLI

GitHub Copilot CLI is currently distributed via multiple methods (choose one):

- WinGet (Windows)
- Homebrew (macOS and Linux)
- npm (all platforms, requires Node.js 22+)
- Install script (macOS and Linux)

### Authenticate

On first launch of `copilot`, you’ll be prompted to log in using the `/login` slash command.

For non-interactive/auth automation, you can also use a fine-grained PAT with the “Copilot Requests” permission via `GH_TOKEN` or `GITHUB_TOKEN`.

When you run `copilot-multi start`, it will preflight-check whether `copilot` is already authenticated. If not, it will temporarily launch `copilot` so you can run `/login`, then it continues and starts the tmux session.

Note: the first time it launches `copilot` you may also see a folder trust prompt. Choose “Yes, and remember this folder for future sessions” if you want to avoid being asked again.

### Run

```bash
uv run copilot-multi start
```

To start the session in the background (no attach):

```bash
uv run copilot-multi start --detach
```

This creates/uses `.copilot-multi/` for shared context and a session state file at `.copilot-multi/session.json`.

Each tmux pane starts in a lightweight "Copilot router" REPL:

- Anything you type is forwarded to the GitHub Copilot CLI (`copilot`) via a shared local broker, so all panes share one Copilot session/history.
- To run wrapper commands locally (not via Copilot), prefix them with `copilot-multi`, for example: `copilot-multi status`.

If you want to authenticate Copilot CLI ahead of time (without launching tmux):

```bash
uv run copilot-multi auth
```

### Pane colors / theme

The pane REPL supports ANSI-colored headers and persona prompts (e.g. `pm>`, `review>`).

Config lookup (lowest → highest precedence):

- `~/.config/copilot-multi/config.toml` (or `$XDG_CONFIG_HOME/copilot-multi/config.toml`)
- `./copilot-multi.toml`
- `./.copilot-multi/config.toml`
- `$COPILOT_MULTI_CONFIG` (explicit path)

Example `copilot-multi.toml`:

```toml
[ui]
color = true

[ui.styles]
header = "bold cyan"
tips = "dim"
prompt_delim = "dim white"

[ui.persona_prompt]
pm = "bold magenta"
impl = "bold blue"
review = "bold green"
docs = "bold yellow"
```

### Coordination

```bash
uv run copilot-multi status
uv run copilot-multi set-status pm working --message "Drafting scope + acceptance"
uv run copilot-multi wait impl --status done --timeout 1800
uv run copilot-multi stop
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
