# EPIC-06 — GDD Compiler

**Roadmap stage:** §135 Stage 6
**Goal.** A GDD is ingested, analysed for readiness, normalised into requirements with stable ids, decomposed into a phase plan of epics, features and stories carrying Executable Story Contracts, and traced from requirement to QC evidence with derived coverage.
**Requirements.** §48–§50, §51, §52, §57, §58, §66–§67 (scope), §73–§74, §137 (Inv. 7), §138 (Under-Specified GDD).
**Epic gate.** `tests/e2e/test_e06_gate.py`: a small fixture GDD (3 areas) is compiled by fake agents into one `Phase` with 2 epics / 3 features / 6 stories in `LocalWorkProvider`, `traceability.yaml` links every story to a requirement, `gdd-coverage.md` shows 0 % per area, one deliberate contradiction yields a Level-2 escalation.
**Branching.** `story/<ID>-<slug>` + worktree per story (COMMIT-POLICY §4); merge `--no-ff` after E06-R01.
**Preconditions.** E05-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green; E06-X01 committed before any E06 story starts (WBS §2 rule 3).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E06-X01 | Refine E06 against codebase | E05-R01 | LOW |
| E06-S01 | GDD ingestion: Markdown parsing to `GddRef` index and areas | E06-X01 | MEDIUM |
| E06-S02 | GDD readiness analysis run and findings | E06-S01, E05-S01 | HIGH |
| E06-S03 | Requirement normalisation and `traceability.yaml` | E06-S01 | MEDIUM |
| E06-S04 | `GddCompiler`, `Orchestrator.plan_phase`, `walk phase plan` | E06-S03, E03-S09 | HIGH |
| E06-S05 | Traceability chain queries | E06-S03, E03-S12 | MEDIUM |
| E06-S06 | GDD coverage computation and `gdd-coverage.md` | E06-S05 | MEDIUM |
| E06-S07 | Phase scope guard and scope assignment | E06-S04 | LOW |
| E06-S08 | Epic gate: GDD → one planned phase (e2e) | E06-S02, E06-S06, E06-S07 | MEDIUM |
| E06-R01 | Review E06 | E06-S08 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (rules; §3.4 payload keys incl. `phase_state`, §3.6 fakes and e2e fixtures, §3.9 templates).
2. `requirements/WAL_K_REQ.md` §48 (compilation pipeline), §49 (readiness detection list), §50–§51 (clarification and autonomy levels), §52 (hierarchy), §57 (Executable Story Contract), §58 (Definition of Ready), §66–§67 (phases, scope), §73 (traceability chain), §74 (coverage).
3. `DOMAIN-MODEL.md` §4.1 (`Project.gdd_paths`, `GddRef`, `Phase.scope_epic_ids`, `StoryContract`, `Epic/Feature.gdd_refs`, `WorkItemDraft`), §4.7 (`MemoryDocument`, `FeatureContext.relevant_gdd`), §4.8 (`EscalationRequest`, `AutonomyLevel`), §4.12 (`EvidenceKind`, ledger kinds).
4. `INTERFACES.md` §1.1 (`Orchestrator.plan_phase`, `KernelStatus.gdd_coverage`), §1.3 (`WorkflowManager.create/check_definition_of_ready/ready_items/gdd_coverage`), §1.8 (`MemoryManager`), §1.9 (`DecisionManager.escalate`), §2.2 (`WorkProvider.create/link`), §3.1–§3.2 (`in_phase_scope`, `ready`), §4 (routing), §6 (`walk phase plan`).
5. `ARCHITECTURE.md` §1.2 (`walk.workflow` owns traceability links; `walk.orchestrator` owns `GddCompiler`), §2.2 (import table: `workflow` may not import `memory`), §7 Inv. 7, §8 (`.ai/project/traceability.yaml`, `gdd-coverage.md`).
6. Existing code from E01-S10/S11 (`readiness.py`, `in_phase_scope` placeholder, `create_phase`), E03-S09 (feature PLAN flow, `walk feature add`), E03-S12 (integration step evidence), E04-S01 (`ensure_feature_context`), E05-S01/S02 (`escalate`, `EscalationRouter`).

Parallel sets (WBS §8): `{S01→S02} ∥ {S03→S05→S06}`; `{S04} ∥ {S05}`.

Planning decisions fixed for this epic (Autonomy Level 0 unless marked `NEW NAME:`):
- **GDD structure.** GDD files are Markdown. `#` = document title; each `##` heading is a GDD **area** (area key = upper-snake of the heading, e.g. `Meta Progression` → `META_PROGRESSION`); each `###` heading is a **section** (requirement candidate) addressed by `GddRef(path, anchor)` with a GitHub-style slug anchor. A `##` heading named `Glossary` (case-insensitive) is not an area; its `- **Term**: definition` bullets form the glossary.
- **Requirement ids.** `REQ-<AREA>-<NNN>` (3-digit minimum, per area, never reused); stored in `GddRef.requirement_id` (DOMAIN-MODEL §4.1 field reserved for Stage 6). `NEW NAME:` id format (DOMAIN-MODEL §2 has no requirement row).
- **Project data files.** `.ai/project/traceability.yaml`, `.ai/project/gdd-readiness.yaml` and `.ai/project/gdd-coverage.md` are written only through `MemoryManager.write_project_data` (E06-S01; ADR-0003 D-4 single writer) and read through `MemoryManager.read_project_data`. `NEW NAME:` both methods and `gdd-readiness.yaml` (ARCHITECTURE §8 lists the other two).
- **Structured agent output for compilation.** Readiness findings and the phase plan travel as fenced YAML blocks in `AgentOutput.result` (` ```walk-gdd-findings ` and ` ```walk-phase-plan `), parsed by the kernel with pydantic; invalid blocks are `OutputInvalid` (repair turn per ADR-0004). `NEW NAME:` both block labels. Rationale: `AgentOutput.new_tasks` cannot express parent links between drafts created in the same output.
- **Compile tasks.** Agent work for the compiler runs on project-level `TASK` items (`phase_id = None`) labelled `gdd-compile` plus `gdd:readiness` or `gdd:plan`, routed by label like the E07 intake tasks: `gdd:readiness` → DESIGN_LEADER if enabled else ORCHESTRATOR, purpose `ANALYSIS`; `gdd:plan` → ORCHESTRATOR, purpose `PLAN`.
- **Planned item states.** The compiler creates EPICs, FEATUREs and STORYs in `IDEA`; epics and features carry label `gdd-planned`. Stories are promoted to READY by E03-S09 `on_design_approved` through the Definition of Ready (§58). When the phase becomes ACTIVE, E06-S07 raises `start_discovery` on its `gdd-planned` features, and `ready_items` never offers a `gdd-planned` FEATURE in IDEA, so the FEATURE/IDEA PLAN decomposition of E03-S09 is not repeated. Nothing of a phase is scheduled before the phase is ACTIVE (E06-S07).

## `NEW NAME:` items introduced by this epic (to be added to WBS.md §6 by E06-X01)

| Item | Story | Why |
|---|---|---|
| `walk.workflow.gdd` (`GddSection`, `GddArea`, `GddDocument`, `GddIndex`, `GlossaryEntry`, `parse_gdd_markdown`, `load_gdd_index`, `area_key`, `slug_anchor`, `parse_gdd_ref`) | S01 | ARCHITECTURE names no GDD parser |
| `MemoryManager.write_project_data/read_project_data`, `PROJECT_DATA_FILES`, `project_data_path` | S01 | `.ai/project/*.yaml` data files need the single `.ai/` writer |
| `walk.orchestrator.gdd_readiness` (`GddFindingKind`, `FindingSeverity`, `GddFinding`, `GddReadiness`, `FINDING_ESCALATION`, `UNBOUNDED_TERMS`, `FINDINGS_BLOCK_LABEL`, `kernel_prechecks`, `parse_findings_block`, `GddReadinessAnalyzer`), `gdd-readiness.yaml`, `WorkItemDraft.labels`, label `analysis-only`, guard `analysis_only_task`, event `analysis_done` + `story_workflow.yaml` row | S02 | §49 list has no model in DOMAIN-MODEL; INTERFACES §3.2 has no completion path for non-code tasks |
| `walk.workflow.traceability` (`GddRequirement`, `RequirementStatus`, `RequirementLinks`, `TraceabilityMatrix`, `REQUIREMENT_ID_PATTERN`, `format_requirement_id`, `normalise_requirements`), id format `REQ-<AREA>-<NNN>`, `walk.orchestrator.traceability_store.TraceabilityStore`, `walk doctor --fix` traceability refresh | S03 | §73 file schema undefined |
| `GddCompiler` methods, `PLAN_BLOCK_LABEL`, `PhasePlanDraft` family, `PlanStatus`, `PhasePlanResult`, `parse_plan_block`, `validate_plan`, `WorkItemDraft.gdd_refs`, labels `gdd-compile`/`gdd:readiness`/`gdd:plan`/`gdd-planned`/`phase:<id>`, command `phase.plan`, idempotency keys `gdd.readiness:*`/`gdd.plan:*`/`gdd.materialise:*` | S02, S04 | INTERFACES names `GddCompiler` without methods |
| `TraceLevel`, `TraceChain`, `TraceQuery`, CLI `walk work trace` | S05 | §73 queries have no interface |
| `walk.workflow.coverage` (`area_of_requirement`, `RequirementCoverage`, `AreaCoverage`, `GddCoverage`, `compute_coverage`, `render_gdd_coverage`), `GddCoverageWriter`, `TraceabilityStore.subscribe`, hook `builtin.gdd_coverage_refresh` | S06 | §74 file format undefined |
| `WorkflowManager.assign_phase_scope`, payload key `scope_epic_id`, `ready_items` phase-state and `gdd-planned` filters, `walk.orchestrator.scope_hooks` (`GDD_PLANNED_LABEL`, `activate_planned_features`, `register_scope_hooks`), hook `builtin.gdd_phase_activate` | S07 | Inv. 7 scope assignment has no method |

---

### E06-X01 — Refine E06 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §135 (Stage 6), §58 (Definition of Ready applied to stories)
**Depends on:** E05-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E06 story's Files table, interface references and dependencies are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E05-R01, the epic's `NEW NAME:` items are registered in `WBS.md` §6, and the corrected epic file is committed before any E06 story starts.

#### Scope
- In: this file (`EPIC-06-gdd-compiler.md`), `WBS.md` §5 rows for E06, `WBS.md` §6 register entries introduced by E06.
- Out: changing story IDs, titles, dependencies or effort (fixed by WBS §4); writing code.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-06-gdd-compiler.md` | modify | — |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status row E06-X01; §6 register additions from the epic header table) |

#### Interface contract
Checklist applied to every story E06-S01…S08 and E06-R01:
1. Every path in the Files table marked `modify` exists in `src/walk/` or `tests/`, or is created by an earlier story of this epic; every path marked `create` does not exist and is not created by an earlier story.
2. Every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference resolves to a section that still defines the named symbol with the signature quoted in the story.
3. Every `Depends on` ID is `DONE` in `WBS.md` §5 (or belongs to E06 and precedes the story).
4. Every symbol the stories call exists under the name used here, otherwise the story is corrected to the real name: `DefaultWorkflowManager.create/create_phase/check_definition_of_ready/ready_items/gdd_coverage/raise_event`, `definition_of_ready_checks`, guard `in_phase_scope` (E01-S10 placeholder), `DefaultMemoryManager.ensure_feature_context` (E04-S01), `write_report`, `DefaultDecisionManager.escalate` (E05-S01), `EscalationRouter` (E05-S02), `DefaultTaskRouter` label-based rows (E07-style; E03-S07), `DefaultOutputApplier`, `DefaultOrchestrator` post-apply callbacks (E03-S09), `LocalWorkProvider.create/link` (E03-S02), `CommandConsumer`/`CommandClient`, `cmd_phase.py` (`phase_app`), `cmd_work.py`, `cmd_doctor.py`, `LedgerManager.query`, `EvidenceManager.for_item`, `tests/e2e/conftest.py::bootstrapped_repo`, `tests/fakes/fake_model_adapter.py::FakeModelAdapter`.
5. Specifically verify (E03-S09…S20 bodies were not written when this file was planned): the module and callback through which E03-S09 runs the FEATURE PLAN flow and how `DefaultOrchestrator` calls a post-apply hook for special tasks (E06-S02/S04 attach `GddCompiler.on_task_completed` there); which ledger kinds/evidence kinds E03-S11/S12 record for builds and tests (E06-S05 levels BUILD/TEST); whether `WorkflowManager.create` accepts `phase_id` for EPIC items and whether an EPIC transition table exists.
6. The epic header `NEW NAME:` table is copied into `WBS.md` §6.

#### Behavior
1. For each checklist failure the planner edits the story in place (path, symbol or reference) and records the change in a `Refinement log` list appended to this story's Evidence section (`<story id>: <old> → <new>`).
2. A story that cannot be made ready without an architecture change is marked `BLOCKED` with a `BLOCKING:` note naming the missing name/decision.
3. Nothing outside `docs/02-work-breakdown/` is modified.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every E06 story When the Files tables are checked Then every `modify` path exists (or is created earlier in E06) and every `create` path is absent | manual checklist recorded in Evidence |
| 2 | Given every E06 story When each `INTERFACES.md`/`DOMAIN-MODEL.md` reference is opened Then the referenced symbol and signature exist | manual checklist recorded in Evidence |
| 3 | Given every E06 story When its `Depends on` list is compared with `WBS.md` §5 Then every dependency outside E06 is `DONE` | manual checklist recorded in Evidence |
| 4 | Given `WBS.md` §6 When compared with the epic header table Then every E06 `NEW NAME:` row is present | manual checklist recorded in Evidence |
| 5 | Given the refined file When `grep -c "^### E06-"` Then 10 headings (X01, S01…S08, R01) and no ID renamed | manual checklist recorded in Evidence |

#### Evidence required
- Refinement log (list of corrections, or "no corrections").
- `git diff --stat` of the commit (only `docs/02-work-breakdown/` files).

#### Notes
- WBS §1 (`Exx-Xyy` refine task), §2 rule 3.
- Commit subject: `docs: refine epic 06 stories (E06-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S01 — GDD ingestion: Markdown parsing to `GddRef` index and areas

**Status:** TODO
**Type:** feat
**Requirements:** §48 (Analyze/Normalize input), §73 (requirement anchor), §74 (areas), §26 (preflight reports GDD), §137 (Inv. 2)
**Depends on:** E06-X01
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The GDD files listed in `Project.gdd_paths` are parsed deterministically into a `GddIndex` of areas, sections addressable by `GddRef(path, anchor)` and a glossary, and the kernel gains the single sanctioned writer/reader for the `.ai/project/` data files the compiler produces.

#### Scope
- In: Markdown structure parser (areas, sections, glossary, anchors, content hashes), multi-file index, `GddRef` parse/resolve, `MemoryManager.write_project_data/read_project_data`, GDD summary line in `walk doctor`, the small fixture GDD used by every E06 test.
- Out: readiness findings (E06-S02); requirement ids and `traceability.yaml` content (E06-S03); GDD formats other than Markdown (not required by §48).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/gdd.py` | create | `GddSection`, `GddArea`, `GlossaryEntry`, `GddDocument`, `GddIndex`, `parse_gdd_markdown`, `load_gdd_index`, `area_key`, `slug_anchor`, `parse_gdd_ref` |
| `src/walk/workflow/__init__.py` | modify | re-exports |
| `src/walk/memory/paths.py` | modify | `PROJECT_DATA_FILES`, `project_data_path` |
| `src/walk/memory/protocols.py` | modify | `MemoryManager.write_project_data`, `MemoryManager.read_project_data` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.write_project_data`, `DefaultMemoryManager.read_project_data` |
| `src/walk/cli/cmd_doctor.py` | modify | — (`gdd:` summary line) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.8 `write_project_data`, `read_project_data`) |
| `tests/fixtures/gdd/small_game.md` | create | — (3 areas × 2 sections + glossary; every section has a `Success:` line and no `UNBOUNDED_TERMS` word so E06-S02 pre-checks find nothing; Economy sections `Shop Prices` / `Price Scaling` contain the deliberate contradiction used by E06-S08) |
| `tests/workflow/test_gdd.py` | create | — |
| `tests/memory/test_project_data.py` | create | — |
| `tests/cli/test_cmd_doctor.py` | modify | — |

