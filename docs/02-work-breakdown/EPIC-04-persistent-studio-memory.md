# EPIC-04 — Persistent Studio Memory

**Roadmap stage:** §135 Stage 4
**Goal.** Project knowledge lives in `.ai/` with typed feature/bug/project contexts, freshness classification, decision records, handover documents, context-first ranked retrieval (ADR-0012) and optional Graphify code graph — and the §132 failover succeeds using only real `.ai/` files produced by the kernel.
**Requirements.** §6.2, §6.10, §22, §34–§44, §47 (use in ranking), §88, §96 (MVP skeleton), §130, §137 (Inv. 2, 8), §138 (Context Drift, Hallucinated Project State, Excessive Context Cost).
**Epic gate.** `tests/e2e/test_e04_gate.py`: run the E03 §131 scenario until the implementer's second checkpoint; stop the kernel; modify one `relevant_files` entry on disk; restart; assert the new run's `AgentInput.context` contains the `FeatureContext` with `POSSIBLY_STALE` flagged `requires_verification`, the `Handover` parsed from `.ai/handovers/HO-0001.md`, the ACCEPTED decision from `.ai/decisions/DEC-0001.md`; the bundle is byte-identical across two `build()` calls; the run completes and `FeatureContext.remaining_work` is updated via `context_updates`.
**Branching.** From this epic on every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E04-R01.
**Preconditions.** E01-R01, E02-R01, E03-R01 `DONE`; `main` green.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E04-S01 | Typed context documents: `FeatureContext`, `BugContext`, `ProjectContext` ↔ sections | E01-S16, E03-S09, E03-S14 | HIGH |
| E04-S02 | Project context sections and `read_project_context` | E04-S01, E02-S03 | LOW |
| E04-S03 | Freshness stamping and classification, `walk memory freshness` | E04-S01, E01-S23 | HIGH |
| E04-S04 | Freshness hooks: `ON_CONTEXT_STALE`, `ON_CONTEXT_UPDATED`, `ON_CODE_CHANGED` invalidation | E04-S03, E02-S08 | MEDIUM |
| E04-S05 | Decision records persistence, `.ai/decisions/`, `walk decisions list/show` | E01-S16, E01-S05 | HIGH |
| E04-S06 | Handover documents lifecycle, `walk handover show/create` | E01-S28, E01-S16 | MEDIUM |
| E04-S07 | Context checkpoint hooks (§41) and `ON_AGENT_END` context-update requirement | E04-S06, E04-S04 | MEDIUM |
| E04-S08 | Context ranking engine (ADR-0012) | E04-S03, E04-S05, E01-S24 | HIGH |
| E04-S09 | Source slicing | E04-S08 | MEDIUM |
| E04-S10 | Evidence, decision and sibling-context candidates | E04-S08, E01-S06 | MEDIUM |
| E04-S11 | `GraphifyProvider` (`CodeGraphProvider` via CLI, optional) | E01-S23, E02-S02 | HIGH |
| E04-S12 | Code graph in context and refresh hooks | E04-S11, E04-S08 | MEDIUM |
| E04-S13 | Improvement observations skeleton | E01-S16, E01-S27 | MEDIUM |
| E04-S14 | Task templates: context-first, stale verification, mandatory context updates | E04-S08, E04-S07 | LOW |
| E04-S15 | Epic gate: §132 failover against real `.ai/` files (e2e) | E04-S14, E04-S12, E04-S10, E04-S06, E03-S20 | HIGH |
| E04-R01 | Review E04 | E04-S15 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (binding conventions, especially §3.4 payload keys, §3.5 ledger vs hooks, §3.6 fakes).
2. ADR-0003 (memory format), ADR-0012 (ranking), ADR-0002 D-5 (handover document), ADR-0004 D-5, ADR-0009 D-9 (Graphify).
3. `INTERFACES.md` §1.7, §1.8, §1.9 (`DecisionManager`), §1.13 (`CheckpointManager`), §1.15 (`ImprovementManager`), §2.6, §5.4, §5.5.
4. `DOMAIN-MODEL.md` §4.7 (memory), §4.8 (decisions), §4.9 (context), §4.14 (improvement), §6.2 (`memory_index`, `decisions`, `handovers`, `improvement_observations`).
5. `ARCHITECTURE.md` §4.1 (hook rows `ON_CONTEXT_*`, `ON_CODE_CHANGED`, `ON_MERGED`, `ON_DECISION_RECORDED`, `ON_IMPROVEMENT_OBSERVATION`), §7 (Inv. 2, 8), §8.2.

---

### E04-S01 — Typed context documents: `FeatureContext`, `BugContext`, `ProjectContext` ↔ sections

**Status:** TODO
**Type:** feat
**Requirements:** §36, §37, §38, §39, §130, §6.2
**Depends on:** E01-S16, E03-S09, E03-S14
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`MemoryDocument`s of type `feature`, `bug` and `project` convert losslessly to and from the typed pydantic contexts of DOMAIN-MODEL §4.7, and a feature/bug context skeleton exists on disk as soon as the work item exists.

