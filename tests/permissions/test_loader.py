from pathlib import Path

import pytest

from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.permissions import (
    DEFAULT_PROTECTED_ACTIONS,
    Approver,
    PermissionEffect,
    PermissionRule,
    PermissionsFile,
    ProtectedAction,
    load_defaults,
    load_project_rules,
    merge_narrowing,
)

ALLOW = PermissionEffect.ALLOW
DENY = PermissionEffect.DENY
APPROVAL = PermissionEffect.REQUIRE_APPROVAL
R = AgentRole
AGENTS = [role for role in AgentRole if role not in {R.USER, R.KERNEL}]
DEV_FILES = ("read", "edit", "write", "glob", "grep")
# The E02-S10 defaults table, one (role, tool, effect) per cell.
TABLE: list[tuple[AgentRole, str, PermissionEffect]] = [
    *[(role, tool, ALLOW) for role in (R.SENIOR_DEV, R.LEAD_DEV) for tool in DEV_FILES],
    (R.SENIOR_DEV, "bash", ALLOW),
    (R.SENIOR_DEV, "git.commit", ALLOW),
    *[
        (R.SENIOR_DEV, tool, DENY)
        for tool in (
            "git.merge_protected",
            "git.push_protected",
            "jira.close_feature",
            "review.approve",
            "review.reject",
            "qc.*",
        )
    ],
    (R.LEAD_DEV, "bash", ALLOW),
    (R.LEAD_DEV, "git.commit", ALLOW),
    *[(R.LEAD_DEV, t, ALLOW) for t in ("review.approve", "review.reject", "jira.create_task")],
    (R.LEAD_DEV, "jira.close_feature", DENY),
    (R.LEAD_DEV, "git.merge_protected", APPROVAL),
    *[(R.QC, tool, ALLOW) for tool in ("read", "glob", "grep", "bash")],
    *[(R.QC, t, ALLOW) for t in ("jira.create_bug", "jira.reopen", "qc.approve", "qc.reject")],
    *[(R.QC, tool, DENY) for tool in ("edit", "write", "git.commit")],
    *[
        (R.ORCHESTRATOR, tool, ALLOW)
        for tool in ("jira.create_*", "jira.transition", "work.plan", "read", "glob", "grep")
    ],
    *[(R.ORCHESTRATOR, tool, DENY) for tool in ("edit", "write", "bash")],
    *[
        (role, tool, effect)
        for role in (R.PRODUCT_OWNER, R.DESIGN_LEADER, R.ART_DIRECTOR)
        for tool, effect in (
            ("read", ALLOW),
            ("glob", ALLOW),
            ("grep", ALLOW),
            ("decision.propose", ALLOW),
            ("edit", DENY),
            ("write", DENY),
            ("bash", DENY),
        )
    ],
    *[(role, "bash", DENY) for role in AGENTS],
    *[(role, action, APPROVAL) for role in AGENTS for action in DEFAULT_PROTECTED_ACTIONS],
]


def _rule(role: AgentRole, tool: str, effect: PermissionEffect, **fields: object) -> PermissionRule:
    data: dict[str, object] = {"role": role, "tool": tool, "effect": effect, **fields}
    if effect is APPROVAL:
        data.setdefault("approver", Approver.USER)
    return PermissionRule.model_validate(data)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "permissions.yaml"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_defaults_file_loads_and_covers_table() -> None:
    defaults = load_defaults()

    cells = {(rule.role, rule.tool, rule.effect) for rule in defaults.rules}
    missing = [cell for cell in TABLE if cell not in cells]
    assert missing == []
    assert [a.name for a in defaults.protected_actions] == list(DEFAULT_PROTECTED_ACTIONS)
    assert all(a.approver is Approver.USER for a in defaults.protected_actions)
    global_denies = [r for r in defaults.rules if r.role is R.SCRUM_MASTER and r.tool == "bash"]
    assert [r.effect for r in global_denies] == [DENY]
    assert r"\bcurl\b" in global_denies[0].command_patterns
    merged = merge_narrowing(defaults, PermissionsFile()).rules
    assert {(r.role, r.tool, r.effect) for r in merged} == cells


def test_project_can_add_deny(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "rules:\n  - {role: SENIOR_DEV, tool: bash, effect: DENY, command_patterns: ['^npm']}\n",
    )

    merged = merge_narrowing(load_defaults(), load_project_rules(path))

    deny = _rule(R.SENIOR_DEV, "bash", DENY, command_patterns=["^npm"])
    assert deny in merged.rules
    approval = PermissionsFile(rules=[_rule(R.QC, "bash", APPROVAL)])
    assert _rule(R.QC, "bash", APPROVAL) in merge_narrowing(load_defaults(), approval).rules


