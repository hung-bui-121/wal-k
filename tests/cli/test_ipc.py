import asyncio
from pathlib import Path

import pytest

from walk.cli.composition import KernelHandle
from walk.cli.ipc import COMMAND_POLL_INTERVAL_S, CommandClient, daemon_running, run_mutation
from walk.common.clock import SystemClock
from walk.common.errors import ConfigError, GuardRejected, Timeout
from walk.common.models import JsonDict
from walk.orchestrator import CommandConsumer
from walk.persistence import Database, KernelLock


async def test_client_round_trip_and_timeout(kernel_repo: Path) -> None:
    tmp_path = kernel_repo
    daemon_db = Database(tmp_path / ".ai" / "kernel.db")
    client_db = Database(tmp_path / ".ai" / "kernel.db")
    consumer = CommandConsumer(daemon_db, SystemClock(), poll_interval_s=0.01)

    async def wake(args: JsonDict) -> JsonDict:
        return {"woken": args.get("reason")}

    consumer.register("wake", wake)
    stop = asyncio.Event()
    serving = asyncio.create_task(consumer.run(stop))
    client = CommandClient(client_db, SystemClock())
    try:
        command_id = await client.submit("wake", {"reason": "test"})
        result = await client.wait(command_id)
    finally:
        stop.set()
        await serving

    assert result.command_id == command_id
    assert result.ok is True
    assert result.exit_code == 0
    assert result.result == {"woken": "test"}
    slow = CommandClient(client_db, SystemClock(), timeout_s=0.5)
    with pytest.raises(Timeout, match="daemon not responding"):
        await slow.wait(await slow.submit("wake", {}, requested_by="KERNEL"))
    assert COMMAND_POLL_INTERVAL_S == 0.25
    daemon_db.close()
    client_db.close()


async def test_run_mutation_in_process_without_daemon(kernel_repo: Path) -> None:
    ai_root = kernel_repo / ".ai"
    seen: list[bool] = []

    async def in_process(handle: KernelHandle) -> JsonDict:
        seen.append(KernelLock.is_held(ai_root))
        return {"project": handle.project_key}

    assert daemon_running(kernel_repo) is False

    result = await run_mutation(kernel_repo, "probe", {}, in_process)

    assert seen == [True]
    assert result.ok is True
    assert result.result == {"project": "DEMO"}
    assert result.exit_code == 0
    assert KernelLock.is_held(ai_root) is False


async def test_run_mutation_maps_in_process_errors(kernel_repo: Path) -> None:
    async def rejected(handle: KernelHandle) -> JsonDict:
        del handle
        msg = "guard said no"
        raise GuardRejected(msg)

    async def broken(handle: KernelHandle) -> JsonDict:
        del handle
        msg = "bad"
        raise ConfigError(msg)

    guard = await run_mutation(kernel_repo, "probe", {}, rejected)
    config = await run_mutation(kernel_repo, "probe", {}, broken)

    assert (guard.ok, guard.exit_code, guard.result) == (False, 2, {"error": "guard said no"})
    assert (config.ok, config.exit_code) == (False, 1)
    assert KernelLock.is_held(kernel_repo / ".ai") is False
