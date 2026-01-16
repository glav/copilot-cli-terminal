import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class LockedSession:
    file_path: Path
    fd: int

    def read_json(self) -> dict:
        with os.fdopen(os.dup(self.fd), "r", encoding="utf-8") as fp:
            fp.seek(0)
            raw = fp.read().strip()
            if not raw:
                return {}
            return json.loads(raw)

    def write_json(self, data: dict) -> None:
        raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
        with os.fdopen(os.dup(self.fd), "r+", encoding="utf-8") as fp:
            fp.seek(0)
            fp.truncate(0)
            fp.write(raw)
            fp.flush()
            os.fsync(fp.fileno())

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def lock_session_file(file_path: Path) -> LockedSession:
    # Linux-only MVP: use fcntl.flock for cross-process mutual exclusion.
    import fcntl

    ensure_dir(file_path.parent)
    fd = os.open(file_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return LockedSession(file_path=file_path, fd=fd)


def unlock_session_file(locked: LockedSession) -> None:
    import fcntl

    try:
        fcntl.flock(locked.fd, fcntl.LOCK_UN)
    finally:
        locked.close()


def wait_for_predicate(
    *,
    session_path: Path,
    predicate,
    timeout_seconds: float | None,
    poll_interval_seconds: float,
) -> bool:
    start = time.time()
    while True:
        locked = lock_session_file(session_path)
        try:
            data = locked.read_json()
            if predicate(data):
                return True
        finally:
            unlock_session_file(locked)

        if timeout_seconds is not None and (time.time() - start) >= timeout_seconds:
            return False

        time.sleep(poll_interval_seconds)
