from pathlib import Path

import pytest

import walk.agents
import walk.skills
from walk.agents import AgentOutput, PolicyLoader
from walk.common.enums import LearningScope
from walk.common.roles import AgentRole
from walk.skills.loader import discover_skill_dirs, parse_skill_file

BUILTIN = Path(walk.skills.__file__).resolve().parent / "builtin"
POLICIES = Path(walk.agents.__file__).resolve().parent / "defaults" / "policies.yaml"
MVP_ROLES = {AgentRole.ORCHESTRATOR, AgentRole.LEAD_DEV, AgentRole.SENIOR_DEV, AgentRole.QC}
MAX_BODY_BYTES = 4096
DEFAULT_SKILLS = {
    AgentRole.ORCHESTRATOR: ["walk-output-contract"],
    AgentRole.LEAD_DEV: [
        "walk-output-contract",
        "code-review-checklist",
        "unity-csharp-conventions",
        "git-hygiene",
    ],
    AgentRole.SENIOR_DEV: ["walk-output-contract", "unity-csharp-conventions", "git-hygiene"],
    AgentRole.QC: ["walk-output-contract", "qc-exploratory-testing", "git-hygiene"],
}
ROLES = {
    "walk-output-contract": MVP_ROLES,
    "unity-csharp-conventions": {AgentRole.SENIOR_DEV, AgentRole.LEAD_DEV},
    "git-hygiene": {AgentRole.SENIOR_DEV, AgentRole.LEAD_DEV, AgentRole.QC},
    "qc-exploratory-testing": {AgentRole.QC},
    "code-review-checklist": {AgentRole.LEAD_DEV},
}


def test_builtin_skills_size_and_contract_coverage() -> None:
    skills = {skill.name: skill for skill in map(parse_skill_file, _skill_files())}

    assert set(skills) == set(ROLES)
    for name, skill in skills.items():
        assert len(skill.body_markdown.encode("utf-8")) <= MAX_BODY_BYTES, name
        assert skill.scope is LearningScope.KERNEL, name
        assert skill.version == "1.0", name
        assert set(skill.applies_to_roles) == ROLES[name], name
        assert skill.requires_tools == [], name
    contract = skills["walk-output-contract"].body_markdown
    missing = [field for field in AgentOutput.model_fields if f"`{field}`" not in contract]
    assert missing == []
    assert ".walk/output.json" in contract
    assert ".ai/" in contract


@pytest.mark.parametrize("role", sorted(DEFAULT_SKILLS))
def test_policies_name_the_builtin_default_skills(role: AgentRole) -> None:
    policy = PolicyLoader(POLICIES, None).load(role)

    assert policy.default_skills == DEFAULT_SKILLS[role]


def test_qc_skill_lists_the_section_65_questions() -> None:
    body = parse_skill_file(BUILTIN / "qc-exploratory-testing" / "SKILL.md").body_markdown

    for question in ("taps rapidly", "app pauses", "FPS drops", "network interrupts"):
        assert question in body
    for severity in ("BLOCKER", "MAJOR", "MINOR", "TRIVIAL"):
        assert severity in body


def _skill_files() -> list[Path]:
    return [directory / "SKILL.md" for directory in discover_skill_dirs(BUILTIN)]
