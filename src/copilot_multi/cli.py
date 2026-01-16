import argparse
import json
import shutil
from pathlib import Path

from copilot_multi.constants import (
    ALLOWED_STATUSES,
    DEFAULT_SESSION_FILE_NAME,
    DEFAULT_SHARED_DIR_NAME,
    PERSONAS,
    TMUX_SESSION_NAME,
)
from copilot_multi.session_store import (
    lock_session_file,
    unlock_session_file,
    utc_now_iso,
    wait_for_predicate,
)
from copilot_multi.tmux import (
    TmuxError,
    attach,
    ensure_tmux_available,
    kill_session,
    send_keys,
    set_pane_title,
    start_2x2_session,
)


def _repo_root_from_cwd() -> Path:
    return Path.cwd()


def _shared_dir(repo_root: Path) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME


def _session_path(repo_root: Path) -> Path:
    return _shared_dir(repo_root) / DEFAULT_SESSION_FILE_NAME


def _ensure_shared_files(shared_dir: Path) -> list[Path]:
    shared_dir.mkdir(parents=True, exist_ok=True)
    templates = {
        "WORK_CONTEXT.md": (
            "# Work Context\n\n"
            "## Current goal\n"
            "- TBD\n\n"
            "## Current constraints\n"
            "- Linux-only MVP\n"
            "- tmux panes\n\n"
            "## Notes\n"
            "- TBD\n"
        ),
        "DECISIONS.md": (
            "# Decisions\n\n"
            "| Date | Decision | Rationale | Owner |\n"
            "|------|----------|-----------|-------|\n"
        ),
        "HANDOFF.md": (
            "# Handoff\n\n"
            "## From\n"
            "- Persona: TBD\n\n"
            "## To\n"
            "- Persona: TBD\n\n"
            "## What changed\n"
            "- TBD\n\n"
            "## Next steps\n"
            "- TBD\n"
        ),
    }

    created: list[Path] = []
    for name, content in templates.items():
        path = shared_dir / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created


def _init_session_state(repo_root: Path) -> dict:
    return {
        "version": 1,
        "sessionName": TMUX_SESSION_NAME,
        "repoRoot": str(repo_root),
        "createdAt": utc_now_iso(),
        "personas": {
            key: {
                "displayName": display,
                "status": "idle",
                "updatedAt": utc_now_iso(),
                "message": "",
            }
            for key, display in PERSONAS.items()
        },
    }


def _write_session_state_if_missing(session_path: Path, state: dict) -> None:
    locked = lock_session_file(session_path)
    try:
        existing = locked.read_json()
        if existing:
            return
        locked.write_json(state)
    finally:
        unlock_session_file(locked)


