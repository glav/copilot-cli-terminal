# Repo code citations research — copilot-multi (2026-01-15)

Scope: current implementation in `src/copilot_multi/*`.

## CLI entrypoint + subcommands + argparse contract

- Entrypoint `main()` + dispatch (`args.func`) + `__main__`:
  - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L284-L295)
- Argparse contract: parser/subcommands and their args:
  - `build_parser()` and `add_subparsers(dest="cmd", required=True)`:
    - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L249-L252)
  - `start`:
    - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L253-L256)
  - `status`:
    - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L257-L259)
  - `set-status` positional choices (`persona`, `status`) + optional `--message`:
    - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L260-L264)
  - `wait` positional persona + repeatable `--status` + `--timeout` + `--poll`:
    - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L266-L276)
  - `stop`:
    - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L278-L279)

## Session schema creation / validation (session.json structure)

- Session schema definition is the literal dict returned by `_init_session_state()`:
  - version/sessionName/repoRoot/createdAt + `personas.{key}.{displayName,status,updatedAt,message}`
  - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L82-L97)
- Initialization-once behavior (create `session.json` if empty/missing):
  - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L100-L108)
- Partial “schema repair” logic when setting status (creates missing keys rather than validating full schema):
  - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L193-L203)

## Allowed statuses + personas constants

- Persona keys and display names:
  - [src/copilot_multi/constants.py](src/copilot_multi/constants.py#L1-L6)
- Allowed statuses list:
  - [src/copilot_multi/constants.py](src/copilot_multi/constants.py#L8-L8)
- Shared dir + session filename + tmux session name:
  - [src/copilot_multi/constants.py](src/copilot_multi/constants.py#L10-L13)

## File locking / write behavior (session_store.py)

- Locked file wrapper, including JSON read (no corruption handling) and write (truncate + rewrite + fsync):
  - `LockedSession.read_json()`:
    - [src/copilot_multi/session_store.py](src/copilot_multi/session_store.py#L14-L21)
  - `LockedSession.write_json()`:
    - [src/copilot_multi/session_store.py](src/copilot_multi/session_store.py#L22-L30)
- File lock acquisition uses `fcntl.flock(LOCK_EX)` on an `os.open()` fd:
  - [src/copilot_multi/session_store.py](src/copilot_multi/session_store.py#L46-L53)
- Unlock uses `fcntl.flock(LOCK_UN)` then closes fd:
  - [src/copilot_multi/session_store.py](src/copilot_multi/session_store.py#L56-L63)

Notes:
- This is *mutual exclusion*, but not an atomic write/rename strategy. Writes are in-place with `truncate(0)`; a crash mid-write can leave partial/empty JSON.
- `json.loads()` errors (e.g., corrupted JSON) are not caught anywhere in `LockedSession.read_json()`.

## tmux pane creation + targeting (index vs pane_id)

- tmux availability (fail-fast) via `tmux -V` and `_run_tmux()` raising on `FileNotFoundError`:
  - [src/copilot_multi/tmux.py](src/copilot_multi/tmux.py#L9-L27)
- 2x2 creation logic uses a fixed sequence of `split-window` and `select-pane` targeting by *index* (`{session}:0.0`, `{session}:0.2`, etc):
  - [src/copilot_multi/tmux.py](src/copilot_multi/tmux.py#L40-L62)
- Pane title uses `select-pane -T` (implemented as separate argv elements; there is no literal string `"select-pane -T"` in the repo):
  - [src/copilot_multi/tmux.py](src/copilot_multi/tmux.py#L64-L68)
- CLI assigns personas to panes by explicit pane indices (no `pane_id` usage):
  - [src/copilot_multi/cli.py](src/copilot_multi/cli.py#L127-L150)

## Required grep_search results (src/**)

- `JSONDecodeError`: no matches in `src/**` (no explicit corruption recovery path).
- `flock`: present in session file lock/unlock:
  - [src/copilot_multi/session_store.py](src/copilot_multi/session_store.py#L46-L62)
- `pane_id`: no matches in `src/**` (pane targeting is index-based).
- `split-window`: present in 2x2 layout creation:
  - [src/copilot_multi/tmux.py](src/copilot_multi/tmux.py#L49-L55)
- `pane-border-status`: no matches in `src/**`.
- `select-pane -T`: no literal matches; equivalent behavior exists in:
  - [src/copilot_multi/tmux.py](src/copilot_multi/tmux.py#L64-L68)

## Gaps vs desired behavior (implementation observations)

- Corruption recovery: no handling for `json.JSONDecodeError` during read; any corrupted `session.json` will crash commands that read it.
- Atomicity: write path truncates and rewrites the same file descriptor; no temp-file + `os.replace()` atomic swap.
- Deterministic pane mapping: panes are addressed by index; mapping is deterministic *if* the `start_2x2_session()` sequence always yields the same indices, but there is no verification (e.g., querying tmux for pane IDs) nor recovery if layout differs.
- tmux missing: `cmd_start()` checks `shutil.which("tmux")` and also calls `ensure_tmux_available()`; this is already a fail-fast path.
- Docs/spec mismatch (FYI): feature spec references future commands like `copilot-multi config init` (not implemented in current argparse surface).