#### Interface contract
`GddRef` (DOMAIN-MODEL §4.1), `Project.gdd_paths`, `MemoryManager` (INTERFACES §1.8). Deltas:
```python
# src/walk/workflow/gdd.py
class GddSection(FrozenModel):
    ref: GddRef                      # path relative to repo root, anchor = slug_anchor(title) (deduplicated per file)
    area: str                        # area key
    title: str
    text: str                        # body until the next heading of level <= 3, '\r\n' -> '\n', trailing spaces stripped
    content_sha256: str
    line: int                        # 1-based line of the heading

class GddArea(FrozenModel):
    key: str                         # area_key(title)
    title: str
    sections: tuple[GddSection, ...]

class GlossaryEntry(FrozenModel):
    term: str
    definition: str

class GddDocument(FrozenModel):
    path: str
    title: str                       # first '#' heading or file stem
    areas: tuple[GddArea, ...]
    glossary: tuple[GlossaryEntry, ...]
    source_sha256: str

class GddIndex(FrozenModel):
    documents: tuple[GddDocument, ...]
    areas: tuple[GddArea, ...]       # merged by key across documents, first-appearance order
    glossary: tuple[GlossaryEntry, ...]
    index_sha256: str                # sha256 over the documents' source_sha256 in gdd_paths order
    def section(self, ref: GddRef) -> GddSection: ...          # ConfigError("unknown GDD ref …")
    def sections(self) -> list[GddSection]: ...                 # all, area order then document order

def area_key(title: str) -> str: ...          # "Meta Progression" -> "META_PROGRESSION"; non [A-Z0-9] runs -> "_"
def slug_anchor(title: str) -> str: ...       # GitHub style: lower, drop punctuation except '-', spaces -> '-'
def parse_gdd_ref(text: str) -> GddRef: ...   # "GDD/combat.md#shotgun" -> GddRef(path="GDD/combat.md", anchor="shotgun")
def parse_gdd_markdown(path: str, text: str) -> GddDocument: ...
def load_gdd_index(repo_root: Path, gdd_paths: list[str]) -> GddIndex: ...

# src/walk/memory/paths.py
PROJECT_DATA_FILES: tuple[str, ...] = ("traceability.yaml", "gdd-readiness.yaml", "gdd-coverage.md")
def project_data_path(root: Path, name: str) -> Path: ...     # <root>/project/<name>; ConfigError for other names

# src/walk/memory/protocols.py (MemoryManager additions)
async def write_project_data(self, name: str, text: str, *, actor: Actor, head: Sha, branch: str) -> str: ...
async def read_project_data(self, name: str) -> str | None: ...
```

#### Behavior
1. `parse_gdd_markdown`: headings inside fenced code blocks are ignored; `#` sets the title; each `##` opens an area (`area_key`); each `###` opens a section in the current area; `####` and deeper stay inside the current section's text. A `##` titled `Glossary` (case-insensitive) is not an area: its lines `- **Term**: definition` become `GlossaryEntry`s, other lines are ignored.
2. An area without any `###` gets one synthetic section whose title is the area title, anchor `slug_anchor(area title)` and text the area body. A `###` before any `##` belongs to area `GENERAL`. Text before the first `##` is ignored (document preamble).
3. Duplicate anchors in one file get suffixes `-1`, `-2` in order of appearance (GitHub rule); anchors are unique per file.
4. `content_sha256` is computed over the normalised section text only (title changes do not change it); `source_sha256` over the raw file bytes.
5. `load_gdd_index`: each entry of `gdd_paths` is a file or a directory (directory → all `*.md` sorted by path); paths are resolved relative to `repo_root`, a path escaping the repo or missing → `ConfigError`; files are read as UTF-8; identical area keys from several files merge (sections appended in path order); output is deterministic for equal inputs.
6. `write_project_data(name, text, …)`: `name ∈ PROJECT_DATA_FILES` else `ConfigError`; secret-looking content refused exactly as `write` (ARCHITECTURE §6); atomic temp + rename to `.ai/project/<name>`; ledger `CONTEXT_UPDATED{path, kind: "project_data", sha256}`; no `memory_index` row and no `ON_CONTEXT_UPDATED` (generated data, ADR-0003 D-6 semantics). Returns the repo-relative path.
7. `read_project_data(name)` returns the file text or `None` when absent; unknown name → `ConfigError`.
8. `walk doctor` prints `gdd: <files> files, <areas> areas, <sections> sections` when `gdd_paths` is non-empty, `gdd: none configured` (warning) when empty; a parse/load error is a finding (exit 1 under `--strict`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `small_game.md` When parsed Then areas `[MOVEMENT, COMBAT, ECONOMY]`, two sections each, glossary has `Airtime`, title "Sky Hopper" | `tests/workflow/test_gdd.py::test_parse_fixture_areas_sections_glossary` |
| 2 | Given a `##` heading inside a fenced code block Then it is not an area | `tests/workflow/test_gdd.py::test_headings_in_code_fences_ignored` |
| 3 | Given an area without `###` Then one synthetic section with the area's anchor and body | `tests/workflow/test_gdd.py::test_area_without_sections_gets_synthetic_section` |
| 4 | Given two `### Shotgun` headings in one file Then anchors `shotgun` and `shotgun-1` | `tests/workflow/test_gdd.py::test_duplicate_anchors_suffixed` |
| 5 | Given a section whose title changes but text does not Then `content_sha256` unchanged; text change Then changed | `tests/workflow/test_gdd.py::test_content_hash_tracks_text_only` |
| 6 | Given `area_key("Meta Progression")` and `slug_anchor("Enemy Knockback!")` Then `META_PROGRESSION` and `enemy-knockback` | `tests/workflow/test_gdd.py::test_area_key_and_slug_anchor` |
| 7 | Given two files both with `## Combat` When `load_gdd_index` Then one `COMBAT` area with sections from both in path order; loading twice Then equal `index_sha256` | `tests/workflow/test_gdd.py::test_index_merges_areas_deterministically` |
| 8 | Given `gdd_paths=["../outside.md"]` or a missing file Then `ConfigError` | `tests/workflow/test_gdd.py::test_load_rejects_missing_and_escaping_paths` |
| 9 | Given `parse_gdd_ref("GDD/small_game.md#shotgun")` When `index.section(ref)` Then the Shotgun section; unknown anchor Then `ConfigError` | `tests/workflow/test_gdd.py::test_parse_and_resolve_gdd_ref` |
| 10 | When `write_project_data("traceability.yaml", "a: 1")` Then file at `.ai/project/traceability.yaml`, one `CONTEXT_UPDATED` ledger event with `kind == "project_data"`, no `memory_index` row; `read_project_data` returns the text | `tests/memory/test_project_data.py::test_write_and_read_project_data` |
| 11 | When `write_project_data("notes.yaml", …)` Then `ConfigError`; text containing a secret pattern Then refused and no file | `tests/memory/test_project_data.py::test_project_data_name_and_secret_guard` |
| 12 | Given a repo with `gdd_paths=["GDD/small_game.md"]` When `walk doctor` Then output contains `gdd: 1 files, 3 areas, 6 sections` | `tests/cli/test_cmd_doctor.py::test_doctor_reports_gdd_summary` |

#### Evidence required
- Quality gate output.
- Demo: `walk bootstrap --gdd GDD/small_game.md --name "Sky Hopper" --key SKY --yes` on a temp repo, then `walk doctor` showing the `gdd:` line.

#### Notes
- Epic planning decisions "GDD structure" and "Project data files"; ARCHITECTURE §1.2 places traceability in `walk.workflow` (pure; file reading of the GDD itself is not a `.ai/` write and needs no provider).
- `NEW NAME:` see epic header table rows for S01.
- Pitfall: Windows line endings in fixture files — normalise before hashing so hashes are platform-independent (determinism, CONVENTIONS §3).
- Commit subject: `feat: parse gdd markdown into areas and refs (E06-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S02 — GDD readiness analysis run and findings

**Status:** TODO
**Type:** feat
**Requirements:** §49, §50, §51, §48 (Analyze, Clarify), §58, §137 (Inv. 7), §138 (Under-Specified GDD)
**Depends on:** E06-S01, E05-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Whenever the GDD index changes, the kernel runs a readiness analysis — deterministic pre-checks plus an agent `ANALYSIS` run — that yields findings enumerated by the §49 list, routes each finding by severity to "agent decides" (Level 0) or an escalation (Levels 1–3, §50–§51), and persists the verdict in `.ai/project/gdd-readiness.yaml` with the areas that are blocked from planning.

#### Scope
- In: `GddFindingKind` (§49 list), finding/verdict models, kernel pre-checks, `walk-gdd-findings` block parsing, finding → escalation table, readiness task lifecycle (label-routed `ANALYSIS` run, `analysis_done` completion row), `gdd-readiness.yaml` + `.ai/reports/gdd/readiness.md`, startup trigger, `ANALYSIS.md.j2` readiness block.
- Out: requirement ids (E06-S03); planning and use of `blocked_areas` (E06-S04); escalation routing itself (E05-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/gdd_readiness.py` | create | `GddFindingKind`, `FindingSeverity`, `GddFinding`, `GddReadiness`, `FINDING_ESCALATION`, `UNBOUNDED_TERMS`, `FINDINGS_BLOCK_LABEL`, `kernel_prechecks`, `parse_findings_block`, `GddReadinessAnalyzer` |
| `src/walk/orchestrator/router.py` | modify | — (label rows: `gdd:readiness` → DESIGN_LEADER if enabled else ORCHESTRATOR, purpose `ANALYSIS`) |
| `src/walk/orchestrator/service.py` | modify | — (startup calls `GddReadinessAnalyzer.ensure_current` after recovery) |
| `src/walk/workflow/tables/story_workflow.yaml` | modify | — (row `IMPLEMENTING --analysis_done--> COMPLETE`) |
| `src/walk/workflow/guards.py` | modify | guard `analysis_only_task` |
| `src/walk/workflow/models.py` | modify | `WorkItemDraft.labels` (skip if E03-S09 already added draft labels — E06-X01 verifies) |
| `src/walk/workflow/service.py` | modify | — (`create` copies `draft.labels` to the item) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§3.2 `analysis_done` row; §4.1 `WorkItemDraft.labels`) |
| `src/walk/runtime/output_applier.py` | modify | — (label `analysis-only` + status `COMPLETED` → event `analysis_done` instead of the table-mapped event) |
| `src/walk/agents/templates/ANALYSIS.md.j2` | modify | — (`gdd_readiness` block) |
| `src/walk/cli/composition.py` | modify | — (builds `GddReadinessAnalyzer`; calls `register(run_completion_handler)`) |
| `tests/orchestrator/test_gdd_readiness_models.py` | create | — |
| `tests/orchestrator/test_gdd_readiness_flow.py` | create | — |
| `tests/orchestrator/test_router.py` | modify | — |
| `tests/workflow/test_tables.py` | modify | — |
| `tests/runtime/test_applier_analysis_only.py` | create | — |
| `tests/agents/test_templates_gdd.py` | create | — |

