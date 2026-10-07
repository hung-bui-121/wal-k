"""`CommandConsumer`: the daemon side of the SQLite command channel (ADR-0009 D-3; E01-S30).

E02-S13 adds `override_handlers`, the §93 human-override commands.

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
from walk.common.roles import AgentRole
from walk.decisions.models import AutonomyLevel
from walk.orchestrator.service import DefaultOrchestrator
from walk.persistence.database import Database
from walk.persistence.uow import UnitOfWork
from walk.workflow.models import Priority

_LOG = logging.getLogger(__name__)

CommandHandler = Callable[[JsonDict], Awaitable[JsonDict]]

_EXIT_OK: Final = 0
_EXIT_ERROR: Final = 1
_EXIT_REJECTED: Final = 2
_EXIT_CODE_KEY: Final = "exit_code"
_USER: Final = "user"  # actor of a CLI override


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


def override_handlers(orchestrator: DefaultOrchestrator) -> dict[str, CommandHandler]:
    """The §93 override commands by name (E02-S13); daemon and in-process paths share them.

    ``pause``/``resume`` ``{run_id?}``, ``work.cancel`` ``{work_item_id, reason}``,
    ``work.priority`` ``{work_item_id, priority}``, ``policy.set_model`` ``{role, preferred,
    fallback}``, ``policy.set_autonomy`` ``{level}``. Each one writes ``USER_OVERRIDE``.
    """

    async def pause(args: JsonDict) -> JsonDict:
        run_id = args.get("run_id")
        await orchestrator.pause(str(run_id) if run_id else None)
        return {"paused": True, "run_id": run_id}

    async def resume(args: JsonDict) -> JsonDict:
        run_id = args.get("run_id")
        await orchestrator.resume(str(run_id) if run_id else None)
        return {"paused": False, "run_id": run_id}

    async def cancel(args: JsonDict) -> JsonDict:
        work_item_id = str(args["work_item_id"])
        await orchestrator.cancel_work_item(work_item_id, str(args["reason"]))
        return {"work_item_id": work_item_id, "state": "CANCELLED"}

    async def priority(args: JsonDict) -> JsonDict:
        item = await orchestrator.set_priority(
            str(args["work_item_id"]), Priority(str(args["priority"])), actor=_USER
        )
        return {"work_item_id": item.id, "priority": item.priority.value}

    async def set_model(args: JsonDict) -> JsonDict:
        role = AgentRole(str(args["role"]))
        policy = await orchestrator.set_model_policy(
            role, list(args["preferred"]), list(args.get("fallback") or [])
        )
        return {"role": role.value, "model_policy": policy.model_policy.model_dump(mode="json")}

    async def set_autonomy(args: JsonDict) -> JsonDict:
        project = await orchestrator.set_autonomy(AutonomyLevel(int(args["level"])), actor=_USER)
        return {"autonomy_level_max": project.autonomy_level_max}

    return {
        "pause": pause,
        "resume": resume,
        "work.cancel": cancel,
        "work.priority": priority,
        "policy.set_model": set_model,
        "policy.set_autonomy": set_autonomy,
    }
