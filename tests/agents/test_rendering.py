import json
import re

from tests.agents.conftest import DEFAULTS
from walk.agents import (
    INPUT_SECTION_ORDER,
    AgentInput,
    ConstitutionLoader,
    render_constitution,
    render_input_sections,
)
from walk.common.roles import AgentRole

D3_HEADINGS = [
    "Identity",
    "Mission",
    "Responsibilities",
    "Authority",
    "Professional Bias",
    "Core Beliefs",
    "Decision Principles",
    "Risk Tolerance",
    "Preferred Evidence",
    "Conflict Behavior",
    "Escalation Rules",
    "Forbidden Actions",
]
PROVIDERS = re.compile(r"\b(claude|codex|gpt|anthropic|openai)", re.IGNORECASE)


def _h2(text: str) -> list[str]:
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


def test_render_constitution_is_deterministic_and_ordered() -> None:
    constitution = ConstitutionLoader(DEFAULTS, None).load(AgentRole.LEAD_DEV)

    first = render_constitution(constitution, None)
    second = render_constitution(constitution, None)

    assert first == second
    assert _h2(first) == D3_HEADINGS
    assert "- decision_scope: TECH" in first
    assert "- Functional does not mean finished." in first
    assert "Protect long-term technical integrity so that" in first
    assert first.endswith("\n")
    assert not PROVIDERS.search(first)


def test_render_constitution_appends_project_constitution_and_guidance() -> None:
    constitution = ConstitutionLoader(DEFAULTS, None).load(AgentRole.QC)
    constitution = constitution.model_copy(
        update={"body_markdown": constitution.body_markdown + "\n\n## Working Guidance\n\nBe kind."}
    )

    text = render_constitution(constitution, "Ship on mobile first.\n")

    headings = _h2(text)
    assert headings[-2:] == ["Working Guidance", "Project Constitution"]
    assert text.rstrip().endswith("Ship on mobile first.")


def test_render_input_sections_order_and_markers(agent_input: AgentInput) -> None:
    text = render_input_sections(agent_input)

    assert _h2(text) == list(INPUT_SECTION_ORDER)
    assert _h2(text)[-1] == "Handover"
    assert "> VERIFY AGAINST SOURCE BEFORE RELYING ON THIS" in text
    context = text.split("## Relevant Context", 1)[1].split("\n## ", 1)[0]
    assert context.index("### WORK_ITEM WORK_ITEM:STORY-0001") < context.index(
        "### FEATURE_CONTEXT FEATURE_CONTEXT:FEAT-0001"
    )
    marker = context.index("> VERIFY AGAINST SOURCE")
    assert marker > context.index("### FEATURE_CONTEXT")
    effort = text.split("## Effort\n\n", 1)[1].split("\n", 1)[0]
    assert effort == "MEDIUM"
    task_json = text.split("## Task\n\n```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(task_json)["id"] == "STORY-0001"
    assert render_input_sections(agent_input) == text


def test_render_input_sections_without_handover(agent_input: AgentInput) -> None:
    text = render_input_sections(agent_input.model_copy(update={"handover": None}))

    assert _h2(text) == list(INPUT_SECTION_ORDER[:-1])


def test_context_headings_are_demoted_outside_code(agent_input: AgentInput) -> None:
    item = agent_input.context.items[1].model_copy(
        update={"content": "# Title\n\n## Intent\n\n```text\n## not a heading\n```\n##### deep"}
    )
    bundle = agent_input.context.model_copy(update={"items": [item]})

    text = render_input_sections(agent_input.model_copy(update={"context": bundle}))

    assert "### Title" in text
    assert "#### Intent" in text
    assert "\n## not a heading\n" in text
    assert "\n##### deep" in text
