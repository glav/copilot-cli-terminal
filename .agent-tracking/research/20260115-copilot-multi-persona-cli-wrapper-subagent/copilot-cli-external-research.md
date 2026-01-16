# External research: GitHub Copilot CLI (preview) vs `gh copilot` extension

Access date for all sources: **2026-01-15**

## Scope / what this is (and isn’t)
This research is about **GitHub Copilot on the command line** (GitHub/Microsoft Copilot), not **AWS Copilot**.

## Executive summary
There are **two distinct “Copilot in the terminal” command surfaces** that are easy to conflate:

1) **Standalone GitHub Copilot CLI (public preview)**: invoked primarily as **`copilot`**. It is an agentic terminal app that can read/modify files, run commands, use MCP servers, and run in interactive or programmatic (`-p`) mode.

2) **Legacy GitHub CLI extension**: invoked as **`gh copilot …`** (an extension for GitHub CLI). This provides a more limited “suggest/explain” flow and is now **retired/deprecated** in favor of the standalone Copilot CLI.

Because the names overlap (“Copilot in the CLI”, “Copilot CLI”), a wrapper should treat these as **separate backends** and choose integration points deliberately.

## What command is “the Copilot CLI”?
### Standalone GitHub Copilot CLI (preview)
- **Primary command**: `copilot` (interactive mode)
- **Programmatic one-shot mode**: `copilot -p "…"` / `copilot --prompt "…"`
- GitHub Docs “About GitHub Copilot CLI” explicitly describes interactive mode as starting with the `copilot` command and notes `-p/--prompt` for programmatic mode.

Sources:
- https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli

### Legacy GitHub CLI extension (retired)
- **Command surface**: `gh copilot <subcommand>`
- The archived repository `github/gh-copilot` describes it as an extension for GitHub CLI and shows `gh copilot suggest` and `gh copilot explain`.

Sources:
- https://github.com/github/gh-copilot
- https://github.com/github/gh-copilot/blob/main/README.md

## Core subcommands / capabilities
### Standalone `copilot` CLI (preview)
GitHub’s docs emphasize:
- Interactive sessions started by `copilot`.
- Programmatic mode via `-p/--prompt`.
- Extensive tool/permission system (paths, URLs, allow/deny tools) and slash commands.

The GitHub Docs usage guide calls out several **slash commands** and UX conventions:
- `/login` to authenticate when not logged in.
- `@path/to/file` to include a file’s contents as prompt context.
- `!<shell command>` to run a shell command directly without calling the model.
- `/delegate` to hand off work to Copilot coding agent on GitHub.
- `/cwd` and `/add-dir` for directory management.
- `/agent` to switch/select custom agents.
- `/mcp add` to add an MCP server.
- `/usage` and `/context` for session stats/context.
- “Find out more” suggests `copilot help` (and `copilot help config|environment|logging|permissions`) as the authoritative command list.

Sources:
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli
- https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli
- GitHub changelog post (Jan 14, 2026) describing built-in agents and scripting flags: https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install

Notes:
- I did not enumerate every `copilot` flag or slash command because the docs point to `copilot --help` / `copilot help` and in-CLI `?` for the canonical list.

### Legacy `gh copilot` extension
`gh copilot --help` in the `gh-copilot` README shows the command set:
- `gh copilot suggest` — suggest a command from natural language.
- `gh copilot explain` — explain a command.
- `gh copilot alias` — generate shell aliases/helpers (including `ghcs` and `ghce` wrappers).
- `gh copilot config` — configure options.

Sources:
- https://github.com/github/gh-copilot/blob/main/README.md

## Typical installation methods
### Standalone `copilot` CLI
GitHub Docs “Installing GitHub Copilot CLI” lists these installation paths:
- Windows: `winget install GitHub.Copilot` (and prerelease `GitHub.Copilot.Prerelease`)
- macOS/Linux: `brew install copilot-cli` (and `copilot-cli@prerelease`)
- All platforms (requires Node.js 22+): `npm install -g @github/copilot` (and `@github/copilot@prerelease`)
- macOS/Linux install script: `curl -fsSL https://gh.io/copilot-install | bash` (or `wget -qO- … | bash`)
- Direct downloads from GitHub releases are also mentioned.

Sources:
- https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli
- https://github.com/github/copilot-cli
- https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install

### Legacy `gh copilot` extension
The `gh-copilot` README quickstart uses GitHub CLI’s extension mechanism:
- `gh extension install github/gh-copilot --force`

Source:
- https://github.com/github/gh-copilot/blob/main/README.md

## Typical authentication flow
### Standalone `copilot` CLI
GitHub Docs “Installing GitHub Copilot CLI” and the `copilot-cli` README agree:
- On first launch, if not logged in, you run `/login` and follow on-screen instructions.
- Alternative: authenticate with a **fine-grained PAT** with **“Copilot Requests”** permission enabled, supplied via `GH_TOKEN` or `GITHUB_TOKEN` (in that order of precedence per docs).

Sources:
- https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli
- https://github.com/github/copilot-cli
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli

