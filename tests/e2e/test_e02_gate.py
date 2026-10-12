"""Epic 02 gate (WBS §4 E02): bootstrap → doctor → skills → approval → override → hooks."""

import asyncio
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

from tests.e2e.conftest import BOUNDARY_FILE, BOUNDARY_STORY, GATE_KEY, PROTECTED_TOOL
from walk.cli.composition import KernelHandle
from walk.common.ids import WorkItemId
from walk.common.roles import AgentRole
from walk.improvement import KernelVersionPins
from walk.integrations import EnvironmentManifest, ProductionKit, ReadinessState
from walk.persistence import Database, UnitOfWork
from walk.runtime import AgentRun, AgentRunRepository, AgentRunState
from walk.skills.lockfile import ProjectionLock
from walk.telemetry import LedgerEvent, LedgerEventKind
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

Cli = Callable[..., tuple[int, str]]
K = LedgerEventKind

# ARCHITECTURE §8: every [MVP] folder plus the Production Kit (`agents/`) of a bootstrapped repo.
KIT_DIRS: Final = (
    ".walk",
    ".ai/project",
    ".ai/features",
    ".ai/bugs",
    ".ai/decisions",
    ".ai/handovers",
    ".ai/agents/roles",
    ".ai/agents/skills",
)
KIT_FILES: Final = (
    ".ai/.gitignore",
    ".ai/kernel.db",
    ".ai/project/project.md",
    ".ai/project/constitution.md",
    ".ai/project/environment.yaml",
    ".ai/project/kernel-versions.yaml",
    ".ai/project/work-provider.yaml",
    ".ai/project/production-kit.yaml",
    ".ai/agents/policies.yaml",
    ".ai/agents/models.yaml",
    ".ai/agents/permissions.yaml",
    ".ai/agents/hooks.yaml",
    ".ai/agents/projections.lock.yaml",
)
PROVIDERS: Final = {"claude", "codex"}
EDITED_SKILL: Final = "git-hygiene"
ECHO_HOOKS: Final = (
    b"hooks:\n  - {name: on_project_start, id: project.echo, command: echo hello, timeout_s: 30}\n"
)
FEATURE: Final = "FEAT-0001"
STORY_TITLE: Final = "Shotgun spread"
_EPOCH: Final = datetime(2026, 1, 1, tzinfo=UTC)
_POLL_S: Final = 0.05
_PAUSE_POLLS: Final = 600  # 30 s for the run to reach the approval
_RUN_TIMEOUT_S: Final = 60.0


