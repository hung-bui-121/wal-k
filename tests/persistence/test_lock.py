import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.persistence import LOCK_FILE_NAME, KernelLock, KernelLockHeld

PROBE = (
    "import sys\n"
    "from pathlib import Path\n"
    "from walk.persistence import KernelLock, KernelLockHeld\n"
    "lock = KernelLock(Path(sys.argv[1]), kernel_instance='probe')\n"
    "try:\n"
    "    lock.acquire()\n"
    "except KernelLockHeld as exc:\n"
    "    print('held', exc.detail.get('pid'), exc.detail.get('kernel_instance'))\n"
    "else:\n"
    "    print('acquired')\n"
    "    lock.release()\n"
)


def _probe(ai_root: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-c", PROBE, str(ai_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def test_lock_is_exclusive_across_processes(tmp_path: Path, fake_clock: FakeClock) -> None:
    ai_root = tmp_path / ".ai"
    lock = KernelLock(ai_root, kernel_instance="kernel-1", clock=fake_clock)

    lock.acquire()
    try:
        held = _probe(ai_root)
        holder = json.loads((ai_root / LOCK_FILE_NAME).read_text(encoding="utf-8"))
    finally:
        lock.release()
    acquired = _probe(ai_root)

    assert held == f"held {os.getpid()} kernel-1"
    assert holder == {
        "pid": os.getpid(),
        "kernel_instance": "kernel-1",
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    assert acquired == "acquired"


def test_stale_lock_file_does_not_block(tmp_path: Path) -> None:
    ai_root = tmp_path / ".ai"
    assert _probe(ai_root) == "acquired"  # a process took the lock and exited
    (ai_root / LOCK_FILE_NAME).write_text('{"pid": 999999, "kernel_instance": "dead"}', "utf-8")

    with KernelLock(ai_root, kernel_instance="kernel-2") as lock:
        assert KernelLock.is_held(ai_root) is True
        lock.acquire()  # already held by this lock: no-op

    assert KernelLock.is_held(ai_root) is False


def test_second_lock_in_one_process_is_refused(tmp_path: Path) -> None:
    ai_root = tmp_path / ".ai"
    assert KernelLock.is_held(ai_root) is False
    first = KernelLock(ai_root, kernel_instance="kernel-1")
    first.acquire()
    try:
        with pytest.raises(KernelLockHeld, match="kernel already running") as caught:
            KernelLock(ai_root, kernel_instance="kernel-2").acquire()
        assert caught.value.detail["kernel_instance"] == "kernel-1"
        (ai_root / LOCK_FILE_NAME).write_text("not json", "utf-8")
        with pytest.raises(KernelLockHeld, match="pid unknown") as unreadable:
            KernelLock(ai_root, kernel_instance="kernel-3").acquire()
        assert unreadable.value.detail == {}
    finally:
        first.release()
        first.release()