### Legacy `gh copilot` extension
The `gh-copilot` README states:
- You must authenticate using the **GitHub CLI OAuth app** (example: `gh auth login --web`).
- PATs are “currently unsupported” and may require clearing `GITHUB_TOKEN` and `GH_TOKEN` env vars.

Source:
- https://github.com/github/gh-copilot/blob/main/README.md

## Explicit ambiguity callouts: `copilot` vs `gh copilot`
### 1) Same words, different products
- GitHub Docs includes pages that mention “GitHub Copilot in the CLI”, “Copilot CLI”, and “GitHub CLI Copilot extension”.
- The page https://docs.github.com/en/copilot/github-copilot-in-the-cli is titled “Using the GitHub CLI Copilot extension” and says it “provides details about the replacement for the Copilot extension for GitHub CLI,” while also pointing to “About GitHub Copilot CLI.” This is an easy place for confusion because the URL path implies “Copilot in the CLI” but the content is about the retired extension and its replacement.

Source:
- https://docs.github.com/en/copilot/github-copilot-in-the-cli

### 2) Repo name vs command name mismatch
- The standalone preview product is “GitHub Copilot CLI” but the GitHub repo is `github/copilot-cli` and the npm package is `@github/copilot`, while the executable is `copilot`.

Sources:
- https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli
- https://github.com/github/copilot-cli

### 3) `gh-copilot` repo indicates it was deprecated in favor of `github/copilot-cli`
- The `gh-copilot` repo header notes it has been deprecated (Oct 25, 2025) in favor of GitHub Copilot CLI, and the repo itself is archived read-only.

Sources:
- https://github.com/github/gh-copilot

## Recommendations for our wrapper integration (evidence-based)
### Recommendation A (default): integrate with standalone `copilot` for “multi-persona/agent” workflows
Evidence:
- GitHub describes `copilot` as an **agentic assistant** that can create/modify files, execute commands, manage context, support custom agents, and integrate with MCP.
- Official installation guidance emphasizes standalone install methods (winget/brew/npm/script) and highlights built-in agents and automation flags.

Why it matters for our wrapper:
- Your “multi-persona” wrapper aligns naturally with Copilot CLI’s **custom agents** (`/agent`, `--agent=...`) and context/scoping controls.
- It supports both interactive and scripted entrypoints (`copilot` and `copilot -p ...`), which is useful for a wrapper that might need a programmatic mode.

Sources:
- https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli
- https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install

### Recommendation B (compatibility mode): treat `gh copilot` as a legacy backend (optional)
Evidence:
- The GitHub CLI extension is explicitly retired/replaced.
- It provides a small, stable set of subcommands (`suggest`, `explain`, etc.).

Why it matters:
- Some users may still have `gh copilot` installed (or locked-down environments where they can’t install the new standalone CLI). A wrapper can optionally detect and pass-through to `gh copilot` for basic “suggest/explain” use-cases.

Sources:
- https://docs.github.com/en/copilot/github-copilot-in-the-cli
- https://github.com/github/gh-copilot

### Recommendation C (implementation detail): prefer pass-through execution rather than “reimplementing”
Evidence:
- Both official docs emphasize `copilot help` / in-CLI `?` for canonical command lists and evolving preview features.

Why it matters:
- If our wrapper shells out to `copilot` (or `gh copilot` in legacy mode), we inherit upstream behavior and don’t fight fast-moving preview changes.

## Evidence log (URLs + access date)
All accessed: **2026-01-15**

### Standalone GitHub Copilot CLI (preview)
- About Copilot CLI (concepts): https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli
- Install Copilot CLI: https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli
- Use Copilot CLI: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli
- Responsible use of Copilot CLI: https://docs.github.com/en/copilot/responsible-use/copilot-cli
- Copilot CLI repository: https://github.com/github/copilot-cli
- Copilot CLI releases: https://github.com/github/copilot-cli/releases
- GitHub changelog (Jan 14, 2026) describing built-in agents + install methods + scripting flags: https://github.blog/changelog/2026-01-14-github-copilot-cli-enhanced-agents-context-management-and-new-ways-to-install

### Legacy `gh copilot` (GitHub CLI extension)
- Archived extension repo: https://github.com/github/gh-copilot
- Extension README (commands/quickstart/auth caveats): https://github.com/github/gh-copilot/blob/main/README.md
- Extension releases (deprecation note & references to Copilot CLI): https://github.com/github/gh-copilot/releases

### GitHub CLI (context for `gh auth login`)
- GitHub CLI quickstart (shows `gh auth login`): https://docs.github.com/en/github-cli/github-cli/quickstart
- About GitHub CLI: https://docs.github.com/en/github-cli/github-cli/about-github-cli

## Open questions / limitations
- I did not capture a full, enumerated list of `copilot` flags or slash commands beyond those explicitly called out in docs and changelog. GitHub positions `copilot help` / in-CLI `?` as the canonical, current list.
- Some older GitHub Docs URLs under `/copilot/github-copilot-in-the-cli/...` returned 404 during retrieval, suggesting docs information architecture changed; the authoritative “install” and “use” pages above appear current.
