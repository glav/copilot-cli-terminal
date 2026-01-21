import argparse
import atexit
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from copilot_multi.constants import (
    DEFAULT_SESSION_FILE_NAME,
    DEFAULT_SHARED_DIR_NAME,
    PERSONAS,
)
from copilot_multi.session_store import lock_session_file, unlock_session_file, utc_now_iso
from copilot_multi.tmux import TmuxError, send_keys
from copilot_multi.ui import Ansi, UiConfig


@dataclass(frozen=True)
class _AgentRequest:
    idx: int
    persona: str
    segment: str
    deps: set[str]
    deadline: float


def _print_err(message: str, *, ansi: Ansi | None = None) -> None:
    text = ansi.error_text(message) if ansi else message
    print(text, file=sys.stderr)


def _print_local(message: str, *, ansi: Ansi | None = None) -> None:
    if ansi:
        print(f"{ansi.local_prefix()} {message}")
    else:
        print(f"(local) {message}")


def _spinner(stop_event: threading.Event, text: str = "Waiting for response...") -> None:
    frames = ["|", "/", "-", "\\"]
    clear_len = len(text) + 2
    idx = 0
    while not stop_event.is_set():
        frame = frames[idx % len(frames)]
        sys.stderr.write(f"\r{frame} {text}")
        sys.stderr.flush()
        stop_event.wait(0.1)
        idx += 1
    sys.stderr.write("\r" + (" " * clear_len) + "\r")
    sys.stderr.flush()


def _connect_and_send(*, socket_path: Path, payload: dict, show_spinner: bool = False) -> dict:
    raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    stop_event: threading.Event | None = None
    spinner_thread: threading.Thread | None = None
    if show_spinner and sys.stderr.isatty():
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=_spinner, args=(stop_event,), daemon=True)
        spinner_thread.start()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        try:
            s.connect(str(socket_path))
            s.sendall(raw)
            chunks: list[bytes] = []
            while True:
                data = s.recv(65536)
                if not data:
                    break
                chunks.append(data)
                if b"\n" in data:
                    break
        finally:
            if stop_event and spinner_thread:
                stop_event.set()
                spinner_thread.join()

    joined = b"".join(chunks)
    line = joined.split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))


def _run_local_command(command_line: str) -> int:
    try:
        argv = shlex.split(command_line)
    except ValueError as e:
        _print_err(f"Parse error: {e}")
        return 2

    if not argv:
        return 0

    proc = subprocess.run(argv, text=True)
    return int(proc.returncode)


def _session_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME / DEFAULT_SESSION_FILE_NAME


def _history_path(*, repo_root: Path, persona: str) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME / "history" / f"{persona}.txt"


def _response_id_path(*, repo_root: Path, persona: str) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME / "responses" / f"{persona}.last.id"


def _response_path(*, repo_root: Path, persona: str) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME / "responses" / f"{persona}.last.txt"


def _pane_id_for_persona(*, repo_root: Path, persona: str) -> str | None:
    session_path = _session_path(repo_root)
    locked = lock_session_file(session_path)
    try:
        data = locked.read_json() or {}
    finally:
        unlock_session_file(locked)
    pane_id = data.get("personas", {}).get(persona, {}).get("paneId")
    return pane_id if isinstance(pane_id, str) and pane_id else None


def _wait_for_persona_input_ready(
    *, repo_root: Path, persona: str, timeout: float, poll: float
) -> bool:
    deadline = time.time() + timeout
    while True:
        session_path = _session_path(repo_root)
        locked = lock_session_file(session_path)
        try:
            data = locked.read_json() or {}
        finally:
            unlock_session_file(locked)
        ready = data.get("personas", {}).get(persona, {}).get("inputReady") is True
        if ready:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(poll)


