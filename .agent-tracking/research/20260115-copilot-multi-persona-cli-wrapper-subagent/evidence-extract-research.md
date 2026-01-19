# Evidence extract — Copilot multi-persona CLI wrapper

Access date for all items: **2026-01-15**

## Evidence table

| Finding | URL (if any) | Access date | Quote/snippet (from subagent memo) |
|---|---|---:|---|
| Two different “Copilot in the terminal” command surfaces exist and are easy to conflate: standalone **`copilot`** vs legacy **`gh copilot`** | https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli | 2026-01-15 | “There are **two distinct ‘Copilot in the terminal’ command surfaces**… 1) **Standalone GitHub Copilot CLI (public preview)**: invoked primarily as **`copilot`** … 2) **Legacy GitHub CLI extension**: invoked as **`gh copilot …`**.” |
| Standalone Copilot CLI primary command is `copilot`; supports programmatic prompt mode via `-p/--prompt` | https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli | 2026-01-15 | “Interactive mode: Start an interactive session by using the `copilot` command.” / “You do this by using the `-p` or `--prompt` command-line option.” |
| Standalone Copilot CLI supports richer “agentic” workflows (permissions/tools/context, slash commands, MCP, custom agents) | https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli | 2026-01-15 | Memo notes docs call out: “`/login`… `@path/to/file`… `!<shell command>`… `/delegate`… `/cwd`… `/add-dir`… `/agent`… `/mcp add`… `/usage`… `/context`.” |
| Legacy `gh copilot` extension provides a smaller command set: suggest/explain/alias/config | https://github.com/github/gh-copilot/blob/main/README.md | 2026-01-15 | “`gh copilot suggest` — suggest a command… `gh copilot explain` — explain a command… `gh copilot alias`… `gh copilot config`…” |
| Legacy `gh-copilot` is deprecated and the repository is archived/read-only | https://github.com/github/gh-copilot | 2026-01-15 | “This repository was archived by the owner on Oct 30, 2025. It is now read-only.” |
| Legacy “GitHub Copilot in the CLI” (`gh copilot`) is deprecated in favor of “GitHub Copilot CLI” (`copilot`) | https://github.com/github/gh-copilot/blob/main/README.md | 2026-01-15 | “GitHub Copilot in the CLI has been deprecated on October 25, 2025 in favor of GitHub Copilot CLI…” |
| Standalone Copilot CLI installation methods include WinGet, Homebrew, npm, install script, and direct downloads | https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli | 2026-01-15 | “You can install Copilot CLI using WinGet (Windows), Homebrew (macOS and Linux), npm (all platforms), or an install script (macOS and Linux).” / “You can download the executables directly from the copilot-cli repository.” |
| Installing via npm requires Node.js 22+ | https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli | 2026-01-15 | “Installing with npm (all platforms, requires Node.js 22+)” |
| Standalone Copilot CLI authentication supports `/login` and PAT via `GH_TOKEN`/`GITHUB_TOKEN` with “Copilot Requests” permission | https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli | 2026-01-15 | “On first launch, if you're not currently logged in to GitHub, you'll be prompted to use the `/login` slash command.” / “You can also authenticate using a fine-grained personal access token with the \"Copilot Requests\" permission enabled.” / “Add the token to your environment using the `GH_TOKEN` or `GITHUB_TOKEN` environment variable (in order of precedence).” |
| Legacy `gh copilot` extension auth uses `gh auth login` (OAuth); PATs unsupported (may need clearing `GITHUB_TOKEN`/`GH_TOKEN`) | https://github.com/github/gh-copilot/blob/main/README.md | 2026-01-15 | “You must authenticate using the **GitHub CLI OAuth app**… PATs are ‘currently unsupported’ and may require clearing `GITHUB_TOKEN` and `GH_TOKEN` env vars.” |
| Naming ambiguity exists in GitHub Docs: a URL path about “copilot in the cli” discusses the retired extension + replacement | https://docs.github.com/en/copilot/github-copilot-in-the-cli | 2026-01-15 | “This is an easy place for confusion because the URL path implies ‘Copilot in the CLI’ but the content is about the retired extension and its replacement.” |
| Product/repo/package naming mismatch: product “GitHub Copilot CLI”, repo `github/copilot-cli`, npm `@github/copilot`, executable `copilot` | https://github.com/github/copilot-cli | 2026-01-15 | “Standalone preview product is ‘GitHub Copilot CLI’ but the GitHub repo is `github/copilot-cli` and the npm package is `@github/copilot`, while the executable is `copilot`.” |
| Changelog indicates Jan 14, 2026 Copilot CLI updates: enhanced agents/context and install/scripting changes | https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install | 2026-01-15 | Memo cites this post as describing “built-in agents and scripting flags” plus “context management” and “new ways to install.” |
| In this devcontainer, `tmux` is not installed (`tmux: command not found`) | (none — local container probe) | 2026-01-15 | “Output: `command -v tmux: NOT FOUND` … `bash: tmux: command not found`.” |
| Debian base image is Debian 13 (trixie) | (none — local container probe) | 2026-01-15 | “`PRETTY_NAME=\"Debian GNU/Linux 13 (trixie)\"` … `VERSION_ID=\"13\"`.” |
| `apt-get -s install tmux` reports “no installation candidate” (in this container config) | (none — local container probe) | 2026-01-15 | “`E: Package 'tmux' has no installation candidate`.” |
| `sudo` works non-interactively, but installing tmux may require apt source changes/updates (not attempted) | (none — local container probe) | 2026-01-15 | “`sudo -n true: OK (no password)`… Interpretation: ‘sudo works… but tmux cannot be installed from configured apt sources (at least without changing apt sources or running apt update; not attempted).’” |
| Deterministic tmux pane orchestration: create session detached, capture `pane_id` on split (`-P -F`), then normalize layout | (none — command patterns) | 2026-01-15 | “Key best practice: capture pane IDs… `split-window -P -F \"#{pane_id}\"`… ‘You never rely on pane indexes… `select-layout tiled` normalizes sizing…’” |
| Pane titles are separate from display; to show titles, set `pane-border-status` + `pane-border-format` and set titles with `select-pane -T` | (none — command patterns) | 2026-01-15 | “Setting a pane title doesn’t automatically display it… `pane-border-status top`… `pane-border-format \"#{pane_title}\"`… `select-pane -T \"Planner\"`.” |

## Caveats / ambiguities

- “Copilot CLI” naming is overloaded:
  - Standalone GitHub Copilot CLI (command: `copilot`) vs legacy GitHub CLI extension (command: `gh copilot …`).
  - Also unrelated to AWS Copilot (explicitly excluded in the memo).
- The table mixes older memo-derived rows with verbatim quotes. Rows updated in this step are verbatim quotes extracted from the fetched sources on 2026-01-15.
- Auth details differ materially between the two command surfaces:
  - Standalone supports `/login` and PAT via `GH_TOKEN`/`GITHUB_TOKEN` (with the noted “Copilot Requests” permission), while the legacy extension memo states PATs are unsupported.
- The tmux installability conclusion is specific to this devcontainer’s configured apt sources at time of probing:
  - The memo explicitly notes `apt update` and apt source changes were not attempted; “no installation candidate” may not generalize to other Debian environments.
- The GitHub Docs information architecture may be in flux:
  - The memo notes some older URLs under `/copilot/github-copilot-in-the-cli/...` returned 404 during the original research, so the “install” and “use” pages cited are treated as current/authoritative.
