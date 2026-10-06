"""Epic 01 gate fixtures (E01-S31; WBS §4 E01): the kernel loop with two fake providers.

`e01_repo` is a temporary game repository with a migrated database, the DEMO project, two READY
stories and a project `policies.yaml`; `e01_kernel` is `build_kernel` on it with two scripted
`FakeModelAdapter`s; `e01_scenario` runs one `run_once()`. `gate_script_for` decides what every
fake run does, from its `AgentInput` alone.
"""

import asyncio
import concurrent.futures
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from pydantic import ConfigDict
from typer.testing import CliRunner

from tests.cli.conftest import migrate
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from walk.agents import AgentInput, AgentOutput, AgentOutputStatus
from walk.cli.app import app
from walk.cli.composition import (
    KernelHandle,
    KernelOverrides,
    KernelSettings,
    build_kernel,
    open_database,
    open_workflow,
)
from walk.common.ids import WorkItemId
from walk.common.models import WalkModel
from walk.common.roles import AgentRole
from walk.model_router import FallbackTrigger
from walk.persistence import UnitOfWork
from walk.telemetry import EvidenceDraft, EvidenceKind
from walk.workflow import (
    Feature,
    StoryContract,
    TransitionContext,
    TransitionSource,
    WorkflowRepository,
    WorkItemDraft,
    WorkItemKind,
    WorkItemState,
)

CODEX_MODEL: Final = "fake-codex/sim"
CLAUDE_MODEL: Final = "fake-claude/sim"
STORY_OK: Final = "STORY-0001"
STORY_FALLBACK: Final = "STORY-0002"
FEATURE: Final = "FEAT-0001"
GATE_TOOL_CALLS: Final = 12  # WBS §4 E01: 12 tool calls → 2 periodic checkpoints at every 5
OUTAGE_AFTER_TOOL_CALLS: Final = 3
CONTINUATION_TOOL_CALLS: Final = 6  # > OUTAGE_AFTER so the continuation commits new files
EVIDENCE_PATH: Final = "src/Fake1.cs"  # written by the fake's first tool call
GATE_POLICIES: Final = (
    "roles:\n"
    "  SENIOR_DEV:\n"
    "    model_policy:\n"
    f"      preferred: [{CODEX_MODEL}]\n"
    f"      fallback: [{CLAUDE_MODEL}]\n"
    "      cross_model_review: true\n"
    "    checkpoint_every_tool_calls: 5\n"
    "    max_parallel_runs: 2\n"
)
_EPOCH: Final = datetime(2026, 1, 1, tzinfo=UTC)
_STORY_TITLES: Final = ("Double jump", "Wall slide")


