"""Default memory manager: the single write path for `.ai/` documents (ADR-0003 D-4)."""

import hashlib
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import ApprovedArtifactId, BugId, FeatureId, HandoverId, ProjectKey, Sha
from walk.common.models import Actor, JsonDict
from walk.common.roles import AgentRole
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.integrations.protocols import GitProvider
from walk.memory.approved import APPROVED_DIR, approved_doc, hash_payload
from walk.memory.errors import (
    ApprovalNotAuthorized,
    ApprovedWriteRefused,
    DocumentNotFound,
    SecretDetected,
)
from walk.memory.frontmatter import parse_document, render_document
from walk.memory.models import (
    ApprovalStatus,
    ApprovedArtifact,
    BugContext,
    ContextUpdate,
    FeatureContext,
    Freshness,
    FreshnessAssessment,
    FreshnessStatus,
    MemoryDocType,
    MemoryDocument,
    ProjectContext,
)
from walk.memory.paths import doc_path_for
from walk.memory.repository import (
    ApprovedArtifactRepository,
    MemoryIndexRepository,
    MemoryIndexRow,
)
from walk.memory.secrets import find_secrets
from walk.memory.sections import sections_for, skeleton_for
from walk.persistence import IdSequenceStore, UnitOfWork
from walk.telemetry.models import LedgerEvent, LedgerEventKind
from walk.telemetry.protocols import LedgerManager

logger = logging.getLogger(__name__)

_CHANGE_DECISION: Final = "change_request_decision"
_TMP_SUFFIX: Final = ".tmp"
_REPORTS: Final = "reports"
_SKILLS: Final = ("agents", "skills")
_EVIDENCE: Final = "evidence"
_SAFE_SEGMENT: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
# Documents apply_updates may create when missing (ContextUpdate.doc_id: FEAT-/BUG-/project).
_CREATABLE: Final = (("FEAT-", MemoryDocType.FEATURE), ("BUG-", MemoryDocType.BUG))
_PROJECT_ID: Final = "project"
_WORK_ITEM_DOCS: Final = frozenset({MemoryDocType.FEATURE, MemoryDocType.BUG})


def _creatable_type(doc_id: str) -> MemoryDocType | None:
    if doc_id == _PROJECT_ID:
        return MemoryDocType.PROJECT
    return next((t for prefix, t in _CREATABLE if doc_id.startswith(prefix)), None)


_TYPED_CONTEXTS: Final = "E04-S01"
_FRESHNESS: Final = "E04-S03"
_ONLY_THROUGH_APPROVE: Final = "approved artifacts change only through approve_artifact"
_DECISION_ID: Final = re.compile(r"^DEC-\d{4,}$")
_PLACEHOLDER_ID: Final = "APR-0000"
_APR_PREFIX: Final = "APR"
_DRIFT_REASON: Final = "approved artifact drift"
_APPROVED_DOC_DEPTH: Final = 2  # approved/APR-NNNN.md; deeper files are payload, not documents
_MayApprove = Callable[[AgentRole], frozenset[str]]


def _later(story: str, *_arguments: object) -> ConfigError:
    """The error of a protocol method that a later story implements."""
    return ConfigError(f"implemented in {story}", detail={"story": story})