def _response_id(*, repo_root: Path, persona: str) -> str:
    path = _response_id_path(repo_root=repo_root, persona=persona)
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _response_mtime(*, repo_root: Path, persona: str) -> float | None:
    path = _response_path(repo_root=repo_root, persona=persona)
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _read_last_response(*, repo_root: Path, persona: str, max_chars: int = 12000) -> str:
    path = _response_path(repo_root=repo_root, persona=persona)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return f"(no saved response for {persona})"

    text = text.strip()
    if not text:
        return f"(no saved response for {persona})"

    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n...(truncated)"


def _parse_marker_matches(*, text: str, marker: str) -> tuple[list[re.Match[str]], str | None]:
    pattern = re.compile(rf"\{{\{{{re.escape(marker)}[:\.]([A-Za-z0-9_-]+)\}}\}}")
    current = text or ""
    matches: list[re.Match[str]] = []
    cursor = 0
    start_token = f"{{{{{marker}"
    while True:
        idx = current.find(start_token, cursor)
        if idx == -1:
            break
        match = pattern.match(current, idx)
        if not match:
            return (
                [],
                f"Invalid {marker} marker syntax; expected {{{{{marker}:persona}}}} "
                f"or {{{{{marker}.persona}}}}.",
            )
        persona = match.group(1)
        if persona not in PERSONAS:
            return [], f"Unrecognized persona '{persona}' in {marker} marker."
        matches.append(match)
        cursor = match.end()
    return matches, None


def _validate_prompt_personas(*, text: str) -> str | None:
    current = text or ""
    for marker in ("agent", "ctx", "last"):
        _, error = _parse_marker_matches(text=current, marker=marker)
        if error:
            return error
    return None


def _extract_ctx_dependencies(*, text: str) -> set[str]:
    current = text or ""
    deps: set[str] = set()
    for marker in ("ctx", "last"):
        matches, error = _parse_marker_matches(text=current, marker=marker)
        if error:
            continue
        for match in matches:
            persona = match.group(1)
            if persona in PERSONAS:
                deps.add(persona)
    return deps


def _expand_last_response_placeholders(*, text: str, repo_root: Path) -> tuple[str, str | None]:
    # Replace {{ctx:pm}} / {{ctx:impl}} / ... with that persona's last response.
    # Keep {{last:...}} as a backward-compatible alias.
    current = text or ""
    for marker in ("ctx", "last"):
        _, error = _parse_marker_matches(text=current, marker=marker)
        if error:
            return current, error

    def _repl(m: re.Match) -> str:
        key = m.group(2)
        if key not in PERSONAS:
            return m.group(0)
        blob = _read_last_response(repo_root=repo_root, persona=key)
        return f"\n\n--- begin {key} last response ---\n{blob}\n--- end {key} last response ---\n\n"

    return re.sub(r"\{\{(ctx|last)[:\.]([A-Za-z0-9_-]+)\}\}", _repl, current), None


def _parse_agent_requests(text: str) -> tuple[str, list[tuple[str, str]], str | None]:
    current = text or ""
    matches, error = _parse_marker_matches(text=current, marker="agent")
    if error:
        return current.strip(), [], error
    if not matches:
        return current.strip(), [], None

    head = current[: matches[0].start()].strip()
    requests: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        persona = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(current)
        segment = current[start:end].strip()
        if not segment:
            continue
        requests.append((persona, segment))
    return head, requests, None


