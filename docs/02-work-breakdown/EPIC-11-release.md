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

### E11-S02 — RC lifecycle service and `walk rc create/list/show`

**Status:** TODO
**Type:** feat
**Requirements:** §76, §136 (§1 flow `RELEASE CANDIDATE → FINAL QC → STORE / RELEASE`), §87, §137 (Inv. 9, 14)
**Depends on:** E11-X01, E01-S11
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Release candidates are created, inspected and advanced through one kernel service: `ReleaseManager` creates `RC-NN` in `BUILDING` from a commit and a project release configuration, computes the `rc_workflow` guard payload from evidence, bugs and approvals, enforces one active release line per project, and is exposed by the new `walk rc create/list/show` command group and in `walk status`.

#### Scope
- In: `ReleaseManager` protocol + `DefaultReleaseManager` (create, get, list, current, event, next); `ReleaseConfig` (`.ai/project/release.yaml`); `DefaultWorkflowManager.create_rc/get_rc/list_rcs`; RC payload keys and the guards that read them; daemon command `rc.create`; `walk rc create/list/show`; `KernelStatus.build_status`.
- Out: running builds (E11-S03); final QC and rejection bugs (E11-S04); carrier-task creation and `on_run_completed` (E11-S04–S06 add the step handlers); store metadata and publishing (E11-S05/S06); the `release` event execution (E11-S06 — this story only computes `approval_user` from an approval id).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager` |
| `src/walk/orchestrator/release.py` | create | `DefaultReleaseManager`, `ReleaseConfig`, `RELEASE_CONFIG_PATH`, `rc_payload` |
| `src/walk/orchestrator/__init__.py` | modify | re-exports `ReleaseManager`, `DefaultReleaseManager`, `ReleaseConfig` |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.create_rc`, `.get_rc`, `.list_rcs`, `.rc_event` (`rc_fields` payload) |
| `src/walk/workflow/guards.py` | modify | — (`build_evidence_present`, `qc_report_evidence`, `rejection_bugs_created`, `rejection_bugs_complete`, `approval_user` read the payload keys below) `(verify E01-S11 implementation)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.create`) `(verify)` |
| `src/walk/orchestrator/status.py` | modify | — (`KernelStatus.build_status` = latest RC id and state) `(verify E09-S04)` |
| `src/walk/cli/cmd_rc.py` | create | `rc_app` (`create`, `list`, `show`) |
| `src/walk/cli/app.py` | modify | — (registers `rc_app`) |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultReleaseManager`; `KernelHandle.release`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (new `ReleaseManager` block under §1.1; §1.3 `create_rc/get_rc/list_rcs`; §6 `walk rc …` rows) |
| `tests/orchestrator/test_release_manager.py` | create | — |
| `tests/orchestrator/test_release_payload.py` | create | — |
| `tests/workflow/test_service_rc.py` | create | — |
| `tests/cli/test_cmd_rc.py` | create | — |

#### Interface contract
`ReleaseCandidate`, `ReleaseCandidateState` per DOMAIN-MODEL §4.1/§3; `rc_workflow` per INTERFACES §3.6; `BuildTarget` per INTERFACES §2.4.
```python
# src/walk/orchestrator/release.py
RELEASE_CONFIG_PATH: str = "project/release.yaml"          # relative to .ai/

class ReleaseConfig(WalkModel):
    targets: list[BuildTarget] = Field(min_length=1, description="§62/§77 targets every RC must build, e.g. [Android, iOS]")
    release_branch: str = Field(default="main", description="branch whose HEAD is the default RC commit")
    output_dir: str = Field(default=".walk/release", description="build/output root, gitignored")

async def rc_payload(rc: ReleaseCandidate, *, config: ReleaseConfig, evidence: EvidenceManager, workflow: WorkflowManager,
                     permissions: PermissionManager) -> JsonDict: ...

# src/walk/orchestrator/protocols.py
class ReleaseManager(Protocol):
    """§76. Hosted by walk.orchestrator. Owns RC creation and RC events; WorkflowManager.rc_event stays the only state change."""
    async def create(self, *, commit: Sha | None, targets: list[BuildTarget] | None, actor: Actor) -> ReleaseCandidate: ...
    async def get(self, rc_id: ReleaseCandidateId) -> ReleaseCandidate: ...
    async def list(self) -> list[ReleaseCandidate]: ...
    async def current(self) -> ReleaseCandidate | None: ...           # latest RC not RELEASED
    async def event(self, rc_id: ReleaseCandidateId, event: str, *, actor: Actor, extra: JsonDict | None = None) -> ReleaseCandidate: ...
    def config(self) -> ReleaseConfig: ...

