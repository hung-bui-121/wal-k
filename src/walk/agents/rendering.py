"""Kernel-owned prompt assembly (ADR-0004 D-4; ADR-0013 D-3; §126 input order).

`TemplateRenderer` renders the versioned task templates `templates/<purpose>.md.j2`; a project
template in `.ai/agents/templates/` shadows the kernel one. `render_constitution` produces the
system-prompt part of a role and `render_input_sections` the §126 user-message sections.
"""

import json
import re
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Final

import jinja2
from pydantic import BaseModel

from walk.agents.models import AgentInput, Constitution
from walk.common.errors import ConfigError

TEMPLATE_PURPOSES: tuple[str, ...] = (
    "IMPLEMENT",
    "DESIGN",
    "REVIEW",
    "QC",
    "TRIAGE",
    "DEBATE",
    "PLAN",
    "ANALYSIS",
    "RETRO",
)
INPUT_SECTION_ORDER: tuple[str, ...] = (
    "Agent Role",
    "Constitution",
    "Authority",
    "Task",
    "Workflow State",
    "Relevant Context",
    "Approved Artifacts",
    "Relevant Decisions",
    "Available Skills",
    "Allowed Tools",
    "Permissions",
    "Budget",
    "Effort",
    "Required Evidence",
    "Expected Output",
    "Handover",
)  # §126 order; "Handover" only when present

_TEMPLATE_SUFFIX: Final = ".md.j2"
_VERSION_RE: Final = re.compile(r"^\{#\s*version:\s*([0-9]+(?:\.[0-9]+)*)\s*#\}\s*$")
_VERIFY_MARKER: Final = "> VERIFY AGAINST SOURCE BEFORE RELYING ON THIS"
_PROJECT_HEADING: Final = "Project Constitution"
_H2: Final = "## "
_FENCE: Final = "```"
_DEMOTE_BY: Final = "##"  # `#` → `###`, `####` → `######` (the deepest Markdown level)
_DEMOTABLE_HEADING: Final = re.compile(r"^#{1,4} ")


class TemplateRenderer:
    """Renders `templates/<purpose>.md.j2` with jinja2 (strict: undefined variables fail)."""

    def __init__(self, templates_dir: Path, project_templates_dir: Path | None = None) -> None:
        """Load kernel templates from ``templates_dir``; project ones shadow them.

        Args:
            templates_dir: Kernel templates (`walk/agents/templates`).
            project_templates_dir: `.ai/agents/templates`; ``None`` or missing = none.
        """
        search = [templates_dir]
        if project_templates_dir is not None and project_templates_dir.is_dir():
            search.insert(0, project_templates_dir)
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(search),
            autoescape=False,  # noqa: S701 - Markdown prompts, never HTML
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, purpose: str, **context: object) -> str:
        """Render the template of ``purpose`` with ``context`` (``purpose`` is added to it).

        Raises:
            ConfigError: Unknown purpose, missing template, or an undefined variable.
        """
        template = self._template(purpose)
        try:
            return template.render(**context, purpose=purpose)
        except jinja2.UndefinedError as exc:
            msg = f"template {purpose} uses an undefined variable: {exc.message}"
            raise ConfigError(msg, detail={"purpose": purpose}) from exc

    def version_of(self, purpose: str) -> str:
        """The version from the template's first line ``{# version: x.y #}``.

        Raises:
            ConfigError: Unknown purpose, missing template, or no version line.
        """
        template = self._template(purpose)
        source = Path(template.filename or "").read_text(encoding="utf-8")
        match = _VERSION_RE.match(source.split("\n", 1)[0])
        if match is None:
            msg = f"template {purpose} has no '{{# version: x.y #}}' first line"
            raise ConfigError(msg, detail={"purpose": purpose, "path": template.filename})
        return match.group(1)

    def _template(self, purpose: str) -> jinja2.Template:
        if purpose not in TEMPLATE_PURPOSES:
            msg = f"unknown template purpose: {purpose}"
            raise ConfigError(msg, detail={"purpose": purpose, "known": list(TEMPLATE_PURPOSES)})
        try:
            return self._env.get_template(purpose + _TEMPLATE_SUFFIX)
        except jinja2.TemplateNotFound as exc:
            msg = f"template for purpose {purpose} not found"
            raise ConfigError(msg, detail={"purpose": purpose}) from exc


