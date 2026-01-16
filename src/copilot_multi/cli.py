import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
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
    focus_pane,
    has_session,
    kill_session,
    send_keys,
    set_pane_title,
    start_2x2_session,
)

CURRENT_SESSION_VERSION = 2


def _broker_socket_path(repo_root: Path) -> Path:
    return _shared_dir(repo_root) / "broker.sock"


def _broker_pid_path(repo_root: Path) -> Path:
    return _shared_dir(repo_root) / "broker.pid"


def _copilot_shared_dir(repo_root: Path) -> Path:
    # Keep Copilot CLI state/config local to the repo so panes share it.
    return _shared_dir(repo_root) / "copilot"


def _default_copilot_config_dir() -> Path:
    # Copilot CLI defaults to $HOME/.copilot when XDG_* are not set.
    # We use this to detect and reuse an existing authenticated session.
    return Path.home() / ".copilot"


def _copilot_config_dir_marker_path(repo_root: Path) -> Path:
    return _shared_dir(repo_root) / "copilot-config-dir.txt"


def _copilot_auth_marker_path(repo_root: Path) -> Path:
    return _shared_dir(repo_root) / "copilot-authenticated.txt"


def _copilot_env_for_dir(copilot_config_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    # Rely on `copilot --config-dir ...` to select the active Copilot directory.
    # Overriding XDG_* can cause Copilot CLI to look in a different location and
    # appear unauthenticated even when the config dir is valid.
    return env


def _looks_like_no_auth_error(text: str) -> bool:
    return "no authentication information found" in (text or "").lower()


def _copilot_session_marker_path(repo_root: Path) -> Path:
    return _shared_dir(repo_root) / "copilot.session"


def _is_broker_responsive(socket_path: Path, timeout_seconds: float = 0.2) -> bool:
    if not socket_path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_seconds)
            s.connect(str(socket_path))
            s.sendall(b'{"kind":"ping"}\n')
            data = s.recv(2048)
            return b"pong" in data
    except OSError:
        return False


def _broker_info(socket_path: Path, timeout_seconds: float = 0.3) -> dict | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_seconds)
            s.connect(str(socket_path))
            s.sendall(b'{"kind":"info"}\n')
            raw = s.recv(8192)
    except OSError:
        return None

    try:
        line = raw.split(b"\n", 1)[0]
        return json.loads(line.decode("utf-8"))
    except Exception:
        return None