def _git(cwd: Path | str, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _ledger(cli: Cli, kind: LedgerEventKind) -> list[LedgerEvent]:
    """``walk ledger query --kind <kind> --json``, parsed."""
    code, out = cli("ledger", "query", "--kind", kind.value, "--json")
    assert code == 0, out
    return [LedgerEvent.model_validate(row) for row in json.loads(out)]


async def _ready_story(
    handle: KernelHandle, owner: AgentRole, title: str = STORY_TITLE
) -> WorkItemId:
    """A READY story ``title`` owned by ``owner`` under FEAT-0001 (IMPLEMENTING, never scheduled).

    The E02 scheduler admits STORY/TASK in READY/REWORK only (IMPLEMENT by the owner role).
    """
    feature = Feature(
        id=FEATURE,
        project_key=GATE_KEY,
        title="Combat",
        state=WorkItemState.IMPLEMENTING,
        created_at=_EPOCH,
        updated_at=_EPOCH,
    )
    async with UnitOfWork(handle.db) as uow:
        await WorkflowRepository(handle.db).insert(feature, uow)
    contract = StoryContract(
        goal="The shotgun fires eight pellets",
        acceptance_criteria=["eight pellets leave the muzzle in a cone"],
        constraints=["keep the weapon API"],
        owner_role=owner,
    )
    draft = WorkItemDraft(
        kind=WorkItemKind.STORY,
        title=title,
        description="Spread pattern of the shotgun.",
        parent_id=FEATURE,
        contract=contract,
    )
    story = await handle.workflow.create(draft, actor=AgentRole.ORCHESTRATOR, phase_id=None)
    ctx = TransitionContext(actor_role=AgentRole.ORCHESTRATOR, source=TransitionSource.KERNEL)
    await handle.workflow.raise_event(story.id, "ready", ctx)
    return story.id


async def _only_run(handle: KernelHandle, item: WorkItemId) -> AgentRun:
    (run,) = await AgentRunRepository(handle.db).for_item(item)
    return run


async def _run_in_state(handle: KernelHandle, item: WorkItemId, state: AgentRunState) -> AgentRun:
    """Poll until the single run of ``item`` is in ``state`` (the tick runs concurrently)."""
    runs = AgentRunRepository(handle.db)
    for _ in range(_PAUSE_POLLS):
        found = [run for run in await runs.for_item(item) if run.state is state]
        if found:
            return found[0]
        await asyncio.sleep(_POLL_S)
    msg = f"no run of {item} reached {state.value}"
    raise AssertionError(msg)


def test_bootstrap_creates_production_kit(bootstrapped_repo: Path) -> None:
    repo = bootstrapped_repo

    for directory in KIT_DIRS:
        assert (repo / directory).is_dir(), directory
    for file in KIT_FILES:
        assert (repo / file).is_file(), file
    assert (repo / ".ai" / ".gitignore").read_text(encoding="utf-8").splitlines() == [
        "kernel.db*",
        "kernel.lock",
    ]
    text = (repo / ".ai" / "project" / "production-kit.yaml").read_text(encoding="utf-8")
    kit = ProductionKit.model_validate(yaml.safe_load(text))
    assert kit.agent_instruction_paths
    assert kit.skill_names
    kit_paths = (*kit.agent_instruction_paths, *kit.initial_memory_paths, kit.tool_config_path)
    for path in (*kit_paths, kit.hook_config_path, kit.kernel_versions_path):
        assert (repo / path).is_file(), path
    assert KernelVersionPins.load(repo / ".ai").pins["WORKFLOW/story_workflow"] == "1.0"
    db = Database(repo / ".ai" / "kernel.db")
    try:
        row = db.connect().execute("SELECT key FROM projects").fetchall()
    finally:
        db.close()
    assert [tuple(r) for r in row] == [(GATE_KEY,)]


def test_doctor_passes_and_writes_manifest(bootstrapped_repo: Path, cli: Cli) -> None:
    manifest_path = bootstrapped_repo / ".ai" / "project" / "environment.yaml"
    manifest_path.unlink()

    code, out = cli("doctor")

    assert code == 0, out
    manifest = EnvironmentManifest.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )
    assert manifest.tools["git"].state is ReadinessState.READY
    assert manifest.work_provider.state is ReadinessState.READY
    assert manifest.unity.state is ReadinessState.MISSING  # optional: never fails the doctor


def test_skill_projections_clean_for_both_providers(bootstrapped_repo: Path, cli: Cli) -> None:
    code, out = cli("skills", "sync")
    assert code == 0, out

    code, out = cli("skills", "check-drift", "--strict")

    assert (code, out.strip()) == (0, "ok")
    lock = ProjectionLock.load(bootstrapped_repo / ".ai").projections
    assert {entry.provider for entry in lock} >= PROVIDERS
    for provider in PROVIDERS:
        assert EDITED_SKILL in {e.skill for e in lock if e.provider == provider}, provider


def test_edited_projection_detected_as_modified(bootstrapped_repo: Path, cli: Cli) -> None:
    code, out = cli("skills", "sync")
    assert code == 0, out
    lock = ProjectionLock.load(bootstrapped_repo / ".ai").projections
    (entry,) = [e for e in lock if e.provider == "claude" and e.skill == EDITED_SKILL]
    projection = bootstrapped_repo / ".walk" / "projections" / "claude" / entry.target_path
    projection.write_bytes(b"edited by hand\n")

    code, out = cli("skills", "check-drift", "--strict")

    assert code == 1, out
    assert f"modified: {EDITED_SKILL} (projection edited)" in out
    assert projection.read_bytes() == b"edited by hand\n"  # --strict reports, never repairs