#### Interface contract
`DecisionManager.escalate` (INTERFACES §1.9), `EscalationRequest`/`AutonomyLevel`/`DecisionCategory` (DOMAIN-MODEL §4.8), `WorkflowManager.create/raise_event/query` (INTERFACES §1.3), `MemoryManager.write_project_data/write_report` (E06-S01, INTERFACES §1.8), `Project.autonomy_level_max`. Deltas:
```python
# src/walk/orchestrator/gdd_readiness.py
class GddFindingKind(StrEnum):                       # §49, verbatim order
    AMBIGUITY = "AMBIGUITY"; CONTRADICTION = "CONTRADICTION"; UNDEFINED_TERM = "UNDEFINED_TERM"
    MISSING_SUCCESS_CRITERIA = "MISSING_SUCCESS_CRITERIA"; MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    UNBOUNDED_SCOPE = "UNBOUNDED_SCOPE"; CONFLICTING_SYSTEMS = "CONFLICTING_SYSTEMS"; MISSING_UX = "MISSING_UX"
    MISSING_DESIGN_INTENT = "MISSING_DESIGN_INTENT"

FindingSeverity = Literal["MINOR", "MAJOR", "BLOCKING"]

class GddFinding(WalkModel):
    kind: GddFindingKind
    severity: FindingSeverity
    area: str
    refs: list[GddRef] = Field(min_length=1)
    summary: str
    options: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    source: Literal["KERNEL", "AGENT"]
    level: AutonomyLevel | None = None              # set by the analyzer
    escalation_id: str | None = None

class GddReadiness(WalkModel):
    index_sha256: str
    analysed_at: datetime
    task_id: WorkItemId | None
    findings: list[GddFinding]
    blocked_areas: list[str]                        # areas with a BLOCKING finding
    ready: bool                                     # blocked_areas == []
    def to_yaml(self) -> str: ...                   # schema version 1, keys in field order
    @classmethod
    def from_yaml(cls, text: str) -> "GddReadiness": ...

FINDING_ESCALATION: dict[tuple[GddFindingKind, FindingSeverity], tuple[AutonomyLevel, DecisionCategory]]   # table in Behavior 4
UNBOUNDED_TERMS: tuple[str, ...] = ("unlimited", "infinite", "endless", "any number of", "all possible")
FINDINGS_BLOCK_LABEL = "walk-gdd-findings"

def kernel_prechecks(index: GddIndex) -> list[GddFinding]: ...
def parse_findings_block(result_markdown: str, index: GddIndex) -> list[GddFinding]: ...   # OutputInvalid on bad YAML/refs

class GddReadinessAnalyzer:
    def __init__(self, workflow: WorkflowManager, decisions: DecisionManager, memory: MemoryManager,
                 idempotency: IdempotencyStore, enabled_roles: Callable[[], list[AgentRole]],
                 project: Callable[[], Project], repo_root: Path, clock: Clock) -> None: ...
    async def ensure_current(self) -> Task | None: ...          # creates a readiness task when needed
    async def current(self) -> GddReadiness | None: ...         # parsed gdd-readiness.yaml if index_sha256 matches
    async def on_task_completed(self, task: Task, run: AgentRun, output: AgentOutput) -> GddReadiness | None: ...
    async def on_completion(self, ctx: CompletionContext) -> None: ...   # label dispatch: gdd:readiness -> on_task_completed(ctx.item, ctx.run, ctx.run.output)
    def register(self, handler: RunCompletionHandler) -> None: ...      # registers (TASK, "ANALYSIS", "analysis_done") -> on_completion (E03-S09)
```
Agent block format (inside `AgentOutput.result`):
````text
```walk-gdd-findings
- kind: CONTRADICTION
  severity: MAJOR
  refs: ["GDD/small_game.md#shop-prices", "GDD/small_game.md#price-scaling"]
  summary: Prices are fixed in one section and scale with level in another.
  options: ["Fixed prices", "Level-scaled prices"]
  suggestion: Level-scaled prices
```
````
New table row (`story_workflow.yaml`, applies to STORY and TASK): `IMPLEMENTING | analysis_done | output_status_is_completed, analysis_only_task | COMPLETE | ON_TASK_COMPLETE | KERNEL`.

#### Behavior
1. `ensure_current()`: `index = load_gdd_index(repo_root, project().gdd_paths)` (no paths → `None`); if `current()` matches `index.index_sha256` → `None`; if a non-terminal TASK labelled `gdd:readiness` exists → `None`; else create `Task(title=f"GDD readiness {sha[:8]}", labels=["gdd-compile", "gdd:readiness", "analysis-only"], phase_id=None, contract=StoryContract(goal="Analyse GDD readiness (§49)", acceptance_criteria=["every §49 category considered", "findings reported in a walk-gdd-findings block"], owner_role=DESIGN_LEADER if enabled else ORCHESTRATOR, reviewer_role=LEAD_DEV, required_evidence=[]))`, raise `ready`; idempotency key `gdd.readiness:<sha>:<attempt>`. Called by `DefaultOrchestrator.start` after recovery and by `GddCompiler.plan_phase` (E06-S04).
2. Routing: TASK/READY with label `gdd:readiness` → role per Behavior 1, purpose `ANALYSIS` (label rows take precedence over `contract.owner_role`). `ANALYSIS.md.j2` renders, when `item.labels` contains `gdd:readiness`, every area and section (ref, title, text), the glossary, the nine §49 kinds with one-line definitions, the severity scale, the block format above, and: "decide MINOR matters yourself and record them as `decisions` (Level 0, §50); never invent missing product intent".
3. Applier: for an item labelled `analysis-only`, output `COMPLETED` raises `analysis_done` (guard `analysis_only_task` = label present); `NEEDS_INPUT`/`BLOCKED` keep the table mapping (`block`); `FAILED` → no event.
4. `on_task_completed(task, run, output)` (post-apply through `RunCompletionHandler` (E03-S09) entry `(TASK, "ANALYSIS", "analysis_done")`, items labelled `gdd:readiness` only; other labels are a no-op): `findings = kernel_prechecks(index) + parse_findings_block(output.result, index)` de-duplicated by `(kind, sorted refs)` (agent wins); level/category from `FINDING_ESCALATION`:

| Kind | MINOR | MAJOR | BLOCKING |
|---|---|---|---|
| AMBIGUITY, UNDEFINED_TERM, MISSING_SUCCESS_CRITERIA, MISSING_UX | 0 / DESIGN | 1 / DESIGN | 2 / PRODUCT |
| MISSING_DEPENDENCY | 0 / TECH | 1 / TECH | 2 / PRODUCT |
| CONTRADICTION, CONFLICTING_SYSTEMS | 2 / DESIGN | 2 / PRODUCT | 3 / PRODUCT |
| UNBOUNDED_SCOPE, MISSING_DESIGN_INTENT | 1 / PRODUCT | 2 / PRODUCT | 3 / PRODUCT |

   A level above `project.autonomy_level_max` and below USER becomes USER (Inv. 7). Level 0 → no escalation. Level ≥ 1 → `decisions.escalate(EscalationRequest(to_level, category, question=f"[{kind}] {refs[0]}: {summary}", options, recommendation=suggestion), from_role=run.role, work_item_id=task.id, run_id=run.id)`, `escalation_id` stored on the finding.
5. Verdict `GddReadiness(index_sha256, analysed_at=clock.now(), task_id, findings, blocked_areas=sorted areas with a BLOCKING finding, ready=not blocked_areas)` → `write_project_data("gdd-readiness.yaml", to_yaml())` and `write_report("gdd", "readiness", <markdown table of findings by area>)`.
6. `kernel_prechecks`: empty section text → `MISSING_DESIGN_INTENT` MAJOR; no line starting with `Success:` or `Acceptance:` (case-insensitive) → `MISSING_SUCCESS_CRITERIA` MINOR; `[[Term]]` not in the glossary → `UNDEFINED_TERM` MINOR; any `UNBOUNDED_TERMS` word (whole-word, case-insensitive) → `UNBOUNDED_SCOPE` MINOR. Pure and deterministic (ordered by area, ref, kind).
7. `parse_findings_block`: exactly one fenced block labelled `walk-gdd-findings` (none → `[]`; two → `OutputInvalid`); YAML list validated as `GddFinding` with `source="AGENT"`; every ref must resolve in the index and `area` is derived from the first ref (`OutputInvalid` otherwise).
8. When `parse_findings_block` raises, no readiness file is written, the error is attached to the run as a `Finding(severity="RISK")`, and the next `ensure_current` creates attempt 2; after 2 failed attempts for one `index_sha256` a Level-3 escalation "GDD readiness analysis failed" is raised instead of a third task.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `GddFindingKind` Then exactly the nine §49 kinds in order | `tests/orchestrator/test_gdd_readiness_models.py::test_finding_kinds_match_section_49` |
| 2 | Given the fixture GDD with one empty section, one `[[Stamina]]` reference and the word "unlimited" When `kernel_prechecks` Then `MISSING_DESIGN_INTENT` MAJOR, `UNDEFINED_TERM` MINOR, `UNBOUNDED_SCOPE` MINOR on the right refs | `tests/orchestrator/test_gdd_readiness_models.py::test_kernel_prechecks_detect_structural_gaps` |
| 3 | Given a result with a valid `walk-gdd-findings` block Then parsed findings with `source == "AGENT"` and `area == "ECONOMY"`; a block with an unknown ref Then `OutputInvalid` | `tests/orchestrator/test_gdd_readiness_models.py::test_parse_findings_block_validates_refs` |
| 4 | For every `(kind, severity)` Then `FINDING_ESCALATION` has an entry and CONTRADICTION/MAJOR maps to `(PO, PRODUCT)` | `tests/orchestrator/test_gdd_readiness_models.py::test_escalation_table_complete` |
| 5 | Given `GddReadiness` When `to_yaml` then `from_yaml` Then equal | `tests/orchestrator/test_gdd_readiness_models.py::test_readiness_yaml_round_trip` |
| 6 | Given no readiness file When `ensure_current` Then one READY TASK with labels `gdd-compile, gdd:readiness, analysis-only`, `phase_id None`; calling again Then no second task | `tests/orchestrator/test_gdd_readiness_flow.py::test_ensure_current_creates_one_task` |
| 7 | Given a current readiness file with the same `index_sha256` Then `ensure_current` returns `None`; after the GDD text changes Then a new task | `tests/orchestrator/test_gdd_readiness_flow.py::test_readiness_reanalysed_when_gdd_changes` |
| 8 | Given DESIGN_LEADER disabled When routing the readiness task Then ORCHESTRATOR/`ANALYSIS`; enabled Then DESIGN_LEADER/`ANALYSIS` | `tests/orchestrator/test_router.py::test_gdd_readiness_task_routing` |
| 9 | Given a fake analysis output with one CONTRADICTION MAJOR and one AMBIGUITY MINOR When completed Then one escalation with `to_level == 2`, none for the MINOR finding, `gdd-readiness.yaml` lists both with `level` 2 and 0, `ready == True` | `tests/orchestrator/test_gdd_readiness_flow.py::test_findings_routed_by_level` |
| 10 | Given a BLOCKING MISSING_DESIGN_INTENT in COMBAT Then `blocked_areas == ["COMBAT"]`, `ready == False`, Level-3 escalation | `tests/orchestrator/test_gdd_readiness_flow.py::test_blocking_finding_blocks_area` |
| 11 | Given `autonomy_level_max == 1` and a MAJOR CONTRADICTION Then the escalation `to_level == USER` | `tests/orchestrator/test_gdd_readiness_flow.py::test_project_autonomy_cap_applies` |
| 12 | Given an invalid block twice for one index Then no readiness file and one Level-3 escalation "GDD readiness analysis failed", no third task | `tests/orchestrator/test_gdd_readiness_flow.py::test_invalid_output_retried_then_escalated` |
| 13 | Given an `analysis-only` TASK in IMPLEMENTING and output `COMPLETED` When applied Then event `analysis_done` and state `COMPLETE`; without the label Then `submit_for_review` as before | `tests/runtime/test_applier_analysis_only.py::test_analysis_only_tasks_complete_directly` |
| 14 | When `story_workflow.yaml` loads Then the `analysis_done` row exists with guards `output_status_is_completed, analysis_only_task` and role KERNEL | `tests/workflow/test_tables.py::test_story_table_has_analysis_done_row` |
| 15 | Given a readiness task When `ANALYSIS` renders Then every section ref, the nine kinds and the block label appear; rendered twice byte-identical | `tests/agents/test_templates_gdd.py::test_analysis_template_gdd_readiness_block` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `walk run --once` (creates and starts the readiness task), then after the fake output `cat .ai/project/gdd-readiness.yaml`, `walk ledger query --kind ESCALATION_RAISED --json` (one `to_level == 2`), `cat .ai/reports/gdd/readiness.md`.

