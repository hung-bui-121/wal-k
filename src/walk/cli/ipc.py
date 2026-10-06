"""CLI side of the SQLite command channel (ADR-0009 D-3; E01-S30).

A mutating command goes to the daemon when one holds the kernel lock: the CLI inserts a
`commands` row and polls `command_results`. Without a daemon it runs in-process under the lock
(ARCHITECTURE §3.1 offline-safe commands). The CLI never holds a write transaction while it
waits for a result.
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Final

from walk.cli.composition import KernelHandle, KernelSettings, build_kernel, open_database
from walk.common.clock import Clock, SystemClock
from walk.common.errors import GuardRejected, PermissionDenied, Timeout, WalkError
from walk.common.models import JsonDict
from walk.orchestrator import CommandResult
from walk.persistence import Database, KernelLock, UnitOfWork

COMMAND_POLL_INTERVAL_S = 0.25  # ADR-0009 D-3

_AI_DIR: Final = ".ai"
_EXIT_CODE_KEY: Final = "exit_code"
_EXIT_ERROR: Final = 1
_EXIT_REJECTED: Final = 2
_IN_PROCESS_COMMAND_ID: Final = 0


class CommandClient:
    """Submits commands to the daemon and waits for their results."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        timeout_s: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Wire the client.

        Args:
            db: The project database the daemon consumes.
            clock: Stamps ``requested_at``.
            timeout_s: How long `wait` polls before giving up.
            sleep: Awaited between polls.
        """
        self._db = db
        self._clock = clock
        self._timeout_s = timeout_s
        self._sleep = sleep

    async def submit(self, name: str, args: JsonDict, *, requested_by: str = "USER") -> int:
        """Insert a PENDING command; return its id."""
        async with UnitOfWork(self._db) as uow:
            cursor = uow.conn.execute(
                "INSERT INTO commands (name, args_json, requested_at, requested_by, state) "
                "VALUES (?, ?, ?, ?, 'PENDING')",
                (name, json.dumps(args), self._clock.now().isoformat(), requested_by),
            )
            command_id = cursor.lastrowid
        if command_id is None:  # pragma: no cover - sqlite always returns the AUTOINCREMENT id
            msg = "command insert returned no id"
            raise WalkError(msg)
        return command_id

    async def wait(self, command_id: int) -> CommandResult:
        """Poll `command_results` every `COMMAND_POLL_INTERVAL_S` until the result arrives.

        Raises:
            Timeout: No result within ``timeout_s``.
        """
        waited = 0.0
        while True:
            row = (
                self._db.connect()
                .execute(
                    "SELECT finished_at, ok, result_json FROM command_results WHERE command_id = ?",
                    (command_id,),
                )
                .fetchone()
            )
            if row is not None:
                return _result(command_id, row["finished_at"], row["ok"], row["result_json"])
            if waited >= self._timeout_s:
                msg = "daemon not responding"
                raise Timeout(msg, detail={"command_id": command_id, "timeout_s": self._timeout_s})
            await self._sleep(COMMAND_POLL_INTERVAL_S)
            waited += COMMAND_POLL_INTERVAL_S


def daemon_running(repo: Path) -> bool:
    """Whether a kernel process holds `<repo>/.ai/kernel.lock`."""
    return KernelLock.is_held(repo / _AI_DIR)


async def run_mutation(
    repo: Path,
    name: str,
    args: JsonDict,
    in_process: Callable[[KernelHandle], Awaitable[JsonDict]],
) -> CommandResult:
    """Run a mutating command through the daemon, or in-process under the lock without one.

    Raises:
        Timeout: The daemon did not answer within the client timeout.
        KernelLockHeld: A daemon started between the probe and the in-process lock.
        ConfigError: The repository has no usable database or project (in-process).
    """
    if daemon_running(repo):
        db = open_database(repo)
        try:
            client = CommandClient(db, SystemClock())
            return await client.wait(await client.submit(name, args))
        finally:
            db.close()
    clock = SystemClock()
    with KernelLock(repo / _AI_DIR, kernel_instance=str(uuid.uuid4()), clock=clock):
        handle = build_kernel(KernelSettings(repo_path=repo))
        try:
            result = await in_process(handle)
        except (GuardRejected, PermissionDenied) as exc:
            return _in_process_failure(exc, _EXIT_REJECTED, clock)
        except WalkError as exc:
            return _in_process_failure(exc, _EXIT_ERROR, clock)
        finally:
            await handle.aclose()
    return CommandResult(
        command_id=_IN_PROCESS_COMMAND_ID,
        finished_at=clock.now(),
        ok=True,
        result=result,
        exit_code=0,
    )


def _result(command_id: int, finished_at: str, ok: int, result_json: str) -> CommandResult:
    data = json.loads(result_json)
    exit_code = int(data.pop(_EXIT_CODE_KEY, 0 if ok else _EXIT_ERROR))
    return CommandResult(
        command_id=command_id,
        finished_at=datetime.fromisoformat(finished_at),
        ok=bool(ok),
        result=data,
        exit_code=exit_code,
    )


def _in_process_failure(exc: WalkError, exit_code: int, clock: Clock) -> CommandResult:
    return CommandResult(
        command_id=_IN_PROCESS_COMMAND_ID,
        finished_at=clock.now(),
        ok=False,
        result={"error": exc.message},
        exit_code=exit_code,
    )