def _has_copilot_token_env() -> bool:
    # Copilot CLI supports these env vars (in precedence order):
    # COPILOT_GITHUB_TOKEN, GH_TOKEN, GITHUB_TOKEN.
    return bool(
        os.environ.get("COPILOT_GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )


def _has_gh_auth(repo_root: Path) -> bool:
    if shutil.which("gh") is None:
        return False
    proc = subprocess.run(
        ["gh", "auth", "status"],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _copilot_config_dir_looks_authenticated(copilot_config_dir: Path) -> bool:
    # Heuristic: Copilot stores auth material in its config dir.
    # Avoid reading any secrets; only check for presence of likely auth files.
    if not copilot_config_dir.exists() or not copilot_config_dir.is_dir():
        return False

    likely_names = {
        "auth.json",
        "oauth.json",
        "oauth-token.json",
        "credentials.json",
        "hosts.json",
        "token.json",
    }

    for candidate in likely_names:
        path = copilot_config_dir / candidate
        try:
            if path.exists() and path.is_file() and path.stat().st_size > 0:
                return True
        except OSError:
            continue

    # Copilot frequently persists session/auth state under session-state.
    try:
        session_state = copilot_config_dir / "session-state"
        if session_state.exists() and session_state.is_dir():
            for p in session_state.glob("*/events.jsonl"):
                if p.exists() and p.stat().st_size > 0:
                    return True
    except OSError:
        pass

    # Fallback: any file with "auth" or "token" in the name.
    try:
        for p in copilot_config_dir.glob("*.json"):
            name = p.name.lower()
            if ("auth" in name or "token" in name or "oauth" in name) and p.stat().st_size > 0:
                return True
    except OSError:
        return False

    return False


def _copilot_auth_smoke_test(*, copilot_config_dir: Path, repo_root: Path) -> bool:
    # As a last resort, run a tiny non-interactive prompt with a very short timeout.
    # If unauthenticated, Copilot CLI fails fast with a clear error.
    # If authenticated, it may take time to answer; a timeout is treated as success.
    copilot_config_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "copilot",
        "--config-dir",
        str(copilot_config_dir),
        "--add-dir",
        str(repo_root),
        "--no-color",
        "--stream",
        "off",
        "--silent",
        "-p",
        "Reply with exactly: OK",
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=_copilot_env_for_dir(copilot_config_dir),
            text=True,
            capture_output=True,
            check=False,
            timeout=2.0,
        )
    except subprocess.TimeoutExpired as e:
        combined = (e.stdout or "") + (e.stderr or "")
        if _looks_like_no_auth_error(combined):
            return False
        return True

    combined = (proc.stdout or "") + (proc.stderr or "")
    if _looks_like_no_auth_error(combined):
        return False
    if proc.returncode == 0:
        return True
    # Unknown failure: assume authenticated to avoid blocking startup.
    return True


def _copilot_is_authenticated(*, copilot_config_dir: Path, repo_root: Path) -> bool:
    marker = _copilot_auth_marker_path(repo_root)
    if marker.exists():
        try:
            recorded = marker.read_text(encoding="utf-8").strip()
            if recorded and recorded == str(copilot_config_dir):
                ok = _copilot_auth_smoke_test(
                    copilot_config_dir=copilot_config_dir,
                    repo_root=repo_root,
                )
                if ok:
                    return True
                # Stale marker: remove so we don't keep selecting a bad config dir.
                try:
                    marker.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    if _has_copilot_token_env():
        return True
    if _has_gh_auth(repo_root):
        return True
    if _copilot_config_dir_looks_authenticated(copilot_config_dir):
        return True

    ok = _copilot_auth_smoke_test(copilot_config_dir=copilot_config_dir, repo_root=repo_root)
    if ok:
        try:
            marker.write_text(str(copilot_config_dir) + "\n", encoding="utf-8")
        except OSError:
            pass
    return ok


def _resolve_copilot_config_dir(repo_root: Path) -> Path:
    # Prefer any previously selected config dir, but only if it still works.
    hint_path = _copilot_config_dir_marker_path(repo_root)
    if hint_path.exists():
        try:
            hinted = Path(hint_path.read_text(encoding="utf-8").strip())
        except OSError:
            hinted = None

        if hinted is not None and _copilot_is_authenticated(
            copilot_config_dir=hinted,
            repo_root=repo_root,
        ):
            return hinted

    # Prefer repo-local copilot state if already authenticated there.
    repo_local = _copilot_shared_dir(repo_root)
    if _copilot_is_authenticated(copilot_config_dir=repo_local, repo_root=repo_root):
        return repo_local

    # Otherwise, fall back to the user's default Copilot directory if it's already authenticated.
    default_dir = _default_copilot_config_dir()
    if _copilot_is_authenticated(copilot_config_dir=default_dir, repo_root=repo_root):
        return default_dir

    # If neither is authenticated, we will authenticate into the repo-local dir.
    return repo_local


def _ensure_copilot_authenticated(*, copilot_config_dir: Path, repo_root: Path) -> None:
    if _copilot_is_authenticated(copilot_config_dir=copilot_config_dir, repo_root=repo_root):
        return

    print("Copilot CLI is not authenticated; launching login flow...")
    print("In the Copilot CLI, run '/login' then exit when done.")
    print(f"Using config dir: {copilot_config_dir}")

    proc = subprocess.run(
        [
            "copilot",
            "--config-dir",
            str(copilot_config_dir),
            "--add-dir",
            str(repo_root),
        ],
        cwd=str(repo_root),
        env=_copilot_env_for_dir(copilot_config_dir),
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit("Copilot authentication flow exited with an error")

    # Copilot CLI doesn't currently provide a reliable, fast, non-model way to
    # verify login state across environments. If the user completed `/login` and
    # exited cleanly, persist a local marker and proceed.
    try:
        _copilot_auth_marker_path(repo_root).write_text(
            str(copilot_config_dir) + "\n", encoding="utf-8"
        )
    except OSError:
        pass

    return


def _start_broker(*, repo_root: Path, copilot_config_dir: Path) -> None:
    socket_path = _broker_socket_path(repo_root)
    pid_path = _broker_pid_path(repo_root)
    session_marker = _copilot_session_marker_path(repo_root)
    log_path = _shared_dir(repo_root) / "broker.log"

    _shared_dir(repo_root).mkdir(parents=True, exist_ok=True)
    copilot_config_dir.mkdir(parents=True, exist_ok=True)

    if _is_broker_responsive(socket_path):
        info = _broker_info(socket_path)
        if isinstance(info, dict) and info.get("copilotConfigDir") == str(copilot_config_dir):
            return

        # Broker is running but pointed at a different config dir; restart it.
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text(encoding="utf-8").strip())
                import signal

                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

        try:
            socket_path.unlink()
        except OSError:
            pass

    # If we have a PID but no responsive socket, try to terminate the stale broker.
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
        except Exception:
            pid = None

        if pid is not None:
            try:
                import signal

                os.kill(pid, signal.SIGTERM)
                for _ in range(20):
                    if not pid_path.exists():
                        break
                    time.sleep(0.05)
                # Force-kill if still alive.
                try:
                    os.kill(pid, 0)
                except OSError:
                    pass
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

        # Clean up any stale artifacts; the new broker will recreate them.
        try:
            pid_path.unlink()
        except OSError:
            pass
        try:
            socket_path.unlink()
        except OSError:
            pass

    # Start the broker as a detached process. It will create the socket + pid file.
    with log_path.open("a", encoding="utf-8") as log_fp:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "copilot_multi.broker",
                "--socket",
                str(socket_path),
                "--repo-root",
                str(repo_root),
                "--copilot-config-dir",
                str(copilot_config_dir),
                "--pid-file",
                str(pid_path),
                "--session-marker-file",
                str(session_marker),
            ],
            cwd=str(repo_root),
            stdout=log_fp,
            stderr=log_fp,
            start_new_session=True,
        )

    # Wait briefly for broker readiness.
    for _ in range(30):
        if _is_broker_responsive(socket_path):
            return
        time.sleep(0.1)

    raise SystemExit(f"Broker failed to start (no socket): {socket_path}")


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
        "version": CURRENT_SESSION_VERSION,
        "sessionName": TMUX_SESSION_NAME,
        "repoRoot": str(repo_root),
        "createdAt": utc_now_iso(),
        "personas": {
            key: {
                "displayName": display,
                "status": "idle",
                "updatedAt": utc_now_iso(),
                "message": "",
                "paneId": "",
            }
            for key, display in PERSONAS.items()
        },
    }


