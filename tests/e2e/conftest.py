"""Epic gate fixtures (WBS §3.6, §4): E01 kernel loop (E01-S31) and E02 Production Kit (E02-S16).

E01: `e01_repo` is a temporary game repository with a migrated database, the DEMO project, two
READY stories and a project `policies.yaml`; `e01_kernel` is `build_kernel` on it with two
scripted `FakeModelAdapter`s; `e01_scenario` runs one `run_once()`. `gate_script_for` decides
what every fake run does, from its `AgentInput` alone.

E02: `bootstrapped_repo` is `tmp_game_repo` with `GDD/combat.md` after `walk bootstrap`;
`cli` runs `walk <args>` on it; `kernel_with_fakes` is `build_kernel` on it with the two E02 gate
fakes (the `BOUNDARY_STORY` run edits `BOUNDARY_FILE` once, any other run requests
`PROTECTED_TOOL` once).
Preflight probes (bootstrap, doctor) are scripted; git commands run for real.
"""

import asyncio
import concurrent.futures
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
import yaml
from pydantic import ConfigDict
from typer.testing import CliRunner

from tests.cli.conftest import migrate
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_keyring import FakeKeyringBackend
from tests.fakes.fake_model_adapter import FakeModelAdapter, FakeScript, fake_descriptor
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import script_environment
from tests.orchestrator.test_bootstrap import ProbeRunner
from walk.agents import AgentInput, AgentOutput, AgentOutputStatus
from walk.cli import composition
from walk.cli.app import app
from walk.cli.composition import (
    KernelHandle,
    KernelOverrides,
    KernelSettings,
    build_kernel,
    open_database,
    open_workflow,
)
from walk.common.clock import Clock, SystemClock
from walk.common.ids import ModelId, WorkItemId
from walk.common.models import WalkModel
from walk.common.roles import AgentRole
from walk.integrations import DefaultIntegrationManager
from walk.model_router import (
    AgentEvent,
    AgentEventKind,
    FallbackTrigger,
    ProviderSessionRef,
    RunSession,
    parse_agent_output,
)
from walk.orchestrator import BootstrapOptions, Bootstrapper
from walk.permissions import PermissionEffect, ToolCallRequest
from walk.persistence import UnitOfWork
from walk.telemetry import EvidenceDraft, EvidenceKind
from walk.tools import ToolKind
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


# ---- Epic 02 gate (E02-S16; WBS §4 E02) ---------------------------------------------------

GATE_KEY: Final = "DEMO"
BOUNDARY_FILE: Final = ".ai/agents/roles/senior_dev.md"  # forbidden for every agent (§91)
PROTECTED_TOOL: Final = "git.delete_branch_protected"  # §92 protected action: USER approval
BOUNDARY_STORY: Final = "Rogue role rewrite"  # title of the story whose run edits BOUNDARY_FILE
_GDD_COMBAT: Final = b"# Combat\n\n## Shotgun\n\nEight pellets in a cone.\n"
_GATE_ROLE: Final = AgentRole.SENIOR_DEV  # the only role that can end an E02 IMPLEMENT run
_GATE_MODEL_POLICY: Final = {"preferred": [CODEX_MODEL], "fallback": [CLAUDE_MODEL]}


def _gate_output() -> AgentOutput:
    return AgentOutput(
        status=AgentOutputStatus.COMPLETED,
        result="done by the E02 gate fake",
        no_context_change_reason="gate fake run changes no shared context",
    )


class _GateAdapter(FakeModelAdapter):
    """E02 gate fake: the `BOUNDARY_STORY` run edits `BOUNDARY_FILE`, others `PROTECTED_TOOL`.

    One tool call each (the protected action is the `FakeModelAdapter` script); both report
    COMPLETED. Both scenarios are SENIOR_DEV runs, so the work item, not the role, picks one.
    """

    def __init__(self, provider: str, model_id: ModelId, clock: Clock) -> None:
        script = FakeScript(tool_calls=1, tool_name=PROTECTED_TOOL, output=_gate_output())
        super().__init__(provider, [fake_descriptor(model_id, provider)], script, clock)
        self._gate_clock = clock

    def run(self, input: AgentInput, session: RunSession) -> AsyncIterator[AgentEvent]:  # noqa: A002 - parameter name fixed by INTERFACES §2.1
        """`BOUNDARY_STORY`: the boundary-file edit; any other story: the protected action."""
        if input.task.title == BOUNDARY_STORY:
            return self._edit_boundary_file(session)
        return super().run(input, session)

    async def _edit_boundary_file(self, session: RunSession) -> AsyncIterator[AgentEvent]:
        ref = ProviderSessionRef(
            provider=self.provider, session_id=f"gate-{session.run_id}", resumable=False
        )
        yield self._gate_event(session, AgentEventKind.STARTED, session=ref)
        request = ToolCallRequest(
            run_id=session.run_id,
            role=AgentRole.SENIOR_DEV,
            tool="edit",
            kind=ToolKind.PROVIDER_NATIVE,
            arguments={"path": BOUNDARY_FILE},
            paths=[BOUNDARY_FILE],
            worktree_path=session.worktree_path,
        )
        yield self._gate_event(session, AgentEventKind.TOOL_CALL_REQUESTED, tool_call=request)
        decision = await session.permission_authorizer(request)
        allowed = decision.effect is PermissionEffect.ALLOW
        if allowed:
            _write_bytes(Path(session.worktree_path) / BOUNDARY_FILE, b"# rogue role rewrite\n")
        yield self._gate_event(
            session, AgentEventKind.TOOL_CALL_RESULT, tool_result={"ok": allowed}
        )
        raw = _gate_output().model_dump_json()
        _write_bytes(Path(session.output_path), raw.encode("utf-8"))
        output = parse_agent_output(raw)
        yield self._gate_event(session, AgentEventKind.FINAL_OUTPUT, output=output)
        yield self._gate_event(session, AgentEventKind.ENDED)

    def _gate_event(self, run: RunSession, kind: AgentEventKind, /, **fields: object) -> AgentEvent:
        return AgentEvent.model_validate(
            {"kind": kind, "run_id": run.run_id, "at": self._gate_clock.now(), **fields}
        )


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _probes() -> ProbeRunner:
    """Scripted preflight probes (Unity absent, as on a machine without the editor)."""
    return ProbeRunner(script_environment(FakeSubprocessRunner(), unity=None))


