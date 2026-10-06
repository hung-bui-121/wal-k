"""Parse and render `.ai/` Markdown documents (ARCHITECTURE §8.2; ADR-0003 D-2)."""

import hashlib
import re
from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from walk.common.errors import ConfigError
from walk.common.models import JsonDict
from walk.memory.models import FrontMatter, MemoryDocument
from walk.memory.sections import sections_for

_DELIMITER: Final = "---"
_H1: Final = "# "
_H2: Final = "## "
_FENCE: Final = re.compile(r"^\s*(```|~~~)")


def _fail(path: Path, problem: str) -> ConfigError:
    return ConfigError(f"{path.as_posix()}: {problem}", detail={"path": path.as_posix()})


def split_document(path: Path, text: str) -> tuple[JsonDict, dict[str, str]]:
    """Split ``text`` into its YAML front matter mapping and its H2 sections (no schema check).

    Before the first H2 only blank lines and an H1 title are allowed. ``## `` lines inside
    fenced code blocks are content. Sections keep file order. Used by `parse_document` and by
    loaders of documents with their own front-matter schema (constitutions, ADR-0013).

    Raises:
        ConfigError: If front matter is missing, unterminated, not valid YAML or not a mapping,
            text precedes the first section or a heading repeats.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != _DELIMITER:
        raise _fail(path, "missing front matter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == _DELIMITER)
    except StopIteration:
        raise _fail(path, "unterminated front matter") from None
    try:
        header = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise _fail(path, f"invalid front matter: {exc}") from exc
    if not isinstance(header, dict):
        raise _fail(path, "invalid front matter: not a mapping")
    return header, _sections(path, lines[end + 1 :])


def parse_document(path: Path, text: str) -> MemoryDocument:
    """Parse a memory document: `split_document` plus the `FrontMatter` schema.

    Args:
        path: Document path; stored as given (POSIX) and its stem must equal the id.
        text: File content.

    Raises:
        ConfigError: As `split_document`; also if the front matter does not match
            `FrontMatter` (unknown type included) or the id differs from the file stem.
    """
    header, sections = split_document(path, text)
    try:
        front_matter = FrontMatter.model_validate(header)
    except ValidationError as exc:
        raise _fail(path, f"invalid front matter: {exc}") from exc
    if front_matter.id != path.stem:
        raise _fail(path, f"id {front_matter.id!r} does not equal the file stem {path.stem!r}")
    raw = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return MemoryDocument(
        path=path.as_posix(), front_matter=front_matter, sections=sections, raw_sha256=raw
    )


def _sections(path: Path, body: list[str]) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    in_fence = False
    for line in body:
        if _FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and line.startswith(_H2):
            heading = line[len(_H2) :].strip()
            if heading in sections:
                raise _fail(path, f"duplicate section {heading!r}")
            current = sections.setdefault(heading, [])
        elif current is not None:
            current.append(line)
        elif line.strip() and not line.startswith(_H1):
            raise _fail(path, "text before the first section")
    return {heading: "\n".join(content).strip("\n") for heading, content in sections.items()}


def render_document(doc: MemoryDocument) -> str:
    """Render ``doc`` deterministically.

    Front matter is sorted-key block YAML; an H1 title follows; then the sections of the
    type's `SECTION_ORDER` that are present, then the other sections in their current order.
    """
    header = yaml.safe_dump(
        doc.front_matter.model_dump(mode="json"),
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
    )
    known = sections_for(doc.front_matter.type)
    order = [name for name in known if name in doc.sections]
    order += [name for name in doc.sections if name not in known]
    parts = [f"{_DELIMITER}\n{header}{_DELIMITER}\n\n{_H1}{doc.front_matter.title}\n"]
    for name in order:
        body = doc.sections[name].strip("\n")
        parts.append(f"\n{_H2}{name}\n" + (f"\n{body}\n" if body else ""))
    return "".join(parts)
