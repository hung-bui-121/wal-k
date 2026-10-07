from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import PermissionDenied
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.memory import (
    ApprovedWriteRefused,
    DefaultMemoryManager,
    FrontMatter,
    MemoryDocType,
    MemoryDocument,
    MemoryIndexRepository,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository

AT = datetime(2026, 1, 1, tzinfo=UTC)
ACTOR = Actor(role=AgentRole.LEAD_DEV)
HEAD = "3f9c2e1"


@pytest.fixture
def manager(db: Database, fake_clock: FakeClock) -> DefaultMemoryManager:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    return DefaultMemoryManager(
        db.path.parent,
        MemoryIndexRepository(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock),
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )


def _approved(**extra: object) -> MemoryDocument:
    front = FrontMatter(
        id="APR-0001",
        type=MemoryDocType.APPROVED,
        title="Core loop",
        created_at=AT,
        updated_at=AT,
        updated_by=ACTOR,
        extra=dict(extra),
    )
    return MemoryDocument(
        path="approved/APR-0001.md",
        front_matter=front,
        sections={"Summary": "edited"},
        raw_sha256="",
    )


async def test_write_under_approved_refused_without_decision(
    manager: DefaultMemoryManager, db: Database
) -> None:
    for doc in (_approved(), _approved(change_request_decision="not-a-decision")):
        with pytest.raises(PermissionDenied, match="only through approve_artifact"):
            await manager.write(doc, actor=ACTOR, head=HEAD, branch="main")

    assert issubclass(ApprovedWriteRefused, PermissionDenied)
    assert not (Path(db.path.parent) / "approved" / "APR-0001.md").exists()


async def test_write_under_approved_with_a_change_decision_is_accepted(
    manager: DefaultMemoryManager, db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    written = await manager.write(
        _approved(change_request_decision="DEC-0007"), actor=ACTOR, head=HEAD, branch="main"
    )

    assert written.path == "approved/APR-0001.md"
    assert (Path(db.path.parent) / "approved" / "APR-0001.md").is_file()
    assert "not verified" in caplog.text
