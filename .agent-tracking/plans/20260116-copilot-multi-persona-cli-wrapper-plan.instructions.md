---
applyTo: '.agent-tracking/changes/20260116-copilot-multi-persona-cli-wrapper-changes.md'
---
<!-- markdownlint-disable-file -->
# Task Checklist: Copilot Multi-Persona CLI Wrapper Hardening (Linux-only, tmux)

## Overview

Create an implementation-ready plan to harden the existing `copilot-multi` MVP by making tmux pane addressing deterministic, improving session state durability/recovery, and aligning docs/UX with GitHub Copilot CLI.

Follow project guidance in AGENTS.md, .github/copilot-instructions.md, and relevant standards under .agent/instructions/.

## Objectives

- Replace index-based tmux targeting with deterministic `pane_id` targeting and visible persona titles.
- Make `.copilot-multi/session.json` writes atomic and resilient to corruption.
- Ensure documentation explicitly targets GitHub Copilot CLI (`copilot`) and excludes AWS Copilot.
- Improve CLI UX and onboarding so prerequisites and workflows are obvious.

## Research Summary

### Validated Research
- .agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md — repo snapshot + selected approaches, including tmux pane-id capture and session-store atomic writes/corruption recovery.

### Project Files (from research)
- src/copilot_multi/tmux.py — tmux session creation + pane management
- src/copilot_multi/session_store.py — locking + JSON read/write for session state
- src/copilot_multi/cli.py — CLI command surface + session schema initialization
- README.md and docs/feature-specs/copilot-cli-multi-persona-wrapper.md — user onboarding and feature spec

### External References (from research)
- https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli — confirms standalone `copilot` CLI usage
- https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli — install + auth expectations
- https://github.com/github/gh-copilot — archival/deprecation context

## Implementation Checklist

### [x] Phase 1: tmux Launcher Determinism + Pane UX

- [x] Task 1.1: Make tmux pane targeting deterministic via pane IDs
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 10-25)


- [x] Task 1.2: Ensure persona titles are visible in the tmux UI
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 27-40)

- [x] Task 1.3: Improve tmux availability checks and error messaging
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 42-56)

- [x] Task 1.4: Extend session schema to record per-persona pane IDs
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 58-73)

### [x] Phase 2: Session State Durability + Corruption Recovery

- [x] Task 2.1: Make session writes atomic (temp file + os.replace)
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 77-90)

- [x] Task 2.2: Add JSON corruption recovery that preserves the corrupt artifact
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 92-106)

- [x] Task 2.3: Formalize schema validation and migration
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 108-122)

### [x] Phase 3: Copilot CLI Backend Clarity (Exclude AWS Copilot)

- [x] Task 3.1: Align docs with GitHub Copilot CLI (standalone `copilot`)
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 126-140)

- [x] Task 3.2: Document install/auth expectations for Copilot CLI
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 142-154)

### [x] Phase 4: CLI UX + Onboarding Polish

- [x] Task 4.1: Ensure CLI UX is consistent and self-documenting
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 158-172)

- [x] Task 4.2: Add prerequisite checks for `copilot` and guide users to install
  - Details: .agent-tracking/details/20260116-copilot-multi-persona-cli-wrapper-details.md (Lines 174-188)

## Dependencies

- Linux environment (MVP scope)
- tmux installed and runnable
- GitHub Copilot CLI installed (`copilot`)
- Python runtime + dependencies (recommended: `uv sync`)

## Success Criteria

- tmux launcher creates a deterministic 2x2 layout and targets panes by `pane_id`.
- Session writes are atomic and corruption does not crash CLI commands.
- Docs consistently reference GitHub Copilot CLI and explicitly exclude AWS Copilot.
- CLI help text and README examples match and provide a clear onboarding path.
