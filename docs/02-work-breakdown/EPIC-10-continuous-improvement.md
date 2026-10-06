# EPIC-10 — Continuous Improvement

**Roadmap stage:** §135 Stage 10
**Goal.** Production evidence turns into controlled, versioned behaviour change: observations (agent-made and ledger-detected) become hypotheses and candidates, candidates are reviewed by the §104 authority tier, approved candidates become `BehaviorVersion`s that roll out through `rollout_workflow` (DRAFT → EXPERIMENTAL → LIMITED → DEFAULT → DEPRECATED, with rollback), projects pin the versions they run, experiments (A/B by work-item hash, shadow evaluation) and §116 metrics measure the outcome, and every step is a ledger event — while project learning stays in `.ai/improvements/` and kernel learning in `$WALK_HOME/.improvement/` (promotion is explicit).
**Requirements.** §94–§121 (all of Continuous Improvement), §6.11, §32 (hook attachments `ON_IMPROVEMENT_OBSERVATION`, `ON_PHASE_REVIEW_START`, `ON_PHASE_GATE_DECISION`, `ON_AGENT_START`), §82/§105 (`behavior_versions` on events, pins), §137 (Inv. 13; Inv. 5 for PROCESS decisions), §138 (Workflow Drift), §139 (experiment methodology → ADR-0008 addendum).
**Epic gate.** `tests/e2e/test_e10_gate.py`: a repeated-fallback signal produces an observation, `walk improvement promote` copies it to kernel scope, a MEDIUM candidate is approved by PO, `register_version` creates `feature_workflow 1.1` at `LIMITED` with a changelog entry, the project pins it, ledger events carry `behavior_versions`, and `rollback` returns to `DRAFT`.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E10-R01.
**Preconditions.** E09-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green. E10 runs in parallel with E11 (WBS §7.1): E10 stories never touch `walk.workflow.release`, `walk.orchestrator.release*`, `walk.integrations.store*` or `cmd_rc.py`; the one shared file is `src/walk/workflow/tables/story_workflow.yaml` (see E10-S07 Notes).
**Refine first.** E10-X01 re-validates every Files table below against the `src/walk/` tree as it exists after E09 — E01 (S18–S31), E03 (S06–S20), E05–E09 stories were planned at index level when this file was written; paths and symbols marked `(verify)` are the ones most likely to differ.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E10-X01 | Refine E10 against codebase | E09-R01 | LOW |
| E10-S01 | Observations full: `observe`, `.ai/improvements/`, `walk improvement observations` | E10-X01, E04-S13 | MEDIUM |
| E10-S02 | `detect_signals` from ledger | E10-S01 | MEDIUM |
| E10-S03 | Kernel store `$WALK_HOME/.improvement/` and kernel DB migrations | E10-X01 | MEDIUM |
| E10-S04 | Candidates and risk-tier review, `walk improvement candidates` | E10-S03, E05-S01 | HIGH |
| E10-S05 | `BehaviorVersion` registry, `rollout_workflow`, pins, changelog | E10-S04, E02-S04 | HIGH |
| E10-S06 | Promotion and pattern/anti-pattern registries | E10-S03 | MEDIUM |
| E10-S07 | Retrospectives with narrative and PROCESS_ARCHITECT constitution | E10-S01, E07-S08 | MEDIUM |
| E10-S08 | Experiments: A/B by work-item hash and shadow evaluation | E10-S05 | HIGH |
| E10-S09 | Improvement metrics and report | E10-S02, E09-S02 | MEDIUM |
| E10-S10 | Epic gate: observation → versioned rollout (e2e) | E10-S06, E10-S07, E10-S08, E10-S09 | MEDIUM |
| E10-R01 | Review E10 | E10-S10 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (especially §3.4 payload-key pattern, §3.5 ledger write points, §3.6 fakes/e2e, §3.7 CLI layout — `improvement` command group).
2. ADR-0008 (D-1 two stores, D-2 explicit promotion, D-3 versioned artefacts, D-4 pins, D-5 rollout, D-6 authority tiers, D-7 agents cannot write behaviour, D-8 changelog, D-9 experiments), ADR-0006 (D-2 kernel executes side effects, D-3 rule semantics), ADR-0009 (D-3 IPC via `commands`, D-8 credentials, D-15), ADR-0013 (constitution schema, D-6 immutability).
3. `INTERFACES.md` §1.15 (`ImprovementManager`), §3.7 (`rollout_workflow`), §1.14 (`LedgerManager`, `EvidenceManager`, `TelemetryManager`), §1.9 (`DecisionManager.record`), §1.10 (`PermissionManager`), §1.13 (`ToolInvoker`, `OutputApplier`), §1.3 (`TransitionTable`, `Guard`), §4 (routing table), §6 (`walk improvement …`, `walk version`, `walk report improvement`).
4. `DOMAIN-MODEL.md` §2 (`OBS-`/`OBS-K-`/`IMP-`/`PATTERN-`/`ANTI-`/`EXP-`/`RETRO-` ids), §3 (`LearningScope`, `ImprovementScope`, `RolloutStage`, `ImprovementRisk`, `CandidateState`, `LedgerEventKind`, `DecisionCategory.PROCESS`, `ApprovalRequest.kind == "IMPROVEMENT"`), §4.14 (all improvement entities), §4.12 (`RetrospectiveMetrics`, `LedgerEvent.behavior_versions`), §6.2 (`improvement_*`, `patterns`, `retrospectives`, `behavior_versions`, `experiments`, `kernel_changelog`; table → DB mapping).
5. `ARCHITECTURE.md` §4.1 (hook rows named in item 1), §4.3 (`improvement.ImprovementManager` write point: `IMPROVEMENT_OBSERVATION`, `IMPROVEMENT_CANDIDATE`, `BEHAVIOR_VERSION_CHANGED`), §6 (`BoundaryAuditor` forbidden paths), §7 (Inv. 13), §8 (`improvements/` layout), §9 (`$WALK_HOME/.improvement/` layout), §2.2 (improvement may import `agents`, `model_router`, `memory`, `decisions`, `debate`, `skills`, `hooks`, `workflow`, `telemetry`; never `runtime`, `orchestrator`, `permissions`, `tools`, `integrations`).
6. `requirements/WAL_K_REQ.md` §94–§121, §6.11, §82, §105, §138 "Workflow Drift".
7. Existing files named in each story's Files table (E02-S04, E04-S13, E07-S05/S08, E09-S02/S05/S06) and their tests.

Parallel sets (WBS §8): `{S01→S02} ∥ {S03→S06}`; `{S07} ∥ {S08} ∥ {S09}` after their dependencies; S04 after S03 and E05-S01; S05 after S04; S10 last.

**Scope/store rule (binding for every story).** Every improvement entity carries `scope: LearningScope`. `PROJECT` rows live in the project DB and documents in `<repo>/.ai/improvements/` (written only through `MemoryManager.write`, ADR-0003 D-4); `KERNEL` rows live in `$WALK_HOME/kernel.db` and documents in `$WALK_HOME/.improvement/<folder>/` (written through `KernelImprovementStore`, E10-S03, using the same front-matter schema and `walk.persistence.atomic_write`). Ledger events are always written to the **project** ledger of the kernel instance performing the action (the kernel DB has no ledger). Nothing is written to `$WALK_HOME` by S01, S02, S07 or S09; nothing is promoted automatically (§110).

## `NEW NAME:` items introduced by this epic (to be added to WBS.md §6 by E10-X01)

| Item | Story | Why |
|---|---|---|
| `ObservationDraft.evidence_ids`, `ObservationDraft.ledger_seq_refs` (optional fields); `ObservationQuery`; `ObservationRepository.query/exists/mark_promoted`; `ImprovementManager.list_observations`; `walk improvement show <ID>`; `OBSERVATION_DEDUPE_WINDOW_S`; module `walk.improvement.documents` | S01 | §96 observations must link evidence and ledger rows; INTERFACES §1.15 has no query/listing method |
| module `walk.improvement.signals` (`SignalRule`, `SignalMatch`, `SignalDetector`, `load_signal_rules`) and data file `signals.yaml`; hook callable `phase_review_detect_signals`; `walk improvement detect`; `CommandConsumer` command `improvement.detect` | S02 | §99 sources are declared as data; INTERFACES §1.15 names `detect_signals` without rules or a CLI |
| module `walk.improvement.kernel_home` (`KernelHome`, `KernelConfig`, `WALK_HOME_ENV`, `DEFAULT_WALK_HOME`, `IMPROVEMENT_FOLDERS`); module `walk.improvement.store` (`KernelImprovementStore`, `ProjectImprovementStore`, `store_for`); repositories `CandidateRepository`, `PatternRepository`, `BehaviorVersionRepository`, `ExperimentRepository`, `ChangelogRepository`; kernel migration `0002_improvement_indexes.sql`; `KernelSettings.walk_home`; `KernelOverrides.kernel_home`; `walk doctor` section `improvement_home`; fixture `tmp_walk_home` | S03 | ARCHITECTURE §9 fixes the layout but no code owns `$WALK_HOME` |
| module `walk.improvement.candidates` (`CANDIDATE_TRANSITIONS`, `CandidateEvent`, `APPROVER_TIERS`, `can_approve`, `candidate_from_observations`); `CANDIDATE_SECTIONS` (`walk.memory.sections`); `ImprovementManager.candidate_event/list_candidates`; `CandidateQuery`; KERNEL tools `improvement.candidate`, `improvement.review` (provider `improvement`); `walk improvement candidates list/new/event/review` | S04 | §97 lifecycle and §104 tiers need data tables and an enforceable channel for agents (§103) |
| `rollout_workflow.yaml` under `walk/workflow/tables/`; module `walk.improvement.rollout` (`RolloutStateMachine`, `ROLLOUT_GUARDS`, `rollout_event_for`, payload keys `candidate_state`, `experiment_defined`, `shadow`, `experiment_evidence_count`, `approver_role`, `risk`, `projects_ran_phase`, `metrics_not_worse`, `changelog_entry_present`, `successor_default_exists`); module `walk.improvement.changelog` (`ChangelogEntry`, `render_changelog`, `changelog_path`); `ChangelogRequired` error; `$WALK_HOME/.improvement/versions/<KIND>/<name>/<version>.<ext>` folder; `BehaviorVersionCatalog.resolve/entries`; `ImprovementManager.rollback/list_versions/pin_version`; `PIN_RISK_BY_KIND`; `walk improvement versions/stage/pin/rollback` | S05 | INTERFACES §3.7 is a table without an engine; ARCHITECTURE §9 has no place for non-builtin artefact versions; INTERFACES §1.15 lacks rollback/pin methods |
| module `walk.improvement.patterns` (`pattern_document`, `anti_pattern_document`, `load_builtin_anti_patterns`, `BUILTIN_ANTI_PATTERNS_PATH`) and data file `defaults/anti_patterns.yaml`; `PATTERN_SECTIONS`, `ANTI_PATTERN_SECTIONS`; `ImprovementManager.register_pattern/register_anti_pattern/list_patterns`; `walk improvement patterns` | S06 | §112–§113 registries have models but no service methods, documents or seeds |
| kernel default constitution `process_architect.md`; module `walk.improvement.retrospectives` (`ANALYSIS_LABEL_PREFIX`, `ANALYSIS_STEP_LABEL_PREFIX`, `analysis_labels`, `analysis_step_of`, `narrative_from_output`); `story_workflow` row `analysis_done` + guard `is_analysis_task`; `ANALYSIS_ROUTES`; `ImprovementManager.retrospective(level, subject_id)`; `RETRO.md.j2` block `process_architect_duties`; `walk improvement retro --narrative` | S07 | §101 role exists only as an `AgentRole` member; a run needs a work item (`AgentExecutor.start`), and no phase-level run mechanism is confirmed |
| module `walk.improvement.experiments` (`ExperimentAssigner`, `arm_for`, `ExperimentResult`, `compare_arms`, `MIN_ARM_SIZE`, `IMPROVEMENT_THRESHOLD`, `REGRESSION_TOLERANCE`, `EXPERIMENT_METRICS`, `ShadowEvaluator`, `RoutingShadowEvaluator`, `EffortShadowEvaluator`); `LedgerEventKind.SHADOW_EVALUATION`; `KernelVersionPins.experiments`; `ImprovementManager.start_experiment/end_experiment/shadow_evaluate/experiment_versions_for`; `AgentExecutor` constructor parameter `versions_for_item`; hook callable `agent_start_shadow_evaluate`; `EXPERIMENT_SECTIONS`; `walk improvement experiments list/show/start/end`; ADR-0008 addendum | S08 | ADR-0008 D-9 fixes the two methods but defers thresholds and names no code; shadow results need a ledger kind |
| `ImprovementMetrics` (`walk.telemetry.models`), `IMPROVEMENT_METRIC_QUERIES`, `compute_improvement_metrics`, `AUTONOMY_QUALITY_FIELDS` (`walk.telemetry.metrics`); `TelemetryManager.improvement_metrics`; `VersionOutcome`, `ImprovementManager.measure_version`; `walk improvement metrics`; `walk report improvement --since` | S09 | §116 lists metrics that `RetrospectiveMetrics` does not cover (E09-S06 Notes) |
| `e10_scenario` fixture, `E10Scenario` (`tests/e2e/conftest.py`) | S10 | Gate fixture |

---

### E10-X01 — Refine E10 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §135 (Stage 10), §58, §94, §119, §139
**Depends on:** E09-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E10 story's Files table, interface references, dependencies and planning assumptions are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E09-R01, and the corrected epic file plus WBS rows are committed before any `E10-S*` story starts (WBS §1 `X` task, §2 rule 3).

