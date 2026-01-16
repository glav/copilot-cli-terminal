import argparse
import json
import os
import signal
import socket
import socketserver
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrokerConfig:
    socket_path: Path
    repo_root: Path
    copilot_config_dir: Path
    pid_file: Path
    session_marker_file: Path


class BrokerError(RuntimeError):
    pass


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copilot_env(config_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    # Rely on `copilot --config-dir ...` to select the active Copilot directory.
    # Overriding XDG_* can cause Copilot CLI to look in a different location and
    # appear unauthenticated even when the config dir is valid.
    return env


def _run_copilot_prompt(*, prompt: str, cfg: BrokerConfig, lock: threading.Lock) -> tuple[int, str]:
    # Ensure prompts are serialized so we don't corrupt Copilot state or overlap.
    with lock:
        cmd = [
            "copilot",
            "--config-dir",
            str(cfg.copilot_config_dir),
            "--add-dir",
            str(cfg.repo_root),
            "-p",
            prompt,
        ]

        # Once we've successfully created a session, follow-up prompts should
        # continue that same session.
        use_continue = cfg.session_marker_file.exists()
        if use_continue:
            cmd.insert(1, "--continue")

        proc = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            env=_copilot_env(cfg.copilot_config_dir),
            text=True,
            capture_output=True,
            check=False,
        )

        combined = (proc.stdout or "") + (proc.stderr or "")

        # If we attempted --continue but Copilot reports there is nothing to
        # continue, retry once without --continue and clear the marker.
        if use_continue and proc.returncode != 0:
            msg = combined.lower()
            if "session" in msg and "continue" in msg and ("no" in msg or "not" in msg):
                try:
                    cfg.session_marker_file.unlink()
                except OSError:
                    pass

                retry_cmd = [
                    "copilot",
                    "--config-dir",
                    str(cfg.copilot_config_dir),
                    "--add-dir",
                    str(cfg.repo_root),
                    "-p",
                    prompt,
                ]
                proc = subprocess.run(
                    retry_cmd,
                    cwd=str(cfg.repo_root),
                    env=_copilot_env(cfg.copilot_config_dir),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                combined = (proc.stdout or "") + (proc.stderr or "")

        # Mark session as started only on success.
        if proc.returncode == 0 and not cfg.session_marker_file.exists():
            try:
                cfg.session_marker_file.write_text("started\n", encoding="utf-8")
            except OSError:
                pass

        return proc.returncode, combined


class _UnixJSONLineHandler(socketserver.StreamRequestHandler):
    # Assigned by server init.
    broker_cfg: BrokerConfig
    copilot_lock: threading.Lock

    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return

        try:
            req = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json({"ok": False, "error": "invalid_json"})
            return

        if not isinstance(req, dict):
            self._write_json({"ok": False, "error": "invalid_request"})
            return

        kind = req.get("kind")
        if kind == "ping":
            self._write_json({"ok": True, "kind": "pong"})
            return

        if kind == "info":
            self._write_json(
                {
                    "ok": True,
                    "kind": "info",
                    "repoRoot": str(self.broker_cfg.repo_root),
                    "copilotConfigDir": str(self.broker_cfg.copilot_config_dir),
                }
            )
            return

        if kind != "prompt":
            self._write_json({"ok": False, "error": "unknown_kind"})
            return

        prompt = req.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            self._write_json({"ok": False, "error": "empty_prompt"})
            return

        code, output = _run_copilot_prompt(
            prompt=prompt,
            cfg=self.broker_cfg,
            lock=self.copilot_lock,
        )
        self._write_json({"ok": True, "exitCode": code, "output": output})

    def _write_json(self, payload: dict) -> None:
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.wfile.write(raw)
        self.wfile.flush()


class _ThreadedUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def _write_pid(pid_file: Path) -> None:
    try:
        pid_file.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    except OSError as e:
        raise BrokerError(f"Failed to write pid file: {pid_file}") from e


def _remove_socket(socket_path: Path) -> None:
    try:
        if socket_path.exists():
            socket_path.unlink()
    except OSError:
        pass


def _is_broker_responsive(socket_path: Path, timeout_seconds: float = 0.2) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_seconds)
            s.connect(str(socket_path))
            s.sendall(b'{"kind":"ping"}\n')
            data = s.recv(2048)
            return b"pong" in data
    except OSError:
        return False


def run_server(cfg: BrokerConfig) -> int:
    _ensure_dir(cfg.socket_path.parent)
    _ensure_dir(cfg.copilot_config_dir)

    # Refuse to start if another broker is already active on the socket.
    if cfg.socket_path.exists() and _is_broker_responsive(cfg.socket_path):
        raise BrokerError(f"Broker already running at {cfg.socket_path}")

    _remove_socket(cfg.socket_path)

    copilot_lock = threading.Lock()

    handler_cls = _UnixJSONLineHandler
    server = _ThreadedUnixServer(str(cfg.socket_path), handler_cls)
    server.RequestHandlerClass.broker_cfg = cfg
    server.RequestHandlerClass.copilot_lock = copilot_lock

    def _shutdown(*_args):
        try:
            server.shutdown()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    _write_pid(cfg.pid_file)

    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        _remove_socket(cfg.socket_path)
        try:
            cfg.pid_file.unlink()
        except OSError:
            pass

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copilot-multi-broker")
    p.add_argument("--socket", required=True, help="Path to the broker Unix socket")
    p.add_argument("--repo-root", required=True, help="Repo root cwd for copilot runs")
    p.add_argument(
        "--copilot-config-dir",
        required=True,
        help="Directory used for Copilot CLI config+state (XDG_CONFIG_HOME/XDG_STATE_HOME)",
    )
    p.add_argument("--pid-file", required=True, help="PID file path")
    p.add_argument(
        "--session-marker-file",
        required=True,
        help="Marker file used to decide when to add --continue",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cfg = BrokerConfig(
        socket_path=Path(args.socket),
        repo_root=Path(args.repo_root),
        copilot_config_dir=Path(args.copilot_config_dir),
        pid_file=Path(args.pid_file),
        session_marker_file=Path(args.session_marker_file),
    )

    try:
        return run_server(cfg)
    except BrokerError as e:
        raise SystemExit(str(e)) from e


if __name__ == "__main__":
    raise SystemExit(main())
