"""Epic 01 gate (WBS §4 E01): the kernel loop with fake providers, fallback and CLI views."""

import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from tests.e2e.conftest import (
    CLAUDE_MODEL,
    CODEX_MODEL,
    CONTINUATION_TOOL_CALLS,
    GATE_TOOL_CALLS,
    OUTAGE_AFTER_TOOL_CALLS,
    E01Scenario,
    run_cli,
)
from tests.fakes.fake_model_adapter import FakeModelAdapter
from walk.agents import HANDOVER_SECTION_FIELDS
from walk.common.roles import AgentRole
from walk.model_router import AgentEventKind
from walk.orchestrator import KernelStatus
from walk.runtime import (
    AgentRun,
    AgentRunRepository,
    AgentRunState,
    Checkpoint,
    CheckpointKind,
    HandoverRepository,
)
from walk.telemetry import EvidenceKind, LedgerEvent, LedgerEventKind
from walk.workflow import WorkflowRepository, WorkItemState

K = LedgerEventKind
ROOT = Path(__file__).resolve().parents[2]
TRAILER = "Walk-Work-Item"
TERMINAL = {AgentRunState.COMPLETED, AgentRunState.HANDED_OVER}
FALLBACK_ORDER = [
    K.AGENT_RUN_STARTED,
    K.CHECKPOINT_CREATED,
    K.HANDOVER_CREATED,
    K.MODEL_FALLBACK,
    K.AGENT_RUN_ENDED,
    K.AGENT_RUN_STARTED,
    K.AGENT_RUN_ENDED,
]


