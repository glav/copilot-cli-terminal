<!-- markdownlint-disable-file -->
# Copilot Multi: Multi-Persona Ask/Revise Implementation Plan
Version 0.1 | Status Draft | Owner TBD | Team TBD

## Phase 1 — Design & UX
- [x] Define `copilot-multi ask <persona> --prompt ...` command UX (flags, timeout default, backoff).
- [x] Define `{{agent:<persona>}}` placeholder parsing rules (sequential only).
- [x] Specify waiting mechanics: poll `responses/<persona>.last.txt` mtime and/or `session.json` status with timeout/backoff.

## Phase 2 — Core Implementation
- [x] Add CLI command `ask` in `copilot_multi/cli.py` with persona validation.
- [x] Route the prompt to the target persona via the broker path used by panes.
- [x] Wait for completion by polling response file mtime until changed or timeout.
- [x] Persist persona responses in `responses/<persona>.last.txt` (reuse existing store).
- [x] Mirror persona activity into the target pane (e.g., tmux `send-keys` or broker notify) so it appears as if the prompt was typed there.

## Phase 3 — Placeholder Wiring
- [x] Extend placeholder expansion to translate `{{agent:<persona>}}` into `ask` calls.
- [x] Implement sequential multi-persona requests by looping over placeholders in prompt order.
- [x] Ensure `{{ctx:<persona>}}` remains backward compatible.
- [x] Ensure multi-persona invocations update each target pane with visible activity (one per persona, via tmux `send-keys` or broker notify).
- [x] Update parsing so each `{{agent:<persona>}}` consumes the text *after* the marker up to the next marker/end, expanding `{{ctx:<persona>}}` before dispatch.
- [x] Add example to plan: `Tell me a dad joke about unicorns {{agent:review}} Review the joke from {{ctx:pm}}` where PM keeps the pre-marker text and review receives the post-marker text with ctx expanded.

## Phase 4 — Tests
- [ ] Unit tests for placeholder parsing and persona targeting.
- [ ] Unit tests for wait/polling behavior (timeouts, missing responses).
- [ ] CLI tests for `ask` command argument handling.

## Phase 5 — Docs
- [x] Update README with `ask` command and `{{agent:<persona>}}` usage.
- [x] Add notes on sequential behavior and timeouts/backoff defaults.