#### Scope
- In: `src/walk/memory/contexts.py`; `read_feature_context`/`read_bug_context` implementations; skeleton creation; `Feature.context_path`/`Bug.context_path` assignment; `OutputApplier` and `apply_updates` call sites.
- Out: `read_project_context` and bootstrap fill (E04-S02); freshness (E04-S03); decision linking into `Important Decisions` (E04-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/contexts.py` | create | `feature_context_from_document`, `feature_context_to_document`, `bug_context_from_document`, `bug_context_to_document`, `project_context_from_document`, `project_context_to_document`, `FEATURE_SECTIONS`, `BUG_SECTIONS`, `PROJECT_SECTIONS` |
| `src/walk/memory/sections.py` | modify | — (section order constants re-exported from `contexts.py` constants; no new public names) |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.read_feature_context`, `DefaultMemoryManager.read_bug_context`, `DefaultMemoryManager.ensure_feature_context`, `DefaultMemoryManager.ensure_bug_context` |
| `src/walk/memory/protocols.py` | modify | `MemoryManager.ensure_feature_context`, `MemoryManager.ensure_bug_context` |
| `src/walk/memory/__init__.py` | modify | re-export the six conversion functions |
| `src/walk/runtime/output_applier.py` | modify | — (`DefaultOutputApplier` calls `ensure_feature_context`/`ensure_bug_context` after creating FEATURE/BUG items) |
| `src/walk/workflow/service.py` | modify | — (`DefaultWorkflowManager.create` sets `context_path` for FEATURE/BUG) |
| `tests/memory/test_contexts.py` | create | — |
| `tests/memory/test_service_contexts.py` | create | — |
| `tests/runtime/test_applier_contexts.py` | create | — |
| `tests/fixtures/memory/FEAT-0001.md`, `tests/fixtures/memory/BUG-0001.md`, `tests/fixtures/memory/project.md` | create | — |

#### Interface contract
```python
# src/walk/memory/contexts.py
FEATURE_SECTIONS: tuple[str, ...] = (
    "Intent",
    "Design Goal",
    "Relevant GDD",
    "Current Status",
    "Architecture",
    "Affected Systems",
    "Dependencies",
    "Relevant Files",
    "Important Decisions",
    "Implementation Notes",
    "Known Risks",
    "QC Notes",
    "Evidence",
    "Remaining Work",
)  # §37 order
BUG_SECTIONS: tuple[str, ...] = (
    "Problem",
    "Reproduction",
    "Expected Behavior",
    "Observed Behavior",
    "Investigations",
    "Hypotheses",
    "Failed Attempts",
    "Root Cause",
    "Affected Systems",
    "Fix",
    "Regression Risk",
    "Verification",
)  # §38
PROJECT_SECTIONS: tuple[str, ...] = (
    "Goals",
    "Platforms",
    "Technical Constraints",
    "Performance Targets",
    "Coding Conventions",
    "Architecture Overview",
    "Art Direction",
    "Product Constraints",
    "Major Decisions",
    "Known Limitations",
)  # §36


def feature_context_from_document(doc: MemoryDocument) -> FeatureContext: ...
def feature_context_to_document(
    ctx: FeatureContext, front_matter: FrontMatter, *, extra_sections: dict[str, str] | None = None
) -> MemoryDocument: ...
def bug_context_from_document(doc: MemoryDocument) -> BugContext: ...
def bug_context_to_document(
    ctx: BugContext, front_matter: FrontMatter, *, extra_sections: dict[str, str] | None = None
) -> MemoryDocument: ...
def project_context_from_document(doc: MemoryDocument) -> ProjectContext: ...
def project_context_to_document(
    ctx: ProjectContext, front_matter: FrontMatter, *, extra_sections: dict[str, str] | None = None
) -> MemoryDocument: ...


# DefaultMemoryManager (additions; protocol methods see INTERFACES.md §1.8)
async def read_feature_context(self, feature_id: FeatureId) -> FeatureContext: ...
async def read_bug_context(self, bug_id: BugId) -> BugContext: ...
async def ensure_feature_context(
    self, feature: Feature, *, actor: Actor, head: Sha, branch: str
) -> MemoryDocument: ...
async def ensure_bug_context(
    self, bug: Bug, *, actor: Actor, head: Sha, branch: str
) -> MemoryDocument: ...
```

#### Behavior
1. `*_from_document` reads H2 sections by exact name; a missing section yields the field's empty value (`""` or `[]`); section lookup is case-sensitive.
2. List-typed fields (`relevant_gdd`, `affected_systems`, `dependencies`, `relevant_files`, `important_decisions`, `evidence`, `platforms`, `major_decisions`) are parsed from Markdown bullet lines (`- ` or `* `); non-bullet lines in those sections raise `OutputInvalid` with the section name.
3. `important_decisions`, `major_decisions`, `evidence` items are validated against `DecisionId`/`EvidenceId` patterns; an invalid id raises `OutputInvalid`.
4. `relevant_gdd` bullets are parsed as `path#anchor` into `GddRef(path, anchor)`.
5. `*_to_document` renders sections in the constant order; list fields as `- item` lines; `extra_sections` (unknown H2 sections from the original document) are appended after the typed ones, in their original order; `front_matter.relevant_files` is set equal to `ctx.relevant_files` (feature) — the document's front matter mirrors the section.
6. Round trip `to_document(from_document(doc))` preserves every section body byte-for-byte for conformant documents.
7. `read_feature_context(id)` reads `.ai/features/<id>.md` via `MemoryManager.read`; a document whose `type != feature` raises `ConfigError`; a missing document raises `ConfigError("feature context missing: <id>")`.
8. `ensure_feature_context(feature)` writes `.ai/features/<id>.md` with all `FEATURE_SECTIONS` present (`Intent` = `feature.description`, `Current Status` = `feature.state`, `Relevant GDD` from `feature.gdd_refs`, everything else empty) only when the file does not exist; existing files are returned unchanged. Same for bugs (`Problem` = `bug.description`, `Reproduction/Expected Behavior/Observed Behavior` from the `Bug` fields).
9. `DefaultWorkflowManager.create` sets `context_path = ".ai/features/<id>.md"` / `".ai/bugs/<id>.md"` on FEATURE/BUG items; `DefaultOutputApplier` calls `ensure_*_context` right after a FEATURE/BUG row is created (before `WorkProvider.create`).
10. `apply_updates` with a `doc_id` whose document does not exist creates the skeleton through `ensure_*_context` first (item looked up through `WorkflowManager.get`), then applies the update.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the fixture `FEAT-0001.md` with all 14 sections When parsed Then every `FeatureContext` field equals the fixture values | `tests/memory/test_contexts.py::test_feature_from_document_maps_all_sections` |
| 2 | Given a feature document missing `QC Notes` When parsed Then `qc_notes == ""` and no error | `tests/memory/test_contexts.py::test_feature_from_document_missing_section_is_empty` |
| 3 | Given `Affected Systems` containing a non-bullet line When parsed Then `OutputInvalid` names the section | `tests/memory/test_contexts.py::test_list_section_non_bullet_raises_output_invalid` |
| 4 | Given `Important Decisions` with `- DEC-12` When parsed Then `OutputInvalid` is raised (pattern requires 4 digits) | `tests/memory/test_contexts.py::test_invalid_decision_id_raises` |
| 5 | Given a `FeatureContext` plus an unknown section `Playtest Notes` When rendered Then the 14 typed sections come first in §37 order and `Playtest Notes` last | `tests/memory/test_contexts.py::test_feature_to_document_order_and_extra_sections` |
| 6 | Given the fixture When round-tripped Then the rendered sections equal the original bodies | `tests/memory/test_contexts.py::test_feature_roundtrip_preserves_sections` |
| 7 | Given the fixture `BUG-0001.md` When parsed and rendered Then all 12 §38 fields round-trip | `tests/memory/test_contexts.py::test_bug_roundtrip` |
| 8 | Given `project.md` When parsed Then `platforms` is a list and `major_decisions` are `DecisionId`s | `tests/memory/test_contexts.py::test_project_from_document_lists` |
| 9 | Given no `.ai/features/FEAT-0001.md` When `ensure_feature_context` runs Then the file exists with 14 H2 sections, `Intent` = description, `version == 1` | `tests/memory/test_service_contexts.py::test_ensure_feature_context_creates_skeleton` |
| 10 | Given an existing feature context When `ensure_feature_context` runs Then the file sha is unchanged and `version` not bumped | `tests/memory/test_service_contexts.py::test_ensure_feature_context_is_idempotent` |
| 11 | Given a document with `type: bug` at the feature path When `read_feature_context` runs Then `ConfigError` | `tests/memory/test_service_contexts.py::test_read_feature_context_wrong_type_raises` |
| 12 | Given a fake PLAN output with `new_tasks` creating a FEATURE and QC output with `new_bugs` When applied Then both context files exist and `context_path` is set on the items | `tests/runtime/test_applier_contexts.py::test_applier_creates_context_skeletons` |
| 13 | Given `apply_updates` for a FEAT whose file is missing When applied Then skeleton is created and the section replaced | `tests/memory/test_service_contexts.py::test_apply_updates_creates_missing_skeleton` |

#### Evidence required
- Quality gate output (ruff ok, mypy ok, N passed, coverage %).
- Demo: `walk work show FEAT-0001` prints `context_path: .ai/features/FEAT-0001.md`; `cat .ai/features/FEAT-0001.md` shows 14 H2 headings in §37 order.

#### Notes
- ADR-0003 D-2: unknown H2 sections preserved verbatim.
- `NEW NAME:` module `walk.memory.contexts`; methods `MemoryManager.ensure_feature_context`, `MemoryManager.ensure_bug_context`.
- `FeatureContext.freshness`/`BugContext.freshness` are filled from `front_matter.freshness` (read-only in this story).
- Commit subject: `feat: add typed feature, bug and project context documents (E04-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S02 — Project context sections and `read_project_context`

**Status:** TODO
**Type:** feat
**Requirements:** §36, §34, §130, §40
**Depends on:** E04-S01, E02-S03
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`.ai/project/project.md` is a typed `ProjectContext` that bootstrap seeds from the GDD and that the context manager can read section-selectively; any memory document can be inspected from the CLI.

#### Scope
- In: `read_project_context`, `project_context_sections_for_context`, bootstrap seeding of `Goals`, `walk memory show`.
- Out: platform detection from Unity settings (not in MVP); ranking of project sections (E04-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.read_project_context`, `DefaultMemoryManager.project_context_sections_for_context` |
| `src/walk/memory/protocols.py` | modify | `MemoryManager.project_context_sections_for_context` |
| `src/walk/orchestrator/bootstrap.py` | modify | — (`Bootstrapper` writes `project.md` through `project_context_to_document`; ADR-0020) |
| `src/walk/cli/cmd_memory.py` | modify | `show` command |
| `tests/memory/test_service_project_context.py` | create | — |
| `tests/orchestrator/test_bootstrap_project_context.py` | create | — |
| `tests/cli/test_cmd_memory_show.py` | create | — |

#### Interface contract
```python
CONTEXT_PROJECT_SECTIONS: tuple[str, ...] = (
    "Goals",
    "Technical Constraints",
    "Coding Conventions",
    "Architecture Overview",
)


async def read_project_context(self) -> ProjectContext: ...
async def project_context_sections_for_context(self) -> dict[str, str]:
    """Returns {section_name: markdown} for CONTEXT_PROJECT_SECTIONS only (INTERFACES §5.4 step 2d)."""
```
CLI: `walk memory show DOC_ID [--json]` — prints front matter (YAML) and sections; `--json` prints `MemoryDocument.model_dump()`; unknown id → exit 1.

#### Behavior
1. `read_project_context` reads `.ai/project/project.md` (`doc_id == "project"`); missing → `ConfigError("project context missing")`.
2. `project_context_sections_for_context` returns exactly the four whitelisted sections, in that order, empty strings for missing sections.
3. Bootstrap writes `project.md` with all `PROJECT_SECTIONS`; `Goals` bullets are the GDD H1/H2 headings (deduplicated, max 50, each `- <heading> (<relative path>)`); `Platforms` is `- TBD`; other sections are `_TBD_`.
4. Bootstrap re-run does not overwrite an existing `project.md` (idempotency from E02-S03 preserved).
5. `walk memory show` resolves `DOC_ID` through `memory_index`; `project` maps to `.ai/project/project.md`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a bootstrapped repo When `read_project_context` runs Then `goals` lists GDD headings and `platforms == ["TBD"]` | `tests/memory/test_service_project_context.py::test_read_project_context_after_bootstrap` |
| 2 | Given no `project.md` When `read_project_context` runs Then `ConfigError` | `tests/memory/test_service_project_context.py::test_read_project_context_missing_raises` |
| 3 | Given a project doc with all sections When `project_context_sections_for_context` runs Then exactly the four whitelisted keys in order | `tests/memory/test_service_project_context.py::test_sections_for_context_whitelist` |
| 4 | Given a GDD with 3 files and 12 headings When bootstrap runs Then `Goals` has 12 bullets each ending with the file path | `tests/orchestrator/test_bootstrap_project_context.py::test_bootstrap_seeds_goals_from_gdd` |
| 5 | Given an edited `project.md` When bootstrap runs again Then the file is unchanged | `tests/orchestrator/test_bootstrap_project_context.py::test_bootstrap_keeps_existing_project_md` |
| 6 | Given `walk memory show project --json` Then output parses as JSON with `front_matter.type == "project"` | `tests/cli/test_cmd_memory_show.py::test_memory_show_json` |
| 7 | Given `walk memory show NOPE` Then exit code 1 | `tests/cli/test_cmd_memory_show.py::test_memory_show_unknown_exits_1` |

#### Evidence required
- Quality gate output.
- Demo: `walk memory show project` → YAML header + `## Goals` with GDD headings.

#### Notes
- `NEW NAME:` `MemoryManager.project_context_sections_for_context`; `walk memory show` command (INTERFACES §6 has no read command for memory documents; needed for operators and gate evidence).
- Commit subject: `feat: add project context reading and memory show command (E04-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S03 — Freshness stamping and classification, `walk memory freshness`

**Status:** TODO
**Type:** feat
**Requirements:** §42, §138 (Context Drift), §6.2
**Depends on:** E04-S01, E01-S23
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every memory document can be classified `CURRENT | POSSIBLY_STALE | INVALID` against a git HEAD with the INTERFACES §5.5 algorithm, with results cached in `memory_index`.

#### Scope
- In: `assess_freshness`, cache columns, `KernelSettings.memory_max_age_days`, CLI.
- Out: hooks reacting to staleness (E04-S04); ranking weights (E04-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/freshness.py` | create | `classify_freshness`, `FreshnessInputs` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.assess_freshness` |
| `src/walk/memory/repository.py` | modify | `MemoryIndexRepository.get_cached_freshness`, `MemoryIndexRepository.set_cached_freshness` |
| `src/walk/cli/composition.py` | modify | `KernelSettings.memory_max_age_days` |
| `src/walk/cli/cmd_memory.py` | modify | `freshness` command |
| `tests/memory/test_freshness.py` | create | — |
| `tests/memory/test_service_freshness.py` | create | — |
| `tests/cli/test_cmd_memory_freshness.py` | create | — |

#### Interface contract
```python
# src/walk/memory/freshness.py
class FreshnessInputs(FrozenModel):
    stamp: Freshness | None
    relevant_files: list[str]
    head: Sha
    stamp_is_ancestor: bool  # GitProvider.is_ancestor(stamp.commit, head) or stamp.commit == head
    missing_files: list[str]
    changed_files: list[
        str
    ]  # GitProvider.changed_between(stamp.commit, head, paths=relevant_files)
    now: datetime
    max_age_days: int = 30


def classify_freshness(
    inputs: FreshnessInputs,
) -> FreshnessAssessment: ...  # pure, INTERFACES §5.5 steps 1–6


# DefaultMemoryManager
async def assess_freshness(
    self, doc: MemoryDocument, head: Sha
) -> FreshnessAssessment: ...  # see INTERFACES.md §1.8
```
`KernelSettings.memory_max_age_days: int = 30`. CLI: `walk memory freshness [DOC_ID] [--json]`.

#### Behavior
1. Step 1: `stamp is None` → `POSSIBLY_STALE("never stamped")`.
2. Step 2: not ancestor and `stamp.commit != head` → `INVALID("stamp commit not in history")`.
3. Step 3: `missing_files` non-empty → `INVALID("relevant files missing: <sorted list>")`.
4. Step 4: `changed_files` non-empty → `POSSIBLY_STALE("relevant files changed")` with `changed_relevant_files` set.
5. Step 5: `now - stamp.timestamp > max_age_days` → `POSSIBLY_STALE("age")`.
6. Step 6: otherwise `CURRENT("")`. `assessed_against = head`, `assessed_at = now` (from injected `Clock`).
7. `assess_freshness` builds `FreshnessInputs` using `GitProvider.is_ancestor`, file existence under `root().parent` (repo root), `GitProvider.changed_between`, and caches `(freshness_status, freshness_checked_at, freshness_commit=head)` in `memory_index`; a cache hit for `(path, head)` returns without calling git.
8. A `GitProvider` `TransientError` propagates (no classification guessed).
9. `walk memory freshness` without `DOC_ID` assesses every indexed document against repo HEAD and prints `id | status | reason`; with `DOC_ID` prints one row plus changed files; exit 0 in all cases.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `stamp=None` When classified Then `POSSIBLY_STALE` / `never stamped` | `tests/memory/test_freshness.py::test_never_stamped_is_possibly_stale` |
| 2 | Given stamp commit not ancestor of head When classified Then `INVALID` / `stamp commit not in history` | `tests/memory/test_freshness.py::test_non_ancestor_is_invalid` |
| 3 | Given a missing relevant file When classified Then `INVALID` listing the file | `tests/memory/test_freshness.py::test_missing_relevant_file_is_invalid` |
| 4 | Given changed relevant files When classified Then `POSSIBLY_STALE` with `changed_relevant_files` | `tests/memory/test_freshness.py::test_changed_files_is_possibly_stale` |
| 5 | Given stamp 31 days old, nothing changed When classified Then `POSSIBLY_STALE` / `age` | `tests/memory/test_freshness.py::test_age_is_possibly_stale` |
| 6 | Given stamp == head and fresh When classified Then `CURRENT` | `tests/memory/test_freshness.py::test_current` |
| 7 | Given step-2 and step-3 conditions both true When classified Then step 2 wins | `tests/memory/test_freshness.py::test_step_order_precedence` |
| 8 | Given a real temp repo where a relevant file is modified and committed after the stamp When `assess_freshness` runs Then `POSSIBLY_STALE` and `memory_index` holds the cached status | `tests/memory/test_service_freshness.py::test_assess_freshness_real_repo_and_cache` |
| 9 | Given a cached `(path, head)` When assessed again Then `GitProvider` is not called (fake counter) | `tests/memory/test_service_freshness.py::test_assess_freshness_cache_hit_skips_git` |
| 10 | Given `GitProvider.changed_between` raising `Timeout` When assessed Then `Timeout` propagates | `tests/memory/test_service_freshness.py::test_git_error_propagates` |
| 11 | Given two docs When `walk memory freshness` runs Then two rows and exit 0 | `tests/cli/test_cmd_memory_freshness.py::test_freshness_lists_all` |
| 12 | Given `walk memory freshness FEAT-0001 --json` Then JSON has `status`, `reason`, `changed_relevant_files` | `tests/cli/test_cmd_memory_freshness.py::test_freshness_single_json` |

#### Evidence required
- Quality gate output.
- Demo: `walk memory freshness` after editing a relevant file → `FEAT-0001 | POSSIBLY_STALE | relevant files changed`.

#### Notes
- ADR-0003 D-3. Cache key is `(path, head)`: a new HEAD always re-assesses.
- `NEW NAME:` `walk.memory.freshness.classify_freshness`, `FreshnessInputs`; `KernelSettings.memory_max_age_days`.
- Commit subject: `feat: add memory freshness classification and cli (E04-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S04 — Freshness hooks: `ON_CONTEXT_STALE`, `ON_CONTEXT_UPDATED`, `ON_CODE_CHANGED` invalidation

**Status:** TODO
**Type:** feat
**Requirements:** §42, §41, §32, §138 (Context Drift), §116
**Depends on:** E04-S03, E02-S08
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Staleness is detected before every agent run, flagged on the bundle, recorded in the ledger, and memory documents are proactively invalidated when files they reference change.

#### Scope
- In: builtin attachments for `ON_AGENT_START`, `ON_CONTEXT_STALE`, `ON_CONTEXT_UPDATED`, `ON_CODE_CHANGED`; `invalidate_for_paths`; `CONTEXT_FRESHNESS` write point.
- Out: observation counters (E04-S13); graph `mark_dirty` on `ON_CODE_CHANGED` (E04-S12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/builtin_hooks.py` | modify | `agent_start_freshness_check`, `context_stale_flag`, `context_updated_counter`, `code_changed_invalidate` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.invalidate_for_paths`, `DefaultMemoryManager.record_stale` |
| `src/walk/memory/protocols.py` | modify | `MemoryManager.invalidate_for_paths` |
| `src/walk/memory/repository.py` | modify | `MemoryIndexRepository.docs_referencing` |
| `src/walk/context/service.py` | modify | — (`DefaultContextManager.build` fires `ON_CONTEXT_STALE` per non-CURRENT mandatory item, ARCHITECTURE §5.4 step 3) |
| `src/walk/runtime/executor.py` | modify | — (`ON_TOOL_AFTER` write-tool detection fires `ON_CODE_CHANGED` with `payload["paths"]`; checkpoint diff fires it too) |
| `tests/hooks/test_builtins_freshness.py` | create | — |
| `tests/memory/test_service_invalidate.py` | create | — |
| `tests/context/test_service_stale_hooks.py` | create | — |

#### Interface contract
```python
async def invalidate_for_paths(self, paths: list[str]) -> list[str]:
    """Sets memory_index.freshness_status=POSSIBLY_STALE for docs whose relevant_files intersect paths. Returns doc ids."""


async def record_stale(
    self, doc_id: str, assessment: FreshnessAssessment, *, run_id: RunId | None
) -> None:
    """Ledger CONTEXT_FRESHNESS (write point ARCHITECTURE §4.3: memory.MemoryManager)."""
```
Hook payloads: `ON_CONTEXT_STALE.payload = {"doc_id", "status", "reason", "item_id"}`; `ON_CODE_CHANGED.payload = {"paths": list[str]}`.

#### Behavior
1. `ON_AGENT_START` builtin (priority 40, `required=True`): no-op here — freshness is assessed inside `ContextManager.build` (which runs before `ON_AGENT_START`); the hook asserts `payload["stale_item_ids"]` from the `ContextBundleRef` and fires nothing new. (Avoids double assessment; documented.)
2. `ContextManager.build` step 3: for each mandatory memory doc with status ≠ `CURRENT`: `item.requires_verification = True`, `HookManager.fire(ON_CONTEXT_STALE, …)`.
3. `ON_CONTEXT_STALE` MUST (priority 10): `MemoryManager.record_stale` → ledger `CONTEXT_FRESHNESS{doc_id, status, reason}` with `outcome="SKIPPED"` when `INVALID`, else `"OK"`; `TelemetryManager.counter("context.stale", status=…)`.
4. `ON_CONTEXT_UPDATED` MUST (priority 10): counter `context.updated` only — stamp and index update are done inside `write()` (WBS §3.5).
5. `ON_CODE_CHANGED` default (priority 100, `required=False`): `MemoryManager.invalidate_for_paths(payload["paths"])`.
6. `invalidate_for_paths` matches by exact repo-relative path; never touches the Markdown file; returns affected doc ids; no ledger event (the next `assess_freshness` produces one via `ON_CONTEXT_STALE`).
7. `AgentExecutor` fires `ON_CODE_CHANGED` after a `TOOL_CALL_RESULT` whose `ToolSpec.name ∈ {"Edit","Write","MultiEdit","NotebookEdit"}` or kind `KERNEL` with `provider == "git"`, with the paths from `tool_call.paths`; and at every checkpoint with `Checkpoint.dirty_files`.
8. A failing `invalidate_for_paths` (e.g. DB error) is `LOG_AND_CONTINUE` (default hook).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a POSSIBLY_STALE feature context When `build` runs Then the item has `requires_verification=True` and `ON_CONTEXT_STALE` fired once | `tests/context/test_service_stale_hooks.py::test_build_flags_stale_and_fires_hook` |
| 2 | Given a CURRENT doc When `build` runs Then no `ON_CONTEXT_STALE` | `tests/context/test_service_stale_hooks.py::test_build_current_no_hook` |
| 3 | Given `ON_CONTEXT_STALE` fired for INVALID When handled Then ledger `CONTEXT_FRESHNESS` with `outcome=SKIPPED` and counter incremented | `tests/hooks/test_builtins_freshness.py::test_context_stale_writes_ledger_and_counter` |
| 4 | Given `ON_CONTEXT_UPDATED` fired When handled Then exactly one `CONTEXT_UPDATED` ledger event exists (written by `write()`), none by the hook | `tests/hooks/test_builtins_freshness.py::test_context_updated_hook_does_not_duplicate_ledger` |
| 5 | Given docs A (`Assets/A.cs`) and B (`Assets/B.cs`) When `invalidate_for_paths(["Assets/A.cs"])` Then only A is `POSSIBLY_STALE` in the index and the Markdown is unchanged | `tests/memory/test_service_invalidate.py::test_invalidate_marks_only_referencing_docs` |
| 6 | Given a fake run with an `Edit` tool result on `Assets/A.cs` When executed Then `ON_CODE_CHANGED` fired with `paths == ["Assets/A.cs"]` | `tests/hooks/test_builtins_freshness.py::test_executor_fires_code_changed_on_write_tool` |
| 7 | Given a checkpoint with dirty files When created Then `ON_CODE_CHANGED` fired with those paths | `tests/hooks/test_builtins_freshness.py::test_checkpoint_fires_code_changed` |
| 8 | Given `invalidate_for_paths` raising When `ON_CODE_CHANGED` fires Then hook result `FAILED`, run continues | `tests/hooks/test_builtins_freshness.py::test_code_changed_failure_logs_and_continues` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --kind CONTEXT_FRESHNESS` after a run with a stale doc → one row with `payload.reason`.

#### Notes
- ARCHITECTURE §4.1 rows `ON_CONTEXT_STALE`, `ON_CONTEXT_UPDATED`, `ON_CODE_CHANGED`; §4.3 write point `memory.MemoryManager` for `CONTEXT_FRESHNESS`.
- `NEW NAME:` `MemoryManager.invalidate_for_paths`, `MemoryManager.record_stale`.
- Commit subject: `feat: add freshness hooks and path invalidation (E04-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S05 — Decision records persistence, `.ai/decisions/`, `walk decisions list/show`

**Status:** TODO
**Type:** feat
**Requirements:** §44, §6.10, §88, §130, §137 (Inv. 5, 8)
**Depends on:** E01-S16, E01-S05
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Accepted decisions are first-class, persisted in SQLite and `.ai/decisions/DEC-NNNN.md`, recorded only by an authority or the user, and retrievable by relevance for context assembly.

#### Scope
- In: `walk.decisions` protocols/repository/service; `record`, `relevant_for`; `ON_DECISION_RECORDED` MUST hook; CLI list/show.
- Out: `propose/escalate/override/classify_autonomy` logic (E05-S01, declared here raising `NotSupported`); debate-based authority (E05-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/decisions/protocols.py` | create | `DecisionManager` (INTERFACES §1.9), `AuthorityResolver` |
| `src/walk/decisions/repository.py` | create | `DecisionRepository` |
| `src/walk/decisions/service.py` | create | `DefaultDecisionManager` |
| `src/walk/decisions/errors.py` | create | `AuthorityViolation` |
| `src/walk/decisions/__init__.py` | modify | re-exports |
| `src/walk/memory/sections.py` | modify | `DECISION_SECTIONS` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `decision_recorded_write_and_link` |
| `src/walk/cli/cmd_decisions.py` | create | `list`, `show` |
| `src/walk/cli/app.py` | modify | — (register `decisions` group) |
| `src/walk/cli/composition.py` | modify | — (wire `DefaultDecisionManager`, `KernelHandle.decisions`) |
| `tests/decisions/test_service.py` | create | — |
| `tests/decisions/test_repository.py` | create | — |
| `tests/hooks/test_builtins_decisions.py` | create | — |
| `tests/cli/test_cmd_decisions.py` | create | — |

#### Interface contract
```python
# src/walk/decisions/protocols.py
AuthorityResolver = Callable[
    [AgentRole], Authority
]  # injected by composition root: lambda r: agent_manager.load_constitution(r).authority


class DecisionManager(Protocol): ...  # verbatim INTERFACES.md §1.9


# src/walk/decisions/errors.py
class AuthorityViolation(PermissionDenied): ...


# src/walk/decisions/service.py
class DefaultDecisionManager:
    def __init__(
        self,
        repo: DecisionRepository,
        memory: MemoryManager,
        ledger: LedgerManager,
        hooks: HookManager,
        ids: IdFactory,
        clock: Clock,
        authority_for: AuthorityResolver,
        workflow: WorkflowManager,
    ) -> None: ...


DECISION_SECTIONS = (
    "Topic",
    "Participants",
    "Positions",
    "Evidence",
    "Outcome",
    "Rationale",
    "Alternatives",
    "Affected Systems",
    "Related Work Items",
)
```
CLI: `walk decisions list [--status S] [--category C] [--json]`, `walk decisions show DEC_ID [--json]`.

#### Behavior
1. `record(decision, by)`: allowed iff `by.role == USER`, or `decision.category ∈ authority_for(by.role).decision_scope`, or `decision.debate_id is not None` (debate resolution check is E05-S03; until then `debate_id` set → `NotSupported("E05-S03")`). Otherwise `AuthorityViolation`.
2. On success, in one `UnitOfWork`: id allocated (`DEC-` width 4) when `decision.id` is a placeholder `DEC-0000`; `status=ACCEPTED`; `decisions` row + `decision_work_items` rows; ledger `DECISION_RECORDED{category, topic, owner}`; then `ON_DECISION_RECORDED` fires.
3. `ON_DECISION_RECORDED` MUST (priority 10): writes `.ai/decisions/DEC-NNNN.md` (`type: decision`, `status: ACCEPTED`, sections in `DECISION_SECTIONS` order, `related.work_items`, `related.evidence`) via `MemoryManager.write`; for every `related_work_items` FEATURE (or the parent feature of a story/bug) appends `- DEC-NNNN` to `Important Decisions` via `apply_updates(APPEND)`.
4. `relevant_for(item, affected_systems)`: ACCEPTED decisions where `work_item_id ∈ {item.id} ∪ ancestors(item)` or `set(decision.affected_systems) ∩ set(affected_systems) ≠ ∅`; ordered by `decided_at desc`; superseded decisions excluded.
5. `propose`, `escalate`, `override`, `classify_autonomy` raise `NotSupported("E05-S01")`.
6. `ai_path` column equals the written path; version starts at 1.
7. `walk decisions list` reads SQLite directly (read-only); `show` prints the record plus the document body.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `by=Actor(role=USER)` When `record` Then status ACCEPTED, row exists, `DECISION_RECORDED` ledger, `.ai/decisions/DEC-0001.md` exists with 9 sections in order | `tests/decisions/test_service.py::test_record_by_user_persists_and_writes_doc` |
| 2 | Given LEAD_DEV with `decision_scope=[TECH]` When recording a TECH decision Then accepted | `tests/decisions/test_service.py::test_record_within_authority_scope` |
| 3 | Given SENIOR_DEV (`decision_scope=[]`) When recording Then `AuthorityViolation` and no row/doc/ledger | `tests/decisions/test_service.py::test_record_outside_authority_raises` |
| 4 | Given `debate_id` set When `record` Then `NotSupported` | `tests/decisions/test_service.py::test_record_with_debate_not_supported_yet` |
| 5 | Given a decision related to STORY-0001 (child of FEAT-0001) When hook runs Then `FEAT-0001.md` `Important Decisions` contains `- DEC-0001` | `tests/hooks/test_builtins_decisions.py::test_decision_recorded_links_feature_context` |
| 6 | Given decisions linked to FEAT-0001 and one with overlapping `affected_systems` When `relevant_for(STORY-0001, ["SaveSystem"])` Then both returned, newest first | `tests/decisions/test_service.py::test_relevant_for_ancestors_and_systems` |
| 7 | Given a SUPERSEDED decision When `relevant_for` Then excluded | `tests/decisions/test_service.py::test_relevant_for_excludes_superseded` |
| 8 | Given `propose(...)` When called Then `NotSupported` | `tests/decisions/test_service.py::test_propose_not_supported` |
| 9 | Given two decisions When `walk decisions list --category TECH --json` Then one row | `tests/cli/test_cmd_decisions.py::test_decisions_list_filter` |
| 10 | Given `walk decisions show DEC-0001` Then output contains `## Rationale` | `tests/cli/test_cmd_decisions.py::test_decisions_show` |
| 11 | Given a repository round trip When saving and loading Then `Decision` equal | `tests/decisions/test_repository.py::test_repository_roundtrip` |

#### Evidence required
- Quality gate output.
- Demo: `walk decisions show DEC-0001` → header `DEC-0001 ACCEPTED TECH` and the `## Outcome` section.

#### Notes
- Invariant 5: only `record()` sets ACCEPTED; `AgentOutput.decisions` are proposals handled in E05-S01.
- `NEW NAME:` `AuthorityResolver` callable type, `AuthorityViolation` error (subclass of `PermissionDenied`), `DECISION_SECTIONS`.
- Commit subject: `feat: add decision record persistence and cli (E04-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S06 — Handover documents lifecycle, `walk handover show/create`

**Status:** TODO
**Type:** feat
**Requirements:** §22, §41, §89, §130, §137 (Inv. 12)
**Depends on:** E01-S28, E01-S16
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every handover reason produces a complete `.ai/handovers/HO-NNNN.md` built from kernel facts, the latest open handover is fed to the next run and closed when consumed, and operators can inspect or force handovers from the CLI.

#### Scope
- In: `build_handover` enrichment; open/close lifecycle; CLI `handover show/create`; `CommandConsumer` action `handover.create`.
- Out: triggers for PARTIAL/PAUSE/BUDGET (E04-S07); template wording (E04-S14).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/checkpoints.py` | modify | `DefaultCheckpointManager.build_handover`, `DefaultCheckpointManager.open_handover_for`, `DefaultCheckpointManager.close_handover` |
| `src/walk/runtime/protocols.py` | modify | `CheckpointManager.open_handover_for`, `CheckpointManager.close_handover` |
| `src/walk/runtime/repository.py` | modify | `HandoverRepository.latest_open_for_item`, `HandoverRepository.set_to_run` |
| `src/walk/orchestrator/scheduler.py` | modify | — (tick step 12 uses `open_handover_for`; step 13 closes it with the new run id) |
| `src/walk/orchestrator/commands.py` | modify | — (`handover.create` command action) |
| `src/walk/cli/cmd_handover.py` | create | `show`, `create` |
| `src/walk/cli/app.py` | modify | — |
| `tests/runtime/test_checkpoints_handover.py` | create | — |
| `tests/orchestrator/test_scheduler_handover.py` | create | — |
| `tests/cli/test_cmd_handover.py` | create | — |

#### Interface contract
```python
async def build_handover(
    self, run: AgentRun, reason: str, partial_output: AgentOutput | None
) -> Handover: ...  # INTERFACES §1.13
async def open_handover_for(self, work_item_id: WorkItemId) -> Handover | None:
    """Latest handovers row with to_run_id IS NULL for the item, converted with walk.agents.handover.from_document."""


async def close_handover(self, handover_id: HandoverId, to_run_id: RunId) -> None: ...
```
CLI: `walk handover show (ITEM_ID | HO_ID) [--json]`; `walk handover create RUN_ID --reason {FALLBACK,PAUSE,BUDGET,PARTIAL,REASSIGN,RECOVERY}` (daemon required, exit 3 otherwise).

#### Behavior
1. `build_handover` composes: `task_summary` = item title + `contract.goal`; `current_state` = workflow state + run state; `completed_work`/`findings`/`hypotheses`/`risks`/`remaining_work`/`next_action` from `partial_output.handover` when present, else from `partial_output` fields (`findings`, `next_actions`), else from the feature/bug context sections `Current Status`/`Remaining Work`; `modified_files` = `GitProvider.diff_names(worktree, base=run_start_sha)` ∪ `status`; `decisions` = `DECISION_RECORDED` ledger events with `run_id == run.id`; `worktree_head` = HEAD after the WIP commit; `from_model_id`, `reason`.
2. Never reads `TEXT` events or transcripts (ADR-0004 D-5).
3. For each reason in `FALLBACK|PAUSE|BUDGET|PARTIAL|REASSIGN|RECOVERY` the same document shape is written (`type: handover`, sections `Task, Current State, Completed Work, Modified Files, Findings, Hypotheses, Decisions, Risks, Remaining Work, Next Action`); `HANDOVER_CREATED` ledger once per document.
4. `open_handover_for` returns the newest open handover; scheduler step 12 passes it as `AgentInput.handover`; step 13 calls `close_handover(id, new_run.id)` in the same transaction as the schedule idempotency key.
5. A closed handover is never re-fed (query filters `to_run_id IS NULL`).
6. `walk handover show ITEM_ID` prints the latest handover for the item (open or closed); `HO_ID` prints that one; neither found → exit 1.
7. `walk handover create` enqueues `handover.create{run_id, reason}`; the consumer performs `checkpoint(run, HANDOFF, handover=build_handover(...))` on a RUNNING run; a non-RUNNING run → command result `ok=false`, CLI exit 2.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a run with 2 recorded decisions, 3 modified files and a PARTIAL output When `build_handover` Then `decisions` has 2 ids, `modified_files` 3 paths, `next_action` from output | `tests/runtime/test_checkpoints_handover.py::test_build_handover_from_kernel_facts` |
| 2 | Given no partial output When `build_handover` Then `remaining_work` comes from the feature context `Remaining Work` | `tests/runtime/test_checkpoints_handover.py::test_build_handover_falls_back_to_context` |
| 3 | Given each of the six reasons (parametrised) When checkpoint with handover Then a `HO-000N.md` exists with 10 sections and one `HANDOVER_CREATED` event | `tests/runtime/test_checkpoints_handover.py::test_each_reason_writes_document` |
| 4 | Given a `TEXT` event containing "secret reasoning" When `build_handover` Then the string appears nowhere in the document | `tests/runtime/test_checkpoints_handover.py::test_handover_never_contains_transcript_text` |
| 5 | Given an open handover for STORY-0001 When `tick` schedules it Then `AgentInput.handover.id` matches and the row's `to_run_id` equals the new run | `tests/orchestrator/test_scheduler_handover.py::test_tick_feeds_and_closes_open_handover` |
| 6 | Given only closed handovers When `open_handover_for` Then `None` | `tests/runtime/test_checkpoints_handover.py::test_open_handover_ignores_closed` |
| 7 | Given `walk handover show STORY-0001` Then prints `HO-0001` and `## Next Action` | `tests/cli/test_cmd_handover.py::test_handover_show_by_item` |
| 8 | Given `walk handover show HO-9999` Then exit 1 | `tests/cli/test_cmd_handover.py::test_handover_show_unknown_exits_1` |
| 9 | Given a RUNNING fake run and daemon When `walk handover create RUN --reason REASSIGN` Then a HANDOFF checkpoint and HO doc exist | `tests/cli/test_cmd_handover.py::test_handover_create_via_command` |
| 10 | Given a COMPLETED run When `walk handover create` Then exit 2 | `tests/cli/test_cmd_handover.py::test_handover_create_non_running_exits_2` |

#### Evidence required
- Quality gate output.
- Demo: `walk handover show STORY-0001` → document with `reason: PARTIAL` front matter.

#### Notes
- From E01-B05 (2026-10-07): handover document/row/HANDOFF-checkpoint consistency is already delivered by E01-B05. Behavior 1 is satisfied; keep its acceptance test only if it adds coverage beyond `tests/runtime` E01-B05 tests, otherwise drop it and record that in Evidence.
- ADR-0002 D-5, ADR-0004 D-5. `handovers.ai_path` is set by `CheckpointManager` after `MemoryManager.write_handover` returns the path.
- `NEW NAME:` `CheckpointManager.open_handover_for`, `CheckpointManager.close_handover`; command action `handover.create`.
- Commit subject: `feat: add handover document lifecycle and cli (E04-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S07 — Context checkpoint hooks (§41) and `ON_AGENT_END` context-update requirement

**Status:** TODO
**Type:** feat
**Requirements:** §41, §22, §20, §137 (Inv. 2, 12), §6.2
**Depends on:** E04-S06, E04-S04
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Mandatory context checkpoints are enforced by hooks, not by prompts: PARTIAL, user pause and budget exhaustion all produce checkpoint + handover, and a run cannot end without updating context or stating why.

#### Scope
- In: `partial` event path, `PAUSE`/`BUDGET` handover triggers, `ON_AGENT_END` MUST validation with one repair turn.
- Out: `FALLBACK` (E01-S28), `RECOVERY` (E01-S28), template wording (E04-S14).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/executor.py` | modify | — (`DefaultAgentExecutor._on_final_output`: PARTIAL path; `_block_budget` and `pause` attach the BUDGET/PAUSE handover to the checkpoint they already take; `ON_AGENT_END` repair turn) |
| `src/walk/runtime/output_applier.py` | modify | — (`partial` event with `payload["handover_present"]`) |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `agent_end_requires_context_update` (the PAUSE/BUDGET handovers are written by the executor, E02-S08 Behavior 3) |
| `src/walk/orchestrator/service.py` | modify | — (`pause(run_id)` delegates to `AgentExecutor.pause`; no checkpoint of its own) |
| `tests/runtime/test_executor_partial.py` | create | — |
| `tests/runtime/test_executor_agent_end_context.py` | create | — |
| `tests/hooks/test_builtins_checkpoints.py` | create | — |

#### Interface contract
See INTERFACES.md §1.13 `AgentExecutor`, `CheckpointManager`; §1.1 `Orchestrator.pause`. No new public signatures. Hook payloads: `ON_AGENT_END.payload = {"status", "context_updates": int, "no_context_change_reason": str | None}`.

#### Behavior
1. `FINAL_OUTPUT(status=PARTIAL)` without `output.handover` → `OutputInvalid("handover required for PARTIAL")` → one repair turn; second failure → run `FAILED`.
2. PARTIAL with handover: `checkpoint(HANDOFF, handover=build_handover(reason="PARTIAL", partial_output=output))`, `ON_AGENT_HANDOFF` chain, workflow event `partial` with `payload.handover_present=True` (story table row IMPLEMENTING→IMPLEMENTING), run state `COMPLETED`, scheduler re-queues at once with `escalation_bump` when `output.effort_request` is an UPGRADE (ADR-0011 D-6).
3. `Orchestrator.pause(run_id)` → `AgentExecutor.pause(run_id)`: adapter `cancel`, one PAUSE checkpoint that now carries `handover(reason="PAUSE")` (built inside the executor), run `PAUSED_BY_USER`. `pause()` without run id fires `ON_PROJECT_PAUSE`, whose MUST builtin `builtin.pause_all_runs` (E02-S08) calls `AgentExecutor.pause` for every RUNNING run — no second checkpoint.
4. Budget exhausted with hard action `BLOCK`: the executor's `_block_budget` takes `checkpoint(HANDOFF, handover(reason="BUDGET"))` in place of its plain PAUSE checkpoint and ends the run `BLOCKED_BUDGET`. The `ApprovalRequest(kind="ESCALATION", approver=USER)` comes from the `ON_BUDGET_EXHAUSTED` MUST builtin `builtin.budget_escalate` (E02-S08), which fires inside the run's task and therefore never checkpoints or stops the run (E02-S08 Behavior 3); Level-3 `EscalationRequest` routing is E05-S02.
5. `ON_AGENT_END` MUST (priority 10): if `status != FAILED` and `context_updates` empty and `no_context_change_reason` is `None` → `HookFailed` is **not** raised directly; instead the executor, before firing `ON_AGENT_END`, validates this rule and issues one repair turn ("add context_updates or no_context_change_reason"); if still violated → `OutputInvalid`, run `FAILED`, `ON_TASK_FAILED` not fired (retry path is the normal repair budget). The hook itself asserts the invariant and raises `HookFailed` if reached in violation (defence in depth).
6. `HANDOVER_CREATED` ledger count equals the number of `HO-*.md` files after any sequence of these triggers.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a fake run returning PARTIAL with handover When executed Then HANDOFF checkpoint, `HO-0001.md`, workflow transition event `partial`, item re-queued | `tests/runtime/test_executor_partial.py::test_partial_creates_handover_and_requeues` |
| 2 | Given PARTIAL without handover then a repaired output When executed Then one `repair_turns == 1` and success | `tests/runtime/test_executor_partial.py::test_partial_without_handover_repair_turn` |
| 3 | Given PARTIAL without handover twice When executed Then run `FAILED` with `failure_reason` containing `handover required` | `tests/runtime/test_executor_partial.py::test_partial_without_handover_twice_fails` |
| 4 | Given PARTIAL with `effort_request UPGRADE` When re-queued Then next `EffortResolution.escalation_bump == 1` | `tests/runtime/test_executor_partial.py::test_partial_upgrade_bumps_next_run` |
| 5 | Given a RUNNING fake run When `Orchestrator.pause(run_id)` Then PAUSE checkpoint, handover `reason=PAUSE`, state `PAUSED_BY_USER` | `tests/hooks/test_builtins_checkpoints.py::test_pause_agent_checkpoints_with_handover` |
| 6 | Given two RUNNING runs When `walk pause` Then two PAUSE checkpoints | `tests/hooks/test_builtins_checkpoints.py::test_pause_project_checkpoints_all` |
| 7 | Given `BudgetManager.meter` returning EXHAUSTED(BLOCK) When fired Then handover `reason=BUDGET`, run `BLOCKED_BUDGET`, `ApprovalRequest(kind=ESCALATION)` pending | `tests/hooks/test_builtins_checkpoints.py::test_budget_exhausted_handover_and_escalation` |
| 8 | Given COMPLETED output with empty `context_updates` and no reason, then repaired When executed Then success with `repair_turns == 1` | `tests/runtime/test_executor_agent_end_context.py::test_agent_end_missing_context_update_repair` |
| 9 | Given the violation twice When executed Then run `FAILED` and no `ON_AGENT_END` violation reached the hook | `tests/runtime/test_executor_agent_end_context.py::test_agent_end_missing_context_update_twice_fails` |
| 10 | Given `status=FAILED` with no context updates When executed Then no repair turn | `tests/runtime/test_executor_agent_end_context.py::test_agent_end_failed_status_exempt` |
| 11 | Given `no_context_change_reason="read-only review"` When executed Then accepted | `tests/runtime/test_executor_agent_end_context.py::test_agent_end_reason_accepted` |
| 12 | Given the hook fired directly with a violating payload Then `HookFailed` | `tests/hooks/test_builtins_checkpoints.py::test_agent_end_hook_raises_on_violation` |
| 13 | Given PARTIAL + PAUSE + BUDGET in one test When counted Then `HANDOVER_CREATED` events == `HO-*.md` files == 3 | `tests/hooks/test_builtins_checkpoints.py::test_handover_ledger_matches_documents` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --kind HANDOVER_CREATED --item STORY-0001` and `ls .ai/handovers/` showing equal counts.

#### Notes
- ARCHITECTURE §4.1 rows `ON_AGENT_END`, `ON_BUDGET_EXHAUSTED`, `ON_PROJECT_PAUSE`, `ON_AGENT_HANDOFF`; §7 Invariant 2 mechanism.
- Pitfall: do not fire `ON_AGENT_END` before validation; the repair turn uses the same `OutputInvalid` path as schema failures (ADR-0004 D-3) and counts against `repair_turns` (max 1).
- Commit subject: `feat: enforce context checkpoints and context updates at run end (E04-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S08 — Context ranking engine (ADR-0012)

**Status:** TODO
**Type:** feat
**Requirements:** §40, §42, §43, §6.8, §138 (Excessive Context Cost, Hallucinated Project State)
**Depends on:** E04-S03, E04-S05, E01-S24
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`ContextManager.build` admits ranked candidates within the token budget using the deterministic ADR-0012 scoring, orders the bundle per §6.8, and produces byte-identical bundles for identical inputs.

#### Scope
- In: `DefaultContextRanker`, `ContextCandidate`, `RankingConstants`, greedy admission, ordering, `fingerprint`, mandatory-tier integration with real `relevant_for` and freshness.
- Out: concrete candidate producers for source (E04-S09), evidence/decisions/siblings (E04-S10), code graph (E04-S12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/context/ranker.py` | create | `ContextCandidate`, `RankingConstants`, `RANKING_V1`, `DefaultContextRanker`, `CandidateProducer` |
| `src/walk/context/protocols.py` | modify | `ContextRanker` |
| `src/walk/context/models.py` | modify | `ContextBundle.fingerprint` |
| `src/walk/context/service.py` | modify | — (`DefaultContextManager.build` steps 2e, 3–8 with ranker; constructor takes `producers: list[CandidateProducer]`) |
| `src/walk/improvement/catalog.py` | modify | — (`BehaviorVersionCatalog` registers `CONTEXT_FORMAT/context_ranking 1.0`) |
| `tests/context/test_ranker.py` | create | — |
| `tests/context/test_service_ranking.py` | create | — |

#### Interface contract
```python
# src/walk/context/ranker.py
RelevanceTag = Literal["DIRECT", "PARENT", "AFFECTED_SYSTEMS", "GRAPH", "KEYWORD"]


class ContextCandidate(WalkModel):
    item: ContextItem  # score/mandatory filled by the ranker
    relevance_tag: RelevanceTag
    graph_distance: int | None = None  # for GRAPH
    directly_linked: bool = False  # INVALID allowed only when True
    updated_at: datetime


class RankingConstants(FrozenModel):
    relevance: dict[RelevanceTag, float] = {
        "DIRECT": 1.0,
        "PARENT": 0.8,
        "AFFECTED_SYSTEMS": 0.6,
        "GRAPH": 0.5,
        "KEYWORD": 0.3,
    }
    freshness: dict[FreshnessStatus, float] = {CURRENT: 1.0, POSSIBLY_STALE: 0.7, INVALID: 0.0}
    source_weight_dev: float = 1.2
    source_weight_non_dev: float = 0.5
    evidence_weight_review: float = 1.5
    graph_weight_high_effort: float = 1.3
    chars_per_token: float = 3.5
    version: str = "1.0"


RANKING_V1 = RankingConstants()


class CandidateProducer(Protocol):
    kinds: tuple[ContextItemKind, ...]

    async def produce(
        self, request: ContextRequest, item: WorkItem, feature: Feature | None, head: Sha
    ) -> list[ContextCandidate]: ...


class ContextRanker(Protocol):
    def score(self, candidate: ContextCandidate, request: ContextRequest) -> float: ...
    def admit(
        self, candidates: list[ContextCandidate], budget_left: int, request: ContextRequest
    ) -> tuple[list[ContextItem], int]:
        """Greedy by score desc (ties: updated_at desc, id asc); returns (admitted, excluded_count)."""

    def order(
        self, mandatory: list[ContextItem], admitted: list[ContextItem]
    ) -> list[ContextItem]: ...


# ContextBundle
def fingerprint(self) -> str:
    """sha256 over (request.model_dump_json(), head_commit, [(i.id, i.kind, i.content, i.requires_verification) for i in items]). Excludes built_at."""
```

#### Behavior
1. `score = relevance[tag] × freshness[status] × role_weight`; `GRAPH` relevance = `0.5 / graph_distance` (distance ≥ 1); `freshness=None` counts as `CURRENT`.
2. `role_weight`: `SOURCE_FILE` ×1.2 for `SENIOR_DEV`/`LEAD_DEV`, ×0.5 for `QC`/`PRODUCT_OWNER`/`DESIGN_LEADER`; `EVIDENCE` ×1.5 for `QC` and `LEAD_DEV`; `CODE_GRAPH` ×1.3 when `request.effort ∈ {HIGH, VERY_HIGH}`; otherwise ×1.0.
3. INVALID candidates are excluded unless `directly_linked`, in which case they are admitted with `requires_verification=True` and `score` computed with freshness factor 0.7 (treated as POSSIBLY_STALE for ordering) — documented deviation to make "included with requires_verification" meaningful.
4. `admit`: sort by `(−score, −updated_at, id)`; add while `tokens_estimate ≤ budget_left`; skipped candidates count in `excluded_count`; a candidate larger than the whole budget is excluded.
5. `order`: mandatory in §40 order, then `CODE_GRAPH`, then `SOURCE_FILE`, then the rest by score.
6. `build`: mandatory tier (E01-S24) now uses `DecisionManager.relevant_for` for step 2e and `assess_freshness` for step 3; producers run in constructor order; `budget_left = token_budget − Σ mandatory tokens` (negative → no candidates, `excluded_count` = all).
7. Determinism: given the same DB, `.ai/` tree, HEAD and request, two `build()` calls return equal `fingerprint()`.
8. `RANKING_V1.version` is registered as `BehaviorVersion(kind=CONTEXT_FORMAT, name="context_ranking", version="1.0", stage=DEFAULT)` and recorded in `LedgerEvent.behavior_versions` of `AGENT_RUN_STARTED`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given tags DIRECT/PARENT/AFFECTED_SYSTEMS/KEYWORD, CURRENT, SENIOR_DEV, DECISION kind When scored Then 1.0/0.8/0.6/0.3 | `tests/context/test_ranker.py::test_relevance_constants` |
| 2 | Given GRAPH distance 2 Then 0.25 | `tests/context/test_ranker.py::test_graph_distance_relevance` |
| 3 | Given POSSIBLY_STALE Then factor 0.7 | `tests/context/test_ranker.py::test_freshness_factor` |
| 4 | Given SOURCE_FILE for SENIOR_DEV vs QC Then ×1.2 vs ×0.5 | `tests/context/test_ranker.py::test_role_weight_source` |
| 5 | Given EVIDENCE for QC Then ×1.5; for SENIOR_DEV ×1.0 | `tests/context/test_ranker.py::test_role_weight_evidence` |
| 6 | Given CODE_GRAPH at HIGH vs MEDIUM Then ×1.3 vs ×1.0 | `tests/context/test_ranker.py::test_graph_weight_effort` |
| 7 | Given INVALID not directly linked Then excluded; directly linked Then admitted with `requires_verification` | `tests/context/test_ranker.py::test_invalid_exclusion_rule` |
| 8 | Given equal scores When admitted Then newer `updated_at` first, then id asc | `tests/context/test_ranker.py::test_tie_break` |
| 9 | Given budget 100 and candidates of 60/60/30 tokens When admitted Then two admitted, `excluded_count == 1` | `tests/context/test_ranker.py::test_greedy_admission_and_excluded_count` |
| 10 | Given mixed kinds When ordered Then mandatory, CODE_GRAPH, SOURCE_FILE, rest | `tests/context/test_ranker.py::test_order` |
| 11 | Given a real `.ai/` tree with decisions and a stale doc When `build` twice Then equal `fingerprint()` | `tests/context/test_service_ranking.py::test_build_is_deterministic` |
| 12 | Given mandatory tokens exceeding budget When `build` Then zero candidates, all excluded, mandatory intact | `tests/context/test_service_ranking.py::test_mandatory_never_trimmed` |
| 13 | Given ACCEPTED decision via `relevant_for` When `build` Then DECISION item mandatory | `tests/context/test_service_ranking.py::test_mandatory_decisions_from_relevant_for` |
| 14 | Given `AGENT_RUN_STARTED` event Then `behavior_versions["CONTEXT_FORMAT/context_ranking"] == "1.0"` | `tests/context/test_service_ranking.py::test_ranking_version_in_ledger` |

#### Evidence required
- Quality gate output.
- Demo: pytest transcript of `test_build_is_deterministic`; `walk runs show RUN_ID` printing `context_manifest.total_tokens_estimate` and `stale_item_ids`.

#### Notes
- ADR-0012 D-1…D-4, D-7. Constants live in one frozen model so a future `CONTEXT_FORMAT` version only swaps `RANKING_V1`.
- `NEW NAME:` `ContextCandidate`, `RankingConstants`, `RANKING_V1`, `CandidateProducer`, `RelevanceTag`, `ContextBundle.fingerprint`, `DefaultContextRanker`.
- Behavior rule 3 (INVALID directly linked ordered as 0.7) is a planner decision; record in the story Notes if the architect prefers 0.0 with forced admission.
- Commit subject: `feat: add context ranking engine (E04-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S09 — Source slicing

**Status:** TODO
**Type:** feat
**Requirements:** §40, §43, §6.8, §138 (Excessive Context Cost)
**Depends on:** E04-S08
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Source files enter the bundle as symbol-centred windows of at most 400 lines instead of whole files, with folder expansion when no code graph is available.

#### Scope
- In: `slicing.py`, `SourceFileProducer`, symbol extraction, folder expansion (ADR-0012 D-6 half).
- Out: graph-derived file seeds (E04-S12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/context/slicing.py` | create | `slice_source`, `extract_symbols`, `SourceWindow`, `MAX_SLICE_LINES`, `MAX_SOURCE_BYTES` |
| `src/walk/context/producers.py` | create | `SourceFileProducer` |
| `src/walk/context/__init__.py` | modify | re-exports |
| `src/walk/cli/composition.py` | modify | — (register `SourceFileProducer`) |
| `tests/context/test_slicing.py` | create | — |
| `tests/context/test_producers_source.py` | create | — |

#### Interface contract
```python
MAX_SLICE_LINES = 400
MAX_SOURCE_BYTES = 1_048_576


class SourceWindow(FrozenModel):
    start_line: int
    end_line: int
    symbols: list[str]


def extract_symbols(contract: StoryContract | None, feature: FeatureContext | None) -> list[str]:
    """Identifiers matching r'\b[A-Z][A-Za-z0-9_]{2,}\b' in contract.goal, contract.acceptance_criteria and feature.affected_systems; de-duplicated, sorted."""


def slice_source(
    path: str, text: str, symbols: list[str], *, max_lines: int = MAX_SLICE_LINES
) -> tuple[str, list[SourceWindow]]:
    """Windows centred on symbol occurrences, merged when overlapping, total ≤ max_lines; header '// <path> lines a-b' per window."""


class SourceFileProducer:  # CandidateProducer, kinds=(SOURCE_FILE,)
    def __init__(
        self, repo_root_resolver: Callable[[], str], graph_available: Callable[[], bool]
    ) -> None: ...
```

#### Behavior
1. Seeds = `feature.relevant_files ∪ paths mentioned in contract (regex r'[\w./-]+\.(cs|asmdef|json|yaml|md|unity|prefab)')`; when `graph_available()` is false, add every file directly inside the directories of `relevant_files` (depth 1, same extensions).
2. Files larger than `MAX_SOURCE_BYTES`, binary (NUL byte in first 8 KB) or missing are skipped silently (counted as `excluded_count` by the ranker only if produced; here they are not produced).
3. No symbols found in a file → one window: first `min(len, max_lines)` lines.
4. Windows: each occurrence gets `±(max_lines // (2·k))` lines where `k` = number of occurrences, capped so the total ≤ `max_lines`; overlapping windows merge; header line per window.
5. Candidate: `relevance_tag=DIRECT` for `relevant_files`, `AFFECTED_SYSTEMS` for contract-mentioned paths, `KEYWORD` for folder-expanded files; `updated_at` = file mtime from git (`GitProvider` not needed: use `os.stat` → documented non-determinism risk; instead use the file's last commit? **Decision:** `updated_at` = fixed epoch for SOURCE_FILE so ties break by id → deterministic).
6. `tokens_estimate = ceil(len(content) / 3.5)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a contract mentioning `SaveManager` and `LoadGame` When `extract_symbols` Then both, sorted, no duplicates | `tests/context/test_slicing.py::test_extract_symbols` |
| 2 | Given a 1000-line file with one symbol at line 600 When sliced Then one window of 400 lines containing line 600 | `tests/context/test_slicing.py::test_single_window_centred` |
| 3 | Given two symbols at lines 50 and 900 When sliced Then two windows, total ≤ 400 lines | `tests/context/test_slicing.py::test_two_windows_total_cap` |
| 4 | Given two symbols 10 lines apart When sliced Then one merged window | `tests/context/test_slicing.py::test_overlapping_windows_merge` |
| 5 | Given no symbol match When sliced Then first 400 lines | `tests/context/test_slicing.py::test_no_symbols_head_window` |
| 6 | Given a 2 MB file When produced Then not produced | `tests/context/test_producers_source.py::test_large_file_skipped` |
| 7 | Given a file with NUL bytes When produced Then skipped | `tests/context/test_producers_source.py::test_binary_skipped` |
| 8 | Given `graph_available=False` and `relevant_files=["Assets/Save/SaveManager.cs"]` with sibling `SaveData.cs` When produced Then both produced, sibling tagged KEYWORD | `tests/context/test_producers_source.py::test_folder_expansion_without_graph` |
| 9 | Given `graph_available=True` Then no folder expansion | `tests/context/test_producers_source.py::test_no_expansion_with_graph` |
| 10 | Given a produced candidate Then `tokens_estimate == ceil(len/3.5)` and header lines present | `tests/context/test_producers_source.py::test_candidate_tokens_and_header` |

#### Evidence required
- Quality gate output.
- Demo: `walk runs show RUN_ID --json` → `context_manifest.item_ids` containing `SOURCE_FILE:Assets/Save/SaveManager.cs#1-400`.

#### Notes
- ADR-0012 D-5, D-6. Item id format `SOURCE_FILE:<path>#<start>-<end>`.
- `NEW NAME:` module `walk.context.slicing`, `walk.context.producers`, `SourceFileProducer`, `SourceWindow`.
- Commit subject: `feat: add source slicing producer for context (E04-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S10 — Evidence, decision and sibling-context candidates

**Status:** TODO
**Type:** feat
**Requirements:** §40, §47, §44, §39, §6.6
**Depends on:** E04-S08, E01-S06
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The ranked tier offers evidence, non-accepted decisions and sibling story contexts as candidates (INTERFACES §5.4 steps 4i–4j).

#### Scope
- In: `EvidenceProducer`, `DecisionProducer`, `SiblingContextProducer`.
- Out: code graph (E04-S12); evidence ranking in verdicts (E03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/context/producers.py` | modify | `EvidenceProducer`, `DecisionProducer`, `SiblingContextProducer` |
| `src/walk/cli/composition.py` | modify | — (register producers in order: Evidence, Decision, Sibling, Source) |
| `tests/context/test_producers_evidence.py` | create | — |
| `tests/context/test_producers_decisions.py` | create | — |
| `tests/context/test_producers_siblings.py` | create | — |

#### Interface contract
```python
class EvidenceProducer:  # kinds=(EVIDENCE,)
    def __init__(self, evidence: EvidenceManager) -> None: ...


class DecisionProducer:  # kinds=(DECISION,)
    def __init__(self, decisions: DecisionManager, repo: DecisionRepository) -> None: ...


class SiblingContextProducer:  # kinds=(FEATURE_CONTEXT,) — sibling STORY/TASK items rendered as short cards
    def __init__(self, workflow: WorkflowManager) -> None: ...
```
All implement `CandidateProducer.produce(request, item, feature, head)`.

#### Behavior
1. `EvidenceProducer`: `EvidenceManager.for_item(item.id)` → latest `Evidence` per `EvidenceKind` (by `produced_at`), one candidate each: content = kind, description, uri, metrics JSON, `rank` (§47); `relevance_tag=DIRECT`; `updated_at=produced_at`; freshness `None`.
2. `DecisionProducer`: decisions with status `PROPOSED` or `SUPERSEDED` linked to the item/ancestors or overlapping `feature.affected_systems`; `relevance_tag=AFFECTED_SYSTEMS` (0.6); ACCEPTED ones are excluded (already mandatory).
3. `SiblingContextProducer`: other STORY/TASK children of the same parent feature, excluding `item`; card = id, title, state, `contract.goal`, first 3 acceptance criteria; `relevance_tag=AFFECTED_SYSTEMS` (0.6); `updated_at=sibling.updated_at`; cancelled siblings excluded.
4. Keyword relevance: any producer may downgrade to `KEYWORD` (0.3) when the only link is a title word match with the item title (used by `SiblingContextProducer` for siblings under a different parent that share ≥ 2 title words of length ≥ 4).
5. Producers never raise on empty data; a `TransientError` from `EvidenceManager` propagates.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given 3 AUTOMATED_TEST and 1 QC_REPORT evidence When produced Then 2 candidates (latest per kind) with `rank` in content | `tests/context/test_producers_evidence.py::test_latest_per_kind` |
| 2 | Given no evidence Then empty list | `tests/context/test_producers_evidence.py::test_no_evidence_empty` |
| 3 | Given PROPOSED, SUPERSEDED and ACCEPTED decisions on the feature When produced Then only PROPOSED and SUPERSEDED | `tests/context/test_producers_decisions.py::test_non_accepted_only` |
| 4 | Given a PROPOSED decision overlapping `affected_systems` only When produced Then included with tag AFFECTED_SYSTEMS | `tests/context/test_producers_decisions.py::test_overlap_by_systems` |
| 5 | Given STORY-0002 and STORY-0003 (CANCELLED) under FEAT-0001 When producing for STORY-0001 Then one sibling card | `tests/context/test_producers_siblings.py::test_siblings_exclude_self_and_cancelled` |
| 6 | Given a story under another feature sharing title words "Inventory Panel" When produced Then tag KEYWORD | `tests/context/test_producers_siblings.py::test_keyword_sibling` |
| 7 | Given producers registered When `build` runs on the fixture repo Then bundle contains EVIDENCE and DECISION items after SOURCE_FILE items | `tests/context/test_producers_evidence.py::test_build_integration_order` |

#### Evidence required
- Quality gate output.
- Demo: `walk runs show RUN_ID --json` → `context_manifest.item_ids` includes `EVIDENCE:EVD-000001` and `DECISION:DEC-0002`.

#### Notes
- Item id formats: `EVIDENCE:<EvidenceId>`, `DECISION:<DecisionId>`, `SIBLING:<WorkItemId>`.
- `NEW NAME:` `EvidenceProducer`, `DecisionProducer`, `SiblingContextProducer`.
- Commit subject: `feat: add evidence, decision and sibling context producers (E04-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S11 — `GraphifyProvider` (`CodeGraphProvider` via CLI, optional)

**Status:** TODO
**Type:** feat
**Requirements:** §43, §129, §40, §30
**Depends on:** E01-S23, E02-S02
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `CodeGraphProvider` backed by the `graphify` CLI answers neighbourhood and impact questions from `graphify-out/graph.json`, and its absence degrades gracefully.

#### Scope
- In: `GraphifyProvider`, graph.json reader, dirty batching, health/preflight, bootstrap `.gitignore`, `FakeCodeGraphProvider`.
- Out: use in context (E04-S12); `impact` use for CHANGE analysis (E07-S07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/graphify/__init__.py` | create | `GraphifyProvider` |
| `src/walk/integrations/graphify/provider.py` | create | `GraphifyProvider` |
| `src/walk/integrations/graphify/graph_file.py` | create | `GraphFile`, `load_graph_file` |
| `src/walk/integrations/preflight.py` | modify | — (`graphify` component, non-required) |
| `src/walk/orchestrator/bootstrap.py` | modify | — (append `graphify-out/` to repo `.gitignore`; ADR-0020) |
| `src/walk/cli/composition.py` | modify | — (`code_graph = GraphifyProvider(...) if manifest.tools["graphify"].state == READY else None`) |
| `tests/fakes/fake_code_graph_provider.py` | create | `FakeCodeGraphProvider` |
| `tests/fixtures/graphify/graph.json` | create | — |
| `tests/integrations/graphify/test_provider.py` | create | — |
| `tests/integrations/graphify/test_graph_file.py` | create | — |
| `tests/integrations/test_preflight_graphify.py` | create | — |

#### Interface contract
```python
# src/walk/integrations/graphify/graph_file.py — minimal shape assumed from graphify-out/graph.json
class GraphFile(FrozenModel):
    nodes: list[
        GraphNode
    ]  # from json nodes[{id, type, path?, name}] ; type mapped to GraphNode.kind (unknown → "file")
    edges: list[GraphEdge]  # from json edges[{source, target, type}]
    communities: dict[str, list[str]]  # community id → node ids (optional in file)


def load_graph_file(path: str) -> GraphFile: ...  # ConfigError on missing/invalid file


class GraphifyProvider:  # CodeGraphProvider, provider = "graphify"
    def __init__(self, runner: SubprocessRunner, out_dir: str = "graphify-out") -> None: ...

    # methods verbatim INTERFACES.md §2.6
```

#### Behavior
1. `health(repo)`: `READY` iff `graphify --version` exits 0 and `<repo>/graphify-out/graph.json` exists; `MISSING` if CLI absent; `MISCONFIGURED` if CLI present but no graph (detail "run walk doctor --fix or graphify .").
2. `build(repo, incremental)`: runs `graphify .` in `repo` (incremental flag is advisory: dirty set is cleared after a successful run; graphify itself decides incrementality); returns sha256 of `graph.json`; non-zero exit → `ToolCrashed`.
3. `mark_dirty(paths)` adds to an in-memory set; `build(incremental=True)` with an empty dirty set is a no-op returning the current sha.
4. `neighbors(repo, seeds, depth)`: seeds matched by `path` (exact) or `name` (exact); BFS over undirected edges up to `depth`; returns the induced subgraph; unknown seeds ignored; empty result for no match.
5. `impact(repo, changed_paths)`: nodes reachable via reverse edges (`target == changed`) transitively; de-duplicated, sorted by id.
6. `query(repo, question)`: runs `graphify query "<question>"` and returns stdout as markdown; empty stdout → `""`.
7. Preflight lists `graphify` under `tools` as **not required**; `IntegrationManager.code_graph` is `None` when not READY; `walk doctor` prints `graphify: missing (recommended)` and still exits 0.
8. Bootstrap appends `graphify-out/` to the repo `.gitignore` once.
9. `FakeCodeGraphProvider` loads a `GraphFile` directly and records `mark_dirty`/`build` calls.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the fixture graph.json When loaded Then node/edge counts match and unknown type maps to `file` | `tests/integrations/graphify/test_graph_file.py::test_load_graph_file` |
| 2 | Given an invalid JSON file When loaded Then `ConfigError` | `tests/integrations/graphify/test_graph_file.py::test_load_invalid_raises` |
| 3 | Given fake runner with CLI present and graph file When `health` Then READY; without file Then MISCONFIGURED; without CLI Then MISSING | `tests/integrations/graphify/test_provider.py::test_health_states` |
| 4 | Given fake runner exit 1 When `build` Then `ToolCrashed` | `tests/integrations/graphify/test_provider.py::test_build_failure_raises` |
| 5 | Given dirty set empty When `build(incremental=True)` Then runner not invoked | `tests/integrations/graphify/test_provider.py::test_incremental_noop_when_clean` |
| 6 | Given seed `Assets/Save/SaveManager.cs` depth 2 When `neighbors` Then nodes within 2 hops only | `tests/integrations/graphify/test_provider.py::test_neighbors_depth` |
| 7 | Given changed `SaveData.cs` When `impact` Then reverse dependents transitively, sorted | `tests/integrations/graphify/test_provider.py::test_impact_reverse_edges` |
| 8 | Given unknown seed When `neighbors` Then empty neighbourhood | `tests/integrations/graphify/test_provider.py::test_neighbors_unknown_seed_empty` |
| 9 | Given no graphify on PATH When preflight Then `tools.graphify.state == missing` and preflight passes | `tests/integrations/test_preflight_graphify.py::test_graphify_optional` |
| 10 | Given bootstrap twice Then `.gitignore` contains `graphify-out/` once | `tests/integrations/test_preflight_graphify.py::test_bootstrap_gitignore_once` |
| 11 | Given real `graphify` (integration-marked) When `build` then `neighbors` Then non-empty | `tests/integrations/graphify/test_provider.py::test_real_graphify_roundtrip` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor` line `graphify: ready 0.x` or `missing (recommended)`.

#### Notes
- ADR-0009 D-9. The JSON shape is an assumption; test 11 (integration) is the place to validate it against the installed version and record deviations in the story Notes.
- `NEW NAME:` `GraphFile`, `load_graph_file`, `FakeCodeGraphProvider` (listed in WBS §3.6).
- Commit subject: `feat: add code graph provider via graphify cli (E04-S11)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S12 — Code graph in context and refresh hooks

**Status:** TODO
**Type:** feat
**Requirements:** §40, §43, §42, §32
**Depends on:** E04-S11, E04-S08
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Code-graph neighbourhoods are ranked context candidates, graph-derived files seed source slicing, and the graph is kept fresh by hooks.

#### Scope
- In: `CodeGraphProducer`, graph seeds for `SourceFileProducer`, `ON_CODE_CHANGED → mark_dirty`, `ON_MERGED → build + relevant_files refresh`.
- Out: `impact` for CHANGE (E07-S07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/context/producers.py` | modify | `CodeGraphProducer` |
| `src/walk/context/service.py` | modify | — (graph file nodes feed `SourceFileProducer` seeds via `request`-scoped shared state `BuildScratch`) |
| `src/walk/context/models.py` | modify | `BuildScratch` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `code_changed_mark_dirty`, `merged_refresh_graph_and_files` |
| `src/walk/cli/composition.py` | modify | — |
| `tests/context/test_producers_graph.py` | create | — |
| `tests/hooks/test_builtins_graph.py` | create | — |

#### Interface contract
```python
class BuildScratch(WalkModel):
    """Per-build shared state between producers (not persisted)."""

    graph_file_paths: list[str] = []


class CodeGraphProducer:  # kinds=(CODE_GRAPH,)
    def __init__(self, code_graph_resolver: Callable[[], CodeGraphProvider | None]) -> None: ...
```
`ON_MERGED.payload = {"work_item_id", "pr_number", "diff_names": list[str]}` (from E03-S01).

#### Behavior
1. `CodeGraphProducer.produce`: if resolver returns `None` → `[]`; else `neighbors(seeds = feature.relevant_files ∪ feature.affected_systems, depth = request.code_graph_depth)`; one candidate per connected component of the neighbourhood (max 5), content = Markdown table `| node | kind | path |` + edge list, `relevance_tag=GRAPH`, `graph_distance` = min distance of the component to a seed, `updated_at` fixed epoch; nodes with `kind=file` and a path are appended to `BuildScratch.graph_file_paths`.
2. `SourceFileProducer` (runs after `CodeGraphProducer`) adds `BuildScratch.graph_file_paths` as seeds tagged `GRAPH` with the component distance.
3. Role weight ×1.3 at effort ≥ HIGH is applied by the ranker (E04-S08 rule 2) — verified end-to-end here.
4. `ON_CODE_CHANGED` default (priority 110): `code_graph.mark_dirty(payload["paths"])` when provider present.
5. `ON_MERGED` default (priority 100): `code_graph.build(incremental=True)`; then for the merged item's feature context, `relevant_files` ← existing ∪ `payload["diff_names"]` filtered to source extensions, written through `apply_updates(REPLACE, "Relevant Files")`.
6. Provider errors in hooks are `LOG_AND_CONTINUE`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `FakeCodeGraphProvider` with the fixture graph and seeds When produced Then ≤ 5 candidates tagged GRAPH with correct min distance | `tests/context/test_producers_graph.py::test_graph_candidates_components` |
| 2 | Given no provider Then no CODE_GRAPH items and folder expansion active | `tests/context/test_producers_graph.py::test_no_provider_fallback` |
| 3 | Given graph file nodes When build runs Then SOURCE_FILE candidates for those paths exist with tag GRAPH | `tests/context/test_producers_graph.py::test_graph_seeds_source_files` |
| 4 | Given effort HIGH vs MEDIUM When build Then CODE_GRAPH scores differ by ×1.3 | `tests/context/test_producers_graph.py::test_graph_weight_end_to_end` |
| 5 | Given `ON_CODE_CHANGED` with 2 paths Then fake `mark_dirty` called with them | `tests/hooks/test_builtins_graph.py::test_code_changed_marks_dirty` |
| 6 | Given `ON_MERGED` with diff names `Assets/A.cs`, `README.md` Then `build` called and feature `Relevant Files` gains `Assets/A.cs` only | `tests/hooks/test_builtins_graph.py::test_merged_refreshes_graph_and_relevant_files` |
| 7 | Given provider `build` raising `ToolCrashed` on `ON_MERGED` Then hook result FAILED and merge flow continues | `tests/hooks/test_builtins_graph.py::test_merged_graph_failure_continues` |

#### Evidence required
- Quality gate output.
- Demo: `walk runs show RUN_ID --json` → `context_manifest.item_ids` containing `CODE_GRAPH:component-1`.

#### Notes
- ADR-0012 D-6; ARCHITECTURE §4.1 rows `ON_CODE_CHANGED`, `ON_PR_OPENED / ON_MERGED`.
- `NEW NAME:` `CodeGraphProducer`, `BuildScratch`.
- Commit subject: `feat: add code graph context candidates and refresh hooks (E04-S12)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S13 — Improvement observations skeleton

**Status:** TODO
**Type:** feat
**Requirements:** §96, §99, §41, §32, §110
**Depends on:** E01-S16, E01-S27
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Agents and the kernel can record improvement observations as project-scoped `.ai/improvements/OBS-NNNN.md` documents (ARCHITECTURE §10 MVP skeleton), while every other improvement capability stays explicitly deferred.

#### Scope
- In: `walk.improvement` protocols/repository/service skeleton, `observe`, `AgentOutput.observations` application, two automatic signals, CLI listing.
- Out: `detect_signals`, retrospectives, candidates, versions (E07-S08, E10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/protocols.py` | create | `ImprovementManager` (INTERFACES §1.15) |
| `src/walk/improvement/repository.py` | create | `ObservationRepository` |
| `src/walk/improvement/service.py` | create | `DefaultImprovementManager` |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/memory/sections.py` | modify | `OBSERVATION_SECTIONS` |
| `src/walk/orchestrator/builtin_hooks.py` | modify | `improvement_observation_write`, `model_fallback_observe_repeated`, `context_stale_observe_repeated` |
| `src/walk/runtime/output_applier.py` | modify | — (applies `output.observations`) |
| `src/walk/cli/cmd_improvement.py` | create | `observations` |
| `src/walk/cli/app.py` | modify | — |
| `src/walk/cli/composition.py` | modify | — |
| `tests/improvement/test_service.py` | create | — |
| `tests/hooks/test_builtins_improvement.py` | create | — |
| `tests/runtime/test_applier_observations.py` | create | — |
| `tests/cli/test_cmd_improvement.py` | create | — |

#### Interface contract
```python
OBSERVATION_SECTIONS = (
    "Observed",
    "Potential Cause",
    "Possible Improvement",
    "Source Signal",
    "Evidence",
)


class DefaultImprovementManager:
    def __init__(
        self,
        repo: ObservationRepository,
        memory: MemoryManager,
        ledger: LedgerManager,
        hooks: HookManager,
        ids: IdFactory,
        clock: Clock,
        versions: BehaviorVersionCatalog,
        project_key: ProjectKey,
    ) -> None: ...

    # observe(), pinned_versions() implemented; others raise NotSupported with the owning story id
```
CLI: `walk improvement observations [--signal S] [--json]`.

#### Behavior
1. `observe(draft, actor, work_item_id, run_id, source_signal)`: id `OBS-NNNN` (project `id_sequences`, width 4), `scope=PROJECT`, `origin_project=project_key`; row in `improvement_observations`; ledger `IMPROVEMENT_OBSERVATION{source_signal, improvement_scope}`; fires `ON_IMPROVEMENT_OBSERVATION`.
2. `ON_IMPROVEMENT_OBSERVATION` MUST (priority 10): writes `.ai/improvements/OBS-NNNN.md` (`type: observation`, sections `OBSERVATION_SECTIONS`, `related.work_items`, `related.evidence`) via `MemoryManager.write`.
3. `DefaultOutputApplier` calls `observe` for each `AgentOutput.observations` entry with `source_signal="agent"`.
4. `ON_MODEL_FALLBACK` default (priority 120): count `MODEL_FALLBACK` ledger events for `work_item_id`; when ≥ 2 → `observe(source_signal="repeated_fallback", improvement_scope=MODEL_ROUTING)` once per item (guarded by an existing observation with the same signal and item).
5. `ON_CONTEXT_STALE` default (priority 120): count `CONTEXT_FRESHNESS` events for `run_id`; when ≥ 3 → `observe(source_signal="stale_context", improvement_scope=CONTEXT_FORMAT)` once per run.
6. `pinned_versions()` returns `BehaviorVersionCatalog.pinned()` (E02-S04).
7. `detect_signals`, `phase_retrospective`, `promote`, `create_candidate`, `review_candidate`, `register_version`, `set_stage` raise `NotSupported("<story id>")` with ids `E10-S02`, `E07-S08`, `E10-S06`, `E10-S04`, `E10-S04`, `E10-S05`, `E10-S05`.
8. Nothing is ever written to `$WALK_HOME` in this story (§110).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a draft When `observe` Then `OBS-0001`, row, ledger event and `.ai/improvements/OBS-0001.md` with 5 sections | `tests/improvement/test_service.py::test_observe_persists_and_writes_doc` |
| 2 | Given two observations Then ids `OBS-0001`, `OBS-0002` | `tests/improvement/test_service.py::test_observe_sequence_ids` |
| 3 | Given `promote("OBS-0001")` Then `NotSupported` mentioning `E10-S06` | `tests/improvement/test_service.py::test_deferred_methods_not_supported` |
| 4 | Given `pinned_versions()` Then equals catalog pins | `tests/improvement/test_service.py::test_pinned_versions_delegates` |
| 5 | Given a fake output with 2 observations When applied Then 2 docs with `Source Signal` = `agent` | `tests/runtime/test_applier_observations.py::test_applier_records_observations` |
| 6 | Given 2 `MODEL_FALLBACK` events for an item When `ON_MODEL_FALLBACK` fires Then one `repeated_fallback` observation; a third event adds none | `tests/hooks/test_builtins_improvement.py::test_repeated_fallback_observation_once` |
| 7 | Given 3 `CONTEXT_FRESHNESS` events in a run When `ON_CONTEXT_STALE` fires Then one `stale_context` observation | `tests/hooks/test_builtins_improvement.py::test_stale_context_observation_threshold` |
| 8 | Given 2 `CONTEXT_FRESHNESS` events Then no observation | `tests/hooks/test_builtins_improvement.py::test_stale_context_below_threshold` |
| 9 | Given `walk improvement observations --signal repeated_fallback --json` Then one row | `tests/cli/test_cmd_improvement.py::test_observations_filter` |
| 10 | Given any test in this story Then `$WALK_HOME` (tmp) stays empty | `tests/improvement/test_service.py::test_no_kernel_scope_writes` |

#### Evidence required
- Quality gate output.
- Demo: `walk improvement observations` → table `OBS-0001 | repeated_fallback | MODEL_ROUTING`.

#### Notes
- ADR-0008 D-1/D-2 (project scope only here). ARCHITECTURE §4.1 rows `ON_IMPROVEMENT_OBSERVATION`, `ON_MODEL_FALLBACK` default, `ON_CONTEXT_STALE` default.
- `NEW NAME:` `ObservationRepository`, `OBSERVATION_SECTIONS`.
- Commit subject: `feat: add improvement observations skeleton (E04-S13)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S14 — Task templates: context-first, stale verification, mandatory context updates

**Status:** TODO
**Type:** feat
**Requirements:** §40, §42, §41, §22, §6.8, §138 (Hallucinated Project State)
**Depends on:** E04-S08, E04-S07
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Rendered task prompts instruct agents to read context in §40 order, verify stale items against source, continue from a handover's `Next Action`, and always return context updates.

#### Scope
- In: six templates (`IMPLEMENT, REVIEW, QC, PLAN, DESIGN, TRIAGE`), rendering tests, template version `1.1`.
- Out: `DEBATE` (E05), `ANALYSIS`/`RETRO` (E07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/templates/IMPLEMENT.md.j2` | modify | — |
| `src/walk/agents/templates/REVIEW.md.j2` | modify | — |
| `src/walk/agents/templates/QC.md.j2` | modify | — |
| `src/walk/agents/templates/PLAN.md.j2` | modify | — |
| `src/walk/agents/templates/DESIGN.md.j2` | modify | — |
| `src/walk/agents/templates/TRIAGE.md.j2` | modify | — |
| `src/walk/agents/templates/_context_rules.md.j2` | create | — (shared include) |
| `src/walk/improvement/catalog.py` | modify | — (`PROMPT/<purpose>` versions → `1.1` for the six) |
| `tests/agents/test_templates_context_rules.py` | create | — |

#### Interface contract
`AgentManager.render_instructions(agent, item, purpose) -> str` unchanged. The include `_context_rules.md.j2` receives the `AgentInput` and renders:
- `## Reading order` — §40 steps 1–8 as a numbered list.
- `## Verification required` — present iff any `context.items[*].requires_verification`; lists item ids; sentence: "Items marked REQUIRES VERIFICATION must be checked against source before use."
- `## Continue from handover` — present iff `handover is not None`; quotes `handover.next_action` and `remaining_work`; sentence: "Continue from Next Action; do not redo Completed Work."
- `## Context updates (mandatory)` — always: "Return non-empty `context_updates` or set `no_context_change_reason`."
- `## Output` — path `.walk/output.json` reminder (from E01-S18, unchanged).

#### Behavior
1. Every stale item is listed as `- <id> (<status>: <reason>)` in `## Verification required`.
2. Sections appear in the order above, after the role/task sections of each template.
3. No template mentions a provider or model name (ADR-0013 D-5 lint applies to templates too — `walk doctor --strict` extended by one check on `templates/`).
4. `BehaviorVersionCatalog` reports `PROMPT/IMPLEMENT == "1.1"` (and the other five); `AGENT_RUN_STARTED.behavior_versions` carries it.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an input with two stale items When rendered (each of six purposes, parametrised) Then `## Verification required` lists both ids | `tests/agents/test_templates_context_rules.py::test_verification_section_lists_stale_items` |
| 2 | Given no stale items Then the section is absent | `tests/agents/test_templates_context_rules.py::test_verification_section_absent_when_current` |
| 3 | Given a handover Then `## Continue from handover` quotes `next_action` | `tests/agents/test_templates_context_rules.py::test_handover_section_present` |
| 4 | Given no handover Then absent | `tests/agents/test_templates_context_rules.py::test_handover_section_absent` |
| 5 | Given any input Then `## Reading order` has 8 numbered steps and `## Context updates (mandatory)` present | `tests/agents/test_templates_context_rules.py::test_reading_order_and_mandatory_updates` |
| 6 | Given the six templates Then none contains a provider name (list from the E02-S15 lint) | `tests/agents/test_templates_context_rules.py::test_templates_provider_neutral` |
| 7 | Given the catalog Then `PROMPT/IMPLEMENT` version is `1.1` | `tests/agents/test_templates_context_rules.py::test_template_version_bumped` |

#### Evidence required
- Quality gate output.
- Demo: `walk runs show RUN_ID --json` → `behavior_versions["PROMPT/IMPLEMENT"] == "1.1"`; rendered instructions excerpt from a test log.

#### Notes
- ADR-0004 D-4/D-5, ADR-0012 D-4, Invariant 2. Template changes are `BehaviorVersion kind=PROMPT` MINOR bumps.
- Commit subject: `feat: add context-first rules to task templates (E04-S14)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-S15 — Epic gate: §132 failover against real `.ai/` files (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §132, §22, §37, §42, §44, §130, §137 (Inv. 2, 8, 12), §138 (Context Drift), §3 (continuity across model and session loss)
**Depends on:** E04-S14, E04-S12, E04-S10, E04-S06, E03-S20
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
The §132 failover is proven with knowledge that exists only in `.ai/` files written by the kernel: feature context, handover and decision documents are read back after a restart, staleness is detected and flagged, and the continuing run completes while updating context.

#### Scope
- In: `tests/e2e/test_e04_gate.py`, shared e2e fixtures.
- Out: production code changes (any defect found → `bugfix` story `E04-Bxx`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e04_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e04_scenario` fixture |
| `tests/fakes/fake_model_adapter.py` | modify | — (script helper `interrupt_after_tool_calls(n)` reused from E03-S20; `context_updates` scripted) |

#### Interface contract
Fixture `e04_scenario(tmp_game_repo) -> E04Scenario` (dataclass-free `WalkModel` in conftest): `handle: KernelHandle`, `feature_id`, `story_id`, `implementer_run_id`, `relevant_file: str`. Adapters: `fake-codex/sim` (implementer, scripted with `interrupt_after_tool_calls(20, ...)` from E03-S20: checkpoints `START` seq 1, `PERIODIC` seq 2 after call 10, `PERIODIC` seq 3 after call 20, then hangs) and `fake-claude/sim` (fallback, scripted `COMPLETED` with `context_updates=[REPLACE "Remaining Work" → "- none"]`).

#### Behavior
Scenario steps (each a test, executed in order via the fixture's cached state):
1. Run the E03 §131 scenario until the story implementer's checkpoint `seq == 3` (the second `PERIODIC`, after tool call 20); the kernel is crashed with `simulate_crash` (E03-S20; `Orchestrator.stop()` would pause runs cleanly and recovery would not treat them as interrupted, ARCHITECTURE §5.3 step 1); `USER` records `DEC-0001` (`TECH`, related to the feature, `affected_systems=["SaveSystem"]`) via `DefaultDecisionManager.record` before restart.
2. Modify and commit `relevant_file` (listed in `FeatureContext.relevant_files`) on the work branch outside the kernel.
3. Restart with a new `kernel_instance`; recovery runs; `fake-codex` health is scripted unhealthy → fallback to `fake-claude`.
4. Assertions on the new run's `AgentInput`: `context` has a `FEATURE_CONTEXT` item with `requires_verification=True` and freshness `POSSIBLY_STALE`/`relevant files changed`; `handover` equals `from_document(read .ai/handovers/HO-0001.md)`; a `DECISION` item for `DEC-0001` marked mandatory; `instructions_markdown` contains `## Verification required` and `## Continue from handover`.
5. `ContextManager.build(request)` called twice returns equal `fingerprint()`.
6. The run completes; `.ai/features/FEAT-0001.md` `Remaining Work` is `- none` with `version` incremented and `freshness.commit == HEAD`.
7. Ledger: `CONTEXT_FRESHNESS` ≥ 1 for the feature doc; `HANDOVER_CREATED == 1`; `RECOVERY_RESUMED == 1`; `MODEL_FALLBACK == 1`; `DECISION_RECORDED == 1`.
8. If `CONTEXT_FRESHNESS` events for the run ≥ 3, exactly one `stale_context` observation exists; otherwise none (the scripted scenario yields exactly 1 → none).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the scenario at step 3 When the new run starts Then `FEATURE_CONTEXT` item is `POSSIBLY_STALE` with `requires_verification` | `tests/e2e/test_e04_gate.py::test_stale_feature_context_flagged` |
| 2 | Given the new run Then `AgentInput.handover` equals the document `HO-0001.md` parsed | `tests/e2e/test_e04_gate.py::test_handover_read_from_ai_file` |
| 3 | Given the new run Then `DEC-0001` is a mandatory DECISION item | `tests/e2e/test_e04_gate.py::test_decision_read_from_ai_file` |
| 4 | Given the new run Then instructions contain the verification and handover sections | `tests/e2e/test_e04_gate.py::test_instructions_contain_context_rules` |
| 5 | Given the same request When built twice Then equal fingerprints | `tests/e2e/test_e04_gate.py::test_bundle_deterministic` |
| 6 | Given the run completes Then feature `Remaining Work == "- none"`, version bumped, freshness commit == HEAD | `tests/e2e/test_e04_gate.py::test_context_updated_after_completion` |
| 7 | Given the ledger Then counts per Behavior 7 | `tests/e2e/test_e04_gate.py::test_ledger_trail` |
| 8 | Given the ledger Then no `stale_context` observation (threshold not met) | `tests/e2e/test_e04_gate.py::test_no_observation_below_threshold` |
| 9 | Given `fake-claude` run Then `handover_in_id == HO-0001` and branch HEAD descends from the interrupted run's `head_sha` | `tests/e2e/test_e04_gate.py::test_failover_continuity` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e04_gate.py` (9 passed).
- Demo transcript on the fixture repo after the test: `walk memory freshness FEAT-0001`, `walk handover show STORY-0001`, `walk decisions show DEC-0001`, `walk ledger query --kind MODEL_FALLBACK --kind RECOVERY_RESUMED`.

#### Notes
- Gate uses only `tests/fakes` adapters and a real temp git repo with `LocalWorkProvider`; no network.
- Any production change needed to pass is a separate `bugfix` story; this story's commit touches tests only.
- Commit subject: `feat: add epic 04 gate failover test over memory files (E04-S15)`.

#### Evidence (filled by implementer)
_pending_

---

### E04-R01 — Review E04

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 2, 8), §6.2, §6.10, §42
**Depends on:** E04-S15
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the E04 implementer where possible, §23) verifies every E04 story against the Definition of Done and the epic's invariants, recording defects as `bugfix` stories.

#### Scope
- In: stories E04-S01…S15 and their commits; `INTERFACES.md`/`DOMAIN-MODEL.md` deltas.
- Out: fixing defects (each becomes `E04-Bxx`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-04-persistent-studio-memory.md` | modify | — (review record appended; `E04-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md` | modify (only if drift found) | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5.

#### Behavior
1. For each story: `git show <sha>`; confirm Files table == changed files (extra files need commit-body justification); every acceptance-criterion test name exists and passes; coverage ≥ 90 % for touched modules.
2. Invariant 2: grep `src/walk` for writes under `.ai/` — only `walk/memory/service.py` (and `persistence`) may open files for writing under the memory root; `OutputApplier`/hooks go through `MemoryManager`.
3. Invariant 8: every ACCEPTED decision in SQLite has an `ai_path` file whose front matter `id` matches.
4. Determinism: `test_build_is_deterministic` and `test_bundle_deterministic` exist and pass twice in a row.
5. §37/§38 coverage: each field of `FeatureContext`/`BugContext` has a section constant and at least one parse test.
6. `NEW NAME:` items of E04 are listed in a review note for the architect and absent from or added to WBS §6.
7. Defects → `E04-Bxx` stories using the template; commit `docs: review epic 04 stories E04-S01..S15`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E04 story When DoD checklist applied Then every box checked or a `E04-Bxx` story exists | manual checklist recorded in this story's Evidence (no automated test) |
| 2 | Given `src/walk` When grepping `open(` / `write_text(` / `rename(` Then matches only under `walk/memory/` and `walk/persistence/` | `tests/architecture/test_memory_write_path.py::test_only_memory_writes_ai_tree` |
| 3 | Given the DB after the gate Then every `decisions.ai_path` exists with matching id | `tests/architecture/test_decisions_have_documents.py::test_decision_docs_exist` |
| 4 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % | gate output in Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after review commit.
- List of `E04-Bxx` stories created (or "none").

#### Notes
- Tests 2–3 are new architecture tests created by the reviewer (allowed: review tasks may add tests, never production code).
- Commit subject: `docs: review epic 04 stories E04-S01..S15 (E04-R01)`.

#### Evidence (filled by implementer)
_pending_