def _run_agent_requests(
    *,
    requests: list[tuple[str, str]],
    repo_root: Path,
    timeout: float,
    poll: float,
    origin_persona: str,
    socket_path: Path,
    ansi: Ansi,
) -> None:
    if os.environ.get("COPILOT_MULTI_AGENT_CALL") == "1":
        return
    if not requests:
        return

    pending: list[_AgentRequest] = []
    deadline = time.time() + timeout
    for idx, (persona, segment) in enumerate(requests):
        deps = _extract_ctx_dependencies(text=segment)
        pending.append(
            _AgentRequest(
                idx=idx,
                persona=persona,
                segment=segment,
                deps=deps,
                deadline=deadline,
            )
        )

    active_personas: set[str] = set()
    last_response_mtime: dict[str, float | None] = {
        req.persona: _response_mtime(repo_root=repo_root, persona=req.persona) for req in pending
    }
    last_response_id: dict[str, str] = {
        req.persona: _response_id(repo_root=repo_root, persona=req.persona) for req in pending
    }

    def _has_blocking_dependency(req: _AgentRequest) -> bool:
        for other in pending:
            if other.idx >= req.idx:
                continue
            if other.persona == req.persona:
                return True
            if other.persona in req.deps:
                return True
        for dep in req.deps:
            if dep in active_personas:
                return True
        return False

    def _dispatch_to_pane(req: _AgentRequest) -> bool:
        pane_id = _pane_id_for_persona(repo_root=repo_root, persona=req.persona)
        if not pane_id:
            _print_err(f"No pane found for persona '{req.persona}'")
            return False
        if req.persona == origin_persona:
            try:
                head = req.segment.strip()
                head, ctx_error = _expand_last_response_placeholders(
                    text=head, repo_root=repo_root
                )
                if ctx_error:
                    _print_err(ctx_error, ansi=ansi)
                    return False
                if head:
                    prompt = f"[{origin_persona}] {head}"
                    resp = _connect_and_send(
                        socket_path=socket_path,
                        payload={"kind": "prompt", "prompt": prompt},
                        show_spinner=True,
                    )
                    if not resp.get("ok"):
                        _print_err(f"Broker error: {resp.get('error')}", ansi=ansi)
                        return False
                    output = resp.get("output") or ""
                    if output:
                        sys.stdout.write(output)
                        if not output.endswith("\n"):
                            sys.stdout.write("\n")
                        sys.stdout.flush()
                last_response_mtime[req.persona] = _response_mtime(
                    repo_root=repo_root, persona=req.persona
                )
                last_response_id[req.persona] = _response_id(
                    repo_root=repo_root, persona=req.persona
                )
            except OSError as e:
                _print_err(f"Broker error: {e}", ansi=ansi)
                _print_err(f"Expected socket at: {socket_path}", ansi=ansi)
                return False
            except json.JSONDecodeError:
                _print_err("Broker returned invalid JSON", ansi=ansi)
                return False
            return True
        if not _wait_for_persona_input_ready(
            repo_root=repo_root, persona=req.persona, timeout=timeout, poll=poll
        ):
            _print_err(f"Timed out waiting for {req.persona} input ready")
            return False
        try:
            send_keys(target=pane_id, command=req.segment.strip())
        except TmuxError as e:
            _print_err(str(e))
            return False
        active_personas.add(req.persona)
        return True

    while pending or active_personas:
        now = time.time()
        for req in list(pending):
            if now >= req.deadline:
                _print_err(f"Timed out waiting to start {req.persona} request")
                pending.remove(req)

        for persona in list(active_personas):
            current_mtime = _response_mtime(repo_root=repo_root, persona=persona)
            current_id = _response_id(repo_root=repo_root, persona=persona)
            before_mtime = last_response_mtime.get(persona)
            before_id = last_response_id.get(persona, "")
            if (
                (current_id and current_id != before_id)
                or (
                    current_mtime is not None
                    and current_mtime != before_mtime
                )
            ):
                active_personas.discard(persona)
                last_response_mtime[persona] = current_mtime
                last_response_id[persona] = current_id

        started_any = False
        for req in list(pending):
            if req.persona in active_personas:
                continue
            if _has_blocking_dependency(req):
                continue
            pending.remove(req)
            if _dispatch_to_pane(req):
                started_any = True

        if not started_any and not active_personas:
            time.sleep(poll)



