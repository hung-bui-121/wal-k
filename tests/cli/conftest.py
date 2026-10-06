"""Fixtures for the kernel-level CLI tests (E01-S30): a migrated game repository and fakes."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import AgentOutput, AgentOutputStatus
from walk.cli.composition import KernelOverrides
from walk.model_router import ModelAdapter
from walk.persistence import Database, MigrationRunner, UnitOfWork
from walk.workflow import (
    Project,
    ProjectRepository,
    Story,
    StoryContract,
    WorkflowRepository,
    WorkItemState,
)

CODEX_MODEL = "fake-codex/sim"
CLAUDE_MODEL = "fake-claude/sim"
POLICIES = (
    "roles:\n"
    "  SENIOR_DEV:\n"
    f"    model_policy: {{preferred: [{CODEX_MODEL}], fallback: [{CLAUDE_MODEL}]}}\n"
)

OverridesFactory = Callable[..., KernelOverrides]


async def _no_sleep(seconds: float) -> None:
    del seconds


def fake_script(tool_calls: int = 3) -> FakeScript:
    output = AgentOutput(
        status=AgentOutputStatus.COMPLETED, result="done", no_context_change_reason="fake run"
    )
    return FakeScript(tool_calls=tool_calls, output=output)


def fake_adapters(clock: FakeClock, plan: FakeScript | None = None) -> dict[str, ModelAdapter]:
    script = plan or fake_script()
    return {
        "fake-codex": FakeModelAdapter(
            "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], script, clock
        ),
        "fake-claude": FakeModelAdapter(
            "fake-claude", [fake_descriptor(CLAUDE_MODEL, "fake-claude")], script, clock
        ),
    }


def migrate(repo: Path, *, project: bool = True) -> None:
    """Create `<repo>/.ai/kernel.db` with the schema and (optionally) the DEMO project."""
    db = Database(repo / ".ai" / "kernel.db")
    MigrationRunner(db, "project").apply_pending()

    async def seed() -> None:
        demo = Project(
            key="DEMO",
            name="Demo",
            repo_path=str(repo),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        async with UnitOfWork(db) as uow:
            await ProjectRepository(db).insert(demo, uow)

    if project:
        asyncio.run(seed())
    db.close()


async def add_story(
    repo: Path, number: int, title: str, state: WorkItemState = WorkItemState.READY
) -> Story:
    """Insert ``STORY-<number>`` in ``state``."""
    db = Database(repo / ".ai" / "kernel.db")
    item = Story(
        id=f"STORY-{number:04d}",
        project_key="DEMO",
        title=title,
        state=state,
        contract=StoryContract(goal=title),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    try:
        async with UnitOfWork(db) as uow:
            await WorkflowRepository(db).insert(item, uow)
    finally:
        db.close()
    return item


@pytest.fixture
def kernel_repo(tmp_game_repo: Path) -> Path:
    """`tmp_game_repo` with a migrated database, the DEMO project and fake-model policies."""
    migrate(tmp_game_repo)
    policies = tmp_game_repo / ".ai" / "agents" / "policies.yaml"
    policies.parent.mkdir(parents=True, exist_ok=True)
    policies.write_bytes(POLICIES.encode("utf-8"))
    return tmp_game_repo


@pytest.fixture
def fake_overrides(fake_clock: FakeClock) -> OverridesFactory:
    """Overrides with the two fake adapters, the fake clock and a no-op sleep."""

    def build(plan: FakeScript | None = None, **fields: object) -> KernelOverrides:
        data: dict[str, object] = {
            "adapters": fake_adapters(fake_clock, plan),
            "clock": fake_clock,
            "sleep": _no_sleep,
            "kernel_instance": "test-instance",
            "ready_env_keys": {"git"},
            **fields,
        }
        return KernelOverrides.model_validate(data)

    return build
