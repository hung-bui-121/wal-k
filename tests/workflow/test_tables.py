import re
from pathlib import Path

import pytest
import yaml

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


INTERFACES = Path(__file__).resolve().parents[2] / "docs" / "01-architecture" / "INTERFACES.md"


def _documented_rows(heading: str) -> list[tuple[str, str, str]]:
    """(from, event, to) of an INTERFACES §3 table; 'any…' sources become '*'."""
    text = INTERFACES.read_text(encoding="utf-8")
    section = text[text.index(heading) :]
    section = section[: section.index("\n### ", 1)]
    rows: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[1].startswith("`"):
            continue
        source = cells[0].split()[0]
        target = cells[3].split()[0]
        rows.append(("*" if source == "any" else source, cells[1].strip("`"), target))
    return rows


def _loaded_rows(name: str) -> list[tuple[str, str, str]]:
    table = TableLoader().load(TABLES_DIR / f"{name}.yaml")
    return [(str(row.from_state), row.event, str(row.to_state)) for row in table.transitions]


def _same_pairs(name: str, heading: str, count: int) -> None:
    documented = _documented_rows(heading)
    loaded = _loaded_rows(name)
    assert len(loaded) == count
    assert [(src, event) for src, event, _ in loaded] == [(s, e) for s, e, _ in documented]
    for (_, _, target), (_, _, doc_target) in zip(loaded, documented, strict=True):
        if doc_target in WorkItemState.__members__:
            assert target == doc_target


def test_tables_dir_contains_exactly_the_kernel_tables() -> None:
    assert sorted(path.name for path in TABLES_DIR.iterdir() if path.is_file()) == [
        "bug_workflow.yaml",
        "feature_workflow.yaml",
        "scheduled_states.yaml",
        "story_workflow.yaml",
    ]


def test_feature_workflow_matches_interfaces() -> None:
    _same_pairs("feature_workflow", "### 3.1 Feature lifecycle", 21)
    table = TableLoader().load(TABLES_DIR / "feature_workflow.yaml")
    assert table.kinds == (WorkItemKind.FEATURE,)
    force = table.transitions[-1]
    assert (force.to_state, force.effects) == (
        "CHILDREN_READY_FOR_REVIEW",
        ("force_children_review",),
    )
    cancel = table.transitions[-2]
    assert cancel.excluded_states == (WorkItemState.COMPLETE, WorkItemState.CANCELLED)


def test_bug_workflow_matches_interfaces() -> None:
    _same_pairs("bug_workflow", "### 3.3 Bug lifecycle", 17)
    table = TableLoader().load(TABLES_DIR / "bug_workflow.yaml")
    assert table.kinds == (WorkItemKind.BUG,)
    reopen = [row for row in table.transitions if row.event == "reopen"]
    assert [row.guards for row in reopen] == [("reopen_below_max",), ("reopen_at_max",)]
    assert reopen[0].effects == ("increment_reopen_count",)
    assert table.transitions[-1].to_state == "PREVIOUS"


def test_scheduled_states_match_routing_table() -> None:
    text = INTERFACES.read_text(encoding="utf-8")
    section = text[text.index("## 4. Routing table") : text.index("## 5. Algorithms")]
    documented: set[tuple[str, str]] = set()
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in {"Work item kind", "---"}:
            continue
        for kind in cells[0].split("/"):
            if kind in {"FEATURE", "STORY", "TASK", "BUG"}:
                documented.update((kind, state) for state in cells[1].split("/"))
    entries = yaml.safe_load((TABLES_DIR / "scheduled_states.yaml").read_text(encoding="utf-8"))
    loaded = {(entry["kind"], entry["state"]) for entry in entries}
    assert loaded == documented
    assert len(entries) == len(loaded)
    roles = {(e["kind"], e["state"]): e["role"] for e in entries}
    assert roles[("STORY", "REWORK")] == "contract.owner_role"
    assert roles[("TASK", "READY_FOR_REVIEW")] == "contract.reviewer_role"
    assert roles[("BUG", "READY_FOR_REVIEW")] == "LEAD_DEV"
    assert re.fullmatch(r"[A-Z_]+", roles[("FEATURE", "IDEA")])