#### Scope
- In: this file (E10-S01…S10, R01); the header `NEW NAME:` table; WBS §3.4 payload-key rows introduced by E10-S05; WBS §5 rows for E10; WBS §6 register rows for every E10 `NEW NAME:` item; resolution of every `(verify)` marker; confirmation or correction of the assumptions listed under Behavior.
- Out: renaming, renumbering, adding or dropping stories (WBS §1); any source or test change; the ADR-0008 addendum (written by E10-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-10-continuous-improvement.md` | modify | — (corrected Files tables, interface references, Notes, `(verify)` markers resolved) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§3.4 rows for rollout payload keys, §5 status of E10-X01, §6 register rows for E10 `NEW NAME:` items) |

#### Interface contract
No code. Refine protocol (WBS §1 `Exx-Xyy`, §2 rule 3), applied to every Files table of E10-S01…S10 and E10-R01:
1. Every `create` path does not exist in `src/walk/` or `tests/` (or is created by an earlier story of this epic); every `modify` path exists (or is created by an earlier story of this epic).
2. Every symbol named in a `modify` row already exists in that file with the signature the story assumes (grep), or is listed as new by the story.
3. Every `INTERFACES.md §x.y`, `DOMAIN-MODEL.md §x.y`, `ARCHITECTURE.md §x` and ADR `D-n` reference resolves and still defines the referenced name.
4. Every `Depends on` id outside E10 is `DONE` in WBS §5 (E09-R01, E04-S13, E05-S01, E02-S04, E07-S08, E09-S02).
5. Migration numbers: the next free numbers under `src/walk/persistence/migrations/kernel/` and `.../project/` are recorded in E10-S03 (`0002_improvement_indexes.sql` assumed for kernel).
6. Every `(verify)` marker is resolved (kept or corrected) and removed.

#### Behavior
Assumptions made at planning time (E01-S18…S31, E03-S06…S20, E05–E09 stories were partly planned at index level) that this task must confirm or correct in this file:
1. `walk.improvement` package exists with `models.py`, `protocols.py`, `repository.py` (`ObservationRepository`), `service.py` (`DefaultImprovementManager`), `versions.py` (`BehaviorVersionCatalog`, `KernelVersionPins`, `PINS_PATH`), `errors.py` (`VersionPinError`) — E02-S04, E04-S13.
2. `BehaviorVersionCatalog.pinned()` exists (E04-S13 rule 6 calls it; E02-S04 defines `scan`/`key` only) — correct E10-S05 if the name differs.
3. `src/walk/persistence/migrations/kernel/0001_init.sql` (E01-S03) creates every kernel-DB table listed in DOMAIN-MODEL §6.2 "Table → DB"; `Database` can open a second (kernel) database file with `MigrationRunner.apply_pending(db, "kernel")`.
4. `walk.persistence.atomic_write` exists (E01-S04) for non-`.ai/` writes used by `KernelImprovementStore` (E10-S03).
5. The E07-S08 phase retrospective lives in `DefaultImprovementManager.phase_retrospective`, writes `.ai/improvements/RETRO-PHASE-NN.md` and a `retrospectives` row, and the `RETRO.md.j2` template exists (E01-S18, §3.9) — E10-S07 depends on all three `(verify)`.
6. `src/walk/hooks/builtins.py` holds the E04-S13 improvement callables and `BuiltinHookDeps.improvement` (E07-S05); E10-S02/S07/S08 add callables there.
7. `DefaultTaskRouter` is in `src/walk/orchestrator/router.py`, `DefaultOutputApplier` in `src/walk/runtime/applier.py`, `DefaultAgentExecutor` in `src/walk/runtime/executor.py` (E01-S27, E03-S07/S08) — E10-S07 and E10-S08 modify them.
8. `ImprovementReportQuery` is in `src/walk/telemetry/reports.py` (E09-S02) and `METRIC_QUERIES`/`compute_metrics` in `src/walk/telemetry/metrics.py` (E01-S06, E09-S06) — E10-S09 extends both.
9. `DefaultLedgerManager(behavior_versions=…)` stamping (E09-S05) is wired from `KernelVersionPins` in `src/walk/cli/composition.py`; E10-S08 replaces the callable with an experiment-aware one.
10. `ToolInvoker.register_handler` (E01-S26) is the registration mechanism for KERNEL tools; E10-S04 registers `improvement.candidate`/`improvement.review` from the composition root (improvement may not import `tools`/`runtime`, ARCHITECTURE §2.2).
11. `DecisionManager.record(..., category=PROCESS)` accepts kernel-actor records for improvement decisions (E05-S01/S03) — E10-S04 records one decision per review.
12. Shared-file coordination with E11 (runs in parallel, WBS §7.1): E10-S07 and E11-S01 both modify `story_workflow.yaml`, `src/walk/workflow/guards.py`, `src/walk/orchestrator/router.py` and `src/walk/runtime/applier.py`; record the merge-order rule from E10-S07 Notes in both epic files.
13. Record the rollout payload keys of E10-S05 in WBS §3.4 and every `NEW NAME:` item of E10 (header table plus each story's Notes) in WBS §6.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every Files table path in this file When checked against `src/walk/` and `tests/` Then each `modify` path exists and each `create` path is absent or created by an earlier E10 story, or the row is corrected | manual checklist recorded in Evidence |
| 2 | Given every `INTERFACES.md`/`DOMAIN-MODEL.md`/`ARCHITECTURE.md`/ADR reference in this file When opened Then the section exists and defines the named symbol | manual checklist recorded in Evidence |
| 3 | Given WBS §5 When E10 dependencies outside the epic are read Then each is `DONE` or the dependent story is marked `BLOCKED` with the id | manual checklist recorded in Evidence |
| 4 | Given Behavior items 1–13 When each is confirmed or corrected Then this file reflects the real path/symbol and WBS §3.4/§6 contain the E10 rows | manual checklist recorded in Evidence |
| 5 | Given the corrected file When `py -3 scripts/validate_wbs.py` runs Then no error mentions an `E10-` id | manual checklist recorded in Evidence |

#### Evidence required
- Checklist table (story → files verified → interface refs verified → deps verified → corrections made).
- `scripts/validate_wbs.py` output.
- `git show --stat` of the refine commit (only the two documentation files).

#### Notes
- WBS §2 rule 3; IMPLEMENTATION-PROTOCOL §1.2 (Definition of Ready); DEFINITION-OF-DONE "Definition of Ready".
- Corrections are made in place; no story text is removed, only paths, symbol names, references and Notes are corrected. A story whose assumption fails is set `BLOCKED` with `pending <symbol> (<story that should create it>)`, never rewritten into a different story.
- No production code; no test files.
- Commit subject: `docs: refine epic 10 stories (E10-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S01 — Observations full: `observe`, `.ai/improvements/`, `walk improvement observations`

**Status:** TODO
**Type:** feat
**Requirements:** §96, §99, §106, §110, §119, §6.11, §32 (`ON_IMPROVEMENT_OBSERVATION`)
**Depends on:** E10-X01, E04-S13
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Project-scoped observations are complete §96 records: they link evidence and ledger rows (§106 provenance), are validated and de-duplicated, round-trip between the `improvement_observations` row and `.ai/improvements/OBS-NNNN.md` through one document module, and can be filtered and inspected with `walk improvement observations` / `walk improvement show`.

#### Scope
- In: `ObservationDraft.evidence_ids/ledger_seq_refs`; `ObservationQuery`; `ObservationRepository.query/exists/mark_promoted`; `ImprovementManager.list_observations`; `observe` validation, de-duplication and payload enrichment; module `walk.improvement.documents` (observation documents); E04-S13 hook delegation; CLI filters and `show`.
- Out: automatic ledger signal detection (E10-S02); kernel store and `OBS-K-` documents (E10-S03); promotion (`mark_promoted` is called by E10-S06); candidates (E10-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/models.py` | modify | `ObservationDraft.evidence_ids`, `ObservationDraft.ledger_seq_refs` |
| `src/walk/improvement/models.py` | modify | `ObservationQuery` |
| `src/walk/improvement/repository.py` | modify | `ObservationRepository.query`, `ObservationRepository.exists`, `ObservationRepository.mark_promoted` |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.list_observations` |
| `src/walk/improvement/documents.py` | create | `observation_document`, `observation_from_document` |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.observe`, `DefaultImprovementManager.list_observations`, `OBSERVATION_DEDUPE_WINDOW_S` |
| `src/walk/improvement/__init__.py` | modify | re-exports `ObservationQuery`, `observation_document`, `observation_from_document` |
| `src/walk/hooks/builtins.py` | modify | `improvement_observation_write` (delegates to `observation_document`) `(verify)` |
| `src/walk/cli/cmd_improvement.py` | modify | `observations` (filters), `show` |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 `list_observations`; §6 `walk improvement observations` options, `walk improvement show`) |
| `tests/agents/test_models_observation_draft.py` | create | — |
| `tests/improvement/test_documents_observation.py` | create | — |
| `tests/improvement/test_repository_observations.py` | create | — |
| `tests/improvement/test_service_observe_full.py` | create | — |
| `tests/cli/test_cmd_improvement_observations.py` | create | — |

#### Interface contract
`ImprovementManager.observe` per INTERFACES §1.15 (signature unchanged); `ImprovementObservation` per DOMAIN-MODEL §4.14 (unchanged).
```python
# src/walk/agents/models.py — ObservationDraft, additive optional fields
evidence_ids: list[EvidenceId] = Field(default_factory=list, description="§106 evidence supporting the observation")
ledger_seq_refs: list[int] = Field(default_factory=list, description="ledger_events.seq rows the observation is based on")

# src/walk/improvement/models.py
class ObservationQuery(WalkModel):
    ids: list[ObservationId] | None = None
    scope: LearningScope | None = None
    source_signal: str | None = None
    improvement_scope: ImprovementScope | None = None
    work_item_id: WorkItemId | None = None
    since: datetime | None = None
    promoted: bool | None = None          # True → promoted_to set; False → not set
    limit: int = Field(default=100, ge=1, le=1000)

# src/walk/improvement/repository.py
class ObservationRepository:
    async def query(self, q: ObservationQuery) -> list[ImprovementObservation]: ...      # created_at DESC, id DESC
    async def exists(self, source_signal: str, work_item_id: WorkItemId | None,
                     improvement_scope: ImprovementScope, since: datetime) -> ObservationId | None: ...
    async def mark_promoted(self, observation_id: ObservationId, promoted_to: ObservationId) -> None: ...

# src/walk/improvement/documents.py
def observation_document(obs: ImprovementObservation) -> MemoryDocument: ...
def observation_from_document(doc: MemoryDocument) -> ImprovementObservation: ...

# src/walk/improvement/protocols.py — ImprovementManager addition
async def list_observations(self, query: ObservationQuery) -> list[ImprovementObservation]: ...

# src/walk/improvement/service.py
OBSERVATION_DEDUPE_WINDOW_S: int = 86_400
```
CLI: `walk improvement observations [--signal S] [--component IMPROVEMENT_SCOPE] [--item ID] [--since ISO] [--promoted/--not-promoted] [--limit N] [--json]`; `walk improvement show OBS_ID [--json]`.

#### Behavior
1. `observe` rejects a draft whose `observed`, `potential_cause` or `possible_improvement` is empty after `strip()` with `OutputInvalid` naming the field; no row, no event.
2. Every `draft.evidence_ids` entry must resolve through `EvidenceManager`; every `ledger_seq_refs` entry must exist in `ledger_events` (one `SELECT COUNT(*) … WHERE seq IN (…)`); otherwise `OutputInvalid` naming the first unknown id or seq; no row, no event.
3. De-duplication: for `source_signal != "agent"`, when `ObservationRepository.exists(signal, work_item_id, improvement_scope, now − OBSERVATION_DEDUPE_WINDOW_S)` returns an id, `observe` returns that observation unchanged — no new id, no ledger event, no hook. Agent observations (`"agent"`) are never de-duplicated (§96: agents MAY create observations).
4. The `IMPROVEMENT_OBSERVATION` ledger payload keeps the E04-S13 keys (`source_signal`, `improvement_scope`) and adds `id`, `evidence_ids`, `ledger_seq_refs`; the event carries `work_item_id`/`run_id` from the call.
5. `observation_document(obs)`: front matter `id`, `type: observation`, `title` = first line of `observed` truncated to 80 chars, `status` = `PROMOTED` when `promoted_to` is set else `OPEN`, `related.work_items` = `[work_item_id]` when set; H2 sections exactly `OBSERVATION_SECTIONS` in order; `Evidence` lists one `- EVD-…` line per evidence id then one `- ledger seq N` line per seq ref. `observation_from_document(observation_document(o))` equals `o` for every field persisted in the row JSON.
6. The `ON_IMPROVEMENT_OBSERVATION` MUST hook (`improvement_observation_write`) builds the document with `observation_document` and writes it via `MemoryManager.write`; it contains no rendering code of its own.
7. `list_observations` reads the project DB only in this story (a query with `scope=KERNEL` returns `[]` until E10-S06); filters combine with AND; ordering `created_at DESC, id DESC`.
8. `mark_promoted` sets `promoted_to` once; a second call with a different target raises `ConfigError`; the document status becomes `PROMOTED` on the next hook write (E10-S06 rewrites it).
9. `walk improvement show OBS-0001` prints the document body; unknown id → exit 1; ids of other prefixes → exit 1 `unsupported id prefix` (extended by E10-S04/S06/S08).
10. Nothing is written under `$WALK_HOME` (Scope/store rule; §110).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an `ObservationDraft` without the new fields When validated Then `evidence_ids == []` and `ledger_seq_refs == []` (E04-S13 payloads still parse) | `tests/agents/test_models_observation_draft.py::test_observation_draft_new_fields_default_empty` |
| 2 | Given an observation with 2 evidence ids and 3 seq refs When `observation_document` then `observation_from_document` Then the result equals the original | `tests/improvement/test_documents_observation.py::test_observation_document_roundtrip` |
| 3 | Given an observation with `promoted_to` set When rendered Then front matter `status == "PROMOTED"` and sections equal `OBSERVATION_SECTIONS` | `tests/improvement/test_documents_observation.py::test_observation_document_status_and_sections` |
| 4 | Given 5 observations across 2 signals and 2 items When `query` with a signal and an item Then only matching rows in `created_at DESC` order | `tests/improvement/test_repository_observations.py::test_query_filters_and_order` |
| 5 | Given an observation already promoted When `mark_promoted` with a different target Then `ConfigError` | `tests/improvement/test_repository_observations.py::test_mark_promoted_once` |
| 6 | Given a draft with empty `observed` When `observe` Then `OutputInvalid` and no row and no ledger event | `tests/improvement/test_service_observe_full.py::test_observe_rejects_empty_fields` |
| 7 | Given a draft referencing `EVD-9999` When `observe` Then `OutputInvalid` naming `EVD-9999` | `tests/improvement/test_service_observe_full.py::test_observe_rejects_unknown_evidence` |
| 8 | Given a draft referencing ledger seq 10000 on a 50-event ledger When `observe` Then `OutputInvalid` | `tests/improvement/test_service_observe_full.py::test_observe_rejects_unknown_ledger_seq` |
| 9 | Given a `repeated_fallback` observation for STORY-0001 one hour ago When observed again Then the same id is returned and the ledger has one `IMPROVEMENT_OBSERVATION` | `tests/improvement/test_service_observe_full.py::test_observe_dedupes_signal_within_window` |
| 10 | Given two identical `agent` drafts When observed Then two distinct ids | `tests/improvement/test_service_observe_full.py::test_observe_never_dedupes_agent_observations` |
| 11 | Given a valid draft with evidence and seq refs When observed Then the ledger payload has `id`, `evidence_ids`, `ledger_seq_refs`, `source_signal`, `improvement_scope` and `.ai/improvements/OBS-0001.md` equals the `observation_document` rendering | `tests/improvement/test_service_observe_full.py::test_observe_payload_and_document` |
| 12 | Given any test in this story Then the temporary `$WALK_HOME` stays empty | `tests/improvement/test_service_observe_full.py::test_no_kernel_home_writes` |
| 13 | Given 3 observations When `walk improvement observations --component MODEL_ROUTING --json` Then only matching rows as a valid JSON list | `tests/cli/test_cmd_improvement_observations.py::test_observations_component_filter_json` |
| 14 | Given `walk improvement show OBS-0001` Then exit 0 and the `Observed` section text; given `OBS-0999` Then exit 1 | `tests/cli/test_cmd_improvement_observations.py::test_show_observation_and_unknown` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `walk improvement observations --json` (rows with `evidence_ids`), `walk improvement show OBS-0001`, `cat .ai/improvements/OBS-0001.md`.

#### Notes
- ADR-0003 D-4 (only `MemoryManager` writes under `.ai/`); ADR-0008 D-1/D-2 (project scope only; no automatic promotion); ARCHITECTURE §4.3 (`IMPROVEMENT_OBSERVATION` written by `ImprovementManager`), §8 `improvements/` layout.
- `OutputInvalid` (not `ConfigError`) because drafts come from `AgentOutput.observations` (E04-S13 rule 3); the applier already converts it into a rejected output.
- `NEW NAME:` `ObservationDraft.evidence_ids`, `ObservationDraft.ledger_seq_refs`; `ObservationQuery`; `ObservationRepository.query/exists/mark_promoted`; `ImprovementManager.list_observations`; `walk improvement show <ID>`; `OBSERVATION_DEDUPE_WINDOW_S`; module `walk.improvement.documents` (`observation_document`, `observation_from_document`).
- Commit subject: `feat: complete improvement observations with provenance (E10-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S02 — `detect_signals` from ledger

**Status:** TODO
**Type:** feat
**Requirements:** §99, §118, §94, §102, §110, §32 (`ON_PHASE_REVIEW_START`), §6.11
**Depends on:** E10-S01
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §99 improvement sources that are visible in the ledger are declared as data rules (`signals.yaml`), a read-only `SignalDetector` evaluates them over a time range, and `ImprovementManager.detect_signals` turns each match into a de-duplicated PROJECT observation with ledger references — run automatically when a phase enters review and on demand with `walk improvement detect`.

#### Scope
- In: module `walk.improvement.signals`; kernel default `signals.yaml` with the rule set below; `DefaultImprovementManager.detect_signals`; default hook `phase_review_detect_signals` on `ON_PHASE_REVIEW_START`; `walk improvement detect` (offline and via daemon command `improvement.detect`).
- Out: candidate creation from observations (E10-S04); kernel-scope signals (never — ADR-0008 D-2: detection creates PROJECT observations only); project-specific rule overrides (not planned); §99 sources not visible in the ledger (excessive code reading, bad task decomposition, technical debt — agent observations only, E10-S01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/signals.py` | create | `SignalRule`, `SignalMatch`, `SignalDetector`, `load_signal_rules`, `SIGNAL_RULES_PATH` |
| `src/walk/improvement/defaults/signals.yaml` | create | — (rule table below; `version: "1.0"`) |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.detect_signals`, `DefaultImprovementManager.__init__` (`signals: SignalDetector` parameter) |
| `src/walk/improvement/__init__.py` | modify | re-exports `SignalRule`, `SignalMatch`, `SignalDetector`, `load_signal_rules` |
| `src/walk/hooks/builtins.py` | modify | `phase_review_detect_signals` (default, priority 130) `(verify)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `improvement.detect`) `(verify)` |
| `src/walk/cli/cmd_improvement.py` | modify | `detect` |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 `detect_signals` docstring names `signals.yaml`; §6 `walk improvement detect`) |
| `src/walk/cli/composition.py` | modify | — (builds `SignalDetector(db, load_signal_rules())`, passes it to `DefaultImprovementManager`) |
| `tests/improvement/test_signals_rules.py` | create | — |
| `tests/improvement/test_signals_detector.py` | create | — |
| `tests/improvement/test_service_detect_signals.py` | create | — |
| `tests/hooks/test_builtins_detect_signals.py` | create | — |
| `tests/cli/test_cmd_improvement_detect.py` | create | — |

#### Interface contract
`ImprovementManager.detect_signals(since)` per INTERFACES §1.15.
```python
# src/walk/improvement/signals.py
SIGNAL_RULES_PATH: str = "improvement/defaults/signals.yaml"     # package-relative

class SignalRule(FrozenModel):
    name: str = Field(description="becomes ImprovementObservation.source_signal; snake_case, unique")
    requirement: str = Field(description="§99/§118 bullet this rule implements")
    improvement_scope: ImprovementScope
    event_kinds: list[LedgerEventKind]
    where: dict[str, str | int | bool | list[str]] = Field(default_factory=dict, description="payload key → value or allowed values")
    group_by: str = Field(description="'work_item_id' | 'run_id' | 'phase_id' | 'role' | 'payload.<key>' | 'none'")
    aggregate: Literal["count", "sum"] = "count"
    field: str | None = Field(default=None, description="for sum: 'cost_usd' | 'duration_ms' | 'payload.<key>'")
    threshold: float
    window_s: int | None = None
    observed: str               # str.format template; placeholders {group}, {value}, {threshold}, {window_s}
    potential_cause: str
    possible_improvement: str

class SignalMatch(FrozenModel):
    rule: str
    group: str | None
    value: float
    seqs: list[int]             # ascending, capped at 50
    work_item_id: WorkItemId | None
    run_id: RunId | None
    phase_id: PhaseId | None

class SignalDetector:
    def __init__(self, db: Database, rules: list[SignalRule]) -> None: ...
    @property
    def rules(self) -> list[SignalRule]: ...
    async def scan(self, since: datetime, until: datetime | None = None) -> list[SignalMatch]: ...

def load_signal_rules(path: Path | None = None) -> list[SignalRule]: ...
```
Shipped rule set (`signals.yaml`):

| name | §ref | kinds | where | group_by | aggregate | threshold | improvement_scope |
|---|---|---|---|---|---|---|---|
| `repeated_fallback` | §99 repeated model fallback | `MODEL_FALLBACK` | — | `work_item_id` | count | 2 | MODEL_ROUTING |
| `stale_context` | §99 stale context | `CONTEXT_FRESHNESS` | — | `run_id` | count | 3 | CONTEXT_FORMAT |
| `repeated_build_errors` | §99 repeated build errors | `BUILD_RESULT` | `ok: false` | `work_item_id` | count | 3 | SKILL |
| `recurring_rework` | §99 recurring QC bugs | `WORK_ITEM_TRANSITION` | `to_state: REWORK` | `work_item_id` | count | 2 | QUALITY_GATE |
| `failed_handoff` | §99 failed handoff | `ERROR` | `error_class: [NotResumable, HookFailed]` | `work_item_id` | count | 1 | CONTEXT_FORMAT |
| `tool_instability` | §99 tool instability | `TOOL_INVOKED` | `status: error` | `payload.tool` | count | 5 | TOOL_USAGE |
| `repeated_tool_denial` | §99 tool instability / ARCHITECTURE §4.1 `ON_TOOL_DENIED` | `TOOL_DENIED` | — | `role` | count | 3 | TOOL_USAGE |
| `high_cost` | §99 high cost | `COST_RECORDED` | — | `work_item_id` | sum `cost_usd` | 5.0 | MODEL_ROUTING |
| `excessive_task_duration` | §99 excessive task duration | `AGENT_RUN_ENDED` | — | `work_item_id` | sum `duration_ms` | 14400000 | EFFORT_POLICY |
| `user_override` | §118 repeated user overrides | `USER_OVERRIDE` | — | `payload.command` | count | 3 | WORKFLOW |
| `repeated_phase_rework` | §99 repeated phase rework, §118 REWORK/CHANGE | `PHASE_GATE_DECISION` | `decision: [REWORK, CHANGE]` | `none` | count | 2 | WORKFLOW |

#### Behavior
1. `load_signal_rules` validates: names unique and snake_case; every `event_kinds` member is a `LedgerEventKind`; `aggregate == "sum"` requires `field`; templates reference only the four placeholders; `threshold > 0`; any violation → `ConfigError` naming the rule. The file carries `version: "1.0"` in its header; it is not added to `BehaviorVersionCatalog` in this story (see Notes).
2. `SignalDetector.scan` is read-only SQL over `ledger_events` with `at >= since` (and `at < until` when given); when `window_s` is set the lower bound is `max(since, (until or now) − window_s)`. `where` keys match `json_extract(payload, '$.<key>')`; list values mean membership.
3. Grouping: `none` yields at most one match; `payload.<key>` groups by that payload value; groups whose aggregate is `>= threshold` produce one `SignalMatch`; `seqs` are the contributing rows (ascending, first 50); `work_item_id`/`run_id`/`phase_id` are set when the group key is that column or when all contributing rows share one value.
4. Matches are ordered by rule order in the file, then group key ascending — deterministic for equal input.
5. `detect_signals(since)` calls `scan(since)`, and for each match calls `observe(ObservationDraft(observed=…, potential_cause=…, possible_improvement=…, scope=rule.improvement_scope, ledger_seq_refs=match.seqs), actor=Actor(role=KERNEL), work_item_id=match.work_item_id, run_id=match.run_id, source_signal=rule.name)`; it returns only observations created by this call (E10-S01 de-duplication returns existing ones, which are excluded).
6. `detect_signals` never writes to the kernel store and never promotes (ADR-0008 D-2); every observation has `scope == PROJECT`.
7. `phase_review_detect_signals` (default attachment, `log_and_continue`) calls `detect_signals(since=<phase started_at from the last PHASE_TRANSITION to ACTIVE>)` before the retrospective attachment runs (priority 130 < the E07-S08 retrospective attachment priority `(verify)`), so that the retrospective sees the new observations.
8. `walk improvement detect [--since ISO] [--json]`: default `since` = 7 days before now; with a running daemon the CLI sends command `improvement.detect` (ADR-0009 D-3) and prints the result; without a daemon it runs in-process under `KernelLock`; prints one line per created observation `OBS-NNNN <signal> <work item or ->`, or `no new observations`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the shipped `signals.yaml` When loaded Then 11 rules with the names of the table, all kinds valid | `tests/improvement/test_signals_rules.py::test_shipped_rules_load` |
| 2 | Given a rule with `aggregate: sum` and no `field` When loaded Then `ConfigError` naming the rule | `tests/improvement/test_signals_rules.py::test_sum_rule_requires_field` |
| 3 | Given a template with placeholder `{foo}` When loaded Then `ConfigError` | `tests/improvement/test_signals_rules.py::test_unknown_placeholder_rejected` |
| 4 | Given 2 `MODEL_FALLBACK` events for STORY-0001 and 1 for STORY-0002 When `scan` Then one `repeated_fallback` match for STORY-0001 with both seqs | `tests/improvement/test_signals_detector.py::test_count_rule_groups_by_work_item` |
| 5 | Given `BUILD_RESULT` events with `ok: true` and `ok: false` When `scan` Then only `ok: false` rows count toward `repeated_build_errors` | `tests/improvement/test_signals_detector.py::test_where_filters_payload` |
| 6 | Given `COST_RECORDED` rows summing 6.0 USD for one item When `scan` Then one `high_cost` match with `value == 6.0` | `tests/improvement/test_signals_detector.py::test_sum_rule_threshold` |
| 7 | Given 3 `USER_OVERRIDE` events with `command: work.cancel` When `scan` Then one `user_override` match with `group == "work.cancel"` | `tests/improvement/test_signals_detector.py::test_user_override_groups_by_command` |
| 8 | Given events before `since` When `scan(since)` Then they are ignored | `tests/improvement/test_signals_detector.py::test_scan_respects_since` |
| 9 | Given the same ledger When `scan` runs twice Then identical match lists | `tests/improvement/test_signals_detector.py::test_scan_deterministic` |
| 10 | Given a ledger producing 2 matches When `detect_signals` Then 2 PROJECT observations with `source_signal` = rule names and `ledger_seq_refs` = match seqs | `tests/improvement/test_service_detect_signals.py::test_detect_creates_project_observations` |
| 11 | Given `detect_signals` called twice on the same ledger When the second call returns Then `[]` and the observation count is unchanged | `tests/improvement/test_service_detect_signals.py::test_detect_is_idempotent_via_dedupe` |
| 12 | Given a detection run Then the temporary `$WALK_HOME` stays empty | `tests/improvement/test_service_detect_signals.py::test_detect_never_writes_kernel_scope` |
| 13 | Given a phase entering `EVIDENCE_REVIEW` with 2 fallbacks on one story When `ON_PHASE_REVIEW_START` fires Then one `repeated_fallback` observation exists before the retrospective attachment runs | `tests/hooks/test_builtins_detect_signals.py::test_phase_review_runs_detection_before_retro` |
| 14 | Given no daemon When `walk improvement detect --since 2026-01-01T00:00:00Z` Then exit 0 and one line per new observation | `tests/cli/test_cmd_improvement_detect.py::test_detect_offline` |
| 15 | Given a running fake daemon When `walk improvement detect` Then a `commands` row `improvement.detect` is written and its result printed | `tests/cli/test_cmd_improvement_detect.py::test_detect_via_daemon_command` |

#### Evidence required
- Quality gate output.
- Demo on the E07 gate fixture repo: `walk improvement detect --since <phase start>` → observation lines; `walk improvement observations --signal repeated_fallback`.

#### Notes
- §99 sources as data follows CONVENTIONS §4 ("declared in data, never only in prose"); thresholds are planning defaults changed only by a kernel release. Cataloguing `signals.yaml` as a `QUALITY_GATE` `BehaviorVersion` is deliberately deferred: a new catalog entry would make every existing pin file fail `KernelVersionPins.validate` (E02-S04 rule 5) — a candidate for E10-S05 pin migration if the owner wants it.
- `failed_handoff` relies on `ERROR` payload key `error_class` written by `AgentExecutor` `(verify E01-S27)`; `recurring_rework` on `WORK_ITEM_TRANSITION` payload key `to_state` `(verify E01-S09)`; X01 corrects key names if they differ.
- The E04-S13 real-time hooks (`model_fallback_observe_repeated`, `context_stale_observe_repeated`) stay; E10-S01 de-duplication prevents double observations for the same signal and item.
- `NEW NAME:` module `walk.improvement.signals` (`SignalRule`, `SignalMatch`, `SignalDetector`, `load_signal_rules`, `SIGNAL_RULES_PATH`); data file `improvement/defaults/signals.yaml`; hook callable `phase_review_detect_signals`; `walk improvement detect`; `CommandConsumer` command `improvement.detect`; `DefaultImprovementManager(signals=…)`.
- Commit subject: `feat: detect improvement signals from ledger rules (E10-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S03 — Kernel store `$WALK_HOME/.improvement/` and kernel DB migrations

**Status:** TODO
**Type:** feat
**Requirements:** §119, §110, §111, §6.11, §137 (Inv. 13)
**Depends on:** E10-X01
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel-scope learning home exists as code: `KernelHome` resolves and initialises `$WALK_HOME` (folders of ARCHITECTURE §9, migrated `kernel.db`, `config.yaml`), `KernelImprovementStore` writes kernel documents with the `.ai/` front-matter schema, `store_for(scope)` selects the project or kernel store, the five remaining improvement repositories exist for both databases, and `walk doctor` reports the home's health.

#### Scope
- In: module `walk.improvement.kernel_home`; module `walk.improvement.store`; `CandidateRepository`, `PatternRepository`, `BehaviorVersionRepository`, `ExperimentRepository`, `ChangelogRepository`; kernel migration `0002_improvement_indexes.sql`; kernel `IdSequenceStore`; composition wiring (`KernelSettings.walk_home`, `KernelOverrides.kernel_home`, `KernelHandle.kernel_home`); `walk doctor` section `improvement_home`; test fixture `tmp_walk_home`.
- Out: any service method that writes kernel rows (promotion E10-S06, candidates E10-S04, versions E10-S05, experiments E10-S08); `versions/` folder (E10-S05); sharing `$WALK_HOME` as a git repository (ARCHITECTURE §9 "may", not planned).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/kernel_home.py` | create | `KernelHome`, `KernelConfig`, `WALK_HOME_ENV`, `DEFAULT_WALK_HOME`, `IMPROVEMENT_FOLDERS` |
| `src/walk/improvement/store.py` | create | `KernelImprovementStore`, `ProjectImprovementStore`, `store_for` |
| `src/walk/improvement/models.py` | modify | `ImprovementCandidate`, `Pattern`, `AntiPattern`, `Experiment` (DOMAIN-MODEL §4.14 verbatim; only those not yet defined by E02-S04/E04-S13/E07-S08) `(verify)` |
| `src/walk/improvement/repository.py` | modify | `CandidateRepository`, `PatternRepository`, `BehaviorVersionRepository`, `ExperimentRepository`, `ChangelogRepository` |
| `src/walk/improvement/__init__.py` | modify | re-exports of the above |
| `src/walk/persistence/migrations/kernel/0002_improvement_indexes.sql` | create | — |
| `src/walk/cli/composition.py` | modify | `KernelSettings.walk_home`, `KernelOverrides.kernel_home`, `KernelHandle.kernel_home` |
| `src/walk/cli/cmd_doctor.py` | modify | — (`improvement_home` section; `--fix` runs `KernelHome.ensure()`) `(verify DoctorReport location, E02-S15)` |
| `tests/conftest.py` | modify | `tmp_walk_home` fixture |
| `tests/improvement/test_kernel_home.py` | create | — |
| `tests/improvement/test_store.py` | create | — |
| `tests/improvement/test_repository_improvement_tables.py` | create | — |
| `tests/persistence/test_kernel_migrations.py` | create | — |
| `tests/cli/test_cmd_doctor_improvement_home.py` | create | — |

#### Interface contract
Layout: ARCHITECTURE §9. Tables: DOMAIN-MODEL §6.2 (improvement block and "Table → DB"). Models: DOMAIN-MODEL §4.14.
```python
# src/walk/improvement/kernel_home.py
WALK_HOME_ENV: str = "WALK_HOME"
DEFAULT_WALK_HOME: Path = Path("~/.walk")
IMPROVEMENT_FOLDERS: tuple[str, ...] = ("observations", "candidates", "experiments", "patterns",
                                         "anti-patterns", "retrospectives", "changelog")

class KernelConfig(WalkModel):
    """$WALK_HOME/config.yaml (ARCHITECTURE §9); missing file → defaults."""
    schema_version: int = 1
    maintainers: list[str] = Field(default_factory=list, description="§104 maintainers allowed to approve MEDIUM candidates as USER actors")

class KernelHome:
    def __init__(self, root: Path, clock: Clock) -> None: ...
    @classmethod
    def resolve(cls, explicit: Path | None, clock: Clock) -> "KernelHome":
        """explicit (KernelSettings.walk_home) > $WALK_HOME > DEFAULT_WALK_HOME; user-expanded, absolute."""
    @property
    def root(self) -> Path: ...
    @property
    def improvement_dir(self) -> Path: ...            # root / ".improvement"
    def folder(self, name: str) -> Path: ...           # name ∈ IMPROVEMENT_FOLDERS (E10-S05 adds "versions") else ConfigError
    async def ensure(self) -> None: ...                # mkdir -p folders; open + migrate kernel.db (MigrationRunner kind="kernel")
    async def database(self) -> Database: ...          # $WALK_HOME/kernel.db, WAL, busy_timeout 5000 ms
    async def ids(self) -> IdFactory: ...              # IdSequenceStore over the kernel DB
    def config(self) -> KernelConfig: ...
    def is_initialised(self) -> bool: ...

# src/walk/improvement/store.py
class KernelImprovementStore:
    def __init__(self, home: KernelHome, clock: Clock) -> None: ...
    async def write(self, folder: str, doc: MemoryDocument, *, actor: Actor) -> Path: ...
    async def read(self, folder: str, doc_id: str) -> MemoryDocument: ...
    async def list_ids(self, folder: str) -> list[str]: ...

class ProjectImprovementStore:
    def __init__(self, memory: MemoryManager) -> None: ...
    async def write(self, folder: str, doc: MemoryDocument, *, actor: Actor) -> Path: ...   # folder ignored: .ai/improvements/ is flat
    async def read(self, folder: str, doc_id: str) -> MemoryDocument: ...
    async def list_ids(self, folder: str) -> list[str]: ...

def store_for(scope: LearningScope, *, project: ProjectImprovementStore,
              kernel: KernelImprovementStore) -> KernelImprovementStore | ProjectImprovementStore: ...

# src/walk/improvement/repository.py — all take `db: Database`; rows per DOMAIN-MODEL §6.2, model JSON in `json`
class CandidateRepository:        # get, upsert, query(state, risk, scope, limit)
class PatternRepository:          # get, insert, query(kind: Literal["PATTERN","ANTI"], scope)
class BehaviorVersionRepository:  # get(kind, name, version), upsert, list(kind, name, stage)
class ExperimentRepository:       # get, upsert, query(candidate_id, open_only)     — kernel DB only
class ChangelogRepository:        # append(version, entry) -> entry_seq, entries(version | None)  — kernel DB only
```
`0002_improvement_indexes.sql` (kernel): `ix_candidates_state(state, risk)`, `ix_patterns_kind(kind, scope)`, `ix_bv_stage(kind, name, stage)`, `ix_experiments_candidate(candidate_id)`, `ix_changelog_candidate(candidate_id)` — `CREATE INDEX IF NOT EXISTS` only.

#### Behavior
1. `KernelHome.resolve` precedence: explicit argument, then the `WALK_HOME` environment variable, then `~/.walk`; the result is absolute; the variable is read only here (it is not a secret, CONVENTIONS §2 secrets rule unaffected).
2. `ensure()` is idempotent: creates `.improvement/` and every `IMPROVEMENT_FOLDERS` entry, creates/migrates `kernel.db` to the latest kernel migration (`0001_init`, `0002_improvement_indexes`), and never deletes or rewrites existing files.
3. `config()` parses `config.yaml` when present; unknown keys or wrong types → `ConfigError` naming the file; missing file → `KernelConfig()` defaults.
4. `KernelImprovementStore.write` validates front matter with `FrontMatter` (ARCHITECTURE §8.2), requires `doc.id` to equal the file stem, refuses secrets (`find_secrets`, E01-S16 → `SecretDetected`), bumps `version`, stamps `updated_at`/`updated_by`, and writes with `walk.persistence.atomic_write` to `folder(name)/<id>.md`. No `freshness` commit stamp (kernel documents are not tied to a game repo HEAD).
5. `ProjectImprovementStore` delegates to `MemoryManager.write`/`read` under `improvements/` (ADR-0003 D-4); it never touches `$WALK_HOME`.
6. `store_for(PROJECT)` returns the project store, `store_for(KERNEL)` the kernel store; the mapping is the single place deciding the document location (Scope/store rule of this epic).
7. Kernel ids: `ids()` allocates `OBS-K-` (width 4), `IMP-` (2), `PATTERN-`/`ANTI-` (3), `EXP-` (4) from the kernel `id_sequences` (DOMAIN-MODEL §2); project ids keep using the project `IdSequenceStore`.
8. `ExperimentRepository` and `ChangelogRepository` constructed on a database without their table raise `ConfigError("<table> exists only in the kernel DB")` on first use.
9. `walk doctor` prints section `improvement_home` with `path`, `initialised`, `writable`, `kernel_db_version`, `folders_missing`; a missing home is a warning (exit unaffected) unless `--strict`; `walk doctor --fix` calls `ensure()`.
10. Kernel startup (`build_kernel`) resolves the home but does not create it; the first story that writes kernel scope (E10-S04/S06) calls `ensure()`.
11. Fixture `tmp_walk_home` points `WALK_HOME` at a pytest temp directory and yields an initialised `KernelHome`; tests never touch the real `~/.walk`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `WALK_HOME` set and an explicit path When `resolve` Then the explicit path wins; given only the variable Then the variable; given neither Then `~/.walk` expanded | `tests/improvement/test_kernel_home.py::test_resolve_precedence` |
| 2 | Given an empty temp home When `ensure()` twice Then the seven folders and `kernel.db` exist and `schema_migrations` lists `0001` and `0002` once each | `tests/improvement/test_kernel_home.py::test_ensure_idempotent_creates_layout` |
| 3 | Given `config.yaml` with `maintainers: [alice]` When `config()` Then `maintainers == ["alice"]`; given an unknown key Then `ConfigError` | `tests/improvement/test_kernel_home.py::test_config_parse_and_reject_unknown` |
| 4 | Given `folder("bogus")` Then `ConfigError` | `tests/improvement/test_kernel_home.py::test_unknown_folder_rejected` |
| 5 | Given a candidate document When `KernelImprovementStore.write("candidates", doc)` Then `$WALK_HOME/.improvement/candidates/IMP-01.md` exists, front matter valid, version 1, and a second write gives version 2 | `tests/improvement/test_store.py::test_kernel_store_write_versions` |
| 6 | Given a document containing an API-key pattern When written to the kernel store Then `SecretDetected` and no file | `tests/improvement/test_store.py::test_kernel_store_rejects_secrets` |
| 7 | Given a document whose id differs from the target stem When written Then `ConfigError` | `tests/improvement/test_store.py::test_kernel_store_id_must_match_stem` |
| 8 | Given `store_for(PROJECT)` When writing `PATTERN-001` Then the file is `.ai/improvements/PATTERN-001.md` via `MemoryManager.write` and `$WALK_HOME` is unchanged | `tests/improvement/test_store.py::test_store_for_project_writes_ai_only` |
| 9 | Given the kernel `IdFactory` When allocating `OBS-K`, `IMP`, `PATTERN`, `EXP` Then `OBS-K-0001`, `IMP-01`, `PATTERN-001`, `EXP-0001` | `tests/improvement/test_kernel_home.py::test_kernel_id_allocation_widths` |
| 10 | Given a candidate, a pattern and a behavior version When upserted and read back on both DBs Then equal models | `tests/improvement/test_repository_improvement_tables.py::test_roundtrip_project_and_kernel_tables` |
| 11 | Given an `ExperimentRepository` on the project DB When used Then `ConfigError` naming `experiments` | `tests/improvement/test_repository_improvement_tables.py::test_kernel_only_tables_rejected_on_project_db` |
| 12 | Given `ChangelogRepository.append("0.9.0", …)` twice When `entries("0.9.0")` Then `entry_seq` 1 and 2 in order | `tests/improvement/test_repository_improvement_tables.py::test_changelog_entry_seq_increments` |
| 13 | Given the kernel migrations When applied to an empty DB Then the five indexes exist and the migration is `CREATE INDEX IF NOT EXISTS` only | `tests/persistence/test_kernel_migrations.py::test_kernel_0002_creates_indexes_only` |
| 14 | Given an uninitialised home When `walk doctor --json` Then `improvement_home.initialised == false` and exit 0; after `walk doctor --fix` Then `initialised == true` | `tests/cli/test_cmd_doctor_improvement_home.py::test_doctor_reports_and_fixes_home` |

#### Evidence required
- Quality gate output.
- Demo: `WALK_HOME=<tmp> walk doctor --fix` then `walk doctor --json` (section `improvement_home`), `ls -R <tmp>/.improvement`, `sqlite3 <tmp>/kernel.db "select version from schema_migrations"`.

#### Notes
- ADR-0008 D-1 (two stores, same models, different id prefixes); ARCHITECTURE §9 (layout), §6 (secret scan); DOMAIN-MODEL §6.2 "Table → DB"; ADR-0002 (SQLite, WAL).
- Several kernel instances (one per game repo) may share `kernel.db`; correctness relies on SQLite WAL + `busy_timeout` and short `BEGIN IMMEDIATE` transactions, not on `KernelLock` (which is per project).
- The improvement package may import `persistence`, `memory`, `telemetry` (ARCHITECTURE §2.2); it never imports `runtime`, `orchestrator`, `permissions`, `tools`, `integrations`.
- `NEW NAME:` module `walk.improvement.kernel_home` (`KernelHome`, `KernelConfig`, `WALK_HOME_ENV`, `DEFAULT_WALK_HOME`, `IMPROVEMENT_FOLDERS`); module `walk.improvement.store` (`KernelImprovementStore`, `ProjectImprovementStore`, `store_for`); `CandidateRepository`, `PatternRepository`, `BehaviorVersionRepository`, `ExperimentRepository`, `ChangelogRepository`; kernel migration `0002_improvement_indexes.sql`; `KernelSettings.walk_home`; `KernelOverrides.kernel_home`; `KernelHandle.kernel_home`; `KernelConfig.maintainers`; `walk doctor` section `improvement_home`; fixture `tmp_walk_home`.
- Commit subject: `feat: add kernel improvement home and store (E10-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S04 — Candidates and risk-tier review, `walk improvement candidates`

**Status:** TODO
**Type:** feat
**Requirements:** §97, §98, §102, §103, §104, §106, §110, §44 (`PROCESS`), §137 (Inv. 5, 13)
**Depends on:** E10-S03, E05-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Improvement candidates follow the §97 lifecycle as a data table, carry every §98 field as a `.md` document in the scope's store, can only be submitted with §102 evidence appropriate to their risk, and are approved or rejected exclusively by the §104 authority tier — producing a `PROCESS` decision and an `IMPROVEMENT` approval request trail — while agents can propose and (within tier) review only through two kernel tools, never by editing behaviour files (§103).

#### Scope
- In: module `walk.improvement.candidates` (transition table, tiers, risk floors, evidence levels, `candidate_from_observations`); `CandidateQuery`; `CANDIDATE_SECTIONS`; candidate documents; `create_candidate`, `candidate_event`, `review_candidate`, `list_candidates`; `ImprovementApprovalSink` wiring to `PermissionManager.request_approval`; KERNEL tools `improvement.candidate` / `improvement.review` (spec, permission rows, handlers); `walk approve` routing for `IMPROVEMENT` requests; `walk improvement candidates list/new/event/review` and `show IMP-NN`.
- Out: turning an approved candidate into a `BehaviorVersion` (E10-S05); experiments (E10-S08 sets `experiment_id`); patch files for proposed changes (ADR-0008 D-7 — `proposed_change` is text in this story; E10-S05 reads the artefact file given at registration); promotion of observations (E10-S06).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/candidates.py` | create | `CandidateEvent`, `CANDIDATE_TRANSITIONS`, `APPROVER_TIERS`, `RISK_FLOOR`, `CandidateEvidenceLevel`, `MIN_EVIDENCE_FOR_RISK`, `effective_risk`, `evidence_level`, `can_approve`, `candidate_from_observations`, `ImprovementApprovalSink` |
| `src/walk/improvement/models.py` | modify | `CandidateQuery` |
| `src/walk/improvement/documents.py` | modify | `candidate_document`, `candidate_from_document` |
| `src/walk/memory/sections.py` | modify | `CANDIDATE_SECTIONS` |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.candidate_event`, `ImprovementManager.list_candidates` |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.create_candidate`, `.candidate_event`, `.review_candidate`, `.list_candidates`; `__init__` (`kernel_home`, `kernel_store`, `project_store`, `decisions`, `approvals: ImprovementApprovalSink`) |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/tools/defaults/tools.yaml` | modify | — (`improvement.candidate`, `improvement.review`: kind `KERNEL`, provider `improvement`) |
| `src/walk/permissions/defaults.yaml` | modify | — (rows in the table below) |
| `src/walk/orchestrator/improvement_tools.py` | create | `improvement_tool_handlers`, `PermissionApprovalSink` |
| `src/walk/orchestrator/commands.py` | modify | — (`approve`/`deny` of an `IMPROVEMENT` request calls `review_candidate`) `(verify E02-S11)` |
| `src/walk/cli/composition.py` | modify | — (wires stores, decisions, `PermissionApprovalSink`; registers the two handlers with `ToolInvoker.register_handler`) |
| `src/walk/cli/cmd_improvement.py` | modify | `candidates_app` (`list`, `new`, `event`, `review`); `show` accepts `IMP-` |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 `candidate_event`, `list_candidates`; §6 `walk improvement candidates …` sub-commands) |
| `tests/improvement/test_candidates_table.py` | create | — |
| `tests/improvement/test_candidates_tiers.py` | create | — |
| `tests/improvement/test_documents_candidate.py` | create | — |
| `tests/improvement/test_service_candidates.py` | create | — |
| `tests/orchestrator/test_improvement_tools.py` | create | — |
| `tests/permissions/test_defaults_improvement_tools.py` | create | — |
| `tests/cli/test_cmd_improvement_candidates.py` | create | — |

#### Interface contract
`create_candidate`, `review_candidate` per INTERFACES §1.15; `ImprovementCandidate` per DOMAIN-MODEL §4.14; `CandidateState`, `ImprovementRisk` per DOMAIN-MODEL §3; `ApprovalRequest.kind == "IMPROVEMENT"` per DOMAIN-MODEL §4.5.
```python
# src/walk/improvement/candidates.py
class CandidateEvent(StrEnum):
    HYPOTHESIZE = "hypothesize"   # OBSERVATION  → HYPOTHESIS
    PROPOSE = "propose"           # HYPOTHESIS   → CANDIDATE     (all §98 fields non-empty)
    SUBMIT = "submit"             # CANDIDATE    → UNDER_REVIEW  (evidence level ≥ MIN_EVIDENCE_FOR_RISK[risk])
    APPROVE = "approve"           # UNDER_REVIEW → APPROVED      (review_candidate only)
    REJECT = "reject"             # UNDER_REVIEW → REJECTED      (review_candidate only)
    REVISE = "revise"             # REJECTED     → HYPOTHESIS

CANDIDATE_TRANSITIONS: dict[tuple[CandidateState, CandidateEvent], CandidateState]

APPROVER_TIERS: dict[ImprovementRisk, frozenset[AgentRole]] = {
    ImprovementRisk.LOW: frozenset({AgentRole.ORCHESTRATOR, AgentRole.PRODUCT_OWNER, AgentRole.USER}),
    ImprovementRisk.MEDIUM: frozenset({AgentRole.PRODUCT_OWNER, AgentRole.USER}),
    ImprovementRisk.HIGH: frozenset({AgentRole.USER}),
}
RISK_FLOOR: dict[ImprovementScope, ImprovementRisk] = {
    PROMPT: LOW, CONTEXT_FORMAT: MEDIUM, HOOK: MEDIUM, SKILL: MEDIUM, MODEL_ROUTING: MEDIUM, EFFORT_POLICY: MEDIUM,
    WORKFLOW: MEDIUM, STORY_TEMPLATE: MEDIUM, CONSTITUTION: HIGH, QUALITY_GATE: HIGH, TOOL_USAGE: HIGH,
}   # §104: skills/routing/workflow step/DoR = MEDIUM; agent authority/phase gate/permissions = HIGH

class CandidateEvidenceLevel(IntEnum):     # §102 order, higher = stronger
    PREFERENCE = 0
    AGENT_RECOMMENDATION = 1
    SINGLE_PROJECT = 2
    CONTROLLED_COMPARISON = 3
    REPEATED_PRODUCTION = 4

MIN_EVIDENCE_FOR_RISK: dict[ImprovementRisk, CandidateEvidenceLevel] = {
    LOW: AGENT_RECOMMENDATION, MEDIUM: SINGLE_PROJECT, HIGH: CONTROLLED_COMPARISON,
}

def effective_risk(declared: ImprovementRisk, components: list[ImprovementScope]) -> ImprovementRisk: ...
def evidence_level(candidate: ImprovementCandidate, observations: list[ImprovementObservation],
                   experiment: Experiment | None) -> CandidateEvidenceLevel: ...
def can_approve(risk: ImprovementRisk, by: Actor, scope: LearningScope, config: KernelConfig) -> bool: ...
def candidate_from_observations(observations: list[ImprovementObservation], *, risk: ImprovementRisk, problem: str | None,
                                proposed_change: str, expected_benefit: str, validation_method: str,
                                scope: LearningScope) -> ImprovementCandidate: ...   # id="IMP-00" placeholder, state HYPOTHESIS

class ImprovementApprovalSink(Protocol):
    async def request(self, candidate: ImprovementCandidate, approver: Approver) -> ApprovalRequestId: ...
    async def resolve_for(self, candidate_id: ImprovementId, approve: bool, *, by: str, note: str) -> None: ...

# src/walk/improvement/models.py
class CandidateQuery(WalkModel):
    ids: list[ImprovementId] | None = None
    scope: LearningScope | None = None
    state: CandidateState | None = None
    risk: ImprovementRisk | None = None
    limit: int = Field(default=100, ge=1, le=1000)

# src/walk/memory/sections.py
CANDIDATE_SECTIONS = ("Problem", "Evidence", "Frequency", "Impact", "Suspected Cause", "Proposed Change",
                      "Expected Benefit", "Risk", "Affected Components", "Validation Method")    # §98 verbatim order

# src/walk/improvement/protocols.py — additions
async def candidate_event(self, candidate_id: ImprovementId, event: CandidateEvent, *, by: Actor, note: str = "") -> ImprovementCandidate: ...
async def list_candidates(self, query: CandidateQuery) -> list[ImprovementCandidate]: ...

# src/walk/orchestrator/improvement_tools.py
def improvement_tool_handlers(improvement: ImprovementManager) -> dict[ToolName, KernelToolHandler]: ...
class PermissionApprovalSink:      # implements ImprovementApprovalSink over PermissionManager
    def __init__(self, permissions: PermissionManager) -> None: ...
```
Tool arguments: `improvement.candidate {observation_ids: [..], risk, problem?, proposed_change, expected_benefit, validation_method, scope?}` → `{id, state}`; `improvement.review {candidate_id, approve: bool, note}` → `{id, state, decision_id}`.

`permissions/defaults.yaml` rows added:

| role | tool | effect |
|---|---|---|
| PROCESS_ARCHITECT, ORCHESTRATOR, PRODUCT_OWNER, LEAD_DEV | `improvement.candidate` | ALLOW |
| ORCHESTRATOR, PRODUCT_OWNER | `improvement.review` | ALLOW |
| `*` | `improvement.review` | DENY |

CLI: `walk improvement candidates list [--state S] [--risk R] [--scope PROJECT|KERNEL] [--json]`; `walk improvement candidates new --from OBS_ID... --risk R --proposed-change TEXT --expected-benefit TEXT --validation-method TEXT [--problem TEXT] [--scope KERNEL]`; `walk improvement candidates event IMP_ID EVENT [--note TEXT]`; `walk improvement candidates review IMP_ID (--approve|--reject) --note TEXT`.

#### Behavior
1. `create_candidate` accepts states `OBSERVATION`, `HYPOTHESIS`, `CANDIDATE` only (else `ConfigError`); calls `KernelHome.ensure()`; allocates `IMP-NN` from the kernel `id_sequences` for both scopes (DOMAIN-MODEL §2); sets `risk = effective_risk(risk, affected_components)`; persists the row in the scope's DB (`CandidateRepository`), writes `candidate_document` through `store_for(scope)` (`$WALK_HOME/.improvement/candidates/IMP-NN.md` or `.ai/improvements/IMP-NN.md`); ledger `IMPROVEMENT_CANDIDATE{id, scope, state, risk, observation_ids, evidence_ids}` on the project ledger.
2. Scope rule (§110): every referenced observation must have the candidate's scope (a `KERNEL` candidate references only `OBS-K-` observations); otherwise `ConfigError("observation <id> is <scope>")`.
3. `candidate_event` applies `CANDIDATE_TRANSITIONS`; an undefined `(state, event)` pair, or `APPROVE`/`REJECT` through this method, raises `GuardRejected`. `PROPOSE` requires all ten §98 fields non-empty (`GuardRejected` naming the first empty one). Each transition rewrites the document (`status` = state) and writes an `IMPROVEMENT_CANDIDATE` event with `from_state`, `to_state`, `event`, `by_role`.
4. `SUBMIT` requires `evidence_level(candidate, observations, experiment) >= MIN_EVIDENCE_FOR_RISK[risk]` (`GuardRejected` naming both levels). Levels: `REPEATED_PRODUCTION` = observations from ≥ 2 distinct `origin_project`; `CONTROLLED_COMPARISON` = linked experiment ended with non-empty `result_evidence_ids`; `SINGLE_PROJECT` = any non-`agent` observation with `ledger_seq_refs`, or any `evidence_ids`; `AGENT_RECOMMENDATION` = only `agent` observations; `PREFERENCE` = none of these. A `PREFERENCE` candidate can never be submitted (§102 "not only because it seems better").
5. On `SUBMIT` for `MEDIUM` and `HIGH`, the service calls `approvals.request(candidate, Approver.PRODUCT_OWNER | Approver.USER)` so the request appears in `walk approvals`; `LOW` creates no approval request.
6. `review_candidate(id, approve, by, note)`: state must be `UNDER_REVIEW` (`GuardRejected`); `can_approve(risk, by, scope, config)` must hold (`PermissionDenied` naming the tier) — `by.role ∈ APPROVER_TIERS[risk]`, and for `scope == KERNEL` with non-empty `KernelConfig.maintainers`, a `USER` approver's name must be listed; `note` non-empty (`ConfigError`). It records a `DecisionCategory.PROCESS` decision through `DecisionManager.record` (owner `by.role`, outcome `approve`/`reject` + candidate id, rationale `note`, evidence ids = candidate evidence) and stores `decision_id`; transitions to `APPROVED`/`REJECTED`; calls `approvals.resolve_for(...)`; ledger `IMPROVEMENT_CANDIDATE{to_state, decision_id, approver_role, risk}`.
7. `walk approve APV-… --note` / `walk deny` on an `IMPROVEMENT` request route to `review_candidate(candidate_id, approve, by=Actor(role=USER, …), note)`; a denial of a `HIGH` request by anyone else is impossible (approver USER, E02-S11).
8. Tool `improvement.candidate`: the handler builds the candidate with `candidate_from_observations`, forces `scope=PROJECT` unless the caller role is `PROCESS_ARCHITECT`, then `create_candidate` and, when all §98 fields are present, `candidate_event(PROPOSE)`. Tool `improvement.review` calls `review_candidate(by=Actor(role=<run role>, run_id=…))` — an ORCHESTRATOR call on a MEDIUM candidate therefore fails with `PermissionDenied` from the tier check even though the tool itself is allowed.
9. No code path in this story writes a behaviour artefact (constitution, table, skill, template, policy); agent runs cannot change a candidate except through the two tools (§103, Inv. 13).
10. `list_candidates` merges project-DB and kernel-DB rows when `scope` is `None`, ordered by `created_at DESC, id DESC`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `CANDIDATE_TRANSITIONS` When enumerated Then exactly the six transitions of the contract exist and every `CandidateState` is reachable from `OBSERVATION` | `tests/improvement/test_candidates_table.py::test_transition_table_matches_section_97` |
| 2 | Given declared risk LOW and components `[CONSTITUTION]` When `effective_risk` Then HIGH; given `[PROMPT]` Then LOW | `tests/improvement/test_candidates_tiers.py::test_effective_risk_applies_floor` |
| 3 | Given risk MEDIUM When `can_approve` for ORCHESTRATOR, PRODUCT_OWNER, USER Then false, true, true; risk HIGH Then only USER | `tests/improvement/test_candidates_tiers.py::test_approver_tiers_match_section_104` |
| 4 | Given a KERNEL candidate and `maintainers: [alice]` When USER `bob` approves Then `can_approve` false; `alice` Then true | `tests/improvement/test_candidates_tiers.py::test_kernel_scope_requires_listed_maintainer` |
| 5 | Given observations from 2 projects / one ledger-detected / agent-only / none When `evidence_level` Then REPEATED_PRODUCTION / SINGLE_PROJECT / AGENT_RECOMMENDATION / PREFERENCE | `tests/improvement/test_candidates_tiers.py::test_evidence_levels_follow_section_102` |
| 6 | Given a candidate with all §98 fields When `candidate_document` then `candidate_from_document` Then equal, and sections equal `CANDIDATE_SECTIONS` | `tests/improvement/test_documents_candidate.py::test_candidate_document_roundtrip` |
| 7 | Given two PROJECT observations When `create_candidate` (scope PROJECT) Then id `IMP-01` from the kernel sequence, row in the project DB, `.ai/improvements/IMP-01.md` written, `IMPROVEMENT_CANDIDATE` event on the project ledger | `tests/improvement/test_service_candidates.py::test_create_project_candidate` |
| 8 | Given a PROJECT observation When creating a KERNEL candidate from it Then `ConfigError` | `tests/improvement/test_service_candidates.py::test_kernel_candidate_rejects_project_observation` |
| 9 | Given a HYPOTHESIS candidate with empty `validation_method` When `PROPOSE` Then `GuardRejected` naming `validation_method` | `tests/improvement/test_service_candidates.py::test_propose_requires_all_section_98_fields` |
| 10 | Given a MEDIUM candidate backed only by agent observations When `SUBMIT` Then `GuardRejected` naming `AGENT_RECOMMENDATION < SINGLE_PROJECT` | `tests/improvement/test_service_candidates.py::test_submit_requires_evidence_for_risk` |
| 11 | Given a MEDIUM candidate with a ledger-detected observation When `SUBMIT` Then `UNDER_REVIEW` and one PENDING `ApprovalRequest(kind="IMPROVEMENT", approver=PRODUCT_OWNER)` | `tests/improvement/test_service_candidates.py::test_submit_medium_creates_approval_request` |
| 12 | Given an UNDER_REVIEW MEDIUM candidate When PRODUCT_OWNER `review_candidate(approve=True, note)` Then `APPROVED`, a PROCESS decision `ACCEPTED` linked by `decision_id`, the approval request APPROVED, ledger `IMPROVEMENT_CANDIDATE` with `approver_role` | `tests/improvement/test_service_candidates.py::test_review_medium_by_po_records_process_decision` |
| 13 | Given an UNDER_REVIEW HIGH candidate When PRODUCT_OWNER reviews Then `PermissionDenied` and state unchanged | `tests/improvement/test_service_candidates.py::test_review_high_requires_user` |
| 14 | Given `candidate_event(APPROVE)` Then `GuardRejected` | `tests/improvement/test_service_candidates.py::test_approve_only_via_review` |
| 15 | Given a fake SENIOR_DEV run calling `improvement.candidate` with `scope: KERNEL` When handled Then the created candidate has scope PROJECT | `tests/orchestrator/test_improvement_tools.py::test_candidate_tool_forces_project_scope_for_non_pa` |
| 16 | Given an ORCHESTRATOR run calling `improvement.review` on a MEDIUM candidate When handled Then the tool result is an error `PermissionDenied` and no decision is recorded | `tests/orchestrator/test_improvement_tools.py::test_review_tool_enforces_tier` |
| 17 | Given the default rules When `decide(QC, improvement.review)` Then DENY; `decide(PRODUCT_OWNER, improvement.review)` Then ALLOW; `decide(PROCESS_ARCHITECT, improvement.candidate)` Then ALLOW | `tests/permissions/test_defaults_improvement_tools.py::test_improvement_tool_rules` |
| 18 | Given a pending IMPROVEMENT approval When `walk approve APV-0001 --note ok` Then the candidate is APPROVED by `USER` | `tests/cli/test_cmd_improvement_candidates.py::test_walk_approve_routes_to_review` |
| 19 | Given `walk improvement candidates new --from OBS-0001 --risk LOW …` then `event IMP-01 propose`, `event IMP-01 submit`, `review IMP-01 --approve --note ok` Then exit 0 each and `candidates list --state APPROVED --json` has IMP-01 | `tests/cli/test_cmd_improvement_candidates.py::test_candidate_cli_lifecycle` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `walk improvement candidates new --from OBS-0001 --risk MEDIUM …`, `walk improvement candidates event IMP-01 submit`, `walk approvals --pending`, `walk improvement candidates review IMP-01 --approve --note "PO review"` (as configured PO actor) or `walk approve APV-…`, `walk improvement show IMP-01`, `walk ledger query --kind IMPROVEMENT_CANDIDATE`.

#### Notes
- ADR-0008 D-6 (tiers), D-7 (agents cannot write behaviour; proposals are data); Invariant 5 (only `DecisionManager.record` makes an `ACCEPTED` decision), Invariant 13; ARCHITECTURE §4.2 (KERNEL tools enforced at `ToolInvoker`), §2.2 (improvement may not import `permissions`/`tools`/`runtime`, hence the handlers and `PermissionApprovalSink` live in `walk.orchestrator`).
- `RISK_FLOOR` and `MIN_EVIDENCE_FOR_RISK` are planning decisions derived from §102/§104; changing them is itself a `QUALITY_GATE` improvement.
- The INTERFACES §6 row `walk improvement candidates` becomes a sub-command group; update INTERFACES §6 and §1.15 in the same commit (CONVENTIONS §4).
- `NEW NAME:` module `walk.improvement.candidates` (`CandidateEvent`, `CANDIDATE_TRANSITIONS`, `APPROVER_TIERS`, `RISK_FLOOR`, `CandidateEvidenceLevel`, `MIN_EVIDENCE_FOR_RISK`, `effective_risk`, `evidence_level`, `can_approve`, `candidate_from_observations`, `ImprovementApprovalSink`); `CandidateQuery`; `CANDIDATE_SECTIONS`; `candidate_document`, `candidate_from_document`; `ImprovementManager.candidate_event/list_candidates`; KERNEL tools `improvement.candidate`, `improvement.review` (provider `improvement`); module `walk.orchestrator.improvement_tools` (`improvement_tool_handlers`, `PermissionApprovalSink`); `walk improvement candidates list/new/event/review`.
- Commit subject: `feat: add improvement candidates with risk-tier review (E10-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S05 — `BehaviorVersion` registry, `rollout_workflow`, pins, changelog

**Status:** TODO
**Type:** feat
**Requirements:** §105, §109, §120, §121, §103, §104, §106, §82, §137 (Inv. 13)
**Depends on:** E10-S04, E02-S04
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An approved candidate can become a registered, content-hashed `BehaviorVersion` that moves through the INTERFACES §3.7 rollout table (DRAFT → EXPERIMENTAL → LIMITED → DEFAULT → DEPRECATED, rollback to DRAFT) under data-declared guards, every LIMITED/DEFAULT step produces a §120 changelog entry, projects opt in by pinning a version (an authority-tiered decision), and the kernel actually loads a pinned registered `WORKFLOW` table — so every behaviour change is evidence-based, versioned, auditable, measurable and reversible (§121).

#### Scope
- In: `rollout_workflow.yaml`; module `walk.improvement.rollout` (engine, guards, payload, metrics check); module `walk.improvement.changelog`; `ChangelogRequired`; `$WALK_HOME/.improvement/versions/` artefact folder; `BehaviorVersionCatalog.resolve/entries` over builtin + registered versions; stage-aware `KernelVersionPins.validate`; `register_version`, `set_stage`, `rollback`, `list_versions`, `pin_version`; `PIN_RISK_BY_KIND`; pinned-table loading for `WORKFLOW`; CLI `walk improvement versions/register/stage/pin/rollback`.
- Out: experiment assignment and shadow evaluation (E10-S08 — this story only checks that an experiment is defined and has result evidence); §116 version outcome reporting (E10-S09); loading registered (non-builtin) versions of kinds other than `WORKFLOW` — a pin to such a version fails at startup with `ConfigError("registered <KIND> versions are not loadable yet")` (follow-up candidate, not planned in E10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/tables/rollout_workflow.yaml` | create | — (INTERFACES §3.7 rows with the guard names below; `version: "1.0"`) |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.__init__` (`table_source: Callable[[str], Path] \| None`) `(verify table loader location, E01-S09)` |
| `src/walk/improvement/rollout.py` | create | `RolloutStateMachine`, `ROLLOUT_GUARDS`, `rollout_event_for`, `rollout_payload`, `VersionMetricsCheck`, `RetrospectiveMetricsCheck`, `METRICS_TOLERANCE` |
| `src/walk/improvement/changelog.py` | create | `ChangelogEntry`, `render_changelog`, `changelog_path` |
| `src/walk/improvement/errors.py` | modify | `ChangelogRequired` |
| `src/walk/improvement/versions.py` | modify | `BehaviorVersionCatalog.resolve`, `BehaviorVersionCatalog.entries`, `KernelVersionPins.validate` (stage-aware), `PIN_RISK_BY_KIND` |
| `src/walk/improvement/kernel_home.py` | modify | `IMPROVEMENT_FOLDERS` (+ `versions`) |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.set_stage` (`by` keyword), `.rollback`, `.list_versions`, `.pin_version` |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.register_version`, `.set_stage`, `.rollback`, `.list_versions`, `.pin_version` |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/cli/cmd_improvement.py` | modify | `versions`, `register`, `stage`, `pin`, `rollback` |
| `src/walk/cli/composition.py` | modify | — (catalog over builtin + kernel home; `table_source` from pins via `catalog.resolve`; `RetrospectiveMetricsCheck`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 new/changed methods; §3.7 guard registry names; §6 CLI rows) |
| `tests/improvement/test_rollout_table.py` | create | — |
| `tests/improvement/test_rollout_guards.py` | create | — |
| `tests/improvement/test_changelog.py` | create | — |
| `tests/improvement/test_versions_registered.py` | create | — |
| `tests/improvement/test_service_register_version.py` | create | — |
| `tests/improvement/test_service_pin_rollback.py` | create | — |
| `tests/workflow/test_service_table_source.py` | create | — |
| `tests/cli/test_cmd_improvement_versions.py` | create | — |

#### Interface contract
Rollout table: INTERFACES §3.7. `BehaviorVersion`, `RolloutStage`: DOMAIN-MODEL §4.14/§3. Version folder: `$WALK_HOME/.improvement/versions/<KIND>/<name>/<version>.<ext>` (`ext` of the source file).

`rollout_workflow.yaml` guard names (registry names, WBS §3.4 style):

| From | Event | Guards | To |
|---|---|---|---|
| DRAFT | `experiment` | `candidate_approved`, `experiment_defined_or_shadow` | EXPERIMENTAL |
| EXPERIMENTAL | `limited` | `experiment_evidence_present`, `approver_in_risk_tier`, `changelog_entry_present` | LIMITED |
| LIMITED | `default` | `ran_through_phase`, `metrics_not_worse`, `changelog_entry_present`, `approver_in_risk_tier` | DEFAULT |
| DEFAULT | `deprecate` | `successor_default_exists` | DEPRECATED |
| EXPERIMENTAL, LIMITED | `rollback` | — | DRAFT |

Payload keys (`TransitionContext.payload`, built by `rollout_payload`): `candidate_state`, `experiment_defined`, `shadow`, `experiment_evidence_count`, `approver_role`, `risk`, `projects_ran_phase`, `metrics_not_worse`, `changelog_entry_present`, `successor_default_exists`.
```python
# src/walk/improvement/rollout.py
ROLLOUT_GUARDS: dict[str, Callable[[BehaviorVersion, TransitionContext], GuardResult]]
METRICS_TOLERANCE: float = 0.10

def rollout_event_for(current: RolloutStage, target: RolloutStage) -> str: ...      # undefined pair → GuardRejected

class VersionMetricsCheck(Protocol):
    async def not_worse(self, version: BehaviorVersion) -> tuple[bool, str]: ...    # (verdict, reason)

class RetrospectiveMetricsCheck:
    def __init__(self, telemetry: TelemetryManager, ledger: LedgerManager) -> None: ...
    async def not_worse(self, version: BehaviorVersion) -> tuple[bool, str]: ...

async def rollout_payload(version: BehaviorVersion, *, by: Actor, candidates: CandidateRepository, experiments: ExperimentRepository,
                          changelog: ChangelogRepository, ledger: LedgerManager, metrics: VersionMetricsCheck,
                          catalog: BehaviorVersionCatalog) -> JsonDict: ...

class RolloutStateMachine:
    def __init__(self, table: TransitionTable, guards: dict[str, Callable[..., GuardResult]] = ROLLOUT_GUARDS) -> None: ...
    def fire(self, version: BehaviorVersion, event: str, ctx: TransitionContext) -> BehaviorVersion: ...   # pure; GuardRejected lists failing guards

# src/walk/improvement/changelog.py
class ChangelogEntry(FrozenModel):
    release: str              # kernel release, e.g. "0.9.0" (walk.__version__)
    entry_seq: int
    key: str                  # "<KIND>/<name>"
    version: str
    stage: RolloutStage
    changed: str
    reason: ImprovementId
    evidence: str             # summary + evidence ids
    at: datetime
def render_changelog(release: str, entries: list[ChangelogEntry]) -> str: ...   # §120 layout: "Kernel <release>", then per entry Changed / Reason / Evidence
def changelog_path(home: KernelHome, release: str) -> Path: ...                 # .improvement/changelog/<release>.md

# src/walk/improvement/errors.py
class ChangelogRequired(PermanentError): ...

# src/walk/improvement/versions.py
PIN_RISK_BY_KIND: dict[ImprovementScope, ImprovementRisk]   # WORKFLOW, CONSTITUTION, TOOL_USAGE, QUALITY_GATE → HIGH; all others → MEDIUM (ADR-0008 D-4)
class BehaviorVersionCatalog:
    def entries(self) -> list[BehaviorVersion]: ...                               # builtin (DEFAULT) + registered (kernel DB stage)
    def resolve(self, key: str, version: str) -> tuple[BehaviorVersion, Path]: ...  # ConfigError when unknown

# src/walk/improvement/protocols.py — ImprovementManager changes/additions
async def set_stage(self, kind: ImprovementScope, name: str, version: str, stage: RolloutStage, *, by: Actor, changed: str = "") -> BehaviorVersion: ...
async def rollback(self, kind: ImprovementScope, name: str, version: str, *, by: Actor, reason: str) -> BehaviorVersion: ...
async def list_versions(self, kind: ImprovementScope | None = None, name: str | None = None) -> list[BehaviorVersion]: ...
async def pin_version(self, kind: ImprovementScope, name: str, version: str, *, by: Actor, note: str) -> KernelVersionPins: ...
```
CLI: `walk improvement versions [--kind K] [--name N] [--json]`; `walk improvement register KIND/NAME VERSION --source PATH --candidate IMP_ID [--stage STAGE] [--changed TEXT]`; `walk improvement stage KIND/NAME VERSION STAGE [--changed TEXT]`; `walk improvement pin KIND/NAME VERSION --note TEXT`; `walk improvement rollback KIND/NAME VERSION --reason TEXT`.

#### Behavior
1. `register_version(v)`: `v.candidate_id` must reference an `APPROVED` candidate (`GuardRejected` otherwise — Inv. 13); `v.version` must match `^\d+\.\d+$` and be greater than every known version of the same key; a MAJOR bump requires the candidate's risk to be `HIGH` (ADR-0008 D-3); the file at `v.source_path` is validated per kind (WORKFLOW: loads as `TransitionTable` and its `version` equals `v.version`; other kinds: the E02-S04 version marker equals `v.version`), copied to the versions folder, `content_sha256` recomputed; the row is inserted in the kernel DB at `DRAFT`; ledger `BEHAVIOR_VERSION_CHANGED{key, version, from_stage: null, to_stage: DRAFT, candidate_id}`; the candidate's `resulting_behavior_version` is set to `"<key> <version>"`.
2. When `v.stage` is above `DRAFT`, `register_version` then applies `set_stage` step by step (`experiment`, `limited`, `default`) inside one kernel-DB transaction; if any guard rejects, nothing (row, file copy, changelog, events) is persisted.
3. `set_stage` builds the payload with `rollout_payload`, fires the event chosen by `rollout_event_for`, persists the new stage, writes `BEHAVIOR_VERSION_CHANGED{key, version, from_stage, to_stage, event, by_role, changelog_release}`. Guard semantics: `candidate_approved` ⇔ `candidate_state == APPROVED`; `experiment_defined_or_shadow` ⇔ `experiment_defined or shadow` (`shadow` ⇔ `v.shadow_of` set); `experiment_evidence_present` ⇔ `experiment_evidence_count >= 1`; `approver_in_risk_tier` ⇔ `approver_role ∈ APPROVER_TIERS[risk]`; `ran_through_phase` ⇔ `projects_ran_phase >= 1`; `metrics_not_worse` ⇔ payload true; `changelog_entry_present` ⇔ payload true; `successor_default_exists` ⇔ another version of the key is `DEFAULT`.
4. Changelog (§120, ADR-0008 D-8): on `limited` and `default`, before guards are evaluated, the service appends a `ChangelogEntry` (release = running kernel version, `changed` = the `changed` argument or the candidate's `proposed_change`, `reason` = candidate id, `evidence` = candidate evidence ids + experiment `result_summary`) to `kernel_changelog` and re-renders `changelog/<release>.md` atomically; when no candidate is linked or `changed` resolves to empty, `ChangelogRequired` is raised and nothing changes.
5. Promotion to `DEFAULT` demotes the previous `DEFAULT` of the same key to `DEPRECATED` in the same transaction (one `BEHAVIOR_VERSION_CHANGED` per version).
6. `RetrospectiveMetricsCheck.not_worse(v)`: compares `TelemetryManager.metrics(phase_id)` of phases whose `PHASE_TRANSITION → COMPLETE` event carries `behavior_versions[key] == v.version` against the latest such phase of the version it replaces: not worse ⇔ `first_pass_success_rate ≥ base − METRICS_TOLERANCE`, `qc_bugs/stories ≤ base × (1 + METRICS_TOLERANCE)`, `total_cost_usd/stories ≤ base × (1 + METRICS_TOLERANCE)`; no phase under either version → `(False, "no baseline")`. `projects_ran_phase` counts phases run under the version in the current project ledger (1 project per kernel instance).
7. `rollback(..., by, reason)`: allowed from `EXPERIMENTAL`/`LIMITED` only (`GuardRejected` otherwise); `by.role` must be in any approver tier (`ORCHESTRATOR`, `PRODUCT_OWNER`, `USER`, else `PermissionDenied`); stage becomes `DRAFT`; when the current project pins that version its pin is reverted to the key's `DEFAULT` version and `.ai/project/kernel-versions.yaml` rewritten; ledger `BEHAVIOR_VERSION_CHANGED{event: rollback, reason, pin_reverted_to}`.
8. `pin_version`: target stage must be `LIMITED`, `DEFAULT` or `DEPRECATED` (`GuardRejected` for `DRAFT`/`EXPERIMENTAL`; experiment arms are assigned by E10-S08, not pinned); `can_approve(PIN_RISK_BY_KIND[kind], by, PROJECT, config)` must hold (`PermissionDenied`); records a `PROCESS` decision (`DecisionManager.record`); writes the pin file via `KernelVersionPins.write`; mirrors the pinned version into the project DB `behavior_versions`; ledger `BEHAVIOR_VERSION_CHANGED{key, version, pinned: true, previous}`. The change takes effect at the next kernel start; with a running daemon the CLI prints `restart required`.
9. `KernelVersionPins.validate` accepts a pin when `catalog.entries()` contains that key/version in `LIMITED`, `DEFAULT` or `DEPRECATED`; message lines of E02-S04 rule 5 are kept, plus `pin X is <stage> (not pinnable)`.
10. Pinned-table loading: `DefaultWorkflowManager` obtains each table file through `table_source(name)`; composition supplies `lambda name: catalog.resolve(f"WORKFLOW/{name}", pins[...])[1]`; with no pin for a table the builtin path is used. A pinned registered table whose file hash differs from `content_sha256` → `ConfigError` at startup.
11. `list_versions` returns builtin and registered versions ordered by key, then version numerically; `walk improvement versions` prints `KIND/name version stage [pinned]`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `rollout_workflow.yaml` When loaded Then version `1.0`, the five rows of INTERFACES §3.7 with the guard names of this story, and `TransitionTable` validation passes | `tests/improvement/test_rollout_table.py::test_rollout_table_matches_interfaces` |
| 2 | Given each guard and a payload making it false When evaluated Then `GuardResult.ok` is false with the guard name in the reason | `tests/improvement/test_rollout_guards.py::test_each_guard_rejects_on_false_payload` |
| 3 | Given `rollout_event_for(DRAFT, DEFAULT)` Then `GuardRejected` | `tests/improvement/test_rollout_guards.py::test_rollout_event_for_rejects_skips` |
| 4 | Given 2 entries for release `0.9.0` When `render_changelog` Then the text has `Kernel 0.9.0` and per entry `Changed:`, `Reason: IMP-…`, `Evidence:` in order | `tests/improvement/test_changelog.py::test_render_changelog_section_120_layout` |
| 5 | Given a registered `WORKFLOW/feature_workflow 1.1` When `catalog.entries()` Then both `1.0` (DEFAULT, builtin) and `1.1` (registered stage) appear; `resolve` returns the versions-folder path for `1.1` | `tests/improvement/test_versions_registered.py::test_catalog_merges_builtin_and_registered` |
| 6 | Given a pin to a DRAFT version When `validate` Then `VersionPinError` with `not pinnable` | `tests/improvement/test_versions_registered.py::test_validate_rejects_unpinnable_stage` |
| 7 | Given a candidate in `UNDER_REVIEW` When `register_version` Then `GuardRejected` and no row, no file copy, no event | `tests/improvement/test_service_register_version.py::test_register_requires_approved_candidate` |
| 8 | Given a source table whose `version` field is `1.2` When registering version `1.1` Then `ConfigError` | `tests/improvement/test_service_register_version.py::test_register_validates_artifact_version` |
| 9 | Given a MEDIUM approved candidate When registering `2.0` of `feature_workflow` Then `GuardRejected` (MAJOR needs HIGH) | `tests/improvement/test_service_register_version.py::test_major_bump_requires_high_risk` |
| 10 | Given an approved MEDIUM candidate with an ended experiment holding 1 evidence id When `register_version(stage=LIMITED)` by PRODUCT_OWNER Then stage `LIMITED`, a `kernel_changelog` row with `reason == candidate id`, `changelog/<release>.md` written, three `BEHAVIOR_VERSION_CHANGED` events (DRAFT, EXPERIMENTAL, LIMITED) | `tests/improvement/test_service_register_version.py::test_register_to_limited_with_changelog` |
| 11 | Given the same request by ORCHESTRATOR When registering Then `GuardRejected` from `approver_in_risk_tier` and nothing persisted | `tests/improvement/test_service_register_version.py::test_register_atomic_on_guard_failure` |
| 12 | Given a version without `candidate_id` moving to LIMITED When `set_stage` Then `ChangelogRequired` | `tests/improvement/test_service_register_version.py::test_changelog_required_without_candidate` |
| 13 | Given a LIMITED version with phases showing first-pass drop of 0.2 vs baseline When `set_stage(DEFAULT)` Then `GuardRejected` naming `metrics_not_worse` | `tests/improvement/test_rollout_guards.py::test_metrics_check_blocks_default_on_regression` |
| 14 | Given a LIMITED `1.1` passing all guards When `set_stage(DEFAULT)` by USER Then `1.1` DEFAULT and builtin-registered `1.0` DEPRECATED | `tests/improvement/test_service_register_version.py::test_default_demotes_previous_default` |
| 15 | Given a LIMITED version When USER `pin_version` Then `kernel-versions.yaml` has the new version, a PROCESS decision exists, ledger event has `previous == "1.0"`; given PRODUCT_OWNER for a WORKFLOW pin Then `PermissionDenied` | `tests/improvement/test_service_pin_rollback.py::test_pin_requires_tier_and_records_decision` |
| 16 | Given the project pinned to LIMITED `1.1` When `rollback` by PRODUCT_OWNER Then stage `DRAFT`, pin reverted to `1.0`, event payload `pin_reverted_to == "1.0"` | `tests/improvement/test_service_pin_rollback.py::test_rollback_reverts_stage_and_pin` |
| 17 | Given a DEFAULT version When `rollback` Then `GuardRejected` | `tests/improvement/test_service_pin_rollback.py::test_rollback_only_from_experimental_or_limited` |
| 18 | Given a pin to registered `feature_workflow 1.1` with one extra row When the kernel is built Then `WorkflowManager` uses the `1.1` table (the extra transition is accepted) | `tests/workflow/test_service_table_source.py::test_pinned_registered_table_is_loaded` |
| 19 | Given the registered table file edited after registration When the kernel is built Then `ConfigError` (hash mismatch) | `tests/workflow/test_service_table_source.py::test_registered_table_hash_checked` |
| 20 | Given `walk improvement register WORKFLOW/feature_workflow 1.1 --source f.yaml --candidate IMP-01 --stage LIMITED` then `walk improvement versions --kind WORKFLOW --json` Then exit 0 and `1.1` with stage `LIMITED` | `tests/cli/test_cmd_improvement_versions.py::test_register_and_list_versions` |

#### Evidence required
- Quality gate output.
- Demo: `walk improvement register WORKFLOW/feature_workflow 1.1 --source <file> --candidate IMP-01 --stage LIMITED`, `walk improvement pin WORKFLOW/feature_workflow 1.1 --note "opt in"`, `walk version`, `cat $WALK_HOME/.improvement/changelog/<release>.md`, `walk improvement rollback WORKFLOW/feature_workflow 1.1 --reason test`, `walk ledger query --kind BEHAVIOR_VERSION_CHANGED`.

#### Notes
- ADR-0008 D-3 (versioned artefacts, MAJOR opt-in), D-4 (pins; pin change is an improvement decision), D-5 (stages), D-8 (changelog); Invariant 13; §121 (reversible: `rollback` + pin revert).
- `set_stage` gains a `by: Actor` keyword because INTERFACES §3.7 requires a risk-tier approver; update INTERFACES §1.15 in this commit.
- Workflow tables are the only kind whose registered versions are loadable here because the gate (E10-S10) needs `feature_workflow 1.1`; other kinds reuse `catalog.resolve` once their loaders accept a source path.
- Payload keys above are recorded in WBS §3.4 by E10-X01.
- `NEW NAME:` `rollout_workflow.yaml`; module `walk.improvement.rollout` (`RolloutStateMachine`, `ROLLOUT_GUARDS`, `rollout_event_for`, `rollout_payload`, `VersionMetricsCheck`, `RetrospectiveMetricsCheck`, `METRICS_TOLERANCE`) and the guard names `candidate_approved`, `experiment_defined_or_shadow`, `experiment_evidence_present`, `approver_in_risk_tier`, `ran_through_phase`, `metrics_not_worse`, `changelog_entry_present`, `successor_default_exists`; payload keys listed above; module `walk.improvement.changelog` (`ChangelogEntry`, `render_changelog`, `changelog_path`); `ChangelogRequired`; folder `$WALK_HOME/.improvement/versions/<KIND>/<name>/<version>.<ext>`; `BehaviorVersionCatalog.resolve/entries`; `ImprovementManager.set_stage(by=…)`, `.rollback`, `.list_versions`, `.pin_version`; `PIN_RISK_BY_KIND`; `DefaultWorkflowManager(table_source=…)`; `walk improvement versions/register/stage/pin/rollback`.
- Commit subject: `feat: add behavior version rollout, pins and changelog (E10-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S06 — Promotion and pattern/anti-pattern registries

**Status:** TODO
**Type:** feat
**Requirements:** §110, §111, §112, §113, §119, §6.11, §137 (Inv. 9, 13)
**Depends on:** E10-S03
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Project learning reaches kernel scope only through an explicit `walk improvement promote` (§110–§111, ADR-0008 D-2), and the §112 pattern and §113 anti-pattern registries exist in both scopes — with documents, kernel seeds from the requirements, the cross-project rule for kernel patterns, a ledger trail and `walk improvement patterns`.

#### Scope
- In: `promote`; kernel-scope `list_observations`; module `walk.improvement.patterns`; builtin `anti_patterns.yaml` seeds; `PATTERN_SECTIONS`, `ANTI_PATTERN_SECTIONS`; `register_pattern`, `register_anti_pattern`, `list_patterns`; `LedgerEventKind.PATTERN_REGISTERED`; CLI `walk improvement promote`, `walk improvement patterns [add]`; `walk improvement show` for `OBS-K-`, `PATTERN-`, `ANTI-`.
- Out: automatic promotion of any kind (forbidden, §110); kernel candidates from promoted observations (E10-S04 already supports `KERNEL` candidates); agents consuming patterns in their context bundles (not planned in E10); agent tools for promotion or pattern registration (USER/CLI only in this story).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/patterns.py` | create | `pattern_document`, `anti_pattern_document`, `pattern_from_document`, `anti_pattern_from_document`, `load_builtin_anti_patterns`, `BUILTIN_ANTI_PATTERNS_PATH`, `PATTERN_REGISTRARS`, `MIN_PROJECTS_FOR_KERNEL_PATTERN` |
| `src/walk/improvement/defaults/anti_patterns.yaml` | create | — (four seeds, table below; `version: "1.0"`) |
| `src/walk/memory/sections.py` | modify | `PATTERN_SECTIONS`, `ANTI_PATTERN_SECTIONS` |
| `src/walk/telemetry/models.py` | modify | `LedgerEventKind.PATTERN_REGISTERED` |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.register_pattern`, `.register_anti_pattern`, `.list_patterns` |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.promote`, `.register_pattern`, `.register_anti_pattern`, `.list_patterns`, `.list_observations` (kernel scope) |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/cli/cmd_improvement.py` | modify | `promote`, `patterns_app` (`list`, `add`); `show` accepts `OBS-K-`, `PATTERN-`, `ANTI-` |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 three methods; §6 `walk improvement patterns`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§3 `LedgerEventKind.PATTERN_REGISTERED`) |
| `docs/01-architecture/ARCHITECTURE.md` | modify | — (§4.3 `improvement.ImprovementManager` write point gains `PATTERN_REGISTERED`) |
| `tests/improvement/test_patterns_documents.py` | create | — |
| `tests/improvement/test_service_promote.py` | create | — |
| `tests/improvement/test_service_patterns.py` | create | — |
| `tests/cli/test_cmd_improvement_patterns.py` | create | — |

#### Interface contract
`promote(observation_id)` per INTERFACES §1.15; `Pattern`, `AntiPattern` per DOMAIN-MODEL §4.14; ids `PATTERN-NNN`/`ANTI-NNN` from the kernel `id_sequences` (DOMAIN-MODEL §2); kernel layout ARCHITECTURE §9 (`patterns/`, `anti-patterns/`); project documents flat under `.ai/improvements/`.
```python
# src/walk/memory/sections.py
PATTERN_SECTIONS = ("Description", "Observed Benefits", "Applies To", "Evidence", "Source")       # §112 example fields
ANTI_PATTERN_SECTIONS = ("Pattern", "Observed Harm", "Replacement", "Evidence", "Source")         # §113 example fields

# src/walk/improvement/patterns.py
BUILTIN_ANTI_PATTERNS_PATH: str = "improvement/defaults/anti_patterns.yaml"
MIN_PROJECTS_FOR_KERNEL_PATTERN: int = 2                       # ADR-0008 D-2 "from ≥ 2 projects' observations"
PATTERN_REGISTRARS: dict[LearningScope, frozenset[AgentRole]] = {
    LearningScope.PROJECT: frozenset({AgentRole.USER, AgentRole.PROCESS_ARCHITECT, AgentRole.ORCHESTRATOR}),
    LearningScope.KERNEL: frozenset({AgentRole.USER, AgentRole.PROCESS_ARCHITECT}),
}
def pattern_document(p: Pattern, observation_ids: list[ObservationId]) -> MemoryDocument: ...
def anti_pattern_document(a: AntiPattern, observation_ids: list[ObservationId]) -> MemoryDocument: ...
def pattern_from_document(doc: MemoryDocument) -> Pattern: ...
def anti_pattern_from_document(doc: MemoryDocument) -> AntiPattern: ...
def load_builtin_anti_patterns(path: Path | None = None) -> list[AntiPattern]: ...   # ids placeholder "ANTI-000"; scope KERNEL

# src/walk/improvement/protocols.py — additions
async def register_pattern(self, pattern: Pattern, *, observation_ids: list[ObservationId], by: Actor) -> Pattern: ...
async def register_anti_pattern(self, anti: AntiPattern, *, observation_ids: list[ObservationId], by: Actor) -> AntiPattern: ...
async def list_patterns(self, kind: Literal["PATTERN", "ANTI"] | None = None, scope: LearningScope | None = None) -> list[Pattern | AntiPattern]: ...
```
Builtin anti-pattern seeds (`anti_patterns.yaml`):

| title | pattern | replacement | source |
|---|---|---|---|
| Developer closes its own feature | implementer marks its own feature complete | independent QC acceptance | §113 example, Inv. 4 |
| Agent edits its own constitution | agent changes production rules and behaviour changes immediately | observe → propose → review → approve → version → rollout | §103 |
| Adopting a change because it seems better | improvement adopted on preference only | evidence-ordered review (§102) | §102 |
| Project learning becomes global automatically | project-specific lesson changes kernel behaviour without promotion | explicit promotion to a cross-project pattern, then a kernel candidate | §110–§111 |

CLI: `walk improvement promote OBS_ID [--json]`; `walk improvement patterns [list] [--kind PATTERN|ANTI] [--scope PROJECT|KERNEL] [--json]`; `walk improvement patterns add --kind PATTERN|ANTI --title TEXT --from OBS_ID... (--description TEXT --benefit TEXT... --applies-to SCOPE... | --pattern TEXT --harm TEXT... --replacement TEXT) [--scope KERNEL]`.

#### Behavior
1. `promote(OBS-NNNN)`: the observation must exist, be `PROJECT` scope and not yet promoted (`ConfigError` otherwise); `KernelHome.ensure()`; a copy with a new `OBS-K-NNNN` id (kernel sequence), `scope=KERNEL`, the same `origin_project`, `evidence_ids`, `ledger_seq_refs` is inserted in the kernel DB and written to `$WALK_HOME/.improvement/observations/OBS-K-NNNN.md` (`observation_document`); the project observation gets `promoted_to` (`mark_promoted`) and its `.ai/improvements/OBS-NNNN.md` is rewritten with `status: PROMOTED`; ledger `IMPROVEMENT_OBSERVATION{id: OBS-K-…, scope: KERNEL, promoted_from: OBS-…}` on the project ledger.
2. Only the CLI (actor USER) calls `promote` in this story; no hook, signal rule or agent tool calls it (§110, ADR-0008 D-2) — enforced by an architecture test grepping callers.
3. `list_observations(ObservationQuery(scope=KERNEL))` now reads the kernel DB; `scope=None` merges both DBs (ordering of E10-S01 rule 7).
4. `register_pattern` / `register_anti_pattern`: `by.role ∈ PATTERN_REGISTRARS[scope]` (`PermissionDenied`); every observation id exists and has the pattern's scope (`ConfigError`); `KERNEL` scope requires observations from at least `MIN_PROJECTS_FOR_KERNEL_PATTERN` distinct `origin_project` values (`GuardRejected`); `title` and the §112/§113 text fields non-empty; id from the kernel sequence; row in the scope's `patterns` table (`kind` `PATTERN`/`ANTI`); document through `store_for(scope)` (`patterns/` or `anti-patterns/` folder in kernel scope); ledger `PATTERN_REGISTERED{id, kind, scope, observation_ids, by_role}`.
5. Kernel seeds: the first `list_patterns`/`register_anti_pattern` call on a kernel home inserts the builtin anti-patterns that are not yet present (matched by exact `title`), so a fresh home gets `ANTI-001`…`ANTI-004` in file order; re-running inserts nothing (idempotent); seeds carry `evidence_ids == []` and source `§<ref>` text.
6. `list_patterns` orders by id; `kind=None` returns both registries; project patterns never appear in a `scope=KERNEL` listing.
7. `walk improvement show` renders `OBS-K-`, `PATTERN-` and `ANTI-` ids from the correct store; unknown id → exit 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a pattern with 2 benefits When `pattern_document` then `pattern_from_document` Then equal and sections equal `PATTERN_SECTIONS` | `tests/improvement/test_patterns_documents.py::test_pattern_document_roundtrip` |
| 2 | Given an anti-pattern When rendered and parsed Then equal and sections equal `ANTI_PATTERN_SECTIONS` | `tests/improvement/test_patterns_documents.py::test_anti_pattern_document_roundtrip` |
| 3 | Given the shipped `anti_patterns.yaml` When loaded Then 4 anti-patterns with non-empty `pattern`, `observed_harm`, `replacement` | `tests/improvement/test_patterns_documents.py::test_builtin_anti_patterns_load` |
| 4 | Given project observation `OBS-0001` When `promote` Then `OBS-K-0001` exists in the kernel DB and as `$WALK_HOME/.improvement/observations/OBS-K-0001.md` with `origin_project == "DEMO"`, and `OBS-0001.promoted_to == "OBS-K-0001"` with document status `PROMOTED` | `tests/improvement/test_service_promote.py::test_promote_copies_to_kernel_scope` |
| 5 | Given `OBS-0001` already promoted When `promote` again Then `ConfigError` and no second kernel row | `tests/improvement/test_service_promote.py::test_promote_twice_rejected` |
| 6 | Given a promotion When the ledger is queried Then one `IMPROVEMENT_OBSERVATION` with `scope == "KERNEL"` and `promoted_from == "OBS-0001"` | `tests/improvement/test_service_promote.py::test_promote_ledger_event` |
| 7 | Given `src/walk` When grepping for calls to `promote(` Then only `cli/cmd_improvement.py` and the service itself match | `tests/improvement/test_service_promote.py::test_promote_has_no_automatic_callers` |
| 8 | Given kernel observations from projects `DEMO` and `ZOMB` When USER registers a KERNEL pattern from them Then `PATTERN-001` in the kernel DB, document under `patterns/`, `PATTERN_REGISTERED` event | `tests/improvement/test_service_patterns.py::test_register_kernel_pattern_cross_project` |
| 9 | Given kernel observations from one project only When registering a KERNEL pattern Then `GuardRejected` | `tests/improvement/test_service_patterns.py::test_kernel_pattern_requires_two_projects` |
| 10 | Given ORCHESTRATOR When registering a KERNEL anti-pattern Then `PermissionDenied`; a PROJECT pattern by ORCHESTRATOR Then accepted under `.ai/improvements/` | `tests/improvement/test_service_patterns.py::test_registrar_roles_per_scope` |
| 11 | Given a fresh kernel home When `list_patterns(kind="ANTI")` twice Then `ANTI-001`…`ANTI-004` once each | `tests/improvement/test_service_patterns.py::test_builtin_anti_patterns_seeded_once` |
| 12 | Given `walk improvement promote OBS-0001` then `walk improvement observations --scope KERNEL --json` Then exit 0 and one `OBS-K-0001` row | `tests/cli/test_cmd_improvement_patterns.py::test_promote_cli_and_kernel_listing` |
| 13 | Given `walk improvement patterns --kind ANTI --json` on a fresh home Then 4 rows; `walk improvement show ANTI-001` Then the `Replacement` section | `tests/cli/test_cmd_improvement_patterns.py::test_patterns_list_and_show` |

#### Evidence required
- Quality gate output.
- Demo with `WALK_HOME=<tmp>`: `walk improvement promote OBS-0001`, `ls <tmp>/.improvement/observations`, `walk improvement patterns --kind ANTI`, `walk improvement show ANTI-002`.

#### Notes
- ADR-0008 D-1, D-2; §111 promotion path (project observation → project pattern → cross-project pattern → kernel candidate) is realised by `promote` + `register_pattern` + E10-S04 `KERNEL` candidates.
- Evidence ids on promoted observations remain project-local references; the kernel copy records `origin_project` so a reader knows which repository holds the files.
- Implementation-order note: `promote` uses `ObservationRepository.mark_promoted`, `observation_document` and `list_observations` from E10-S01, which WBS §5 does not list as a dependency of this story; E10-X01 must either confirm E10-S01 is merged first or add the dependency (WBS change requires the planner).
- `NEW NAME:` module `walk.improvement.patterns` (`pattern_document`, `anti_pattern_document`, `pattern_from_document`, `anti_pattern_from_document`, `load_builtin_anti_patterns`, `BUILTIN_ANTI_PATTERNS_PATH`, `PATTERN_REGISTRARS`, `MIN_PROJECTS_FOR_KERNEL_PATTERN`); data file `improvement/defaults/anti_patterns.yaml`; `PATTERN_SECTIONS`, `ANTI_PATTERN_SECTIONS`; `ImprovementManager.register_pattern/register_anti_pattern/list_patterns`; `LedgerEventKind.PATTERN_REGISTERED`; `walk improvement patterns [list|add]`.
- Commit subject: `feat: add learning promotion and pattern registries (E10-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S07 — Retrospectives with narrative and PROCESS_ARCHITECT constitution

**Status:** TODO
**Type:** feat
**Requirements:** §101, §114, §115, §117, §32 (`ON_PHASE_REVIEW_START`), §9, §12, §137 (Inv. 1, 5, 13)
**Depends on:** E10-S01, E07-S08
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §101 Process Architect exists as a kernel-default role (constitution, policy, permission rows) that can be run on a retrospective through a carrier task, all four §114 retrospective levels can be generated (metrics-only for tasks and features), and a phase retrospective can carry an LLM-written narrative attached from the Process Architect's output — without the role ever being able to edit behaviour artefacts.

#### Scope
- In: `process_architect.md`; `policies.yaml` / `permissions/defaults.yaml` rows; `RETRO.md.j2` block `process_architect_duties`; module `walk.workflow.analysis` (carrier-task labels); `story_workflow` row `analysis_done` + guard `is_analysis_task`; `ANALYSIS_ROUTES`; `OutputApplier` mapping and `on_analysis_output` callback; module `walk.improvement.retrospectives`; `ImprovementManager.retrospective(level, subject_id)`, `phase_retrospective(with_narrative=True)`, `attach_narrative`; `ON_PHASE_REVIEW_START` attachment passes `with_narrative`; `walk improvement retro SUBJECT_ID [--narrative]`.
- Out: §116 metrics beyond `RetrospectiveMetrics` (E10-S09); kernel copies under `$WALK_HOME/.improvement/retrospectives/` (nothing is written to `$WALK_HOME` by this story — Scope/store rule; copying belongs to a future promotion of retrospectives, not planned); Process Architect use of the `improvement.candidate` tool (available once E10-S04 is merged; its permission row already allows the role); narrative for TASK/FEATURE levels (§114: not required for small tasks).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/defaults/process_architect.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`PROCESS_ARCHITECT` entry) |
| `src/walk/permissions/defaults.yaml` | modify | — (`PROCESS_ARCHITECT` rows, table below) |
| `src/walk/agents/templates/RETRO.md.j2` | modify | — (block `process_architect_duties`; version bump `1.1`) `(verify E07-S08 content)` |
| `src/walk/workflow/analysis.py` | create | `AnalysisStep`, `ANALYSIS_LABEL_PREFIX`, `ANALYSIS_STEP_LABEL_PREFIX`, `analysis_labels`, `analysis_subject_of`, `analysis_step_of` |
| `src/walk/workflow/guards.py` | modify | `is_analysis_task` |
| `src/walk/workflow/tables/story_workflow.yaml` | modify | — (row `analysis_done`; version bump, see Notes) |
| `src/walk/workflow/__init__.py` | modify | re-export `AnalysisStep`, `analysis_labels`, `analysis_step_of`, `analysis_subject_of` |
| `src/walk/orchestrator/router.py` | modify | `ANALYSIS_ROUTES`, `DefaultTaskRouter.route` (analysis rows) |
| `src/walk/runtime/applier.py` | modify | `DefaultOutputApplier.__init__` (`on_analysis_output` parameter); `analysis_done` implied event |
| `src/walk/improvement/retrospectives.py` | create | `narrative_from_output`, `metrics_from_report`, `retrospective_id_for`, `NARRATIVE_LEVELS` |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.retrospective`, `ImprovementManager.attach_narrative` |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.retrospective`, `.phase_retrospective` (narrative carrier), `.attach_narrative` |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/hooks/builtins.py` | modify | — (the E07-S08 `ON_PHASE_REVIEW_START` retrospective attachment passes `with_narrative = PROCESS_ARCHITECT enabled`) `(verify)` |
| `src/walk/cli/cmd_improvement.py` | modify | `retro` (`SUBJECT_ID`, `--narrative`) |
| `src/walk/cli/composition.py` | modify | — (`on_analysis_output = improvement.attach_narrative`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 two methods; §3.2 row; §4 routing row for analysis tasks; §6 `walk improvement retro`) |
| `tests/agents/test_defaults_process_architect.py` | create | — |
| `tests/permissions/test_defaults_process_architect.py` | create | — |
| `tests/workflow/test_analysis_labels.py` | create | — |
| `tests/workflow/test_tables.py` | modify | — (story table row count + version) |
| `tests/orchestrator/test_router_analysis.py` | create | — |
| `tests/runtime/test_applier_analysis.py` | create | — |
| `tests/improvement/test_retrospectives.py` | create | — |
| `tests/improvement/test_service_retrospective_levels.py` | create | — |
| `tests/cli/test_cmd_improvement_retro.py` | create | — |

#### Interface contract
`Retrospective` per DOMAIN-MODEL §4.14; `RetrospectiveMetrics` per §4.12; `phase_retrospective(phase_id, *, with_narrative)` per INTERFACES §1.15; constitution schema ADR-0013.
```python
# src/walk/workflow/analysis.py
class AnalysisStep(StrEnum):
    RETRO = "retro"                                   # Process Architect narrative for a retrospective
ANALYSIS_LABEL_PREFIX = "walk-analysis:"              # + RetrospectiveId
ANALYSIS_STEP_LABEL_PREFIX = "walk-analysis-step:"    # + AnalysisStep value
def analysis_labels(subject: str, step: AnalysisStep) -> list[str]: ...
def analysis_subject_of(item: WorkItem) -> str | None: ...
def analysis_step_of(item: WorkItem) -> AnalysisStep | None: ...    # one label without the other → ConfigError

# src/walk/orchestrator/router.py
ANALYSIS_ROUTES: dict[AnalysisStep, tuple[AgentRole, str]] = {AnalysisStep.RETRO: (AgentRole.PROCESS_ARCHITECT, "RETRO")}

# src/walk/runtime/applier.py — DefaultOutputApplier constructor addition
on_analysis_output: Callable[[WorkItem, AgentOutput], Awaitable[None]] | None = None

# src/walk/improvement/retrospectives.py
NARRATIVE_LEVELS: frozenset[str] = frozenset({"PHASE", "PROJECT"})      # §114: no LLM retrospective for small tasks
def retrospective_id_for(level: Literal["TASK", "FEATURE", "PHASE", "PROJECT"], subject_id: str) -> RetrospectiveId: ...
    # "RETRO-" + subject_id for TASK/FEATURE/PHASE (RETRO-STORY-0001, RETRO-FEAT-0012, RETRO-PHASE-03); "RETRO-PROJECT-<key>"
def metrics_from_report(report: Report) -> RetrospectiveMetrics: ...    # maps E09-S01 task/feature report data `(verify keys)`
def narrative_from_output(output: AgentOutput) -> str: ...              # summary + findings rendered as Markdown; secrets refused

# src/walk/improvement/protocols.py — additions
async def retrospective(self, level: Literal["TASK", "FEATURE", "PHASE", "PROJECT"], subject_id: str, *, with_narrative: bool = False) -> Retrospective: ...
async def attach_narrative(self, item: WorkItem, output: AgentOutput) -> Retrospective: ...
```
`story_workflow.yaml` new row (INTERFACES §3.2 addition): `READY | analysis_done | is_analysis_task, output_status_is_completed | COMPLETE | ON_TASK_COMPLETE | KERNEL`.

Constitution front matter (ADR-0013 D-2): `id: PROCESS_ARCHITECT`, `role: PROCESS_ARCHITECT`, `version: "1.0"`, `identity: Process Architect (Kernel Improvement Agent)`, `mission: Improve AI Studio effectiveness using production evidence.` (§101), `responsibilities: [analyze ledger, inspect retrospective, find recurring patterns, create improvement candidates, evaluate impact, track post-change performance]`, `authority: {decision_scope: [PROCESS], max_autonomy_level: 1, may_approve: [], may_reject: [], may_create_work: []}`, `risk_tolerance: LOW`, `preferred_evidence: [PROJECT_DATA, QC_REPORT, AUTOMATED_TEST, PERFORMANCE_METRICS]`, `escalation_rules: [{condition: "change to agent authority, autonomy, phase gate or permissions", to_level: 3, category: PROCESS}]`, `tool_permissions: [{tool: Edit, effect: DENY}, {tool: Write, effect: DENY}, {tool: bash, effect: DENY}]`, `forbidden_actions: ["edit constitutions, workflow tables, skills, templates or policies", "approve or pin its own proposals", "promote project learning to kernel scope"]`. Body sections per ADR-0013 D-3, one paragraph each derived from §101–§103.

`permissions/defaults.yaml` rows added:

| role | tool | effect |
|---|---|---|
| PROCESS_ARCHITECT | `Read`, `Glob`, `Grep`, `decision.propose` | ALLOW |
| PROCESS_ARCHITECT | `Edit`, `Write`, `bash`, `git.*`, `jira.*`, `store.*` | DENY |

`policies.yaml` `PROCESS_ARCHITECT` entry: `model_policy` copied from the `ORCHESTRATOR` row of ADR-0011 D-3 with `required_capabilities: [PLANNING, LONG_CONTEXT_REASONING]`, `cross_model_review: false`; `effort_policy.default: MEDIUM`; kernel-default `budget_policy`; `allowed_tools: [Read, Glob, Grep]`; `allowed_paths: []`; `execution_strategy: single_run`; `max_parallel_runs: 1`.

CLI: `walk improvement retro SUBJECT_ID [--narrative] [--json]` — level inferred from the id prefix (`PHASE-` → PHASE; `EPIC-|FEAT-` → FEATURE; `STORY-|TASK-|BUG-` → TASK; otherwise the project key → PROJECT).

#### Behavior
1. `ConstitutionLoader.load(PROCESS_ARCHITECT)` succeeds, `list_roles()` includes it, and the provider-name lint passes; `PermissionManager.decide` gives DENY for `Edit`/`Write`/`bash` and a project rule widening any of them → `ConfigError` (E02-S10 narrowing). The role cannot write `.ai/agents/**` or kernel paths (BoundaryAuditor, Inv. 13).
2. `analysis_labels(subject, step)` returns exactly `[f"walk-analysis:{subject}", f"walk-analysis-step:{step}"]`; parsing helpers return `None` without labels and raise `ConfigError` when only one label is present.
3. `DefaultTaskRouter.route`: a TASK in `READY`/`REWORK` with `analysis_step_of(item)` set → `RouteDecision` from `ANALYSIS_ROUTES`, `cross_model_review=False`; all other routing unchanged.
4. `DefaultOutputApplier`: for an analysis task, raises `analysis_done` (payload `output_status`, `evidence_kinds_present`) instead of the regular mapping, then awaits `on_analysis_output(item, output)` when set; a callback error is logged and re-raised as the run's failure (no silent swallow).
5. `retrospective(level, subject_id)`: `PHASE` delegates to `phase_retrospective`; `PROJECT` uses `TelemetryManager.metrics()` over the whole ledger; `TASK`/`FEATURE` use `LedgerManager.report("task"|"feature", subject_id)` and `metrics_from_report`; each writes the `retrospectives` row (upsert by id) and `.ai/improvements/<RETRO-id>.md` (`type: retrospective`) through `MemoryManager.write`; `top_bottleneck`/`top_defect` rules are the E07-S08 ones `(verify)`; `with_narrative=True` for `TASK`/`FEATURE` → `ConfigError` (§114).
6. `phase_retrospective(phase_id, with_narrative=True)` (and `PROJECT` with narrative): after the metrics retrospective is written, when `PROCESS_ARCHITECT` is an enabled role, creates one carrier TASK (`WorkflowManager.create`, `contract.owner_role = PROCESS_ARCHITECT`, labels `analysis_labels(retro_id, RETRO)`, state `READY`); when the role is not enabled, the call returns the metrics-only retrospective and logs `narrative skipped: PROCESS_ARCHITECT not enabled`. An existing non-terminal carrier for the same retrospective is reused (idempotent).
7. The `RETRO` purpose instructions for the carrier include the block `process_architect_duties`: the retrospective metrics table, the ids of observations created during the subject's time range, the instruction to return the narrative in `summary`/`findings`, to report proposed improvements as `observations`, and the forbidden actions of the constitution.
8. `attach_narrative(item, output)`: resolves the retrospective from `analysis_subject_of(item)`; `narrative_markdown = narrative_from_output(output)` (refuses secrets with `SecretDetected`); rewrites the retrospective row and document section `Narrative`; observation drafts in the same output are applied by the existing applier path (`source_signal="agent"`); a second call replaces the narrative (latest run wins).
9. The default `ON_PHASE_REVIEW_START` retrospective attachment calls `phase_retrospective(phase_id, with_narrative=<PROCESS_ARCHITECT enabled>)`; the phase guard `retrospective_written` is satisfied by the metrics retrospective and never waits for the narrative.
10. Nothing in this story writes under `$WALK_HOME`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the shipped defaults When `ConstitutionLoader.load(PROCESS_ARCHITECT)` Then `decision_scope == [PROCESS]`, `may_approve == []`, `max_autonomy_level == 1`, mission equals §101 | `tests/agents/test_defaults_process_architect.py::test_process_architect_constitution_loads` |
| 2 | Given `policies.yaml` When loaded for `PROCESS_ARCHITECT` Then `allowed_paths == []` and `allowed_tools == ["Read", "Glob", "Grep"]` | `tests/agents/test_defaults_process_architect.py::test_process_architect_policy_defaults` |
| 3 | Given `PROCESS_ARCHITECT` When `decide(Edit)`, `decide(bash)`, `decide(Read)` Then DENY, DENY, ALLOW; a project rule `PROCESS_ARCHITECT Write ALLOW` Then `ConfigError` | `tests/permissions/test_defaults_process_architect.py::test_process_architect_cannot_write` |
| 4 | Given `analysis_labels("RETRO-PHASE-01", RETRO)` on a TASK When parsed Then subject and step round-trip; one label only Then `ConfigError` | `tests/workflow/test_analysis_labels.py::test_analysis_labels_roundtrip_and_partial_rejected` |
| 5 | Given `story_workflow.yaml` When loaded Then it contains `READY --analysis_done--> COMPLETE` with `is_analysis_task` and `output_status_is_completed`, and all previous rows unchanged | `tests/workflow/test_tables.py::test_story_workflow_analysis_row` |
| 6 | Given a plain TASK When `raise_event(analysis_done)` Then `GuardRejected` from `is_analysis_task` | `tests/workflow/test_analysis_labels.py::test_analysis_done_rejected_for_plain_task` |
| 7 | Given an analysis TASK in READY When `route` Then `(PROCESS_ARCHITECT, "RETRO")` with `cross_model_review False`; a plain TASK Then the E03-S07 result | `tests/orchestrator/test_router_analysis.py::test_analysis_task_routes_to_process_architect` |
| 8 | Given a fake PROCESS_ARCHITECT run on a carrier returning `COMPLETED` with a summary When applied Then the task is `COMPLETE` via `analysis_done` and `on_analysis_output` was awaited once | `tests/runtime/test_applier_analysis.py::test_carrier_completes_and_callback_called` |
| 9 | Given an `AgentOutput` with summary and 2 findings When `narrative_from_output` Then Markdown containing the summary and both findings; with a key pattern Then `SecretDetected` | `tests/improvement/test_retrospectives.py::test_narrative_from_output` |
| 10 | Given levels and subjects When `retrospective_id_for` Then `RETRO-STORY-0001`, `RETRO-FEAT-0012`, `RETRO-PHASE-03`, `RETRO-PROJECT-DEMO`, all matching `RetrospectiveId` | `tests/improvement/test_retrospectives.py::test_retrospective_ids` |
| 11 | Given a seeded feature with 3 stories When `retrospective("FEATURE", "FEAT-0001")` Then metrics `stories == 3`, document `.ai/improvements/RETRO-FEAT-0001.md` written, `narrative_markdown == ""` | `tests/improvement/test_service_retrospective_levels.py::test_feature_retrospective_metrics_only` |
| 12 | Given `retrospective("TASK", "STORY-0001", with_narrative=True)` Then `ConfigError` | `tests/improvement/test_service_retrospective_levels.py::test_task_narrative_rejected` |
| 13 | Given PROCESS_ARCHITECT enabled When `phase_retrospective("PHASE-01", with_narrative=True)` twice Then one carrier TASK with the analysis labels in READY | `tests/improvement/test_service_retrospective_levels.py::test_phase_narrative_creates_single_carrier` |
| 14 | Given PROCESS_ARCHITECT not enabled When `phase_retrospective(with_narrative=True)` Then no carrier and a metrics retrospective | `tests/improvement/test_service_retrospective_levels.py::test_phase_narrative_skipped_without_role` |
| 15 | Given a carrier for `RETRO-PHASE-01` When `attach_narrative(item, output)` Then the row and the document `Narrative` section hold the rendered narrative | `tests/improvement/test_service_retrospective_levels.py::test_attach_narrative_updates_retrospective` |
| 16 | Given any test in this story Then the temporary `$WALK_HOME` stays empty | `tests/improvement/test_service_retrospective_levels.py::test_no_kernel_home_writes` |
| 17 | Given `walk improvement retro PHASE-01 --narrative --json` with PROCESS_ARCHITECT enabled Then exit 0 and JSON has `id == "RETRO-PHASE-01"` and `carrier_task_id` | `tests/cli/test_cmd_improvement_retro.py::test_retro_cli_phase_with_narrative` |

#### Evidence required
- Quality gate output.
- Demo on the E07 gate fixture repo with `PROCESS_ARCHITECT` enabled and a scripted fake adapter: `walk improvement retro PHASE-01 --narrative`, `walk run --once` (carrier run), `walk improvement show RETRO-PHASE-01` (narrative present), `walk improvement retro FEAT-0001`.

#### Notes
- §101 "SHOULD support a specialized role"; ADR-0013 D-1–D-5, D-7; ADR-0008 D-7 (agents cannot write behaviour); Invariant 5 (`decision_scope: [PROCESS]` with `max_autonomy_level: 1` — PA proposes, never records accepted decisions alone).
- Placement correction to the header `NEW NAME:` table: the label helpers live in `walk.workflow.analysis` (not `walk.improvement.retrospectives`) because `workflow.guards` and `runtime.applier` may not import `walk.improvement` (ARCHITECTURE §2.2); this mirrors E11-S01's `walk.workflow.release`.
- Shared files with E11-S01 (parallel epic): `story_workflow.yaml`, `workflow/guards.py`, `workflow/__init__.py`, `orchestrator/router.py`, `runtime/applier.py`, `tests/workflow/test_tables.py`. Merge-order rule: whichever of E10-S07 / E11-S01 merges first sets `story_workflow` `version: "1.1"`; the second rebases, keeps both rows and sets `"1.2"` (one MINOR bump per added row, §105).
- Carrier-task pattern is the same as E11's (header "Carrier-task mechanism"): agent runs need a work item (`AgentExecutor.start(agent, item, purpose)`).
- `NEW NAME:` kernel default constitution `process_architect.md`; module `walk.workflow.analysis` (`AnalysisStep`, `ANALYSIS_LABEL_PREFIX`, `ANALYSIS_STEP_LABEL_PREFIX`, `analysis_labels`, `analysis_subject_of`, `analysis_step_of`); guard `is_analysis_task`; `story_workflow` event `analysis_done`; `ANALYSIS_ROUTES`; `DefaultOutputApplier(on_analysis_output=…)`; module `walk.improvement.retrospectives` (`narrative_from_output`, `metrics_from_report`, `retrospective_id_for`, `NARRATIVE_LEVELS`); `ImprovementManager.retrospective(level, subject_id)`, `.attach_narrative`; `RETRO.md.j2` block `process_architect_duties`; `walk improvement retro SUBJECT_ID --narrative`.
- Commit subject: `feat: add process architect and multi-level retrospectives (E10-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S08 — Experiments: A/B by work-item hash and shadow evaluation

**Status:** TODO
**Type:** feat
**Requirements:** §107, §108, §102, §105, §82, §139 (experiment methodology), §32 (`ON_AGENT_START`), §137 (Inv. 13)
**Depends on:** E10-S05
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A candidate's versioned change can be measured before rollout by the two ADR-0008 D-9 methods: `AB_BY_WORK_ITEM_HASH` (opted-in projects run treatment `WORKFLOW` tables on the hash-selected half of new work items, with per-arm §107 metrics compared by a fixed, documented rule) and `SHADOW` (the treatment `MODEL_ROUTING`/`EFFORT_POLICY` version computes "would have" decisions recorded in the ledger without acting) — and every ended experiment yields result evidence that the E10-S05 rollout guards consume.

#### Scope
- In: module `walk.improvement.experiments`; `start_experiment`, `end_experiment`, `shadow_evaluate`, `experiment_versions_for`; experiment documents (`EXPERIMENT_SECTIONS`); project opt-in `KernelVersionPins.experiments`; per-item `WORKFLOW` table selection; `AgentExecutor(versions_for_item=…)` stamping; `LedgerEventKind.SHADOW_EVALUATION`; hook `agent_start_shadow_evaluate`; ADR-0008 addendum (decision rule and thresholds); CLI `walk improvement experiments list/show/start/end`.
- Out: statistical significance testing (the addendum fixes a threshold rule and records that significance is not computed); A/B for kinds other than `WORKFLOW` and shadow for kinds other than `MODEL_ROUTING`/`EFFORT_POLICY` — `start_experiment` refuses them with `ConfigError` (their loaders do not accept per-run sources, E10-S05 Scope); §116 version outcome reporting (E10-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/experiments.py` | create | `ExperimentAssigner`, `arm_for`, `ExperimentArm`, `ArmMetrics`, `ExperimentResult`, `ExperimentVerdict`, `compare_arms`, `MIN_ARM_SIZE`, `IMPROVEMENT_THRESHOLD`, `REGRESSION_TOLERANCE`, `EXPERIMENT_METRICS`, `AB_KINDS`, `SHADOW_KINDS`, `ShadowEvaluator`, `RoutingShadowEvaluator`, `EffortShadowEvaluator`, `experiment_document` |
| `src/walk/memory/sections.py` | modify | `EXPERIMENT_SECTIONS` |
| `src/walk/telemetry/models.py` | modify | `LedgerEventKind.SHADOW_EVALUATION` |
| `src/walk/improvement/versions.py` | modify | `KernelVersionPins.experiments` |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.start_experiment`, `.end_experiment`, `.shadow_evaluate`, `.experiment_versions_for` |
| `src/walk/improvement/service.py` | modify | the four methods above |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.__init__` (`table_source: Callable[[str, WorkItemId \| None], Path]`), explicit `WORKFLOW/<table>` version on transition events `(verify stamping point, E01-S09)` |
| `src/walk/runtime/executor.py` | modify | `DefaultAgentExecutor.__init__` (`versions_for_item` parameter) `(verify, E01-S27)` |
| `src/walk/hooks/builtins.py` | modify | `agent_start_shadow_evaluate` (default, `ON_AGENT_START`, priority 140) `(verify)` |
| `src/walk/cli/cmd_improvement.py` | modify | `experiments_app` (`list`, `show`, `start`, `end`); `show` accepts `EXP-` |
| `src/walk/cli/composition.py` | modify | — (`ExperimentAssigner` from pins; experiment-aware `table_source`; `versions_for_item`; shadow evaluators) |
| `docs/01-architecture/adr/ADR-0008-learning-separation-and-behavior-versioning.md` | modify | — (Addendum A: D-9 decision rule) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.15 four methods; §6 `walk improvement experiments …`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§3 `LedgerEventKind.SHADOW_EVALUATION`) |
| `docs/01-architecture/ARCHITECTURE.md` | modify | — (§4.3 `improvement.ImprovementManager` write point gains `SHADOW_EVALUATION`) |
| `tests/improvement/test_experiments_assign.py` | create | — |
| `tests/improvement/test_experiments_compare.py` | create | — |
| `tests/improvement/test_shadow_evaluators.py` | create | — |
| `tests/improvement/test_service_experiments.py` | create | — |
| `tests/workflow/test_service_table_source_per_item.py` | create | — |
| `tests/runtime/test_executor_versions_for_item.py` | create | — |
| `tests/hooks/test_builtins_shadow.py` | create | — |
| `tests/cli/test_cmd_improvement_experiments.py` | create | — |

#### Interface contract
`Experiment` per DOMAIN-MODEL §4.14; method definitions ADR-0008 D-9; folder `$WALK_HOME/.improvement/experiments/EXP-NNNN.md` (ARCHITECTURE §9).
```python
# src/walk/improvement/experiments.py
EXPERIMENT_METRICS: tuple[str, ...] = ("duration_s", "rework", "qc_defects", "tokens", "cost_usd", "escalations")   # §107
MIN_ARM_SIZE: int = 20                  # ADR-0008 D-9
IMPROVEMENT_THRESHOLD: float = 0.05     # ≥ 5 % better mean on at least one selected metric
REGRESSION_TOLERANCE: float = 0.10      # no selected metric > 10 % worse
AB_KINDS: frozenset[ImprovementScope] = frozenset({ImprovementScope.WORKFLOW})
SHADOW_KINDS: frozenset[ImprovementScope] = frozenset({ImprovementScope.MODEL_ROUTING, ImprovementScope.EFFORT_POLICY})

class ExperimentArm(StrEnum):
    CONTROL = "control"
    TREATMENT = "treatment"

def arm_for(work_item_id: WorkItemId) -> ExperimentArm: ...        # int(sha1(id).hexdigest(), 16) % 2 == 1 → TREATMENT

class ArmMetrics(FrozenModel):
    arm: ExperimentArm
    items: int
    means: dict[str, float]            # keys ⊆ EXPERIMENT_METRICS

class ExperimentVerdict(StrEnum):
    IMPROVED = "IMPROVED"
    NO_CHANGE = "NO_CHANGE"
    REGRESSED = "REGRESSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class ExperimentResult(FrozenModel):
    experiment_id: ExperimentId
    verdict: ExperimentVerdict
    control: ArmMetrics | None
    treatment: ArmMetrics | None
    relative_change: dict[str, float]   # (treatment − control) / control per metric; lower is better for all six
    shadow_agreement: float | None      # SHADOW only: share of evaluations where would_have == actual
    shadow_evaluations: int
    summary: str

def compare_arms(control: ArmMetrics, treatment: ArmMetrics, metrics: list[str]) -> ExperimentResult: ...

class ExperimentAssigner:
    def __init__(self, active: list[tuple[Experiment, str]], pins: dict[str, str]) -> None: ...    # (experiment, "<KIND>/<name>")
    def versions_for(self, work_item_id: WorkItemId) -> dict[str, str]: ...    # pins with treatment versions for TREATMENT items

class ShadowEvaluator(Protocol):
    kind: ImprovementScope
    async def evaluate(self, version_path: Path, ctx: HookContext) -> tuple[JsonDict, JsonDict]: ...    # (would_have, actual)
class RoutingShadowEvaluator: ...      # treatment models.yaml → ModelRouter selection for the run's role/effort `(verify loader, E01-S20)`
class EffortShadowEvaluator: ...       # treatment policies.yaml effort_policy → EffortManager.resolve `(verify, E01-S13)`

def experiment_document(e: Experiment, result: ExperimentResult | None) -> MemoryDocument: ...

# src/walk/memory/sections.py
EXPERIMENT_SECTIONS = ("Design", "Arms", "Metrics", "Results")

# src/walk/improvement/versions.py
class KernelVersionPins(WalkModel):
    experiments: list[ExperimentId] = Field(default_factory=list, description="experiments this project opted into (§107)")

# src/walk/improvement/protocols.py — additions
async def start_experiment(self, candidate_id: ImprovementId, *, key: str, treatment_version: str,
                           assignment: Literal["AB_BY_WORK_ITEM_HASH", "SHADOW"], metrics: list[str], by: Actor) -> Experiment: ...
async def end_experiment(self, experiment_id: ExperimentId, *, by: Actor) -> ExperimentResult: ...
async def shadow_evaluate(self, ctx: HookContext) -> list[LedgerEvent]: ...
def experiment_versions_for(self, work_item_id: WorkItemId) -> dict[str, str]: ...

# src/walk/runtime/executor.py — DefaultAgentExecutor constructor addition
versions_for_item: Callable[[WorkItemId], dict[str, str]] | None = None
```
`SHADOW_EVALUATION` payload: `experiment_id`, `key`, `version`, `would_have`, `actual`, `agrees: bool`.

CLI: `walk improvement experiments list [--open] [--json]`; `walk improvement experiments show EXP_ID`; `walk improvement experiments start --candidate IMP_ID --version KIND/NAME@VERSION --assignment AB_BY_WORK_ITEM_HASH|SHADOW [--metric M...]`; `walk improvement experiments end EXP_ID [--json]`.

#### Behavior
1. `start_experiment`: candidate `APPROVED` (`GuardRejected`); `by.role ∈ {PROCESS_ARCHITECT, USER}` (`PermissionDenied`, INTERFACES §3.7 "Who"); the treatment version is registered and `DRAFT` (E10-S05); kind ∈ `AB_KINDS` for AB and ∈ `SHADOW_KINDS` for SHADOW (`ConfigError`); `metrics ⊆ EXPERIMENT_METRICS` and non-empty for AB (`ConfigError`); control version = the project's current pin for the key. Allocates `EXP-NNNN` (kernel sequence), inserts the kernel row, writes `experiment_document`, sets `candidate.experiment_id`, sets `shadow_of = <control version>` on the treatment `BehaviorVersion` for SHADOW, adds the id to `KernelVersionPins.experiments` of the current project (opt-in) and rewrites the pin file; ledger `IMPROVEMENT_CANDIDATE{id: candidate, experiment_id, event: experiment_started}`. The caller then moves the version to `EXPERIMENTAL` with `set_stage` (guard `experiment_defined_or_shadow` now true).
2. Assignment is active only while the experiment is open, opted in by the project, and its treatment version is `EXPERIMENTAL`. `arm_for` is deterministic and independent of time; items created before `started_at` are always `CONTROL`.
3. `experiment_versions_for(item)` = `ExperimentAssigner.versions_for(item)`: the pin map with the treatment version substituted for `TREATMENT` items of active AB experiments.
4. Per-item `WORKFLOW` table: `DefaultWorkflowManager` calls `table_source(name, item_id)`; composition resolves the version from `experiment_versions_for(item_id)` (falling back to the pin when `item_id` is `None`), so a treatment item follows the treatment table for its whole life; every `WORK_ITEM_TRANSITION` carries the explicit `behavior_versions["WORKFLOW/<table>"]` actually used (E09-S05 rule 1 merges it over the pins).
5. `DefaultAgentExecutor` with `versions_for_item` set stamps that map explicitly on every ledger event it writes for the run (`AGENT_RUN_STARTED`, `AGENT_RUN_ENDED`, `MODEL_SELECTED`, …); with `None` behaviour is unchanged.
6. Shadow (§108): `agent_start_shadow_evaluate` (default attachment, `log_and_continue`) calls `shadow_evaluate(ctx)`; for each open, opted-in SHADOW experiment the matching evaluator computes `(would_have, actual)` from the treatment file without changing the run's selection; one `SHADOW_EVALUATION` event per experiment; an evaluator error is logged and never fails the run.
7. `end_experiment`: `by.role ∈ {PROCESS_ARCHITECT, USER}`; AB — arm membership = items created after `started_at` in the project, by `arm_for`; per-item metrics from the ledger (`duration_s` = Σ `AGENT_RUN_ENDED.duration_ms`/1000, `rework` = count `WORK_ITEM_TRANSITION` to `REWORK`, `qc_defects` = `BUG_CREATED` linked to the item or its feature, `tokens`/`cost_usd` = Σ `COST_RECORDED`, `escalations` = count `ESCALATION_RAISED`); `compare_arms` verdict: `INSUFFICIENT_DATA` when either arm has fewer than `MIN_ARM_SIZE` items; `REGRESSED` when any selected metric's relative change > `REGRESSION_TOLERANCE`; `IMPROVED` when at least one is ≤ −`IMPROVEMENT_THRESHOLD`; else `NO_CHANGE`. SHADOW — `shadow_agreement` and count; verdict `INSUFFICIENT_DATA` below `MIN_ARM_SIZE` evaluations, else `NO_CHANGE` (shadow measures divergence, not outcome; the summary states the agreement).
8. `end_experiment` always records the result as evidence (`EvidenceManager.record`, kind `PROJECT_DATA`, JSON of `ExperimentResult`), sets `ended_at`, `result_summary` (`verdict` + key figures), `result_evidence_ids`, rewrites the document (`Results` section), removes the id from the project's opted-in list; a second call raises `ConfigError`. The verdict is shown to the approver through the changelog evidence (E10-S05 rule 4); rollout guards do not interpret it.
9. ADR-0008 Addendum A records: the two methods as implemented, `MIN_ARM_SIZE`, `IMPROVEMENT_THRESHOLD`, `REGRESSION_TOLERANCE`, the "lower is better" orientation of all six metrics, the fact that no significance test is computed (§139 open question answered as "threshold rule, revisit with data"), and the AB/SHADOW kind limits.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given 1 000 synthetic ids When `arm_for` Then the result equals `int(sha1(id).hexdigest(), 16) % 2` mapping and both arms hold 40–60 % | `tests/improvement/test_experiments_assign.py::test_arm_for_matches_sha1_rule` |
| 2 | Given an active AB experiment on `WORKFLOW/feature_workflow` with treatment `1.1` When `versions_for` a TREATMENT id and a CONTROL id Then `1.1` and the pinned `1.0` | `tests/improvement/test_experiments_assign.py::test_assigner_substitutes_treatment_version` |
| 3 | Given arms of 25 items with treatment cost −8 % and others within ±3 % When `compare_arms` Then `IMPROVED` | `tests/improvement/test_experiments_compare.py::test_verdict_improved` |
| 4 | Given treatment rework +15 % When `compare_arms` Then `REGRESSED` even if cost improved | `tests/improvement/test_experiments_compare.py::test_verdict_regressed_dominates` |
| 5 | Given an arm of 19 items When `compare_arms` Then `INSUFFICIENT_DATA` | `tests/improvement/test_experiments_compare.py::test_verdict_insufficient_below_min_arm_size` |
| 6 | Given a treatment `models.yaml` preferring another model for SENIOR_DEV When `RoutingShadowEvaluator.evaluate` Then `would_have.model_id` differs from `actual.model_id` and the real router state is unchanged | `tests/improvement/test_shadow_evaluators.py::test_routing_shadow_records_would_have_only` |
| 7 | Given a treatment effort policy When `EffortShadowEvaluator.evaluate` Then `would_have.effort` is the treatment resolution | `tests/improvement/test_shadow_evaluators.py::test_effort_shadow_resolution` |
| 8 | Given an `UNDER_REVIEW` candidate When `start_experiment` Then `GuardRejected`; given SENIOR_DEV Then `PermissionDenied`; given AB on `SKILL` Then `ConfigError` | `tests/improvement/test_service_experiments.py::test_start_experiment_preconditions` |
| 9 | Given an approved candidate and a DRAFT `feature_workflow 1.1` When USER `start_experiment(AB)` Then `EXP-0001` row and document exist, `candidate.experiment_id == "EXP-0001"`, `kernel-versions.yaml` lists `EXP-0001`, and `set_stage(EXPERIMENTAL)` then succeeds | `tests/improvement/test_service_experiments.py::test_start_ab_experiment_enables_experimental_stage` |
| 10 | Given an open AB experiment and 25 items per arm seeded in the ledger When `end_experiment` Then a `PROJECT_DATA` evidence row, `result_evidence_ids` non-empty, `ended_at` set, document `Results` filled, opt-in removed | `tests/improvement/test_service_experiments.py::test_end_experiment_records_evidence` |
| 11 | Given an ended experiment When `end_experiment` again Then `ConfigError` | `tests/improvement/test_service_experiments.py::test_end_experiment_twice_rejected` |
| 12 | Given a TREATMENT item under an active AB experiment When it transitions Then the treatment table is used and the `WORK_ITEM_TRANSITION` event has `behavior_versions["WORKFLOW/feature_workflow"] == "1.1"`; a CONTROL item Then `"1.0"` | `tests/workflow/test_service_table_source_per_item.py::test_treatment_item_uses_treatment_table` |
| 13 | Given `versions_for_item` returning a treatment map When a fake run executes Then `AGENT_RUN_STARTED` and `AGENT_RUN_ENDED` carry that map; with `None` Then only the pins | `tests/runtime/test_executor_versions_for_item.py::test_run_events_stamped_with_item_versions` |
| 14 | Given an open SHADOW experiment on `MODEL_ROUTING` When `ON_AGENT_START` fires Then one `SHADOW_EVALUATION` event with `would_have`, `actual`, `agrees` and the run uses the production model | `tests/hooks/test_builtins_shadow.py::test_shadow_evaluation_recorded_without_acting` |
| 15 | Given a shadow evaluator raising When `ON_AGENT_START` fires Then the run proceeds and `HOOK_FAILED` is recorded | `tests/hooks/test_builtins_shadow.py::test_shadow_failure_does_not_fail_run` |
| 16 | Given `walk improvement experiments start --candidate IMP-01 --version WORKFLOW/feature_workflow@1.1 --assignment AB_BY_WORK_ITEM_HASH --metric cost_usd` then `experiments list --open --json` Then exit 0 and one open experiment | `tests/cli/test_cmd_improvement_experiments.py::test_experiments_start_and_list` |

#### Evidence required
- Quality gate output.
- Demo: `walk improvement experiments start …`, `walk improvement stage WORKFLOW/feature_workflow 1.1 EXPERIMENTAL`, a fake phase run, `walk ledger query --kind SHADOW_EVALUATION --limit 3`, `walk improvement experiments end EXP-0001`, `walk improvement show EXP-0001`, and the ADR-0008 addendum diff.

#### Notes
- ADR-0008 D-9 (methods), D-5 (EXPERIMENTAL stage), D-4 (every event records the versions in effect); §102 (controlled comparison ranks above single-project evidence; E10-S04 `CONTROLLED_COMPARISON` becomes reachable here).
- `DefaultWorkflowManager.table_source` signature changes from `Callable[[str], Path]` (E10-S05) to `Callable[[str, WorkItemId | None], Path]`; update E10-S05 call sites and INTERFACES in this commit.
- Treatment items keep the treatment table after the experiment ends (stable per item); new items after `end_experiment` use the pin.
- `NEW NAME:` module `walk.improvement.experiments` (`ExperimentAssigner`, `arm_for`, `ExperimentArm`, `ArmMetrics`, `ExperimentResult`, `ExperimentVerdict`, `compare_arms`, `MIN_ARM_SIZE`, `IMPROVEMENT_THRESHOLD`, `REGRESSION_TOLERANCE`, `EXPERIMENT_METRICS`, `AB_KINDS`, `SHADOW_KINDS`, `ShadowEvaluator`, `RoutingShadowEvaluator`, `EffortShadowEvaluator`, `experiment_document`); `EXPERIMENT_SECTIONS`; `LedgerEventKind.SHADOW_EVALUATION`; `KernelVersionPins.experiments`; `ImprovementManager.start_experiment/end_experiment/shadow_evaluate/experiment_versions_for`; `DefaultAgentExecutor(versions_for_item=…)`; item-aware `table_source`; hook callable `agent_start_shadow_evaluate`; `walk improvement experiments list/show/start/end`; ADR-0008 Addendum A.
- Commit subject: `feat: add a/b and shadow improvement experiments (E10-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S09 — Improvement metrics and report

**Status:** TODO
**Type:** feat
**Requirements:** §116, §117, §118, §106, §83, §86, §137 (Inv. 9)
**Depends on:** E10-S02, E09-S02
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
All eighteen §116 improvement metrics are computed from the ledger alone (per period, phase or behaviour version), the human-intervention rate is never reported without the decision-quality metrics beside it (§117), a version's measured outcome against its predecessor closes the §106 provenance chain, and the improvement report and `walk improvement metrics` expose them.

#### Scope
- In: `ImprovementMetrics`; `IMPROVEMENT_METRIC_QUERIES`, `compute_improvement_metrics`, `AUTONOMY_QUALITY_FIELDS`; `TelemetryManager.improvement_metrics`; version filter on metric queries; `VersionOutcome`, `ImprovementManager.measure_version`; `ImprovementReportQuery` sections `Improvement metrics`, `Autonomy quality`, `Version outcomes`, `User feedback signals`; `LedgerManager.report(..., since=…)`; `walk improvement metrics`; `walk report improvement --since`.
- Out: changing `RetrospectiveMetrics` (fixed by DOMAIN-MODEL §4.12); rollout guard `metrics_not_worse` (E10-S05 keeps its own `RetrospectiveMetricsCheck`; switching it to `measure_version` is a later improvement); dashboards/views for these metrics (no new `v_*` view in E10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/models.py` | modify | `ImprovementMetrics` |
| `src/walk/telemetry/metrics.py` | modify | `IMPROVEMENT_METRIC_QUERIES`, `compute_improvement_metrics`, `AUTONOMY_QUALITY_FIELDS` |
| `src/walk/telemetry/protocols.py` | modify | `TelemetryManager.improvement_metrics`, `LedgerManager.report` (`since` keyword) |
| `src/walk/telemetry/service.py` | modify | `DefaultTelemetryManager.improvement_metrics`, `DefaultLedgerManager.report` |
| `src/walk/telemetry/reports.py` | modify | `ImprovementReportQuery` (new sections, `since`) |
| `src/walk/telemetry/__init__.py` | modify | re-exports |
| `src/walk/improvement/models.py` | modify | `VersionOutcome` |
| `src/walk/improvement/protocols.py` | modify | `ImprovementManager.measure_version` |
| `src/walk/improvement/service.py` | modify | `DefaultImprovementManager.measure_version` |
| `src/walk/improvement/__init__.py` | modify | re-exports |
| `src/walk/cli/cmd_improvement.py` | modify | `metrics` |
| `src/walk/cli/cmd_report.py` | modify | `report_app` (`improvement … --since`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.14 `improvement_metrics`, `report(since=)`; §1.15 `measure_version`; §6 rows) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§4.12 `ImprovementMetrics`; §4.14 `VersionOutcome`) |
| `tests/telemetry/test_improvement_metrics.py` | create | — |
| `tests/telemetry/test_reports_improvement_metrics.py` | create | — |
| `tests/improvement/test_service_measure_version.py` | create | — |
| `tests/cli/test_cmd_improvement_metrics.py` | create | — |
| `tests/cli/test_cmd_report_improvement_since.py` | create | — |

#### Interface contract
```python
# src/walk/telemetry/models.py
class ImprovementMetrics(WalkModel):
    """§116, computed only from ledger_events (+ cost_records)."""
    period_start: datetime | None
    period_end: datetime | None
    phase_id: PhaseId | None
    version_filter: str | None = Field(description="'<KIND>/<name>@<version>' when restricted to events stamped with that version")
    first_pass_completion_rate: float      # COMPLETE items with fix_loops == 0 / COMPLETE items
    rework_rate: float                     # items that entered REWORK / items that entered READY_FOR_REVIEW
    bug_density: float                     # BUG_CREATED / COMPLETE stories+tasks
    escaped_defect_rate: float             # bugs created against items already COMPLETE / BUG_CREATED
    fix_loops: float                       # mean fix_loops of COMPLETE items
    debate_rounds: float                   # mean rounds per DEBATE_RESOLVED
    user_escalation_rate: float            # ESCALATION_RAISED level 3 / DECISION_RECORDED
    human_intervention_rate: float         # (USER_OVERRIDE + APPROVAL_DECIDED by USER) / COMPLETE items
    context_hit_rate: float                # runs without CONTEXT_FRESHNESS stale/invalid / AGENT_RUN_STARTED
    context_stale_rate: float              # 1 − context_hit_rate
    handoff_success: float                 # RECOVERY_RESUMED runs ending COMPLETED / RECOVERY_RESUMED
    fallback_success: float                # runs with MODEL_FALLBACK ending COMPLETED / runs with MODEL_FALLBACK
    build_success: float                   # BUILD_RESULT ok / BUILD_RESULT
    task_duration_s: float                 # mean Σ AGENT_RUN_ENDED.duration_ms per COMPLETE item / 1000
    token_usage: int                       # Σ tokens of COST_RECORDED
    cost_per_task: float                   # Σ cost_usd / COMPLETE stories+tasks
    cost_per_feature: float                # Σ cost_usd / COMPLETE features
    agent_blocked_time_s: float            # Σ time between → BLOCKED and the next transition out of BLOCKED

# src/walk/telemetry/metrics.py
IMPROVEMENT_METRIC_QUERIES: dict[str, str]           # one read-only SQL per ImprovementMetrics metric field (18)
AUTONOMY_QUALITY_FIELDS: tuple[str, ...] = ("human_intervention_rate", "first_pass_completion_rate",
                                            "escaped_defect_rate", "user_escalation_rate")    # §117: shown together
async def compute_improvement_metrics(db: Database, *, phase_id: PhaseId | None = None, since: datetime | None = None,
                                      until: datetime | None = None, version: tuple[str, str] | None = None) -> ImprovementMetrics: ...

# src/walk/telemetry/protocols.py — additions
# TelemetryManager
async def improvement_metrics(self, *, phase_id: PhaseId | None = None, since: datetime | None = None,
                              until: datetime | None = None, version: tuple[str, str] | None = None) -> ImprovementMetrics: ...
# LedgerManager.report gains: since: datetime | None = None   (used by kind "improvement" only; ignored otherwise)

# src/walk/improvement/models.py
class VersionOutcome(WalkModel):
    """§106 'Measured Outcome' of one behaviour version."""
    key: str
    version: str
    baseline_version: str | None
    metrics: ImprovementMetrics
    baseline_metrics: ImprovementMetrics | None
    deltas: dict[str, float]          # metric − baseline metric, for the 18 metric fields

# src/walk/improvement/protocols.py — addition
async def measure_version(self, key: str, version: str, *, since: datetime | None = None) -> VersionOutcome: ...
```
CLI: `walk improvement metrics [--phase ID] [--since ISO] [--until ISO] [--version KIND/NAME@VERSION] [--json]`; `walk report improvement SUBJECT_ID [--since ISO] [--write] [--json]`.

#### Behavior
1. Every metric is computed by one read-only SQL statement in `IMPROVEMENT_METRIC_QUERIES` over `ledger_events` (and `cost_records` for cost/tokens); no other table and no `.ai/` file is read (§83, Inv. 9). Ratios with a zero denominator are `0.0`; never `NaN`.
2. Filters: `phase_id` restricts to events with that `phase_id` (or descendants' events, the E01-S06 `METRIC_QUERIES` rule); `since`/`until` restrict `at`; `version=("<KIND>/<name>", "<v>")` restricts to events whose `behavior_versions` JSON has that key equal to `v` (`json_extract(behavior_versions, '$."<key>"')`). Filters combine with AND.
3. Where `RetrospectiveMetrics` already defines the same figure for the same filter (first-pass rate, debate rounds, fallbacks, build failures, mean task duration, cost), `ImprovementMetrics` equals the value derived from `TelemetryManager.metrics(...)` — asserted by test, so the two never diverge.
4. §117: every renderer of `ImprovementMetrics` (report section, CLI table) prints the `AUTONOMY_QUALITY_FIELDS` together in one block titled `Autonomy quality`; `human_intervention_rate` never appears outside that block.
5. `measure_version(key, version)`: metrics for events stamped with `version`; `baseline_version` = the other version of the same key with the most stamped events before the first event of `version` (`None` when none); `deltas` = metric − baseline for every field (0.0 when no baseline). Read-only.
6. `ImprovementReportQuery` adds sections: `Improvement metrics` (all non-autonomy fields), `Autonomy quality` (rule 4), `Version outcomes` (one row per key/version that appears in a `BEHAVIOR_VERSION_CHANGED` event, with first-pass, rework, cost-per-task and their deltas versus the baseline computed with the same SQL — telemetry does not import improvement), `User feedback signals` (§118: counts of `PHASE_GATE_DECISION` REWORK/CHANGE, `USER_OVERRIDE` by `command`, `DECISION_RECORDED` with status `OVERRIDDEN`, and `user_override`/`repeated_phase_rework` observations from E10-S02); existing E09-S02 sections unchanged; `since` restricts every section.
7. `walk improvement metrics` prints the 18 metrics in two blocks (`Autonomy quality`, `Other`) or JSON of `ImprovementMetrics`; `--version` without `@` → exit 1.
8. `walk report improvement DEMO --since 2026-10-01T00:00:00Z --write` writes the same path as E09-S02 (`.ai/reports/improvement/DEMO.md`); output is byte-identical for identical ledger and frozen clock.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `ImprovementMetrics` When its metric fields are listed Then exactly 18 and `IMPROVEMENT_METRIC_QUERIES` has one entry per field | `tests/telemetry/test_improvement_metrics.py::test_metric_fields_cover_section_116` |
| 2 | Given a seeded ledger (4 COMPLETE stories, 1 with a fix loop, 2 bugs of which 1 escaped, 3 builds with 1 failure) When `compute_improvement_metrics` Then `first_pass_completion_rate == 0.75`, `escaped_defect_rate == 0.5`, `build_success == 2/3` | `tests/telemetry/test_improvement_metrics.py::test_seeded_ledger_values` |
| 3 | Given an empty ledger When computed Then every ratio is `0.0` and no exception | `tests/telemetry/test_improvement_metrics.py::test_zero_denominators_are_zero` |
| 4 | Given the seeded ledger When comparing with `TelemetryManager.metrics()` Then first-pass rate, debate rounds, mean duration and total cost agree | `tests/telemetry/test_improvement_metrics.py::test_consistent_with_retrospective_metrics` |
| 5 | Given events stamped `WORKFLOW/feature_workflow` `1.0` and `1.1` When computed with `version=("WORKFLOW/feature_workflow", "1.1")` Then only `1.1` events count | `tests/telemetry/test_improvement_metrics.py::test_version_filter` |
| 6 | Given a `BLOCKED` interval of 600 s When computed Then `agent_blocked_time_s == 600` | `tests/telemetry/test_improvement_metrics.py::test_blocked_time` |
| 7 | Given the metrics module When grepping its SQL Then no `INSERT`, `UPDATE`, `DELETE` | `tests/telemetry/test_improvement_metrics.py::test_queries_read_only` |
| 8 | Given the seeded ledger When `ImprovementReportQuery.run("DEMO")` Then sections `Improvement metrics`, `Autonomy quality`, `Version outcomes`, `User feedback signals` exist and `human_intervention_rate` appears only in `Autonomy quality` | `tests/telemetry/test_reports_improvement_metrics.py::test_report_sections_and_autonomy_block` |
| 9 | Given 2 REWORK gate decisions and 3 `USER_OVERRIDE` `work.cancel` When reported Then `User feedback signals` shows 2 and 3 | `tests/telemetry/test_reports_improvement_metrics.py::test_user_feedback_signals_counts` |
| 10 | Given events under `1.0` then `1.1` When `measure_version("WORKFLOW/feature_workflow", "1.1")` Then `baseline_version == "1.0"` and `deltas["first_pass_completion_rate"]` equals the difference of the two computed rates | `tests/improvement/test_service_measure_version.py::test_measure_version_against_baseline` |
| 11 | Given a version with no predecessor When measured Then `baseline_version is None` and all deltas `0.0` | `tests/improvement/test_service_measure_version.py::test_measure_version_without_baseline` |
| 12 | Given `walk improvement metrics --json` Then valid `ImprovementMetrics` JSON; given `--version WORKFLOW/feature_workflow` Then exit 1 | `tests/cli/test_cmd_improvement_metrics.py::test_metrics_cli_json_and_bad_version` |
| 13 | Given `walk report improvement DEMO --since <iso> --write` twice with a frozen clock Then the same file, byte-identical, and events before `since` excluded | `tests/cli/test_cmd_report_improvement_since.py::test_report_improvement_since_reproducible` |

#### Evidence required
- Quality gate output.
- Demo on the E07/E09 gate fixture repo: `walk improvement metrics`, `walk improvement metrics --version WORKFLOW/feature_workflow@1.0 --json`, `walk report improvement DEMO --write` and the written file's `Autonomy quality` block.

#### Notes
- §83 (reports from events only), Inv. 9; E09-S06 Notes deferred the §116 metrics not in `RetrospectiveMetrics` to this story; §117 is enforced by rendering rule 4, not by omitting the metric.
- Escaped defect = a bug whose `WORK_ITEM_CREATED` payload names a related item that was already `COMPLETE` (or its feature) at bug creation time `(verify E03-S14 bug payload keys)`.
- `NEW NAME:` `ImprovementMetrics` (`walk.telemetry.models`); `IMPROVEMENT_METRIC_QUERIES`, `compute_improvement_metrics`, `AUTONOMY_QUALITY_FIELDS` (`walk.telemetry.metrics`); `TelemetryManager.improvement_metrics`; `LedgerManager.report(since=…)`; `VersionOutcome`, `ImprovementManager.measure_version`; `walk improvement metrics`; `walk report improvement --since`.
- Commit subject: `feat: add improvement metrics and version outcomes (E10-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-S10 — Epic gate: observation → versioned rollout (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §94, §96, §97, §102–§111, §114–§116, §120, §121, §136 (Improvement loop), §137 (Inv. 9, 13)
**Depends on:** E10-S06, E10-S07, E10-S08, E10-S09
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end scenario with fakes proves the §94 loop and the §121 invariant: a ledger signal becomes a project observation, is explicitly promoted to kernel scope, feeds a MEDIUM candidate approved by the Product Owner, becomes `feature_workflow 1.1` measured by an experiment and moved to `LIMITED` with a changelog entry, is pinned and actually used by the project (ledger events carry the version), is measured, and is rolled back to `DRAFT` with the pin restored.

#### Scope
- In: `tests/e2e/test_e10_gate.py`; fixture `e10_scenario` / model `E10Scenario`; treatment table data file.
- Out: production code (defects → `E10-Bxx` bugfix stories); `DEFAULT` promotion (needs phases under both versions; covered by E10-S05 unit tests).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e10_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e10_scenario` fixture, `E10Scenario` `(verify: builds on the E07/E09 scenario helpers)` |
| `tests/e2e/data/feature_workflow_1_1.yaml` | create | — (copy of the builtin `feature_workflow` table with only `version: "1.1"` changed; a version-only change is enough to prove loading, stamping and rollback) |

#### Interface contract
Fixture `e10_scenario(tmp_game_repo, tmp_walk_home) -> E10Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `project_key: ProjectKey` (`"DEMO"`), `phase_id: PhaseId` (`PHASE-01`), `fallback_item: WorkItemId`, `walk_home: Path`, `treatment_table: Path`. Settings: `PROCESS_ARCHITECT` enabled in `policies.yaml`; `FakeModelAdapter` providers `fake-codex/sim` (fails twice on `fallback_item`, WBS §3.6 injectable failure) and `fake-claude/sim`; `LocalWorkProvider`; real temporary git repository; `FakeClock`; `SequentialIdFactory`. Actors: `USER` (`name: "owner"`), `PRODUCT_OWNER`, `PROCESS_ARCHITECT` used through `ImprovementManager` and the `walk improvement …` CLI exactly as specified in E10-S01…S09.

#### Behavior
Scenario steps (each a test, executed in order via the fixture's cached state):
1. A one-phase fake run completes with two `MODEL_FALLBACK` events on `fallback_item`; when the phase enters `EVIDENCE_REVIEW`, `phase_review_detect_signals` creates `OBS-0001` (`source_signal == "repeated_fallback"`, `scope == PROJECT`, `ledger_seq_refs` = the two fallback seqs); the retrospective `RETRO-PHASE-01` exists and a carrier TASK for `PROCESS_ARCHITECT` is created.
2. The carrier run (fake PROCESS_ARCHITECT output with a summary) completes via `analysis_done`; `RETRO-PHASE-01` has a non-empty `narrative_markdown`.
3. Before promotion `$WALK_HOME/.improvement/` contains no observation, candidate or experiment documents; `walk improvement promote OBS-0001` creates `OBS-K-0001` in the kernel DB and folder, and `OBS-0001.promoted_to == "OBS-K-0001"`.
4. A KERNEL candidate `IMP-01` built from `OBS-K-0001` (`candidate_from_observations`, risk MEDIUM, all §98 fields) is proposed and submitted; a PENDING `IMPROVEMENT` approval for `PRODUCT_OWNER` exists; ORCHESTRATOR review → `PermissionDenied`; PRODUCT_OWNER review with a note → `APPROVED`, `decision_id` points to an `ACCEPTED` `PROCESS` decision.
5. `register_version(BehaviorVersion(kind=WORKFLOW, name="feature_workflow", version="1.1", stage=DRAFT, source_path=treatment_table, candidate_id="IMP-01"))` → `DRAFT`; USER `start_experiment(AB_BY_WORK_ITEM_HASH, metrics=["cost_usd", "rework"])` → `EXP-0001`; `set_stage(EXPERIMENTAL, by=PROCESS_ARCHITECT)`; `end_experiment` → verdict `INSUFFICIENT_DATA` with one evidence id; `set_stage(LIMITED, by=PRODUCT_OWNER, changed="…")` → `LIMITED`, `kernel_changelog` row with `reason == "IMP-01"`, `changelog/<release>.md` contains `IMP-01`.
6. USER `walk improvement pin WORKFLOW/feature_workflow 1.1 --note opt-in` → `kernel-versions.yaml` pins `1.1`; the kernel is rebuilt (`build_kernel` with the same settings) and `KernelVersionPins.validate` passes; one new story runs to `COMPLETE`; every ledger event written after the rebuild has `behavior_versions["WORKFLOW/feature_workflow"] == "1.1"`.
7. `walk improvement metrics --version WORKFLOW/feature_workflow@1.1 --json` returns metrics computed only from the post-rebuild events; `measure_version("WORKFLOW/feature_workflow", "1.1").baseline_version == "1.0"`; `walk report improvement DEMO --write` lists `feature_workflow 1.1` under `Version outcomes`.
8. §106 provenance by SQL alone: from `BEHAVIOR_VERSION_CHANGED(1.1, LIMITED)` → `candidate_id IMP-01` → `IMPROVEMENT_CANDIDATE` with `decision_id` → `DECISION_RECORDED` → `observation_ids [OBS-K-0001]` → promotion event `promoted_from OBS-0001` → `IMPROVEMENT_OBSERVATION` with the fallback `ledger_seq_refs`; every hop resolves.
9. PRODUCT_OWNER `walk improvement rollback WORKFLOW/feature_workflow 1.1 --reason gate` → stage `DRAFT`, pin reverted to `1.0`; after a kernel rebuild new events carry `"1.0"`.
10. Invariant 13: no file under `src/walk/` package defaults, `.ai/agents/` or the builtin `feature_workflow.yaml` changed during the scenario (hashes before/after equal); every behaviour change in the ledger is a `BEHAVIOR_VERSION_CHANGED` event with a `candidate_id`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given two fallbacks on one story When the phase enters review Then `OBS-0001` with signal `repeated_fallback`, PROJECT scope and both fallback seqs | `tests/e2e/test_e10_gate.py::test_fallback_signal_creates_project_observation` |
| 2 | Given PROCESS_ARCHITECT enabled When the carrier run completes Then `RETRO-PHASE-01` has a narrative | `tests/e2e/test_e10_gate.py::test_phase_retrospective_has_narrative` |
| 3 | Given no promotion yet Then the kernel home has no learning documents; after `walk improvement promote OBS-0001` Then `OBS-K-0001` exists and `OBS-0001` is PROMOTED | `tests/e2e/test_e10_gate.py::test_explicit_promotion_only` |
| 4 | Given `IMP-01` (MEDIUM) under review When ORCHESTRATOR reviews Then `PermissionDenied`; when PRODUCT_OWNER approves Then APPROVED with a PROCESS decision | `tests/e2e/test_e10_gate.py::test_medium_candidate_approved_by_po_only` |
| 5 | Given the approved candidate When registered, experimented and staged Then `feature_workflow 1.1` is `LIMITED` with a changelog entry naming `IMP-01` | `tests/e2e/test_e10_gate.py::test_version_reaches_limited_with_changelog` |
| 6 | Given the pin to `1.1` and a kernel rebuild When a story completes Then all new events carry `WORKFLOW/feature_workflow == "1.1"` | `tests/e2e/test_e10_gate.py::test_pinned_version_used_and_stamped` |
| 7 | Given version-filtered metrics When computed Then only `1.1` events count, `baseline_version == "1.0"`, and the improvement report lists the version outcome | `tests/e2e/test_e10_gate.py::test_version_outcome_measured` |
| 8 | Given the ledger When the provenance hops of Behavior 8 are followed by SQL Then each hop resolves to exactly one row | `tests/e2e/test_e10_gate.py::test_improvement_provenance_chain_by_sql` |
| 9 | Given PRODUCT_OWNER rollback When the kernel is rebuilt Then stage `DRAFT`, pin `1.0`, new events stamped `"1.0"` | `tests/e2e/test_e10_gate.py::test_rollback_restores_previous_behavior` |
| 10 | Given hashes of defaults, `.ai/agents/` and builtin tables before the scenario When compared after Then equal, and every `BEHAVIOR_VERSION_CHANGED` has a `candidate_id` | `tests/e2e/test_e10_gate.py::test_no_silent_behavior_modification` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e10_gate.py` (10 passed).
- Demo transcript on the fixture repo with `WALK_HOME=<tmp>`: `walk improvement observations`, `walk improvement promote OBS-0001`, `walk improvement candidates list`, `walk improvement versions --kind WORKFLOW`, `walk version`, `walk ledger query --kind BEHAVIOR_VERSION_CHANGED`, `cat $WALK_HOME/.improvement/changelog/<release>.md`, `walk improvement rollback WORKFLOW/feature_workflow 1.1 --reason demo`.

#### Notes
- WBS §9 maps "Improvement loop" of §136 to this story. The WBS gate wording "`register_version` creates `feature_workflow 1.1` at `LIMITED`" is realised as register (DRAFT) → experiment → `EXPERIMENTAL` → `LIMITED`, because the INTERFACES §3.7 table has no direct DRAFT → LIMITED edge.
- Gate uses only fakes and temporary directories (`tmp_walk_home`); no network; the real `~/.walk` is never touched. Any production change needed is a separate `bugfix` story; this commit touches tests only.
- `NEW NAME:` `e10_scenario` fixture, `E10Scenario` (`tests/e2e/conftest.py`); data file `tests/e2e/data/feature_workflow_1_1.yaml`.
- Commit subject: `feat: add epic 10 gate test for improvement rollout (E10-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E10-R01 — Review E10

**Status:** TODO
**Type:** docs
**Requirements:** §121, §137 (Inv. 9, 13), §103, §104, §110
**Depends on:** E10-S10
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (a different model than the E10 implementer where possible, §23) verifies every E10 story against the Definition of Done, Invariant 13 and the §121 continuous-improvement invariant, recording defects as `E10-Bxx` bugfix stories.

#### Scope
- In: stories E10-S01…S10 and their commits; `INTERFACES.md`, `DOMAIN-MODEL.md`, `ARCHITECTURE.md`, ADR-0008 (addendum) deltas; WBS §3.4/§6 entries from this epic; architecture tests listed below.
- Out: fixing defects (each becomes `E10-Bxx`); production code.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-10-continuous-improvement.md` | modify | — (review record appended; `E10-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/ARCHITECTURE.md`, `docs/01-architecture/adr/ADR-0008-learning-separation-and-behavior-versioning.md` | modify (only if drift found) | — |
| `tests/architecture/test_improvement_boundaries.py` | create | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5, plus the checks under Behavior.

#### Behavior
1. For each story: `git show <sha>`; Files table equals changed files (extra files need commit-body justification); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules.
2. Layering (ARCHITECTURE §2.2): `src/walk/improvement/` imports nothing from `walk.runtime`, `walk.orchestrator`, `walk.permissions`, `walk.tools`, `walk.integrations`, `walk.context`; `src/walk/workflow/` and `src/walk/runtime/` import nothing from `walk.improvement`.
3. Invariant 13 / §103: no module in `src/walk/improvement/` opens for writing any path under the package defaults (`agents/defaults`, `workflow/tables`, `skills/builtin`, `agents/templates`, `tools/defaults`, `model_router/defaults`) or `.ai/agents/`; `register_version` writes only under `$WALK_HOME/.improvement/versions/`; every `BEHAVIOR_VERSION_CHANGED` write path requires a `candidate_id`.
4. §110 / ADR-0008 D-2: `promote` has no caller other than the CLI (E10-S06 AC 7 still green); `detect_signals` creates only `PROJECT` observations.
5. §104: `APPROVER_TIERS`, `RISK_FLOOR`, `PIN_RISK_BY_KIND` match ADR-0008 D-6/D-4 and the review record lists any deviation for the owner.
6. Ledger write points (ARCHITECTURE §4.3): `IMPROVEMENT_OBSERVATION`, `IMPROVEMENT_CANDIDATE`, `BEHAVIOR_VERSION_CHANGED`, `PATTERN_REGISTERED`, `SHADOW_EVALUATION` are appended only from `walk.improvement.service`.
7. ADR-0008 Addendum A exists and its constants equal `MIN_ARM_SIZE`, `IMPROVEMENT_THRESHOLD`, `REGRESSION_TOLERANCE` in code.
8. `NEW NAME:` items of E10 (header table and story Notes, including the `walk.workflow.analysis` relocation) are present in WBS §6 or listed in the review note for the architect; shared-file merges with E11-S01 (`story_workflow.yaml` version) are consistent.
9. Defects → `E10-Bxx` stories using the template.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E10 story When the DoD checklist is applied Then every box is checked or an `E10-Bxx` story exists | manual checklist recorded in this story's Evidence |
| 2 | Given `src/walk/improvement` When its imports are parsed Then none of `walk.runtime`, `walk.orchestrator`, `walk.permissions`, `walk.tools`, `walk.integrations`, `walk.context` | `tests/architecture/test_improvement_boundaries.py::test_improvement_imports_respect_layer_table` |
| 3 | Given `src/walk/workflow` and `src/walk/runtime` When their imports are parsed Then no `walk.improvement` | `tests/architecture/test_improvement_boundaries.py::test_lower_layers_do_not_import_improvement` |
| 4 | Given `src/walk/improvement` When grepping write calls (`write_text`, `open(… "w"`, `atomic_write`) Then no target path is built from package default folders or `.ai/agents` | `tests/architecture/test_improvement_boundaries.py::test_no_behavior_artifact_writes` |
| 5 | Given `src/walk` When grepping `LedgerEventKind.(IMPROVEMENT_OBSERVATION\|IMPROVEMENT_CANDIDATE\|BEHAVIOR_VERSION_CHANGED\|PATTERN_REGISTERED\|SHADOW_EVALUATION)` in `append` calls Then only `improvement/service.py` matches | `tests/architecture/test_improvement_boundaries.py::test_improvement_events_single_write_point` |
| 6 | Given ADR-0008 Addendum A and `walk.improvement.experiments` When constants are compared Then equal | manual checklist recorded in this story's Evidence |
| 7 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % and `tests/e2e/test_e10_gate.py` passing | manual checklist recorded in this story's Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after the review commit.
- List of `E10-Bxx` stories created (or "none").

#### Notes
- Tests 2–5 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- Commit subject: `docs: review epic 10 stories E10-S01..S10 (E10-R01)`.

#### Evidence (filled by implementer)
_pending_

---

