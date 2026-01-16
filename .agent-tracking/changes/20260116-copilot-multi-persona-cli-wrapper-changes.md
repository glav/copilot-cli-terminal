<!-- markdownlint-disable-file -->
# Release Changes: Copilot Multi-Persona CLI Wrapper Hardening (Linux-only, tmux)

Related Plan: .agent-tracking/plans/20260116-copilot-multi-persona-cli-wrapper-plan.instructions.md
Implementation Date: 2026-01-16

## Summary

Hardened the `copilot-multi` Linux-only tmux orchestrator with deterministic pane targeting, durable session state storage, and clearer onboarding/docs for GitHub Copilot CLI.

## Changes

### Added

### Modified

* src/copilot_multi/tmux.py - Capture tmux pane IDs during 2x2 creation and return them for stable targeting.
* src/copilot_multi/cli.py - Use tmux pane IDs for all pane operations and persist per-persona pane IDs into session state.
* src/copilot_multi/tmux.py - Enable pane border titles and set pane title format for consistent persona labels.
* src/copilot_multi/tmux.py - Improve tmux availability errors with actionable install guidance.
* src/copilot_multi/cli.py - Remove redundant tmux PATH check and rely on tmux module errors.
* README.md - Add Debian/Ubuntu install instructions for tmux.
* src/copilot_multi/cli.py - Include per-persona paneId in the initialized session schema and repair it on status updates.
* src/copilot_multi/session_store.py - Write session.json atomically via temp file + fsync + os.replace under a stable lock file.
* src/copilot_multi/session_store.py - Recover from corrupt JSON by preserving a `.corrupt-*` artifact and reinitializing state.
* src/copilot_multi/cli.py - Make `status` command resilient to missing/corrupt session.json by recreating valid state.
* src/copilot_multi/cli.py - Add explicit session schema normalization and versioned migration to repair/migrate older session files.
* README.md - Clarify backend is GitHub Copilot CLI (`copilot`), explicitly exclude AWS Copilot, and document install/auth expectations.
* docs/feature-specs/copilot-cli-multi-persona-wrapper.md - Align spec language to GitHub Copilot CLI and exclude AWS Copilot and deprecated gh-copilot backends.
* README.md - Fix `wait` example to match CLI (positional persona argument).
* src/copilot_multi/cli.py - Add a `copilot` binary preflight check for clearer onboarding failures.
* src/copilot_multi/cli.py - Make `start` attach by default (and attach if the session already exists); add `--detach` for background start.
* src/copilot_multi/cli.py - Focus the Project Manager pane before attaching so PM is active by default.
* src/copilot_multi/tmux.py - Add `focus_pane()` helper used to select the initial active pane.
* README.md - Update `start` example to reflect default attach and document `--detach`.
* src/copilot_multi/cli.py - Start a shared local broker and run a per-pane REPL so typed input routes through Copilot (except `copilot-multi` commands).
* src/copilot_multi/broker.py - New: shared broker process that serializes prompts and uses shared Copilot CLI state.
* src/copilot_multi/pane_repl.py - New: per-pane REPL that forwards input to broker and prints output in the originating pane.
* src/copilot_multi/cli.py - Make `stop` idempotent (no error if tmux session is not running).

### Removed

## Release Summary

Total Files Affected: 5

Files Modified (5)

* src/copilot_multi/tmux.py - Deterministic pane IDs, visible titles, and improved tmux errors.
* src/copilot_multi/cli.py - Persist pane IDs, normalize/migrate session schema, and preflight `copilot` availability.
* src/copilot_multi/session_store.py - Stable locking, atomic writes, and corruption recovery.
* README.md - Clarify GitHub Copilot CLI backend, add install/auth guidance, fix CLI examples.
* docs/feature-specs/copilot-cli-multi-persona-wrapper.md - Align spec with GitHub Copilot CLI and explicitly exclude AWS Copilot.

Dependencies & Infrastructure

* New Dependencies: none
* Updated Dependencies: none
