# EPIC-11 — Release

**Roadmap stage:** §135 Stage 11
**Goal.** RC lifecycle, UA/Release role, store metadata and publishing behind protected actions: a release candidate is built for every target, passes final QC (rejections re-enter the bug loop and produce the next RC), store metadata is generated and approved as an artifact, and publishing runs only after explicit user approval recorded in the ledger.
**Requirements.** §10.9, §75–§77, §92 (`store.publish`), §62 (release builds), §63–§64 (final QC and rejection bugs), §33 (store metadata as approved artifacts), §136 / §1 flow (`RELEASE CANDIDATE → FINAL QC → STORE / RELEASE`), §137 (Inv. 7, 9, 10, 14).
**Epic gate.** `tests/e2e/test_e11_gate.py`: RC1 is built (fake Unity), QC rejects creating a BLOCKER bug, bug fixed, RC2 passes, `release` requires `walk approve`, `RELEASED` with `RC_TRANSITION` ledger trail.
**Branching.** Every story uses `story/<ID>-<slug>` + worktree (COMMIT-POLICY §4); merge `--no-ff` after E11-R01.
**Preconditions.** E08-R01 and E09-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green; E11-X01 committed before any `E11-S*` story starts (WBS §2 rule 3).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E11-X01 | Refine E11 against codebase | E08-R01, E09-R01 | LOW |
| E11-S01 | UA_RELEASE constitution and routing | E11-X01 | MEDIUM |
| E11-S02 | RC lifecycle service and `walk rc create/list/show` | E11-X01, E01-S11 | HIGH |
| E11-S03 | RC build pipeline for all targets | E11-S02, E03-S11 | MEDIUM |
| E11-S04 | Final QC on RC and rejection bugs | E11-S03, E03-S15 | MEDIUM |
| E11-S05 | Store metadata as approved artifacts | E11-S01, E02-S12 | MEDIUM |
| E11-S06 | Publishing integrations behind `store.publish` | E11-S05, E02-S11 | HIGH |
| E11-S07 | Polish phase template | E11-X01, E07-S05 | LOW |
| E11-S08 | Epic gate: RC1 reject → RC2 release (e2e) | E11-S04, E11-S06, E11-S07 | MEDIUM |
| E11-R01 | Review E11 | E11-S08 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (especially §3.4 payload keys, §3.5 ledger vs hooks, §3.6 fakes, §3.7 CLI layout — `rc` command group).
2. `INTERFACES.md` §3.6 (`rc_workflow`), §3.2 (`story_workflow`, extended here by one row), §4 (routing table, extended here), §1.3 (`WorkflowManager.rc_event`), §1.10 (`PermissionManager`), §1.8 (`approve_artifact`, `write_report`), §2.4 (`UnityProvider.build`, `CiProvider.run_pipeline`), §6 (CLI).
3. `DOMAIN-MODEL.md` §3 (`ReleaseCandidateState`, `ApprovedArtifactKind`, `EvidenceKind`), §4.1 (`ReleaseCandidate`, `Phase`), §4.5 (`ProtectedAction`, `ApprovalRequest`), §4.7 (`ApprovedArtifact`), §6.2 (`release_candidates`).
4. `ARCHITECTURE.md` §4.2 (enforcement point), §4.3 (`RC_TRANSITION` write point), §6 (protected actions, `store.publish`), §7 (Inv. 7, 9, 10, 14), §8 (`.ai/reports/`, `.ai/approved/`).
5. ADR-0006 (D-2 kernel executes side effects, D-3 protected actions cannot be downgraded, D-4 approval pauses the run), ADR-0009 (D-6 Unity batchmode, D-8 credentials), ADR-0013 (constitution schema).
6. `requirements/WAL_K_REQ.md` §10.9, §75, §76, §77, §92; the §1 flow lines 51–61.

Parallel sets (WBS §8): `{S01→S05} ∥ {S02→S03→S04} ∥ {S07}`; S06 after S05 and S02; S08 after S04, S06, S07.

**Carrier-task mechanism (binding for S01, S04, S05, S06).** Release-candidate work has no work item of its own, but every agent run needs one (`AgentExecutor.start(agent, item, purpose)`). Each RC step that needs an agent is therefore represented by a `TASK` work item created by `ReleaseManager` with labels `walk-release:<RC-id>` and `walk-release-step:<qc|ua-review|publish>`. The `TaskRouter` routes such tasks by step (S01), the carrier completes `READY → COMPLETE` through one new `story_workflow` row `release_step_done` (S01), and `ReleaseManager.on_run_completed` maps the applied `AgentOutput` onto `rc_event(...)` (S04–S06). Carrier tasks never enter `IMPLEMENTING`; they are scheduled like any `READY` task.