def render_constitution(
    constitution: Constitution, project_constitution_markdown: str | None
) -> str:
    """Render ``constitution`` (and the project constitution) as the role's system prompt.

    One ``##`` section per ADR-0013 D-3 heading, in order: the structured front-matter facts
    as bullets, then the matching body prose. Other body sections (e.g. Working Guidance)
    follow in body order, then ``## Project Constitution`` when given. Byte-stable.
    """
    c = constitution
    a = c.authority
    facts: dict[str, list[str]] = {
        "Identity": [f"role: {c.role.value}", f"identity: {c.identity}", f"version: {c.version}"],
        "Mission": [c.mission],
        "Responsibilities": list(c.responsibilities),
        "Authority": [
            f"decision_scope: {_join(a.decision_scope)}",
            f"max_autonomy_level: {int(a.max_autonomy_level)}",
            f"may_approve: {_join(a.may_approve)}",
            f"may_reject: {_join(a.may_reject)}",
            f"may_create_work: {_join(a.may_create_work)}",
        ],
        "Professional Bias": [c.professional_bias],
        "Core Beliefs": list(c.core_beliefs),
        "Decision Principles": list(c.decision_principles),
        "Risk Tolerance": [c.risk_tolerance],
        "Preferred Evidence": [kind.value for kind in c.preferred_evidence],
        "Conflict Behavior": [c.conflict_behavior],
        "Escalation Rules": [
            f"{rule.condition} → level {int(rule.to_level)}"
            + (f" ({rule.category.value})" if rule.category is not None else "")
            for rule in c.escalation_rules
        ],
        "Forbidden Actions": list(c.forbidden_actions),
    }
    prose = _split_sections(c.body_markdown)
    parts = [f"# {c.identity}"]
    for heading, bullets in facts.items():
        body = "\n".join(f"- {line}" for line in bullets) if bullets else "- none"
        extra = prose.pop(heading, "")
        parts.append(f"{_H2}{heading}\n\n{body}" + (f"\n\n{extra}" if extra else ""))
    parts.extend(
        f"{_H2}{heading}\n\n{body}" if body else f"{_H2}{heading}"
        for heading, body in prose.items()
    )
    if project_constitution_markdown is not None:
        parts.append(f"{_H2}{_PROJECT_HEADING}\n\n{project_constitution_markdown.strip()}")
    return "\n\n".join(parts) + "\n"


def render_input_sections(agent_input: AgentInput) -> str:
    """Render ``agent_input`` as §126 sections in `INPUT_SECTION_ORDER`.

    Models and lists are fenced JSON (sorted keys); role and effort are plain text; context
    items become ``### <kind> <id>`` blocks in bundle order, stale ones marked for
    verification. ``## Handover`` appears only when a handover is present.
    """
    i = agent_input
    sections: dict[str, str] = {
        "Agent Role": i.role.value,
        "Constitution": _json(i.constitution),
        "Authority": _json(i.authority),
        "Task": _json(i.task) + (f"\n\n### Debate\n\n{_json(i.debate)}" if i.debate else ""),
        "Workflow State": _json(
            {
                "state": i.workflow_state,
                "phase": i.phase,
                "run_id": i.run_id,
                "branch": i.branch,
                "worktree_path": i.worktree_path,
            }
        ),
        "Relevant Context": _context_section(i),
        "Approved Artifacts": _json(i.approved_artifacts),
        "Relevant Decisions": _json(i.decisions),
        "Available Skills": _json(i.skills),
        "Allowed Tools": _json(i.allowed_tools),
        "Permissions": _json(i.permissions),
        "Budget": _json(i.budget),
        "Effort": i.effort.value,
        "Required Evidence": _json(i.required_evidence),
        "Expected Output": _json(i.expected_output),
    }
    if i.handover is not None:
        sections["Handover"] = _json(i.handover)
    ordered = [name for name in INPUT_SECTION_ORDER if name in sections]
    return "\n\n".join(f"{_H2}{name}\n\n{sections[name]}" for name in ordered) + "\n"


def _context_section(agent_input: AgentInput) -> str:
    bundle = agent_input.context
    blocks = [f"head_commit: {bundle.head_commit}"]
    for item in bundle.items:
        header = f"### {item.kind.value} {item.id}"
        marker = f"{_VERIFY_MARKER}\n\n" if item.requires_verification else ""
        blocks.append(f"{header}\n\n{marker}{_demote_headings(item.content)}")
    return "\n\n".join(blocks)


def _json(value: object) -> str:
    return f"```json\n{json.dumps(_plain(value), sort_keys=True, indent=2)}\n```"


def _plain(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _demote_headings(markdown: str) -> str:
    # Item contents are whole documents; their headings must nest below `### <kind> <id>`
    # so that the `##` section structure of the message stays unambiguous.
    lines: list[str] = []
    in_fence = False
    for line in markdown.split("\n"):
        if line.lstrip().startswith(_FENCE):
            in_fence = not in_fence
        elif not in_fence and _DEMOTABLE_HEADING.match(line):
            line = _DEMOTE_BY + line  # noqa: PLW2901 - rewriting the line is the point
        lines.append(line)
    return "\n".join(lines)


def _join(values: Sequence[str]) -> str:
    return ", ".join(str(v) for v in values) or "none"


def _split_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith(_H2):
            if current is not None:
                sections[current] = "\n".join(lines).strip("\n")
            current, lines = line.removeprefix(_H2).strip(), []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip("\n")
    return sections
