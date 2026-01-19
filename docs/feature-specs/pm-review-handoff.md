<!-- markdownlint-disable-file -->
# Copilot Multi: Multi-Persona Handoff & Revision Spec
Version 0.1 | Status Draft | Owner TBD | Team TBD | Target TBD

## 1. Executive Summary
### Context
Prompts often need input from other personas and a revised plan based on feedback. Today, users must manually copy/paste or wait for another persona and then edit the plan. This spec proposes a built-in workflow that lets any persona request other persona responses and then explicitly apply suggestions.

### Goals
- Allow any persona to request another persona response via an explicit command or placeholder.
- Support a follow-up prompt that applies persona feedback to the original output.
- Keep the flow simple and explicit (no hidden automation).

## 2. Scope
### In Scope
- A persona-facing workflow to request another persona and then revise the original output.
- A clear syntax for referencing a persona response (e.g., `{{agent:review}}`).
- A minimal command path that triggers any persona and stores its output for reuse.
- Sequential multi-persona requests within a single prompt (no parallel fan-out).
- Explicit opt-in to apply review suggestions (no automatic edits without PM intent).

### Out of Scope
- Automatic multi-step delegation to cloud agents outside the local broker flow.
- Changes to Copilot CLI or its slash commands.
- AI-driven auto-merge of conflicting suggestions.

## 3. Requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| R-001 | Provide a way for any persona to request another persona within a single flow. | P0 |
| R-002 | Provide a clear placeholder to inject a persona response into a follow-up. | P0 |
| R-003 | Support a “revise plan using persona feedback” prompt pattern. | P0 |
| R-004 | Preserve existing `{{ctx:<persona>}}` placeholder behavior. | P1 |
| R-005 | Provide a minimal implementation path (command + wait) that works with the current broker. | P0 |
| R-006 | Define how the command blocks (polling session state or response files). | P0 |

## 4. UX / Prompt Examples
### Example Flow
1) Persona creates an initial plan:
```
Create a plan to implement a tic tac toe game.
```

2) Persona requests input from another persona (command path):
```
copilot-multi ask review --prompt "Review the plan and suggest improvements."
```

3) Persona requests input from another persona (placeholder path):
```
Review this plan and suggest improvements. {{agent:review}}
```

4) Persona revises based on feedback:
```
Update the plan based on the review feedback: {{ctx:review}}
```

## 5. Implementation Notes (Non-binding)
- Provide a `copilot-multi ask <persona> --prompt ...` command that routes to the target persona, waits for completion, and writes the response to the shared `responses/` store.
- Implement blocking via polling the session file and/or checking `responses/<persona>.last.txt` for updates, with timeout/backoff.
- Extend placeholder handling to support `{{agent:<persona>}}` as a special “request persona” token, implemented as a wrapper for the command path.
- Store persona responses via existing `responses/` persistence for reuse in `{{ctx:<persona>}}`.
- Keep all changes local to the broker/pane REPL; no reliance on Copilot CLI slash commands.

## 6. Risks / Considerations
- Users may expect automatic execution; ensure messaging clarifies explicit commands for review + revision.
- Placeholder parsing must remain backward compatible with `{{ctx:...}}` / `{{last:...}}`.
- Multiple persona requests in one prompt execute sequentially, which can be slower; document this explicitly.
