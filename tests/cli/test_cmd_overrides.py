import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.cli.conftest import add_story
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_id_factory import SequentialIdFactory
from walk.cli import cmd_policy
from walk.cli.app import app
from walk.common.errors import Timeout
from walk.persistence import Database
from walk.telemetry import DefaultLedgerManager, LedgerEventKind, LedgerRepository
from walk.workflow import ProjectRepository, WorkItemState

runner = CliRunner()


def _overrides(repo: Path, clock: FakeClock) -> list[dict[str, object]]:
    db = Database(repo / ".ai" / "kernel.db")
    try:
        ledger = DefaultLedgerManager(db, LedgerRepository(db), SequentialIdFactory(), clock)
        events = asyncio.run(ledger.query(kinds=[LedgerEventKind.USER_OVERRIDE]))
        return [e.payload for e in events]
    finally:
        db.close()


def _project(repo: Path) -> tuple[bool, int]:
    db = Database(repo / ".ai" / "kernel.db")
    try:
        project = asyncio.run(ProjectRepository(db).single())
        return project.paused, project.autonomy_level_max
    finally:
        db.close()


def test_set_model_rejects_unknown_model(kernel_repo: Path) -> None:
    policies = kernel_repo / ".ai" / "agents" / "policies.yaml"
    before = policies.read_bytes()

    result = runner.invoke(
        app,
        ["policy", "set-model", "SENIOR_DEV", "--preferred", "nope/x", "--repo", str(kernel_repo)],
    )

    assert result.exit_code == 1
    assert "nope/x" in result.output
    assert policies.read_bytes() == before


def test_set_model_rewrites_the_role(kernel_repo: Path, fake_clock: FakeClock) -> None:
    result = runner.invoke(
        app,
        [
            "policy",
            "set-model",
            "SENIOR_DEV",
            "--preferred",
            "codex/default",
            "--fallback",
            "codex/gpt-5-codex",
            "--repo",
            str(kernel_repo),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "SENIOR_DEV" in result.stdout
    text = (kernel_repo / ".ai" / "agents" / "policies.yaml").read_text(encoding="utf-8")
    assert "codex/default" in text
    assert _overrides(kernel_repo, fake_clock) == [
        {
            "command": "policy.set_model",
            "args": {
                "role": "SENIOR_DEV",
                "preferred": ["codex/default"],
                "fallback": ["codex/gpt-5-codex"],
            },
        }
    ]


def test_set_autonomy(kernel_repo: Path, fake_clock: FakeClock) -> None:
    result = runner.invoke(app, ["policy", "set-autonomy", "1", "--repo", str(kernel_repo)])
    invalid = runner.invoke(app, ["policy", "set-autonomy", "7", "--repo", str(kernel_repo)])

    assert result.exit_code == 0, result.output
    assert _project(kernel_repo)[1] == 1
    assert _overrides(kernel_repo, fake_clock) == [
        {"command": "policy.set_autonomy", "args": {"level": 1, "actor": "user"}}
    ]
    assert invalid.exit_code != 0


def test_pause_agent_requires_daemon(kernel_repo: Path) -> None:
    paused = runner.invoke(
        app, ["pause", "--agent", "RUN-01J0000000000000000000000A", "--repo", str(kernel_repo)]
    )
    resumed = runner.invoke(
        app, ["resume", "--agent", "RUN-01J0000000000000000000000A", "--repo", str(kernel_repo)]
    )

    assert paused.exit_code == 3
    assert "daemon" in paused.output
    assert resumed.exit_code == 3


def test_pause_and_resume_project_in_process(kernel_repo: Path, fake_clock: FakeClock) -> None:
    paused = runner.invoke(app, ["pause", "--repo", str(kernel_repo)])
    state = _project(kernel_repo)[0]
    resumed = runner.invoke(app, ["resume", "--json", "--repo", str(kernel_repo)])

    assert (paused.exit_code, paused.stdout.strip()) == (0, "project paused")
    assert state is True
    assert resumed.exit_code == 0, resumed.output
    assert json.loads(resumed.stdout) == {"paused": False, "run_id": None}
    assert _project(kernel_repo)[0] is False
    assert [p["command"] for p in _overrides(kernel_repo, fake_clock)] == ["pause", "resume"]


def test_work_cancel_and_priority(kernel_repo: Path, fake_clock: FakeClock) -> None:
    asyncio.run(add_story(kernel_repo, 1, "Jump", WorkItemState.READY))
    asyncio.run(add_story(kernel_repo, 2, "Done", WorkItemState.COMPLETE))

    priority = runner.invoke(
        app, ["work", "priority", "STORY-0001", "P0", "--repo", str(kernel_repo)]
    )
    cancelled = runner.invoke(
        app,
        ["work", "cancel", "STORY-0001", "--reason", "scope dropped", "--repo", str(kernel_repo)],
    )
    rejected = runner.invoke(
        app, ["work", "cancel", "STORY-0002", "--reason", "late", "--repo", str(kernel_repo)]
    )

    assert (priority.exit_code, priority.stdout.strip()) == (0, "STORY-0001 priority P0")
    assert (cancelled.exit_code, cancelled.stdout.strip()) == (0, "STORY-0001 cancelled")
    assert rejected.exit_code == 2
    assert [p["command"] for p in _overrides(kernel_repo, fake_clock)] == [
        "work.priority",
        "work.cancel",
    ]


@pytest.mark.parametrize(
    "argv",
    [["pause"], ["work", "priority", "STORY-0001", "P1"], ["policy", "set-autonomy", "2"]],
)
def test_override_commands_report_a_silent_daemon(
    kernel_repo: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    async def silent(*args: object, **kwargs: object) -> object:
        del args, kwargs
        msg = "no answer"
        raise Timeout(msg)

    monkeypatch.setattr(cmd_policy, "run_mutation", silent)

    result = runner.invoke(app, [*argv, "--repo", str(kernel_repo)])

    assert result.exit_code == 3
    assert "daemon not responding" in result.output


def test_override_commands_json_and_errors(kernel_repo: Path, tmp_path: Path) -> None:
    asyncio.run(add_story(kernel_repo, 1, "Jump", WorkItemState.READY))
    base = ["--json", "--repo", str(kernel_repo)]

    model = runner.invoke(app, ["policy", "set-model", "QC", "--preferred", "codex/default", *base])
    autonomy = runner.invoke(app, ["policy", "set-autonomy", "3", *base])
    priority = runner.invoke(app, ["work", "priority", "STORY-0001", "P2", *base])
    cancel = runner.invoke(app, ["work", "cancel", "STORY-0001", "--reason", "x", *base])
    paused = runner.invoke(app, ["pause", *base])
    unknown = runner.invoke(
        app, ["work", "priority", "STORY-0404", "P1", "--repo", str(kernel_repo)]
    )
    no_project = runner.invoke(app, ["policy", "set-autonomy", "1", "--repo", str(tmp_path)])

    assert json.loads(model.stdout)["role"] == "QC"
    assert json.loads(autonomy.stdout) == {"autonomy_level_max": 3}
    assert json.loads(priority.stdout) == {"work_item_id": "STORY-0001", "priority": "P2"}
    assert json.loads(cancel.stdout) == {"work_item_id": "STORY-0001", "state": "CANCELLED"}
    assert json.loads(paused.stdout) == {"paused": True, "run_id": None}
    assert unknown.exit_code == 1
    assert no_project.exit_code == 1
