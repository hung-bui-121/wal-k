"""`Handover` ↔ `.ai/handovers/HO-NNNN.md` document conversion (§22; ADR-0003 D-5, ADR-0004 D-5).

The document is readable Markdown and converts back losslessly: scalar fields live in the front
matter's ``extra``, list fields are ``- `` bullets (continuation lines indented by two spaces),
and the structured findings and proposed decisions are kept as fenced JSON blocks next to their
human-readable bullets. Text fields round-trip unless they start or end with blank lines or
contain a line starting with ``## `` (both change the Markdown section structure).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Final, get_args

from pydantic import TypeAdapter, ValidationError

from walk.agents.models import Finding, Handover
from walk.common.errors import ConfigError
from walk.common.models import Actor, JsonDict
from walk.decisions.models import DecisionProposal
from walk.memory.models import FrontMatter, MemoryDocType, MemoryDocument, RelatedLinks
from walk.memory.paths import doc_path_for

HANDOVER_SECTION_FIELDS: tuple[
    tuple[str, str], ...
] = (  # §22 H2 heading → Handover field, in SECTION_ORDER[HANDOVER] order
    ("Task", "task_summary"),
    ("Current State", "current_state"),
    ("Completed Work", "completed_work"),
    ("Modified Files", "modified_files"),
    ("Findings", "findings"),
    ("Hypotheses", "hypotheses"),
    ("Decisions", "decisions"),
    ("Risks", "risks"),
    ("Remaining Work", "remaining_work"),
    ("Next Action", "next_action"),
)

_SCALAR_KEYS: Final = (
    "work_item_id",
    "role",
    "from_run_id",
    "from_model_id",
    "to_run_id",
    "reason",
    "worktree_head",
    "branch",
    "created_at",
)
_OPTIONAL_KEYS: Final = frozenset({"to_run_id"})
_TEXT_FIELDS: Final = frozenset({"task_summary", "current_state", "next_action"})
_REASONS: Final = get_args(Handover.model_fields["reason"].annotation)
_NONE: Final = "(none)"
_BULLET: Final = "- "
_CONTINUATION: Final = "  "
_FENCE_OPEN: Final = "```json"
_FENCE_CLOSE: Final = "```"
_PROPOSED_LABEL: Final = "Proposed decisions:"
_FINDINGS: Final = TypeAdapter(list[Finding])
_PROPOSALS: Final = TypeAdapter(list[DecisionProposal])


def to_document(handover: Handover, *, actor: Actor, now: datetime) -> MemoryDocument:
    """Render ``handover`` as an unwritten HANDOVER document.

    ``freshness`` is left for `MemoryManager.write` to stamp; ``related.work_items`` and
    ``extra["work_item_id"]``/``extra["reason"]`` carry the item (E01-S16 convention).
    """
    data = handover.model_dump(mode="json")
    extra: JsonDict = {key: data[key] for key in _SCALAR_KEYS}
    front_matter = FrontMatter(
        id=handover.id,
        type=MemoryDocType.HANDOVER,
        title=f"Handover {handover.id} for {handover.work_item_id}",
        created_at=now,
        updated_at=now,
        updated_by=actor,
        related=RelatedLinks(work_items=[handover.work_item_id], decisions=handover.decisions),
        extra=extra,
    )
    sections = {
        "Task": handover.task_summary,
        "Current State": handover.current_state,
        "Completed Work": _bullets(handover.completed_work),
        "Modified Files": _bullets(handover.modified_files),
        "Findings": _findings_section(handover.findings),
        "Hypotheses": _bullets(handover.hypotheses),
        "Decisions": _decisions_section(handover),
        "Risks": _bullets(handover.risks),
        "Remaining Work": _bullets(handover.remaining_work),
        "Next Action": handover.next_action,
    }
    path = doc_path_for(Path(), MemoryDocType.HANDOVER, handover.id).as_posix()
    return MemoryDocument(path=path, front_matter=front_matter, sections=sections, raw_sha256="")


def from_document(doc: MemoryDocument) -> Handover:
    """Rebuild the `Handover` that `to_document` rendered.

    Raises:
        ConfigError: The document is not a handover, a front-matter key or section is missing,
            ``extra.reason`` is not a §22 reason, a JSON block is missing or invalid, or the
            values do not form a valid `Handover` (``detail["key"]`` names the culprit).
    """
    fm = doc.front_matter
    if fm.type is not MemoryDocType.HANDOVER:
        msg = f"not a handover document: {fm.id} has type {fm.type.value}"
        raise ConfigError(msg, detail={"doc_id": fm.id, "key": "type"})
    data: JsonDict = {"id": fm.id, **_scalars(fm.id, fm.extra)}
    for heading, field in HANDOVER_SECTION_FIELDS:
        if heading not in doc.sections:
            raise _missing(fm.id, heading, "section")
        data.update(_section_values(fm.id, heading, field, doc.sections[heading]))
    try:
        return Handover.model_validate(data)
    except ValidationError as exc:
        msg = f"handover {fm.id} is invalid: {exc.errors()[0]['msg']}"
        key = ".".join(str(part) for part in exc.errors()[0]["loc"])
        raise ConfigError(msg, detail={"doc_id": fm.id, "key": key}) from exc


def _scalars(doc_id: str, extra: JsonDict) -> JsonDict:
    values: JsonDict = {}
    for key in _SCALAR_KEYS:
        if key in extra:
            values[key] = extra[key]
        elif key not in _OPTIONAL_KEYS:
            raise _missing(doc_id, key, "front-matter key")
    if values["reason"] not in _REASONS:
        msg = f"handover {doc_id}: reason {values['reason']!r} is not one of {', '.join(_REASONS)}"
        raise ConfigError(msg, detail={"doc_id": doc_id, "key": "reason"})
    return values


def _section_values(doc_id: str, heading: str, field: str, body: str) -> JsonDict:
    if field in _TEXT_FIELDS:
        return {field: body}
    if field == "findings":
        return {field: _json_block(doc_id, heading, body)}
    if field == "decisions":
        return {
            field: _parse_bullets(body.split(_PROPOSED_LABEL, 1)[0]),
            "proposed_decisions": _json_block(doc_id, heading, body),
        }
    return {field: _parse_bullets(body)}


def _missing(doc_id: str, key: str, what: str) -> ConfigError:
    msg = f"handover {doc_id}: missing {what} {key!r}"
    return ConfigError(msg, detail={"doc_id": doc_id, "key": key})


def _bullets(values: list[str]) -> str:
    if not values:
        return _NONE
    return "\n".join(_BULLET + value.replace("\n", "\n" + _CONTINUATION) for value in values)


def _parse_bullets(body: str) -> list[str]:
    items: list[str] = []
    for line in body.strip("\n").split("\n"):
        if line.startswith(_BULLET):
            items.append(line.removeprefix(_BULLET))
        elif line.startswith(_CONTINUATION) and items:
            items[-1] += "\n" + line.removeprefix(_CONTINUATION)
    return items


def _fenced(payload: list[JsonDict]) -> str:
    return f"{_FENCE_OPEN}\n{json.dumps(payload, sort_keys=True, indent=2)}\n{_FENCE_CLOSE}"


def _findings_section(findings: list[Finding]) -> str:
    lines = [
        f"- **{f.summary}** — {f.detail}"
        + (f" (evidence: {', '.join(f.evidence_ids)})" if f.evidence_ids else "")
        for f in findings
    ]
    human = "\n".join(lines) if lines else _NONE
    return f"{human}\n\n{_fenced(_FINDINGS.dump_python(findings, mode='json'))}"


def _decisions_section(handover: Handover) -> str:
    proposals = _PROPOSALS.dump_python(handover.proposed_decisions, mode="json")
    return f"{_bullets(handover.decisions)}\n\n{_PROPOSED_LABEL}\n\n{_fenced(proposals)}"


def _json_block(doc_id: str, heading: str, body: str) -> object:
    start = body.find(_FENCE_OPEN + "\n")
    end = body.find("\n" + _FENCE_CLOSE, start + len(_FENCE_OPEN))
    if start < 0 or end < 0:
        msg = f"handover {doc_id}: section {heading!r} has no JSON block"
        raise ConfigError(msg, detail={"doc_id": doc_id, "key": heading})
    try:
        return json.loads(body[start + len(_FENCE_OPEN) + 1 : end])
    except json.JSONDecodeError as exc:
        msg = f"handover {doc_id}: section {heading!r} has invalid JSON"
        raise ConfigError(msg, detail={"doc_id": doc_id, "key": heading}) from exc
