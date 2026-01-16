<!-- markdownlint-disable-file -->
<!-- markdown-table-prettify-ignore-start -->
# Copilot CLI Multi-Persona Terminal Wrapper - Feature Specification Document
Version 0.1 | Status Draft | Owner glav | Team TBD | Target MVP | Lifecycle Discovery

## Progress Tracker
| Phase | Done | Gaps | Updated |
|-------|------|------|---------|
| Context | Done | None | 2026-01-15 |
| Problem & Users | Partial | Confirm primary user workflow (typical session sequence + handoffs) | 2026-01-15 |
| Scope | Partial | Define MVP vs v1.0 boundaries | 2026-01-15 |
| Requirements | Partial | Confirm session file locations + command UX details | 2026-01-15 |
| Metrics & Risks | Partial | Confirm success metrics and risks tolerance | 2026-01-15 |
| Operationalization | Not started | Packaging/install story; support boundaries | 2026-01-15 |
| Finalization | Not started | Review/approval + sign-off | 2026-01-15 |
Unresolved Critical Questions: 0 | TBDs: 8

## 1. Executive Summary
### Context
We want a small CLI tool that wraps the existing `copilot` CLI command and launches a coordinated, multi-persona workflow.

The tool should open 4 visible terminal panes (via `tmux`) in a shared working directory. Each pane represents a dedicated persona:
1) Project Manager
2) Implementation Engineer
3) Code Review Engineer
4) Technical Writer / Documentor

Each persona can coordinate with the others by checking whether another persona is currently working, has finished, or is blocked, so the next persona can proceed.

### Core Opportunity
Make multi-role “agentic” workflows practical from the terminal by:
- Creating predictable role separation (PM vs implementer vs reviewer vs writer)
- Keeping a shared, file-based context to avoid prompt drift
- Enabling lightweight handoffs via explicit status signaling

### Goals
| Goal ID | Statement | Type | Baseline | Target | Timeframe | Priority |
|---------|-----------|------|----------|--------|-----------|----------|
| G-001 | Launch 4 persona terminals from one command in a shared workspace | User value | Manual setup/splitting terminals | ≤ 5 seconds, one command | MVP | P0 |
| G-002 | Provide reliable “who is working / done / blocked” coordination between personas | Quality | No coordination | Status visible + queryable | MVP | P0 |
| G-003 | Ensure personas share consistent context through common working files | Quality | Ad-hoc copy/paste | Standardized shared files | MVP | P0 |
| G-004 | Keep the wrapper lightweight and safe (no secrets persistence) | Risk | Unknown | No sensitive logging; clear boundaries | MVP | P0 |

### Objectives (Optional)
| Objective | Key Result | Priority | Owner |
|-----------|------------|----------|-------|
| Improve throughput | End-to-end task cycle time reduced by 30% vs manual | P1 | TBD |

## 2. Problem Definition
### Current Situation
Users manually open multiple terminals and attempt to run Copilot CLI in different “modes” (PM, implementer, reviewer, writer). There’s no consistent way to share context or coordinate handoffs.

### Problem Statement
A multi-persona workflow is hard to operate reliably from the terminal because terminal sessions are not coordinated and shared context is not standardized.

### Root Causes
* No standardized “shared context” files that each persona reads/writes.
* No shared state signaling for handoffs (working/done/waiting).

### Impact of Inaction
Work becomes fragmented (duplicate work, conflicting decisions), and the overhead of orchestrating personas outweighs the benefits.

## 3. Users & Personas
| Persona | Goals | Pain Points | Impact |
|---------|-------|------------|--------|
| Project Manager | Drive scope, sequencing, and acceptance criteria | Hard to know when engineers are ready; poor visibility | Delays, scope creep |
| Implementation Engineer | Implement requested changes quickly | Missing requirements, unclear priorities | Rework, churn |
| Code Review Engineer | Review for correctness and maintainability | Context scattered; unclear “definition of done” | Missed issues or slow review |
| Technical Writer / Documentor | Capture decisions and usage docs | Hard to track changes and rationale | Docs lag behind code |

