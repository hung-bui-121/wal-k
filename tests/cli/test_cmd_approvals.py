import asyncio
import json
import threading
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.fakes.fake_clock import FakeClock
from walk.cli import cmd_approvals
from walk.cli.app import app
from walk.cli.composition import KernelSettings
from walk.cli.daemon import run_daemon
from walk.cli.ipc import CommandClient
from walk.common.clock import SystemClock
from walk.common.errors import Timeout
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.permissions import ApprovalRepository, Approver, DefaultPermissionManager
from walk.persistence import Database, IdSequenceStore, KernelLock
from walk.telemetry import DefaultLedgerManager, LedgerRepository

runner = CliRunner()


def _seed(repo: Path, clock: FakeClock, count: int, *, deny_first: bool = False) -> list[str]:
    """``count`` PENDING protected-action requests (the first one denied when asked)."""
    db = Database(repo / ".ai" / "kernel.db")
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, clock)
    manager = DefaultPermissionManager(
        [],
        [],
        ApprovalRepository(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, clock),
        ids,
        clock,
        project_key="DEMO",
    )

    async def seed() -> list[str]:
        created = [
            await manager.request_approval(
                {"tool": "git.merge_protected"},
                kind="PROTECTED_ACTION",
                approver=Approver.USER,
                requested_by=AgentRole.LEAD_DEV,
                run_id=None,
                work_item_id="STORY-0001",
            )
            for _ in range(count)
        ]
        if deny_first:
            await manager.decide_approval(created[0].id, approve=False, by="user", note=None)
        return [a.id for a in created]

    try:
        return asyncio.run(seed())
    finally:
        db.close()


def _state(repo: Path, approval_id: str) -> str:
    db = Database(repo / ".ai" / "kernel.db")
    try:
        row = (
            db.connect()
            .execute("SELECT state FROM approval_requests WHERE id = ?", (approval_id,))
            .fetchone()
        )
        return str(row[0])
    finally:
        db.close()


def test_approve_command(kernel_repo: Path, fake_clock: FakeClock) -> None:
    _seed(kernel_repo, fake_clock, 1)

    result = runner.invoke(app, ["approve", "APV-0001", "--note", "ok", "--repo", str(kernel_repo)])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "APV-0001 APPROVED"
    assert _state(kernel_repo, "APV-0001") == "APPROVED"
    again = runner.invoke(app, ["deny", "APV-0001", "--repo", str(kernel_repo)])
    assert again.exit_code == 2
    assert "approval already decided" in again.output


def test_deny_unknown_exits_one(kernel_repo: Path, fake_clock: FakeClock) -> None:
    _seed(kernel_repo, fake_clock, 1)

    result = runner.invoke(app, ["deny", "APV-9999", "--repo", str(kernel_repo)])
    denied = runner.invoke(app, ["deny", "APV-0001", "--json", "--repo", str(kernel_repo)])

    assert result.exit_code == 1
    assert "APV-9999" in result.output
    assert denied.exit_code == 0, denied.output
    assert json.loads(denied.output)["state"] == "DENIED"


def test_approvals_pending_lists_only_pending(kernel_repo: Path, fake_clock: FakeClock) -> None:
    _seed(kernel_repo, fake_clock, 3, deny_first=True)

    pending = runner.invoke(app, ["approvals", "--pending", "--json", "--repo", str(kernel_repo)])
    table = runner.invoke(app, ["approvals", "--pending", "--repo", str(kernel_repo)])
    every = runner.invoke(app, ["approvals", "--json", "--repo", str(kernel_repo)])

    assert pending.exit_code == 0, pending.output
    assert [row["id"] for row in json.loads(pending.output)] == ["APV-0002", "APV-0003"]
    assert "APV-0002" in table.output
    assert "PROTECTED_ACTION" in table.output
    assert "git.merge_protected" in table.output
    assert [row["state"] for row in json.loads(every.output)] == [
        "DENIED",
        "PENDING",
        "PENDING",
    ]


def test_approvals_without_database_exits_one(tmp_path: Path) -> None:
    result = runner.invoke(app, ["approvals", "--repo", str(tmp_path)])

    assert result.exit_code == 1
    assert not (tmp_path / ".ai").exists()


def test_approve_routes_through_daemon(kernel_repo: Path) -> None:
    # The daemon runs on the system clock and expires overdue requests every tick.
    _seed(kernel_repo, FakeClock(SystemClock().now()), 2)
    codes: list[int] = []
    settings = KernelSettings(repo_path=kernel_repo, poll_interval_s=0.1)
    thread = threading.Thread(
        target=lambda: codes.append(asyncio.run(run_daemon(settings, once=False))), daemon=True
    )
    thread.start()
    try:
        for _ in range(500):
            if KernelLock.is_held(kernel_repo / ".ai"):
                break
            time.sleep(0.01)
        approved = runner.invoke(app, ["approve", "APV-0001", "--repo", str(kernel_repo)])
        denied = runner.invoke(app, ["deny", "APV-0002", "--repo", str(kernel_repo)])
        twice = runner.invoke(app, ["deny", "APV-0002", "--repo", str(kernel_repo)])
    finally:
        asyncio.run(_stop(kernel_repo))
        thread.join(timeout=30)

    assert (approved.exit_code, approved.stdout.strip()) == (0, "APV-0001 APPROVED")
    assert (denied.exit_code, denied.stdout.strip()) == (0, "APV-0002 DENIED")
    assert twice.exit_code == 2
    assert codes == [0]
    db = Database(kernel_repo / ".ai" / "kernel.db")
    try:
        rows = db.connect().execute(
            "SELECT name, state FROM commands WHERE name IN ('approve', 'deny') ORDER BY id"
        )
        assert [tuple(row) for row in rows.fetchall()] == [
            ("approve", "DONE"),
            ("deny", "DONE"),
            ("deny", "FAILED"),
        ]
    finally:
        db.close()


async def _stop(repo: Path) -> None:
    db = Database(repo / ".ai" / "kernel.db")
    try:
        client = CommandClient(db, SystemClock(), timeout_s=20)
        await client.wait(await client.submit("stop", {}))
    finally:
        db.close()


def test_decide_without_database_or_daemon_answer(
    kernel_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = runner.invoke(app, ["approve", "APV-0001", "--repo", str(tmp_path / "nowhere")])

    async def silent(*args: object, **kwargs: object) -> object:
        del args, kwargs
        msg = "no answer"
        raise Timeout(msg)

    monkeypatch.setattr(cmd_approvals, "run_mutation", silent)
    no_answer = runner.invoke(app, ["deny", "APV-0001", "--repo", str(kernel_repo)])

    assert missing.exit_code == 1
    assert "database does not exist" in missing.output
    assert no_answer.exit_code == 3
    assert "daemon not responding" in no_answer.output