#### Notes
- §50 "small detail: agent decides; major product decision: escalate" is the MINOR/MAJOR split of Behavior 4; §58 "BLOCKED rather than inventing" is `blocked_areas`, consumed by E06-S04.
- `NEW NAME:` see epic header (S02 row); plus label `analysis-only`, guard `analysis_only_task`, event `analysis_done` and its `story_workflow.yaml` row (INTERFACES §3.2 has no completion path for non-code tasks; E05-S03 set the precedent of planner-added rows marked `NEW NAME:`). E07 intake/change-analysis tasks can reuse the same label — E07-X01 to decide; because `RunCompletionHandler.register` rejects duplicate `(kind, purpose, event)` keys, a second `ANALYSIS`/`analysis_done` consumer must add a label branch to `on_completion` (or E07-X01 extends the handler to multiple entries).
- Pitfall: the analyzer runs post-apply, after the task is already `COMPLETE`; never raise events on the task from `on_task_completed`.
- Commit subject: `feat: analyse gdd readiness and route findings by autonomy (E06-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S03 — Requirement normalisation and `traceability.yaml`

**Status:** TODO
**Type:** feat
**Requirements:** §48 (Normalize → Product Requirements), §73, §74, §6.2, §137 (Inv. 2)
**Depends on:** E06-S01
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every GDD section becomes a product requirement with a stable id `REQ-<AREA>-<NNN>` that survives re-compiles, renames and edits (changed and removed requirements are marked, never renumbered), persisted as `.ai/project/traceability.yaml` — the root of the §73 chain to which later stories attach specification and work-item links.

#### Scope
- In: `walk.workflow.traceability` models and pure `normalise_requirements`, YAML schema v1, `TraceabilityStore` (load/refresh/save/link through `MemoryManager` project data), `walk doctor --fix` refresh line.
- Out: adding links when work is planned (E06-S04); chain queries to commits/builds/tests/QC (E06-S05); coverage (E06-S06); agent-authored acceptance criteria (they live in story contracts, E06-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/traceability.py` | create | `RequirementStatus`, `RequirementLinks`, `GddRequirement`, `TraceabilityMatrix`, `REQUIREMENT_ID_PATTERN`, `format_requirement_id`, `normalise_requirements` |
| `src/walk/workflow/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/traceability_store.py` | create | `TraceabilityStore` |
| `src/walk/cli/cmd_doctor.py` | modify | — (`--fix` refreshes requirements and prints the `traceability:` line) |
| `src/walk/cli/composition.py` | modify | — (builds `TraceabilityStore`; `KernelHandle.traceability`) |
| `tests/workflow/test_traceability.py` | create | — |
| `tests/orchestrator/test_traceability_store.py` | create | — |
| `tests/cli/test_cmd_doctor.py` | modify | — |

#### Interface contract
`GddRef.requirement_id` (DOMAIN-MODEL §4.1), `GddIndex`/`GddSection` (E06-S01), `MemoryManager.read_project_data/write_project_data` (E06-S01). Deltas:
```python
# src/walk/workflow/traceability.py
REQUIREMENT_ID_PATTERN = r"^REQ-[A-Z0-9_]+-\d{3,}$"
def format_requirement_id(area: str, n: int) -> str: ...      # ("COMBAT", 7) -> "REQ-COMBAT-007"

class RequirementStatus(StrEnum):
    ACTIVE = "ACTIVE"; CHANGED = "CHANGED"; REMOVED = "REMOVED"

class RequirementLinks(WalkModel):
    specs: list[str] = Field(default_factory=list, description="Spec documents: FEAT ids (feature context) and APR ids")
    work_items: list[WorkItemId] = Field(default_factory=list, description="EPIC/FEATURE/STORY/TASK ids, creation order")

class GddRequirement(WalkModel):
    id: str = Field(pattern=REQUIREMENT_ID_PATTERN)
    area: str
    ref: GddRef                                    # ref.requirement_id == id
    title: str
    text_sha256: str
    status: RequirementStatus = RequirementStatus.ACTIVE
    links: RequirementLinks = Field(default_factory=RequirementLinks)

class TraceabilityMatrix(WalkModel):
    version: Literal[1] = 1
    index_sha256: str
    requirements: list[GddRequirement]
    def by_id(self, requirement_id: str) -> GddRequirement: ...          # ConfigError when unknown
    def for_ref(self, ref: GddRef) -> GddRequirement | None: ...         # match on (path, anchor)
    def active(self) -> list[GddRequirement]: ...                        # status != REMOVED
    def with_links(self, requirement_id: str, *, specs: list[str] = (), work_items: list[WorkItemId] = ()) -> "TraceabilityMatrix": ...
    def to_yaml(self) -> str: ...
    @classmethod
    def from_yaml(cls, text: str) -> "TraceabilityMatrix": ...

def normalise_requirements(index: GddIndex, previous: TraceabilityMatrix | None) -> TraceabilityMatrix: ...

# src/walk/orchestrator/traceability_store.py
class TraceabilityStore:
    def __init__(self, memory: MemoryManager, git_head: Callable[[], Awaitable[tuple[Sha, str]]]) -> None: ...
    async def load(self) -> TraceabilityMatrix | None: ...
    async def refresh(self, index: GddIndex, *, actor: Actor) -> TraceabilityMatrix: ...   # normalise + save when changed
    async def link(self, requirement_id: str, *, specs: list[str] = (), work_items: list[WorkItemId] = (), actor: Actor) -> TraceabilityMatrix: ...
```
File `.ai/project/traceability.yaml` (schema v1):
```yaml
version: 1
index_sha256: 3f2a…
requirements:
  - id: REQ-COMBAT-001
    area: COMBAT
    ref: {path: GDD/small_game.md, anchor: shotgun, requirement_id: REQ-COMBAT-001}
    title: Shotgun
    text_sha256: 9c1e…
    status: ACTIVE
    links: {specs: [FEAT-0002], work_items: [EPIC-001, FEAT-0002, STORY-0003]}
```

#### Behavior
1. `normalise_requirements` walks `index.sections()` in order. For each section with key `(path, anchor)`:
   a. previous requirement with the same key → same id; `status = ACTIVE` when `text_sha256` equal, `CHANGED` when different (sha updated); a previously `REMOVED` one becomes `ACTIVE`/`CHANGED` again; links kept;
   b. else a previous requirement of the same area, not matched in this pass, with equal `text_sha256` → same id, `ref` updated (rename/move detection), status `ACTIVE`;
   c. else a new id `format_requirement_id(area, max_number_ever_used_in_area + 1)` (numbers of REMOVED requirements count — ids are never reused).
2. Previous requirements left unmatched become `REMOVED` and keep their links. Output order: index area order, then number. `ref.requirement_id` always equals `id`.
3. The function is pure: equal inputs → equal output (byte-identical `to_yaml`).
4. `to_yaml` emits keys in model field order with block style; `from_yaml` validates against the models (`ConfigError` on schema violations, including duplicate ids).
5. `TraceabilityStore.refresh`: `previous = load()`; `matrix = normalise_requirements(index, previous)`; when `matrix.to_yaml()` differs from the stored text → `write_project_data("traceability.yaml", …, actor, head, branch)` (HEAD/branch of the repo default branch from `git_head`); returns the matrix. No write when unchanged.
6. `TraceabilityStore.link` appends ids not yet present (order kept, no duplicates) and saves; linking a `REMOVED` requirement is allowed (history), an unknown id → `ConfigError`.
7. `walk doctor --fix` with `gdd_paths` set refreshes and prints `traceability: <active> requirements (<new> new, <changed> changed, <removed> removed)`; without `--fix` it prints the stored counts or `traceability: not generated`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the fixture index and no previous matrix When normalised Then six requirements `REQ-MOVEMENT-001/002`, `REQ-COMBAT-001/002`, `REQ-ECONOMY-001/002`, all ACTIVE, refs carrying the ids | `tests/workflow/test_traceability.py::test_first_normalisation_assigns_ids_per_area` |
| 2 | Given a previous matrix and the same index Then identical output and identical YAML | `tests/workflow/test_traceability.py::test_normalisation_idempotent` |
| 3 | Given one section's text edited Then same id, status CHANGED, new `text_sha256`, links kept | `tests/workflow/test_traceability.py::test_edited_section_keeps_id_marked_changed` |
| 4 | Given a section renamed (anchor changed, text equal) Then same id with the new anchor | `tests/workflow/test_traceability.py::test_renamed_section_keeps_id` |
| 5 | Given `REQ-COMBAT-002` removed from the GDD and a new Combat section added Then `REQ-COMBAT-002` REMOVED (links kept) and the new one is `REQ-COMBAT-003` | `tests/workflow/test_traceability.py::test_removed_ids_never_reused` |
| 6 | Given a matrix When `to_yaml` then `from_yaml` Then equal; YAML with duplicate ids Then `ConfigError` | `tests/workflow/test_traceability.py::test_yaml_round_trip_and_validation` |
| 7 | Given no file When `refresh` Then file written once and one `CONTEXT_UPDATED` event; second `refresh` with the same index Then no write | `tests/orchestrator/test_traceability_store.py::test_refresh_writes_only_on_change` |
| 8 | When `link("REQ-COMBAT-001", specs=["FEAT-0002"], work_items=["EPIC-001", "FEAT-0002"])` twice Then each id present once; unknown id Then `ConfigError` | `tests/orchestrator/test_traceability_store.py::test_link_appends_without_duplicates` |
| 9 | Given a bootstrapped fixture repo When `walk doctor --fix` Then output contains `traceability: 6 requirements (6 new, 0 changed, 0 removed)` and the file exists | `tests/cli/test_cmd_doctor.py::test_doctor_fix_refreshes_traceability` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `walk doctor --fix` then `cat .ai/project/traceability.yaml | head -20`; edit one GDD section, `walk doctor --fix` again → `(0 new, 1 changed, 0 removed)`.

#### Notes
- §73 chain level 1 ("GDD Requirement") and level 2 ("Specification": feature context documents / approved artifacts listed under `links.specs`); levels 3–8 are derived (E06-S05).
- `NEW NAME:` see epic header (S03 row) plus `TraceabilityStore` (`walk.orchestrator.traceability_store`) and the `walk doctor --fix` traceability refresh.
- Import rule: `walk.workflow` may not import `walk.memory` (ARCHITECTURE §2.2) — the pure matrix lives in workflow, file I/O in `TraceabilityStore` (orchestrator).
- Commit subject: `feat: normalise gdd requirements into traceability file (E06-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S04 — `GddCompiler`, `Orchestrator.plan_phase`, `walk phase plan`

**Status:** TODO
**Type:** feat
**Requirements:** §48 (Product Requirements → Phase Plan → Executable Work), §52, §57, §58, §66, §67, §73, §55, §137 (Inv. 4, 7)
**Depends on:** E06-S02, E06-S03, E03-S09
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`walk phase plan PHASE-NN` drives the GDD compile for a PLANNED phase: refresh requirements, wait for a current readiness verdict, run one ORCHESTRATOR `PLAN` on a compile task, validate the returned `walk-phase-plan` against the requirements, and materialise epics → features → stories (with Executable Story Contracts and `GddRef`s) in the workflow and the work provider, linking every item back to its requirements in `traceability.yaml`.

#### Scope
- In: `PhasePlanDraft` family, `walk-phase-plan` block parsing and validation, `GddCompiler.plan_phase/on_plan_completed/materialise`, `DefaultOrchestrator.plan_phase`, label routing `gdd:plan` → ORCHESTRATOR/`PLAN`, `PLAN.md.j2` `gdd_plan` block, `WorkItemDraft.gdd_refs`, work-provider creation and PARENT links, traceability links, `walk phase plan` (daemon command `phase.plan` and offline), re-plan with `existing_id`.
- Out: readiness analysis (E06-S02 — consumed through `GddReadinessAnalyzer`); real `in_phase_scope`, `assign_phase_scope` and activation of planned features at phase start (E06-S07); chain queries (E06-S05); coverage (E06-S06); starting the phase (E07-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/gdd_compiler.py` | create | `PLAN_BLOCK_LABEL`, `PlanStoryDraft`, `PlanFeatureDraft`, `PlanEpicDraft`, `PhasePlanDraft`, `PlanStatus`, `PhasePlanResult`, `parse_plan_block`, `validate_plan`, `GddCompiler` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.plan_phase` |
| `src/walk/orchestrator/router.py` | modify | — (label row `gdd:plan` → ORCHESTRATOR, purpose `PLAN`) |
| `src/walk/orchestrator/commands.py` | modify | — (`CommandConsumer` handles `phase.plan`) |
| `src/walk/workflow/models.py` | modify | `WorkItemDraft.gdd_refs` |
| `src/walk/workflow/service.py` | modify | — (`create` copies `draft.gdd_refs` to `Epic/Feature.gdd_refs` and, for STORY/TASK, into `contract.source_requirements` when empty) |
| `src/walk/agents/templates/PLAN.md.j2` | modify | — (`gdd_plan` block when `item.labels` contains `gdd:plan`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§4.1 `WorkItemDraft.gdd_refs`) |
| `src/walk/cli/cmd_phase.py` | modify | `plan` command |
| `src/walk/cli/composition.py` | modify | — (builds `GddCompiler`, registers it on `RunCompletionHandler`; `KernelHandle.gdd_compiler`) |
| `tests/orchestrator/test_gdd_plan_models.py` | create | — |
| `tests/orchestrator/test_gdd_compiler.py` | create | — |
| `tests/orchestrator/test_router.py` | modify | — |
| `tests/workflow/test_service_create.py` | modify | — |
| `tests/agents/test_templates_gdd.py` | modify | — |
| `tests/cli/test_cmd_phase_plan.py` | create | — |

#### Interface contract
`Orchestrator.plan_phase(phase_id) -> list[WorkItem]` (INTERFACES §1.1, unchanged signature), `WorkflowManager.create` (INTERFACES §1.3), `StoryContract` (DOMAIN-MODEL §4.1, §57), `WorkProvider.create/link` (INTERFACES §2.2), `RunCompletionHandler`/`CompletionContext` (E03-S09), `TraceabilityStore` (E06-S03), `GddReadinessAnalyzer.ensure_current/current` (E06-S02), `walk phase plan ID` (INTERFACES §6). Deltas:
```python
# src/walk/workflow/models.py
class WorkItemDraft(WalkModel):                       # DOMAIN-MODEL §4.1 fields +
    gdd_refs: list[GddRef] = Field(default_factory=list, description="Requirement anchors (Stage 6); copied to Epic/Feature.gdd_refs or contract.source_requirements")