### Journeys (Optional)
A typical journey:
- PM pane creates/updates a shared plan + acceptance criteria.
- Implementation pane works on code and updates shared context.
- Review pane validates changes and updates review checklist.
- Writer pane produces docs/README updates.

## 4. Scope
### In Scope
* Single command that launches a 4-persona session.
* 4 visible terminal panes (2x2 `tmux` layout), all in the same working directory.
* A shared “session state” file at `.copilot-multi/session.json` that personas can read/write to coordinate.
* A shared set of working files (e.g., plan, decisions, handoff notes).
* Session lifecycle commands: start, status, stop, resume (at least start/status/stop for MVP).
* Underlying Copilot CLI command defaults to `copilot` (optionally configurable later).

### Out of Scope (justify if empty)
* Implementing or modifying the Copilot model/service itself.
* Building a VS Code extension (this is a terminal-first tool).
* Cross-machine collaboration (single-machine session only for MVP).
* Windows support (MVP is Linux-only).

### Assumptions
* The underlying Copilot CLI is already installed and authenticated on the machine.
* Users run this tool from a terminal in the target repo directory.

### Constraints
* Must not write secrets to disk.
* MVP requires Linux + `tmux` to create and manage 4 visible panes.

## 5. Product Overview
### Value Proposition
A predictable, repeatable way to run multi-persona Copilot CLI workflows from the terminal with coordination and shared context.

### Differentiators (Optional)
* File-based shared context that is repo-friendly and reviewable.
* Explicit persona handoffs via shared state.

### UX / UI (Conditional)
Terminal UI only.

Expected interaction:
- User runs `copilot-multi start`.
- Tool opens a 2x2 layout (4 panes or 4 windows), each labeled with persona.
- Each pane runs the persona wrapper command and can query/update session status.

UX Status: Proposed

## 6. Functional Requirements
| FR ID | Title | Description | Goals | Personas | Priority | Acceptance | Notes |
|-------|-------|------------|-------|----------|----------|-----------|-------|
| FR-001 | Start session | Provide `start` command to launch a new 4-persona session in current working directory | G-001 | All | P0 | Opens a `tmux` session with a 2x2 layout (4 panes) and initializes session state | MVP launcher: `tmux` |
| FR-002 | Persona labeling | Each terminal clearly indicates its persona | G-001 | All | P0 | Pane title/banner shows persona name | tmux pane titles or printed banner |
| FR-003 | Shared workspace | All personas operate in the same working directory and share files | G-003 | All | P0 | Changes made in one pane visible to others immediately | Standard OS filesystem |
| FR-004 | Shared working files scaffold | On `start`, create a standard set of shared files (if missing) | G-003 | All | P0 | Files created with templates; idempotent | Examples: `.copilot-multi/WORK_CONTEXT.md`, `.copilot-multi/DECISIONS.md`, `.copilot-multi/HANDOFF.md` |
| FR-005 | Session state file | Maintain a single session state file recording persona statuses | G-002 | All | P0 | `status` command shows each persona state reliably | JSON file + file lock |
| FR-006 | Persona status commands | Provide commands to set a persona state: `idle`, `working`, `waiting`, `done`, `blocked` | G-002 | All | P0 | Status updates are atomic and visible cross-pane | Use filesystem lock (e.g., `flock`) |
| FR-007 | Wait-on-persona | Provide a way for a persona to wait until another persona reaches a desired state | G-002 | All | P1 | `wait --persona pm --state done` blocks until satisfied | Polling or file watch |
| FR-008 | Copilot command passthrough | Persona wrapper runs `copilot` in each pane using shared context files | G-003 | All | P0 | Each pane can run `copilot` normally; shared context files provide consistent inputs | No persona prompt injection for MVP |
| FR-009 | Config file | Allow configuring defaults (launcher, underlying copilot command, file locations) | G-001 | PM | P1 | `copilot-multi config init` creates config; `start` reads it | Use repo-local config (TBD) |
| FR-010 | Resume session | Detect existing session state and resume/reopen panes | G-001, G-002 | All | P2 | `resume` reattaches or recreates panes with state preserved | Likely tmux session attach |
| FR-011 | Stop session | Cleanly stop/close a session | G-001 | All | P1 | `stop` closes panes (where possible) and marks session ended | Avoid deleting user files |
| FR-012 | Help + UX affordances | Provide `--help` and clear onboarding output | G-001 | All | P1 | Users can understand usage without reading docs | Include examples |