def _atomic_write(target: Path, text: str) -> None:
    """Write ``text`` to ``<target>.tmp`` then rename over ``target``; the tmp never survives."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + _TMP_SUFFIX)
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _keep_assessment(row: MemoryIndexRow, previous: MemoryIndexRow | None) -> MemoryIndexRow:
    if previous is None or previous.raw_sha256 != row.raw_sha256:
        return row
    return row.model_copy(
        update={
            "freshness_status": previous.freshness_status,
            "freshness_checked_at": previous.freshness_checked_at,
        }
    )


def _check_change_decision(decision: object, relative: Path) -> None:
    """Writes under ``approved/`` need a change-request decision (Invariant 10; E02-S12)."""
    if not isinstance(decision, str) or not _DECISION_ID.match(decision):
        msg = f"{_ONLY_THROUGH_APPROVE} ({relative.as_posix()})"
        raise ApprovedWriteRefused(msg, detail={"path": relative.as_posix()})
    logger.warning(
        "change-request decision not verified until E04-S05",
        extra={"decision_id": decision, "doc_path": relative.as_posix()},
    )


def _refuse_secrets(text: str, where: str) -> None:
    found = find_secrets(text)
    if found:
        msg = f"secret-like content ({', '.join(found)}) refused in {where}"
        raise SecretDetected(msg, detail={"path": where, "patterns": found})


def _changed_sections(previous: MemoryDocument | None, current: MemoryDocument) -> list[str]:
    if previous is None:
        return list(current.sections)
    names = dict.fromkeys([*current.sections, *previous.sections])
    return [n for n in names if previous.sections.get(n) != current.sections.get(n)]


def _excluded(relative: Path) -> bool:
    """Reports, canonical skills and evidence files are not memory documents."""
    parts = relative.parts
    payload = parts[0] == APPROVED_DIR and len(parts) > _APPROVED_DOC_DEPTH  # APR-NNNN/<file>
    return payload or parts[0] == _REPORTS or parts[:2] == _SKILLS or _EVIDENCE in parts[:-1]


def _atomic_copy(source: Path, target: Path) -> None:
    """Copy ``source`` to ``<target>.tmp`` then rename over ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + _TMP_SUFFIX)
    try:
        tmp.write_bytes(source.read_bytes())
        tmp.replace(target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class DefaultMemoryManager:
    """`MemoryManager` over the `.ai/` folder and the ``memory_index`` table."""

    def __init__(  # noqa: PLR0917 - positional parameters fixed by the E01-S16 contract
        self,
        ai_root: Path,
        index: MemoryIndexRepository,
        ledger: LedgerManager,
        hooks: HookManager,
        ids: IdSequenceStore,
        clock: Clock,
        *,
        project_key: ProjectKey,
        git: GitProvider | None = None,
        may_approve: _MayApprove | None = None,
    ) -> None:
        """Wire the manager.

        Args:
            ai_root: The game repository's `.ai/` folder.
            index: ``memory_index`` rows; units of work open on its database.
            ledger: Write point for ``CONTEXT_UPDATED`` / ``HANDOVER_CREATED``.
            hooks: Fires ``ON_CONTEXT_UPDATED``.
            ids: Id allocation for documents created by later stories (approved artifacts).
            clock: Stamps writes.
            project_key: Project of this kernel database; ledger events and hook contexts
                require it.
            git: HEAD and branch of the repository (``ai_root``'s parent) that stamp the
                approved-artifact documents; `approve_artifact` needs it (E02-S12).
            may_approve: The approved-artifact kinds a role's constitution may approve
                (``authority.may_approve``); without it only USER approves (E02-S12).
        """
        self._ai_root = ai_root
        self._index = index
        self._ledger = ledger
        self._hooks = hooks
        self._ids = ids
        self._clock = clock
        self._project_key = project_key
        self._git = git
        self._may_approve = may_approve
        self._approved = ApprovedArtifactRepository(index.db)

    def root(self) -> str:
        """Absolute path of `.ai/`."""
        return str(self._ai_root.resolve())

    async def read(self, doc_id: str) -> MemoryDocument:
        """Load ``doc_id`` via its index row, else via its canonical path (FEAT/BUG/project).

        Raises:
            DocumentNotFound: If no file exists for the id.
            ConfigError: If the file does not parse.
        """
        row = await self._index.by_doc_id(doc_id)
        if row is not None:
            return self._load(Path(row.path), doc_id)
        doc_type = _creatable_type(doc_id)
        if doc_type is None:
            msg = f"memory document not found: {doc_id}"
            raise DocumentNotFound(msg, detail={"doc_id": doc_id})
        return self._load(doc_path_for(Path(), doc_type, doc_id), doc_id)

    async def read_feature_context(self, feature_id: FeatureId) -> FeatureContext:
        """Typed §37 context (E04-S01)."""
        raise _later(_TYPED_CONTEXTS, feature_id)

    async def read_bug_context(self, bug_id: BugId) -> BugContext:
        """Typed §38 context (E04-S01)."""
        raise _later(_TYPED_CONTEXTS, bug_id)

    async def read_project_context(self) -> ProjectContext:
        """Typed §36 context (E04-S01)."""
        raise _later(_TYPED_CONTEXTS)

    async def read_handover(self, handover_id: HandoverId) -> MemoryDocument:
        """The raw handover document.

        Raises:
            DocumentNotFound: If ``.ai/handovers/<id>.md`` does not exist.
        """
        return self._load(doc_path_for(Path(), MemoryDocType.HANDOVER, handover_id), handover_id)

    async def write(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str
    ) -> MemoryDocument:
        """Write ``doc`` to its canonical path (ADR-0003 D-4); returns the written document.

        Bumps ``version`` (1 when new; ``created_at`` kept from the file), stamps
        ``updated_at``/``updated_by`` and ``freshness`` (keeping ``pr``/``build``), writes
        ``memory_index`` and ``CONTEXT_UPDATED`` in one transaction with the atomic file write,
        then fires ``ON_CONTEXT_UPDATED``.

        Raises:
            ApprovedWriteRefused: An ``approved`` document (path under ``approved/``) without
                a valid ``extra["change_request_decision"]`` (``DEC-NNNN``; existence is
                checked from E04-S05, until then a WARNING is logged). Approving goes
                through `approve_artifact` (E02-S12).
            SecretDetected: The rendered document matches a secret pattern.
            ConfigError: Invalid id, head or branch, or the existing file does not parse.
        """
        return await self._write(doc, actor=actor, head=head, branch=branch, handover=False)

    async def apply_updates(
        self, updates: list[ContextUpdate], *, actor: Actor, head: Sha, branch: str
    ) -> list[MemoryDocument]:
        """Apply section edits, then write each touched document once (in first-touch order).

        Missing FEAT-/BUG-/project documents start from `skeleton_for` (title = id). REPLACE
        sets the section; APPEND adds a paragraph. ``relevant_files`` are merged in order.

        Raises:
            ConfigError: A section outside the type's schema, or a missing document whose type
                cannot be inferred. Nothing is written in either case.
        """
        grouped: dict[str, list[ContextUpdate]] = {}
        for update in updates:
            grouped.setdefault(update.doc_id, []).append(update)
        edited = [await self._edit(doc_id, edits, actor) for doc_id, edits in grouped.items()]
        return [await self.write(doc, actor=actor, head=head, branch=branch) for doc in edited]

    async def write_handover(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str
    ) -> str:
        """Write a handover document; also writes ``HANDOVER_CREATED``. Returns its path.

        The payload is ``{handover_id, work_item_id, reason}``, taken from the front matter's
        ``extra["work_item_id"]`` and ``extra["reason"]``.

        Raises:
            ConfigError: If ``doc`` is not a handover document; plus the errors of `write`.
        """
        if doc.front_matter.type is not MemoryDocType.HANDOVER:
            msg = f"write_handover needs a handover document, got {doc.front_matter.type.value}"
            raise ConfigError(msg, detail={"doc_id": doc.front_matter.id})
        written = await self._write(doc, actor=actor, head=head, branch=branch, handover=True)
        return str((self._ai_root / written.path).resolve())

    async def assess_freshness(self, doc: MemoryDocument, head: Sha) -> FreshnessAssessment:
        """INTERFACES §5.5 (E04-S03)."""
        raise _later(_FRESHNESS, doc, head)

    async def rebuild_index(self) -> int:
        """Re-index every memory document under `.ai/`; returns the number indexed.

        Skips ``reports/``, ``agents/skills/``, evidence folders and approved payload folders;
        files that do not parse are skipped with a warning. Rows of vanished files are deleted.
        An unchanged document (same ``raw_sha256``) keeps its cached freshness assessment, so
        an approved artifact marked INVALID for payload drift stays INVALID (E02-S12).
        """
        rows: list[MemoryIndexRow] = []
        for file in sorted(self._ai_root.rglob("*.md")):
            relative = Path(file.relative_to(self._ai_root).as_posix())
            if _excluded(relative):
                continue
            try:
                doc = parse_document(relative, file.read_text(encoding="utf-8"))
            except (ConfigError, OSError, UnicodeDecodeError) as exc:
                logger.warning(
                    "skipping unparsable memory document",
                    extra={"doc_path": relative.as_posix(), "error": str(exc)},
                )
                continue
            rows.append(MemoryIndexRow.of(doc))
        keep = {row.path for row in rows}
        existing = {row.path: row for row in await self._index.all()}
        async with UnitOfWork(self._index.db) as uow:
            for stale in existing.values():
                if stale.path not in keep:
                    await self._index.delete(stale.path, uow)
            for row in rows:
                await self._index.upsert(_keep_assessment(row, existing.get(row.path)), uow)
        return len(rows)

    async def approve_artifact(
        self, artifact: ApprovedArtifact, *, actor: Actor
    ) -> ApprovedArtifact:
        """§33 approval: payload copy, hash, metadata document, row, ``ARTIFACT_APPROVED``.

        ``artifact.payload_paths`` name the source files (absolute, or relative to the
        repository root); they are copied into `.ai/approved/<id>/` under their file names,
        which become the stored ``payload_paths``. ``APR-0000`` allocates the next ``APR-``
        id. With ``supersedes`` the version is the superseded one's + 1 and that artifact
        becomes SUPERSEDED (row and document); else 1.

        Raises:
            ApprovalNotAuthorized: ``actor`` is neither USER nor allowed by its constitution's
                ``may_approve`` to approve ``artifact.kind``.
            ConfigError: No payload, a missing payload file, two files with the same name,
                an unknown ``supersedes``, or no git provider.
        """
        self._authorize(artifact, actor)
        sources = self._payload_sources(artifact.payload_paths)
        if self._git is None:
            msg = "approving artifacts needs a git provider (freshness stamp)"
            raise ConfigError(msg, detail={"artifact_id": artifact.id})
        previous = await self._approved.get(artifact.supersedes) if artifact.supersedes else None
        repo = str(self._ai_root.parent)
        head, branch = await self._git.head(repo), await self._git.current_branch(repo)
        artifact_id = artifact.id
        if artifact_id == _PLACEHOLDER_ID:
            async with UnitOfWork(self._index.db) as uow:
                artifact_id = self._ids.bind(uow).next_sequence(_APR_PREFIX)
        folder = self._ai_root / APPROVED_DIR / artifact_id
        for source in sources:
            _atomic_copy(source, folder / source.name)
        names = sorted(source.name for source in sources)
        now = self._clock.now()
        approved = artifact.model_copy(
            update={
                "id": artifact_id,
                "status": ApprovalStatus.APPROVED,
                "version": previous.version + 1 if previous is not None else 1,
                "approved_by": actor,
                "approved_at": now,
                "payload_paths": names,
                "content_sha256": hash_payload(folder, names),
            }
        )
        await self._write(
            approved_doc(approved, actor, now),
            actor=actor,
            head=head,
            branch=branch,
            handover=False,
            approve=True,
        )
        if previous is not None:
            await self._supersede(previous, actor, head, branch)
        event = self._event(
            LedgerEventKind.ARTIFACT_APPROVED,
            actor,
            None,
            {"id": approved.id, "kind": approved.kind.value, "sha": approved.content_sha256},
        )
        async with UnitOfWork(self._index.db) as uow:
            await self._approved.upsert(uow, approved)
            await self._ledger.append(event, uow=uow)
        return approved

    async def verify_approved_artifacts(self) -> list[ApprovedArtifactId]:
        """Re-hash every APPROVED artifact's payload; return the drifted ids, by id.

        A mismatch or a missing payload file marks the metadata document's index row INVALID,
        writes ``CONTEXT_FRESHNESS`` and fires ``ON_CONTEXT_STALE`` ``{doc_id, status: INVALID,
        reason: "approved artifact drift"}``. The artifact's status is unchanged: approving
        it again restores it.
        """
        drifted: list[ApprovedArtifactId] = []
        for artifact in await self._approved.list(status=ApprovalStatus.APPROVED):
            folder = self._ai_root / APPROVED_DIR / artifact.id
            try:
                intact = hash_payload(folder, artifact.payload_paths) == artifact.content_sha256
            except ConfigError:
                intact = False
            if not intact:
                drifted.append(artifact.id)
                await self._mark_invalid(artifact.id)
        return drifted

    async def write_report(self, kind: str, subject_id: str, markdown: str) -> str:
        """Overwrite ``.ai/reports/<kind>/<subject_id>.md`` atomically (no index, no ledger).

        Raises:
            ConfigError: If ``kind`` or ``subject_id`` is not a safe path segment.
            SecretDetected: If ``markdown`` matches a secret pattern.
        """
        for segment in (kind, subject_id):
            if not _SAFE_SEGMENT.match(segment) or ".." in segment:
                msg = f"unsafe report path segment {segment!r}"
                raise ConfigError(msg, detail={"kind": kind, "subject_id": subject_id})
        target = self._ai_root / _REPORTS / kind / f"{subject_id}.md"
        _refuse_secrets(markdown, f"{_REPORTS}/{kind}/{subject_id}.md")
        _atomic_write(target, markdown)
        return str(target.resolve())

    def _load(self, relative: Path, doc_id: str) -> MemoryDocument:
        file = self._ai_root / relative
        if not file.is_file():
            msg = f"memory document not found: {doc_id}"
            raise DocumentNotFound(msg, detail={"doc_id": doc_id, "path": relative.as_posix()})
        return parse_document(relative, file.read_text(encoding="utf-8"))

    async def _edit(self, doc_id: str, edits: list[ContextUpdate], actor: Actor) -> MemoryDocument:
        try:
            doc = await self.read(doc_id)
        except DocumentNotFound:
            doc_type = _creatable_type(doc_id)
            if doc_type is None:
                msg = f"cannot create memory document {doc_id}: type not inferable from the id"
                raise ConfigError(msg, detail={"doc_id": doc_id}) from None
            doc = skeleton_for(doc_type, doc_id, doc_id, actor, self._clock.now())
        schema = sections_for(doc.front_matter.type)
        for edit in edits:
            if schema and edit.section not in schema:
                msg = f"unknown section {edit.section!r} for {doc_id}"
                raise ConfigError(msg, detail={"doc_id": doc_id, "section": edit.section})
            content = edit.content_markdown.strip("\n")
            existing = doc.sections.get(edit.section, "")
            if edit.operation == "APPEND" and existing:
                content = f"{existing}\n\n{content}"
            doc.sections[edit.section] = content
            files = [*doc.front_matter.relevant_files, *edit.relevant_files]
            doc.front_matter.relevant_files = list(dict.fromkeys(files))
        return doc

    def _authorize(self, artifact: ApprovedArtifact, actor: Actor) -> None:
        if actor.role is AgentRole.USER:
            return
        allowed = self._may_approve(actor.role) if self._may_approve is not None else frozenset()
        if artifact.kind.value not in allowed:
            msg = f"{actor.role.value} may not approve {artifact.kind.value} artifacts"
            raise ApprovalNotAuthorized(
                msg, detail={"role": actor.role.value, "kind": artifact.kind.value}
            )

    def _payload_sources(self, payload_paths: list[str]) -> list[Path]:
        if not payload_paths:
            msg = "an approved artifact needs at least one payload file"
            raise ConfigError(msg, detail={})
        sources = [
            path if path.is_absolute() else self._ai_root.parent / path
            for path in map(Path, payload_paths)
        ]
        missing = [str(path) for path in sources if not path.is_file()]
        if missing:
            msg = f"approved payload file missing: {', '.join(missing)}"
            raise ConfigError(msg, detail={"missing": missing})
        names = [path.name for path in sources]
        if len(set(names)) != len(names):
            msg = "two payload files have the same name"
            raise ConfigError(msg, detail={"names": names})
        return sources

    async def _supersede(
        self, previous: ApprovedArtifact, actor: Actor, head: Sha, branch: str
    ) -> None:
        superseded = previous.model_copy(update={"status": ApprovalStatus.SUPERSEDED})
        try:
            doc = await self.read(previous.id)
        except DocumentNotFound:
            logger.warning("superseded artifact has no document", extra={"doc_id": previous.id})
        else:
            front = doc.front_matter.model_copy(update={"status": superseded.status.value})
            await self._write(
                doc.model_copy(update={"front_matter": front}),
                actor=actor,
                head=head,
                branch=branch,
                handover=False,
                approve=True,
            )
        async with UnitOfWork(self._index.db) as uow:
            await self._approved.upsert(uow, superseded)

    async def _mark_invalid(self, artifact_id: ApprovedArtifactId) -> None:
        now = self._clock.now()
        payload: JsonDict = {
            "doc_id": artifact_id,
            "status": FreshnessStatus.INVALID.value,
            "reason": _DRIFT_REASON,
        }
        actor = Actor(role=AgentRole.KERNEL)
        context = HookContext(
            name=HookName.ON_CONTEXT_STALE,
            at=now,
            project_key=self._project_key,
            role=actor.role,
            payload=payload,
        )
        row = await self._index.by_doc_id(artifact_id)
        async with UnitOfWork(self._index.db) as uow:
            if row is not None:
                invalid = row.model_copy(
                    update={
                        "freshness_status": FreshnessStatus.INVALID,
                        "freshness_checked_at": now,
                    }
                )
                await self._index.upsert(invalid, uow)
            event = self._event(LedgerEventKind.CONTEXT_FRESHNESS, actor, None, payload)
            await self._ledger.append(event, uow=uow)
            uow.after_commit(lambda: self._fire(context))

    async def _write(
        self,
        doc: MemoryDocument,
        *,
        actor: Actor,
        head: Sha,
        branch: str,
        handover: bool,
        approve: bool = False,
    ) -> MemoryDocument:
        fm = doc.front_matter
        relative = doc_path_for(Path(), fm.type, fm.id)
        if fm.type is MemoryDocType.APPROVED and not approve:
            _check_change_decision(fm.extra.get(_CHANGE_DECISION), relative)
        target = self._ai_root / relative
        previous = (
            parse_document(relative, target.read_text(encoding="utf-8"))
            if target.is_file()
            else None
        )
        now = self._clock.now()
        kept = fm.freshness
        try:
            freshness = Freshness(
                commit=head,
                branch=branch,
                timestamp=now,
                pr=kept.pr if kept else None,
                build=kept.build if kept else None,
            )
        except ValidationError as exc:
            msg = f"invalid freshness stamp (head {head!r}, branch {branch!r})"
            raise ConfigError(msg, detail={"doc_id": fm.id}) from exc
        stamped = fm.model_copy(
            update={
                "version": previous.front_matter.version + 1 if previous else 1,
                "created_at": previous.front_matter.created_at if previous else now,
                "updated_at": now,
                "updated_by": actor,
                "freshness": freshness,
            }
        )
        draft = MemoryDocument(
            path=relative.as_posix(),
            front_matter=stamped,
            sections=dict(doc.sections),
            raw_sha256="",
        )
        text = render_document(draft)
        _refuse_secrets(text, draft.path)
        written = draft.model_copy(
            update={"raw_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        )
        payload: JsonDict = {
            "doc_id": stamped.id,
            "type": stamped.type.value,
            "version": stamped.version,
            "path": written.path,
            "sections_changed": _changed_sections(previous, written),
        }
        work_item = stamped.id if stamped.type in _WORK_ITEM_DOCS else None
        events = [self._event(LedgerEventKind.CONTEXT_UPDATED, actor, work_item, payload)]
        if handover:
            events.append(self._handover_event(stamped.id, stamped.extra, actor))
        context = HookContext(
            name=HookName.ON_CONTEXT_UPDATED,
            at=now,
            project_key=self._project_key,
            work_item_id=work_item,
            run_id=actor.run_id,
            role=actor.role,
            payload=payload,
        )
        async with UnitOfWork(self._index.db) as uow:
            await self._index.upsert(MemoryIndexRow.of(written), uow)
            for event in events:
                await self._ledger.append(event, uow=uow)
            _atomic_write(target, text)
            uow.after_commit(lambda: self._fire(context))
        return written

    async def _fire(self, context: HookContext) -> None:
        await self._hooks.fire(context.name, context)

    def _event(
        self, kind: LedgerEventKind, actor: Actor, work_item: str | None, payload: JsonDict
    ) -> LedgerEvent:
        try:
            return LedgerEvent(
                kind=kind,
                at=self._clock.now(),
                project_key=self._project_key,
                actor_role=actor.role,
                work_item_id=work_item,
                run_id=actor.run_id,
                model_id=actor.model_id,
                outcome="OK",
                payload=payload,
            )
        except ValidationError as exc:
            msg = f"invalid {kind.value} event facts"
            raise ConfigError(msg, detail={"work_item_id": work_item}) from exc

    def _handover_event(self, handover_id: str, extra: JsonDict, actor: Actor) -> LedgerEvent:
        work_item = extra.get("work_item_id")
        payload: JsonDict = {
            "handover_id": handover_id,
            "work_item_id": work_item,
            "reason": extra.get("reason"),
        }
        return self._event(
            LedgerEventKind.HANDOVER_CREATED,
            actor,
            work_item if isinstance(work_item, str) else None,
            payload,
        )