async def test_protected_action_pauses_and_approval_resumes(
    kernel_with_fakes: KernelHandle, cli: Cli
) -> None:
    handle = kernel_with_fakes
    story = await _ready_story(handle, AgentRole.SENIOR_DEV)

    tick = asyncio.create_task(handle.orchestrator.run_once())
    paused = await _run_in_state(handle, story, AgentRunState.PAUSED_FOR_APPROVAL)
    code, pending = cli("approvals", "--pending")
    assert code == 0, pending
    approved = cli("approve", "APV-0001", "--note", "ok")
    started = await asyncio.wait_for(tick, timeout=_RUN_TIMEOUT_S)

    assert "APV-0001" in pending
    assert PROTECTED_TOOL in pending
    assert (approved[0], approved[1].strip()) == (0, "APV-0001 APPROVED")
    assert started == 1
    run = await _only_run(handle, story)
    assert (run.id, run.role) == (paused.id, AgentRole.SENIOR_DEV)
    assert run.state is AgentRunState.COMPLETED
    events = await handle.ledger.query(run_id=run.id, limit=10_000)
    assert {K.APPROVAL_REQUESTED, K.APPROVAL_DECIDED, K.TOOL_INVOKED} <= {e.kind for e in events}
    invoked = [e for e in events if e.kind is K.TOOL_INVOKED and e.tool == PROTECTED_TOOL]
    assert [(e.payload["phase"], e.payload.get("approval_request_id")) for e in invoked] == [
        ("pre", "APV-0001"),
        ("post", None),
    ]


def test_pause_resume_recorded_as_user_override(cli: Cli) -> None:
    paused = cli("pause")
    resumed = cli("resume")

    assert paused == (0, "project paused\n")
    assert resumed == (0, "project resumed\n")
    overrides = _ledger(cli, K.USER_OVERRIDE)
    assert [event.payload["command"] for event in overrides] == ["pause", "resume"]
    assert {event.actor_role for event in overrides} == {AgentRole.USER}


async def test_boundary_auditor_rejects_agents_dir_write(
    kernel_with_fakes: KernelHandle, bootstrapped_repo: Path
) -> None:
    handle = kernel_with_fakes
    original = (bootstrapped_repo / BOUNDARY_FILE).read_bytes()
    story = await _ready_story(handle, AgentRole.SENIOR_DEV, BOUNDARY_STORY)

    started = await handle.orchestrator.run_once()

    assert started == 1
    run = await _only_run(handle, story)
    assert run.role is AgentRole.SENIOR_DEV
    assert run.state is AgentRunState.FAILED_BOUNDARY
    assert run.failure_reason == f"boundary: {BOUNDARY_FILE}"
    assert run.worktree_path is not None
    assert not (Path(run.worktree_path) / BOUNDARY_FILE).exists()  # the write was reverted
    assert _git(run.worktree_path, "status", "--porcelain") == ""
    assert (bootstrapped_repo / BOUNDARY_FILE).read_bytes() == original
    denied = await handle.ledger.query(run_id=run.id, kinds=[K.TOOL_DENIED])
    audit = [e for e in denied if e.payload.get("source") == "BOUNDARY_AUDIT"]
    assert [(e.tool, e.payload["path"]) for e in audit] == [(None, BOUNDARY_FILE)]  # E02-B04


def test_project_hook_executes_on_start(bootstrapped_repo: Path, cli: Cli) -> None:
    (bootstrapped_repo / ".ai" / "agents" / "hooks.yaml").write_bytes(ECHO_HOOKS)

    code, out = cli("run", "--once")

    assert code == 0, out
    executed = _ledger(cli, K.HOOK_EXECUTED)
    echo = [e.payload for e in executed if e.payload["hook_id"] == "project.echo"]
    assert [payload["hook_name"] for payload in echo] == ["on_project_start"]
