import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
from pathlib import Path


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


def repl(*, persona: str, socket_path: Path, repo_root: Path) -> int:
    os.chdir(repo_root)

    prompt_prefix = f"{persona}> "

    print("=== Copilot Multi Persona REPL ===")
    print(f"Persona: {persona}")
    print(f"Repo: {repo_root}")
    print("Type anything to send to Copilot CLI.")
    print("Commands starting with 'copilot-multi ' run locally.")
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

        if line.startswith("copilot-multi ") or line == "copilot-multi":
            _run_local_command(line)
            continue

        try:
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
