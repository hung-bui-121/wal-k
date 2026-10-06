"""Initial project documents written by `walk bootstrap` (§24, §36; E02-S03, ADR-0020 D-3).

Pure builders: they return unwritten `MemoryDocument`s; the bootstrapper writes them through
`MemoryManager.write`, which stamps version and freshness.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Final

from walk.common.ids import ProjectKey
from walk.common.models import Actor
from walk.memory.models import FrontMatter, MemoryDocType, MemoryDocument
from walk.memory.paths import doc_path_for
from walk.memory.sections import skeleton_for

_PROJECT_ID: Final = "project"
_CONSTITUTION_ID: Final = "constitution"
_CONSTITUTION_SECTIONS: Final = ("Product Authority", "Constraints", "Quality Bar", "Forbidden")
_GOALS: Final = "Goals"
_NO_GDD: Final = "- (no GDD provided)"
_NO_HEADINGS: Final = "- (no headings found in the GDD)"
_HEADING: Final = re.compile(r"^(#{1,2})\s+(.+?)\s*#*\s*$")


def project_skeleton(  # noqa: PLR0917 - positional signature fixed by the E02-S03 contract
    project_key: ProjectKey,
    name: str,
    gdd_paths: list[str],
    gdd_headings: list[str],
    actor: Actor,
    now: datetime,
) -> MemoryDocument:
    """`.ai/project/project.md` with every §36 section; ``Goals`` is seeded from the GDD.

    Args:
        project_key: Project the document belongs to (``extra["project_key"]``).
        name: Project name, used as the title.
        gdd_paths: GDD files relative to the repository root (``related.gdd``).
        gdd_headings: Markdown H1/H2 heading lines of those files, in reading order
            (``"# Combat"``, ``"## Shotgun"``).
        actor: Author of the document.
        now: Creation time.

    Returns:
        The unwritten document. ``Goals`` holds one bullet per top-level heading (the H1
        headings, or the H2 headings when the GDD has no H1), ``- (no GDD provided)`` without
        GDD files, and ``- (no headings found in the GDD)`` when the files have no heading.
    """
    doc = skeleton_for(MemoryDocType.PROJECT, _PROJECT_ID, name, actor, now)
    front_matter = doc.front_matter.model_copy(
        update={
            "related": doc.front_matter.related.model_copy(update={"gdd": list(gdd_paths)}),
            "extra": {"project_key": project_key},
        }
    )
    sections = dict(doc.sections)
    sections[_GOALS] = _goals(gdd_paths, gdd_headings)
    return doc.model_copy(update={"front_matter": front_matter, "sections": sections})


def project_constitution_skeleton(
    project_key: ProjectKey, name: str, actor: Actor, now: datetime
) -> MemoryDocument:
    """`.ai/project/constitution.md` (§24) with its four sections, empty.

    The sections are Product Authority, Constraints, Quality Bar and Forbidden.

    Args:
        project_key: Project the document belongs to (``extra["project_key"]``).
        name: Project name; the title is ``<name> constitution``.
        actor: Author of the document.
        now: Creation time.

    Returns:
        The unwritten document.
    """
    doc_type = MemoryDocType.PROJECT_CONSTITUTION
    front_matter = FrontMatter(
        id=_CONSTITUTION_ID,
        type=doc_type,
        title=f"{name} constitution",
        created_at=now,
        updated_at=now,
        updated_by=actor,
        extra={"project_key": project_key},
    )
    return MemoryDocument(
        path=doc_path_for(Path(), doc_type, _CONSTITUTION_ID).as_posix(),
        front_matter=front_matter,
        sections=dict.fromkeys(_CONSTITUTION_SECTIONS, ""),
        raw_sha256="",
    )


def _goals(gdd_paths: list[str], gdd_headings: list[str]) -> str:
    if not gdd_paths:
        return _NO_GDD
    parsed = [m.groups() for line in gdd_headings if (m := _HEADING.match(line.strip()))]
    if not parsed:
        return _NO_HEADINGS
    top = min(len(hashes) for hashes, _ in parsed)
    return "\n".join(f"- {title}" for hashes, title in parsed if len(hashes) == top)