def test_project_cannot_widen_with_new_allow(tmp_path: Path) -> None:
    widen = load_project_rules(
        _write(tmp_path, "rules:\n  - {role: QC, tool: edit, effect: ALLOW}\n")
    )

    with pytest.raises(ConfigError, match="widens"):
        merge_narrowing(load_defaults(), widen)


def test_project_allow_restatement_narrows_patterns() -> None:
    defaults = load_defaults()
    dev_bash = next(
        r
        for r in defaults.rules
        if r.role is R.SENIOR_DEV and r.tool == "bash" and r.effect is ALLOW
    )
    same = PermissionsFile(rules=[dev_bash.model_copy()])
    narrower_paths = PermissionsFile(
        rules=[_rule(R.SENIOR_DEV, "write", ALLOW, path_patterns=["Assets/**"])]
    )

    merged = merge_narrowing(defaults, same)
    narrowed = merge_narrowing(defaults, narrower_paths)

    def bash_rows(rules: list[PermissionRule]) -> list[str]:
        return sorted(
            r.model_dump_json() for r in rules if r.role is R.SENIOR_DEV and r.tool == "bash"
        )

    assert bash_rows(merged.rules) == bash_rows(defaults.rules)
    writes = [r for r in narrowed.rules if r.role is R.SENIOR_DEV and r.tool == "write"]
    assert [r.path_patterns for r in writes] == [["Assets/**"]]
    with pytest.raises(ConfigError, match="adds patterns"):
        merge_narrowing(
            defaults,
            PermissionsFile(rules=[_rule(R.SENIOR_DEV, "bash", ALLOW, command_patterns=[".*"])]),
        )
    with pytest.raises(ConfigError, match="adds patterns"):
        merge_narrowing(defaults, PermissionsFile(rules=[_rule(R.SENIOR_DEV, "bash", ALLOW)]))


def test_default_protected_actions_cannot_be_removed() -> None:
    defaults = load_defaults()
    without_store = PermissionsFile(
        rules=defaults.rules,
        protected_actions=[a for a in defaults.protected_actions if a.name != "store.publish"],
    )
    relaxed = PermissionsFile(
        protected_actions=[ProtectedAction(name="store.publish", approver=Approver.LEAD_DEV)]
    )

    with pytest.raises(ConfigError, match=r"store\.publish"):
        merge_narrowing(without_store, PermissionsFile())
    with pytest.raises(ConfigError, match="cannot be redefined"):
        merge_narrowing(defaults, relaxed)
    restated = PermissionsFile(protected_actions=[ProtectedAction(name="store.publish")])
    names = [a.name for a in merge_narrowing(defaults, restated).protected_actions]
    assert names == list(DEFAULT_PROTECTED_ACTIONS)


def test_bootstrap_narrowing_file_and_absent_file_narrow_nothing(tmp_path: Path) -> None:
    bootstrapped = _write(
        tmp_path,
        "# Project narrowing of the kernel permission defaults (ADR-0006 D-6).\n"
        "# Rules may only add DENY/REQUIRE_APPROVAL or restate a default ALLOW (E02-S10).\n"
        "rules: []\nprotected_actions: []\n",
    )

    for project in (load_project_rules(bootstrapped), load_project_rules(tmp_path / "absent")):
        assert project == PermissionsFile()
    assert load_project_rules(_write(tmp_path, "")) == PermissionsFile()


@pytest.mark.parametrize(
    "text",
    [
        "rules: [unclosed\n",
        "- a list\n",
        "rules: []\nextra: 1\n",
        "rules: {}\n",
        "rules:\n  - just-a-string\n",
        "rules:\n  - {tool: bash, effect: DENY}\n",
        "rules:\n  - {role: QC, roles: [QC], tool: bash, effect: DENY}\n",
        "rules:\n  - {role: QC, tools: [], effect: DENY}\n",
        "rules:\n  - {role: NOBODY, tool: bash, effect: DENY}\n",
        "rules:\n  - {role: QC, tool: bash, effect: REQUIRE_APPROVAL}\n",
        "protected_actions:\n  - {approver: USER}\n",
    ],
)
def test_invalid_project_files_are_rejected(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        load_project_rules(_write(tmp_path, text))
