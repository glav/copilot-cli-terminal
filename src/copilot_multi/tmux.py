import subprocess
from pathlib import Path


class TmuxError(RuntimeError):
    pass


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
        raise TmuxError("tmux not found on PATH") from e


def ensure_tmux_available() -> None:
    result = _run_tmux(["-V"])
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or "tmux is not available")


def has_session(session_name: str) -> bool:
    result = _run_tmux(["has-session", "-t", session_name])
    return result.returncode == 0


def kill_session(session_name: str) -> None:
    result = _run_tmux(["kill-session", "-t", session_name])
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or "Failed to kill tmux session")


def start_2x2_session(*, session_name: str, cwd: Path) -> None:
    if has_session(session_name):
        raise TmuxError(f"tmux session already exists: {session_name}")

    result = _run_tmux(["new-session", "-d", "-s", session_name], cwd=cwd)
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or "Failed to create tmux session")

    # Pane 0 exists by default.
    steps: list[list[str]] = [
        ["split-window", "-h", "-t", f"{session_name}:0.0"],
        ["select-pane", "-t", f"{session_name}:0.0"],
        ["split-window", "-v", "-t", f"{session_name}:0.0"],
        ["select-pane", "-t", f"{session_name}:0.2"],
        ["split-window", "-v", "-t", f"{session_name}:0.2"],
        ["select-layout", "-t", f"{session_name}:0", "tiled"],
    ]

    for args in steps:
        r = _run_tmux(args, cwd=cwd)
        if r.returncode != 0:
            raise TmuxError(r.stderr.strip() or f"tmux failed: {' '.join(args)}")


def set_pane_title(*, target: str, title: str) -> None:
    r = _run_tmux(["select-pane", "-t", target, "-T", title])
    if r.returncode != 0:
        raise TmuxError(r.stderr.strip() or "Failed to set pane title")


def send_keys(*, target: str, command: str) -> None:
    # Use `send-keys` with a single shell command; tmux will type it into the pane.
    r = _run_tmux(["send-keys", "-t", target, command, "Enter"])
    if r.returncode != 0:
        raise TmuxError(r.stderr.strip() or "Failed to send keys")


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
