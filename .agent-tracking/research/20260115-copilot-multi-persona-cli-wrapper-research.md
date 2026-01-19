<!-- markdownlint-disable-file -->
# Task Research Documents: Copilot Multi-Persona CLI Wrapper (Linux-only, tmux)

Research-only deep analysis of a Linux-only CLI wrapper/orchestrator that launches **four persona terminals** as a deterministic tmux 2x2 layout and coordinates work via a shared local folder `.copilot-multi/` and a shared session state file `.copilot-multi/session.json`.

✅ Verified: this repo already contains an MVP implementation under `src/copilot_multi/` with a console script entrypoint (`copilot-multi`).
⚠️ Key reliability gaps are in **deterministic tmux pane addressing** and **session.json corruption recovery / atomic writes**.

## Task Implementation Requests
* Harden and finalize the Linux-only tmux launcher (deterministic 2x2 pane creation, visible titles/labels, bootstrap commands)
* Harden session state semantics and storage (`.copilot-multi/session.json`): schema, locking, atomic writes, corruption recovery
* Confirm and document the correct Copilot CLI target (standalone `copilot` public preview) and explicitly exclude AWS Copilot
* Improve CLI UX and docs consistency (help output, README correctness, onboarding prerequisites like `tmux`)

## Scope and Success Criteria
* Scope: Linux-only MVP, tmux panes, local filesystem shared context, single-machine sessions.
* Assumptions:
  * ✅ `tmux` is required for the default launcher mode (no GUI, no Windows/macOS guarantees).
  * ✅ Persona behavior is driven by shared context files + explicit status changes (no prompt injection required for MVP).
  * ✅ Wrapper focuses on orchestration + coordination; actual coding help comes from upstream Copilot CLI.
* Success Criteria:
  * ✅ This dated research file is template-complete (all required sections present; no placeholders).
  * ✅ Evidence log is self-contained with concrete sources (URLs/quotes + repo file+line citations).
  * ✅ Exactly one recommended approach is selected per technical scenario (alternatives only appear in “Removed After Selection”).
  * ✅ Repo references use explicit line ranges (e.g., `src/...py L10-L42`) for key claims.

## Outline
* Repo conventions and current implementation snapshot (verified line references)
* Evidence log (Copilot CLI `copilot` vs legacy `gh copilot`; tmux availability; container install path)
* Technical scenarios (tmux launcher determinism, session state durability, Copilot CLI integration)
* Selected approach and implementation guidance (implementation-ready)

### Potential Next Research
* Confirm whether devcontainer should provision `tmux` automatically (Docker image layer) vs document it as a prerequisite
  * **Reasoning**: ✅ `tmux` is required for the default UX; in this container it becomes installable only after `apt-get update`.
  * **Reference**: `.agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-subagent/tmux-launcher-research.md`

## Research Executed

### File Analysis
* ✅ `src/copilot_multi/cli.py`
  * CLI surface: parser + subcommands wiring (`start`, `status`, `set-status`, `wait`, `stop`) at `L249-L279`, entrypoint dispatch at `L284-L295`.
  * Session schema definition in `_init_session_state()` at `L82-L97` and initialization-once behavior at `L100-L108`.
  * Persona-to-pane mapping uses fixed pane indexes at `L127-L150` (e.g., `copilot-multi:0.0` .. `0.3`).
  * “Schema repair” behavior on `set-status` at `L193-L203` (adds missing keys via `setdefault`, but does not validate whole schema).
* ✅ `src/copilot_multi/constants.py`
  * Personas and display names at `L1-L6`; allowed statuses at `L8`.
  * Directory and filenames: `DEFAULT_SHARED_DIR_NAME`, `DEFAULT_SESSION_FILE_NAME`, `TMUX_SESSION_NAME` at `L10-L13`.
* ✅ `src/copilot_multi/session_store.py`
  * Exclusive file locking with `fcntl.flock(LOCK_EX)` on an `os.open()` fd at `L46-L53` and unlock at `L56-L63`.
  * Read path uses `json.loads()` with no corruption recovery at `L14-L21`.
  * Write path truncates then rewrites the same file descriptor (not atomic replace) at `L22-L30`.