---

### E11-X01 — Refine E11 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §135 (Stage 11), §58, §76, §77
**Depends on:** E08-R01, E09-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E11 story's Files table, interface reference and dependency is re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E10, and the corrected epic file plus WBS rows are committed before E11-S01 starts.

#### Scope
- In: path/symbol verification for all E11 stories; resolution of the assumptions listed under Behavior; WBS §3.4 payload-key rows and §6 `NEW NAME:` rows for E11; story `BLOCKED` marks where an assumption fails.
- Out: any source change; re-scoping stories (a story that cannot be made ready is marked `BLOCKED` with the reason, never rewritten into something else).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-11-release.md` | modify | — (corrected Files tables, interface references, Notes) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§3.4 rows for RC payload keys, §6 register rows for E11 `NEW NAME:` items, §5 status of E11-X01) |

#### Interface contract
Refine protocol (WBS §1 `Exx-Xyy`, §2 rule 3): read `src/walk/` and `INTERFACES.md`, then for each story S01–S08: every `modify` path exists; every `create` path does not exist; every referenced symbol in a `modify` row exists with the signature the story assumes; every `INTERFACES.md §x.y` reference resolves; every dependency is `DONE` in WBS §5.

#### Behavior
Assumptions made at planning time (E03-S06…S20, E05–E10 stories were not yet written) that this task must confirm or correct in the epic file:
1. `TaskRouter` implementation lives in `src/walk/orchestrator/router.py` (E03-S07) and `route()` can be extended by label-based rows (S01).
2. `OutputApplier` (`src/walk/runtime/applier.py`, E03-S08) chooses the implied workflow event from `(kind, state, output.status)`; S01 adds the `release_step_done` mapping there.
3. `LocalCiProvider` lives in `src/walk/integrations/ci.py` (E03-S11) and job names are strings; S03 assumes the form `build:<BuildTarget>` with `development=False` — confirm or rename.
4. `UnityBatchProvider` is `src/walk/integrations/unity/provider.py` and the editor package file is `unity/com.walk.ci/Editor/WalkCI.cs` (E03-S10); `tests/fakes/fake_unity_provider.py` exists (WBS §3.6).
5. `DefaultOrchestrator` has a single run-completion path where QC output is handled (E03-S14; ARCHITECTURE §4.3 `QC_RESULT`) — S04 hooks `ReleaseManager.on_run_completed` there.
6. `KernelStatus.build_status` is unset by E09-S04 and may be filled by S02.
7. `BehaviorVersionCatalog` (`src/walk/improvement/catalog.py`, E10-S05) derives workflow/template versions from file front matter; if versions are hard-coded, S01/S04/S05 must list the catalog file as `modify`.
8. `walk.persistence.atomic_write` (E01-S04) exists for non-`.ai/` file writes (S05 writes `.walk/release/<rc>/store-metadata.json`).
9. `EvidenceManager.for_phase(phase_id)` has no `kinds` filter (INTERFACES §1.14); S03/S05 filter in code.
10. `ToolInvoker.invoke` dispatches `KERNEL` tools to `IntegrationManager` through a name → handler map (E01-S26); S06 registers `store.validate` / `store.publish` handlers in that map — confirm the registration mechanism.
11. Phase creation: confirm whether E06-S04/E07 added a `walk phase create` command; if yes, S07 modifies it instead of creating one.
12. ADR-0011 D-3 model-policy defaults: confirm which row S01 copies for `UA_RELEASE` (planned: the `PRODUCT_OWNER` row).
13. Record in WBS §3.4 the payload keys defined in E11-S02 and in WBS §6 every `NEW NAME:` item of E11 (listed in each story's Notes).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every E11 story Files table When each path is checked against `src/walk/` and `tests/` Then every `modify` path exists and every `create` path is absent, or the row is corrected | manual checklist (story → path → OK/corrected) recorded in this task's Evidence |
| 2 | Given every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference in E11 When opened Then the section exists and names the referenced symbol | manual checklist recorded in Evidence |
| 3 | Given every `Depends on` id of E11 stories When looked up in WBS §5 Then status is `DONE` (or the depending story is marked `BLOCKED` with the id) | manual checklist recorded in Evidence |
| 4 | Given Behavior items 1–13 When each is confirmed or corrected Then the epic file reflects the real path/symbol and WBS §3.4/§6 contain the E11 rows | diff of the refine commit recorded in Evidence |

#### Evidence required
- Checklist table (story → files verified → interface refs verified → deps verified → corrections made).
- `git show --stat` of the refine commit.

#### Notes
- No production code; no test files. A story that depends on a missing symbol is set `BLOCKED` with `pending <symbol> (<story that should create it>)`.
- Commit subject: `docs: refine epic 11 stories (E11-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S01 — UA_RELEASE constitution and routing

**Status:** TODO
**Type:** feat
**Requirements:** §10.9, §9, §12, §31, §127, §137 (Inv. 1, 7)
**Depends on:** E11-X01
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The `UA_RELEASE` role exists as a kernel-default constitution, runtime policy and permission rule set, and release carrier tasks (`walk-release-step:*`) are routed to the right role and purpose and complete through one data-declared `story_workflow` transition.

#### Scope
- In: `ua_release.md` constitution; `policies.yaml` and `permissions/defaults.yaml` rows for `UA_RELEASE`; `walk.workflow.release` label helpers; `TaskRouter` release rows; `story_workflow.yaml` row `release_step_done` + guards; `OutputApplier` implied-event mapping for carrier tasks.
- Out: `ReleaseManager` and carrier-task creation (E11-S02/S04/S05/S06); `store.*` tool specs and handlers (E11-S06); market-feedback participation before release (§10.9 "MAY", not planned).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/defaults/ua_release.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`UA_RELEASE` role entry) |
| `src/walk/permissions/defaults.yaml` | modify | — (`UA_RELEASE` rows, table below) |
| `src/walk/workflow/release.py` | create | `ReleaseStep`, `RELEASE_LABEL_PREFIX`, `RELEASE_STEP_LABEL_PREFIX`, `release_labels`, `rc_id_of`, `release_step_of` |
| `src/walk/workflow/guards.py` | modify | `is_release_step`, `output_status_is_verdict` |
| `src/walk/workflow/tables/story_workflow.yaml` | modify | — (row `release_step_done`; `version: "1.1"`) |
| `src/walk/workflow/__init__.py` | modify | re-export `ReleaseStep`, `release_step_of`, `rc_id_of` |
| `src/walk/orchestrator/router.py` | modify | `DefaultTaskRouter.route` (release rows), `RELEASE_ROUTES` |
| `src/walk/runtime/applier.py` | modify | — (`release_step_done` implied event for carrier tasks) |
| `src/walk/improvement/catalog.py` | modify | — (only if `WORKFLOW/story_workflow` version is hard-coded; E11-X01 item 7) |
| `tests/agents/test_defaults_ua_release.py` | create | — |
| `tests/permissions/test_defaults_ua_release.py` | create | — |
| `tests/workflow/test_release_labels.py` | create | — |
| `tests/workflow/test_tables.py` | modify | — (story table row count + version) |
| `tests/orchestrator/test_router_release.py` | create | — |
| `tests/runtime/test_applier_release.py` | create | — |

