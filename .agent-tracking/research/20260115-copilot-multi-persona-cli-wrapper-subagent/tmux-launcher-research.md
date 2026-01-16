# tmux launcher research (2026-01-15)

## TL;DR
- In this devcontainer, `tmux` is **not installed by default** (`tmux: command not found`).
- `sudo -n true` works (passwordless sudo).
- After running `sudo -n apt-get update`, `tmux` becomes **installable from apt** (`Candidate: 3.5a-3`), and `apt-get -s install tmux` simulates successfully.
- Recommended wrapper behavior: **detect missing tmux** and print an actionable message (install steps) and/or support a **non-tmux fallback** for environments where apt/sudo isn’t available.

## Evidence log (this container)

### tmux availability
Command:
```bash
command -v tmux

tmux -V
```
Output:
```text
## command -v tmux
exit:1
## tmux -V
bash: tmux: command not found
exit:127
```

### OS
Command:
```bash
cat /etc/os-release | sed -n '1,6p'
```
Output:
```text
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
VERSION="13 (trixie)"
VERSION_CODENAME=trixie
DEBIAN_VERSION_FULL=13.2
```

### sudo / apt constraints (non-installing probes)
Command:
```bash
sudo -n true

sudo -n apt-get update

apt-cache policy tmux

apt-get -s install tmux

sudo -n apt-get -s install tmux
```
Output:
```text
sudo -n true: OK (no password)

## sudo -n apt-get update
Get:1 http://deb.debian.org/debian trixie InRelease [140 kB]
Get:2 http://deb.debian.org/debian trixie-updates InRelease [47.3 kB]
Get:3 http://deb.debian.org/debian-security trixie-security InRelease [43.4 kB]
...
Reading package lists... Done
W: https://dl.yarnpkg.com/debian/dists/stable/InRelease: Policy will reject signature within a year, see --audit for details

## apt-cache policy tmux
tmux:
  Installed: (none)
  Candidate: 3.5a-3
  Version table:
     3.5a-3 500
        500 http://deb.debian.org/debian trixie/main amd64 Packages

## apt-get -s install tmux
NOTE: This is only a simulation!
...
The following NEW packages will be installed:
  libjemalloc2 tmux
...
Conf tmux (3.5a-3 Debian:13.3/stable [amd64])
```

Interpretation:
- `sudo` works non-interactively here.
- `tmux` is not present by default, but it *is* installable via apt once package lists are updated.
- If `sudo apt install tmux` fails with exit code 100 in this container, a good first remediation is `sudo apt-get update` and retry.

## Recommended tmux command patterns

### Create a session (detached)
```bash
tmux new-session -d -s <session> -n <window>
```
Notes:
- `-d` allows creation without attaching (works in non-interactive automation).
- If a session might already exist, guard with `tmux has-session`.

Useful existence checks:
```bash
tmux has-session -t <session>
# exit 0 if exists, non-zero otherwise
```

### Deterministic 2x2 panes (layout control)
Goal: always end with 4 panes in a 2x2 grid.

Reliable approach:
1. Start with one pane.
2. Split into two columns (`-h`) from the known starting pane.
3. Split each column into rows (`-v`) while targeting panes by **pane_id**.

Key best practice: capture pane IDs as you create panes.

Example (robust + deterministic):
```bash
session="mp"
window="main"

# Create session + window
# (If you want to reuse, kill existing or handle it separately.)
tmux new-session -d -s "$session" -n "$window"

# Get the initial pane id (left)
p0=$(tmux display-message -p -t "$session:$window" "#{pane_id}")

# Split into right column; capture new pane id
p1=$(tmux split-window -t "$p0" -h -P -F "#{pane_id}")

# Split left column into bottom-left
p2=$(tmux split-window -t "$p0" -v -P -F "#{pane_id}")

# Split right column into bottom-right
p3=$(tmux split-window -t "$p1" -v -P -F "#{pane_id}")

# Optional: force a stable grid layout
tmux select-layout -t "$session:$window" tiled
```

Why this is deterministic:
- You never rely on pane indexes (`0`, `1`, `2`, `3`) that can shift.
- Each split targets a specific `pane_id`.
- `select-layout tiled` normalizes sizing if prior content caused uneven splits.

### Pane titles (what “titles” mean in tmux)
There are 3 related concepts:

1) **Window name** (shows in status):
```bash
tmux rename-window -t <session>:<window> "My Window"
```

2) **Pane title** (a string stored per pane, not always displayed):
```bash
tmux select-pane -t <pane_id> -T "Planner"
```

3) **Showing titles in pane borders** (so humans can see them):
```bash
# enable border title area
tmux set-option -t <session> -g pane-border-status top

# show pane_title in the border
tmux set-option -t <session> -g pane-border-format "#{pane_title}"
```