* ✅ `src/copilot_multi/tmux.py`
  * Fail-fast tmux availability check (`tmux -V`) at `L9-L27`.
  * Current tmux 2x2 pane creation uses index-based pane targeting at `L40-L62` (detailed step sequence at `L49-L55`).
  * Pane title set via `select-pane -T` argv elements at `L64-L68`.

### Code Search Results
All code searches were scoped to `src/**`.

* Query: `DEFAULT_SHARED_DIR_NAME|DEFAULT_SESSION_FILE_NAME|ALLOWED_STATUSES|PERSONAS`
  * Match: `src/copilot_multi/constants.py L1-L13`
* Query: `flock\(|LOCK_EX|LOCK_UN`
  * Match: `src/copilot_multi/session_store.py L46-L63`
* Query: `JSONDecodeError`
  * ✅ No matches in `src/**` → implies no explicit JSON corruption recovery.
* Query: `pane_id|split-window|pane-border-status|pane-border-format`
  * ✅ No `pane_id` capture patterns in current `src/copilot_multi/tmux.py` → pane addressing is index-based (`L40-L62`).

### External Research (Evidence Log)
Access date (all sources): **2026-01-15**

* `fetch_webpage`: `https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli`
  * ✅ Standalone Copilot CLI uses `copilot` and supports prompt mode: “Interactive mode: Start an interactive session by using the `copilot` command.” and “You do this by using the `-p` or `--prompt` command-line option.”
* `fetch_webpage`: `https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli`
  * ✅ Install methods: “You can install Copilot CLI using WinGet (Windows), Homebrew (macOS and Linux), npm (all platforms), or an install script (macOS and Linux).”
  * ✅ npm requirement: “Installing with npm (all platforms, requires Node.js 22+)”.
  * ✅ Auth: “On first launch… you’ll be prompted to use the `/login` slash command.”
  * ✅ PAT support: “fine-grained personal access token with the "Copilot Requests" permission enabled” via `GH_TOKEN` or `GITHUB_TOKEN`.
* `fetch_webpage`: `https://github.com/github/gh-copilot`
  * ✅ Archive status: “This repository was archived by the owner on Oct 30, 2025. It is now read-only.”
* `fetch_webpage`: `https://github.com/github/gh-copilot/blob/main/README.md`
  * ✅ Deprecation note: “GitHub Copilot in the CLI has been deprecated on October 25, 2025 in favor of GitHub Copilot CLI…”
* `run_in_terminal` (local environment probe)
  * ✅ In this devcontainer, `tmux` is installable after updating apt indexes (`sudo apt-get update` then `apt-cache policy tmux` shows a candidate).

### Project Conventions
* Standards referenced: `.agent/instructions/bash/bash.instructions.md`, `.agent/instructions/prompt.instructions.md`, `.agent/standards/research-feature-template.md`
* Instructions followed: `.github/copilot-instructions.md`, `AGENTS.md`, `.agent/commands/sdd/sdd.2-research-feature.prompt.md`
* ✅ Repo conventions (from `AGENTS.md`):
  * Python source belongs under `src/`.
  * Preferred workflow uses `uv` (`uv sync`, `uv run ...`).
  * No test framework configured; if adding tests later, prefer `pytest` under `tests/`.

## Key Discoveries

### Project Structure
✅ MVP already exists under `src/copilot_multi/` and is wired as a console script.

✅ Shared state and shared folder conventions already match the spec direction:
* `.copilot-multi/` (from `DEFAULT_SHARED_DIR_NAME` in `src/copilot_multi/constants.py L10-L13`)
* `.copilot-multi/session.json` (from `DEFAULT_SESSION_FILE_NAME` in `src/copilot_multi/constants.py L10-L13`)

### Implementation Patterns
✅ Locking uses `fcntl.flock(LOCK_EX)` which is appropriate for Linux-only coordination (`src/copilot_multi/session_store.py L46-L53`).