def _setup_readline_history(*, repo_root: Path, persona: str) -> bool:
    """Best-effort shell-like history (up/down arrows) for `input()`.

    Works when Python has the `readline` module available (common on Linux).
    """

    try:
        import readline  # type: ignore
    except Exception:
        return False

    history_path = _history_path(repo_root=repo_root, persona=persona)
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return True

    try:
        readline.read_history_file(str(history_path))
    except FileNotFoundError:
        pass
    except OSError:
        # Non-fatal: history just won't persist.
        pass

    try:
        readline.set_history_length(2000)
    except Exception:
        pass

    def _save_history() -> None:
        try:
            readline.write_history_file(str(history_path))
        except OSError:
            pass

    atexit.register(_save_history)
    return True


def _set_persona_status(*, repo_root: Path, persona: str, status: str) -> None:
    session_path = _session_path(repo_root)
    locked = lock_session_file(session_path)
    try:
        data = locked.read_json() or {}
        personas = data.setdefault("personas", {})
        persona_data = personas.setdefault(persona, {})
        persona_data["status"] = status
        persona_data["updatedAt"] = utc_now_iso()
        locked.write_json(data)
    finally:
        unlock_session_file(locked)


def _set_persona_input_ready(*, repo_root: Path, persona: str, ready: bool) -> None:
    session_path = _session_path(repo_root)
    locked = lock_session_file(session_path)
    try:
        data = locked.read_json() or {}
        personas = data.setdefault("personas", {})
        persona_data = personas.setdefault(persona, {})
        persona_data["inputReady"] = ready
        persona_data["updatedAt"] = utc_now_iso()
        locked.write_json(data)
    finally:
        unlock_session_file(locked)


def _safe_set_persona_input_ready(*, repo_root: Path, persona: str, ready: bool) -> None:
    try:
        _set_persona_input_ready(repo_root=repo_root, persona=persona, ready=ready)
    except OSError:
        pass


def _translate_coordination_alias(argv: list[str]) -> list[str] | None:
    """Translate friendly coordination aliases to `copilot-multi ...` commands.

    We do this because commands like `copilot-wait` are easy to confuse with
    prompts intended for the GitHub Copilot CLI. In the pane REPL, these aliases
    should always run locally.

    Supported forms (examples):
    - copilot-wait --status idle pm
    - copilot-wait pm --status idle
    - copilot-status
    - copilot-set-status pm working --message "..."
    """

    if not argv:
        return None

    cmd = argv[0]
    mapping = {
        "copilot-wait": "wait",
        "copilot-status": "status",
        "copilot-set-status": "set-status",
    }
    if cmd not in mapping:
        return None

    subcmd = mapping[cmd]
    rest = argv[1:]

    # For commands that target a persona, accept the persona anywhere (common
    # pattern is putting it last).
    persona = None
    if subcmd in {"wait", "set-status"}:
        for i, token in enumerate(rest):
            if token in PERSONAS:
                persona = token
                rest = rest[:i] + rest[i + 1 :]
                break

        if persona is None:
            # Let the underlying command print usage.
            return ["copilot-multi", subcmd, *rest]

        return ["copilot-multi", subcmd, persona, *rest]

    return ["copilot-multi", subcmd, *rest]


def _translate_gt_shortcut(line: str) -> list[str] | None:
    """Translate a leading '>' shortcut line into a local argv.

    Examples:
    - >status                      => copilot-multi status
    - >set-status pm working       => copilot-multi set-status pm working
    - >wait pm --status done       => copilot-multi wait pm --status done
    - >waitfor pm                  => copilot-multi wait pm --status idle
    """

    raw = (line or "").lstrip()
    if not raw.startswith(">"):
        return None

    tail = raw[1:].strip()
    if not tail:
        return ["copilot-multi"]

    try:
        argv = shlex.split(tail)
    except ValueError as e:
        _print_err(f"Parse error: {e}")
        return []

    if not argv:
        return ["copilot-multi"]

    head = argv[0]
    if head in {"waitfor", "wait-for"}:
        persona = argv[1] if len(argv) > 1 else ""
        rest = argv[2:]
        return ["copilot-multi", "wait", persona, "--status", "idle", *rest]

    return ["copilot-multi", *argv]