def _script_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """`walk bootstrap` and `walk doctor` probe through `_probes` with a fake keyring."""

    def open_bootstrapper(repo: Path, options: BootstrapOptions) -> Bootstrapper:
        return composition.open_bootstrapper(
            repo, options, runner=_probes(), keyring_backend=FakeKeyringBackend()
        )

    def open_integrations(repo: Path) -> DefaultIntegrationManager:
        return composition.open_integrations(
            repo, runner=_probes(), keyring_backend=FakeKeyringBackend()
        )

    monkeypatch.setattr("walk.cli.cmd_bootstrap.open_bootstrapper", open_bootstrapper)
    monkeypatch.setattr("walk.cli.cmd_doctor.open_integrations", open_integrations)


@pytest.fixture
def bootstrapped_repo(tmp_game_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """tmp_game_repo (E01) + GDD/combat.md + `walk bootstrap` executed.

    Runs ``walk bootstrap --provider local --key DEMO --name Demo --yes``. The kit is not
    committed. Preflight probes stay scripted (`_probes`) for the whole test.
    """
    _write_bytes(tmp_game_repo / "GDD" / "combat.md", _GDD_COMBAT)
    _script_preflight(monkeypatch)
    args = ("bootstrap", "--provider", "local", "--key", GATE_KEY, "--name", "Demo", "--yes")
    code, out = run_cli(tmp_game_repo, *args)
    assert code == 0, out
    return tmp_game_repo


@pytest.fixture
def cli(bootstrapped_repo: Path) -> Callable[..., tuple[int, str]]:
    """``cli(*args)`` runs ``walk <args> --repo <bootstrapped_repo>``; returns (exit, stdout)."""

    def invoke(*args: str) -> tuple[int, str]:
        return run_cli(bootstrapped_repo, *args)

    return invoke


def _use_gate_models(repo: Path) -> None:
    """Point SENIOR_DEV of the bootstrapped `policies.yaml` at the gate fakes."""
    path = repo / ".ai" / "agents" / "policies.yaml"
    policies = yaml.safe_load(path.read_text(encoding="utf-8"))
    policies["roles"][_GATE_ROLE.value]["model_policy"] = dict(_GATE_MODEL_POLICY)
    path.write_bytes(yaml.safe_dump(policies, sort_keys=False).encode("utf-8"))


@pytest.fixture
async def kernel_with_fakes(bootstrapped_repo: Path) -> AsyncIterator[KernelHandle]:
    """`build_kernel` on `bootstrapped_repo` with the gate fakes and a fake keyring.

    ``KernelOverrides(adapters={'fake-codex': …, 'fake-claude': …},
    keyring_backend=FakeKeyringBackend())``; both adapters are `_GateAdapter`s
    (`FakeModelAdapter`s). SENIOR_DEV prefers ``fake-codex/sim``. The kernel runs on
    the system clock, like the CLI commands the tests run next to it.
    """
    _use_gate_models(bootstrapped_repo)
    clock = SystemClock()
    adapters = {
        "fake-codex": _GateAdapter("fake-codex", CODEX_MODEL, clock),
        "fake-claude": _GateAdapter("fake-claude", CLAUDE_MODEL, clock),
    }
    overrides = KernelOverrides(adapters=adapters, keyring_backend=FakeKeyringBackend())
    handle = build_kernel(KernelSettings(repo_path=bootstrapped_repo), overrides=overrides)
    try:
        yield handle
    finally:
        await handle.aclose()
