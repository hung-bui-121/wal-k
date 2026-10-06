"""`walk run`: the kernel process (ARCHITECTURE §3.1, §3.4 steps 1-6; E01-S30).

Acquire the repository lock, build the kernel, register the instance, then either one tick
(``--once``) or the daemon loop: the orchestrator's tick loop and the command consumer run
concurrently until a ``stop`` command (or an interrupt) drains the running runs.
"""

import asyncio
import contextlib
import logging
import os
import socket
import uuid
from typing import Final

import typer

from walk.cli.composition import (
    KernelHandle,
    KernelOverrides,
    KernelSettings,
    build_kernel,
    open_database,
)
from walk.cli.output import render_json
from walk.common.clock import Clock, SystemClock
from walk.common.models import JsonDict
from walk.common.roles import AgentRole
from walk.orchestrator import CommandConsumer
from walk.persistence import KernelInstanceRegistry, KernelLock, KernelLockHeld, MigrationRunner
from walk.workflow import TransitionContext, TransitionSource

_LOG = logging.getLogger(__name__)

_AI_DIR: Final = ".ai"
_EXIT_OK: Final = 0
_EXIT_ERROR: Final = 1
_NO_PROJECT: Final = "no project - run 'walk bootstrap'"


async def run_daemon(
    settings: KernelSettings, *, once: bool, overrides: KernelOverrides | None = None
) -> int:
    """Run the kernel for ``settings.repo_path``; return the process exit code.

    1 when the lock is held or an unexpected error occurs; with ``once`` and no project row,
    0 and nothing started (1 in daemon mode). The lock is always released and the handle
    closed.
    """
    o = overrides or KernelOverrides()
    clock: Clock = o.clock or SystemClock()
    instance = o.kernel_instance or str(uuid.uuid4())
    lock = KernelLock(settings.repo_path / _AI_DIR, kernel_instance=instance, clock=clock)
    try:
        lock.acquire()
    except KernelLockHeld as exc:
        typer.echo(f"error: {exc.message}", err=True)
        return _EXIT_ERROR
    handle: KernelHandle | None = None
    try:
        if not _has_project(settings):
            typer.echo(_NO_PROJECT, err=True)
            if once:
                _print_started(settings, 0)
                return _EXIT_OK
            return _EXIT_ERROR
        handle = build_kernel(
            settings, overrides=o.model_copy(update={"kernel_instance": instance})
        )
        registry = KernelInstanceRegistry(handle.db, clock)
        await registry.register(instance, hostname=socket.gethostname(), pid=os.getpid())
        _LOG.info("preflight skipped until E02-S02", extra={"skip": settings.skip_preflight})
        if once:
            _print_started(settings, await handle.orchestrator.run_once())
            return _EXIT_OK
        await _serve(handle, registry, clock)
    except Exception:  # noqa: BLE001 - the process exits 1 after logging any failure
        _LOG.exception("kernel stopped by an unexpected error")
        return _EXIT_ERROR
    finally:
        if handle is not None:
            await handle.aclose()
        lock.release()
    return _EXIT_OK


async def _serve(handle: KernelHandle, registry: KernelInstanceRegistry, clock: Clock) -> None:
    """The daemon loop until a ``stop`` command or a cancellation; always drains."""
    stop = asyncio.Event()
    consumer = CommandConsumer(handle.db, clock)
    _register_handlers(consumer, handle, stop)
    orchestrator = handle.orchestrator
    loop = asyncio.create_task(orchestrator.start(), name="walk-orchestrator")
    commands = asyncio.create_task(consumer.run(stop), name="walk-commands")
    heartbeat = asyncio.create_task(
        _heartbeat(registry, handle.kernel_instance, stop, handle.settings.poll_interval_s),
        name="walk-heartbeat",
    )
    stopped = asyncio.create_task(stop.wait(), name="walk-stop")
    try:
        await asyncio.wait({loop, stopped}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop.set()
        await orchestrator.stop(drain=True)
        await asyncio.gather(loop, commands, heartbeat, stopped, return_exceptions=True)
    if loop.done() and not loop.cancelled():
        loop.result()  # re-raises a failure of the orchestrator loop


def _register_handlers(
    consumer: CommandConsumer, handle: KernelHandle, stop: asyncio.Event
) -> None:
    async def wake(args: JsonDict) -> JsonDict:
        del args
        await handle.orchestrator.wake()
        return {}

    async def stop_kernel(args: JsonDict) -> JsonDict:
        del args
        stop.set()
        return {}

    async def transition(args: JsonDict) -> JsonDict:
        result = await transition_in_kernel(handle, args)
        await handle.orchestrator.wake()
        return result

    consumer.register("wake", wake)
    consumer.register("stop", stop_kernel)
    consumer.register("work.transition", transition)


async def transition_in_kernel(handle: KernelHandle, args: JsonDict) -> JsonDict:
    """``work.transition{work_item_id, event, reason, payload}`` raised as USER.

    Shared by the daemon handler and the in-process path of `walk work transition`.
    """
    facts: JsonDict = dict(args.get("payload") or {})
    if args.get("reason") is not None:
        facts["reason"] = args["reason"]
    context = TransitionContext(
        actor_role=AgentRole.USER,
        source=TransitionSource.USER,
        run_id=None,
        payload=facts,
        phase=None,
    )
    row = await handle.workflow.raise_event(str(args["work_item_id"]), str(args["event"]), context)
    return {"to_state": row.to_state.value, "transition": row.model_dump(mode="json")}


async def _heartbeat(
    registry: KernelInstanceRegistry, instance: str, stop: asyncio.Event, interval_s: float
) -> None:
    while not stop.is_set():
        await registry.heartbeat(instance)
        with contextlib.suppress(TimeoutError):  # a timeout is the next heartbeat
            await asyncio.wait_for(stop.wait(), interval_s)


def _has_project(settings: KernelSettings) -> bool:
    db = open_database(settings.repo_path)
    try:
        MigrationRunner(db, "project").apply_pending()
        row = db.connect().execute("SELECT COUNT(*) FROM projects").fetchone()
        return int(row[0]) > 0
    finally:
        db.close()


def _print_started(settings: KernelSettings, started: int) -> None:
    if settings.json_output:
        typer.echo(render_json({"started": started}))
    else:
        typer.echo(f"started {started} run(s)")