def _split_then(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split an argv list on `--` into (head, tail).

    Example:
      ["copilot-multi","wait","pm","--status","idle","--","explain","x"]
        -> (["copilot-multi","wait","pm","--status","idle"], ["explain","x"])
    """

    if "--" not in argv:
        return argv, []
    idx = argv.index("--")
    return argv[:idx], argv[idx + 1 :]


def _tokens_to_line(tokens: list[str]) -> str:
    if not tokens:
        return ""
    try:
        return shlex.join(tokens)
    except Exception:
        return " ".join(tokens)


def _run_followup_after_wait(
    *,
    follow_tokens: list[str],
    persona: str,
    socket_path: Path,
    repo_root: Path,
    ansi: Ansi | None,
) -> None:
    """Run a follow-up after a local wait completes.

    The follow-up can be:
    - another local shortcut (starts with '>')
    - a local coordination command (copilot-multi/copilot-wait/etc)
    - otherwise treated as a Copilot prompt line
    """

    follow_line = _tokens_to_line(follow_tokens).strip()
    if not follow_line:
        return

    if follow_line.startswith(">"):
        gt = _translate_gt_shortcut(follow_line)
        if not gt or gt == []:
            return
        try:
            rendered = shlex.join(gt)
        except Exception:
            rendered = " ".join(gt)
        _print_local(rendered, ansi=ansi)
        subprocess.run(gt, text=True)
        return

    if (
        follow_line.startswith("copilot-multi ")
        or follow_line == "copilot-multi"
        or follow_line.startswith("copilot-wait")
        or follow_line.startswith("copilot-status")
        or follow_line.startswith("copilot-set-status")
    ):
        try:
            argv = shlex.split(follow_line)
        except ValueError as e:
            _print_err(f"Parse error: {e}", ansi=ansi)
            return

        translated = _translate_coordination_alias(argv)
        if translated is not None:
            argv = translated

        try:
            rendered = shlex.join(argv)
        except Exception:
            rendered = " ".join(argv)
        _print_local(rendered, ansi=ansi)
        subprocess.run(argv, text=True)
        return

    # Default: treat as a Copilot prompt line.
    try:
        _set_persona_status(repo_root=repo_root, persona=persona, status="working")
    except OSError:
        pass

    try:
        persona_error = _validate_prompt_personas(text=follow_line)
        if persona_error:
            _print_err(persona_error, ansi=ansi)
            return
        head, requests, parse_error = _parse_agent_requests(follow_line)
        if parse_error:
            _print_err(parse_error, ansi=ansi)
            return
        head, ctx_error = _expand_last_response_placeholders(text=head, repo_root=repo_root)
        if ctx_error:
            _print_err(ctx_error, ansi=ansi)
            return
        resp = None
        if head:
            resp = _connect_and_send(
                socket_path=socket_path,
                payload={"kind": "prompt", "prompt": f"[{persona}] {head}"},
                show_spinner=True,
            )
    except OSError as e:
        _print_err(f"Broker error: {e}", ansi=ansi)
        _print_err(f"Expected socket at: {socket_path}", ansi=ansi)
        return
    except json.JSONDecodeError:
        _print_err("Broker returned invalid JSON", ansi=ansi)
        return
    finally:
        try:
            _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
        except OSError:
            pass

    if resp is not None and not resp.get("ok"):
        _print_err(f"Broker error: {resp.get('error')}", ansi=ansi)
        return

    if resp is not None:
        output = resp.get("output") or ""
        if output:
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()

    _run_agent_requests(
        requests=requests,
        repo_root=repo_root,
        timeout=120.0,
        poll=0.5,
        origin_persona=persona,
        socket_path=socket_path,
        ansi=ansi,
    )


def repl(*, persona: str, socket_path: Path, repo_root: Path) -> int:
    # Ensure we're in repo root for readline history and other file operations
    os.chdir(repo_root)

    has_readline = _setup_readline_history(repo_root=repo_root, persona=persona)
    ui = UiConfig.load(repo_root=repo_root)
    ansi = Ansi(theme=ui.theme, use_readline_markers=has_readline)
    
    # After readline is setup, optionally switch to persona directory if it exists
    # This allows per-persona AGENTS.md to be loaded by Copilot while keeping
    # readline history and other functionality working correctly
    persona_dir = repo_root / ".copilot-persona-dirs" / persona
    if persona_dir.exists() and persona_dir.is_dir():
        os.chdir(persona_dir)

    prompt_prefix = ansi.input_prompt(ansi.prompt(persona))

    display_name = PERSONAS.get(persona, persona)
    print(ansi.header_line(f"=== Copilot Multi Persona: {display_name} ==="))
    print(ansi.tip_line("Starting Copilot router..."))
    print(ansi.tip_line("Tmux tip: use Ctrl-b o (or Ctrl-b + arrows) to switch panes"))
    print(ansi.tip_line("Tmux tip: Ctrl-b q shows pane numbers"))
    print(ansi.header_line("=== Copilot Multi Persona REPL ==="))
    print(f"Persona: {persona}")
    print(f"Repo: {repo_root}")
    print(
        ansi.italic_line(
            "Tmux: copilot-multi uses 1 window with 4 panes (not multiple windows)."
        )
    )
    print(ansi.italic_line("Tmux: switch panes with Ctrl-b o, or Ctrl-b then arrow keys."))
    print(ansi.italic_line("Tmux: show pane numbers with Ctrl-b q, then press a number."))
    print(ansi.italic_line("Type anything to send to Copilot CLI."))
    print(ansi.italic_line("Commands starting with 'copilot-multi ' run locally."))
    print(
        ansi.italic_line("Shortcuts: copilot-wait/copilot-status/copilot-set-status run locally.")
    )
    print(
        ansi.italic_line(
            "Shortcuts: '>...' runs 'copilot-multi ...' locally (e.g. >status, >waitfor pm)."
        )
    )
    print(ansi.italic_line("Tip: chain after waits with: >waitfor pm -- <prompt or command>"))
    print(
        ansi.italic_line(
            "Tip: include another pane's context with: {{ctx:impl}} (pm/impl/review/docs)"
        )
    )
    print(ansi.italic_line("Tip: use Up/Down arrows for history."))
    print(ansi.italic_line("Type 'exit' to close this pane."))
    print()
    while True:
        try:
            _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=True)
            line = input(prompt_prefix)
            _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=False)
            if line and ansi.input_reset():
                sys.stdout.write(ansi.input_reset())
                sys.stdout.flush()
        except EOFError:
            _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=False)
            return 0
        except KeyboardInterrupt:
            _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=True)
            print()
            continue

        line = line.strip()
        if not line:
            continue

        if line in {"exit", "quit"}:
            _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=False)
            return 0

        gt = _translate_gt_shortcut(line)
        if gt is not None:
            if gt == []:
                continue
            argv, then_tokens = _split_then(gt)

            # Make it obvious this is a local command (not a Copilot prompt).
            try:
                rendered = shlex.join(argv)
            except Exception:
                rendered = " ".join(argv)
            _print_local(rendered, ansi=ansi)

            subcmd = argv[1] if len(argv) > 1 else ""
            if subcmd == "wait":
                try:
                    _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=False)
                    _set_persona_status(repo_root=repo_root, persona=persona, status="waiting")
                except OSError:
                    pass
                try:
                    proc = subprocess.run(argv, text=True)
                    _ = proc.returncode
                finally:
                    try:
                        _safe_set_persona_input_ready(
                            repo_root=repo_root, persona=persona, ready=True
                        )
                        _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
                    except OSError:
                        pass

                _run_followup_after_wait(
                    follow_tokens=then_tokens,
                    persona=persona,
                    socket_path=socket_path,
                    repo_root=repo_root,
                    ansi=ansi,
                )
                continue

            proc = subprocess.run(argv, text=True)
            _ = proc.returncode
            continue

        if (
            line.startswith("copilot-multi ")
            or line == "copilot-multi"
            or line.startswith("copilot-wait")
            or line.startswith("copilot-status")
            or line.startswith("copilot-set-status")
        ):
            try:
                argv = shlex.split(line)
            except ValueError as e:
                _print_err(f"Parse error: {e}", ansi=ansi)
                continue

            translated = _translate_coordination_alias(argv)
            if translated is not None:
                argv = translated

            argv, then_tokens = _split_then(argv)

            try:
                rendered = shlex.join(argv)
            except Exception:
                rendered = " ".join(argv)
            _print_local(rendered, ansi=ansi)

            subcmd = argv[1] if len(argv) > 1 else ""
            if subcmd == "wait":
                try:
                    _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=False)
                    _set_persona_status(repo_root=repo_root, persona=persona, status="waiting")
                except OSError:
                    pass
                try:
                    proc = subprocess.run(argv, text=True)
                    _ = proc.returncode
                finally:
                    try:
                        _safe_set_persona_input_ready(
                            repo_root=repo_root, persona=persona, ready=True
                        )
                        _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
                    except OSError:
                        pass

                _run_followup_after_wait(
                    follow_tokens=then_tokens,
                    persona=persona,
                    socket_path=socket_path,
                    repo_root=repo_root,
                    ansi=ansi,
                )
                continue

            proc = subprocess.run(argv, text=True)
            _ = proc.returncode
            continue

        try:
            try:
                _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=False)
                _set_persona_status(repo_root=repo_root, persona=persona, status="working")
            except OSError:
                pass

            persona_error = _validate_prompt_personas(text=line)
            if persona_error:
                _print_err(persona_error, ansi=ansi)
                continue
            head, requests, parse_error = _parse_agent_requests(line)
            if parse_error:
                _print_err(parse_error, ansi=ansi)
                continue
            head, ctx_error = _expand_last_response_placeholders(text=head, repo_root=repo_root)
            if ctx_error:
                _print_err(ctx_error, ansi=ansi)
                continue
            resp = None
            if head:
                prompt = f"[{persona}] {head}"
                resp = _connect_and_send(
                    socket_path=socket_path,
                    payload={"kind": "prompt", "prompt": prompt},
                    show_spinner=True,
                )
        except OSError as e:
            _print_err(f"Broker error: {e}", ansi=ansi)
            _print_err(f"Expected socket at: {socket_path}", ansi=ansi)
            continue
        except json.JSONDecodeError:
            _print_err("Broker returned invalid JSON", ansi=ansi)
            continue
        finally:
            try:
                _safe_set_persona_input_ready(repo_root=repo_root, persona=persona, ready=True)
                _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
            except OSError:
                pass

        if resp is not None and not resp.get("ok"):
            _print_err(f"Broker error: {resp.get('error')}", ansi=ansi)
            continue

        if resp is not None:
            output = resp.get("output") or ""
            # Print exactly what Copilot printed.
            if output:
                sys.stdout.write(output)
                if not output.endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()

        _run_agent_requests(
            requests=requests,
            repo_root=repo_root,
            timeout=120.0,
            poll=0.5,
            origin_persona=persona,
            socket_path=socket_path,
            ansi=ansi,
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copilot-multi-pane")
    p.add_argument("--persona", required=True, help="Persona key (pm/impl/review/docs)")
    p.add_argument("--socket", required=True, help="Broker Unix socket path")
    p.add_argument("--repo-root", required=True, help="Repo root directory")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return repl(persona=args.persona, socket_path=Path(args.socket), repo_root=Path(args.repo_root))


if __name__ == "__main__":
    raise SystemExit(main())
