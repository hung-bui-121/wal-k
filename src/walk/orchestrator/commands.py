"""`CommandConsumer`: the daemon side of the SQLite command channel (ADR-0009 D-3; E01-S30).

The CLI inserts `commands` rows; the consumer runs the registered handler for each PENDING row
in id order and writes `command_results`. ``result_json`` holds the handler result plus its
``exit_code`` (0, or 2 for a guard rejection or permission denial, 1 for any other error). The
consumer writes no ledger events: the handlers' services do.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Final

from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected, PermissionDenied, WalkError
from walk.common.models import JsonDict
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork

_LOG = logging.getLogger(__name__)

CommandHandler = Callable[[JsonDict], Awaitable[JsonDict]]

_EXIT_OK: Final = 0
_EXIT_ERROR: Final = 1
_EXIT_REJECTED: Final = 2
_EXIT_CODE_KEY: Final = "exit_code"


class CommandConsumer:
    """Executes PENDING commands with their registered handlers."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        poll_interval_s: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Wire the consumer.

        Args:
            db: The project database holding `commands` and `command_results`.
            clock: Stamps ``finished_at``.
            poll_interval_s: Seconds between polls in `run`.
            sleep: Awaited between polls.
        """
        self._db = db
        self._clock = clock
        self._poll_interval_s = poll_interval_s
        self._sleep = sleep
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, name: str, handler: CommandHandler) -> None:
        """Run ``handler`` for commands called ``name``.

        Raises:
            ConfigError: ``name`` already has a handler.
        """
        if name in self._handlers:
            msg = f"a handler for command {name!r} is already registered"
            raise ConfigError(msg, detail={"command": name})
        self._handlers[name] = handler

    async def poll_once(self) -> int:
        """Process every PENDING command in id order; return how many were processed."""
        rows = (
            self._db.connect()
            .execute("SELECT id, name, args_json FROM commands WHERE state = 'PENDING' ORDER BY id")
            .fetchall()
        )
        for row in rows:
            await self._process(int(row["id"]), str(row["name"]), str(row["args_json"]))
        return len(rows)

    async def run(self, stop: asyncio.Event) -> None:
        """Poll until ``stop`` is set."""
        while not stop.is_set():
            await self.poll_once()
            await self._sleep(self._poll_interval_s)

    async def _process(self, command_id: int, name: str, args_json: str) -> None:
        async with UnitOfWork(self._db) as uow:
            uow.conn.execute("UPDATE commands SET state = 'RUNNING' WHERE id = ?", (command_id,))
        handler = self._handlers.get(name)
        if handler is None:
            result: JsonDict = {"error": f"unknown command {name}", _EXIT_CODE_KEY: _EXIT_ERROR}
        else:
            result = await self._run(handler, name, json.loads(args_json))
        ok = result[_EXIT_CODE_KEY] == _EXIT_OK
        async with UnitOfWork(self._db) as uow:
            uow.conn.execute(
                "INSERT INTO command_results (command_id, finished_at, ok, result_json) "
                "VALUES (?, ?, ?, ?)",
                (command_id, self._clock.now().isoformat(), int(ok), json.dumps(result)),
            )
            uow.conn.execute(
                "UPDATE commands SET state = ? WHERE id = ?",
                ("DONE" if ok else "FAILED", command_id),
            )

    async def _run(self, handler: CommandHandler, name: str, args: JsonDict) -> JsonDict:
        try:
            result = await handler(args)
        except (GuardRejected, PermissionDenied) as exc:
            return {"error": exc.message, _EXIT_CODE_KEY: _EXIT_REJECTED}
        except WalkError as exc:
            return {"error": exc.message, _EXIT_CODE_KEY: _EXIT_ERROR}
        except Exception as exc:  # noqa: BLE001 - every failure becomes a FAILED result
            _LOG.exception("command handler failed", extra={"command": name})
            return {"error": str(exc) or type(exc).__name__, _EXIT_CODE_KEY: _EXIT_ERROR}
        return {**result, _EXIT_CODE_KEY: _EXIT_OK}