def _git(cwd: Path | str, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _commits(repo: Path, branch: str) -> list[tuple[str, str]]:
    """``(subject, Walk-Work-Item trailer)`` of every commit on ``branch``, newest first."""
    fmt = f"%s%x09%(trailers:key={TRAILER},valueonly,separator=%x2C)"
    lines = _git(repo, "log", f"--format={fmt}", branch).splitlines()
    return [
        (subject, trailer) for subject, _, trailer in (line.partition(chr(9)) for line in lines)
    ]


def _checkpoints(scenario: E01Scenario, run_id: str) -> list[Checkpoint]:
    rows = (
        scenario.handle.db.connect()
        .execute("SELECT json FROM checkpoints WHERE run_id = ? ORDER BY seq", (run_id,))
        .fetchall()
    )
    return [Checkpoint.model_validate_json(row[0]) for row in rows]


async def _runs(scenario: E01Scenario, item: str) -> list[AgentRun]:
    return await AgentRunRepository(scenario.handle.db).for_item(item)


async def _events(
    scenario: E01Scenario,
    *,
    kinds: list[LedgerEventKind] | None = None,
    work_item_id: str | None = None,
    run_id: str | None = None,
) -> list[LedgerEvent]:
    return await scenario.handle.ledger.query(
        kinds=kinds, work_item_id=work_item_id, run_id=run_id, limit=10_000
    )


def _subsequence(kinds: list[str], wanted: list[str]) -> bool:
    remaining = iter(kinds)
    return all(kind in remaining for kind in wanted)


def _fake(scenario: E01Scenario, model_id: str) -> FakeModelAdapter:
    adapter = scenario.handle.router.adapter_for(model_id)
    assert isinstance(adapter, FakeModelAdapter)
    return adapter


def _write_point_kinds() -> set[str]:
    """Event kinds of the ARCHITECTURE §4.3 write-point table."""
    text = (ROOT / "docs" / "01-architecture" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    section = text.split("### 4.3 Ledger write points", 1)[1].split("\n---", 1)[0]
    rows = [line.split("|")[2] for line in section.splitlines() if line.startswith("| `")]
    return {kind for row in rows for kind in re.findall(r"`([A-Z_]+)`", row)}


async def test_run_once_admits_both_stories_and_drains(e01_scenario: E01Scenario) -> None:
    assert e01_scenario.started == 2

    first_ok, *_ = await _runs(e01_scenario, e01_scenario.story_ok)
    first_fallback, *_ = await _runs(e01_scenario, e01_scenario.story_fallback)
    assert first_ok.branch != first_fallback.branch
    assert first_ok.started_at == first_fallback.started_at  # one tick admitted both
    every_run = [
        *await _runs(e01_scenario, e01_scenario.story_ok),
        *await _runs(e01_scenario, e01_scenario.story_fallback),
    ]
    assert len(every_run) == 3
    assert {run.state for run in every_run} <= TERMINAL
    assert e01_scenario.handle.executor.running() == []


async def test_story_completes_with_periodic_checkpoints(e01_scenario: E01Scenario) -> None:
    story = e01_scenario.story_ok
    (run,) = await _runs(e01_scenario, story)

    assert run.model_id == CODEX_MODEL
    assert run.state is AgentRunState.COMPLETED
    assert run.tool_calls == GATE_TOOL_CALLS
    invoked = await _events(e01_scenario, run_id=run.id, kinds=[K.TOOL_INVOKED])
    assert len([e for e in invoked if e.payload.get("phase") == "post"]) == GATE_TOOL_CALLS
    checkpoints = _checkpoints(e01_scenario, run.id)
    assert [(c.seq, c.kind) for c in checkpoints] == [
        (1, CheckpointKind.START),
        (2, CheckpointKind.PERIODIC),
        (3, CheckpointKind.PERIODIC),
        (4, CheckpointKind.END),
    ]
    assert run.branch is not None
    commits = _commits(e01_scenario.repo, run.branch)
    wip = [(subject, trailer) for subject, trailer in commits if subject.startswith("wip(")]
    assert (f"wip({story}): checkpoint 2", story) in wip
    assert (f"wip({story}): checkpoint 3", story) in wip
    evidence = await e01_scenario.handle.evidence.for_item(story)
    assert [(e.id.startswith("EVD-"), e.kind) for e in evidence] == [
        (True, EvidenceKind.AUTOMATED_TEST)
    ]
    item = await e01_scenario.handle.workflow.get(story)
    assert item.state is WorkItemState.READY_FOR_REVIEW
    transitions = await WorkflowRepository(e01_scenario.handle.db).transitions(story, limit=None)
    submitted = [t for t in transitions if t.event == "submit_for_review"]
    assert [(t.to_state, t.actor_role, t.run_id) for t in submitted] == [
        (WorkItemState.READY_FOR_REVIEW, AgentRole.SENIOR_DEV, run.id)
    ]


async def test_provider_outage_falls_back_with_handover(e01_scenario: E01Scenario) -> None:
    story = e01_scenario.story_fallback
    first, second = await _runs(e01_scenario, story)

    assert (first.model_id, first.provider) == (CODEX_MODEL, "fake-codex")
    assert first.state is AgentRunState.HANDED_OVER
    assert first.tool_calls == OUTAGE_AFTER_TOOL_CALLS
    assert first.handover_out_id == "HO-0001"
    assert [c.kind for c in _checkpoints(e01_scenario, first.id)][-1] is CheckpointKind.HANDOFF
    document = e01_scenario.repo / ".ai" / "handovers" / "HO-0001.md"
    text = document.read_text(encoding="utf-8")
    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    assert headings == [heading for heading, _ in HANDOVER_SECTION_FIELDS]
    assert "reason: FALLBACK" in text
    (fallback,) = await _events(e01_scenario, work_item_id=story, kinds=[K.MODEL_FALLBACK])
    assert fallback.payload["trigger"] == "PROVIDER_OUTAGE"
    assert (fallback.payload["from"], fallback.payload["to"]) == (CODEX_MODEL, CLAUDE_MODEL)
    assert (second.model_id, second.provider) == (CLAUDE_MODEL, "fake-claude")
    assert second.parent_run_id == first.id
    assert second.handover_in_id == "HO-0001"
    assert second.fallbacks == 1
    assert (second.worktree_path, second.branch) == (first.worktree_path, first.branch)
    assert second.state is AgentRunState.COMPLETED
    assert second.tool_calls == CONTINUATION_TOOL_CALLS
    item = await e01_scenario.handle.workflow.get(story)
    assert item.state is WorkItemState.READY_FOR_REVIEW
    handover = await HandoverRepository(e01_scenario.handle.db).get("HO-0001")
    assert handover is not None
    assert handover.to_run_id == second.id


async def test_cli_views_reflect_kernel_state(e01_scenario: E01Scenario) -> None:
    await e01_scenario.handle.aclose()  # read-only views of a stopped kernel (no daemon)
    repo = e01_scenario.repo

    code, out = run_cli(repo, "status", "--json")
    assert code == 0, out
    status = KernelStatus.model_validate(json.loads(out))
    assert status.active_runs == []
    assert status.phase_progress[WorkItemState.READY_FOR_REVIEW] == 2
    assert set(status.model_usage) == {CODEX_MODEL, CLAUDE_MODEL}

    code, out = run_cli(repo, "ledger", "query", "--item", e01_scenario.story_fallback, "--json")
    assert code == 0, out
    kinds = [event["kind"] for event in json.loads(out)]
    assert _subsequence(kinds, [kind.value for kind in FALLBACK_ORDER]), kinds
    assert kinds.count(K.AGENT_RUN_STARTED.value) == 2

    code, out = run_cli(repo, "work", "show", e01_scenario.story_ok)
    assert code == 0, out
    assert out.splitlines()[0].split() == [e01_scenario.story_ok, "STORY", "READY_FOR_REVIEW"]
    for move in ("IDEA -> READY", "READY -> IMPLEMENTING", "IMPLEMENTING -> READY_FOR_REVIEW"):
        assert move in out
    (run,) = await AgentRunRepository(e01_scenario.handle.db).for_item(e01_scenario.story_ok)
    assert f"{run.id}  COMPLETED  SENIOR_DEV  IMPLEMENT  {CODEX_MODEL}" in out


async def test_ledger_complete_and_immutable(e01_scenario: E01Scenario) -> None:
    events = await _events(e01_scenario)
    runs = [
        *await _runs(e01_scenario, e01_scenario.story_ok),
        *await _runs(e01_scenario, e01_scenario.story_fallback),
    ]

    for run in runs:
        kinds = [e.kind for e in events if e.run_id == run.id]
        assert kinds.count(K.AGENT_RUN_STARTED) == 1, run.id
        assert kinds.count(K.AGENT_RUN_ENDED) == 1, run.id
    assert {e.project_key for e in events} == {"DEMO"}
    assert {e.kind.value for e in events} <= _write_point_kinds() | {K.PROJECT_STARTED.value}
    with pytest.raises(sqlite3.IntegrityError):
        e01_scenario.handle.db.connect().execute("UPDATE ledger_events SET outcome = 'EDITED'")


async def test_role_is_independent_of_model(e01_scenario: E01Scenario) -> None:
    first, second = await _runs(e01_scenario, e01_scenario.story_fallback)
    started = {
        e.run_id: e
        for e in await _events(
            e01_scenario, work_item_id=e01_scenario.story_fallback, kinds=[K.AGENT_RUN_STARTED]
        )
    }
    a, b = started[first.id], started[second.id]

    assert (first.role, first.purpose) == (second.role, second.purpose)
    assert a.actor_role == b.actor_role == AgentRole.SENIOR_DEV
    assert a.payload["purpose"] == b.payload["purpose"] == "IMPLEMENT"
    assert a.behavior_versions["prompt:IMPLEMENT"] == b.behavior_versions["prompt:IMPLEMENT"]
    assert (first.model_id, first.provider) != (second.model_id, second.provider)


async def test_continuation_does_not_depend_on_session(e01_scenario: E01Scenario) -> None:
    first, second = await _runs(e01_scenario, e01_scenario.story_fallback)
    assert first.worktree_path is not None
    handoff = _checkpoints(e01_scenario, first.id)[-1]
    resumed = _checkpoints(e01_scenario, second.id)[0]

    written = {f"src/Fake{n}.cs" for n in range(1, OUTAGE_AFTER_TOOL_CALLS + 1)}
    in_handoff = set(
        _git(e01_scenario.repo, "ls-tree", "-r", "--name-only", handoff.head_sha).splitlines()
    )
    assert written <= in_handoff
    # run B started (START checkpoint, before any tool call) on the HANDOFF commit of run A
    assert resumed.kind is CheckpointKind.START
    assert resumed.head_sha == handoff.head_sha
    events_b = _fake(e01_scenario, CLAUDE_MODEL).runs[second.id]
    first_call = next(e for e in events_b if e.kind is AgentEventKind.TOOL_CALL_REQUESTED)
    assert first_call.tool_call is not None
    assert first_call.tool_call.worktree_path == first.worktree_path
    document = (e01_scenario.repo / ".ai" / "handovers" / "HO-0001.md").read_text(encoding="utf-8")
    events_a = _fake(e01_scenario, CODEX_MODEL).runs[first.id]
    texts = [e.text for e in events_a if e.kind is AgentEventKind.TEXT and e.text]
    assert not [text for text in texts if text in document]


def test_import_linter_contracts_pass() -> None:
    lint_imports = shutil.which("lint-imports")
    assert lint_imports is not None
    done = subprocess.run([lint_imports], cwd=ROOT, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "0 broken" in done.stdout
