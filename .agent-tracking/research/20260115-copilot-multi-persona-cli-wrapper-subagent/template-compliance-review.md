<!-- markdownlint-disable-file -->
# Template & sdd.2 Compliance Review — 20260115 Copilot Multi-Persona CLI Wrapper Research

Target doc reviewed: `.agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-research.md`

Template baseline: `.agent/standards/research-feature-template.md`

Instructions baseline: `.agent/commands/sdd/sdd.2-research-feature.prompt.md`

## Checklist Results (Pass/Needs work)

- `<!-- markdownlint-disable-file -->` present: **PASS**
- Uses and fills the template sections (no `{{placeholders}}` left): **NEEDS WORK**
  - No placeholders remain, but several *mandatory template sections* are missing or not in template form.
- Evidence log with concrete URLs and access date: **NEEDS WORK**
  - The doc contains some URLs and a global “accessed 2026-01-15” note, but the **Evidence Log is not self-contained** (it points to a subagent evidence file rather than including concrete evidence entries inline).
- One recommended approach per scenario (no lingering alternatives): **NEEDS WORK**
  - Scenario 3 leaves a live alternative: “Optionally support legacy `gh copilot` only if explicitly required.”
- References repo files with approximate line ranges: **PARTIAL PASS**
  - File Analysis includes approximate ranges, but other claims (e.g., schema/status enum) don’t cite specific file locations/ranges.
- Includes Potential Next Research items: **PASS**

## Key Gaps vs Template & sdd.2

### 1) Template section coverage is incomplete
Template expects the following sections to exist (even if some are “none found”):
- `### Code Search Results` (missing)
- `### External Research (Evidence Log)` in template format (present, but not in template format)
- `### Project Conventions` should include explicit “Standards referenced” and “Instructions followed” fields (present but not in template format)
- `### Complete Examples` and `### Configuration Examples` (not present as dedicated sections; examples exist only inside scenarios)

### 2) Evidence log is not self-contained in the main research doc
The main doc’s Evidence Log currently:
- References a subagent consolidation file: `.agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-subagent/evidence-extract-research.md`
- Includes a few key claims with URLs, but without consistent per-item access dates/quotes/context.

sdd.2 “Success Criteria” expects the **dated research file** to contain the evidence log with sources/links/context for each key finding.

### 3) “One recommended approach per scenario” not fully enforced
Scenario 3 includes a lingering alternative (“optionally support legacy `gh copilot`…”). Template/sdd.2 guidance is to select ONE approach and remove alternatives from the final doc.

### 4) Repo file references are incomplete for several assertions
Examples:
- “Allowed statuses: `idle`, `working`, `waiting`, `done`, `blocked`” should cite the defining source (likely `src/copilot_multi/constants.py` or wherever the enum/list lives) with approximate line ranges.
- The “session state schema (observed in code)” should cite the exact code region(s) that write/read those keys.

### 5) sdd.2 style requirements are not fully reflected
The sdd.2 instructions explicitly request “Use emojis to help drive specific ideas” for the research doc. The main research file is written in a clean technical style, but is **not following that specific styling instruction**.

(If you want to intentionally *not* follow the emoji styling for this repo, that exception should be documented explicitly in the research file’s conventions section.)

## Punchlist + Suggested Edits (Concrete)

### A) Bring the main research doc into template shape
1) Add a `### Code Search Results` section under “Research Executed”.
   - Suggested content (keep it honest/minimal): include 2–4 searches you actually ran in this repo (e.g., `tmux`, `session.json`, `flock`, `pane-border-status`) and list the discovered files with approximate ranges.

2) Expand `### Project Conventions` into the template’s explicit fields:
   - `Standards referenced: ...`
   - `Instructions followed: ...`

3) Add dedicated sections (even if brief) for:
   - `### Complete Examples` (move or duplicate the best end-to-end tmux launcher snippet here)
   - `### Configuration Examples` (e.g., example `.copilot-multi/` tree, any env var expectations like `GH_TOKEN` vs `/login` guidance)

### B) Make the evidence log self-contained (keep the subagent file as optional)
4) Replace the current Evidence Log content with an inline table or bullet list that includes:
   - Concrete URL
   - Access date per item (or a clearly stated global access date *plus* per-item URLs)
   - One supporting quote/snippet or concise paraphrase

   Suggested starting point: copy the “Evidence table” rows from `.agent-tracking/research/20260115-copilot-multi-persona-cli-wrapper-subagent/evidence-extract-research.md` into the main doc and trim to only the findings used by the recommended approach.

### C) Enforce “one recommended approach per scenario”
5) Update Scenario 3 to a single explicit decision.
   - Either:
     - “Target standalone `copilot` only; `gh copilot` is explicitly out of scope.”
     - Or: “Support both, but only if X is detected” (this would still be one approach if it’s a single deterministic decision tree, not two open options).

6) Add a short “Considered Alternatives (Removed After Selection)” block per scenario (template has it) and keep it to one paragraph.
   - Example: for Scenario 1, mention pane indexes vs pane IDs and explicitly record why pane IDs were chosen.

### D) Strengthen repo-file citations (line ranges)
7) Add approximate line ranges for:
   - Session schema keys and where they are read/written.
   - Status values definition.
   - tmux title/border option usage (if the repo sets these today).

   Suggested approach: in “File Analysis”, add one sub-bullet per file for the exact symbols:
   - `SessionStore.load()/save()`
   - status constants definition
   - tmux pane creation helpers

### E) Align (or explicitly opt out of) sdd.2 styling requirements
8) Decide whether to adopt the “emoji callouts” instruction.
   - If adopting: add light-weight markers like “✅ Verified”, “⚠️ Risk”, “❓ Open question” next to key findings.
   - If not adopting: add a single sentence in “Project Conventions” explaining the deviation (e.g., “We intentionally omit emojis for consistency with repo docs style.”)

## Optional Improvements (Not required by your checklist, but helps)

- Add an explicit “Open Questions / Unknowns” section (if any) and move anything speculative out of “Key Discoveries”.
- Add references to the in-repo feature spec file(s) under `docs/feature-specs/` if they inform scope/requirements.