def _normalize_session_state(repo_root: Path, data: dict | None) -> dict:
    if not isinstance(data, dict) or not data:
        return _init_session_state(repo_root)

    version = data.get("version")
    try:
        version_int = int(version)
    except (TypeError, ValueError):
        version_int = 1

    normalized = {
        "version": version_int,
        "sessionName": TMUX_SESSION_NAME,
        "repoRoot": str(repo_root),
        "createdAt": data.get("createdAt") or utc_now_iso(),
        "personas": {},
    }

    personas = data.get("personas")
    if not isinstance(personas, dict):
        personas = {}

    for key, display in PERSONAS.items():
        existing = personas.get(key)
        if not isinstance(existing, dict):
            existing = {}

        status = existing.get("status")
        if status not in ALLOWED_STATUSES:
            status = "idle"

        normalized["personas"][key] = {
            "displayName": existing.get("displayName") or display,
            "status": status,
            "updatedAt": existing.get("updatedAt") or utc_now_iso(),
            "message": existing.get("message") or "",
            "paneId": existing.get("paneId") or "",
        }

    # Simple migration strategy: bump to CURRENT_SESSION_VERSION after normalization.
    normalized["version"] = CURRENT_SESSION_VERSION
    return normalized


def _write_session_state_if_missing(session_path: Path, state: dict) -> None:
    locked = lock_session_file(session_path)
    try:
        existing = locked.read_json()
        if existing:
            normalized = _normalize_session_state(_repo_root_from_cwd(), existing)
            if normalized != existing:
                locked.write_json(normalized)
            return
        locked.write_json(_normalize_session_state(_repo_root_from_cwd(), state))
    finally:
        unlock_session_file(locked)