Compatibility notes:
- `select-pane -T` exists in modern tmux; older tmux versions may not support it.
- Without configuring `pane-border-status` + `pane-border-format`, titles may exist but not be visible.

### Sending commands to specific panes
Most reliable:
```bash
tmux send-keys -t <pane_id> "echo hello" C-m
```

Notes:
- `C-m` is Enter.
- For literal text with minimal tmux parsing surprises, you can use `-l`:
  ```bash
  tmux send-keys -t <pane_id> -l "raw text" C-m
  ```

If you need to run a shell command with known environment, one pattern is:
```bash
tmux send-keys -t <pane_id> "cd /workspaces/... && ./run.sh" C-m
```

### Attach and kill
Attach:
```bash
tmux attach -t <session>
```

Kill session:
```bash
tmux kill-session -t <session>
```

If you need to clean up even when a client is attached:
- `kill-session` will terminate clients in that session.

## Robust pane addressing and determinism

### Prefer pane_id over pane_index
- `pane_index` (0,1,2,…) is convenient but can change after splits and layout operations.
- `pane_id` (like `%3`) is unique and stable for the life of the pane.

Useful inspection commands:
```bash
tmux list-panes -t <session>:<window> -F "#{pane_id} idx=#{pane_index} active=#{pane_active} title=#{pane_title}"
```

Capture pane IDs at creation time (best practice):
- Use `split-window -P -F "#{pane_id}"` which prints the new pane’s ID.

### Make layout repeatable
- After creating panes, run one of:
  - `tmux select-layout tiled` (good for 2x2)
  - `tmux select-layout even-horizontal` / `even-vertical` (when you want only one split direction)

If you need exact sizes, use `resize-pane -x/-y` after splits.

## Common pitfalls (and mitigations)

### 1) `tmux` missing in containers
Symptoms:
- `tmux: command not found`

Mitigation:
- Detect early:
  ```bash
  command -v tmux >/dev/null 2>&1 || echo "tmux missing"
  ```
- If `sudo` + apt are available, provide copy/paste install steps:
  ```bash
  sudo apt-get update && sudo apt-get install -y tmux
  ```
- Offer alternatives (spawn subprocesses and multiplex logs) when tmux is not available.

### 2) Non-interactive environments
- You can create sessions detached (`new-session -d`) without a TTY.
- Attaching (`attach`) requires a terminal.

Mitigation:
- In automation: avoid attaching; use `capture-pane` for logs if needed:
  ```bash
  tmux capture-pane -t <pane_id> -p
  ```

### 3) Quoting/escaping issues in `send-keys`
- Shell quoting rules still apply because you’re typically passing a string that the pane’s shell will interpret.

Mitigation:
- Keep commands simple; prefer invoking scripts.
- Use `-l` for literal typing.

### 4) Title display confusion
- Setting a pane title doesn’t automatically display it.

Mitigation:
- Set `pane-border-status` + `pane-border-format` as shown above.

### 5) Running tmux inside tmux
- Starting a nested tmux client can be confusing.

Mitigation:
- Detect `TMUX` env var; decide whether to reuse existing server/session or require a fresh session name.

## Suggested best practices for a launcher implementation
- Fail fast with a clear error if `tmux` is required but missing.
- Prefer pane ID capture (`split-window -P -F '#{pane_id}'`) over pane indexes.
- Normalize layout after splits (`select-layout tiled`) to keep a stable UI.
- Set pane border titles explicitly (`pane-border-status` and `pane-border-format`).
- Centralize command sending in a helper that always targets pane IDs and appends Enter (`C-m`).

## Practical command template (copy/paste)
```bash
session="mp"
window="main"

tmux has-session -t "$session" 2>/dev/null && tmux kill-session -t "$session"

tmux new-session -d -s "$session" -n "$window"

p0=$(tmux display-message -p -t "$session:$window" "#{pane_id}")
p1=$(tmux split-window -t "$p0" -h -P -F "#{pane_id}")
p2=$(tmux split-window -t "$p0" -v -P -F "#{pane_id}")
p3=$(tmux split-window -t "$p1" -v -P -F "#{pane_id}")

tmux set-option -t "$session" -g pane-border-status top
tmux set-option -t "$session" -g pane-border-format "#{pane_title}"

tmux select-pane -t "$p0" -T "Planner"
tmux select-pane -t "$p2" -T "Coder"
tmux select-pane -t "$p1" -T "Reviewer"
tmux select-pane -t "$p3" -T "Runner"

tmux send-keys -t "$p0" "echo Planner pane" C-m

tmux select-layout -t "$session:$window" tiled

# attach interactively (only if you have a TTY)
# tmux attach -t "$session"
```