# src/walk/orchestrator/gdd_compiler.py
PLAN_BLOCK_LABEL = "walk-phase-plan"

class PlanStoryDraft(WalkModel):
    key: str                                           # unique in the plan, e.g. "S1"
    existing_id: WorkItemId | None = None              # re-plan: keep this item
    title: str
    description: str = ""
    requirements: list[str] = Field(min_length=1)      # REQ ids
    goal: str
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)          # story keys
    required_evidence: list[EvidenceKind] = Field(default_factory=lambda: [EvidenceKind.AUTOMATED_TEST], min_length=1)
    owner_role: AgentRole = AgentRole.SENIOR_DEV
    reviewer_role: AgentRole = AgentRole.LEAD_DEV
    risk: Risk = Risk.MEDIUM
    priority: Priority = Priority.P2
    complexity: Literal["TRIVIAL", "SMALL", "NORMAL", "LARGE", "CORE"] = "NORMAL"

class PlanFeatureDraft(WalkModel):
    key: str; existing_id: WorkItemId | None = None; title: str; description: str = ""
    requirements: list[str] = Field(min_length=1); stories: list[PlanStoryDraft] = Field(min_length=1)

class PlanEpicDraft(WalkModel):
    key: str; existing_id: WorkItemId | None = None; title: str; description: str = ""
    features: list[PlanFeatureDraft] = Field(min_length=1)

class PhasePlanDraft(WalkModel):
    phase_goal: str
    exit_criteria: list[str] = Field(min_length=1)
    epics: list[PlanEpicDraft] = Field(min_length=1)

class PlanStatus(StrEnum):
    READINESS_PENDING = "READINESS_PENDING"; READINESS_BLOCKED = "READINESS_BLOCKED"
    NOTHING_TO_PLAN = "NOTHING_TO_PLAN"; PLANNING = "PLANNING"; PLANNED = "PLANNED"

class PhasePlanResult(WalkModel):
    phase_id: PhaseId
    status: PlanStatus
    task_id: WorkItemId | None = None                  # readiness or plan task
    blocked_areas: list[str] = Field(default_factory=list)
    created: list[WorkItemId] = Field(default_factory=list)
    unreferenced: list[WorkItemId] = Field(default_factory=list)

def parse_plan_block(result_markdown: str) -> PhasePlanDraft: ...      # OutputInvalid: none/two blocks, bad YAML, schema
def validate_plan(plan: PhasePlanDraft, matrix: TraceabilityMatrix, blocked_areas: list[str],
                  existing: dict[WorkItemId, WorkItem]) -> list[str]: ...   # violations, empty = valid

class GddCompiler:
    def __init__(self, workflow: WorkflowManager, phases: PhaseRepository, memory: MemoryManager, traceability: TraceabilityStore,
                 readiness: GddReadinessAnalyzer, integrations: IntegrationManager, decisions: DecisionManager,
                 idempotency: IdempotencyStore, project: Callable[[], Project], repo_root: Path, clock: Clock) -> None: ...
    async def plan_phase(self, phase_id: PhaseId) -> PhasePlanResult: ...
    async def on_plan_completed(self, ctx: CompletionContext) -> None: ...
    async def materialise(self, phase: Phase, plan: PhasePlanDraft, matrix: TraceabilityMatrix, task: Task) -> list[WorkItem]: ...
    def register(self, handler: RunCompletionHandler) -> None: ...     # (TASK, "PLAN", "analysis_done") -> on_plan_completed
