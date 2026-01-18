import subprocess
from pathlib import Path


def _shell_single_quote(value: str) -> str:
    # Quote a string for safe embedding in a /bin/sh command.
    # Uses POSIX shell single-quote escaping: ' -> '\''
    return "'" + (value or "").replace("'", "'\\''") + "'"


class TmuxError(RuntimeError):
    pass


def _tmux_install_hint() -> str:
    return (
        "Install tmux and retry. On Debian/Ubuntu: "
        "sudo apt-get update && sudo apt-get install -y tmux"
    )


def _run_tmux(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = ["tmux", *args]
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise TmuxError(f"tmux not found on PATH. {_tmux_install_hint()}") from e


def ensure_tmux_available() -> None:
    result = _run_tmux(["-V"])
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "tmux is not available"
        raise TmuxError(f"{details}. {_tmux_install_hint()}")


def has_session(session_name: str) -> bool:
    result = _run_tmux(["has-session", "-t", session_name])
    return result.returncode == 0


def kill_session(session_name: str) -> None:
    result = _run_tmux(["kill-session", "-t", session_name])
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or "Failed to kill tmux session")


def start_2x2_session(*, session_name: str, cwd: Path) -> list[str]:
    if has_session(session_name):
        raise TmuxError(f"tmux session already exists: {session_name}")

    result = _run_tmux(["new-session", "-d", "-s", session_name, "-c", str(cwd)], cwd=cwd)
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or "Failed to create tmux session")

    # Pane 0 exists by default; capture its pane_id and use pane_id targeting thereafter.
    p0_res = _run_tmux(
        ["display-message", "-p", "-t", f"{session_name}:0.0", "#{pane_id}"],
        cwd=cwd,
    )
    if p0_res.returncode != 0:
        raise TmuxError(p0_res.stderr.strip() or "Failed to resolve tmux pane_id")
    p0 = p0_res.stdout.strip()
    if not p0:
        raise TmuxError("Failed to resolve tmux pane_id (empty output)")

    def _split(*, direction_args: list[str], target: str) -> str:
        r = _run_tmux(
            [
                "split-window",
                *direction_args,
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                target,
            ],
            cwd=cwd,
        )
        if r.returncode != 0:
            raise TmuxError(r.stderr.strip() or "Failed to split tmux pane")
        pane_id = r.stdout.strip()
        if not pane_id:
            raise TmuxError("Failed to split tmux pane (empty pane_id output)")
        return pane_id

    p1 = _split(direction_args=["-h"], target=p0)
    p2 = _split(direction_args=["-v"], target=p0)
    p3 = _split(direction_args=["-v"], target=p1)

    layout_res = _run_tmux(["select-layout", "-t", f"{session_name}:0", "tiled"], cwd=cwd)
    if layout_res.returncode != 0:
        raise TmuxError(layout_res.stderr.strip() or "Failed to set tmux layout")

    border_status_res = _run_tmux(
        ["set-option", "-t", session_name, "-g", "pane-border-status", "top"],
        cwd=cwd,
    )
    if border_status_res.returncode != 0:
        raise TmuxError(border_status_res.stderr.strip() or "Failed to enable tmux pane titles")

    border_format_res = _run_tmux(
        ["set-option", "-t", session_name, "-g", "pane-border-format", "#{pane_title}"],
        cwd=cwd,
    )
    if border_format_res.returncode != 0:
        raise TmuxError(border_format_res.stderr.strip() or "Failed to set tmux pane title format")

    # Improve UX inside embedded panes:
    # - Increase per-pane history so output is less likely to be lost.
    # - Enable mouse so mouse wheel scroll enters copy-mode for the active pane.
    #   (tmux does not support visible per-pane scrollbars.)
    history_res = _run_tmux(
        ["set-option", "-t", session_name, "history-limit", "100000"],
        cwd=cwd,
    )
    if history_res.returncode != 0:
        raise TmuxError(history_res.stderr.strip() or "Failed to set tmux history-limit")

    mouse_res = _run_tmux(
        ["set-option", "-t", session_name, "mouse", "on"],
        cwd=cwd,
    )
    if mouse_res.returncode != 0:
        raise TmuxError(mouse_res.stderr.strip() or "Failed to enable tmux mouse mode")

    return [p0, p1, p2, p3]


def configure_session(
    *,
    session_name: str,
    cwd: Path,
    history_limit: int | None = None,
    mouse: bool | None = None,
) -> None:
    if history_limit is not None:
        r = _run_tmux(
            ["set-option", "-t", session_name, "history-limit", str(history_limit)],
            cwd=cwd,
        )
        if r.returncode != 0:
            raise TmuxError(r.stderr.strip() or "Failed to set tmux history-limit")

    if mouse is not None:
        r = _run_tmux(
            ["set-option", "-t", session_name, "mouse", "on" if mouse else "off"],
            cwd=cwd,
        )
        if r.returncode != 0:
            raise TmuxError(r.stderr.strip() or "Failed to set tmux mouse mode")


def pipe_pane_to_file(*, target: str, log_path: Path, cwd: Path | None = None) -> None:
    # Pipe pane output to a file. This is the most reliable way to ensure output
    # is never lost, regardless of tmux history limits.
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # tmux runs the pipe command via /bin/sh -c, so we must shell-quote the path.
    cmd = f"cat >> {_shell_single_quote(str(log_path))}"
    r = _run_tmux(["pipe-pane", "-o", "-t", target, cmd], cwd=cwd)
    if r.returncode != 0:
        raise TmuxError(r.stderr.strip() or "Failed to pipe tmux pane output")


def set_pane_title(*, target: str, title: str) -> None:
    r = _run_tmux(["select-pane", "-t", target, "-T", title])
    if r.returncode != 0:
        raise TmuxError(r.stderr.strip() or "Failed to set pane title")


def focus_pane(*, target: str) -> None:
    r = _run_tmux(["select-pane", "-t", target])
    if r.returncode != 0:
        raise TmuxError(r.stderr.strip() or "Failed to focus tmux pane")


def send_keys(*, target: str, command: str) -> None:
    # Send the command as literal text, then press Enter.
    #
    # We've seen tmux occasionally misparse a combined invocation and error with
    # "unknown command: Enter". Splitting into two calls is more robust.
    cmd = command or ""

    if cmd:
        r1 = _run_tmux(["send-keys", "-t", target, "-l", cmd])
        if r1.returncode != 0:
            raise TmuxError(r1.stderr.strip() or "Failed to send keys")

    r2 = _run_tmux(["send-keys", "-t", target, "C-m"])
    if r2.returncode != 0:
        raise TmuxError(r2.stderr.strip() or "Failed to send keys")


def attach(session_name: str) -> None:
    # Attach should inherit the current stdin/stdout.
    cmd = ["tmux", "attach", "-t", session_name]
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        raise TmuxError("Failed to attach to tmux session")


def shell_banner(*, persona_name: str) -> str:
    # Keep it single-line safe.
    banner = (
        f"echo '=== Copilot Multi Persona: {persona_name} ==='; "
        "echo 'Shared context: .copilot-multi/'; "
        "echo 'Tip: update status with: copilot-multi set-status <persona> <status>'"
    )
    return banner
