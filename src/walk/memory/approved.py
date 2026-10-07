"""Approved artifacts on disk: payload hashing and the metadata document (§33; E02-S12).

An approved artifact is `.ai/approved/APR-NNNN.md` (metadata) plus the payload folder
`.ai/approved/APR-NNNN/`. Its ``content_sha256`` covers the payload files only, so a changed
payload is detected as drift (Invariant 10); the metadata document is not part of the hash.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Final

from walk.common.errors import ConfigError
from walk.common.models import Actor
from walk.memory.models import ApprovedArtifact, FrontMatter, MemoryDocType, MemoryDocument

APPROVED_DIR = "approved"

_NONE: Final = "- none"
_LENGTH_BYTES: Final = 8


def hash_payload(root: Path, payload_paths: list[str]) -> str:
    """SHA-256 over sorted (relative path, file bytes) pairs.

    Every pair is length-prefixed, so different splits of the same bytes hash differently.

    Raises:
        ConfigError: A payload path is missing.
    """
    digest = hashlib.sha256()
    for relative in sorted(payload_paths):
        file = root / relative
        if not file.is_file():
            msg = f"approved payload file missing: {relative}"
            raise ConfigError(msg, detail={"root": str(root), "path": relative})
        name = relative.encode("utf-8")
        data = file.read_bytes()
        for part in (name, data):
            digest.update(len(part).to_bytes(_LENGTH_BYTES, "big"))
            digest.update(part)
    return digest.hexdigest()


def approved_doc(artifact: ApprovedArtifact, actor: Actor, now: datetime) -> MemoryDocument:
    """The metadata document: type=approved, id=artifact.id.

    Sections: Summary, Scope, Related Requirements, Payload, Change History, plus the E01-S16
    schema of approved documents (Status, Scope, Version, Approved By, Related Requirements,
    Payload), which the renderer puts first. ``front_matter.extra`` = {kind, scope,
    approved_by, content_sha256, supersedes, change_request_decision}; ``approved_by`` is the
    approving role.
    """
    requirements = [
        f"- {ref.path}" + (f"#{ref.anchor}" if ref.anchor else "")
        for ref in artifact.related_requirements
    ]
    payload = [f"- {APPROVED_DIR}/{artifact.id}/{path}" for path in artifact.payload_paths]
    history = f"- v{artifact.version}: approved by {artifact.approved_by.role.value}"
    if artifact.supersedes is not None:
        history += f", supersedes {artifact.supersedes}"
    front = FrontMatter(
        id=artifact.id,
        type=MemoryDocType.APPROVED,
        title=artifact.title,
        status=artifact.status.value,
        created_at=now,
        updated_at=now,
        updated_by=actor,
        extra={
            "kind": artifact.kind.value,
            "scope": artifact.scope,
            "approved_by": artifact.approved_by.role.value,
            "content_sha256": artifact.content_sha256,
            "supersedes": artifact.supersedes,
            "change_request_decision": artifact.change_request_decision,
        },
    )
    return MemoryDocument(
        path=f"{APPROVED_DIR}/{artifact.id}.md",
        front_matter=front,
        sections={
            "Status": artifact.status.value,
            "Version": str(artifact.version),
            "Approved By": artifact.approved_by.role.value,
            "Summary": (
                f'{artifact.kind.value} "{artifact.title}" approved by '
                f"{artifact.approved_by.role.value} at {artifact.approved_at.isoformat()}."
            ),
            "Scope": artifact.scope,
            "Related Requirements": "\n".join(requirements) or _NONE,
            "Payload": "\n".join(payload) or _NONE,
            "Change History": history,
        },
        raw_sha256="",
    )