#### Interface contract
```python
# src/walk/workflow/release.py
class ReleaseStep(StrEnum):
    QC = "qc"                 # final QC run (E11-S04)
    UA_REVIEW = "ua-review"   # store metadata review (E11-S05)
    PUBLISH = "publish"       # approval-gated publish run (E11-S06)

RELEASE_LABEL_PREFIX = "walk-release:"            # + ReleaseCandidateId
RELEASE_STEP_LABEL_PREFIX = "walk-release-step:"  # + ReleaseStep value

def release_labels(rc_id: ReleaseCandidateId, step: ReleaseStep) -> list[str]: ...
def rc_id_of(item: WorkItem) -> ReleaseCandidateId | None: ...
def release_step_of(item: WorkItem) -> ReleaseStep | None: ...

# src/walk/orchestrator/router.py
RELEASE_ROUTES: dict[ReleaseStep, tuple[AgentRole, str]] = {
    ReleaseStep.QC: (AgentRole.QC, "QC"),
    ReleaseStep.UA_REVIEW: (AgentRole.UA_RELEASE, "REVIEW"),
    ReleaseStep.PUBLISH: (AgentRole.UA_RELEASE, "IMPLEMENT"),
}
```
`story_workflow.yaml` new row (INTERFACES §3.2 addition, table version `1.1`): `READY | release_step_done | is_release_step, output_status_is_verdict, required_evidence_present | COMPLETE | ON_TASK_COMPLETE | KERNEL`.

