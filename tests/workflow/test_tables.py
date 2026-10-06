from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.hooks import HookName
from walk.workflow import TABLES_DIR, TableLoader, WorkItemKind, WorkItemState

ROW = "{from: IDEA, event: ready, to: READY, guards: [], roles: [USER], hooks: []}"


def _table(tmp_path: Path, rows: list[str], header: str = 'version: "1.0"\nkinds: [STORY]') -> Path:
    path = tmp_path / "custom_workflow.yaml"
    body = "\n".join(f"  - {row}" for row in rows)
    path.write_text(f"name: custom_workflow\n{header}\ntransitions:\n{body}\n", encoding="utf-8")
    return path


def test_story_workflow_loads_with_expected_rows() -> None:
    table = TableLoader().load(TABLES_DIR / "story_workflow.yaml")
    assert table.name == "story_workflow"
    assert table.version == "1.0"
    assert table.kinds == (WorkItemKind.STORY, WorkItemKind.TASK)
    assert len(table.transitions) == 18
    first = table.transitions[0]
    assert (first.from_state, first.event, first.to_state) == (
        WorkItemState.IDEA,
        "ready",
        WorkItemState.READY,
    )
    assert first.guards == ("definition_of_ready",)
    qc_rejected = table.transitions[12]
    assert qc_rejected.effects == ("increment_fix_loops",)
    assert qc_rejected.hooks == (HookName.ON_QC_RESULT, HookName.ON_BUG_CREATED)
    unblock = table.transitions[15]
    assert unblock.to_state == "PREVIOUS"
    cancel = table.transitions[16]
    assert cancel.from_state == "*"
    assert cancel.excluded_states == (WorkItemState.COMPLETE,)
    any_agent = table.transitions[1].allowed_roles
    assert AgentRole.SENIOR_DEV in any_agent
    assert AgentRole.USER not in any_agent
    assert AgentRole.KERNEL not in any_agent


def test_loader_rejects_unknown_guard(tmp_path: Path) -> None:
    path = _table(tmp_path, [ROW, ROW.replace("guards: []", "guards: [nope]")])
    with pytest.raises(ConfigError, match=r"row 2 .*nope") as raised:
        TableLoader().load(path)
    assert raised.value.detail["row"] == 2


@pytest.mark.parametrize(
    ("row", "fragment"),
    [
        (ROW.replace("hooks: []", "hooks: [on_nothing]"), "on_nothing"),
        (ROW.replace("roles: [USER]", "roles: [JANITOR]"), "JANITOR"),
        (ROW.replace("to: READY", "to: SOMEWHERE"), "SOMEWHERE"),
        (ROW.replace("from: IDEA", 'from: "* except NOWHERE"'), "NOWHERE"),
        (ROW.replace("hooks: []", "hooks: [], effects: [explode]"), "explode"),
        (ROW.replace("hooks: []", "hooks: [], colour: red"), "colour"),
    ],
)
def test_loader_rejects_unknown_names(tmp_path: Path, row: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        TableLoader().load(_table(tmp_path, [row]))


@pytest.mark.parametrize(
    "content",
    [
        "name: x\nversion: 1.0\nkinds: [STORY]\ntransitions: []\n",
        "- just a list\n",
        "name: [unclosed\n",
        "name: x\nversion: '1.0'\nkinds: [PLANET]\ntransitions: []\n",
    ],
)
def test_loader_rejects_malformed_tables(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad_workflow.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=r"bad_workflow\.yaml"):
        TableLoader().load(path)


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"missing_workflow\.yaml"):
        TableLoader().load(tmp_path / "missing_workflow.yaml")