### Feature Hierarchy (Optional)
```plain
copilot-multi
  start
  status
  persona
    set-status
    wait
  stop
  config
    init
```

## 7. Non-Functional Requirements
| NFR ID | Category | Requirement | Metric/Target | Priority | Validation | Notes |
|--------|----------|------------|--------------|----------|-----------|-------|
| NFR-001 | Performance | Startup overhead should be small | Session launch ≤ 5s on typical dev machine | P0 | Manual timing | Depends on launcher |
| NFR-002 | Reliability | State updates must be race-safe | No corrupted JSON; atomic updates | P0 | Concurrency test | Use file locks |
| NFR-003 | Portability | Linux-only support for MVP | MVP: Linux only | P0 | Manual verification | Windows/macOS out of scope for MVP |
| NFR-004 | Security | Do not persist secrets | No tokens/keys written to disk | P0 | Code review | Ensure logs are scrubbed |
| NFR-005 | Usability | Commands are discoverable | `--help` covers common flows | P1 | UX review | Keep mental model simple |
| NFR-006 | Observability | Troubleshooting is possible | Debug logs behind a flag | P2 | Manual verification | Avoid leaking secrets |

## 8. Data & Analytics (Conditional)
### Inputs
- User config (if enabled)
- Session state file updates (persona statuses)

### Outputs / Events
- Session state JSON file
- Optional debug logs

### Instrumentation Plan
| Event | Trigger | Payload | Purpose | Owner |
|-------|---------|--------|---------|-------|
| session_started | start command | session id, launcher type | Diagnose start failures | TBD |
| status_changed | persona set-status | persona, old/new status | Debug handoff issues | TBD |

### Metrics & Success Criteria
| Metric | Type | Baseline | Target | Window | Source |
|--------|------|----------|--------|--------|--------|
| Session time-to-ready | Latency | N/A | ≤ 5s | Per start | Manual/Logs |
| Handoff latency | Process | N/A | ≤ 30s median | Per task | Manual |

## 9. Dependencies
| Dependency | Type | Criticality | Owner | Risk | Mitigation |
|-----------|------|------------|-------|------|-----------|
| `copilot` CLI | Runtime | Critical | User | Not installed / auth issues | Pre-flight check + clear error |
| `tmux` | Runtime | Critical | Tool | Not present in environment | Install guidance + actionable error message |
| Python runtime + packaging tooling | Build | High | Repo | Packaging friction | Use existing repo Python setup |

## 10. Risks & Mitigations
| Risk ID | Description | Severity | Likelihood | Mitigation | Owner | Status |
|---------|-------------|---------|-----------|-----------|-------|--------|
| R-001 | `tmux` is missing in some environments | Medium | Medium | Install guidance + clear preflight error | TBD | Open |
| R-002 | Personas drift without prompt injection | Medium | Medium | Use shared context files + conventions; add “persona responsibilities” docs | TBD | Open |
| R-003 | Race conditions corrupt session state | High | Medium | File locking + atomic writes | TBD | Open |
| R-004 | Users confuse shared files with generated files | Low | Medium | Put under a dedicated folder + docs | TBD | Open |

## 11. Privacy, Security & Compliance
### Data Classification
Local developer workspace data only.