Constitution front matter (ADR-0013 D-2): `id: UA_RELEASE`, `role: UA_RELEASE`, `version: "1.0"`, `identity: UA / Release Manager`, `mission: Protect market readiness and release quality.` (§10.9), `responsibilities: [positioning, store listing, ASO, screenshots, creatives, release notes, publishing, release validation]`, `authority: {decision_scope: [RELEASE], max_autonomy_level: 1, may_approve: [STORE_METADATA], may_reject: [review.reject], may_create_work: [TASK]}`, `risk_tolerance: VERY_LOW`, `preferred_evidence: [BUILD_ARTIFACT, QC_REPORT, SCREENSHOT, PLAYTEST]`, `escalation_rules: [{condition: "publishing a store build", to_level: 3, category: RELEASE}, {condition: "release date, pricing or monetization change", to_level: 3, category: PRODUCT}]`, `tool_permissions: [{tool: store.validate, effect: ALLOW}, {tool: store.publish, effect: REQUIRE_APPROVAL, approver: USER}, {tool: Edit, effect: DENY}, {tool: Write, effect: DENY}]`, `forbidden_actions: ["publish without user approval", "edit game code or assets", "change approved store metadata"]`. Body sections per ADR-0013 D-3 with one paragraph each derived from §10.9.

`permissions/defaults.yaml` rows added:

| role | tool | effect | notes |
|---|---|---|---|
| UA_RELEASE | `Read`,`Glob`,`Grep`,`decision.propose`,`store.validate` | ALLOW | |
| UA_RELEASE | `Edit`,`Write`,`bash`,`git.*`,`jira.*` | DENY | |
| UA_RELEASE | `store.publish` | REQUIRE_APPROVAL | approver USER (already covered by the `*` protected-action row; restated for the role) |

`policies.yaml` `UA_RELEASE` entry: `model_policy` families copied from the `PRODUCT_OWNER` row of ADR-0011 D-3 with `required_capabilities: [PLANNING, LONG_CONTEXT_REASONING]`, `cross_model_review: false`; `effort_policy.default: MEDIUM`; `budget_policy` kernel default; `allowed_tools: [Read, Glob, Grep, store.validate, store.publish]`; `allowed_paths: []`; `execution_strategy: single_run`; `max_parallel_runs: 1`.

