"""The per-repository kernel lock `<repo>/.ai/kernel.lock` (ARCHITECTURE §3.1; E01-S30).

A non-blocking exclusive OS lock: `msvcrt.locking` on Windows, `fcntl.flock` elsewhere. The
lock dies with its process, so a file left by a crashed kernel never blocks. The file holds
the holder's JSON (pid, kernel instance, start time); on Windows the locked byte lies past
that text so other processes can still read who holds the lock.
"""

import json
import os
import sys
from pathlib import Path
from typing import IO, Final, Self

from walk.common.clock import Clock, SystemClock
from walk.common.models import JsonDict
from walk.persistence.errors import KernelLockHeld

LOCK_FILE_NAME = "kernel.lock"

# Windows locks byte ranges; locking past end-of-file is allowed and keeps the holder JSON
# (written from offset 0) readable for a second process that wants to name the holder.
_LOCKED_OFFSET: Final = 1 << 20
_LOCKED_BYTES: Final = 1


class KernelLock:
    """Exclusive lock of one kernel process on one game repository."""

    def __init__(self, ai_root: Path, *, kernel_instance: str, clock: Clock | None = None) -> None:
        """Bind to ``<ai_root>/kernel.lock`` (not acquired yet).

        Args:
            ai_root: The repository's `.ai/` folder (created on acquire when missing).
            kernel_instance: Instance id written into the lock file.
            clock: Stamps ``started_at`` (the system clock by default).
        """
        self._path = ai_root / LOCK_FILE_NAME
        self._kernel_instance = kernel_instance
        self._clock: Clock = clock or SystemClock()
        self._handle: IO[bytes] | None = None

    def acquire(self) -> None:
        """Take the lock without blocking and write the holder JSON.

        Raises:
            KernelLockHeld: Another live process (or another `KernelLock`) holds it; ``detail``
                names the holder's pid, kernel instance and start time when readable.
        """
        if self._handle is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        try:
            _lock(handle)
        except OSError as exc:
            handle.close()
            holder = _read_holder(self._path)
            pid = holder.get("pid", "unknown")
            msg = f"kernel already running (pid {pid})"
            raise KernelLockHeld(msg, detail=holder) from exc
        holder_json: JsonDict = {
            "pid": os.getpid(),
            "kernel_instance": self._kernel_instance,
            "started_at": self._clock.now().isoformat(),
        }
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(holder_json).encode("utf-8"))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        """Release the lock; safe to call when not held."""
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> Self:
        """Acquire on entry."""
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        """Release on exit."""
        self.release()

    @staticmethod
    def is_held(ai_root: Path) -> bool:
        """Whether a live process holds the lock (probes without keeping it)."""
        if not (ai_root / LOCK_FILE_NAME).is_file():
            return False
        handle = (ai_root / LOCK_FILE_NAME).open("a+b")
        try:
            _lock(handle)
        except OSError:
            return True
        else:
            _unlock(handle)
            return False
        finally:
            handle.close()


def _read_holder(path: Path) -> JsonDict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


if sys.platform == "win32":
    import msvcrt

    def _lock(handle: IO[bytes]) -> None:
        handle.seek(_LOCKED_OFFSET)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, _LOCKED_BYTES)

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(_LOCKED_OFFSET)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, _LOCKED_BYTES)

else:  # pragma: no cover - the gate runs on Windows; POSIX uses advisory flock
    import fcntl

    def _lock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