⚠️ Session writes are currently “truncate + rewrite same file” (`src/copilot_multi/session_store.py L22-L30`), which is not an atomic replace; partial writes can corrupt JSON if the process dies mid-write.

⚠️ tmux pane addressing is currently index-based (`src/copilot_multi/tmux.py L40-L62`) and persona-to-pane mapping is hard-coded to indexes (`src/copilot_multi/cli.py L127-L150`). This can be made more deterministic by capturing pane IDs.

✅ tmux availability is already fail-fast (`src/copilot_multi/tmux.py L9-L27`).

⚠️ No JSON corruption recovery exists today (`src/copilot_multi/session_store.py L14-L21`; `JSONDecodeError` search shows no handlers).

### Complete Examples

✅ Deterministic tmux 2x2 pane IDs (recommended pattern)
```bash
TMUX= tmux new-session -d -s copilot-multi -c "$PWD"

p0=$(tmux display-message -p -t copilot-multi:0.0 "#{pane_id}")
p1=$(tmux split-window -h -P -F "#{pane_id}" -t "$p0")
p2=$(tmux split-window -v -P -F "#{pane_id}" -t "$p0")
p3=$(tmux split-window -v -P -F "#{pane_id}" -t "$p1")

tmux select-layout -t copilot-multi:0 tiled
tmux set-option -t copilot-multi -g pane-border-status top
tmux set-option -t copilot-multi -g pane-border-format "#{pane_title}"
tmux select-pane -t "$p0" -T "Project Manager"
tmux select-pane -t "$p1" -T "Implementation Engineer"
tmux select-pane -t "$p2" -T "Code Review Engineer"
tmux select-pane -t "$p3" -T "Technical Writer"
```

✅ Example: status handoff loop
```bash
copilot-multi set-status pm working --message "Defining scope"
copilot-multi wait impl --status done --timeout 3600
copilot-multi set-status review working --message "Reviewing implementation"
copilot-multi wait review --status done
copilot-multi set-status docs working --message "Updating README"
copilot-multi wait docs --status done
```

### API and Schema Documentation

✅ Session state schema (current in code)
* File: `.copilot-multi/session.json`
* Defined by: `_init_session_state()` in `src/copilot_multi/cli.py L82-L97`
* Top-level keys: `version`, `sessionName`, `repoRoot`, `createdAt`, `personas`
* `personas.<id>` keys: `displayName`, `status`, `updatedAt`, `message`
* Allowed statuses: `idle`, `working`, `waiting`, `done`, `blocked` from `src/copilot_multi/constants.py L8`

✅ Locking and storage semantics (current)
* Lock acquisition: `src/copilot_multi/session_store.py L46-L53` (`fcntl.flock(LOCK_EX)`)
* Read: `src/copilot_multi/session_store.py L14-L21` (`json.loads`, no `JSONDecodeError` recovery)
* Write: `src/copilot_multi/session_store.py L22-L30` (truncate + rewrite, `fsync`)

### Configuration Examples

MVP uses conventions (no config file). Files created in `.copilot-multi/`:
```text
.copilot-multi/
  WORK_CONTEXT.md
  DECISIONS.md
  HANDOFF.md
  session.json
```

## Technical Scenarios

### 1. tmux Launcher (Linux-only MVP)
Deterministic pane addressing is essential so the wrapper can reliably label panes, send bootstrap commands, and support future automation.

**Requirements:**
* Create one tmux session, detached
* Split into a 2x2 layout deterministically
* Set persona titles and make them visible in pane borders
* Send persona bootstrap commands (e.g., `cd`, print context file pointers)

**Preferred Approach:**
Capture and persist tmux `pane_id` values at creation time (`split-window -P -F "#{pane_id}"`) and then target future commands by pane_id (not pane index).

```text
src/copilot_multi/tmux.py  # update: capture pane IDs; set border title options
src/copilot_multi/cli.py   # update: map personas to pane_ids instead of fixed indexes
```

