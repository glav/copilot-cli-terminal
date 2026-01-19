import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class LockedSession:
    file_path: Path
    lock_fd: int

    def _lock_path(self) -> Path:
        return self.file_path.with_name(self.file_path.name + ".lock")

    def read_json(self) -> dict:
        if not self.file_path.exists():
            return {}

        raw = self.file_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            corrupt_name = self.file_path.name + ".corrupt-" + utc_now_iso().replace(":", "")
            corrupt_path = self.file_path.with_name(corrupt_name)
            try:
                os.replace(self.file_path, corrupt_path)
            except OSError:
                pass
            return {}

    def write_json(self, data: dict) -> None:
        raw = json.dumps(data, indent=2, sort_keys=True) + "\n"
        ensure_dir(self.file_path.parent)
        tmp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.file_path.parent),
                prefix=self.file_path.name + ".tmp.",
                delete=False,
            ) as fp:
                tmp_path = fp.name
                fp.write(raw)
                fp.flush()
                os.fsync(fp.fileno())

            os.replace(tmp_path, self.file_path)

            try:
                dir_fd = os.open(self.file_path.parent, os.O_DIRECTORY)
            except OSError:
                dir_fd = None

            if dir_fd is not None:
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def close(self) -> None:
        try:
            os.close(self.lock_fd)
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
    lock_path = file_path.with_name(file_path.name + ".lock")
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    return LockedSession(file_path=file_path, lock_fd=lock_fd)


def unlock_session_file(locked: LockedSession) -> None:
    import fcntl

    try:
        fcntl.flock(locked.lock_fd, fcntl.LOCK_UN)
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