def cmd_start(args: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    shared_dir = _shared_dir(repo_root)
    session_path = _session_path(repo_root)

    if shutil.which("copilot") is None:
        raise SystemExit(
            "GitHub Copilot CLI ('copilot') is required. Install/authenticate it and retry. "
            "See README for install and login guidance."
        )

    ensure_tmux_available()
    _ensure_shared_files(shared_dir)

    copilot_config_dir = _resolve_copilot_config_dir(repo_root)
    _ensure_copilot_authenticated(copilot_config_dir=copilot_config_dir, repo_root=repo_root)
    try:
        _copilot_config_dir_marker_path(repo_root).write_text(
            str(copilot_config_dir) + "\n", encoding="utf-8"
        )
    except OSError:
        pass

    _start_broker(repo_root=repo_root, copilot_config_dir=copilot_config_dir)

    # If the session already exists, treat `start` as idempotent: attach (default)
    # or no-op when explicitly detached.
    if has_session(TMUX_SESSION_NAME):
        if getattr(args, "detach", False):
            print(
                f"tmux session '{TMUX_SESSION_NAME}' is already running. "
                f"Attach with: tmux attach -t {TMUX_SESSION_NAME}"
            )
            return 0

        # Best-effort: focus the PM pane before attaching.
        pm_target = f"{TMUX_SESSION_NAME}:0.0"
        locked = lock_session_file(session_path)
        try:
            data = _normalize_session_state(repo_root, locked.read_json())
            maybe = data.get("personas", {}).get("pm", {}).get("paneId")
            if isinstance(maybe, str) and maybe:
                pm_target = maybe
        finally:
            unlock_session_file(locked)

        focus_pane(target=pm_target)
        attach(TMUX_SESSION_NAME)
        return 0

    state = _init_session_state(repo_root)
    _write_session_state_if_missing(session_path, state)

    pane_ids = start_2x2_session(session_name=TMUX_SESSION_NAME, cwd=repo_root)

    persona_keys = ["pm", "impl", "review", "docs"]
    pane_targets_by_persona = dict(zip(persona_keys, pane_ids, strict=True))

    locked = lock_session_file(session_path)
    try:
        data = _normalize_session_state(repo_root, locked.read_json() or state)
        for persona_key, pane_id in pane_targets_by_persona.items():
            persona_data = data["personas"].setdefault(persona_key, {})
            persona_data.setdefault("displayName", PERSONAS[persona_key])
            persona_data["paneId"] = pane_id
        locked.write_json(data)
    finally:
        unlock_session_file(locked)

    for persona_key, target in pane_targets_by_persona.items():
        display = PERSONAS[persona_key]
        set_pane_title(target=target, title=display)
        send_keys(target=target, command=f"export COPILOT_MULTI_PERSONA={persona_key}")
        send_keys(target=target, command="cd " + str(repo_root))
        # Route all input through a per-pane REPL that forwards prompts to a shared broker.
        send_keys(
            target=target,
            command=(
                "clear; "
                + f"echo '=== Copilot Multi Persona: {display} ==='; "
                + "echo 'Starting Copilot router...'; "
                + "echo 'Tmux tip: use Ctrl-b o (or Ctrl-b + arrows) to switch panes'; "
                + "echo 'Tmux tip: Ctrl-b q shows pane numbers'; "
                + "uv run python -m copilot_multi.pane_repl "
                + f"--persona {persona_key} "
                + f"--socket {str(_broker_socket_path(repo_root))} "
                + f"--repo-root {str(repo_root)}"
            ),
        )

    # Ensure PM is the active pane when the user attaches.
    focus_pane(target=pane_targets_by_persona["pm"])

    if getattr(args, "detach", False):
        print(
            f"Started tmux session '{TMUX_SESSION_NAME}'. "
            f"Attach with: tmux attach -t {TMUX_SESSION_NAME}"
        )
        return 0

    attach(TMUX_SESSION_NAME)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    session_path = _session_path(repo_root)

    locked = lock_session_file(session_path)
    try:
        existing = locked.read_json()
        data = _normalize_session_state(repo_root, existing)
        if data != existing:
            locked.write_json(data)
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
        data = _normalize_session_state(repo_root, locked.read_json())
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
    repo_root = _repo_root_from_cwd()

    # Best-effort: stop broker first (it may outlive the tmux session).
    pid_path = _broker_pid_path(repo_root)
    socket_path = _broker_socket_path(repo_root)
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            import os
            import signal

            # SIGTERM and wait briefly for cleanup.
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not pid_path.exists():
                    break
                time.sleep(0.05)

            # If still alive, force kill.
            try:
                os.kill(pid, 0)
            except OSError:
                pass
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

            # Clean up pid file if it didn't get removed by the broker.
            if pid_path.exists():
                try:
                    pid_path.unlink()
                except OSError:
                    pass
        except Exception:
            pass

    # Clean up broker socket only when it isn't responsive.
    if socket_path.exists() and not _is_broker_responsive(socket_path):
        try:
            socket_path.unlink()
        except OSError:
            pass

    if has_session(TMUX_SESSION_NAME):
        try:
            kill_session(TMUX_SESSION_NAME)
            print(f"Stopped tmux session '{TMUX_SESSION_NAME}'.")
        except TmuxError as e:
            raise SystemExit(str(e)) from e
    else:
        print(f"tmux session '{TMUX_SESSION_NAME}' is not running.")
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    repo_root = _repo_root_from_cwd()
    shared_dir = _shared_dir(repo_root)

    if shutil.which("copilot") is None:
        raise SystemExit(
            "GitHub Copilot CLI ('copilot') is required. Install/authenticate it and retry. "
            "See README for install and login guidance."
        )

    shared_dir.mkdir(parents=True, exist_ok=True)

    copilot_config_dir = _resolve_copilot_config_dir(repo_root)
    _ensure_copilot_authenticated(copilot_config_dir=copilot_config_dir, repo_root=repo_root)

    try:
        _copilot_config_dir_marker_path(repo_root).write_text(
            str(copilot_config_dir) + "\n", encoding="utf-8"
        )
    except OSError:
        pass

    print(f"Copilot CLI authenticated. Config dir: {copilot_config_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="copilot-multi")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Start a 4-pane tmux session")
    # Default UX: attach immediately.
    # Keep --attach for backward compatibility (it is effectively a no-op now).
    p_start.add_argument("--detach", action="store_true", help="Start but do not attach")
    p_start.add_argument("--attach", action="store_true", help=argparse.SUPPRESS)
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

    p_auth = sub.add_parser(
        "auth",
        help="Authenticate Copilot CLI (runs 'copilot' for /login if needed)",
    )
    p_auth.set_defaults(func=cmd_auth)

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
