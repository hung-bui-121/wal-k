import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from tests.cli.conftest import CODEX_MODEL, OverridesFactory, add_story, fake_script, migrate
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, fake_descriptor
from walk.agents import AgentInput
from walk.cli.composition import KernelSettings
from walk.cli.daemon import run_daemon
from walk.cli.ipc import CommandClient
from walk.common.clock import SystemClock
from walk.model_router import AgentEvent, RunSession
from walk.persistence import Database, KernelLock
from walk.runtime import AgentRunState
from walk.telemetry import LedgerEventKind

EVENT_DELAY_S = 0.05
WAIT_ATTEMPTS = 400


class SlowAdapter(FakeModelAdapter):
    """Fake that takes real time between events, so a run is still going when a command lands."""

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        return self._slow(super().run(input, session))

    async def _slow(self, inner: AsyncIterator[AgentEvent]) -> AsyncIterator[AgentEvent]:
        async for event in inner:
            await asyncio.sleep(EVENT_DELAY_S)
            yield event


def _query(repo: Path, sql: str) -> list[tuple[object, ...]]:
    db = Database(repo / ".ai" / "kernel.db")
    try:
        return [tuple(row) for row in db.connect().execute(sql).fetchall()]
    finally:
        db.close()


async def _until(condition: str, repo: Path) -> None:
    for _ in range(WAIT_ATTEMPTS):
        if _query(repo, condition):
            return
        await asyncio.sleep(0.02)
    msg = f"never true: {condition}"
    raise AssertionError(msg)


async def test_run_once_executes_one_tick(
    kernel_repo: Path, fake_overrides: OverridesFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    await add_story(kernel_repo, 1, "Double jump")

    code = await run_daemon(
        KernelSettings(repo_path=kernel_repo), once=True, overrides=fake_overrides()
    )

    assert code == 0
    assert capsys.readouterr().out.strip() == "started 1 run(s)"
    assert _query(kernel_repo, "SELECT state FROM agent_runs") == [("COMPLETED",)]
    kinds = {row[0] for row in _query(kernel_repo, "SELECT kind FROM ledger_events")}
    assert {LedgerEventKind.PROJECT_STARTED.value, LedgerEventKind.AGENT_RUN_ENDED.value} <= kinds
    assert _query(kernel_repo, "SELECT id FROM kernel_instances") == [("test-instance",)]
    assert KernelLock.is_held(kernel_repo / ".ai") is False


async def test_stop_command_ends_daemon(
    kernel_repo: Path, fake_overrides: OverridesFactory, fake_clock: FakeClock
) -> None:
    await add_story(kernel_repo, 1, "Double jump")
    slow = SlowAdapter(
        "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], fake_script(40), fake_clock
    )
    overrides = fake_overrides()
    assert overrides.adapters is not None
    adapters = {**overrides.adapters, "fake-codex": slow}
    settings = KernelSettings(repo_path=kernel_repo, poll_interval_s=0.05)
    daemon = asyncio.create_task(
        run_daemon(
            settings, once=False, overrides=overrides.model_copy(update={"adapters": adapters})
        )
    )
    await _until(
        "SELECT 1 FROM agent_runs WHERE json_extract(json, '$.tool_calls') > 0", kernel_repo
    )
    db = Database(kernel_repo / ".ai" / "kernel.db")
    try:
        client = CommandClient(db, SystemClock(), timeout_s=10)
        woken = await client.wait(await client.submit("wake", {}))
        result = await client.wait(await client.submit("stop", {}))
    finally:
        db.close()

    code = await asyncio.wait_for(daemon, 30)

    assert code == 0
    assert woken.ok is True
    assert result.ok is True
    (run_id, state) = _query(kernel_repo, "SELECT id, state FROM agent_runs")[0]
    assert state == AgentRunState.PAUSED_BY_USER.value
    pause = _query(kernel_repo, f"SELECT kind FROM checkpoints WHERE run_id = '{run_id}'")  # noqa: S608 - test literal
    assert ("PAUSE",) in pause
    assert KernelLock.is_held(kernel_repo / ".ai") is False


async def test_daemon_exit_codes_without_project_or_lock(
    tmp_game_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    migrate(tmp_game_repo, project=False)
    settings = KernelSettings(repo_path=tmp_game_repo, json_output=True)

    once = await run_daemon(settings, once=True)
    daemon = await run_daemon(settings, once=False)
    output = capsys.readouterr()

    assert (once, daemon) == (0, 1)
    assert output.out.strip() == '{\n  "started": 0\n}'
    assert "no project" in output.err
    with KernelLock(tmp_game_repo / ".ai", kernel_instance="other"):
        held = await run_daemon(settings, once=True)
    assert held == 1
    assert "kernel already running" in capsys.readouterr().err


async def test_daemon_exits_1_on_unexpected_error(
    kernel_repo: Path, fake_overrides: OverridesFactory
) -> None:
    (kernel_repo / ".ai" / "agents" / "models.yaml").write_bytes(b"models: [not, a, mapping]\n")
    await add_story(kernel_repo, 1, "Double jump")

    code = await run_daemon(
        KernelSettings(repo_path=kernel_repo), once=True, overrides=fake_overrides()
    )

    assert code == 1
    assert KernelLock.is_held(kernel_repo / ".ai") is False


async def test_cancelled_daemon_drains_and_releases(
    kernel_repo: Path, fake_overrides: OverridesFactory
) -> None:
    settings = KernelSettings(repo_path=kernel_repo, poll_interval_s=0.05)
    daemon = asyncio.create_task(run_daemon(settings, once=False, overrides=fake_overrides()))
    await _until("SELECT 1 FROM ledger_events WHERE kind = 'PROJECT_STARTED'", kernel_repo)

    daemon.cancel()
    with pytest.raises(asyncio.CancelledError):
        await daemon

    assert KernelLock.is_held(kernel_repo / ".ai") is False