```
CLI: `walk phase plan PHASE_ID [--json]` → one line per status: `PHASE-01 READINESS_PENDING (TASK-0001)`, `PHASE-01 READINESS_BLOCKED areas: COMBAT`, `PHASE-01 PLANNING (TASK-0002)`, `PHASE-01 PLANNED: 2 epics, 3 features, 6 stories`; `--json` prints `PhasePlanResult`. Command row `phase.plan` `{"phase_id"}`.

#### Behavior
1. `plan_phase(phase_id)`: unknown phase → `ConfigError` (exit 1); `phase.state != PLANNED` → `GuardRejected("phase not PLANNED")` (exit 2). `index = load_gdd_index(...)`; `matrix = traceability.refresh(index, actor=Actor(KERNEL))`.
2. Readiness: `await readiness.ensure_current()`; `r = await readiness.current()`; `None` → `READINESS_PENDING` with the open readiness task id. `in_scope = [q for q in matrix.active() if q.area not in r.blocked_areas]`; empty and `r.blocked_areas` non-empty → `READINESS_BLOCKED`; empty otherwise → `NOTHING_TO_PLAN`.
3. A non-terminal TASK labelled `gdd:plan` and `phase:<id>` → `PLANNING` with its id. A COMPLETE plan task for the current `matrix.index_sha256` whose materialisation is recorded (idempotency key `gdd.materialise:<task id>`) → `PLANNED` with the phase's existing descendants (no new task).
4. Otherwise create the plan task: `WorkItemDraft(kind=TASK, title=f"GDD plan {phase.id}", labels=["gdd-compile", "gdd:plan", "analysis-only", f"phase:{phase.id}"], contract=StoryContract(goal=f"Decompose the in-scope GDD requirements into the {phase.name} phase plan", acceptance_criteria=["every in-scope requirement covered by at least one story", "plan returned in a walk-phase-plan block"], owner_role=ORCHESTRATOR, reviewer_role=LEAD_DEV, required_evidence=[]))`, `phase_id=None`, raise `ready`; idempotency key `gdd.plan:<phase id>:<index_sha256>` → `PLANNING`.
5. Routing: TASK/READY with label `gdd:plan` → ORCHESTRATOR, purpose `PLAN`. `PLAN.md.j2` `gdd_plan` block renders: phase id/name/ordinal, in-scope requirements (id, area, title, text, status), blocked areas, Level-0 readiness notes, existing scope items (id, kind, title, state) for re-plans, the block format, and the rules of Behavior 7; output `COMPLETED` with exactly one `walk-phase-plan` block, no `new_tasks`.
6. `on_plan_completed(ctx)` (label `gdd:plan` only): `plan = parse_plan_block(ctx.run.output.result)`; `violations = validate_plan(plan, matrix, r.blocked_areas, existing)`; on `OutputInvalid` or violations → the reasons are attached to the run as `Finding(severity="RISK")`, no item is created, and the next `plan_phase` call creates attempt 2 (key suffix `:2`); after 2 failed attempts a Level-2 `PRODUCT` escalation "phase plan invalid: <first violation>" is raised (`DecisionManager.escalate`) instead of a third task. Valid → `materialise`.
7. `validate_plan` violations: duplicate keys; unknown requirement id; requirement `REMOVED` or in a blocked area; an in-scope requirement referenced by no story (§74 completeness); `depends_on` key unknown or cyclic; `owner_role == reviewer_role` (Inv. 4); `existing_id` not a descendant of the phase scope or of the wrong kind.
8. `materialise` (idempotency key `gdd.materialise:<task id>`; each item created through `WorkflowManager.create(..., actor=ORCHESTRATOR, phase_id=phase.id)` then `IntegrationManager.with_idempotency(f"work.create:{id}", …WorkProvider.create…)` + `set_external_ref`, exactly as E03-S09 Behavior 1):
   a. EPIC per epic draft: `labels=["gdd-planned"]`, `gdd_refs` = refs of the union of its features' requirements; state IDEA.
   b. FEATURE per feature draft: parent epic, `labels=["gdd-planned"]`, `gdd_refs` of its requirements; `MemoryManager.ensure_feature_context` (fills `Relevant GDD`); state IDEA; `WorkProvider.link(epic, feature, "PARENT")`.
   c. STORY per story draft: parent feature, `contract = StoryContract(goal, source_requirements=<refs>, acceptance_criteria, constraints, dependencies=<ids of depends_on, resolved after creation in topological order>, required_evidence, owner_role, reviewer_role, risk, priority, complexity)`, state IDEA (E03-S09 `on_design_approved` promotes children to READY through the Definition of Ready, §58); `WorkProvider.link(feature, story, "PARENT")`; each dependency → `link(dep, story, "BLOCKS")`.
   d. Drafts with `existing_id`: title/description/contract updated only while the item is not `COMPLETE`; nothing is created. Scope items not referenced by the plan are listed in `PhasePlanResult.unreferenced` and left untouched (cancelling is USER-only, INTERFACES §3.2).
   e. `phase.scope_epic_ids` = all epic ids of the plan, `phase.goal = plan.phase_goal`, `phase.exit_criteria = plan.exit_criteria` (`PhaseRepository` save; E06-S07 replaces this with `assign_phase_scope`).
   f. `traceability.link(req, specs=[feature ids covering req], work_items=[epic, feature, story ids covering req])` for every requirement used.
9. `DefaultOrchestrator.plan_phase(phase_id)` returns the phase's descendant work items when the result is `PLANNED`, else `[]` (INTERFACES §1.1 signature kept; `walk phase plan` uses `GddCompiler.plan_phase` for the status).
10. `walk phase plan`: daemon running → `CommandClient` `phase.plan`; otherwise in-process (`build_kernel` without the scheduler) — the command never waits for agent runs; the user runs `walk run` (or the daemon ticks) and calls `walk phase plan` again to see `PLANNED`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a valid `walk-phase-plan` block Then parsed `PhasePlanDraft`; no block or two blocks Then `OutputInvalid` | `tests/orchestrator/test_gdd_plan_models.py::test_parse_plan_block` |
| 2 | Given a plan missing `REQ-ECONOMY-002` Then violation "requirement REQ-ECONOMY-002 not covered" | `tests/orchestrator/test_gdd_plan_models.py::test_validate_requires_full_coverage` |
| 3 | Given cyclic `depends_on`, a REMOVED requirement, `owner_role == reviewer_role` Then three violations | `tests/orchestrator/test_gdd_plan_models.py::test_validate_rejects_cycles_removed_and_same_roles` |
| 4 | Given a PLANNED phase and no readiness file When `plan_phase` Then `READINESS_PENDING` with a readiness task id and `traceability.yaml` written | `tests/orchestrator/test_gdd_compiler.py::test_plan_waits_for_readiness` |
| 5 | Given a current readiness with `blocked_areas == ["MOVEMENT", "COMBAT", "ECONOMY"]` Then `READINESS_BLOCKED` | `tests/orchestrator/test_gdd_compiler.py::test_all_areas_blocked` |
| 6 | Given a current readiness When `plan_phase` twice Then one plan TASK with labels `gdd-compile, gdd:plan, analysis-only, phase:PHASE-01`, status `PLANNING` both times | `tests/orchestrator/test_gdd_compiler.py::test_plan_task_created_once` |
| 7 | Given an ACTIVE phase Then `GuardRejected`; unknown phase Then `ConfigError` | `tests/orchestrator/test_gdd_compiler.py::test_plan_requires_planned_phase` |
| 8 | Given the fake ORCHESTRATOR plan (2 epics, 3 features, 6 stories) When completed Then items created in IDEA with `phase_id == PHASE-01`, labels `gdd-planned` on epics/features, every story contract has goal, AC, `source_requirements` with `requirement_id`, `required_evidence`, and `Phase.scope_epic_ids` lists both epics | `tests/orchestrator/test_gdd_compiler.py::test_materialise_creates_hierarchy_with_contracts` |
| 9 | Given materialisation Then `LocalWorkProvider` holds 11 records with PARENT links and one BLOCKS link per dependency | `tests/orchestrator/test_gdd_compiler.py::test_materialise_syncs_work_provider` |
| 10 | Given materialisation Then every in-scope requirement in `traceability.yaml` lists its epic, feature and story ids and the feature id under `specs`; each feature context `Relevant GDD` lists its refs | `tests/orchestrator/test_gdd_compiler.py::test_materialise_links_traceability_and_context` |
| 11 | Given `on_plan_completed` replayed (recovery) Then no duplicate items | `tests/orchestrator/test_gdd_compiler.py::test_materialise_idempotent` |
| 12 | Given two invalid plan outputs Then no items, one Level-2 escalation "phase plan invalid", no third plan task | `tests/orchestrator/test_gdd_compiler.py::test_invalid_plan_retried_then_escalated` |
| 13 | Given a re-plan with `existing_id` for a COMPLETE story and a new story for a new requirement Then the COMPLETE story unchanged, one story created, unreferenced items reported | `tests/orchestrator/test_gdd_compiler.py::test_replan_keeps_existing_and_adds_new` |
| 14 | Given a TASK labelled `gdd:plan` in READY When routed Then ORCHESTRATOR/`PLAN` | `tests/orchestrator/test_router.py::test_gdd_plan_task_routing` |
| 15 | Given `WorkItemDraft(kind=STORY, gdd_refs=[ref], contract=StoryContract(goal="g"))` When `create` Then `contract.source_requirements == [ref]`; for FEATURE Then `feature.gdd_refs == [ref]` | `tests/workflow/test_service_create.py::test_create_copies_gdd_refs` |
| 16 | Given a plan task When `PLAN` renders Then every in-scope requirement id, the block label and the coverage rule appear; a plain FEATURE PLAN render equals the E03 snapshot | `tests/agents/test_templates_gdd.py::test_plan_template_gdd_block_and_snapshot` |
| 17 | Given no daemon When `walk phase plan PHASE-01` on a repo with a current readiness Then exit 0 and `PHASE-01 PLANNING (TASK-0002)`; `--json` Then a `PhasePlanResult` | `tests/cli/test_cmd_phase_plan.py::test_phase_plan_offline_starts_planning` |
| 18 | Given `walk phase plan PHASE-09` Then exit 1; ACTIVE phase Then exit 2 | `tests/cli/test_cmd_phase_plan.py::test_phase_plan_exit_codes` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo with fakes: `walk phase plan PHASE-01` (→ `READINESS_PENDING`), `walk run --once` ×n, `walk phase plan PHASE-01` (→ `PLANNING`), `walk run --once` ×n, `walk phase plan PHASE-01` (→ `PLANNED: 2 epics, 3 features, 6 stories`), `walk work list --phase PHASE-01`.

#### Notes
- §48 pipeline mapping: Analyze/Clarify = E06-S02; Normalize/Product Requirements = E06-S03; Design/Technical Specifications and Acceptance Criteria = story contracts + feature contexts (refined later by the DESIGN runs of E03-S09); Phase Plan/Executable Work = this story.
- Uses E06-S02's `analysis-only` label, `analysis_done` row and `GddReadinessAnalyzer` (WBS §5 does not list E06-S02 as a dependency; WBS §2 rule 1 ID order and §8 sets keep S02 before S04 — E06-X01 confirms; if S02 is not `DONE`, this story is `BLOCKED`).
- `NEW NAME:` see epic header (S04 row): `walk.orchestrator.gdd_compiler` symbols, `WorkItemDraft.gdd_refs`, labels `gdd:plan`, `gdd-planned`, `phase:<id>`, command `phase.plan`, idempotency keys `gdd.plan:*`, `gdd.materialise:*`.
- Pitfall: create stories in topological order of `depends_on` so `contract.dependencies` can hold real ids; resolve keys → ids before the BLOCKS links.
- Commit subject: `feat: compile gdd requirements into a phase plan (E06-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S05 — Traceability chain queries (requirement → … → QC evidence)

**Status:** TODO
**Type:** feat
**Requirements:** §73, §82, §83, §88, §6.6, §137 (Inv. 9)
**Depends on:** E06-S03, E03-S12
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** QC

#### Goal
For any requirement the kernel answers the full §73 chain — GDD requirement → specification → epic/story → implementation → commit → build → test → QC evidence — and for any work item the requirements it serves, using only `traceability.yaml`, work-item records, the execution ledger and evidence records (never agent memory).

#### Scope
- In: `TraceLevel` (8 §73 levels), `TraceNode`, `TraceChain`, `TraceQuery.chain/chains/requirements_for`, first-gap detection, `walk work trace ID [--json]`.
- Out: coverage percentages and `gdd-coverage.md` (E06-S06); report rendering (E09); writing any link (E06-S04 writes requirement → spec/work-item links; levels 4–8 are derived, not stored).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/trace_query.py` | create | `TraceLevel`, `TraceNode`, `TraceChain`, `TraceQuery` |
| `src/walk/workflow/__init__.py` | modify | re-exports |
| `src/walk/cli/cmd_work.py` | modify | `trace` command |
| `src/walk/cli/composition.py` | modify | — (`KernelHandle.trace_query`) |
| `tests/workflow/test_trace_query.py` | create | — |
| `tests/cli/test_cmd_work_trace.py` | create | — |

#### Interface contract
`TraceabilityMatrix` (E06-S03), `LedgerManager.query` (INTERFACES §1.14), `EvidenceManager.for_item` (INTERFACES §1.14), `WorkflowManager.get/query` (INTERFACES §1.3); ledger kinds `AGENT_RUN_ENDED`, `COMMIT`, `BUILD_RESULT`, `TEST_RESULT`, `QC_RESULT` (ARCHITECTURE §4.3; payloads per E03-S11/S12/S14). Deltas:
```python
# src/walk/workflow/trace_query.py
class TraceLevel(StrEnum):                    # §73 order
    REQUIREMENT = "REQUIREMENT"; SPECIFICATION = "SPECIFICATION"; WORK_ITEM = "WORK_ITEM"; IMPLEMENTATION = "IMPLEMENTATION"
    COMMIT = "COMMIT"; BUILD = "BUILD"; TEST = "TEST"; QC_EVIDENCE = "QC_EVIDENCE"

class TraceNode(FrozenModel):
    level: TraceLevel
    ref: str                                  # REQ id | FEAT/APR id | work item id | RUN id | sha | evidence id / ledger event id
    label: str                                # human summary, e.g. "STORY-0003 Shotgun spread (COMPLETE)"
    work_item_id: WorkItemId | None = None
    at: datetime | None = None

class TraceChain(FrozenModel):
    requirement_id: str
    status: RequirementStatus
    nodes: dict[TraceLevel, list[TraceNode]]  # every level present as a key (possibly empty)
    first_gap: TraceLevel | None              # first level with no node, None when complete

class TraceQuery:
    def __init__(self, workflow: WorkflowManager, ledger: LedgerManager, evidence: EvidenceManager) -> None: ...
    async def chain(self, matrix: TraceabilityMatrix, requirement_id: str) -> TraceChain: ...
    async def chains(self, matrix: TraceabilityMatrix) -> list[TraceChain]: ...           # matrix order
    async def requirements_for(self, matrix: TraceabilityMatrix, work_item_id: WorkItemId) -> list[str]: ...
```
CLI: `walk work trace REQ-COMBAT-001|STORY-0003 [--json]` — for a requirement prints the eight levels with their nodes and `gap: <level>|none`; for a work item prints its requirement ids followed by each chain.

#### Behavior
1. REQUIREMENT: one node (the requirement, label `<id> <title> (<status>)`).
2. SPECIFICATION: `links.specs` ids (feature context documents `.ai/features/<FEAT>.md` and approved artifacts), label from the item/artifact title.
3. WORK_ITEM: `links.work_items` ∪ items whose `gdd_refs` or `contract.source_requirements` carry this `requirement_id` ∪ STORY/TASK/BUG descendants of linked features (bugs via `related_feature_id`); de-duplicated, ordered by id; label includes the current state.
4. IMPLEMENTATION: `AGENT_RUN_ENDED` ledger events for WORK_ITEM ids whose payload `purpose == "IMPLEMENT"` and outcome `COMPLETED` (ref = run id).
5. COMMIT: `COMMIT` events for those work items (ref = sha, both WIP-squashed and kernel commits; de-duplicated by sha).
6. BUILD: `BUILD_RESULT` events with `ok == True` for those work items (ref = `evidence_id` from the payload, else the event id).
7. TEST: `TEST_RESULT` events with `ok == True` plus `AUTOMATED_TEST` evidence of those items (de-duplicated by evidence id).
8. QC_EVIDENCE: `QC_REPORT` and `REPRODUCTION_PROOF` evidence of those items and `QC_RESULT` events with outcome `APPROVED`.
9. Nodes inside each level are ordered by `at` then `ref`; `first_gap` is the first level (in `TraceLevel` order) with no node; later levels are still filled (a gap does not stop the query).
10. `requirements_for(item)`: requirement ids from the item's own refs, else from the nearest ancestor with refs (story → feature → epic), else from any matrix requirement whose `links.work_items` contains the item; sorted, unique.
11. All reads are read-only queries; no ledger events, no file writes (Inv. 9 — history is answered from the ledger). An unknown requirement id → `ConfigError` (CLI exit 1).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a requirement linked to seeded FEATURE/STORY items with no runs When `chain` Then REQUIREMENT, SPECIFICATION and WORK_ITEM filled and `first_gap == IMPLEMENTATION` | `tests/workflow/test_trace_query.py::test_planned_requirement_gap_at_implementation` |
| 2 | Given seeded ledger/evidence for one story (IMPLEMENT run ended COMPLETED, COMMIT, BUILD_RESULT ok, TEST_RESULT ok + AUTOMATED_TEST, QC_REPORT + QC_RESULT APPROVED) Then all eight levels non-empty and `first_gap is None` | `tests/workflow/test_trace_query.py::test_complete_chain_all_levels` |
| 3 | Given a failed build (`ok False`) and a later green build Then BUILD contains only the green one | `tests/workflow/test_trace_query.py::test_only_successful_build_and_test_counted` |
| 4 | Given a BUG with `related_feature_id` = a linked feature Then the bug appears under WORK_ITEM and its QC evidence under QC_EVIDENCE | `tests/workflow/test_trace_query.py::test_bugs_of_linked_features_included` |
| 5 | Given a commit missing but a later level present Then `first_gap == COMMIT` and BUILD still filled | `tests/workflow/test_trace_query.py::test_gap_does_not_stop_later_levels` |
| 6 | Given a story without own refs under a feature with refs Then `requirements_for(story)` equals the feature's requirement ids | `tests/workflow/test_trace_query.py::test_requirements_for_inherits_from_ancestors` |
| 7 | Given a REMOVED requirement with links Then its chain is still returned with `status == REMOVED` | `tests/workflow/test_trace_query.py::test_removed_requirement_chain_kept` |
| 8 | Given a ledger row count before and after `chains` Then equal | `tests/workflow/test_trace_query.py::test_trace_queries_are_read_only` |
| 9 | Given a fixture repo whose `traceability.yaml` links `REQ-COMBAT-001` to seeded FEAT-0002/STORY-0003 (no S04 needed) When `walk work trace REQ-COMBAT-001` Then exit 0 and output lists eight level headings and `gap: IMPLEMENTATION`; `walk work trace STORY-0003 --json` lists `REQ-COMBAT-001` | `tests/cli/test_cmd_work_trace.py::test_work_trace_requirement_and_item` |
| 10 | Given `walk work trace REQ-NOPE-001` Then exit 1 | `tests/cli/test_cmd_work_trace.py::test_work_trace_unknown_requirement_exit_1` |

#### Evidence required
- Quality gate output.
- Demo on the E03 gate fixture DB with a seeded `traceability.yaml` linking `REQ-MOVEMENT-001` to the E03 feature and stories: `walk work trace REQ-MOVEMENT-001` (all eight levels) and `walk work trace STORY-0001 --json`.

#### Notes
- §73 chain levels map 1:1 to `TraceLevel`; ARCHITECTURE §4.3 write points are the only sources for levels 4–8 so the chain is reproducible from SQLite alone (§88).
- `NEW NAME:` `walk.workflow.trace_query` (`TraceLevel`, `TraceNode`, `TraceChain`, `TraceQuery`), CLI `walk work trace` (INTERFACES §6 has no traceability command).
- E06-X01 verifies the payload keys used here (`purpose` and outcome on `AGENT_RUN_ENDED`, `ok`/`evidence_id` on `BUILD_RESULT`/`TEST_RESULT`, outcome on `QC_RESULT`) against E01-S27, E03-S11, E03-S14 as implemented.
- Commit subject: `feat: query gdd traceability chains from ledger and evidence (E06-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S06 — GDD coverage computation and `gdd-coverage.md`

**Status:** TODO
**Type:** feat
**Requirements:** §74, §73, §87 (dashboard), §69 (evidence package GDD coverage), §83, §137 (Inv. 9)
**Depends on:** E06-S05
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** QC

#### Goal
GDD implementation coverage per area and per requirement is derived from traceability and work-item states (never entered by hand), exposed through `WorkflowManager.gdd_coverage` and `KernelStatus.gdd_coverage`, and kept current in `.ai/project/gdd-coverage.md`.

#### Scope
- In: pure coverage computation, `DefaultWorkflowManager.gdd_coverage` real implementation, Markdown rendering, `GddCoverageWriter`, refresh triggers (traceability save, `ON_TASK_COMPLETE`), `KernelStatus.gdd_coverage`.
- Out: phase evidence package use of coverage (E07-S03 consumes `gdd_coverage`); report CLI (`walk report`, E09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/coverage.py` | create | `area_of_requirement`, `RequirementCoverage`, `AreaCoverage`, `GddCoverage`, `compute_coverage`, `render_gdd_coverage` |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.gdd_coverage` |
| `src/walk/workflow/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/traceability_store.py` | modify | `TraceabilityStore.subscribe` |
| `src/walk/orchestrator/coverage_writer.py` | create | `GddCoverageWriter` |
| `src/walk/orchestrator/service.py` | modify | — (`DefaultOrchestrator.status().gdd_coverage` from `WorkflowManager.gdd_coverage`) |
| `src/walk/cli/composition.py` | modify | — (builds `GddCoverageWriter`, subscribes it, registers hook `builtin.gdd_coverage_refresh` on `ON_TASK_COMPLETE`) |
| `tests/workflow/test_coverage.py` | create | — |
| `tests/workflow/test_service_gdd_coverage.py` | create | — |
| `tests/orchestrator/test_coverage_writer.py` | create | — |

#### Interface contract
`WorkflowManager.gdd_coverage(project_key) -> dict[str, float]` ("COMPLETE stories with gdd_refs / all stories with gdd_refs, per GDD area", INTERFACES §1.3), `KernelStatus.gdd_coverage` (INTERFACES §1.1), `MemoryManager.write_project_data` (E06-S01). Deltas:
```python
# src/walk/workflow/coverage.py
def area_of_requirement(requirement_id: str) -> str: ...      # "REQ-META_PROGRESSION-004" -> "META_PROGRESSION"

class RequirementCoverage(FrozenModel):
    requirement_id: str; area: str; title: str
    stories: int; complete: int
    ratio: float                                                  # complete / stories, 0.0 when stories == 0

class AreaCoverage(FrozenModel):
    area: str; requirements: int; planned_requirements: int
    stories: int; complete: int
    ratio: float                                                  # complete / stories, 0.0 when stories == 0

class GddCoverage(FrozenModel):
    index_sha256: str
    areas: list[AreaCoverage]                                     # matrix area order
    requirements: list[RequirementCoverage]
    def as_dict(self) -> dict[str, float]: ...                    # {area: ratio}

def compute_coverage(matrix: TraceabilityMatrix, items: list[WorkItem]) -> GddCoverage: ...
def render_gdd_coverage(coverage: GddCoverage, *, generated_at: datetime) -> str: ...

# src/walk/orchestrator/traceability_store.py
class TraceabilityStore:
    def subscribe(self, callback: Callable[[TraceabilityMatrix], Awaitable[None]]) -> None: ...   # called after every save

# src/walk/orchestrator/coverage_writer.py
class GddCoverageWriter:
    def __init__(self, workflow: WorkflowManager, traceability: TraceabilityStore, memory: MemoryManager,
                 git_head: Callable[[], Awaitable[tuple[Sha, str]]], clock: Clock) -> None: ...
    async def refresh(self, matrix: TraceabilityMatrix | None = None) -> GddCoverage | None: ...   # None when no matrix
```
`gdd-coverage.md`: front matter `{id: GDD-COVERAGE, type: report, title: GDD coverage, generated_at, index_sha256}`, then `## Summary` (table `Area | Coverage | Complete | Stories | Requirements planned`), `## Requirements` (table `Requirement | Area | Title | Coverage | Complete | Stories`), `## Not Planned` (bullets of requirement ids with zero stories, or `- none`). Coverage printed as whole percent (`75%`, §74 example).

#### Behavior
1. Counted items: STORY and TASK items not `CANCELLED`. An item counts for every requirement id in `contract.source_requirements[].requirement_id`; items without any requirement id are ignored (BUGs are never counted; their completion is part of their story's QC).
2. `RequirementCoverage.ratio = complete / stories` (`complete` = items in `COMPLETE`); `AreaCoverage` aggregates distinct items over the area's non-REMOVED requirements (an item counted once per area even if it serves two requirements of the area); areas with no stories → `ratio 0.0` and `planned_requirements = 0`.
3. `DefaultWorkflowManager.gdd_coverage(project_key)` implements the INTERFACES docstring without the matrix: groups counted items by `area_of_requirement` of their refs; areas without stories are absent from the dict (the matrix-aware view is `GddCoverage`).
4. `compute_coverage` is pure and deterministic; `render_gdd_coverage` is byte-identical for equal inputs.
5. `GddCoverageWriter.refresh`: loads the matrix (or uses the given one) and all project STORY/TASK items, computes, renders with `clock.now()` and writes `write_project_data("gdd-coverage.md", …)` only when the rendered body (excluding `generated_at`) differs from the stored file.
6. Triggers: `TraceabilityStore` calls subscribers after every save (so planning via E06-S04 `link` refreshes coverage); hook `builtin.gdd_coverage_refresh` (default attachment, `required=False`, `log_and_continue`, priority 60) on `ON_TASK_COMPLETE` refreshes when the completed item has requirement refs.
7. `KernelStatus.gdd_coverage = workflow.gdd_coverage(project_key)` (§87); `walk status --json` therefore shows it.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `area_of_requirement("REQ-META_PROGRESSION-004")` Then `META_PROGRESSION`; malformed id Then `ConfigError` | `tests/workflow/test_coverage.py::test_area_of_requirement` |
| 2 | Given 4 Combat stories (3 COMPLETE, 1 QC), 4 Progression (3 COMPLETE), 5 Economy (2 COMPLETE), Meta requirements without stories When `compute_coverage` Then ratios `COMBAT 0.75`, `PROGRESSION 0.75`, `ECONOMY 0.4`, `META 0.0` | `tests/workflow/test_coverage.py::test_area_ratios_from_story_states` |
| 3 | Given a story serving two requirements of one area Then the area counts it once and each requirement counts it | `tests/workflow/test_coverage.py::test_story_counted_once_per_area` |
| 4 | Given a CANCELLED story and a BUG with refs Then neither is counted | `tests/workflow/test_coverage.py::test_cancelled_and_bugs_excluded` |
| 5 | Given a coverage When rendered twice with the same clock Then byte-identical with the three sections in order and `75%` formatting | `tests/workflow/test_coverage.py::test_render_deterministic_sections` |
| 6 | Given persisted stories with refs When `gdd_coverage("SKY")` Then dict per area matching INTERFACES semantics; area without stories absent | `tests/workflow/test_service_gdd_coverage.py::test_gdd_coverage_from_work_items` |
| 7 | Given a matrix and items When `refresh` Then `.ai/project/gdd-coverage.md` written; second refresh without changes Then no write | `tests/orchestrator/test_coverage_writer.py::test_refresh_writes_only_on_change` |
| 8 | Given a subscribed writer When `TraceabilityStore.link` saves Then coverage file refreshed once | `tests/orchestrator/test_coverage_writer.py::test_traceability_save_triggers_refresh` |
| 9 | Given a story with refs reaching COMPLETE When `ON_TASK_COMPLETE` fires Then the file shows the new ratio; hook failure does not fail the transition | `tests/orchestrator/test_coverage_writer.py::test_task_complete_hook_refreshes_coverage` |
| 10 | Given seeded stories When `DefaultOrchestrator.status()` Then `gdd_coverage` equals `workflow.gdd_coverage` | `tests/orchestrator/test_coverage_writer.py::test_kernel_status_exposes_coverage` |

#### Evidence required
- Quality gate output.
- Demo on a fixture repo with seeded traceability and stories: `walk doctor --fix`, `cat .ai/project/gdd-coverage.md`, `walk status --json` (shows `gdd_coverage`).

#### Notes
- §74 "Coverage SHOULD derive from traceability rather than manually entered percentage" — there is no input path for a percentage; every number is recomputed from item states.
- `NEW NAME:` `walk.workflow.coverage` symbols, `GddCoverageWriter` (`walk.orchestrator.coverage_writer`), `TraceabilityStore.subscribe`, hook id `builtin.gdd_coverage_refresh`, `gdd-coverage.md` layout (ARCHITECTURE §8 names the file only).
- Commit subject: `feat: derive gdd coverage from traceability and story states (E06-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S07 — Phase scope guard and scope assignment

**Status:** TODO
**Type:** feat
**Requirements:** §67 (all activity within approved phase scope), §66, §68, §137 (Inv. 7)
**Depends on:** E06-S04
**Effort:** LOW   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Phase scope is enforced mechanically: work items are assigned to a phase through its scope epics, the `in_phase_scope` guard rejects any item outside the active phase's scope, nothing of a phase is scheduled before the phase is ACTIVE (or REWORK), and the GDD-planned features of a phase enter DISCOVERY automatically when the phase starts.

#### Scope
- In: real `in_phase_scope` guard (replaces the E01-S10 placeholder), payload key `scope_epic_id`, `DefaultWorkflowManager.assign_phase_scope`, phase inheritance on create, `ready_items` phase-state and `gdd-planned` filters, hook `builtin.gdd_phase_activate` (`ON_PHASE_START`), `GddCompiler.materialise` switched to `assign_phase_scope`.
- Out: scheduler admission rules per phase state (E07-S04 refines `tick`); phase start itself and baseline (E07-S02); scope checks on rework drafts (E07-S06).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/guards.py` | modify | `in_phase_scope` (real implementation) |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.assign_phase_scope`, `ready_items` (filters), `create` (phase inheritance), `raise_event` (adds `scope_epic_id` payload when the transition uses `in_phase_scope`) |
| `src/walk/workflow/protocols.py` | modify | `WorkflowManager.assign_phase_scope` |
| `src/walk/orchestrator/gdd_compiler.py` | modify | — (`materialise` step e calls `assign_phase_scope`) |
| `src/walk/orchestrator/scope_hooks.py` | create | `GDD_PLANNED_LABEL`, `activate_planned_features`, `register_scope_hooks` |
| `src/walk/cli/composition.py` | modify | — (calls `register_scope_hooks`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.3 `assign_phase_scope`; WBS §3.4 payload key `scope_epic_id` noted) |
| `tests/workflow/test_guards_scope.py` | create | — |
| `tests/workflow/test_service_scope.py` | create | — |
| `tests/orchestrator/test_scope_hooks.py` | create | — |

#### Interface contract
Guard protocol and `TransitionContext.phase` (INTERFACES §1.3), payload key `phase_state` (WBS §3.4), `Phase.scope_epic_ids` (DOMAIN-MODEL §4.1), feature row `IDEA --start_discovery [in_phase_scope]--> DISCOVERY` (INTERFACES §3.1). Deltas:
```python
# src/walk/workflow/protocols.py (WorkflowManager addition)
async def assign_phase_scope(self, phase_id: PhaseId, epic_ids: list[EpicId]) -> Phase:
    """Phase must be PLANNED. scope_epic_ids |= epic_ids; every descendant of those epics with phase_id None
    gets phase_id = phase_id. An epic in another phase's scope -> ConfigError. No ledger event (no state change)."""

# src/walk/orchestrator/scope_hooks.py
GDD_PLANNED_LABEL = "gdd-planned"
async def activate_planned_features(workflow: WorkflowManager, phase: Phase) -> list[WorkItemId]: ...
def register_scope_hooks(hooks: HookManager, workflow: WorkflowManager, phases: PhaseRepository) -> None:
    """builtin.gdd_phase_activate on ON_PHASE_START (required=False, log_and_continue, priority 40)."""
```
Payload key `scope_epic_id: EpicId | None` (top-most EPIC ancestor of the item, written by `raise_event`).

#### Behavior
1. `in_phase_scope(item, ctx)`: ok when `item.phase_id is None`. Otherwise not ok with a reason when: `ctx.phase is None` ("no current phase"); `item.phase_id != ctx.phase.id` ("item belongs to <phase>"); `ctx.payload["phase_state"]` (or `ctx.phase.state`) not in `{ACTIVE, REWORK}` ("phase <id> is <state>"); `ctx.payload["scope_epic_id"]` is None or not in `ctx.phase.scope_epic_ids` ("outside phase scope"). Pure.
2. `raise_event` computes `scope_epic_id` (walk `parent_id` up to the top EPIC; an EPIC is its own scope epic) and adds it to the payload only for transitions whose guards include `in_phase_scope`; caller-supplied values are overwritten.
3. `assign_phase_scope`: allowed only in `PLANNED` (`GuardRejected` otherwise); idempotent; updates `phases.json` and the descendants' `phase_id` in one `UnitOfWork`; never changes an item already assigned to another phase (`ConfigError`).
4. `create(draft, phase_id=None)` with `draft.parent_id` set → the item inherits the parent's `phase_id`; an explicit `phase_id` different from the parent's → `ConfigError` (Inv. 7: children cannot escape their parent's phase).
5. `ready_items(phase_id)`: additionally excludes items whose `phase_id` refers to a phase not in `{ACTIVE, REWORK}`, and FEATURE items in `IDEA` carrying `GDD_PLANNED_LABEL` (their decomposition already exists; E03-S09 PLAN must not run). Phase-less items (`phase_id None`, e.g. GDD compile tasks) are unaffected.
6. `builtin.gdd_phase_activate` on `ON_PHASE_START`: for each FEATURE of the phase in `IDEA` with `GDD_PLANNED_LABEL` (ordered by id) → `raise_event(id, "start_discovery", TransitionContext(actor_role=ORCHESTRATOR, source=KERNEL, run_id=None, payload={"phase_state": "ACTIVE"}, phase=phase))`; a `GuardRejected` is logged with structured `extra` and the loop continues; idempotent (only IDEA features).
7. `GddCompiler.materialise` (E06-S04 step e) now calls `assign_phase_scope(phase.id, epic_ids)` instead of saving `scope_epic_ids` directly; goal and exit criteria are still saved through `PhaseRepository`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given ACTIVE PHASE-01 with scope `[EPIC-001]` and a feature under EPIC-001 Then `in_phase_scope` ok; under EPIC-002 Then not ok "outside phase scope" | `tests/workflow/test_guards_scope.py::test_scope_epic_membership` |
| 2 | Given PHASE-01 `PLANNED` Then not ok "phase PHASE-01 is PLANNED"; item of PHASE-02 Then "item belongs to PHASE-02"; `item.phase_id None` Then ok | `tests/workflow/test_guards_scope.py::test_phase_state_and_membership_reasons` |
| 3 | Given a STORY two levels below EPIC-001 When `raise_event` on a transition guarded by `in_phase_scope` Then payload `scope_epic_id == "EPIC-001"` even if the caller passed another value | `tests/workflow/test_service_scope.py::test_raise_event_supplies_scope_epic_id` |
| 4 | Given PLANNED PHASE-01 and EPIC-001 with 1 feature and 2 stories (phase None) When `assign_phase_scope` Then scope `[EPIC-001]` and all four items have `phase_id PHASE-01`; repeated Then unchanged | `tests/workflow/test_service_scope.py::test_assign_phase_scope_propagates` |
| 5 | Given EPIC-001 already in PHASE-02 scope Then `ConfigError`; PHASE-01 ACTIVE Then `GuardRejected` | `tests/workflow/test_service_scope.py::test_assign_phase_scope_rejections` |
| 6 | Given a parent feature in PHASE-01 When creating a child story without `phase_id` Then child `phase_id PHASE-01`; with `phase_id PHASE-02` Then `ConfigError` | `tests/workflow/test_service_scope.py::test_children_inherit_parent_phase` |
| 7 | Given READY stories of PLANNED PHASE-01, one phase-less READY task and a `gdd-planned` FEATURE in IDEA of an ACTIVE phase When `ready_items(None)` Then only the task | `tests/workflow/test_service_scope.py::test_ready_items_excludes_inactive_phases_and_planned_features` |
| 8 | Given PHASE-01 with two `gdd-planned` IDEA features When `phase_event(start)` fires `ON_PHASE_START` Then both features in DISCOVERY; firing again Then no further transitions | `tests/orchestrator/test_scope_hooks.py::test_phase_start_activates_planned_features` |
| 9 | Given a planned feature outside the phase scope Then it stays IDEA and the hook logs the rejection without failing `phase_event` | `tests/orchestrator/test_scope_hooks.py::test_activation_skips_out_of_scope` |

#### Evidence required
- Quality gate output.
- Demo on the E06-S04 fixture repo: `walk work list --phase PHASE-01 --json` (all items carry `phase_id`), `walk work transition FEAT-0001 start_discovery` before start → exit 2 with "phase PHASE-01 is PLANNED"; `walk phase start PHASE-01` → `walk work list --phase PHASE-01 --kind FEATURE` shows DISCOVERY.

#### Notes
- ARCHITECTURE §7 Inv. 7 ("work items outside `Phase.scope` cannot leave `IDEA` while the phase is `ACTIVE`"); E01-S10 Out-of-scope note names this story for the real guard.
- `NEW NAME:` `WorkflowManager.assign_phase_scope`, payload key `scope_epic_id` (WBS §3.4 table addition), `walk.orchestrator.scope_hooks` (`GDD_PLANNED_LABEL`, `activate_planned_features`, `register_scope_hooks`), hook id `builtin.gdd_phase_activate`.
- E07-S02 also attaches builtins to `ON_PHASE_START` (baseline, budget); this hook's priority 40 runs after them (they are priority 10/20) so the baseline captures the pre-activation scope.
- Commit subject: `feat: enforce phase scope guard and assign planned scope (E06-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-S08 — Epic gate: GDD → one planned phase (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §48, §49, §50, §51, §52, §57, §58, §67, §73, §74, §136 ("GDD analyzed · Phase planned"), §137 (Inv. 7), §138 (Under-Specified GDD)
**Depends on:** E06-S02, E06-S06, E06-S07
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
A small three-area GDD is compiled end-to-end by fake agents into one planned phase — readiness analysed with one deliberate contradiction escalated at Level 2, requirements normalised, 2 epics / 3 features / 6 stories with Executable Story Contracts created in the workflow and `LocalWorkProvider`, every story traced to a requirement, coverage 0 % per area — and the resulting repository is the starting fixture of the E07 gate.

#### Scope
- In: `tests/e2e/test_e06_gate.py`, fixture `e06_scenario` (exported for E07-S10) in `tests/e2e/conftest.py`.
- Out: production code (defects become `E06-Bxx` bugfix stories); executing the phase (E07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e06_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e06_scenario` fixture, `E06Scenario` |
| `tests/fixtures/gdd/small_game.md` | modify | — (only if a kernel pre-check of E06-S02 fires on it; the gate requires zero kernel findings) |

#### Interface contract
Fixture `e06_scenario(bootstrapped_repo) -> E06Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `project_key: ProjectKey`, `repo_path: Path`, `phase_ids: list[PhaseId]` (`PHASE-01` Prototype, `PHASE-02` Vertical Slice, created with `create_phase`), `epic_ids`, `feature_ids`, `story_ids`, `escalation_id: str`. Project: `gdd_paths=["GDD/small_game.md"]` (copied from `tests/fixtures/gdd/small_game.md`), PRODUCT_OWNER and DESIGN_LEADER disabled, `autonomy_level_max=2`. Adapters: `FakeModelAdapter` `fake-claude/sim` for ORCHESTRATOR, `LocalWorkProvider`, real temp git repo, `FakeClock`, `SequentialIdFactory`. Scripts:

| Run (role / purpose / item) | Scripted output |
|---|---|
| ORCHESTRATOR / ANALYSIS / TASK `gdd:readiness` | `COMPLETED`; `walk-gdd-findings` block with one finding: `CONTRADICTION`, `MAJOR`, refs `GDD/small_game.md#shop-prices`, `GDD/small_game.md#price-scaling`, options `["Fixed prices", "Level-scaled prices"]`; no `decisions`, no `escalations` |
| ORCHESTRATOR / PLAN / TASK `gdd:plan` | `COMPLETED`; `walk-phase-plan` block: epic "Core Gameplay" → features "Movement" (`REQ-MOVEMENT-001/002`, 2 stories) and "Combat" (`REQ-COMBAT-001/002`, 2 stories); epic "Economy" → feature "Shop" (`REQ-ECONOMY-001/002`, 2 stories, the second `depends_on` the first); every story with goal, ≥ 2 acceptance criteria, `required_evidence [AUTOMATED_TEST]` |

#### Behavior
Scenario steps (each a test, executed in order via the fixture's cached state; ticks via `walk run --once`, at most 20):
1. `walk phase plan PHASE-01` → `PHASE-01 READINESS_PENDING (TASK-0001)`; `.ai/project/traceability.yaml` exists with six ACTIVE requirements.
2. Ticks run the readiness task to `COMPLETE`; `.ai/project/gdd-readiness.yaml` has `ready: true`, `blocked_areas: []`, exactly one finding (`CONTRADICTION`, `level: 2`, `source: AGENT`) and zero `KERNEL` findings.
3. Exactly one `escalations` row: `to_level == 2`, `category == PRODUCT`, question starts with `[CONTRADICTION] GDD/small_game.md#shop-prices`; `ESCALATION_RAISED` ledger event with `to_level 2`; PO disabled → one pending `ApprovalRequest(kind="escalation")` with row json `degraded_to_user: true` (E05-S02).
4. `walk phase plan PHASE-01` → `PLANNING (TASK-0002)`; ticks complete the plan task; `walk phase plan PHASE-01` → `PLANNED: 2 epics, 3 features, 6 stories`.
5. Workflow: 2 EPIC, 3 FEATURE, 6 STORY items, all `IDEA`, all `phase_id == PHASE-01`; `PHASE-01.scope_epic_ids` = both epics; `PHASE-02` still `PLANNED` with empty scope.
6. Every story contract has `goal`, `acceptance_criteria`, `required_evidence`, `owner_role SENIOR_DEV`, `reviewer_role LEAD_DEV`, `source_requirements` whose `requirement_id`s exist in the matrix; the second Shop story's `dependencies` hold the first Shop story id.
7. `LocalWorkProvider` has 11 records labelled `walk:<id>`, 9 PARENT links and 1 BLOCKS link.
8. `traceability.yaml`: every story id appears in `links.work_items` of at least one requirement; every requirement lists its feature under `specs`; each feature context `Relevant GDD` lists its refs.
9. `gdd-coverage.md` Summary shows `MOVEMENT 0%`, `COMBAT 0%`, `ECONOMY 0%` with 2 stories each and `## Not Planned` = `- none`; `walk status --json` → `gdd_coverage == {"MOVEMENT": 0.0, "COMBAT": 0.0, "ECONOMY": 0.0}`.
10. Scope: `walk run --once` after planning starts 0 runs; `walk work transition FEAT-0001 start_discovery` exits 2 with `phase PHASE-01 is PLANNED`.
11. `walk work trace REQ-COMBAT-001` exits 0 with `gap: IMPLEMENTATION`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the fixture GDD When `walk phase plan PHASE-01` first runs Then `READINESS_PENDING` and six requirements in `traceability.yaml` | `tests/e2e/test_e06_gate.py::test_plan_starts_with_readiness_and_requirements` |
| 2 | Given the readiness run Then `gdd-readiness.yaml` ready with exactly one agent CONTRADICTION finding at level 2 and no kernel findings | `tests/e2e/test_e06_gate.py::test_readiness_verdict_persisted` |
| 3 | Given the contradiction Then exactly one Level-2 PRODUCT escalation and one pending user approval (PO disabled) | `tests/e2e/test_e06_gate.py::test_contradiction_yields_level2_escalation` |
| 4 | Given the plan run Then `walk phase plan` reports `PLANNED: 2 epics, 3 features, 6 stories` | `tests/e2e/test_e06_gate.py::test_phase_planned_counts` |
| 5 | Given the planned items Then hierarchy, `phase_id`, scope epics and untouched PHASE-02 match step 5 | `tests/e2e/test_e06_gate.py::test_hierarchy_and_scope` |
| 6 | Given the stories Then every contract satisfies §57 fields and the dependency is recorded | `tests/e2e/test_e06_gate.py::test_story_contracts_complete` |
| 7 | Given `LocalWorkProvider` Then 11 records, 9 PARENT links, 1 BLOCKS link | `tests/e2e/test_e06_gate.py::test_work_provider_records_and_links` |
| 8 | Given `traceability.yaml` Then every story linked to a requirement and every requirement to its feature spec | `tests/e2e/test_e06_gate.py::test_every_story_traced_to_requirement` |
| 9 | Given `gdd-coverage.md` and `walk status --json` Then 0 % per area for all three areas | `tests/e2e/test_e06_gate.py::test_coverage_zero_per_area` |
| 10 | Given the PLANNED phase Then no run is admitted and `start_discovery` is rejected by `in_phase_scope` | `tests/e2e/test_e06_gate.py::test_scope_blocks_execution_before_start` |
| 11 | Given `walk work trace REQ-COMBAT-001` Then exit 0 and first gap IMPLEMENTATION | `tests/e2e/test_e06_gate.py::test_trace_chain_until_implementation` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e06_gate.py` (11 passed).
- Demo transcript on the fixture repo: `walk phase plan PHASE-01` (three times, interleaved with `walk run --once`), `cat .ai/project/gdd-readiness.yaml`, `walk approvals --pending`, `walk work list --phase PHASE-01`, `head -30 .ai/project/traceability.yaml`, `cat .ai/project/gdd-coverage.md`, `walk work trace REQ-ECONOMY-002`.

#### Notes
- WBS §9 maps §136 "GDD analyzed · Phase planned" to this story; E07-S10 builds `e07_scenario` on `e06_scenario` (EPIC-07 `(verify)` note), so `E06Scenario` field names are part of this story's contract.
- Gate uses only fakes and a temp repo; no network. Any production change is a separate `bugfix` story; this commit touches tests (and at most the fixture GDD) only.
- Commit subject: `feat: add epic 06 gate test for gdd compile to phase plan (E06-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E06-R01 — Review E06

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 7, 9), §48, §49, §57, §58, §73, §74
**Depends on:** E06-S08
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the E06 implementer where possible, §23) verifies every E06 story against the Definition of Done, Invariant 7 (phase scope) and the derived-not-entered rule of §74, recording defects as `bugfix` stories.

#### Scope
- In: stories E06-S01…S08 and their commits; `INTERFACES.md` / `DOMAIN-MODEL.md` deltas (`assign_phase_scope`, `WorkItemDraft.labels/gdd_refs`, `MemoryManager.write_project_data/read_project_data`, `story_workflow` `analysis_done` row); WBS §6 register entries from this epic.
- Out: fixing defects (each becomes `E06-Bxx`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-06-gdd-compiler.md` | modify | — (review record appended; `E06-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/ARCHITECTURE.md` | modify (only if drift found) | — |
| `tests/architecture/test_project_data_single_writer.py` | create | — |
| `tests/architecture/test_coverage_derived.py` | create | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5.

#### Behavior
1. For each story: `git show <sha>`; Files table == changed files (extra files need commit-body justification); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules.
2. Single writer (ADR-0003 D-4): no module other than `walk.memory` opens files under `.ai/project/` for writing; `traceability.yaml`, `gdd-readiness.yaml`, `gdd-coverage.md` are written only through `write_project_data`.
3. §74: no code path accepts a coverage percentage as input; `gdd_coverage` and `GddCoverage` are computed from item states and requirement refs only.
4. Invariant 7: `in_phase_scope` is registered on every transition INTERFACES §3.1 lists it for; `ready_items` never returns items of a non-ACTIVE/REWORK phase; the e2e gate DB shows zero runs on PHASE-01 items while it is PLANNED.
5. §49/§50: `GddFindingKind` equals the §49 list; every `(kind, severity)` has a `FINDING_ESCALATION` entry; Level-0 findings raise no escalation; levels are capped by `Project.autonomy_level_max`.
6. §57/§58: every story created by `GddCompiler.materialise` in the gate DB has a non-empty goal, acceptance criteria, source requirement and required evidence, so `check_definition_of_ready` content checks pass.
7. Import table (ARCHITECTURE §2.2): `walk.workflow` modules added by E06 (`gdd`, `traceability`, `trace_query`, `coverage`) import no `memory`, `agents`, `runtime` or `orchestrator` code; `import-linter` green.
8. `NEW NAME:` items of the epic header table are present in WBS §6 or listed in the review note for the architect.
9. Defects → `E06-Bxx` stories using the template; commit `docs: review epic 06 stories E06-S01..S08 (E06-R01)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E06 story When the DoD checklist is applied Then every box is checked or an `E06-Bxx` story exists | manual checklist recorded in Evidence |
| 2 | Given `src/walk` outside `walk/memory` When scanned for writes to paths containing `.ai/project` (`open(`, `write_text`, `write_bytes`, `replace(`) Then no match | `tests/architecture/test_project_data_single_writer.py::test_only_memory_writes_project_data` |
| 3 | Given `walk.workflow.coverage` and `DefaultWorkflowManager.gdd_coverage` When their inputs are inspected Then no parameter or config key carries a percentage | `tests/architecture/test_coverage_derived.py::test_coverage_has_no_manual_input` |
| 4 | Given the E06 gate DB When querying `agent_runs` joined to `work_items` with `phase_id = 'PHASE-01'` Then zero rows | manual checklist recorded in Evidence |
| 5 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % | manual checklist recorded in Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after the review commit.
- List of `E06-Bxx` stories created (or "none") and NEW NAME items forwarded to the architect.

#### Notes
- Tests 2–3 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- Commit subject: `docs: review epic 06 stories E06-S01..S08 (E06-R01)`.

#### Evidence (filled by implementer)
_pending_
