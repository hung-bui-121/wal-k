"""Projection drift against the lock (ADR-0007 D-3; E02-S07). Pure: reads nothing itself."""

from collections.abc import Mapping

from walk.skills.models import DriftReport, Skill, SkillProjection


def compute_drift(
    canonical: list[Skill], lock: list[SkillProjection], on_disk: Mapping[str, str | None]
) -> DriftReport:
    """Compare one provider's locked projections with the canonical skills and the disk.

    ``on_disk`` maps ``<target_path>#<skill>`` (the target file, anchored to the skill's
    projected content: the whole file for Claude, its ``AGENTS.md`` sub-section for Codex) to
    the sha256 of that content on disk, or ``None`` when it is absent. Keys of skills found on
    disk but not locked may carry any target before the ``#``.

    - missing  = canonical skills with no lock entry, or whose locked content is absent;
    - modified = lock entries whose on-disk sha differs from ``content_sha256``, or whose
      ``generated_from_sha256`` differs from the canonical skill's sha;
    - orphaned = skill names locked or found on disk that have no canonical skill.

    Lists are sorted and free of duplicates; ``ok`` when all three are empty.
    """
    skills = {skill.name: skill for skill in canonical}
    locked = {entry.skill for entry in lock}
    missing = {name for name in skills if name not in locked}
    modified: set[str] = set()
    orphaned: set[str] = set()
    for entry in lock:
        skill = skills.get(entry.skill)
        if skill is None:
            orphaned.add(entry.skill)
            continue
        current = on_disk.get(_key(entry))
        if current is None:
            missing.add(entry.skill)
        elif current != entry.content_sha256 or entry.generated_from_sha256 != (
            skill.content_sha256
        ):
            modified.add(entry.skill)
    for key, sha in on_disk.items():
        name = key.rpartition("#")[2]
        if sha is not None and name not in skills:
            orphaned.add(name)
    modified -= missing
    return DriftReport(
        missing=sorted(missing),
        modified=sorted(modified),
        orphaned=sorted(orphaned),
        ok=not (missing or modified or orphaned),
    )


def _key(projection: SkillProjection) -> str:
    return f"{projection.target_path}#{projection.skill}"
