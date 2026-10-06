"""Default memory manager: the single write path for `.ai/` documents (ADR-0003 D-4)."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from walk.common.clock import Clock
from walk.common.errors import ConfigError
from walk.common.ids import ApprovedArtifactId, BugId, FeatureId, HandoverId, ProjectKey, Sha
from walk.common.models import Actor, JsonDict
from walk.hooks.models import HookContext, HookName
from walk.hooks.protocols import HookManager
from walk.memory.errors import ApprovedWriteRefused, DocumentNotFound, SecretDetected
from walk.memory.frontmatter import parse_document, render_document
from walk.memory.models import (
    ApprovedArtifact,
    BugContext,
    ContextUpdate,
    FeatureContext,
    Freshness,
    FreshnessAssessment,
    MemoryDocType,
    MemoryDocument,
    ProjectContext,
)
from walk.memory.paths import doc_path_for
from walk.memory.repository import MemoryIndexRepository, MemoryIndexRow
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
_APPROVED_ARTIFACTS: Final = "E02-S12"


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
    return parts[0] == _REPORTS or parts[:2] == _SKILLS or _EVIDENCE in parts[:-1]


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
        """
        self._ai_root = ai_root
        self._index = index
        self._ledger = ledger
        self._hooks = hooks
        self._ids = ids
        self._clock = clock
        self._project_key = project_key

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
            ApprovedWriteRefused: An ``approved`` document without
                ``extra["change_request_decision"]``.
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

        Skips ``reports/``, ``agents/skills/`` and evidence folders; files that do not parse
        are skipped with a warning. Rows of vanished files are deleted.
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
        async with UnitOfWork(self._index.db) as uow:
            for stale in await self._index.all():
                if stale.path not in keep:
                    await self._index.delete(stale.path, uow)
            for row in rows:
                await self._index.upsert(row, uow)
        return len(rows)

    async def approve_artifact(
        self, artifact: ApprovedArtifact, *, actor: Actor
    ) -> ApprovedArtifact:
        """§33 approval (E02-S12)."""
        raise _later(_APPROVED_ARTIFACTS, artifact, actor)

    async def verify_approved_artifacts(self) -> list[ApprovedArtifactId]:
        """Approved-artifact hash check (E02-S12)."""
        raise _later(_APPROVED_ARTIFACTS)

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

    async def _write(
        self, doc: MemoryDocument, *, actor: Actor, head: Sha, branch: str, handover: bool
    ) -> MemoryDocument:
        fm = doc.front_matter
        relative = doc_path_for(Path(), fm.type, fm.id)
        if fm.type is MemoryDocType.APPROVED and not fm.extra.get(_CHANGE_DECISION):
            msg = f"{relative.as_posix()} needs a change-request decision to be written"
            raise ApprovedWriteRefused(msg, detail={"doc_id": fm.id})
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