**Implementation Details:**
* Today, pane creation and targeting are index-based (`src/copilot_multi/tmux.py L40-L62`) and personas map to fixed indices (`src/copilot_multi/cli.py L127-L150`).
* Recommended change: capture pane IDs while splitting and store a `paneId` per persona in session state (`session.json`).
* Make titles visible by setting `pane-border-status` and `pane-border-format` once per session.
* Keep the existing fail-fast tmux availability check (`src/copilot_multi/tmux.py L9-L27`) and improve the error message to include the apt-based install path for Debian-like containers.

#### Considered Alternatives (Removed After Selection)
* Index-based panes (`session:0.0` .. `0.3`) are simpler but can become brittle when layouts are modified or when additional panes/windows are introduced.

### 2. Session State Durability (Locking + Corruption Recovery)
File locking is already implemented, but two durability gaps remain.

**Requirements:**
* Concurrent access must be safe on a single machine (Linux)
* Writes must be durable and not corrupt JSON on crash
* Corrupt state must not crash the CLI; recovery should preserve the corrupt artifact for debugging
* Schema evolution must be possible (versioned)

**Preferred Approach:**
Keep `fcntl.flock` locking, but:
* Implement **atomic replace** writes (write temp file + `os.replace`) rather than truncating in-place.
* Add explicit corruption recovery for JSON decode errors.

```text
src/copilot_multi/session_store.py  # update: atomic replace + JSONDecodeError recovery
src/copilot_multi/cli.py            # update: stricter schema validation / migration hooks
```

**Implementation Details:**
* Locking is already exclusive and appropriate: `src/copilot_multi/session_store.py L46-L53`.
* Read is currently `json.loads()` with no `JSONDecodeError` recovery: `src/copilot_multi/session_store.py L14-L21`.
* Write is currently truncate + rewrite the same file descriptor: `src/copilot_multi/session_store.py L22-L30`.
* Recommended corruption recovery behavior:
  * On `JSONDecodeError`, rename `session.json` to `session.json.corrupt-<timestamp>` and reinitialize.
  * Validate required top-level keys and persona keys; reinitialize missing required fields.

#### Considered Alternatives (Removed After Selection)
* Using a database (SQLite) adds complexity and is unnecessary for single-file state in an MVP.

### 3. Copilot CLI Integration Target (Exclude AWS Copilot)
There are multiple similarly named “copilot” CLIs; scope must be explicit.

**Requirements:**
* The wrapper must target GitHub Copilot CLI (standalone `copilot`) rather than AWS Copilot.
* Avoid integrating with deprecated tooling by default.

**Preferred Approach:**
Target the standalone GitHub Copilot CLI (`copilot`, public preview) as the backend and treat this project as orchestration + coordination.

```text
docs/  # update docs: prerequisites and clear naming (“GitHub Copilot CLI”)
src/   # wrapper shells out to `copilot` (no re-implementation of copilot flags)
```

**Implementation Details:**
* GitHub docs state interactive mode starts with `copilot` and programmatic mode uses `-p/--prompt` (see Evidence Log).
* Legacy `gh-copilot` is archived and explicitly deprecated in its README (see Evidence Log).
* For MVP: do not attempt “multi-persona prompt injection”; rely on shared `.copilot-multi/*.md` context plus explicit `copilot-multi set-status` handoffs.

#### Considered Alternatives (Removed After Selection)
* Supporting `gh copilot` as a second backend is possible, but increases scope and targets deprecated tooling. Keep it out of MVP unless a concrete user requirement emerges.

## Actionable Next Steps
1) ✅ Update tmux launcher to capture `pane_id` and display pane titles (reliability + UX)
2) ⚠️ Update session store to use atomic replace + JSON corruption recovery (durability)
3) ✅ Ensure docs name the correct backend (`copilot`) and explicitly exclude AWS Copilot
4) ✅ Decide devcontainer strategy for `tmux` (install during build vs document `apt-get update && apt-get install tmux`)