### PII Handling
No intentional PII collection. Shared files may contain project text; treat as repo-local.

### Threat Considerations
- Avoid logging environment variables, tokens, or command histories.
- Avoid executing arbitrary commands beyond configured launcher and Copilot CLI.

### Regulatory / Compliance (Conditional)
| Regulation | Applicability | Action | Owner | Status |
|-----------|--------------|--------|-------|--------|
| N/A | N/A | N/A | N/A | N/A |

## 12. Operational Considerations
| Aspect | Requirement | Notes |
|--------|------------|-------|
| Deployment | Install as a Python CLI via `uv`/pip | Align with repo tooling |
| Rollback | Simple: uninstall package or revert files | Avoid migrations |
| Monitoring | Optional debug logs | Local only |
| Alerting | None | N/A |
| Support | Best-effort; document supported environments | Define MVP support |
| Capacity Planning | Minimal | Local tool |

## 13. Rollout & Launch Plan
### Phases / Milestones
| Phase | Date | Gate Criteria | Owner |
|-------|------|--------------|-------|
| MVP design | 2026-01 | Spec approved; launcher decision made | glav |
| MVP implementation | 2026-01 | `start/status/set-status` working | TBD |
| MVP docs | 2026-01 | README usage + troubleshooting | TBD |

### Feature Flags (Conditional)
| Flag | Purpose | Default | Sunset Criteria |
|------|---------|--------|----------------|
| launcher.tmux | Use tmux for panes | on | Keep; core mode |
| launcher.external_terminal | Spawn terminal emulator windows | off | Promote if stable |

### Communication Plan (Optional)
Add a README section and a short demo recording (optional).

## 14. Open Questions
| Q ID | Question | Owner | Deadline | Status |
|------|----------|-------|---------|--------|
| Q-001 | Which underlying Copilot CLI should be wrapped? | User | MVP | Answered: `copilot` |
| Q-002 | Is `tmux` an acceptable default for “4 terminal windows” (4 panes)? | User | MVP | Answered: yes |
| Q-003 | Must panes be separate OS windows (not panes) in any environment? | User | MVP | Answered: no |
| Q-004 | What is the minimum set of shared working files and their location? | User | MVP | Answered: use `.copilot-multi/` + MVP files |
| Q-005 | What exact handoff semantics are required? | User | MVP | Answered: statuses `idle/working/waiting/done/blocked` are sufficient for MVP |

## 15. Changelog
| Version | Date | Author | Summary | Type |
|---------|------|-------|---------|------|
| 0.1 | 2026-01-15 | GitHub Copilot (GPT-5.2) | Initial draft from user request | Draft |

## 16. References & Provenance
| Ref ID | Type | Source | Summary | Conflict Resolution |
|--------|------|--------|---------|--------------------|
| REF-001 | Repo doc | AGENTS.md | Repo expectations: Python src/, uv workflow | N/A |
| REF-002 | Repo doc | README.md | Project overview + runtime entrypoint | N/A |
| REF-003 | Prompt | .agent/commands/sdd/sdd.1-create-feature-spec.prompt.md | Spec-building process constraints | N/A |
| REF-004 | Template | .agent/standards/feature-spec-template.md | Required spec structure | N/A |

### Citation Usage
References are listed for provenance. Future iterations should cite external Copilot CLI docs once the exact CLI variant is chosen.

## 17. Appendices (Optional)
### Glossary
| Term | Definition |
|------|-----------|
| Persona | A dedicated role-specific terminal session with its own responsibilities |
| Session state | Shared file describing persona statuses and session metadata |
| Launcher | The mechanism used to create 4 visible terminals/panes |

### Additional Notes
MVP assumes `tmux` panes (not OS windows) and uses shared files (no persona prompt injection).

Generated 2026-01-15 by GitHub Copilot (GPT-5.2) (mode: agent)
<!-- markdown-table-prettify-ignore-end -->
