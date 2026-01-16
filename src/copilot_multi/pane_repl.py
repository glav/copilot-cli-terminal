import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
from pathlib import Path

import atexit

from copilot_multi.constants import (
    DEFAULT_SESSION_FILE_NAME,
    DEFAULT_SHARED_DIR_NAME,
    PERSONAS,
)
from copilot_multi.session_store import lock_session_file, unlock_session_file, utc_now_iso


def _connect_and_send(*, socket_path: Path, payload: dict) -> dict:
    raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
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

    joined = b"".join(chunks)
    line = joined.split(b"\n", 1)[0]
    return json.loads(line.decode("utf-8"))


def _run_local_command(command_line: str) -> int:
    try:
        argv = shlex.split(command_line)
    except ValueError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 2

    if not argv:
        return 0

    proc = subprocess.run(argv, text=True)
    return int(proc.returncode)


def _session_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME / DEFAULT_SESSION_FILE_NAME


def _history_path(*, repo_root: Path, persona: str) -> Path:
    return repo_root / DEFAULT_SHARED_DIR_NAME / "history" / f"{persona}.txt"


def _setup_readline_history(*, repo_root: Path, persona: str) -> None:
    """Best-effort shell-like history (up/down arrows) for `input()`.

    Works when Python has the `readline` module available (common on Linux).
    """

    try:
        import readline  # type: ignore
    except Exception:
        return

    history_path = _history_path(repo_root=repo_root, persona=persona)
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

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
        print(f"Parse error: {e}", file=sys.stderr)
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
        print(f"(local) {rendered}")
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
            print(f"Parse error: {e}", file=sys.stderr)
            return

        translated = _translate_coordination_alias(argv)
        if translated is not None:
            argv = translated

        try:
            rendered = shlex.join(argv)
        except Exception:
            rendered = " ".join(argv)
        print(f"(local) {rendered}")
        subprocess.run(argv, text=True)
        return

    # Default: treat as a Copilot prompt line.
    try:
        _set_persona_status(repo_root=repo_root, persona=persona, status="working")
    except OSError:
        pass

    try:
        resp = _connect_and_send(
            socket_path=socket_path,
            payload={"kind": "prompt", "prompt": f"[{persona}] {follow_line}"},
        )
    except OSError as e:
        print(f"Broker error: {e}", file=sys.stderr)
        print(f"Expected socket at: {socket_path}", file=sys.stderr)
        return
    except json.JSONDecodeError:
        print("Broker returned invalid JSON", file=sys.stderr)
        return
    finally:
        try:
            _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
        except OSError:
            pass

    if not resp.get("ok"):
        print(f"Broker error: {resp.get('error')}", file=sys.stderr)
        return

    output = resp.get("output") or ""
    if output:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()


def repl(*, persona: str, socket_path: Path, repo_root: Path) -> int:
    os.chdir(repo_root)

    _setup_readline_history(repo_root=repo_root, persona=persona)

    prompt_prefix = f"{persona}> "

    print("=== Copilot Multi Persona REPL ===")
    print(f"Persona: {persona}")
    print(f"Repo: {repo_root}")
    print("Tmux: copilot-multi uses 1 window with 4 panes (not multiple windows).")
    print("Tmux: switch panes with Ctrl-b o, or Ctrl-b then arrow keys.")
    print("Tmux: show pane numbers with Ctrl-b q, then press a number.")
    print("Type anything to send to Copilot CLI.")
    print("Commands starting with 'copilot-multi ' run locally.")
    print("Shortcuts: copilot-wait/copilot-status/copilot-set-status run locally.")
    print("Shortcuts: '>...' runs 'copilot-multi ...' locally (e.g. >status, >waitfor pm).")
    print("Tip: chain after waits with: >waitfor pm -- <prompt or command>")
    print("Tip: use Up/Down arrows for history.")
    print("Type 'exit' to close this pane.")
    print()

    while True:
        try:
            line = input(prompt_prefix)
        except EOFError:
            return 0
        except KeyboardInterrupt:
            print()
            continue

        line = line.strip()
        if not line:
            continue

        if line in {"exit", "quit"}:
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
            print(f"(local) {rendered}")

            subcmd = argv[1] if len(argv) > 1 else ""
            if subcmd == "wait":
                try:
                    _set_persona_status(repo_root=repo_root, persona=persona, status="waiting")
                except OSError:
                    pass
                try:
                    proc = subprocess.run(argv, text=True)
                    _ = proc.returncode
                finally:
                    try:
                        _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
                    except OSError:
                        pass

                _run_followup_after_wait(
                    follow_tokens=then_tokens,
                    persona=persona,
                    socket_path=socket_path,
                    repo_root=repo_root,
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
                print(f"Parse error: {e}", file=sys.stderr)
                continue

            translated = _translate_coordination_alias(argv)
            if translated is not None:
                argv = translated

            argv, then_tokens = _split_then(argv)

            try:
                rendered = shlex.join(argv)
            except Exception:
                rendered = " ".join(argv)
            print(f"(local) {rendered}")

            subcmd = argv[1] if len(argv) > 1 else ""
            if subcmd == "wait":
                try:
                    _set_persona_status(repo_root=repo_root, persona=persona, status="waiting")
                except OSError:
                    pass
                try:
                    proc = subprocess.run(argv, text=True)
                    _ = proc.returncode
                finally:
                    try:
                        _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
                    except OSError:
                        pass

                _run_followup_after_wait(
                    follow_tokens=then_tokens,
                    persona=persona,
                    socket_path=socket_path,
                    repo_root=repo_root,
                )
                continue

            proc = subprocess.run(argv, text=True)
            _ = proc.returncode
            continue

        try:
            try:
                _set_persona_status(repo_root=repo_root, persona=persona, status="working")
            except OSError:
                pass

            prompt = f"[{persona}] {line}"
            resp = _connect_and_send(
                socket_path=socket_path,
                payload={"kind": "prompt", "prompt": prompt},
            )
        except OSError as e:
            print(f"Broker error: {e}", file=sys.stderr)
            print(f"Expected socket at: {socket_path}", file=sys.stderr)
            continue
        except json.JSONDecodeError:
            print("Broker returned invalid JSON", file=sys.stderr)
            continue
        finally:
            try:
                _set_persona_status(repo_root=repo_root, persona=persona, status="idle")
            except OSError:
                pass

        if not resp.get("ok"):
            print(f"Broker error: {resp.get('error')}", file=sys.stderr)
            continue

        output = resp.get("output") or ""
        # Print exactly what Copilot printed.
        if output:
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()

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