#### Behavior
1. `ConstitutionLoader.load(UA_RELEASE)` succeeds; `list_roles()` includes `UA_RELEASE`; the provider-name lint (E01-S17 rule 3) passes on the new file.
2. `release_labels(rc, step)` returns exactly `[f"walk-release:{rc}", f"walk-release-step:{step}"]`; `rc_id_of`/`release_step_of` return `None` for items without the labels and raise `ConfigError` when exactly one of the two labels is present.
3. `DefaultTaskRouter.route(item, state)`: when `item.kind == TASK`, `state in {READY, REWORK}` and `release_step_of(item)` is set → `RouteDecision(role, purpose)` from `RELEASE_ROUTES`, `cross_model_review=False`; otherwise the E03-S07 table applies unchanged. A release task whose `contract.owner_role` differs from the routed role raises `ConfigError`.
4. `is_release_step(item, ctx)` is true iff `release_step_of(item)` is not `None`; `output_status_is_verdict` is true iff `ctx.payload["output_status"] ∈ {APPROVED, REJECTED, COMPLETED}`.
5. `DefaultOutputApplier` raises `release_step_done` (instead of the regular `(kind, state, status)` mapping) when `release_step_of(run item)` is set; the payload carries `output_status` and `evidence_kinds_present` (WBS §3.4) so `required_evidence_present` checks `contract.required_evidence`.
6. The `story_workflow` table loads as version `1.1` with exactly one more row than `1.0`; `TransitionTable` validation (E01-S09) still passes; non-release tasks cannot take `release_step_done` (guard `is_release_step` rejects).
7. `PermissionManager.decide` for `UA_RELEASE` + `store.publish` → `REQUIRE_APPROVAL(approver=USER)`; for `Edit` → `DENY`; for `store.validate` → `ALLOW`; a project `permissions.yaml` granting `UA_RELEASE Edit ALLOW` → `ConfigError` (E02-S10 narrowing).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the shipped defaults When `ConstitutionLoader.load(UA_RELEASE)` Then `authority.decision_scope == [RELEASE]`, `may_approve == ["STORE_METADATA"]`, `max_autonomy_level == 1`, `version == "1.0"` | `tests/agents/test_defaults_ua_release.py::test_ua_release_constitution_loads_with_adr_authority` |
| 2 | Given `policies.yaml` When loaded for `UA_RELEASE` Then `allowed_paths == []` and `allowed_tools` contains `store.publish` | `tests/agents/test_defaults_ua_release.py::test_ua_release_policy_defaults` |
| 3 | Given `UA_RELEASE` When `decide(store.publish)` Then `REQUIRE_APPROVAL` approver USER; `decide(Edit)` DENY; `decide(store.validate)` ALLOW | `tests/permissions/test_defaults_ua_release.py::test_ua_release_rule_effects` |
| 4 | Given a project rule `UA_RELEASE Edit ALLOW` When merged Then `ConfigError` | `tests/permissions/test_defaults_ua_release.py::test_ua_release_cannot_be_widened` |
| 5 | Given labels from `release_labels("RC-01", QC)` on a TASK When parsed Then `rc_id_of == "RC-01"`, `release_step_of == QC`; given only one label Then `ConfigError` | `tests/workflow/test_release_labels.py::test_release_labels_roundtrip_and_partial_rejected` |
| 6 | Given `story_workflow.yaml` When loaded Then version `1.1`, contains `READY --release_step_done--> COMPLETE` with the three guards, and all `1.0` rows unchanged | `tests/workflow/test_tables.py::test_story_workflow_release_row` |
| 7 | Given a TASK with step `qc` in READY When `route` Then `(QC, "QC")`; step `ua-review` → `(UA_RELEASE, "REVIEW")`; step `publish` → `(UA_RELEASE, "IMPLEMENT")`; all with `cross_model_review False` | `tests/orchestrator/test_router_release.py::test_release_steps_route_by_label` |
| 8 | Given a plain TASK in READY When `route` Then the E03-S07 result is unchanged | `tests/orchestrator/test_router_release.py::test_non_release_task_routing_unchanged` |
| 9 | Given a release task whose `contract.owner_role` is SENIOR_DEV When `route` Then `ConfigError` | `tests/orchestrator/test_router_release.py::test_release_task_owner_mismatch_rejected` |
| 10 | Given a fake QC run on a `qc` carrier task returning `REJECTED` with `QC_REPORT` evidence When output applied Then the task is `COMPLETE` via `release_step_done` and `WORK_ITEM_TRANSITION` names that event | `tests/runtime/test_applier_release.py::test_carrier_task_completes_via_release_step_done` |
| 11 | Given a carrier task whose output lacks the contract's required evidence When applied Then `GuardRejected` and the task stays `READY` | `tests/runtime/test_applier_release.py::test_carrier_task_missing_required_evidence_rejected` |
| 12 | Given a non-release TASK When `raise_event(release_step_done)` Then `GuardRejected` from `is_release_step` | `tests/workflow/test_release_labels.py::test_release_step_done_rejected_for_plain_task` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor --strict` on the demo repo → `lints: none` (new constitution passes the provider-name lint); `uv run python -c "from walk.workflow import ReleaseStep; print(list(ReleaseStep))"`.

#### Notes
- ADR-0013 D-1–D-5, D-7 (optional roles use the same schema); ADR-0006 D-3/D-6 (role row pattern); Invariant 7 (`store.publish` remains USER-approved regardless of role rows).
- `story_workflow` `1.0 → 1.1` is a `BehaviorVersion kind=WORKFLOW` MINOR bump (§105); the version string lives in the YAML `version` field.
- `NEW NAME:` module `walk.workflow.release` (`ReleaseStep`, `RELEASE_LABEL_PREFIX`, `RELEASE_STEP_LABEL_PREFIX`, `release_labels`, `rc_id_of`, `release_step_of`); guards `is_release_step`, `output_status_is_verdict`; `story_workflow` event `release_step_done` (INTERFACES §3.2 row); routing rows keyed by release step (INTERFACES §4 rows); `RELEASE_ROUTES`; kernel default constitution `ua_release.md`; `ApprovedArtifactKind.STORE_METADATA` is referenced here and introduced by E11-S05 (the `may_approve` string is validated only when used).
- Commit subject: `feat: add ua release role and release task routing (E11-S01)`.

#### Evidence (filled by implementer)
_pending_

---