class E01Scenario(WalkModel):
    """The gate repository after one `run_once()`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo: Path
    handle: KernelHandle
    story_ok: WorkItemId
    story_fallback: WorkItemId
    started: int


def _completed() -> AgentOutput:
    evidence = EvidenceDraft(
        kind=EvidenceKind.AUTOMATED_TEST,
        path_or_uri=EVIDENCE_PATH,
        description="fake EditMode results",
    )
    return AgentOutput(
        status=AgentOutputStatus.COMPLETED,
        result="implemented by the gate fake",
        evidence=[evidence],
        no_context_change_reason="gate fake run changes no shared context",
    )


def gate_script_for(agent_input: AgentInput) -> FakeScript:
    """What the fake run for ``agent_input`` does (pure function of the input).

    STORY-0001: 12 calls, COMPLETED. STORY-0002 without a handover (first run): 12 calls with a
    PROVIDER_OUTAGE after 3. STORY-0002 with a handover (fallback run): 6 calls, COMPLETED.

    Raises:
        ValueError: The input is for another work item.
    """
    item = agent_input.task.id
    if item == STORY_OK:
        return FakeScript(tool_calls=GATE_TOOL_CALLS, output=_completed())
    if item == STORY_FALLBACK and agent_input.handover is None:
        return FakeScript(
            tool_calls=GATE_TOOL_CALLS,
            output=_completed(),
            fail_after_tool_calls=OUTAGE_AFTER_TOOL_CALLS,
            fail_trigger=FallbackTrigger.PROVIDER_OUTAGE,
            fail_error="scripted provider outage",
        )
    if item == STORY_FALLBACK:
        return FakeScript(tool_calls=CONTINUATION_TOOL_CALLS, output=_completed())
    msg = f"the E01 gate scripts no run for {item}"
    raise ValueError(msg)


async def _seed_stories(repo: Path) -> None:
    """FEAT-0001 (IMPLEMENTING, not schedulable) with two stories moved to READY."""
    clock = FakeClock(_EPOCH)
    db = open_database(repo)
    try:
        feature = Feature(
            id=FEATURE,
            project_key="DEMO",
            title="Movement",
            state=WorkItemState.IMPLEMENTING,
            created_at=_EPOCH,
            updated_at=_EPOCH,
        )
        async with UnitOfWork(db) as uow:
            await WorkflowRepository(db).insert(feature, uow)
        workflow = open_workflow(db, clock=clock)
        ctx = TransitionContext(actor_role=AgentRole.ORCHESTRATOR, source=TransitionSource.KERNEL)
        for title in _STORY_TITLES:
            contract = StoryContract(
                goal=f"The player can {title.lower()}",
                acceptance_criteria=[f"{title} works in the movement test scene"],
                constraints=["keep the existing movement controller API"],
                required_evidence=[EvidenceKind.AUTOMATED_TEST],
            )
            draft = WorkItemDraft(
                kind=WorkItemKind.STORY,
                title=title,
                description=f"{title} for the player character.",
                parent_id=FEATURE,
                contract=contract,
            )
            story = await workflow.create(draft, actor=AgentRole.ORCHESTRATOR, phase_id=None)
            await workflow.raise_event(story.id, "ready", ctx)
    finally:
        db.close()


@pytest.fixture
def e01_repo(tmp_game_repo: Path) -> Path:
    """`tmp_game_repo` + migrated DB + DEMO project + gate policies + two READY stories."""
    migrate(tmp_game_repo)
    policies = tmp_game_repo / ".ai" / "agents" / "policies.yaml"
    policies.parent.mkdir(parents=True, exist_ok=True)
    policies.write_bytes(GATE_POLICIES.encode("utf-8"))
    asyncio.run(_seed_stories(tmp_game_repo))
    return tmp_game_repo


async def _no_sleep(seconds: float) -> None:
    del seconds


@pytest.fixture
async def e01_kernel(e01_repo: Path, fake_clock: FakeClock) -> AsyncIterator[KernelHandle]:
    """`build_kernel` on the gate repository with the two scripted fakes."""
    adapters = {
        "fake-codex": FakeModelAdapter(
            "fake-codex", [fake_descriptor(CODEX_MODEL, "fake-codex")], gate_script_for, fake_clock
        ),
        "fake-claude": FakeModelAdapter(
            "fake-claude",
            [fake_descriptor(CLAUDE_MODEL, "fake-claude")],
            gate_script_for,
            fake_clock,
        ),
    }
    overrides = KernelOverrides(
        adapters=adapters, clock=fake_clock, sleep=_no_sleep, kernel_instance="gate-1"
    )
    handle = build_kernel(KernelSettings(repo_path=e01_repo), overrides=overrides)
    try:
        yield handle
    finally:
        await handle.aclose()


@pytest.fixture
async def e01_scenario(e01_repo: Path, e01_kernel: KernelHandle) -> E01Scenario:
    """The gate repository after one `run_once()`."""
    started = await e01_kernel.orchestrator.run_once()
    return E01Scenario(
        repo=e01_repo,
        handle=e01_kernel,
        story_ok=STORY_OK,
        story_fallback=STORY_FALLBACK,
        started=started,
    )


def _invoke(repo: Path, args: tuple[str, ...]) -> tuple[int, str]:
    result = CliRunner().invoke(app, [*args, "--repo", str(repo)])
    return result.exit_code, result.stdout


def run_cli(repo: Path, *args: str) -> tuple[int, str]:
    """Run ``walk <args> --repo <repo>`` in-process; return ``(exit_code, stdout)``.

    The commands call `asyncio.run`, so they run on a worker thread: the async gate tests
    already own this thread's event loop.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_invoke, repo, args).result()
