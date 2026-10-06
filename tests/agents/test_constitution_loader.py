import shutil
from pathlib import Path

import pytest
import yaml

import walk.agents
from walk.agents import ConstitutionError, ConstitutionLoader
from walk.common.roles import AgentRole
from walk.decisions import AutonomyLevel, DecisionCategory

DEFAULTS = Path(walk.agents.__file__).resolve().parent / "defaults"
LEAD = AgentRole.LEAD_DEV


def _override(
    roles: Path, front: dict[str, object], body: str = "", name: str = "lead_dev"
) -> None:
    roles.mkdir(parents=True, exist_ok=True)
    header = yaml.safe_dump({"id": "LEAD_DEV", "type": "constitution", **front}, sort_keys=False)
    (roles / f"{name}.md").write_text(f"---\n{header}---\n{body}", encoding="utf-8")


def _default_rules() -> list[dict[str, object]]:
    rules = ConstitutionLoader(DEFAULTS, None).load(LEAD).tool_permissions
    return [r.model_dump(mode="json", exclude={"role"}, exclude_defaults=True) for r in rules]


def test_override_may_narrow(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    rules = _default_rules()
    _override(
        roles,
        {
            "authority": {"max_autonomy_level": 0},
            "tool_permissions": [r for r in rules if r["tool"] != "review.reject"],
            "forbidden_actions": [
                "approve own implementation",
                "close a feature without QC acceptance",
                "touch the save format",
            ],
            "mission": "Keep the save system sound.",
        },
    )
    constitution = ConstitutionLoader(DEFAULTS, roles).load(LEAD)
    assert constitution.authority.max_autonomy_level is AutonomyLevel.LOCAL
    assert constitution.authority.decision_scope == [DecisionCategory.TECH]
    assert "review.reject" not in {r.tool for r in constitution.tool_permissions}
    assert len(constitution.tool_permissions) == len(rules) - 1
    assert constitution.forbidden_actions[-1] == "touch the save format"
    assert constitution.mission == "Keep the save system sound."


def test_override_may_add_denies_and_approval_on_allowed_tools(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    extra = [
        {"tool": "git.push", "effect": "DENY"},
        {"tool": "git.commit", "effect": "REQUIRE_APPROVAL", "approver": "LEAD_DEV"},
    ]
    _override(roles, {"tool_permissions": [*_default_rules(), *extra]})
    constitution = ConstitutionLoader(DEFAULTS, roles).load(LEAD)
    assert len(constitution.tool_permissions) == len(_default_rules()) + 2


def test_override_widening_rejected(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    _override(roles, {"authority": {"decision_scope": ["TECH", "DESIGN"]}})
    with pytest.raises(ConstitutionError, match=r"authority\.decision_scope"):
        ConstitutionLoader(DEFAULTS, roles).load(LEAD)


@pytest.mark.parametrize(
    ("front", "field"),
    [
        ({"authority": {"max_autonomy_level": 3}}, "authority.max_autonomy_level"),
        ({"authority": {"may_approve": ["ART_DIRECTION"]}}, "authority.may_approve"),
        ({"authority": {"may_reject": ["qc.reject"]}}, "authority.may_reject"),
        ({"authority": {"may_create_work": ["EPIC"]}}, "authority.may_create_work"),
        ({"forbidden_actions": ["approve own implementation"]}, "forbidden_actions"),
        ({"tool_permissions": [{"tool": "store.publish", "effect": "ALLOW"}]}, "tool_permissions"),
        (
            {
                "tool_permissions": [
                    {"tool": "jira.delete", "effect": "REQUIRE_APPROVAL", "approver": "LEAD_DEV"}
                ]
            },
            "tool_permissions",
        ),
    ],
)
def test_every_narrow_only_field_rejects_widening(
    tmp_path: Path, front: dict[str, object], field: str
) -> None:
    roles = tmp_path / "roles"
    _override(roles, front)
    with pytest.raises(ConstitutionError, match=field.replace(".", r"\.")):
        ConstitutionLoader(DEFAULTS, roles).load(LEAD)


def test_override_body_sections_merge(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    body = "\n## Mission\n\nGuard the save format.\n\n## House Rules\n\nNo singletons.\n"
    _override(roles, {}, body)
    text = ConstitutionLoader(DEFAULTS, roles).load(LEAD).body_markdown
    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    assert headings[-1] == "House Rules"
    assert headings.count("Mission") == 1
    assert "Guard the save format." in text
    assert "Protect long-term technical integrity so that" not in text
    assert text.index("## Mission") < text.index("## Forbidden Actions")


def test_provider_names_rejected(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    _override(roles, {"core_beliefs": ["Claude writes the best code."]})
    with pytest.raises(ConstitutionError, match="core_beliefs"):
        ConstitutionLoader(DEFAULTS, roles).load(LEAD)
    _override(roles, {}, "\n## Working Guidance\n\nPrefer GPT-5 for refactors.\n")
    with pytest.raises(ConstitutionError, match="Working Guidance"):
        ConstitutionLoader(DEFAULTS, roles).load(LEAD)


def test_wrong_doc_type_rejected(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    _override(roles, {"type": "feature"})
    with pytest.raises(ConstitutionError, match="type"):
        ConstitutionLoader(DEFAULTS, roles).load(LEAD)


@pytest.mark.parametrize(
    "front",
    [{"id": "QC"}, {"role": "QC"}, {"mission": ["not", "a", "string"]}, {"unknown_field": 1}],
)
def test_override_must_describe_the_same_role(tmp_path: Path, front: dict[str, object]) -> None:
    roles = tmp_path / "roles"
    _override(roles, front)
    with pytest.raises(ConstitutionError):
        ConstitutionLoader(DEFAULTS, roles).load(LEAD)


def test_broken_default_file_rejected(tmp_path: Path) -> None:
    defaults = tmp_path / "defaults"
    shutil.copytree(DEFAULTS, defaults)
    (defaults / "qc.md").write_text("no front matter\n", encoding="utf-8")
    with pytest.raises(ConstitutionError, match=r"qc\.md"):
        ConstitutionLoader(defaults, None).load(AgentRole.QC)


def test_loader_caches_per_instance(tmp_path: Path) -> None:
    roles = tmp_path / "roles"
    loader = ConstitutionLoader(DEFAULTS, roles)
    first = loader.load(LEAD)
    _override(roles, {"mission": "Changed after first load."})
    assert loader.load(LEAD) is first
