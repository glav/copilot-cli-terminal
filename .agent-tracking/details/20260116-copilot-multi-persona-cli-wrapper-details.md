<!-- markdownlint-disable-file -->
# Task Details: Copilot Multi-Persona CLI Wrapper Hardening (Linux-only, tmux)

## Research Reference

Source research: .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md

## Phase 1: tmux Launcher Determinism + Pane UX

### Task 1.1: Make tmux pane targeting deterministic via pane IDs

Update the tmux launcher to capture `pane_id` values at pane creation time (via `split-window -P -F "#{pane_id}"`) and use those IDs for all subsequent operations (titles, send-keys, future automation), rather than relying on numeric pane indexes.

- Files:
  - src/copilot_multi/tmux.py — capture pane IDs during 2x2 creation; return a stable mapping
  - src/copilot_multi/cli.py — persist pane IDs into session state and use them for persona targeting
  - src/copilot_multi/session_store.py — ensure updated schema is written safely (Phase 2)
- Success:
  - Pane creation yields 4 stable pane IDs and each persona maps to exactly one ID
  - All tmux commands target panes by `pane_id` (not `session:0.X`)
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 172-194) — preferred approach and implementation details for pane IDs
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 117-133) — example command sequence for deterministic 2x2 with titles
- Dependencies:
  - tmux available on PATH

### Task 1.2: Ensure persona titles are visible in the tmux UI

Configure the tmux session so pane titles are displayed consistently (pane border status + format) and set a clear title for each persona pane.

- Files:
  - src/copilot_multi/tmux.py — set `pane-border-status` and `pane-border-format`; set per-pane titles
- Success:
  - Pane borders display persona titles across the 2x2 layout
  - Titles are applied after layout selection so they persist for the session
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 117-133) — pane border settings and `select-pane -T` usage
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 53-56) — current title-setting behavior and current launcher implementation location
- Dependencies:
  - Task 1.1 completion

### Task 1.3: Improve tmux availability checks and error messaging

Keep the existing fail-fast `tmux -V` check, but make the error messaging actionable for Debian-like environments (especially devcontainers), including the observed “installable after apt index update” behavior.

- Files:
  - src/copilot_multi/tmux.py — improve error text and prerequisite guidance
  - README.md — document `tmux` prerequisite and installation instructions
- Success:
  - Missing tmux fails with a clear message that includes at least one valid install path
  - Docs include a short prerequisite section for tmux
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 33-36) — devcontainer tmux installation note
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 84-85) — local environment probe findings
- Dependencies:
  - Linux environment (this MVP is Linux-only)

### Task 1.4: Extend session schema to record per-persona pane IDs

Update the session schema to store a `paneId` field under each persona record so future operations can safely re-target panes.

- Files:
  - src/copilot_multi/cli.py — add `paneId` to the persona records created by session initialization
  - src/copilot_multi/constants.py — keep persona identifiers consistent
  - src/copilot_multi/session_store.py — ensure schema evolution is safe (Phase 2)
- Success:
  - Newly created sessions include `personas.<id>.paneId` for all personas
  - Session state remains backwards compatible (missing `paneId` can be repaired on demand)
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 145-158) — current schema shape and store semantics
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 189-193) — recommendation to store pane IDs per persona
- Dependencies:
  - Task 1.1 completion

## Phase 2: Session State Durability + Corruption Recovery

### Task 2.1: Make session writes atomic (temp file + os.replace)

Replace “truncate + rewrite same file” with an atomic replace strategy: write JSON to a temp file in the same directory, `fsync`, then `os.replace` to swap it into place while the file lock is held.

- Files:
  - src/copilot_multi/session_store.py — implement atomic replace strategy
- Success:
  - The write path never leaves a partially-written JSON file on crash
  - Locking remains exclusive and effective for concurrent CLI invocations
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 104-113) — current risks and missing recovery
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 198-223) — preferred approach and recommended behavior
- Dependencies:
  - Linux-only file locking via `fcntl` (already in use)

### Task 2.2: Add JSON corruption recovery that preserves the corrupt artifact

On `JSONDecodeError` (or detected invalid schema), preserve the corrupt file (rename to `session.json.corrupt-<timestamp>`), then reinitialize a valid session state.

