import re
from pathlib import Path

import pytest

import walk.agents
from tests.agents.conftest import make_story
from walk.agents import (
    TEMPLATE_PURPOSES,
    AgentOutputStatus,
    ExpectedOutput,
    Handover,
    TemplateRenderer,
)
from walk.common.errors import ConfigError

TEMPLATES = Path(walk.agents.__file__).resolve().parent / "templates"
PROVIDERS = re.compile(r"\b(claude|codex|gpt|anthropic|openai)", re.IGNORECASE)


def _context(handover: Handover | None = None) -> dict[str, object]:
    return {
        "item": make_story(),
        "agent": None,
        "expected_output": ExpectedOutput(
            status_options=[AgentOutputStatus.COMPLETED, AgentOutputStatus.PARTIAL],
            deliverables=["passing EditMode tests"],
            required_evidence=[],
        ),
        "handover": handover,
    }


def test_all_purpose_templates_render(handover: Handover) -> None:
    renderer = TemplateRenderer(TEMPLATES)

    for purpose in TEMPLATE_PURPOSES:
        text = renderer.render(purpose, **_context())
        assert text.strip()
        assert ".walk/output.json" in text
        assert text.startswith(f"# Task: {purpose} STORY-0001 — Run with shift")
        assert "## How to work" in text
        assert "## Deliverables" in text
        assert "- passing EditMode tests" in text
        assert "## Output contract" in text
        assert "## Handover" not in text
        assert not PROVIDERS.search(text)
        assert renderer.version_of(purpose) == "1.0"
    with_handover = renderer.render("IMPLEMENT", **_context(handover))
    assert "## Handover" in with_handover
    assert "Create the run blend tree." in with_handover
    assert sorted(p.name for p in TEMPLATES.glob("*.md.j2")) == sorted(
        f"{p}.md.j2" for p in TEMPLATE_PURPOSES
    )


def test_project_template_shadows_kernel(tmp_path: Path) -> None:
    (tmp_path / "IMPLEMENT.md.j2").write_text(
        "{# version: 1.1 #}\nProject prompt for {{ item.id }}\n", encoding="utf-8"
    )
    renderer = TemplateRenderer(TEMPLATES, tmp_path)

    text = renderer.render("IMPLEMENT", **_context())

    assert text == "Project prompt for STORY-0001\n"
    assert renderer.version_of("IMPLEMENT") == "1.1"
    assert renderer.version_of("REVIEW") == "1.0"
    assert ".walk/output.json" in renderer.render("REVIEW", **_context())


def test_render_rejects_unknown_purpose_or_variable(tmp_path: Path) -> None:
    renderer = TemplateRenderer(TEMPLATES)

    with pytest.raises(ConfigError, match="NOPE"):
        renderer.render("NOPE", **_context())
    with pytest.raises(ConfigError, match="NOPE"):
        renderer.version_of("NOPE")
    with pytest.raises(ConfigError, match="undefined"):
        renderer.render("IMPLEMENT", item=make_story())

    (tmp_path / "QC.md.j2").write_text("no version line\n", encoding="utf-8")
    shadowed = TemplateRenderer(TEMPLATES, tmp_path)
    with pytest.raises(ConfigError, match="version"):
        shadowed.version_of("QC")


def test_missing_template_file_is_a_config_error(tmp_path: Path) -> None:
    renderer = TemplateRenderer(tmp_path / "empty")

    with pytest.raises(ConfigError, match="not found"):
        renderer.render("QC", **_context())