# src/walk/workflow/service.py — DefaultWorkflowManager additions
async def create_rc(self, project_key: ProjectKey, number: int, commit: Sha) -> ReleaseCandidate: ...   # RC-NN, BUILDING, ledger RC_TRANSITION{event: "create"}
async def get_rc(self, rc_id: ReleaseCandidateId) -> ReleaseCandidate: ...
async def list_rcs(self) -> list[ReleaseCandidate]: ...
# rc_event(): when ctx.payload contains "rc_fields" (keys ⊆ {build_evidence_ids, qc_report_evidence_id, rejection_bug_ids}),
# those fields are set on the RC in the same transaction as the state change; any other key → ConfigError.
```
RC payload keys (recorded in WBS §3.4 by E11-X01):

| Payload key | Type | Written by | Read by guard |
|---|---|---|---|
| `rc_targets_required` | list[`BuildTarget`] | `rc_payload` (from `ReleaseConfig.targets`) | `build_evidence_present` |
| `rc_targets_built` | list[`BuildTarget`] | `rc_payload` (from `BUILD_ARTIFACT` evidence ids on the RC, E11-S03) | `build_evidence_present` |
| `qc_report_evidence_id` | `EvidenceId \| None` | `rc_payload` | `qc_report_evidence` |
| `open_blocker_bug_count` | int | `rc_payload` (existing key, WBS §3.4) | `no_open_blocker_bugs` |
| `rejection_bug_ids` | list[`BugId`] | `rc_payload` | `rejection_bugs_created` |
| `rejection_bug_states` | dict[`BugId`, `WorkItemState`] | `rc_payload` | `rejection_bugs_complete` |
| `release_approval_state` | `ApprovalState \| None` | `rc_payload` (from `extra["approval_id"]`) | `approval_user` |

CLI: `walk rc create [--target T...] [--commit SHA] [--json]`; `walk rc list [--json]`; `walk rc show RC_ID [--json]` (RC fields, transitions from `RC_TRANSITION` events, evidence ids, rejection bugs with states).

#### Behavior
1. `create`: refuses (`ConfigError`) when an RC in `BUILDING`, `QC`, `PASSED` or `REJECTED` exists (`REJECTED` continues with `next_rc`, §76); `targets` default to `ReleaseConfig.targets` (missing `release.yaml` and no `--target` → `ConfigError` naming `RELEASE_CONFIG_PATH`); `commit` defaults to `GitProvider` HEAD of `release_branch`; `number` = 1 for a new release line; `WorkflowManager.create_rc` allocates `RC-NN` (project `id_sequences`, width 2) and writes `RC_TRANSITION{event: "create", from_state: null, to_state: BUILDING, commit, targets}` (ARCHITECTURE §4.3 write point `StateMachine.commit`).
2. `event(rc_id, event, actor, extra)` computes `rc_payload`, copies `extra["rc_fields"]` into the context payload and calls `WorkflowManager.rc_event`; guard rejections surface as `GuardRejected` naming the guard; the RC is never mutated outside `rc_event` (fields and state change commit together, or neither).
3. `rc_payload`: `rc_targets_built` = targets of `BUILD_ARTIFACT` evidence listed in `extra["rc_fields"]["build_evidence_ids"]` when given, else in `rc.build_evidence_ids` (target read from the evidence `metadata.target` `(verify EvidenceDraft field, E01-S06)`); `open_blocker_bug_count` = open `BLOCKER` bugs in the project (the §76 "PASS" condition); `rejection_bug_states` = current state of each `rc.rejection_bug_ids`; `release_approval_state` = state of `extra["approval_id"]` via `PermissionManager.pending`/repository lookup, `None` when absent.
4. Guards (E01-S11 names, `(verify)` existing semantics): `build_evidence_present` ⇔ `set(required) ⊆ set(built)`; `qc_report_evidence` ⇔ id not `None`; `no_open_blocker_bugs` ⇔ count == 0; `rejection_bugs_created` ⇔ list non-empty; `rejection_bugs_complete` ⇔ every state ∈ {`COMPLETE`, `CANCELLED`}; `approval_user` ⇔ state == `APPROVED`.
5. `next_rc` from `REJECTED` (via `event(rc, "next_rc")`) yields the successor created by E01-S11 (`number + 1`, `BUILDING`, same targets, `commit` = current HEAD of `release_branch`); `current()` then returns the successor.
6. `walk rc create`: with a running daemon the CLI sends command `rc.create` (ADR-0009 D-3); otherwise runs in-process under `KernelLock`; prints `RC-01 BUILDING <commit> <targets>`. `walk rc list`/`show` read SQLite directly (ARCHITECTURE §3.1); unknown id → exit 1.
7. `KernelStatus.build_status` = `"<RC id> <state>"` of `current()` or `None`; `walk status --json` shows it.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `release.yaml` with `[Android, iOS]` When `create(commit=None)` Then `RC-01`, number 1, `BUILDING`, commit = HEAD of `main`, and one `RC_TRANSITION` with `event == "create"` | `tests/orchestrator/test_release_manager.py::test_create_first_rc` |
| 2 | Given an RC in `QC` When `create` Then `ConfigError` | `tests/orchestrator/test_release_manager.py::test_create_refused_with_active_rc` |
| 3 | Given no `release.yaml` and no targets When `create` Then `ConfigError` naming `project/release.yaml` | `tests/orchestrator/test_release_manager.py::test_create_requires_targets` |
| 4 | Given RC-01 `REJECTED` with both rejection bugs `COMPLETE` When `event("next_rc")` Then `RC-02` number 2 `BUILDING` and `current() == RC-02` | `tests/orchestrator/test_release_manager.py::test_next_rc_successor` |
| 5 | Given build evidence for Android only and required `[Android, iOS]` When `event("build_ok")` Then `GuardRejected` naming `build_evidence_present` | `tests/orchestrator/test_release_payload.py::test_build_ok_requires_all_targets` |
| 6 | Given one open BLOCKER bug When `event("qc_pass")` with a QC report Then `GuardRejected` naming `no_open_blocker_bugs` | `tests/orchestrator/test_release_payload.py::test_qc_pass_blocked_by_open_blocker` |
| 7 | Given a REJECTED RC with one rejection bug in `IMPLEMENTING` When `next_rc` Then `GuardRejected` naming `rejection_bugs_complete` | `tests/orchestrator/test_release_payload.py::test_next_rc_requires_bugs_complete` |
| 8 | Given a PASSED RC and a PENDING approval id When `event("release", extra={"approval_id": …})` Then `GuardRejected` naming `approval_user`; after approval Then `RELEASED` | `tests/orchestrator/test_release_payload.py::test_release_requires_user_approval_state` |
| 9 | Given `create_rc` twice for different lines When ids are read Then `RC-01`, `RC-02` matching `ReleaseCandidateId` | `tests/workflow/test_service_rc.py::test_create_rc_ids_and_ledger` |
| 10 | Given `walk rc create --target Android` (no daemon) then `walk rc list --json` Then exit 0 and one RC in `BUILDING` | `tests/cli/test_cmd_rc.py::test_rc_create_and_list_offline` |
| 11 | Given `walk rc show RC-01 --json` Then the RC, its transitions and targets; `walk rc show RC-99` Then exit 1 | `tests/cli/test_cmd_rc.py::test_rc_show_and_unknown` |
| 12 | Given a running fake daemon When `walk rc create` Then a `commands` row `rc.create` is written and its result printed | `tests/cli/test_cmd_rc.py::test_rc_create_via_daemon` |
| 13 | Given RC-01 `BUILDING` When `walk status --json` Then `build_status == "RC-01 BUILDING"` | `tests/cli/test_cmd_rc.py::test_status_shows_build_status` |
| 14 | Given `rc_event("build_ok")` with `rc_fields.build_evidence_ids` for all targets Then state `QC` and the ids stored; with key `state` in `rc_fields` Then `ConfigError` and nothing changed | `tests/workflow/test_service_rc.py::test_rc_fields_applied_atomically` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo: `cat .ai/project/release.yaml`, `walk rc create`, `walk rc list`, `walk rc show RC-01`, `walk ledger query --kind RC_TRANSITION`, `walk status --json | grep build_status`.

#### Notes
- INTERFACES §3.6 (table unchanged); ARCHITECTURE §4.3 (`RC_TRANSITION` only from `StateMachine.commit`); ADR-0009 D-3 (IPC); WBS §3.7 (`rc` command group).
- `src/walk/workflow/guards.py` is also modified by E11-S01 (parallel set): rebase rather than merge-overwrite; the two edits touch different guard functions.
- `NEW NAME:` `ReleaseManager` (protocol), `DefaultReleaseManager`, `ReleaseConfig`, `RELEASE_CONFIG_PATH` (`.ai/project/release.yaml`), `rc_payload`, the RC payload keys above and payload key `rc_fields`, `DefaultWorkflowManager.create_rc/get_rc/list_rcs`, `CommandConsumer` command `rc.create`, `KernelHandle.release`, `walk rc create/list/show` (already in WBS §6).
- Commit subject: `feat: add release candidate service and walk rc commands (E11-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S03 — RC build pipeline for all targets

**Status:** TODO
**Type:** feat
**Requirements:** §62, §76, §77 (AAB), §84, §90, §137 (Inv. 9)
**Depends on:** E11-S02, E03-S11
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An RC in `BUILDING` is built non-development for every configured target from its exact commit in an isolated worktree through `CiProvider`, every artifact is recorded as `BUILD_ARTIFACT` evidence, and the RC moves to `QC` (`build_ok`) only when all targets succeeded or to `REJECTED` (`build_failed`) otherwise — idempotently across kernel restarts.

#### Scope
- In: `ReleaseManager.build` and `resume_builds`; `release_jobs`; `release-build:<BuildTarget>` jobs in `LocalCiProvider`; Android App Bundle output for release builds (`UnityBatchProvider` + `com.walk.ci`); daemon command `rc.build` and build start after `rc.create`; startup resume of interrupted RC builds; `walk rc build`; fake Unity provider release artifacts.
- Out: iOS `.ipa` export (Unity produces an Xcode project; archiving/signing with `xcodebuild` is not planned — the iOS artifact is the zipped Xcode project and E11-S06 documents the limitation); final QC (E11-S04); compute cost records (already produced by the E09-S03 `ON_BUILD_*` attachments).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager.build`, `ReleaseManager.resume_builds` |
| `src/walk/orchestrator/release.py` | modify | `DefaultReleaseManager.build`, `.resume_builds`, `release_jobs`, `RELEASE_JOB_PREFIX` |
| `src/walk/integrations/ci.py` | modify | — (`LocalCiProvider` runs `release-build:<BuildTarget>` as `UnityProvider.build(..., development=False)`) `(verify E03-S11 job dispatch)` |
| `src/walk/integrations/unity/provider.py` | modify | — (`build(..., development=False)` for `ANDROID` passes `-walkAppBundle`) `(verify E03-S10)` |
| `unity/com.walk.ci/Editor/WalkCI.cs` | modify | — (`-walkAppBundle` sets `EditorUserBuildSettings.buildAppBundle = true`) `(verify E03-S10)` |
| `src/walk/orchestrator/service.py` | modify | — (startup calls `release.resume_builds()`; RC build tasks tracked like runs and cancelled on `stop`) `(verify)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.build`; `rc.create` schedules `build`) |
| `src/walk/cli/cmd_rc.py` | modify | `rc_app` (`build`) |
| `tests/fakes/fake_unity_provider.py` | modify | — (release builds write `<target>.aab` / `<target>.zip` artifacts; scripted per-target failure) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§2.4 `CiProvider` job name `release-build:<BuildTarget>`; `ReleaseManager.build/resume_builds`; §6 `walk rc build`) |
| `tests/orchestrator/test_release_build.py` | create | — |
| `tests/integrations/test_ci_release_jobs.py` | create | — |
| `tests/integrations/test_unity_release_build.py` | create | — |
| `tests/cli/test_cmd_rc_build.py` | create | — |

#### Interface contract
`CiProvider.run_pipeline`, `UnityProvider.build`, `JobResult`, `BuildTarget` per INTERFACES §2.4; `IntegrationManager.with_idempotency` per §1.12; RC payload per E11-S02.
```python
# src/walk/orchestrator/release.py
RELEASE_JOB_PREFIX: str = "release-build:"
def release_jobs(targets: list[BuildTarget]) -> list[str]: ...      # ["release-build:Android", "release-build:iOS"] in config order

# ReleaseManager additions (src/walk/orchestrator/protocols.py)
async def build(self, rc_id: ReleaseCandidateId) -> ReleaseCandidate: ...
    """BUILDING only. Worktree at rc.commit; CiProvider.run_pipeline(worktree, rc.commit, release_jobs(targets),
    idempotency_key=f"rc:{rc_id}:build"); all ok → event build_ok with rc_fields.build_evidence_ids; else build_failed."""
async def resume_builds(self) -> list[ReleaseCandidateId]: ...
    """Startup: every RC still BUILDING is built again (idempotent per job); returns the ids resumed."""
```
Artifact layout: `<repo>/<ReleaseConfig.output_dir>/<RC-id>/<BuildTarget>/` (gitignored `.walk/release/…` by default). CLI: `walk rc build RC_ID [--json]`.

#### Behavior
1. `build` refuses an RC not in `BUILDING` (`GuardRejected`); creates (or reuses) a detached worktree at `rc.commit` under `.walk/worktrees/rc-<RC-id>/` through `GitProvider` `(verify worktree API, E01-S23)`; the worktree is removed after the pipeline.
2. Jobs are `release_jobs(targets)`; `LocalCiProvider` maps `release-build:<T>` to `UnityProvider.build(worktree, T, <output>/<RC-id>/<T>/, development=False)`; any other job prefix keeps its E03-S11 behaviour.
3. Android release builds produce an `.aab` (`-walkAppBundle`); other targets produce Unity's default player output, zipped into one artifact file per target by the provider.
4. Each `JobResult` is recorded by `CiProvider` as `BUILD_RESULT` + `BUILD_ARTIFACT` evidence with `metadata.target = <BuildTarget>` and `metadata.rc_id` (E03-S11 recording, extended with the two metadata keys); `build` collects the evidence ids.
5. All jobs ok → `event(rc, "build_ok", extra={"rc_fields": {"build_evidence_ids": [...]}})` → `QC` (guard `build_evidence_present`); any job failed → `event(rc, "build_failed", extra={"rc_fields": {"build_evidence_ids": [...]}})` → `REJECTED` (no rejection bugs: a failed build is not a QC rejection; the next RC is created with `walk rc create` after the fix lands, since `next_rc` requires rejection bugs).
6. Idempotency (§90): the pipeline runs inside `IntegrationManager.with_idempotency(f"rc:{rc_id}:build:<target>", …)` per job, so a resumed build re-runs only targets without a stored result; `resume_builds` at startup resumes every RC still in `BUILDING`.
7. The `ON_BUILD_SUCCESS`/`ON_BUILD_FAILURE` hooks fired by the RC transition (INTERFACES §3.6) carry `payload.rc_id` and no job result; attachments that need a job result skip such contexts, so no duplicate `BUILD_RESULT` or evidence is written (WBS §3.5) `(verify E03-S11 attachments)`.
8. With a daemon, `rc.create` schedules `build` as a tracked background task and returns immediately; `rc.build` re-triggers it; offline `walk rc build` runs synchronously under `KernelLock` and prints one line per target (`Android ok RC-01/Android/game.aab`) and the final RC state.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given targets `[Android, iOS]` When `release_jobs` Then `["release-build:Android", "release-build:iOS"]` | `tests/orchestrator/test_release_build.py::test_release_jobs_from_targets` |
| 2 | Given RC-01 BUILDING and a fake Unity succeeding for both targets When `build` Then 2 `BUILD_ARTIFACT` evidence rows with `metadata.target`, RC `QC`, `build_evidence_ids` of length 2, one `RC_TRANSITION` with event `build_ok` | `tests/orchestrator/test_release_build.py::test_build_all_targets_ok_moves_to_qc` |
| 3 | Given iOS failing When `build` Then RC `REJECTED` via `build_failed`, Android evidence still recorded | `tests/orchestrator/test_release_build.py::test_build_failure_rejects_rc` |
| 4 | Given RC in `QC` When `build` Then `GuardRejected` | `tests/orchestrator/test_release_build.py::test_build_requires_building_state` |
| 5 | Given a build interrupted after Android succeeded When `resume_builds` Then only iOS is built again and the RC reaches `QC` | `tests/orchestrator/test_release_build.py::test_resume_builds_idempotent_per_target` |
| 6 | Given a completed build When the ledger is queried Then exactly one `BUILD_RESULT` per target (no duplicates from the RC-level hook) | `tests/orchestrator/test_release_build.py::test_no_duplicate_build_results` |
| 7 | Given job `release-build:Android` When `LocalCiProvider.run_pipeline` Then `UnityProvider.build` called with `development=False` and target `Android` | `tests/integrations/test_ci_release_jobs.py::test_release_build_job_dispatch` |
| 8 | Given an Android release build When `UnityBatchProvider.build(development=False)` Then the batchmode arguments include `-walkAppBundle`; a development build Then not | `tests/integrations/test_unity_release_build.py::test_app_bundle_flag_for_android_release` |
| 9 | Given `walk rc build RC-01` offline with a fake Unity Then exit 0, one line per target, last line `RC-01 QC` | `tests/cli/test_cmd_rc_build.py::test_rc_build_offline` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo with the fake Unity provider: `walk rc create`, `walk rc build RC-01`, `ls .walk/release/RC-01/*`, `walk rc show RC-01`, `walk cost --phase <id>` showing COMPUTE cost for the builds.
- Optional (`@pytest.mark.integration`, skipped by default): real Unity Android release build transcript.

#### Notes
- §62 "builds" as `BUILD_ARTIFACT` evidence; ADR-0009 D-6 (Unity batchmode, `com.walk.ci`); E11-X01 item 3 confirms the job naming (`release-build:` was chosen over `build:` + flag because `CiProvider.run_pipeline` has no development parameter).
- `NEW NAME:` `ReleaseManager.build/resume_builds`, `release_jobs`, `RELEASE_JOB_PREFIX`, job name `release-build:<BuildTarget>`, batchmode argument `-walkAppBundle`, evidence metadata keys `target`/`rc_id`, `CommandConsumer` command `rc.build`, `walk rc build`.
- Commit subject: `feat: build release candidates for all targets (E11-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E11-S04 — Final QC on RC and rejection bugs

**Status:** TODO
**Type:** feat
**Requirements:** §76, §63, §64, §23, §136 (`FINAL QC`), §137 (Inv. 4, 9)
**Depends on:** E11-S03, E03-S15
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A built RC gets an independent final QC run through a `qc` carrier task; an approving QC report moves it to `PASSED`, a rejection moves it to `REJECTED` with the bugs QC created linked as rejection bugs, those bugs flow through the normal bug loop, and when the last one completes the kernel itself raises `next_rc` so the next RC is built — the §76 RC1 → QC → REJECT → RC2 → QC → PASS cycle.

#### Scope
- In: `RELEASE_STEP_CONTRACTS`, `release_step_brief`, `ReleaseManager.open_step`; opening the QC carrier after `build_ok`; `ReleaseManager.on_run_completed` for the `qc` step; QC-output path writing `QC_RESULT` with `rc_id` for carriers; rejection-bug linking; hook callable `release_bug_complete_next_rc` (`ON_TASK_COMPLETE`); automatic build of the successor RC; daemon command `rc.qc` and `walk rc qc`.
- Out: carrier routing and the `release_step_done` transition (E11-S01); the bug loop itself (E03-S15, unchanged); `ua-review` and `publish` steps (E11-S05/S06); QC on physical devices (QC uses the fake/real tools its policy allows; no device farm integration is planned).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/protocols.py` | modify | `ReleaseManager.open_step`, `.on_run_completed`, `.on_bug_completed` |
| `src/walk/orchestrator/release.py` | modify | `RELEASE_STEP_CONTRACTS`, `release_step_brief`, `release_bug_complete_next_rc`, `DefaultReleaseManager.open_step/on_run_completed/on_bug_completed`; `build` opens the QC step after `build_ok` |
| `src/walk/orchestrator/service.py` | modify | — (run-completion path calls `release.on_run_completed` for items with `release_step_of(item) == QC`; QC_RESULT payload gains `rc_id` for carriers) `(verify E03-S14 completion path)` |
| `src/walk/orchestrator/commands.py` | modify | — (command `rc.qc`) |
| `src/walk/cli/cmd_rc.py` | modify | `rc_app` (`qc`) |
| `src/walk/cli/composition.py` | modify | — (registers `release_bug_complete_next_rc` on `ON_TASK_COMPLETE`, priority 150, `log_and_continue`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (`ReleaseManager` methods; §6 `walk rc qc`) |
| `tests/orchestrator/test_release_qc.py` | create | — |
| `tests/orchestrator/test_release_rejection_loop.py` | create | — |
| `tests/cli/test_cmd_rc_qc.py` | create | — |

#### Interface contract
Carrier-task mechanism: this file's header; `ReleaseStep`, `release_labels`, `release_step_of`, `rc_id_of` from E11-S01; `rc_workflow` per INTERFACES §3.6; RC payload per E11-S02; `BugDraft` per DOMAIN-MODEL §4.1.
```python
# src/walk/orchestrator/release.py
RELEASE_STEP_CONTRACTS: dict[ReleaseStep, tuple[AgentRole, list[EvidenceKind]]] = {
    ReleaseStep.QC: (AgentRole.QC, [EvidenceKind.QC_REPORT]),
    ReleaseStep.UA_REVIEW: (AgentRole.UA_RELEASE, []),
    ReleaseStep.PUBLISH: (AgentRole.UA_RELEASE, []),
}   # (contract.owner_role, contract.required_evidence)

def release_step_brief(rc: ReleaseCandidate, step: ReleaseStep, *, artifacts: list[Evidence], open_bugs: list[Bug]) -> str: ...
    # carrier description: RC id, commit, targets, artifact paths, open bugs, verdict rules of the step

async def release_bug_complete_next_rc(ctx: HookContext) -> HookResult: ...   # ON_TASK_COMPLETE → ReleaseManager.on_bug_completed

# ReleaseManager additions
async def open_step(self, rc_id: ReleaseCandidateId, step: ReleaseStep) -> WorkItem: ...
    """Creates (or returns the existing non-terminal) carrier TASK: labels release_labels(rc_id, step), state READY,
    contract.owner_role/required_evidence from RELEASE_STEP_CONTRACTS, description release_step_brief(...)."""
async def on_run_completed(self, item: WorkItem, output: AgentOutput, effects: AppliedEffects) -> ReleaseCandidate | None: ...
async def on_bug_completed(self, bug_id: BugId) -> ReleaseCandidate | None: ...
```
CLI: `walk rc qc RC_ID` — (re)opens the QC step of an RC in `QC`.

#### Behavior
1. After `build_ok` (E11-S03) the RC is in `QC` and `build` calls `open_step(rc, QC)`; the carrier is routed to `(QC, "QC")` by E11-S01 and scheduled like any `READY` task; `cross_model_review` preference of §23 applies through the QC role policy, and the QC run never shares a run with an implementer of the release commit (Inv. 4 — a carrier is a separate work item with owner QC).
2. `open_step` is idempotent: an existing carrier with the same labels in a non-terminal state is returned; a second QC carrier for the same RC is created only after the previous one is `COMPLETE`.
3. `on_run_completed` (called only for `qc` carriers in this story): output `APPROVED` with a `QC_REPORT` evidence → `event(rc, "qc_pass", extra={"rc_fields": {"qc_report_evidence_id": <id>}})` → `PASSED` when guard `no_open_blocker_bugs` holds; output `REJECTED` → the bugs created from `output.new_bugs` by the applier (`effects.bug_ids`, E03-S14) become `rejection_bug_ids` in `event(rc, "qc_reject", extra={"rc_fields": {"qc_report_evidence_id": …, "rejection_bug_ids": […]}})` → `REJECTED`.
4. `qc_pass` rejected by `no_open_blocker_bugs` (a BLOCKER bug opened elsewhere) or a `REJECTED` output without new bugs (guard `rejection_bugs_created`): the RC stays in `QC`, an `ERROR` ledger event with `rc_id` and the guard name is written, and an escalation to `ORCHESTRATOR` is raised (`DecisionManager.escalate`, level 2); `walk rc qc RC_ID` re-opens the step after the cause is fixed.
5. Rejection bugs carry `against_commit = rc.commit` (set by `on_run_completed` before linking, through `WorkflowManager` update `(verify field update API)`) and follow the E03-S15 loop unchanged (triage, fix, review, re-test, reopen).
6. `QC_RESULT` for a carrier run is written once by the orchestrator QC-output path with payload `rc_id`, `verdict`, `bug_ids` (ARCHITECTURE §4.3 write point `orchestrator.Orchestrator`); the RC-level `ON_QC_RESULT`/`ON_BUG_CREATED` hooks fired by `rc_event` do not write a second one (WBS §3.5).
7. `on_bug_completed(bug_id)`: when the bug is a rejection bug of the current `REJECTED` RC and every rejection bug is `COMPLETE` or `CANCELLED`, raises `next_rc` (Who: KERNEL) → successor RC in `BUILDING` at the current `release_branch` HEAD, then schedules `build(successor)` (E11-S03); otherwise returns `None`. Idempotent: a second call after the successor exists does nothing.
8. `walk rc qc RC_ID` with an RC not in `QC` → exit 2 (guard semantics).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given RC-01 reaching `QC` via `build` When the carrier is inspected Then one TASK in `READY` with labels `walk-release:RC-01`, `walk-release-step:qc`, `owner_role == QC`, `required_evidence == [QC_REPORT]`, and the description lists every build artifact path | `tests/orchestrator/test_release_qc.py::test_qc_step_opened_after_build_ok` |
| 2 | Given `open_step(RC-01, QC)` called twice Then the same work item id | `tests/orchestrator/test_release_qc.py::test_open_step_idempotent` |
| 3 | Given a fake QC run returning `APPROVED` with a QC report When completed Then RC-01 `PASSED`, `qc_report_evidence_id` set, carrier `COMPLETE`, one `QC_RESULT` with `rc_id == "RC-01"` | `tests/orchestrator/test_release_qc.py::test_qc_pass_moves_rc_to_passed` |
| 4 | Given a fake QC run returning `REJECTED` with one BLOCKER `new_bugs` entry When completed Then a BUG exists with `against_commit == rc.commit`, RC-01 `REJECTED` with `rejection_bug_ids == [that bug]` | `tests/orchestrator/test_release_qc.py::test_qc_reject_links_rejection_bugs` |
| 5 | Given an open BLOCKER bug elsewhere and an approving QC run When completed Then RC stays `QC`, an `ERROR` event names `no_open_blocker_bugs`, an escalation to ORCHESTRATOR exists | `tests/orchestrator/test_release_qc.py::test_qc_pass_blocked_escalates` |
| 6 | Given a `REJECTED` QC output without bugs When completed Then RC stays `QC` and `ERROR` names `rejection_bugs_created` | `tests/orchestrator/test_release_qc.py::test_qc_reject_without_bugs_kept_in_qc` |
| 7 | Given RC-01 `REJECTED` with two rejection bugs When the first completes Then no successor; when the second completes Then RC-02 `BUILDING` and a build is scheduled | `tests/orchestrator/test_release_rejection_loop.py::test_last_rejection_bug_triggers_next_rc` |
| 8 | Given the successor exists When `on_bug_completed` is called again Then no third RC | `tests/orchestrator/test_release_rejection_loop.py::test_next_rc_idempotent` |
| 9 | Given a completed reject cycle When the ledger is queried Then `RC_TRANSITION` events `create, build_ok, qc_reject, next_rc` for RC-01/RC-02 in order and one `QC_RESULT` per QC run | `tests/orchestrator/test_release_rejection_loop.py::test_reject_cycle_ledger_trail` |
| 10 | Given RC-01 in `QC` When `walk rc qc RC-01` Then exit 0 and the carrier id printed; RC in `PASSED` Then exit 2 | `tests/cli/test_cmd_rc_qc.py::test_rc_qc_reopens_step` |

#### Evidence required
- Quality gate output.
- Demo on the fixture repo with scripted fake QC outputs: `walk rc build RC-01` → `walk run --once` (QC rejects) → `walk rc show RC-01` (REJECTED, bug id) → bug loop via fakes → `walk rc list` (RC-02 BUILDING) → `walk ledger query --kind RC_TRANSITION`.

#### Notes
- Carrier-task mechanism (header, binding); §63 QC authority (only QC creates the rejection bugs, through `AgentOutput.new_bugs`); §64 bug loop unchanged; ARCHITECTURE §4.3 `QC_RESULT`/`BUG_CREATED` write point; E11-X01 item 5 confirms the single run-completion path.
- Release instructions are given in the carrier description (`release_step_brief`), not in `QC.md.j2`, so no `PROMPT` behaviour version changes in this story.
- `NEW NAME:` `RELEASE_STEP_CONTRACTS`, `release_step_brief`, hook callable `release_bug_complete_next_rc`, `ReleaseManager.open_step/on_run_completed/on_bug_completed`, `QC_RESULT` payload key `rc_id`, `CommandConsumer` command `rc.qc`, `walk rc qc`.
- Commit subject: `feat: add final qc and rejection loop for release candidates (E11-S04)`.

#### Evidence (filled by implementer)
_pending_

---