- Files:
  - src/copilot_multi/session_store.py — handle JSON decode failure and preserve artifact
  - src/copilot_multi/cli.py — ensure callers get a valid in-memory state and schema repair hooks
- Success:
  - Corrupt session state never crashes CLI commands
  - Corrupt artifacts are retained for debugging
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 65-68) — current absence of JSONDecodeError handling
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 221-223) — recommended corruption recovery behavior
- Dependencies:
  - Task 2.1 completion

### Task 2.3: Formalize schema validation and migration

Introduce explicit schema validation (required top-level keys and required persona keys), and a versioned migration strategy so older session files can be repaired or migrated forward safely.

- Files:
  - src/copilot_multi/cli.py — validate and migrate session dicts; centralize schema definition
  - src/copilot_multi/session_store.py — call validation/migration when reading
- Success:
  - Missing keys are repaired deterministically
  - Schema version changes are handled without breaking older sessions
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 40-45) — current schema creation and “repair” behavior scope
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 201-215) — durability requirements and migration guidance
- Dependencies:
  - Phase 1 completion (schema extension)

## Phase 3: Copilot CLI Backend Clarity (Exclude AWS Copilot)

### Task 3.1: Align docs with GitHub Copilot CLI (standalone `copilot`)

Update docs to clearly specify the wrapper targets GitHub Copilot CLI (standalone `copilot`, public preview), and explicitly call out that AWS Copilot is not in scope.

- Files:
  - README.md — prerequisites and onboarding section
  - docs/feature-specs/copilot-cli-multi-persona-wrapper.md — ensure spec text matches implementation intent
- Success:
  - Documentation consistently refers to GitHub Copilot CLI and the `copilot` binary
  - Documentation includes an explicit “Not AWS Copilot” statement
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 70-83) — external evidence (docs + gh-copilot deprecation/archival)
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 228-246) — preferred approach and integration constraints
- Dependencies:
  - None

### Task 3.2: Document install/auth expectations for Copilot CLI

Document at least one recommended install path for Copilot CLI and the authentication expectations (including token environment variables), with a short “first run” note.

- Files:
  - README.md — installation and authentication section
- Success:
  - README lists install methods and minimum Node requirement if using npm
  - README mentions first-run login behavior and token env vars
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 73-79) — install/auth facts for Copilot CLI
- Dependencies:
  - None

## Phase 4: CLI UX + Onboarding Polish

### Task 4.1: Ensure CLI UX is consistent and self-documenting

Review `copilot-multi` help output and subcommand behavior for consistency (naming, defaults, and examples) and align README examples with actual CLI behavior.

- Files:
  - src/copilot_multi/cli.py — polish argparse help text and examples
  - README.md — update examples to match actual subcommands
- Success:
  - `copilot-multi --help` and README examples agree
  - Status-handoff workflow is documented as a happy path
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 40-45) — current CLI surface and commands
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 135-143) — example workflow loop
- Dependencies:
  - Phase 1 completion (pane mapping)

### Task 4.2: Add prerequisite checks for `copilot` and guide users to install

Optionally add a lightweight backend availability check for `copilot` (GitHub Copilot CLI) so onboarding failures are clearer.

- Files:
  - src/copilot_multi/cli.py — check for `copilot` binary availability (or document-only if preferred)
  - README.md — ensure troubleshooting explains what’s missing
- Success:
  - Missing `copilot` produces a clear next step (install/auth)
  - No accidental coupling to deprecated `gh-copilot` tooling
- Research references:
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 70-83) — correct backend and deprecation context
  - .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md (Lines 231-246) — requirements and MVP stance
- Dependencies:
  - Phase 3 completion (docs clarity)

## Dependencies

- Linux environment (MVP scope)
- tmux installed and runnable
- GitHub Copilot CLI installed (`copilot`)
- Python runtime + project dependencies installed (recommended: `uv sync`)

## Success Criteria

- tmux launcher reliably creates a deterministic 2x2 layout using pane IDs
- Session state storage is durable (atomic writes) and resilient (corruption recovery)
- Documentation clearly targets GitHub Copilot CLI and excludes AWS Copilot
- CLI UX and docs are aligned with a clear onboarding path