def cmd_start(args: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    shared_dir = _shared_dir(repo_root)
    session_path = _session_path(repo_root)

    if shutil.which("tmux") is None:
        raise SystemExit("tmux is required for MVP (Linux-only). Install tmux and retry.")

    ensure_tmux_available()
    _ensure_shared_files(shared_dir)

    state = _init_session_state(repo_root)
    _write_session_state_if_missing(session_path, state)

    start_2x2_session(session_name=TMUX_SESSION_NAME, cwd=repo_root)

    pane_targets = [
        f"{TMUX_SESSION_NAME}:0.0",
        f"{TMUX_SESSION_NAME}:0.1",
        f"{TMUX_SESSION_NAME}:0.2",
        f"{TMUX_SESSION_NAME}:0.3",
    ]
    persona_keys = ["pm", "impl", "review", "docs"]

    for target, persona_key in zip(pane_targets, persona_keys, strict=True):
        display = PERSONAS[persona_key]
        set_pane_title(target=target, title=display)
        send_keys(target=target, command=f"export COPILOT_MULTI_PERSONA={persona_key}")
        send_keys(target=target, command="cd " + str(repo_root))
        send_keys(
            target=target,
            command=(
                "clear; "
                + f"echo '=== Copilot Multi Persona: {display} ==='; "
                + "echo 'Shared context lives in: .copilot-multi/'; "
                + "echo 'Update status: copilot-multi set-status "
                + "<pm|impl|review|docs> <idle|working|waiting|done|blocked>'; "
                + "echo 'Run Copilot: copilot';"
            ),
        )

    if args.attach:
        attach(TMUX_SESSION_NAME)
    else:
        print(
            f"Started tmux session '{TMUX_SESSION_NAME}'. "
            f"Attach with: tmux attach -t {TMUX_SESSION_NAME}"
        )
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    session_path = _session_path(repo_root)

    if not session_path.exists():
        raise SystemExit("No session state found. Run: copilot-multi start")

    locked = lock_session_file(session_path)
    try:
        data = locked.read_json()
    finally:
        unlock_session_file(locked)

    print(json.dumps(data.get("personas", {}), indent=2, sort_keys=True))
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    session_path = _session_path(repo_root)

    persona = args.persona
    status = args.status

    if persona not in PERSONAS:
        raise SystemExit(f"Unknown persona '{persona}'. Expected one of: {', '.join(PERSONAS)}")
    if status not in ALLOWED_STATUSES:
        raise SystemExit(
            f"Unknown status '{status}'. Expected one of: {', '.join(ALLOWED_STATUSES)}"
        )

    locked = lock_session_file(session_path)
    try:
        data = locked.read_json() or _init_session_state(repo_root)
        data.setdefault("personas", {})
        data["personas"].setdefault(persona, {"displayName": PERSONAS[persona]})
        data["personas"][persona]["status"] = status
        data["personas"][persona]["updatedAt"] = utc_now_iso()
        if args.message is not None:
            data["personas"][persona]["message"] = args.message
        locked.write_json(data)
    finally:
        unlock_session_file(locked)

    print(f"{persona} => {status}")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    session_path = _session_path(repo_root)

    persona = args.persona
    desired = set(args.status)

    if persona not in PERSONAS:
        raise SystemExit(f"Unknown persona '{persona}'. Expected one of: {', '.join(PERSONAS)}")

    for st in desired:
        if st not in ALLOWED_STATUSES:
            raise SystemExit(
                f"Unknown status '{st}'. Expected one of: {', '.join(ALLOWED_STATUSES)}"
            )

    ok = wait_for_predicate(
        session_path=session_path,
        predicate=lambda data: data.get("personas", {}).get(persona, {}).get("status") in desired,
        timeout_seconds=args.timeout,
        poll_interval_seconds=args.poll,
    )

    if not ok:
        raise SystemExit(f"Timed out waiting for {persona} to be in {sorted(desired)}")

    print(f"{persona} reached status in {sorted(desired)}")
    return 0


def cmd_stop(_: argparse.Namespace) -> int:
    try:
        kill_session(TMUX_SESSION_NAME)
        print(f"Stopped tmux session '{TMUX_SESSION_NAME}'.")
    except TmuxError as e:
        raise SystemExit(str(e)) from e
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="copilot-multi")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Start a 4-pane tmux session")
    p_start.add_argument("--attach", action="store_true", help="Attach immediately")
    p_start.set_defaults(func=cmd_start)

    p_status = sub.add_parser("status", help="Show persona statuses")
    p_status.set_defaults(func=cmd_status)

    p_set = sub.add_parser("set-status", help="Set a persona status")
    p_set.add_argument("persona", choices=sorted(PERSONAS.keys()))
    p_set.add_argument("status", choices=ALLOWED_STATUSES)
    p_set.add_argument("--message", help="Optional status message")
    p_set.set_defaults(func=cmd_set_status)

    p_wait = sub.add_parser("wait", help="Wait for persona to reach a status")
    p_wait.add_argument("persona", choices=sorted(PERSONAS.keys()))
    p_wait.add_argument(
        "--status",
        action="append",
        required=True,
        help="Status to wait for (repeatable)",
    )
    p_wait.add_argument("--timeout", type=float, default=None, help="Timeout seconds")
    p_wait.add_argument("--poll", type=float, default=0.5, help="Polling interval seconds")
    p_wait.set_defaults(func=cmd_wait)

    p_stop = sub.add_parser("stop", help="Stop the tmux session")
    p_stop.set_defaults(func=cmd_stop)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except TmuxError as e:
        raise SystemExit(str(e)) from e


if __name__ == "__main__":
    raise SystemExit(main())
