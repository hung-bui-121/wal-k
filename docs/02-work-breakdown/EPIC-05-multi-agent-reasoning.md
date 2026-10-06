# EPIC-05 — Multi-Agent Reasoning

**Roadmap stage:** §135 Stage 5
**Goal.** Constitutions with professional bias drive debates, authority and escalation; the PO resolves what agents cannot; every accepted decision is persisted and the §133 debate test passes with fake adapters producing scripted positions.
**Requirements.** §6.7, §6.9, §10.2, §10.4, §12 (full), §44–§47, §50–§51, §93 (decisions override), §127 (optional roles), §133, §137 (Inv. 5, 7), §138 (Infinite Debate, Over-Engineering).
**Epic gate.** `tests/e2e/test_e05_gate.py` (§133): a feature requirement is challenged by fake LEAD_DEV (`REJECTED` with `debate_position`); a `Debate` opens with LEAD_DEV + DESIGN_LEADER (or ORCHESTRATOR), two rounds without consensus escalate to PO, PO resolves, `Decision` is `ACCEPTED`, persisted in SQLite and `.ai/decisions/DEC-NNNN.md`, linked to the feature context.
**Branching.** `story/<ID>-<slug>` + worktree per story (COMMIT-POLICY §4); merge `--no-ff` after E05-R01.
**Preconditions.** E01-R01…E04-R01 `DONE` with no `BLOCKER` bugfix stories; `main` green; E05-X01 committed before any E05 story starts (WBS §2 rule 3).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E05-X01 | Refine E05 against codebase | E04-R01 | LOW |
| E05-S01 | `DecisionManager.propose/classify_autonomy/escalate/override` | E05-X01, E04-S05 | HIGH |
| E05-S02 | `Orchestrator.handle_escalation` routing (L1 debate, L2 PO run, L3 user approval) | E05-S01, E02-S11 | MEDIUM |
| E05-S03 | `DebateManager` and `debate_workflow` table | E05-S01 | HIGH |
| E05-S04 | Debate runs and `DebatePosition` output (incl. `agrees_with_role`) | E05-S03, E03-S07 | HIGH |
| E05-S05 | Debate escalation PO → USER, round and budget limits | E05-S04, E05-S02 | MEDIUM |
| E05-S06 | PRODUCT_OWNER and DESIGN_LEADER constitutions and policies | E05-X01, E03-S06 | MEDIUM |
| E05-S07 | Constitution schema enforcement: narrowing merge, provider-name lint, section rendering | E05-S06 | MEDIUM |
| E05-S08 | Conflict detection → debate opening from review/design disagreement | E05-S04, E03-S13 | MEDIUM |
| E05-S09 | `walk debates list/show`, `walk decisions override` | E05-S03, E05-S01 | LOW |
| E05-S10 | Epic gate: §133 debate test (e2e) | E05-S05, E05-S07, E05-S08, E05-S09 | MEDIUM |
| E05-R01 | Review E05 | E05-S10 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (rules; §3.4 payload keys, §3.5 ledger vs hooks, §3.6 fakes, §3.9 templates).
2. ADR-0013 (constitution schema, D-3 rendering, D-4 narrowing, D-5 lint), ADR-0006 (authority in `OutputApplier`, D-4 approvals), ADR-0010 D-3/D-4 (`DebateState`, `debate_workflow` as data), ADR-0003 (decision documents).
3. `INTERFACES.md` §1.1 `Orchestrator.handle_escalation`, §1.2, §1.9 (`DecisionManager`, `DebateManager`), §1.10, §3.5 (`debate_workflow v1.0`), §4 (DEBATE rows), §5.1.
4. `DOMAIN-MODEL.md` §3 (`DecisionCategory`, `DecisionStatus`, `AutonomyLevel`, `DebateState`), §4.2 (`Constitution`, `AgentOutput.decisions/escalations/debate_position`), §4.8, §6.2 (`decisions`, `debates`, `debate_positions`, `escalations`).
5. `ARCHITECTURE.md` §4.1 rows `ON_DEBATE_*`, `ON_DECISION_RECORDED`, `ON_ESCALATION`; §4.3 write points `debate.DebateManager`, `decisions.DecisionManager`; §5.5 (debate circuit breaker); §7 Inv. 5, 7.
6. Existing E04-S05 `walk.decisions` service (the `NotSupported("E05-S01")`/`("E05-S03")` stubs this epic replaces).

Parallel sets (WBS §8): `{S01→S02} ∥ {S06→S07}`; `{S03→S04→S05} ∥ {S09}`.

Planning decisions fixed for this epic (Autonomy Level 0 unless marked `NEW NAME:`):
- Debate budgets use `BudgetScope.TASK` with `scope_id = <DebateId>` (dimensions `REVIEW_LOOPS` = `max_rounds`, `COST_USD` = `DebatePolicy.cost_usd`); no new `BudgetScope` member.
- Debate guards are registered through `walk.workflow.guards.register_guard` from `walk.debate.guards` (debate may import workflow); the `debate_workflow.yaml` table lives with the other tables under `src/walk/workflow/tables/` and is loaded by the E01-S11 generic engine with `DebateState`.
- Debate runs are scheduled against the debate's `work_item_id`; a debate without a work item is never auto-scheduled (only resolvable by USER via approval).
- `record()` accepts `by.role == KERNEL` only when `decision.debate_id` is set (debate resolution path); any other KERNEL record is `AuthorityViolation`.
- Optional roles are "enabled" when `RuntimePolicy.enabled` is true (`NEW NAME:` field, default `True`; kernel defaults ship PO and DESIGN_LEADER with `enabled: false`); `AgentManager.list_roles()` returns enabled roles with a constitution.

---

### E05-X01 — Refine E05 against codebase

**Status:** TODO
**Type:** docs
**Requirements:** §135 (Stage 5), §58 (Definition of Ready applied to stories), §5 (non-goals: refine rejects stories that drift into out-of-scope work)
**Depends on:** E04-R01
**Effort:** LOW   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every E05 story's Files table, interface references and dependencies are re-validated against the `src/walk/` tree and `INTERFACES.md` as they exist after E04-R01, and the corrected epic file is committed before any E05 story starts.

#### Scope
- In: this file (`EPIC-05-multi-agent-reasoning.md`), `WBS.md` §5 rows for E05, `WBS.md` §6 register entries introduced by E05.
- Out: changing story IDs, titles, dependencies or effort (fixed by WBS §4); writing code.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-05-multi-agent-reasoning.md` | modify | — |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status row E05-X01; §6 register additions) |

#### Interface contract
Checklist applied to every story E05-S01…S10 and E05-R01:
1. Every path in the Files table marked `modify` exists in `src/walk/` or `tests/`; every path marked `create` does not exist and is not created by an earlier story.
2. Every `INTERFACES.md §x.y` / `DOMAIN-MODEL.md §x.y` reference resolves to a section that still defines the named symbol with the signature quoted in the story.
3. Every `Depends on` ID is `DONE` in `WBS.md` §5 (or belongs to E05 and precedes the story).
4. Every symbol the story calls (`DefaultDecisionManager`, `AuthorityResolver`, `AuthorityViolation`, `DECISION_SECTIONS`, `DefaultOutputApplier`, `DefaultOrchestrator`, `Scheduler`, `TaskRouter`, `BuiltinHookDeps`, `ApprovalWaiter`, `ConstitutionLoader`, `PolicyLoader`, `TableLoader`, generic `StateMachine`, `tests/fakes/fake_model_adapter.py::FakeModelAdapter`, `tests/e2e/conftest.py` fixtures) exists under the name used here; otherwise the story is corrected to the real name.
5. Specifically verify (these were planned from WBS §3 and architecture docs because `EPIC-01` S18–S31 and `EPIC-03` S06–S20 story bodies were not yet written at planning time): `src/walk/debate/models.py` + `__init__.py` exist (created by E01-S18 for `AgentInput.debate`); `src/walk/agents/templates/DEBATE.md.j2` exists (E01-S18); `src/walk/orchestrator/{service,scheduler,router,commands}.py` module names (E01-S29/S30); `src/walk/runtime/output_applier.py` (E01-S27); the E01-S11 generic state-machine constructor signature used for `DebateState`.

#### Behavior
1. For each checklist failure the planner edits the story in place (path, symbol or reference) and records the change in a `Refinement log` list appended to this story's Evidence section (`<story id>: <old> → <new>`).
2. A story that cannot be made ready without an architecture change is marked `BLOCKED` with a `BLOCKING:` note naming the missing name/decision, and the corresponding `NEW NAME:` line is added to `WBS.md` §6.
3. Nothing outside `docs/02-work-breakdown/` is modified.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given every E05 story When the Files tables are checked Then every `modify` path exists in the repo and every `create` path is absent | manual check recorded in Evidence (no automated test; docs task) |
| 2 | Given every E05 story When each `INTERFACES.md`/`DOMAIN-MODEL.md` reference is opened Then the referenced symbol and signature exist | manual check recorded in Evidence |
| 3 | Given every E05 story When its `Depends on` list is compared with `WBS.md` §5 Then every dependency outside E05 is `DONE` | manual check recorded in Evidence |
| 4 | Given the refined file When `grep -c "^### E05-"` Then 12 headings (X01, S01…S10, R01) and no ID renamed | manual check recorded in Evidence |

#### Evidence required
- Refinement log (list of corrections, or "no corrections").
- `git diff --stat` of the commit (only `docs/02-work-breakdown/` files).

#### Notes
- WBS §1 (`Exx-Xyy` refine task), §2 rule 3.
- Commit subject: `docs: refine epic 05 stories (E05-X01)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S01 — `DecisionManager.propose/classify_autonomy/escalate/override`

**Status:** TODO
**Type:** feat
**Requirements:** §44, §50, §51, §6.9, §6.10, §93, §137 (Inv. 5, 7)
**Depends on:** E05-X01, E04-S05
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Agent decision proposals are classified into §51 autonomy levels bounded by the proposer's authority and the project's `autonomy_level_max`; Level 0 proposals become ACCEPTED decisions, higher levels become persisted `Escalation`s, and the user can override any accepted decision — replacing the E04-S05 `NotSupported` stubs.

#### Scope
- In: `classify_autonomy`, `propose`, `escalate`, `override`, `EscalationRepository`, `LEVEL3_CONDITIONS`, `OutputApplier` wiring of `AgentOutput.decisions` and `AgentOutput.escalations`.
- Out: routing of escalations (E05-S02); `record()` for debate-sourced decisions (E05-S03); CLI (E05-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/decisions/service.py` | modify | `DefaultDecisionManager.propose`, `.classify_autonomy`, `.escalate`, `.override` |
| `src/walk/decisions/repository.py` | modify | `EscalationRepository`, `DecisionRepository.by_status`, `DecisionRepository.latest_version` |
| `src/walk/decisions/autonomy.py` | create | `LEVEL3_CONDITIONS`, `classify`, `matches_condition` |
| `src/walk/decisions/protocols.py` | modify | `EscalationSink` |
| `src/walk/decisions/__init__.py` | modify | re-exports |
| `src/walk/runtime/output_applier.py` | modify | — (`DefaultOutputApplier` calls `propose` per `output.decisions`, `escalate` per `output.escalations`; fills `AppliedEffects.decision_ids/escalation_ids`) |
| `src/walk/cli/composition.py` | modify | — (injects `project_autonomy_max` resolver and `EscalationSink` into `DefaultDecisionManager`) |
| `tests/decisions/test_autonomy.py` | create | — |
| `tests/decisions/test_service_propose.py` | create | — |
| `tests/decisions/test_service_override.py` | create | — |
| `tests/runtime/test_applier_decisions.py` | create | — |

#### Interface contract
Protocol methods: `INTERFACES.md §1.9 DecisionManager.propose/escalate/override/classify_autonomy` verbatim. Deltas:
```python
# src/walk/decisions/autonomy.py
LEVEL3_CONDITIONS: tuple[str, ...] = ("core gameplay change", "monetization", "major feature removal", "large scope increase",
                                      "major art direction change", "major schedule impact", "phase gate")      # §51 Level 3 list
def matches_condition(condition: str, *texts: str) -> bool:
    """True when every word of `condition` (lower-cased, len >= 3) occurs in the concatenation of `texts` (lower-cased)."""
def classify(proposal: DecisionProposal, authority: Authority, rules: list[EscalationRule], project_max: AutonomyLevel) -> AutonomyLevel:
    """level = proposal.autonomy_level;
    for rule in rules: if (rule.category is None or rule.category == proposal.category) and matches_condition(rule.condition, topic, position): level = max(level, rule.to_level)
    if any(matches_condition(c, topic, position) for c in LEVEL3_CONDITIONS): level = USER
    if proposal.category not in authority.decision_scope: level = max(level, MULTI_AGENT)
    if level > authority.max_autonomy_level and level == LOCAL: level = MULTI_AGENT        # cannot self-resolve
    if level > project_max and level < USER: level = USER                                   # Project.autonomy_level_max (§140)
    return level"""

# src/walk/decisions/protocols.py
class EscalationSink(Protocol):
    """Implemented by walk.orchestrator (handle_escalation); injected so decisions stays below orchestrator."""
    async def __call__(self, escalation: Escalation) -> None: ...

# src/walk/decisions/repository.py
class EscalationRepository(Repository[Escalation]):     # table escalations
    async def open_for_item(self, work_item_id: WorkItemId) -> list[Escalation]: ...   # resolved_decision_id IS NULL
    async def set_approval(self, escalation_id: str, approval_request_id: ApprovalRequestId) -> None: ...
    async def resolve(self, escalation_id: str, decision_id: DecisionId) -> None: ...

# src/walk/decisions/service.py
class DefaultDecisionManager:
    def __init__(self, repo: DecisionRepository, escalations: EscalationRepository, memory: MemoryManager, ledger: LedgerManager,
                 hooks: HookManager, ids: IdFactory, clock: Clock, authority_for: AuthorityResolver, workflow: WorkflowManager,
                 project_autonomy_max: Callable[[], AutonomyLevel], sink: EscalationSink | None) -> None: ...
```

#### Behavior
1. `classify_autonomy(proposal, authority, rules)` delegates to `autonomy.classify(..., project_autonomy_max())`; it is pure apart from that resolver.
2. `propose(proposal, by, work_item_id)`: allocates `DEC-NNNN`, persists `Decision(status=PROPOSED, owner=by.role, autonomy_level=<classified>, participants=[by.role], positions=[DecisionPosition(role=by.role, model_id=by.model_id, position=proposal.position, confidence=1.0)], related_work_items=[work_item_id] if given)`; writes no `.ai/` document for PROPOSED decisions (only ACCEPTED ones are documents, Inv. 8).
3. If the classified level is `LOCAL` → `record(decision, by=by)` in the same call; the returned decision is `ACCEPTED`.
4. Otherwise `escalate(EscalationRequest(to_level=level, category, question=f"{topic}: {position}", options=[position, *alternatives], recommendation=position, evidence_ids), from_role=by.role, work_item_id, run_id=by.run_id)` is called and the PROPOSED decision is returned; the escalation's ledger payload carries `proposal_decision_id`.
5. `escalate(request, from_role, work_item_id, run_id)`: id `ESC-<ULID>` (`new_ulid`), row in `escalations`, ledger `ESCALATION_RAISED{to_level, category, question, proposal_decision_id?}` (write point `decisions.DecisionManager`), fires `ON_ESCALATION` with payload `{"escalation_id", "to_level", "category", "work_item_id"}`, then awaits `sink(escalation)` when a sink is configured (E05-S02 supplies it; `None` in unit tests).
6. `override(decision_id, outcome, rationale)`: the target must be `ACCEPTED` (else `PermanentError("only accepted decisions can be overridden")`); in one `UnitOfWork`: target `status=OVERRIDDEN`, `overridden_by_user_at=now`; new `Decision` with new id, `version = target.version + 1`, `supersedes = target.id`, `owner=USER`, `outcome`, `rationale`, same category/topic/participants/positions/affected_systems/related_work_items, `autonomy_level=USER` → `record(new, by=Actor(role=USER))`; ledger `USER_OVERRIDE{command: "decisions.override", decision_id, new_decision_id}`; the superseded document is rewritten with `status: OVERRIDDEN` through `MemoryManager.write`.
7. `relevant_for` (E04-S05) now also excludes `OVERRIDDEN` decisions.
8. `DefaultOutputApplier.apply`: for each `output.decisions` → `propose(p, by=Actor(run.role, run.model_id, run.id), work_item_id=run.work_item_id)`; for each `output.escalations` → `escalate(...)`; ids collected into `AppliedEffects`; a `AuthorityViolation` from `propose` is converted into a `Finding(severity="RISK")` on the run and does not fail the run.
9. A proposal from a role without a constitution-backed authority (`authority_for` raises `ConstitutionError`) is treated as `Authority()` (empty scope, `max_autonomy_level=LOCAL`) → escalates at Level 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given LEAD_DEV authority (`scope=[TECH]`, max 1) and a TECH proposal at level 0 with no matching rule When classified Then `LOCAL` | `tests/decisions/test_autonomy.py::test_in_scope_level0_stays_local` |
| 2 | Given the same authority and a DESIGN proposal When classified Then `MULTI_AGENT` | `tests/decisions/test_autonomy.py::test_out_of_scope_raises_to_multi_agent` |
| 3 | Given rule `{condition: "core architecture migration", to_level: 3}` and topic "core architecture migration to ECS" When classified Then `USER` | `tests/decisions/test_autonomy.py::test_escalation_rule_matches_condition_words` |
| 4 | Given topic containing "monetization" When classified Then `USER` regardless of authority | `tests/decisions/test_autonomy.py::test_level3_list_forces_user` |
| 5 | Given `project_max=MULTI_AGENT` and classified `PO` When classified Then `USER` | `tests/decisions/test_autonomy.py::test_project_autonomy_max_caps_to_user` |
| 6 | Given `matches_condition("major art direction change", "Minor tweak")` Then False; with "major change to art direction" Then True | `tests/decisions/test_autonomy.py::test_matches_condition_word_based` |
| 7 | Given LEAD_DEV proposing an in-scope TECH decision When `propose` Then returned decision `ACCEPTED`, `DEC-0001.md` exists, `DECISION_RECORDED` written, no escalation row | `tests/decisions/test_service_propose.py::test_propose_level0_records_immediately` |
| 8 | Given SENIOR_DEV proposing a TECH decision When `propose` Then decision `PROPOSED`, one `escalations` row with `to_level=1`, `ESCALATION_RAISED` payload has `proposal_decision_id`, `ON_ESCALATION` fired once, no `.ai/decisions/` file | `tests/decisions/test_service_propose.py::test_propose_escalates_and_keeps_proposed` |
| 9 | Given a sink When `escalate` Then the sink receives the persisted `Escalation` after the ledger event | `tests/decisions/test_service_propose.py::test_escalate_calls_sink_after_persist` |
| 10 | Given `authority_for` raising `ConstitutionError` When `propose` Then escalated at level 1 | `tests/decisions/test_service_propose.py::test_unknown_authority_escalates` |
| 11 | Given ACCEPTED `DEC-0001` When `override("DEC-0001", "Use addressables", "cost")` Then `DEC-0001` OVERRIDDEN with timestamp, `DEC-0002` ACCEPTED version 2 `supersedes=DEC-0001` owner USER, `USER_OVERRIDE` ledger, both documents on disk with matching statuses | `tests/decisions/test_service_override.py::test_override_supersedes_and_logs` |
| 12 | Given a PROPOSED decision When `override` Then `PermanentError` and nothing written | `tests/decisions/test_service_override.py::test_override_requires_accepted` |
| 13 | Given OVERRIDDEN and ACCEPTED decisions on FEAT-0001 When `relevant_for` Then only the ACCEPTED one | `tests/decisions/test_service_override.py::test_relevant_for_excludes_overridden` |
| 14 | Given a fake LEAD_DEV output with 1 Level-0 decision and 1 escalation When applied Then `AppliedEffects.decision_ids == ["DEC-0001"]`, `escalation_ids` has one id | `tests/runtime/test_applier_decisions.py::test_applier_proposes_and_escalates` |
| 15 | Given a fake QC output proposing a TECH decision (out of scope) When applied Then run not failed, decision PROPOSED, escalation created | `tests/runtime/test_applier_decisions.py::test_applier_out_of_scope_proposal_escalates_not_fails` |

#### Evidence required
- Quality gate output.
- Demo: `walk decisions list --json` after a test run showing one `ACCEPTED` and one `PROPOSED` row; `walk ledger query --kind ESCALATION_RAISED --json` showing `payload.to_level == 1`.

#### Notes
- Invariant 5: `AgentOutput.decisions` never reach `ACCEPTED` without passing `classify` → `record`; Invariant 7: `Project.autonomy_level_max` is consulted on every classification.
- `NEW NAME:` `walk.decisions.autonomy` (`LEVEL3_CONDITIONS`, `classify`, `matches_condition`), `EscalationSink`, `EscalationRepository`, `DecisionRepository.by_status/latest_version`, escalation id format `ESC-<ULID>` (DOMAIN-MODEL §2 has no row for `Escalation.id`), `USER_OVERRIDE` write point extended to `decisions.DecisionManager.override` (ARCHITECTURE §4.3 lists `orchestrator.PhaseGate` only).
- Pitfall: `propose` must allocate the id before `classify` so the ledger payload can reference it even when the decision stays PROPOSED.
- Commit subject: `feat: add decision proposals, autonomy classification and override (E05-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S02 — `Orchestrator.handle_escalation` routing (L1 debate, L2 PO run, L3 user approval)

**Status:** TODO
**Type:** feat
**Requirements:** §50, §51, §6.9, §92 (approval path), §137 (Inv. 7, 14), §138 (Infinite Debate — authority)
**Depends on:** E05-S01, E02-S11
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every persisted `Escalation` is routed by its `AutonomyLevel`: Level 1 opens a debate between the proposer and the category counterpart, Level 2 opens an arbitration-only debate for the PRODUCT_OWNER, Level 3 creates an `ApprovalRequest(approver=USER)`; a user approval turns the escalation into an ACCEPTED decision owned by USER and unblocks the work item.

#### Scope
- In: `EscalationRouter` (the `EscalationSink` implementation), `DefaultOrchestrator.handle_escalation`, participant selection by category, Level-3 approval resolution through `walk approve/deny`, degradation when no debate opener is wired yet.
- Out: `DebateManager` implementation and the `debate_workflow` table (E05-S03); PO run scheduling and debate → USER escalation (E05-S05); conflict detection from review outputs (E05-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/debate/participants.py` | create | `CATEGORY_COUNTERPART`, `select_participants` |
| `src/walk/orchestrator/escalation.py` | create | `DebateOpener`, `EscalationRouter` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.handle_escalation`, `DefaultOrchestrator.resolve_escalation_approval` `(verify module name, E01-S29)` |
| `src/walk/orchestrator/commands.py` | modify | — (`approve`/`deny` handlers call `resolve_escalation_approval` when `approval.kind == "escalation"`) |
| `src/walk/cli/composition.py` | modify | — (builds `EscalationRouter`, injects it as `sink` into `DefaultDecisionManager`) |
| `tests/debate/__init__.py` | create | — |
| `tests/debate/test_participants.py` | create | — |
| `tests/orchestrator/test_escalation_router.py` | create | — |
| `tests/orchestrator/test_escalation_approval.py` | create | — |

#### Interface contract
`Orchestrator.handle_escalation` verbatim `INTERFACES.md §1.1`. Deltas:
```python
# src/walk/debate/participants.py
CATEGORY_COUNTERPART: dict[DecisionCategory, tuple[AgentRole, ...]] = {
    DecisionCategory.TECH: (AgentRole.LEAD_DEV, AgentRole.ORCHESTRATOR),
    DecisionCategory.DESIGN: (AgentRole.DESIGN_LEADER, AgentRole.ORCHESTRATOR),
    DecisionCategory.PRODUCT: (AgentRole.PRODUCT_OWNER, AgentRole.ORCHESTRATOR),
    DecisionCategory.QUALITY: (AgentRole.QC, AgentRole.LEAD_DEV),
    DecisionCategory.ART: (AgentRole.ART_DIRECTOR, AgentRole.DESIGN_LEADER, AgentRole.ORCHESTRATOR),
    DecisionCategory.RELEASE: (AgentRole.UA_RELEASE, AgentRole.ORCHESTRATOR),
    DecisionCategory.PROCESS: (AgentRole.PROCESS_ARCHITECT, AgentRole.ORCHESTRATOR),
}
def select_participants(from_role: AgentRole, category: DecisionCategory, enabled_roles: list[AgentRole]) -> list[AgentRole]:
    """[from_role, first enabled counterpart != from_role]; if none enabled -> ORCHESTRATOR; if that equals from_role -> LEAD_DEV.
    Always two distinct roles, proposer first."""

# src/walk/orchestrator/escalation.py
class DebateOpener(Protocol):
    """Structural subset of walk.debate.protocols.DebateManager.open (E05-S03); keeps S02 independent of S03."""
    async def open(self, topic: str, category: DecisionCategory, participants: list[AgentRole], *, opened_by: AgentRole,
                   work_item_id: WorkItemId | None, max_rounds: int | None = None) -> Debate: ...

class EscalationRouter:
    """Implements walk.decisions.protocols.EscalationSink."""
    def __init__(self, escalations: EscalationRepository, decisions: DecisionManager, permissions: PermissionManager,
                 workflow: WorkflowManager, enabled_roles: Callable[[], list[AgentRole]],
                 debates: DebateOpener | None, clock: Clock) -> None: ...
    async def __call__(self, escalation: Escalation) -> None: ...           # == route()
    async def route(self, escalation: Escalation) -> None: ...
    async def on_approval_decided(self, approval: ApprovalRequest) -> Decision | None: ...
    async def on_resolved(self, escalation: Escalation, decision: Decision) -> None:
        """EscalationRepository.resolve; if the work item is BLOCKED -> raise_event('unblock', payload {'blocker_resolved': True},
        actor_role ORCHESTRATOR, source KERNEL)."""

# DefaultOrchestrator
async def handle_escalation(self, escalation: Escalation) -> None: ...                        # delegates to EscalationRouter.route
async def resolve_escalation_approval(self, approval: ApprovalRequest) -> Decision | None: ...  # delegates to on_approval_decided
```
`ApprovalRequest.kind == "escalation"`; its stored request payload is `escalation.model_dump(mode="json")`.

#### Behavior
1. `route(escalation)` is idempotent: an escalation whose row json already has `routed_to`, or with `resolved_decision_id` set, is skipped.
2. Level 1 (`MULTI_AGENT`): `participants = select_participants(escalation.from_role, category, enabled_roles())`; `debates.open(topic=escalation.question, category, participants, opened_by=escalation.from_role, work_item_id=escalation.work_item_id)`; row json gains `routed_to: "DEBATE"`, `debate_id`.
3. Level 2 (`PO`): when `PRODUCT_OWNER ∈ enabled_roles()` → `debates.open(..., participants=[from_role, PRODUCT_OWNER], max_rounds=0)` (arbitration-only debate, E05-S03 Behavior 3), `routed_to: "PO_DEBATE"`; when PO is not enabled → handled as Level 3 and json carries `degraded_to_user: true`.
4. Level 3 (`USER`): `permissions.request_approval(escalation, kind="escalation", approver=Approver.USER, requested_by=escalation.from_role, run_id=escalation.run_id, work_item_id=escalation.work_item_id)`; `EscalationRepository.set_approval(escalation.id, approval.id)`; `routed_to: "USER_APPROVAL"`.
5. When `debates is None` (S03 not yet wired) Levels 1 and 2 degrade to Level 3 with `degraded_to_user: true`; nothing raises.
6. Routing writes no ledger event and fires no hook: `DecisionManager.escalate` already wrote `ESCALATION_RAISED` and fired `ON_ESCALATION` before calling the sink (ARCHITECTURE §4.3 write point); routing facts live in the `escalations` row json (`routed_to`, `routed_at`, `debate_id` | `approval_request_id`, `degraded_to_user`).
7. `on_approval_decided(approval)` for `kind == "escalation"`: APPROVED → build `Decision(id="DEC-0000", category, status=PROPOSED, topic=escalation.question, participants=[from_role, USER], positions=[DecisionPosition(role=from_role, model_id=None, position=recommendation or options[0], confidence=1.0)], evidence_ids, outcome=approval.note or recommendation or options[0], owner=USER, rationale="user approval <approval.id>", alternatives=options, affected_systems=[], related_work_items=[work_item_id] if any, autonomy_level=USER)` → `decisions.record(decision, by=Actor(role=USER))` → `on_resolved`; the PROPOSED decision named by the ledger payload `proposal_decision_id` (E05-S01) becomes `SUPERSEDED` and the new decision's `supersedes` points to it. DENIED or EXPIRED → that PROPOSED decision becomes `REJECTED`; the escalation stays unresolved; no `unblock`.
8. `on_resolved` unblocks only when the item's current state is `BLOCKED`; `GuardRejected`/`UnknownTransition` from `unblock` is logged (structured `extra`) and swallowed — the decision stays recorded.
9. `CommandConsumer` `approve`/`deny` handlers (E02-S11) call `resolve_escalation_approval` after `decide_approval` when `approval.kind == "escalation"`; other kinds are untouched.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given SENIOR_DEV, TECH, enabled roles `[ORCHESTRATOR, LEAD_DEV, SENIOR_DEV, QC]` When `select_participants` Then `[SENIOR_DEV, LEAD_DEV]` | `tests/debate/test_participants.py::test_counterpart_by_category` |
| 2 | Given LEAD_DEV, DESIGN, DESIGN_LEADER not enabled When `select_participants` Then `[LEAD_DEV, ORCHESTRATOR]` | `tests/debate/test_participants.py::test_disabled_counterpart_falls_back_to_orchestrator` |
| 3 | Given ORCHESTRATOR, PRODUCT, PO not enabled When `select_participants` Then `[ORCHESTRATOR, LEAD_DEV]` | `tests/debate/test_participants.py::test_always_two_distinct_roles` |
| 4 | Given a Level-1 escalation and a fake opener When `route` Then `open` called once with two participants and the `work_item_id`, row json has `debate_id` | `tests/orchestrator/test_escalation_router.py::test_level1_opens_debate` |
| 5 | Given a Level-2 escalation with PO enabled When `route` Then `open` called with `[from_role, PRODUCT_OWNER]` and `max_rounds=0` | `tests/orchestrator/test_escalation_router.py::test_level2_opens_arbitration_debate` |
| 6 | Given a Level-2 escalation with PO disabled When `route` Then one `ApprovalRequest(kind="escalation", approver=USER)` pending and json `degraded_to_user` true | `tests/orchestrator/test_escalation_router.py::test_level2_without_po_degrades_to_user` |
| 7 | Given a Level-3 escalation When `route` Then approval request persisted, `approval_request_id` set on the row, `APPROVAL_REQUESTED` ledger present | `tests/orchestrator/test_escalation_router.py::test_level3_requests_user_approval` |
| 8 | Given `debates=None` and a Level-1 escalation When `route` Then approval request created, no exception | `tests/orchestrator/test_escalation_router.py::test_no_opener_degrades_to_user` |
| 9 | Given an already routed escalation When `route` again Then no second debate or approval | `tests/orchestrator/test_escalation_router.py::test_route_is_idempotent` |
| 10 | Given a pending escalation approval and a BLOCKED story When approved with note "Use addressables" Then ACCEPTED decision owner USER outcome "Use addressables", `resolved_decision_id` set, story back in its `resume_state`, proposal SUPERSEDED | `tests/orchestrator/test_escalation_approval.py::test_approval_records_decision_and_unblocks` |
| 11 | Given the same approval denied Then no ACCEPTED decision, proposal `REJECTED`, story still BLOCKED | `tests/orchestrator/test_escalation_approval.py::test_denial_rejects_proposal_and_keeps_blocked` |
| 12 | Given an `approve` command for an approval of kind `tool` When consumed Then `resolve_escalation_approval` not called | `tests/orchestrator/test_escalation_approval.py::test_non_escalation_approvals_untouched` |

#### Evidence required
- Quality gate output.
- Demo: after a fake run proposes a Level-3 decision: `walk approvals --pending --json` shows `kind == "escalation"`; `walk approve APV-0001 --note "Keep current economy"`; `walk decisions list --json` shows the new `ACCEPTED` row with `owner == "USER"`; `walk work show STORY-0001` shows the item back in its previous state.

#### Notes
- INTERFACES §1.1 docstring ("1→DebateManager.open, 2→PO run, 3→ApprovalRequest(USER)"); Level 2 is realised as an arbitration-only debate so that the PO run is scheduled by the same mechanism as debate runs (E05-S04/S05) and appears in `walk debates list`.
- `NEW NAME:` `walk.debate.participants` (`CATEGORY_COUNTERPART`, `select_participants`), `walk.orchestrator.escalation` (`DebateOpener`, `EscalationRouter`), `DefaultOrchestrator.resolve_escalation_approval`, `ApprovalRequest.kind == "escalation"`, escalation row json keys `routed_to/routed_at/debate_id/degraded_to_user`, `max_rounds=0` arbitration-only semantics (defined in E05-S03).
- Pitfall: the router runs inside `DecisionManager.escalate` after the escalation's own transaction committed; it opens its own `UnitOfWork`s and never re-enters `escalate`.
- Commit subject: `feat: route escalations to debate, po arbitration or user approval (E05-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S03 — `DebateManager` and `debate_workflow` table

**Status:** TODO
**Type:** feat
**Requirements:** §45, §46, §44, §6.7, §137 (Inv. 5, 8), §138 (Infinite Debate — round limit, budget)
**Depends on:** E05-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `Debate` aggregate with persisted positions runs through the `debate_workflow v1.0` table (OPEN → IN_ROUND → CONSENSUS_CHECK → RESOLVED | next round | ESCALATED_PO | ESCALATED_USER | ABANDONED) with a configurable round limit (default 3) and a per-debate budget; a resolved debate records an ACCEPTED decision through `DecisionManager.record` — replacing the E04-S05 `NotSupported("E05-S03")` stub.

#### Scope
- In: `walk.debate` protocols/repository/service/errors/guards/consensus, `debate_workflow.yaml`, `DebatePolicy` loaded from `policies.yaml`, `DebatePosition.agrees_with_role`, debate-aware `record()`.
- Out: scheduling debate runs and producing positions from agent output (E05-S04); PO/USER escalation handling, budget exhaustion and `ESCALATION_RAISED` for debates (E05-S05); CLI (E05-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/debate/__init__.py` | modify `(verify: created by E01-S18 with models.py)` | re-exports |
| `src/walk/debate/models.py` | modify | `DebatePosition.agrees_with_role: AgentRole \| None`, `DebatePolicy` |
| `src/walk/debate/protocols.py` | create | `DebateManager` (INTERFACES §1.9 verbatim) |
| `src/walk/debate/errors.py` | create | `DebateStateError`, `NotParticipant`, `DuplicatePosition` |
| `src/walk/debate/repository.py` | create | `DebateRepository`, `DebatePositionRepository` |
| `src/walk/debate/consensus.py` | create | `compute_agreement`, `leading_position` |
| `src/walk/debate/guards.py` | create | `register_debate_guards`, guards listed below |
| `src/walk/debate/state_machine.py` | create | `DebateStateMachine`, `DEBATE_TABLE_PATH`, `load_debate_table` |
| `src/walk/debate/service.py` | create | `DefaultDebateManager` |
| `src/walk/workflow/tables/debate_workflow.yaml` | create | — |
| `src/walk/decisions/service.py` | modify | `DefaultDecisionManager.record` (debate path replaces `NotSupported("E05-S03")`) |
| `src/walk/agents/policy_loader.py` | modify | `PolicyLoader.load_debate_policy` |
| `src/walk/agents/defaults/policies.yaml` | modify | — (top-level `debate:` block) |
| `src/walk/cli/composition.py` | modify | — (wires `DefaultDebateManager`; passes it as `debates` to `EscalationRouter` when E05-S02 is merged; `KernelHandle.debates`) |
| `tests/debate/test_models.py` | create | — |
| `tests/debate/test_consensus.py` | create | — |
| `tests/debate/test_guards.py` | create | — |
| `tests/debate/test_table.py` | create | — |
| `tests/debate/test_service_lifecycle.py` | create | — |
| `tests/debate/test_repository.py` | create | — |
| `tests/decisions/test_service_record_debate.py` | create | — |
| `tests/agents/test_policy_loader.py` | modify | — |

#### Interface contract
Protocol: `INTERFACES.md §1.9 DebateManager` verbatim. Table: `INTERFACES.md §3.5` plus two arbitration rows (Behavior 3). Deltas:
```python
# src/walk/debate/models.py
class DebatePosition(WalkModel):            # DOMAIN-MODEL §4.8 fields +
    agrees_with_role: AgentRole | None = Field(default=None, description="Participant whose position this one endorses; None = own distinct position")

class DebatePolicy(WalkModel):
    """Kernel defaults overridable by `.ai/agents/policies.yaml` top-level `debate:` block."""
    max_rounds: int = Field(default=3, ge=0, le=10)
    consensus_threshold: float = Field(default=0.75, ge=0.5, le=1.0)
    cost_usd: float = Field(default=5.0, gt=0)

# src/walk/debate/consensus.py
def leading_position(positions: list[DebatePosition]) -> DebatePosition | None:
    """Position with most endorsements (own + others' agrees_with_role == its role); ties → highest confidence, then earliest `at`."""
def compute_agreement(positions: list[DebatePosition], participants: list[AgentRole]) -> float:
    """(1 + number of positions whose agrees_with_role == leader.role) / len(participants); 0.0 when no positions."""

# src/walk/debate/guards.py — registered via walk.workflow.guards.register_guard; names used by debate_workflow.yaml
# participants_at_least_two, budget_available (reused from E01-S09), role_in_participants, round_matches, all_positions_in,
# agreement_at_threshold, round_below_max, round_at_max, po_enabled, po_disabled, arbitration_only,
# po_output_completed_with_decision, budget_exhausted_or_user
def register_debate_guards() -> None: ...
# payload keys read: agreement (float), po_enabled (bool), role, round, positions_in (int), output_status, has_decision, budget_ok, by_user

# src/walk/debate/state_machine.py
DEBATE_TABLE_PATH: Path            # TABLES_DIR / "debate_workflow.yaml"
def load_debate_table() -> TransitionTable: ...
class DebateStateMachine:          # the E01-S11 generic engine instantiated with DebateState (constructor verified by E05-X01 item 5)
    def transition_for(self, state: DebateState, event: str, debate: Debate, ctx: TransitionContext) -> Transition: ...

# src/walk/debate/service.py
class DefaultDebateManager:
    def __init__(self, repo: DebateRepository, positions: DebatePositionRepository, decisions: DecisionManager,
                 budgets: BudgetManager, ledger: LedgerManager, hooks: HookManager, ids: IdFactory, clock: Clock,
                 policy: DebatePolicy, po_enabled: Callable[[], bool]) -> None: ...
    async def get(self, debate_id: DebateId) -> Debate: ...
    async def list(self, *, states: list[DebateState] | None = None, work_item_id: WorkItemId | None = None) -> list[Debate]: ...
    async def positions_for(self, debate_id: DebateId, round: int | None = None) -> list[DebatePosition]: ...

# src/walk/agents/policy_loader.py
def load_debate_policy(self) -> DebatePolicy: ...   # defaults block merged with project `debate:` block
```
`DebateRepository(Repository[Debate])` → table `debates` (columns + json); `DebatePositionRepository` → `debate_positions`; `by_state(states)`, `for_item(work_item_id)`, `for_round(debate_id, round)`.

#### Behavior
1. `open(topic, category, participants, *, opened_by, work_item_id, max_rounds=None)`: validates `len(set(participants)) >= 2` (`DebateStateError` otherwise, except Behavior 3); allocates `DEB-NNNN` (`IdFactory`, prefix `DBT`, width 4); `max_rounds = max_rounds if not None else policy.max_rounds`; `consensus_threshold = policy.consensus_threshold`; `BudgetManager.ensure(BudgetScope.TASK, debate.id, BudgetPolicy(per_task={REVIEW_LOOPS: max_rounds or 1, COST_USD: policy.cost_usd}))` → `budget_id`; persists OPEN; raises `start_round` → IN_ROUND, `round = 1`; in the same transaction ledger `DEBATE_OPENED{topic, category, participants, work_item_id, max_rounds}`; after commit fires `ON_DEBATE_OPENED` with payload `{"debate_id", "work_item_id", "participants"}`. Returns the IN_ROUND debate.
2. `submit_position(position)`: debate must be IN_ROUND (`DebateStateError`), `position.role ∈ participants` (`NotParticipant`), `position.round == debate.round` (`DebateStateError`), no existing position for `(round, role)` (`DuplicatePosition`); `agrees_with_role` must be another participant or `None` (`DebateStateError`); `changed_from_previous` is computed by the service (`True` when the role's previous-round `position` text differs), never trusted from input; persists the row, ledger `DEBATE_POSITION{round, role, confidence, agrees_with_role}`, raises `position_submitted` (self-transition). When every participant has a position for the round → `close_round()` is invoked and its result returned.
3. Arbitration-only debates (`max_rounds == 0`, opened by E05-S02 for Level 2): `open` persists OPEN then raises `escalate` directly: `OPEN → ESCALATED_PO` when `po_enabled()`, else `OPEN → ESCALATED_USER` (two extra table rows with guards `arbitration_only` + `po_enabled`/`po_disabled`); no positions are collected; `ON_ESCALATION` payload `{"debate_id", "to_level": 2|3, "category", "work_item_id"}`. The `ESCALATION_RAISED` ledger event for debate escalations is added in E05-S05.
4. `close_round(debate_id)`: IN_ROUND → CONSENSUS_CHECK (`all_positions_in`), fires `ON_DEBATE_ROUND_COMPLETE{debate_id, round, agreement}`; `BudgetManager.consume(TASK, debate.id, REVIEW_LOOPS, 1)`; `agreement = compute_agreement(round positions, participants)`; then exactly one of: `consensus` (`agreement >= consensus_threshold`) → `resolve(outcome=leading.position, by=Actor(role=KERNEL), rationale=leading.reasoning)`; `next_round` (`round < max_rounds` and budget ok) → IN_ROUND with `round + 1`; `escalate` (`round >= max_rounds` or budget exhausted) → ESCALATED_PO when `po_enabled()` else ESCALATED_USER, firing `ON_ESCALATION` as in Behavior 3. `final_positions` is replaced by the latest round's positions on every `close_round`.
5. `resolve(debate_id, outcome, *, by, rationale)`: allowed from CONSENSUS_CHECK (by KERNEL), ESCALATED_PO (by PRODUCT_OWNER) and ESCALATED_USER (by USER) — any other combination `DebateStateError`; builds `Decision(id="DEC-0000", category, status=PROPOSED, topic, participants, positions=[DecisionPosition(role, model_id, position, confidence) per final position], evidence_ids=union of positions' evidence_ids, outcome, owner=by.role, rationale, alternatives=[p.alternative for p in final_positions if p.alternative], affected_systems=[], related_work_items=[work_item_id] if set, autonomy_level=MULTI_AGENT|PO|USER by resolver, debate_id=debate.id)` → `decisions.record(decision, by=by)`; sets `decision_id`, `resolved_at`, state RESOLVED via `consensus`/`po_resolved`/`user_resolved`; ledger `DEBATE_RESOLVED{decision_id, resolved_by, rounds}`; fires `ON_DEBATE_RESOLVED{debate_id, decision_id, work_item_id}`.
6. `abandon(debate_id, reason)`: any non-terminal state → ABANDONED (guard `budget_exhausted_or_user`: payload `by_user` or `budget_ok == False`); ledger `DEBATE_RESOLVED{outcome: "ABANDONED", reason}`; no decision; fires no `ON_DEBATE_RESOLVED`.
7. `DefaultDecisionManager.record` (E04-S05 Behavior 1 extended): when `decision.debate_id` is set the actor must be `KERNEL`, `PRODUCT_OWNER` or `USER`; any other role → `AuthorityViolation`; `KERNEL` without `debate_id` → `AuthorityViolation` (epic planning decision).
8. Every state change goes through `DebateStateMachine` + the table; `PHASE_TRANSITION`-style ledger events are not written for debates (`DEBATE_*` kinds only, ARCHITECTURE §4.3). The debate row (`state`, `round`, `json`), the position row and the ledger event are committed in one `UnitOfWork`; hooks fire after commit.
9. `load_debate_table()` validates every guard name against the registry; `register_debate_guards()` is called at import of `walk.debate.service` and is idempotent.
10. `policies.yaml` `debate:` block: `{max_rounds: 3, consensus_threshold: 0.75, cost_usd: 5.0}`; project values outside the field bounds → `ConfigError`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `debate_workflow.yaml` loads Then 13 rows: the 11 INTERFACES §3.5 rows plus `OPEN→ESCALATED_PO` and `OPEN→ESCALATED_USER` (`escalate`), version `1.0` | `tests/debate/test_table.py::test_debate_workflow_matches_interfaces_plus_arbitration_rows` |
| 2 | Given a YAML row naming an unregistered guard When loaded Then `ConfigError` | `tests/debate/test_table.py::test_unknown_guard_rejected` |
| 3 | Given positions A(own), B(agrees A), C(own) with participants [A,B,C] When `compute_agreement` Then `2/3`; leader A | `tests/debate/test_consensus.py::test_agreement_counts_endorsements_of_leader` |
| 4 | Given two own positions with confidences 0.9/0.6 Then leader is the 0.9 one and agreement `0.5` | `tests/debate/test_consensus.py::test_tie_breaks_by_confidence` |
| 5 | For each guard, Given payload true/false Then ok/not ok with reason (parametrised) | `tests/debate/test_guards.py::test_debate_guards_evaluate_payload_keys` |
| 6 | When `open("ECS or MonoBehaviour", TECH, [LEAD_DEV, SENIOR_DEV], opened_by=SENIOR_DEV, work_item_id=STORY-0001)` Then `DEB-0001` IN_ROUND round 1, budget `TASK:DEB-0001:REVIEW_LOOPS` limit 3, `DEBATE_OPENED` written, `ON_DEBATE_OPENED` fired once | `tests/debate/test_service_lifecycle.py::test_open_starts_round_one_with_budget` |
| 7 | When `open` with one participant Then `DebateStateError` and nothing persisted | `tests/debate/test_service_lifecycle.py::test_open_requires_two_participants` |
| 8 | Given IN_ROUND When QC (not a participant) submits Then `NotParticipant`; wrong round Then `DebateStateError`; same role twice Then `DuplicatePosition` | `tests/debate/test_service_lifecycle.py::test_submit_position_validations` |
| 9 | Given both participants submit, second agreeing with first When the second `submit_position` Then `close_round` ran: state RESOLVED, `DEBATE_RESOLVED` written, decision `ACCEPTED` with `debate_id`, `owner == KERNEL`, `autonomy_level == MULTI_AGENT`, `.ai/decisions/DEC-0001.md` exists, `ON_DEBATE_ROUND_COMPLETE` then `ON_DEBATE_RESOLVED` fired | `tests/debate/test_service_lifecycle.py::test_consensus_resolves_and_records_decision` |
| 10 | Given both disagree in round 1 (max_rounds 3) When closed Then IN_ROUND round 2, `REVIEW_LOOPS` consumed 1, `final_positions` has 2 entries | `tests/debate/test_service_lifecycle.py::test_no_consensus_opens_next_round` |
| 11 | Given disagreement at round == max_rounds and `po_enabled()` True When closed Then ESCALATED_PO and `ON_ESCALATION` payload `to_level == 2` | `tests/debate/test_service_lifecycle.py::test_round_limit_escalates_to_po` |
| 12 | Given the same with `po_enabled()` False Then ESCALATED_USER and `to_level == 3` | `tests/debate/test_service_lifecycle.py::test_round_limit_escalates_to_user_without_po` |
| 13 | Given `open(..., max_rounds=0)` with PO enabled Then state ESCALATED_PO immediately, no positions, `ON_ESCALATION` fired | `tests/debate/test_service_lifecycle.py::test_arbitration_only_debate_skips_rounds` |
| 14 | Given ESCALATED_PO When `resolve(by=Actor(PRODUCT_OWNER))` Then RESOLVED, decision owner PRODUCT_OWNER level PO; `resolve(by=Actor(SENIOR_DEV))` Then `DebateStateError` | `tests/debate/test_service_lifecycle.py::test_resolve_authority_by_state` |
| 15 | Given IN_ROUND When `abandon(reason="user")` with `by_user` Then ABANDONED, no decision, `DEBATE_RESOLVED` outcome ABANDONED | `tests/debate/test_service_lifecycle.py::test_abandon_without_decision` |
| 16 | Given a position in round 2 whose text differs from the role's round-1 text Then stored `changed_from_previous == True` | `tests/debate/test_service_lifecycle.py::test_changed_from_previous_computed` |
| 17 | Given a `Decision(debate_id="DEB-0001")` When `record(by=Actor(KERNEL))` Then ACCEPTED; `by=Actor(LEAD_DEV)` Then `AuthorityViolation`; no `debate_id` and `by=Actor(KERNEL)` Then `AuthorityViolation` | `tests/decisions/test_service_record_debate.py::test_record_debate_path_actors` |
| 18 | Given repository round trips for `Debate` and `DebatePosition` Then equal after reload; `for_round` returns only that round | `tests/debate/test_repository.py::test_repository_roundtrip_and_round_filter` |
| 19 | Given project `policies.yaml` with `debate: {max_rounds: 2}` When `load_debate_policy` Then `max_rounds == 2`, other fields default; `max_rounds: 99` Then `ConfigError` | `tests/agents/test_policy_loader.py::test_debate_policy_merge_and_bounds` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --kind DEBATE_OPENED --kind DEBATE_POSITION --kind DEBATE_RESOLVED --json` after the lifecycle test fixture DB shows the three kinds for `DEB-0001`; `sqlite3 .ai/kernel.db "select id,state,round from debates"`.

#### Notes
- ADR-0010 D-3/D-4; INTERFACES §1.9, §3.5; DOMAIN-MODEL §4.8, §6.2 (`debates`, `debate_positions`); ARCHITECTURE §5.5 (`max_rounds` default 3). Epic planning decisions: debate budgets at `BudgetScope.TASK` with `scope_id = <DebateId>`; guards registered through `walk.workflow.guards.register_guard`; table under `src/walk/workflow/tables/`.
- `NEW NAME:` `DebatePosition.agrees_with_role` (WBS §6 attributes it to E05-S04 — the field is added here so `close_round` is testable; E05-S04 produces it from agent output), `DebatePolicy` + `policies.yaml` `debate:` block + `PolicyLoader.load_debate_policy`, `walk.debate.{consensus,guards,state_machine}`, errors `DebateStateError`/`NotParticipant`/`DuplicatePosition`, id prefix `DBT` (DOMAIN-MODEL §2 has no `DebateId` row), extra table rows `OPEN --escalate--> ESCALATED_PO|ESCALATED_USER` with guard `arbitration_only`, `DefaultDebateManager.get/list/positions_for`.
- Parallelism: this story and E05-S02 both modify `src/walk/cli/composition.py`; merge S02 first (WBS §8 set `{S01→S02} ∥ {S03→S04→S05}` holds for all other files).
- Pitfall: `resolve` must call `record` inside the debate transaction's `UnitOfWork` only if `DecisionManager.record` accepts an outer unit of work; otherwise record first, then commit the debate state — never leave a RESOLVED debate without `decision_id`.
- Commit subject: `feat: add debate manager with lifecycle table and consensus (E05-S03)`.

#### Evidence (filled by implementer)
_pending_

---
### E05-S04 — Debate runs and `DebatePosition` output (incl. `agrees_with_role`)

**Status:** TODO
**Type:** feat
**Requirements:** §45, §46, §6.7, §10.1, §23, §126, §137 (Inv. 5), §138 (Infinite Debate — budget)
**Depends on:** E05-S03, E03-S07
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
For every IN_ROUND debate the scheduler starts exactly one `DEBATE` run per participant per round (INTERFACES §4 DEBATE row), each run receives the debate and the previous round's positions through `AgentInput.debate` and the `DEBATE` template, and the run's `AgentOutput.debate_position` is normalised by the kernel and submitted to `DebateManager.submit_position` — so rounds advance without any manual step.

#### Scope
- In: pure turn computation (`pending_turns`), `Scheduler.schedule_debate_turns` (tick step after work-item admission), `DefaultTaskRouter.route_debate`, kernel normalisation of `debate_position`, `DefaultOutputApplier` DEBATE branch, `DEBATE.md.j2` enrichment, fake-adapter helper for scripted positions.
- Out: PO arbitration runs in ESCALATED_PO, debate → USER escalation, budget-exhaustion abandon (E05-S05); opening debates from review disagreement (E05-S08); `DebatePosition.agrees_with_role` field itself (added by E05-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/debate/scheduling.py` | create | `DebateTurn`, `pending_turns`, `turn_idempotency_key` |
| `src/walk/debate/normalise.py` | create | `normalise_position` |
| `src/walk/debate/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/router.py` | modify | `DefaultTaskRouter.route_debate` |
| `src/walk/orchestrator/scheduler.py` | modify | `Scheduler.schedule_debate_turns` (called from `tick`) |
| `src/walk/runtime/output_applier.py` | modify | — (`DefaultOutputApplier.apply`: purpose `DEBATE` branch) |
| `src/walk/runtime/errors.py` | modify | `MissingDebatePosition(OutputInvalid)` |
| `src/walk/agents/templates/DEBATE.md.j2` | modify | — |
| `src/walk/cli/composition.py` | modify | — (injects `DebateManager` into `Scheduler` and `DefaultOutputApplier`) |
| `tests/fakes/fake_model_adapter.py` | modify | `debate_output` (test helper) |
| `tests/debate/test_scheduling.py` | create | — |
| `tests/debate/test_normalise.py` | create | — |
| `tests/orchestrator/test_scheduler_debate.py` | create | — |
| `tests/orchestrator/test_router.py` | modify | — |
| `tests/runtime/test_applier_debate.py` | create | — |
| `tests/agents/test_templates_debate.py` | create | — |

#### Interface contract
`AgentExecutor.start(..., debate=...)` (INTERFACES §1.13), `AgentInput.debate` / `AgentOutput.debate_position` (DOMAIN-MODEL §4.2), `DebateManager.submit_position` (INTERFACES §1.9), routing row `DEBATE | IN_ROUND | each participant | DEBATE` (INTERFACES §4). Deltas:
```python
# src/walk/debate/scheduling.py
class DebateTurn(FrozenModel):
    debate_id: DebateId
    round: int
    role: AgentRole
    work_item_id: WorkItemId

def pending_turns(debate: Debate, submitted: list[DebatePosition], running_roles: set[AgentRole]) -> list[DebateTurn]:
    """Pure. [] unless debate.state == IN_ROUND and debate.work_item_id is not None.
    One turn per participant (in `participants` order) with no position for debate.round and not in running_roles."""

def turn_idempotency_key(turn: DebateTurn) -> str:
    """f"debate:{debate_id}:{round}:{role}"."""

# src/walk/debate/normalise.py
def normalise_position(raw: DebatePosition, *, debate: Debate, run_id: RunId, role: AgentRole, model_id: ModelId) -> DebatePosition:
    """Kernel-owned fields overwrite agent-supplied ones: debate_id, round=debate.round, role, model_id, run_id,
    changed_from_previous=False (recomputed by DebateManager), at=now. agrees_with_role == role -> None.
    agrees_with_role not in participants -> None. Text fields stripped; empty `position` -> MissingDebatePosition."""

# src/walk/orchestrator/router.py
class DefaultTaskRouter:
    def route_debate(self, debate: Debate, role: AgentRole) -> RouteDecision:
        """purpose='DEBATE'; profile.required_capabilities=[PLANNING, LONG_CONTEXT_REASONING]; profile.risk from the work item;
        cross_model_review=False; role must be in debate.participants (PermissionDenied otherwise)."""

# src/walk/orchestrator/scheduler.py
class Scheduler:
    async def schedule_debate_turns(self, capacity: int) -> int:
        """Runs after INTERFACES §5.1 step 4; returns runs started (<= capacity)."""

# src/walk/runtime/errors.py
class MissingDebatePosition(OutputInvalid): ...

# tests/fakes/fake_model_adapter.py
def debate_output(position: str, *, agrees_with_role: AgentRole | None = None, confidence: float = 0.8,
                  reasoning: str = "scripted", alternative: str = "") -> AgentOutput: ...
```

#### Behavior
1. `Scheduler.tick` (INTERFACES §5.1) gains step 4b: after work-item admission, `schedule_debate_turns(max_parallel_agents - running_count)`; returned count is added to `started`. A paused project schedules no turns (step 1 unchanged).
2. `schedule_debate_turns`: `DebateManager.list(states=[IN_ROUND])` ordered by `opened_at`; for each debate, `pending_turns(debate, positions_for(debate.id, debate.round), roles of running runs whose run.purpose == "DEBATE" and whose AgentInput.debate.id == debate.id)`; for each turn while capacity remains: skip if `IdempotencyStore.has(turn_idempotency_key(turn))`; `route = router.route_debate(debate, turn.role)`; budgets = `BudgetManager.ensure(TASK, item.id, policy.budget_policy)` plus the debate's `TASK:<DEB>:COST_USD` row; effort and model as §5.1 steps 9–10; `AgentManager.instantiate`; `AgentExecutor.start(agent, item, "DEBATE", debate=debate)`; record the key → run id.
3. The work item named by `debate.work_item_id` may be in any state (typically `BLOCKED`); debate turns never raise a work-item event. Debates with `work_item_id is None` are skipped (epic planning decision).
4. `RuntimePolicy.max_parallel_runs` per role is respected exactly as for work items; a role busy elsewhere is retried next tick.
5. `DefaultOutputApplier.apply(run, output)` with `run.purpose == "DEBATE"`: requires `output.status == COMPLETED` and `output.debate_position is not None`, else `MissingDebatePosition` (run → `FAILED`, retried under the normal retry policy; the idempotency key is released on `FAILED`). It then applies findings/evidence/decisions/escalations as for other purposes, normalises the position with `normalise_position(..., debate=<reloaded via DebateManager.get>, run_id=run.id, role=run.role, model_id=run.model_id)` and calls `submit_position`; `AppliedEffects.workflow_event` is `None`.
6. If the debate left IN_ROUND or advanced to another round before the output arrives (`DebateStateError` from `submit_position`), the position is dropped, a `Finding(severity="WARNING", summary="stale debate position")` is attached to the run and the run still ends `COMPLETED`.
7. `DebatePosition.evidence_ids` is replaced by the ids of evidence recorded from this same output (`AppliedEffects.evidence_ids`) plus agent-supplied ids that exist in `evidence_records`; unknown ids are dropped (Invariant 5: an opinion carries only real evidence).
8. `DEBATE.md.j2` renders: topic, category, round `n` of `max_rounds`, participants, the caller's professional bias (`agent.constitution.professional_bias`), every entry of `debate.final_positions` (role, position, reasoning, cost, risk, alternative, confidence) except the caller's own, the §45 field list, and the rule "set `agrees_with_role` to the participant whose position you now endorse, or leave it null to hold your own; you may change your opinion when stronger evidence appears (§45)"; output status options `COMPLETED`, `NEEDS_INPUT`, `FAILED`; includes `_output_contract.md.j2`. Round 1 renders "No previous positions."
9. Rendering is deterministic (same debate and agent → byte-identical text) and contains no provider name.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an IN_ROUND debate round 1 with participants `[SENIOR_DEV, LEAD_DEV]` and no positions When `pending_turns` Then two turns in participant order | `tests/debate/test_scheduling.py::test_pending_turns_one_per_participant` |
| 2 | Given SENIOR_DEV already submitted and LEAD_DEV running Then `[]` | `tests/debate/test_scheduling.py::test_pending_turns_skips_submitted_and_running` |
| 3 | Given an ESCALATED_PO debate or a debate without work item Then `[]` | `tests/debate/test_scheduling.py::test_pending_turns_only_in_round_with_item` |
| 4 | Given raw position with `round=9`, `role=QC`, `agrees_with_role` = own role When normalised for LEAD_DEV round 2 Then round 2, role LEAD_DEV, `agrees_with_role is None`, `run_id` set | `tests/debate/test_normalise.py::test_kernel_fields_overwrite_agent_fields` |
| 5 | Given `agrees_with_role=DESIGN_LEADER` not a participant Then normalised `agrees_with_role is None`; empty `position` Then `MissingDebatePosition` | `tests/debate/test_normalise.py::test_invalid_agreement_and_empty_position` |
| 6 | Given `debate` with LEAD_DEV participant When `route_debate(debate, LEAD_DEV)` Then purpose `DEBATE`, `cross_model_review False`; non-participant Then `PermissionDenied` | `tests/orchestrator/test_router.py::test_route_debate_participants_only` |
| 7 | Given one IN_ROUND debate on STORY-0001 and capacity 4 When `tick` Then two runs with purpose `DEBATE` started, each `AgentInput.debate.id == "DEB-0001"`, budget ids include `TASK:DEB-0001:COST_USD` | `tests/orchestrator/test_scheduler_debate.py::test_tick_starts_one_run_per_participant` |
| 8 | Given the same tick executed twice Then still two runs (idempotency key `debate:DEB-0001:1:<role>`) | `tests/orchestrator/test_scheduler_debate.py::test_debate_turns_idempotent_across_ticks` |
| 9 | Given capacity 1 Then one run started this tick and the second next tick | `tests/orchestrator/test_scheduler_debate.py::test_debate_turns_respect_capacity` |
| 10 | Given a project paused Then no debate run started | `tests/orchestrator/test_scheduler_debate.py::test_paused_project_schedules_no_turns` |
| 11 | Given a fake DEBATE run output `debate_output("Use ECS", confidence=0.9)` When applied Then one `debate_positions` row for round 1 role of the run, `DEBATE_POSITION` ledger, `workflow_event is None` | `tests/runtime/test_applier_debate.py::test_applier_submits_normalised_position` |
| 12 | Given the second participant's output agreeing with the first When applied Then the debate is RESOLVED and an ACCEPTED decision exists (via E05-S03 `close_round`) | `tests/runtime/test_applier_debate.py::test_last_position_closes_round` |
| 13 | Given a DEBATE output without `debate_position` When applied Then `MissingDebatePosition` and run `FAILED` | `tests/runtime/test_applier_debate.py::test_missing_position_fails_run` |
| 14 | Given the debate moved to round 2 before a round-1 output arrives When applied Then no position row, WARNING finding "stale debate position", run `COMPLETED` | `tests/runtime/test_applier_debate.py::test_stale_position_dropped_with_finding` |
| 15 | Given a position citing `EVD-9999` (unknown) and one evidence draft in the same output Then stored `evidence_ids` equals only the new evidence id | `tests/runtime/test_applier_debate.py::test_position_evidence_restricted_to_recorded` |
| 16 | Given round 2 with LEAD_DEV's round-1 position When rendering DEBATE for SENIOR_DEV Then text contains LEAD_DEV's position and reasoning, "round 2 of 3", `agrees_with_role`, and not SENIOR_DEV's own previous position block | `tests/agents/test_templates_debate.py::test_debate_template_shows_other_positions` |
| 17 | Given round 1 Then "No previous positions."; rendered twice Then byte-identical | `tests/agents/test_templates_debate.py::test_debate_template_round_one_and_deterministic` |

#### Evidence required
- Quality gate output.
- Demo: with a debate fixture DB, `walk run --once --json` then `walk runs list --json` shows two runs with `purpose == "DEBATE"`; after the fake outputs are applied `walk ledger query --kind DEBATE_POSITION --json` shows two events for `DEB-0001` round 1.

#### Notes
- INTERFACES §4 DEBATE rows, §5.1; ARCHITECTURE §3.2 step 6 (applier order); ADR-0004 (no chain-of-thought in positions — `reasoning` is the stated rationale only).
- `NEW NAME:` `walk.debate.scheduling` (`DebateTurn`, `pending_turns`, `turn_idempotency_key`), `walk.debate.normalise.normalise_position`, `DefaultTaskRouter.route_debate`, `Scheduler.schedule_debate_turns` (tick step 4b), `MissingDebatePosition`, idempotency key `debate:<id>:<round>:<role>`, test helper `debate_output`. WBS §6 attributes `DebatePosition.agrees_with_role` to this story; the field is created in E05-S03 and produced here.
- Debate ids follow DOMAIN-MODEL §2 (`DEB-` width 4, e.g. `DEB-0001`). E05-S03 Behavior 1, AC 6 and Notes say `DBT`; E05-X01 must correct E05-S03 to `DEB` (the `DebateId` pattern in `walk.common.ids` rejects `DEB-`).
- Pitfall: the running-roles check must use the run's debate id, not only the role — the same role may participate in two debates concurrently.
- Pitfall: `DEBATE` runs need a worktree only for reading; `SandboxManager.create` is reused unchanged, the `BoundaryAuditor` must report any write as a violation because the DEBATE template states the run never edits files (`allowed_paths=[]`).
- Commit subject: `feat: schedule debate runs and submit agent positions (E05-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S05 — Debate escalation PO → USER, round and budget limits

**Status:** TODO
**Type:** feat
**Requirements:** §46, §50, §51, §10.2, §92, §137 (Inv. 5, 7), §138 (Infinite Debate — round limit, authority, escalation, budget)
**Depends on:** E05-S04, E05-S02
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A debate that does not reach consensus within `max_rounds` is arbitrated by a PRODUCT_OWNER `DEBATE` run and, when the PO cannot resolve it (or no PO is enabled), by the user through an `ApprovalRequest`; a debate whose budget is exhausted is abandoned and handed to the user — so every debate terminates in RESOLVED or ABANDONED with an authority-owned outcome (§138 Infinite Debate).

#### Scope
- In: PO arbitration turn scheduling (`ESCALATED_PO`), applying the PO run's output (`po_resolved` / `po_unresolved`), `ESCALATION_RAISED` for every debate escalation through `DecisionManager`, user resolution of a debate via the E05-S02 approval path, debate-budget exhaustion → `abandon` + Level-3 escalation, `ON_DEBATE_RESOLVED` → escalation resolved + work item unblocked.
- Out: PRODUCT_OWNER constitution content (E05-S06); CLI (`walk debates`, E05-S09); conflict detection (E05-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/debate/scheduling.py` | modify | `pending_arbitration_turn`, `ARBITRATION_KEY_SUFFIX` |
| `src/walk/debate/service.py` | modify | `DefaultDebateManager.po_unresolved`, `DefaultDebateManager.on_budget_exhausted` (escalations now go through `DecisionManager.escalate_from_debate`) |
| `src/walk/decisions/service.py` | modify | `DefaultDecisionManager.escalate_from_debate` |
| `src/walk/decisions/repository.py` | modify | `EscalationRepository.open_for_debate` |
| `src/walk/orchestrator/scheduler.py` | modify | — (`schedule_debate_turns` also schedules arbitration turns) |
| `src/walk/orchestrator/escalation.py` | modify | `EscalationRouter.on_approval_decided` (debate branch), `EscalationRouter.on_debate_resolved`, `register_debate_hooks` |
| `src/walk/runtime/output_applier.py` | modify | — (DEBATE branch for runs of PRODUCT_OWNER in `ESCALATED_PO`) |
| `src/walk/cli/composition.py` | modify | — (passes the `DebateManager` as `debates` to `EscalationRouter`; calls `register_debate_hooks`) |
| `tests/debate/test_scheduling.py` | modify | — |
| `tests/debate/test_service_escalation.py` | create | — |
| `tests/decisions/test_service_escalate_debate.py` | create | — |
| `tests/orchestrator/test_debate_arbitration.py` | create | — |
| `tests/runtime/test_applier_debate_po.py` | create | — |

#### Interface contract
`DebateManager` (INTERFACES §1.9), table rows `ESCALATED_PO --po_resolved/po_unresolved-->`, `ESCALATED_USER --user_resolved-->`, `abandon` (INTERFACES §3.5), `PermissionManager.request_approval` (INTERFACES §1.10). Deltas:
```python
# src/walk/debate/scheduling.py
ARBITRATION_KEY_SUFFIX = "po"
def pending_arbitration_turn(debate: Debate, running_roles: set[AgentRole]) -> DebateTurn | None:
    """Pure. A PRODUCT_OWNER turn (round = debate.round) when state == ESCALATED_PO, work_item_id set and PO not running."""
# idempotency key: f"debate:{debate_id}:{ARBITRATION_KEY_SUFFIX}"

# src/walk/decisions/service.py
class DefaultDecisionManager:
    async def escalate_from_debate(self, request: EscalationRequest, *, debate_id: DebateId,
                                   work_item_id: WorkItemId | None, route: bool) -> Escalation:
        """from_role=ORCHESTRATOR; row json `source_debate_id`; ledger ESCALATION_RAISED{to_level, category, question, debate_id};
        fires ON_ESCALATION; awaits the sink only when route is True."""

# src/walk/decisions/repository.py
class EscalationRepository:
    async def open_for_debate(self, debate_id: DebateId) -> list[Escalation]: ...   # json source_debate_id == id, unresolved

# src/walk/debate/service.py
class DefaultDebateManager:
    async def po_unresolved(self, debate_id: DebateId, reason: str) -> Debate: ...   # ESCALATED_PO -> ESCALATED_USER
    async def on_budget_exhausted(self, debate_id: DebateId) -> Debate: ...          # abandon + Level-3 escalation

# src/walk/orchestrator/escalation.py
class EscalationRouter:
    def __init__(self, ..., debates: DebateManager | None, ...) -> None: ...         # was DebateOpener (E05-S02)
    async def on_debate_resolved(self, ctx: HookContext) -> None: ...
def register_debate_hooks(hooks: HookManager, router: EscalationRouter, debates: DebateManager) -> None:
    """builtin.debate_resolved_unblock (ON_DEBATE_RESOLVED, prio 20, required) and
    builtin.debate_budget_abandon (ON_BUDGET_EXHAUSTED, prio 15, required; acts only when budget.scope_id starts with 'DEB-')."""
```
`EscalationRequest` built by the debate for both levels: `to_level`, `category=debate.category`, `question=f"{debate.id}: {debate.topic}"`, `options=[p.position for p in final_positions] + [p.alternative for p in final_positions if p.alternative]` (de-duplicated, order kept), `recommendation=leading_position(final_positions).position` or `None`, `evidence_ids=` union of final positions' evidence.

#### Behavior
1. Every transition into `ESCALATED_PO` calls `decisions.escalate_from_debate(request(to_level=PO), route=False)`; every transition into `ESCALATED_USER` calls it with `to_level=USER, route=True` (the E05-S02 router then creates `ApprovalRequest(kind="escalation", approver=USER)`). The E05-S03 direct `ON_ESCALATION` firing in `DefaultDebateManager` is removed (the hook is now fired once, by `DecisionManager`).
2. Scheduler: `schedule_debate_turns` also lists `ESCALATED_PO` debates and starts one PRODUCT_OWNER `DEBATE` run per debate via `pending_arbitration_turn` (key `debate:<id>:po`), routed with `route_debate` (PO is a valid arbiter even though not a participant — `route_debate` accepts `PRODUCT_OWNER` when state is `ESCALATED_PO`).
3. Applier, run.role == PRODUCT_OWNER and debate state `ESCALATED_PO`: the first `output.decisions` proposal with `category == debate.category` is the arbitration. Present and `status == COMPLETED` → `debates.resolve(debate_id, outcome=proposal.position, by=Actor(PRODUCT_OWNER, run.model_id, run.id), rationale=proposal.rationale)` (event `po_resolved`, payload `{"output_status": "COMPLETED", "has_decision": True}`); that proposal is **not** passed to `DecisionManager.propose`. Otherwise (`NEEDS_INPUT`, `BLOCKED`, no matching proposal) → `po_unresolved(debate_id, reason=output.result[:200])`. Other proposals/escalations in the output are applied normally. A PO run that ends `FAILED` after retries → `po_unresolved(reason="po run failed")`.
4. User resolution: `EscalationRouter.on_approval_decided` for an escalation whose json has `source_debate_id`: APPROVED → `debates.resolve(debate_id, outcome=approval.note or recommendation or options[0], by=Actor(role=USER), rationale=f"user approval {approval.id}")` (event `user_resolved`; decision owner USER, level USER); DENIED or EXPIRED → `debates.abandon(debate_id, reason="user denied")` with payload `by_user=True`; the escalation is resolved only on APPROVED.
5. `on_debate_resolved(ctx)` (hook `ON_DEBATE_RESOLVED`): for every `open_for_debate(debate_id)` escalation → `EscalationRepository.resolve(id, decision_id)`; then `on_resolved` semantics of E05-S02 (unblock the work item only when it is `BLOCKED`). Idempotent.
6. Budget: `builtin.debate_budget_abandon` on `ON_BUDGET_EXHAUSTED` with a budget whose `scope == TASK` and `scope_id` is a `DebateId` → `debates.on_budget_exhausted(debate_id)`: cancels running DEBATE runs of that debate (`AgentExecutor.cancel(run_id, "debate budget exhausted")`), `abandon(reason="budget_exhausted")` (guard payload `budget_ok=False`), then `escalate_from_debate(request(to_level=USER, question=f"{id} abandoned (budget exhausted): {topic}"), route=True)`. The user's approval of that escalation records a USER decision through the generic E05-S02 path (the debate stays ABANDONED; json `source_debate_id` is set but `on_approval_decided` skips `resolve` for ABANDONED debates and falls back to the E05-S02 decision path).
7. Round limit (§46 "2–3 rounds", default 3) is enforced by E05-S03 `close_round`; this story adds no second counter. A debate never returns from `ESCALATED_*` to `IN_ROUND`.
8. Every terminal path leaves exactly one of: an ACCEPTED decision with `debate_id` (RESOLVED) or an ABANDONED debate plus an open Level-3 escalation — never an orphaned non-terminal debate without a scheduled actor.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an ESCALATED_PO debate with work item When `pending_arbitration_turn` Then a PRODUCT_OWNER turn; PO already running Then `None` | `tests/debate/test_scheduling.py::test_arbitration_turn_for_escalated_po` |
| 2 | Given round 3 of 3 without consensus and PO enabled When `close_round` Then ESCALATED_PO, one `escalations` row `to_level=2` with json `source_debate_id`, `ESCALATION_RAISED` written once, `ON_ESCALATION` fired once, no approval request | `tests/debate/test_service_escalation.py::test_round_limit_registers_po_escalation_without_routing` |
| 3 | Given PO disabled Then ESCALATED_USER, escalation `to_level=3`, sink called once, approval `kind="escalation"` pending | `tests/debate/test_service_escalation.py::test_round_limit_without_po_routes_to_user` |
| 4 | Given `escalate_from_debate(route=False)` Then no sink call; `route=True` Then sink called after persist | `tests/decisions/test_service_escalate_debate.py::test_route_flag_controls_sink` |
| 5 | Given an ESCALATED_PO debate on STORY-0001 When `tick` Then exactly one PRODUCT_OWNER run with purpose `DEBATE`; second tick Then none | `tests/orchestrator/test_debate_arbitration.py::test_po_turn_scheduled_once` |
| 6 | Given the PO output COMPLETED with a DESIGN proposal "Keep double jump" for a DESIGN debate When applied Then debate RESOLVED, decision ACCEPTED owner PRODUCT_OWNER level PO `debate_id` set, no PROPOSED decision created from that proposal | `tests/runtime/test_applier_debate_po.py::test_po_arbitration_resolves_debate` |
| 7 | Given the PO output `NEEDS_INPUT` When applied Then ESCALATED_USER and a Level-3 approval pending | `tests/runtime/test_applier_debate_po.py::test_po_needs_input_escalates_to_user` |
| 8 | Given a PO proposal of another category Then treated as unresolved (ESCALATED_USER) | `tests/runtime/test_applier_debate_po.py::test_po_proposal_wrong_category_unresolved` |
| 9 | Given an ESCALATED_USER debate's approval APPROVED with note "Ship ECS" Then debate RESOLVED, decision owner USER outcome "Ship ECS", escalation `resolved_decision_id` set, BLOCKED story unblocked | `tests/orchestrator/test_debate_arbitration.py::test_user_approval_resolves_debate_and_unblocks` |
| 10 | Given the same approval DENIED Then debate ABANDONED, no decision, escalation unresolved, story still BLOCKED | `tests/orchestrator/test_debate_arbitration.py::test_user_denial_abandons_debate` |
| 11 | Given an IN_ROUND debate with one running DEBATE run When its `TASK:DEB-0001:COST_USD` budget is exhausted Then run cancelled, debate ABANDONED reason `budget_exhausted`, one Level-3 escalation with `source_debate_id`, approval pending | `tests/debate/test_service_escalation.py::test_budget_exhaustion_abandons_and_escalates_to_user` |
| 12 | Given `ON_BUDGET_EXHAUSTED` for budget `TASK:STORY-0001:COST_USD` Then the debate hook does nothing | `tests/orchestrator/test_debate_arbitration.py::test_budget_hook_ignores_non_debate_budgets` |
| 13 | Given `ON_DEBATE_RESOLVED` fired twice for the same debate Then the escalation is resolved once and one `unblock` transition exists | `tests/orchestrator/test_debate_arbitration.py::test_debate_resolved_hook_idempotent` |

#### Evidence required
- Quality gate output.
- Demo on the arbitration fixture: `walk ledger query --kind ESCALATION_RAISED --json` shows `to_level` 2 then 3 for `DEB-0001`; `walk approvals --pending --json` shows the `kind == "escalation"` request; `walk approve APV-0001 --note "Ship ECS"`; `walk decisions list --json` shows the ACCEPTED decision with `debate_id == "DEB-0001"` and `owner == "USER"`.

#### Notes
- ARCHITECTURE §5.5 (debate circuit breaker), §4.1 `ON_ESCALATION` ("any autonomy level ≥ 2 → ledger `ESCALATION_RAISED`"), §4.3 (`ESCALATION_RAISED` write point stays in `decisions.DecisionManager`); INTERFACES §4 row `DEBATE | ESCALATED_PO | PRODUCT_OWNER | DEBATE`.
- `NEW NAME:` `DefaultDecisionManager.escalate_from_debate`, escalation row json key `source_debate_id`, `EscalationRepository.open_for_debate`, `DefaultDebateManager.po_unresolved/on_budget_exhausted`, `pending_arbitration_turn`, `ARBITRATION_KEY_SUFFIX`, `EscalationRouter.on_debate_resolved`, `register_debate_hooks`, builtin hook ids `builtin.debate_resolved_unblock`, `builtin.debate_budget_abandon`.
- Import rule: `walk.debate` may not import `walk.permissions`, `walk.hooks` registration or `walk.orchestrator` (ARCHITECTURE §2.2), hence the USER approval is created by the E05-S02 router through the decisions sink and the hooks are registered from `walk.orchestrator.escalation`.
- E05-S02 typed the router's debate dependency as the structural `DebateOpener`; this story widens it to `walk.debate.protocols.DebateManager` (S03 is merged by now). `DebateOpener` stays exported for tests.
- Commit subject: `feat: escalate unresolved debates to po then user with budget stop (E05-S05)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S06 — PRODUCT_OWNER and DESIGN_LEADER constitutions and policies

**Status:** TODO
**Type:** feat
**Requirements:** §10.2, §10.4, §12, §6.7, §127 (optional roles), §51, §137 (Inv. 1, 7), §138 (Over-Engineering — PO challenge, design challenge)
**Depends on:** E05-X01, E03-S06
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The two optional early roles (§127) exist as complete ADR-0013 constitutions with their §10 professional bias and runtime policies, are switched on or off per project through `RuntimePolicy.enabled`, and every consumer of "enabled roles" (routing fallbacks, debate participant selection, `po_enabled`) reads the same source.

#### Scope
- In: `product_owner.md`, `design_leader.md` default constitutions (front matter + all D-3 body sections, arbitration guidance for PO); `policies.yaml` entries; `RuntimePolicy.enabled`; `DefaultAgentManager.list_roles/is_enabled`; composition wiring of `enabled_roles` / `po_enabled`.
- Out: constitution narrowing on `escalation_rules`, D-3 rendering checks and the strict lint over project overrides (E05-S07); ART_DIRECTOR (E08-S01), PROCESS_ARCHITECT (E10-S07), UA_RELEASE (E11-S01); SCRUM_MASTER and GAME_DIRECTOR are not shipped by any epic (§127 lists them neither as MVP nor optional early roles).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/defaults/product_owner.md` | create | — |
| `src/walk/agents/defaults/design_leader.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`roles.PRODUCT_OWNER`, `roles.DESIGN_LEADER`, `enabled` key on every role) |
| `src/walk/agents/models.py` | modify | `RuntimePolicy.enabled` |
| `src/walk/agents/policy_loader.py` | modify | — (`enabled` merged like other scalars) |
| `src/walk/agents/service.py` | modify | `DefaultAgentManager.list_roles`, `DefaultAgentManager.is_enabled` |
| `src/walk/permissions/defaults.yaml` | modify | — (only if the ADR-0006 D-6 PRODUCT_OWNER / DESIGN_LEADER row is absent; verify E02-S10) |
| `src/walk/cli/composition.py` | modify | — (`enabled_roles=agent_manager.list_roles`, `po_enabled=lambda: agent_manager.is_enabled(PRODUCT_OWNER)`) |
| `tests/agents/test_defaults.py` | modify | — |
| `tests/agents/test_optional_roles.py` | create | — |
| `tests/orchestrator/test_router.py` | modify | — |

#### Interface contract
Constitution format: ADR-0013 D-2/D-3. `AgentManager.list_roles` (INTERFACES §1.2). Deltas:
```python
# src/walk/agents/models.py
class RuntimePolicy(WalkModel):                       # DOMAIN-MODEL §4.2 fields +
    enabled: bool = Field(default=True, description="Optional roles (§127) are scheduled only when enabled for the project")

# src/walk/agents/service.py
class DefaultAgentManager:
    def list_roles(self) -> list[AgentRole]: ...       # roles with a default constitution AND load_runtime_policy(role).enabled
    def is_enabled(self, role: AgentRole) -> bool: ... # False for roles without a constitution
```
Front matter fixed by this story:

| Field | PRODUCT_OWNER | DESIGN_LEADER |
|---|---|---|
| `identity` | Product Owner | Design Leader |
| `mission` | Maximize product value under constraints. (§10.2) | Protect player experience and game-design integrity. (§10.4) |
| `responsibilities` | player value, scope, schedule, production cost, business value, product risk, debate arbitration | gameplay intention, mechanics, pacing, feedback, balance, progression, UX, feature depth, interaction between systems |
| `authority.decision_scope` | `[PRODUCT]` | `[DESIGN]` |
| `authority.max_autonomy_level` | 2 | 1 |
| `authority.may_approve` | `[]` | `[GAMEPLAY_CONCEPT, MECHANIC_SPEC, UX_FLOW]` |
| `authority.may_create_work` | `[FEATURE, STORY, TASK]` | `[TASK]` |
| `professional_bias` | Player and business value per unit of cost and schedule; challenges over-engineering with cost evidence. | Functional does not necessarily mean finished; experience quality over implementation convenience. |
| `risk_tolerance` | MEDIUM | MEDIUM |
| `preferred_evidence` | `[PLAYER_TELEMETRY, PLAYTEST, PROJECT_DATA]` | `[PLAYTEST, GAMEPLAY_RECORDING, SCREENSHOT]` |
| `escalation_rules` | monetization (3, PRODUCT); major feature removal (3); large scope increase (3); major schedule impact (3) | core gameplay change (3, DESIGN); cross-feature balance change (2, PRODUCT) |
| `tool_permissions` | ADR-0006 D-6 row: ALLOW read tools; DENY file write tools; REQUIRE_APPROVAL(USER) `monetization.change` | same row |
| `forbidden_actions` | "edit code or assets", "decide a Level-3 matter without the user", "override a user decision", "resolve a debate outside arbitration" | "edit code or assets", "approve own design", "decide technical architecture" |

`policies.yaml`: both roles `enabled: false`, `model_policy.preferred: [claude/opus]`, `fallback: [codex/default]` (ADR-0011 D-3), `execution_strategy: review_only`, `max_parallel_runs: 1`; every existing role gains `enabled: true`.

#### Behavior
1. Both files load through `ConstitutionLoader` with `version: "1.0"`, `type: constitution`, all ADR-0013 D-3 body sections in order and no provider name.
2. PRODUCT_OWNER `## Working Guidance` states the arbitration contract consumed by E05-S05: "When a debate is ESCALATED_PO, read every final position, choose one outcome, and return `status: COMPLETED` with exactly one `decisions` entry whose `category` equals the debate category, `position` is the chosen outcome and `rationale` names the product trade-off; return `NEEDS_INPUT` when the matter is Level 3 (§51) or the options lack the information to choose."
3. DESIGN_LEADER `## Working Guidance` states that as a debate participant it defends player experience, cites playtest/recording evidence where available and concedes on stronger evidence (§45).
4. `## Professional Bias` sections contain the §10.2 / §10.4 optimisation lists verbatim; PO's `## Conflict Behavior` contains "PO resolves trade-offs when specialized roles cannot reach consensus" (§10.2); LEAD_DEV's over-engineering clause (E03-S06) is unchanged.
5. `list_roles()` returns the four MVP roles by default (PO/DL disabled); a project `policies.yaml` with `roles: {PRODUCT_OWNER: {enabled: true}}` adds PRODUCT_OWNER; `is_enabled` mirrors `list_roles`.
6. Routing fallbacks of INTERFACES §4 use `list_roles()` (E03-S07): FEATURE/DISCOVERY routes to DESIGN_LEADER only when enabled; PHASE/REWORK to PRODUCT_OWNER only when enabled.
7. `PermissionManager.rules_for(role, extra=constitution.tool_permissions)` for both roles yields no rule wider than `permissions/defaults.yaml`.
8. Disabling a role never deletes its constitution; `AgentManager.load_constitution(PRODUCT_OWNER)` works while disabled (needed by `walk doctor` and E05-S07 lints).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the two new defaults When loaded Then valid, `version == "1.0"`, D-3 sections in order | `tests/agents/test_defaults.py::test_optional_constitutions_load_with_sections_in_order` |
| 2 | Then PO `decision_scope == [PRODUCT]`, `max_autonomy_level == PO`; DL `decision_scope == [DESIGN]`, `max_autonomy_level == MULTI_AGENT` | `tests/agents/test_defaults.py::test_optional_role_authorities` |
| 3 | Given the PO constitution Then `escalation_rules` contain the conditions "monetization", "major feature removal", "large scope increase", "major schedule impact", each `to_level == USER` | `tests/agents/test_optional_roles.py::test_po_escalation_rules_cover_level3_product_matters` |
| 4 | Given both constitutions When `rules_for(role, extra=…)` Then no widening versus defaults and `monetization.change` requires USER approval | `tests/agents/test_defaults.py::test_optional_role_permissions_do_not_widen` |
| 5 | Given PO body Then `Working Guidance` contains "exactly one `decisions` entry" and "NEEDS_INPUT"; `Professional Bias` contains the six §10.2 terms | `tests/agents/test_optional_roles.py::test_po_body_contains_arbitration_contract_and_bias` |
| 6 | Given DL body Then `Professional Bias` contains the nine §10.4 terms and "Functional does not necessarily mean finished" | `tests/agents/test_optional_roles.py::test_design_leader_body_contains_bias` |
| 7 | Given default policies When `list_roles()` Then exactly `[ORCHESTRATOR, LEAD_DEV, SENIOR_DEV, QC]`; with project `PRODUCT_OWNER.enabled: true` Then PO included and `is_enabled(PRODUCT_OWNER)` | `tests/agents/test_optional_roles.py::test_enabled_flag_controls_list_roles` |
| 8 | Given PO disabled When `load_constitution(PRODUCT_OWNER)` Then the constitution is returned | `tests/agents/test_optional_roles.py::test_disabled_role_constitution_still_loads` |
| 9 | Given DESIGN_LEADER enabled When `route(FEATURE, DISCOVERY)` Then DESIGN_LEADER/DESIGN; disabled Then ORCHESTRATOR/DESIGN | `tests/orchestrator/test_router.py::test_discovery_routes_to_design_leader_when_enabled` |
| 10 | Given both new files When scanned with `lint_constitutions_provider_names` Then zero findings | `tests/agents/test_defaults.py::test_optional_constitutions_have_no_provider_names` |

#### Evidence required
- Quality gate output.
- Demo: in a bootstrapped repo with `PRODUCT_OWNER: {enabled: true}` in `.ai/agents/policies.yaml`, `walk doctor --strict` reports `constitutions: ok (6 roles, no provider names)`; `walk status --json` lists no PO run until a debate escalates.

#### Notes
- ADR-0013 D-2/D-3/D-5/D-7, ADR-0006 D-6, ADR-0011 D-3, §127; epic planning decision "optional roles are enabled when `RuntimePolicy.enabled`".
- `NEW NAME:` `RuntimePolicy.enabled`, `DefaultAgentManager.is_enabled`, `policies.yaml` key `enabled`, PO/DL `escalation_rules` conditions "cross-feature balance change" (§51 does not list it; Level 2 by design leader judgement).
- Parallelism: WBS §8 `{S01→S02} ∥ {S06→S07}` — this story does not touch `DEBATE.md.j2` (E05-S04); the arbitration contract lives in the PO constitution body, which is rendered into the system prompt by `render_constitution` (E01-S18).
- Commit subject: `feat: add product owner and design leader constitutions (E05-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S07 — Constitution schema enforcement: narrowing merge, provider-name lint, section rendering

**Status:** TODO
**Type:** feat
**Requirements:** §12, §103, §104, §6.7, §137 (Inv. 1, 7, 13), §138 (Over-Engineering)
**Depends on:** E05-S06
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
ADR-0013 D-3–D-5 are enforced completely and from one place: every structured field of a project override is merged in an explicit, per-field direction (only ever narrowing authority and autonomy), the provider-name lint has a single pattern shared by the loader and `walk doctor --strict`, and rendered constitutions follow the D-3 section order including appended project sections.

#### Scope
- In: per-field narrowing table (incl. `escalation_rules` and the correct direction for `forbidden_actions`), widening errors naming the field and the §104 route, a single `PROVIDER_NAME_PATTERN` in `walk.agents.lint`, required-section lint, override-text lint for `.ai/agents/roles/*.md`, D-3 rendering order with appended sections, doctor strict output per role.
- Out: approving a widening through an improvement candidate (E10, ADR-0008); BoundaryAuditor protection of `.ai/agents/roles/` (E01-S25, ADR-0013 D-6); new role constitutions (E05-S06, E08-S01, E10-S07, E11-S01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/narrowing.py` | create | `NarrowingDirection`, `NARROWING_RULES`, `check_narrowing`, `merge_escalation_rules` |
| `src/walk/agents/lint.py` | create | `PROVIDER_NAME_PATTERN`, `REQUIRED_BODY_SECTIONS`, `provider_name_hits`, `missing_body_sections` |
| `src/walk/agents/constitution_loader.py` | modify | `ConstitutionLoader.load` (uses `check_narrowing`, lints raw override text) |
| `src/walk/agents/rendering.py` | modify | `render_constitution` (D-3 order, appended sections last) |
| `src/walk/agents/__init__.py` | modify | re-exports |
| `src/walk/cli/lints.py` | modify | `PROVIDER_NAME_PATTERN` (re-export from `walk.agents.lint`), `lint_constitutions_provider_names` (delegates), `lint_constitution_overrides` |
| `src/walk/cli/cmd_doctor.py` | modify | — (strict section: one line per role with a constitution, enabled or not) |
| `tests/agents/test_narrowing.py` | create | — |
| `tests/agents/test_lint.py` | create | — |
| `tests/agents/test_constitution_loader.py` | modify | — |
| `tests/agents/test_rendering.py` | modify | — |
| `tests/cli/test_lints.py` | modify | — |

#### Interface contract
ADR-0013 D-2 (fields), D-3 (body order), D-4 (merge), D-5 (lint); `Constitution` (DOMAIN-MODEL §4.2). Deltas:
```python
# src/walk/agents/narrowing.py
class NarrowingDirection(StrEnum):
    REPLACE = "REPLACE"            # free scalar/list: override replaces
    SUBSET = "SUBSET"              # override list must be a subset of default
    SUPERSET = "SUPERSET"          # override list must contain every default element
    NOT_HIGHER = "NOT_HIGHER"      # ordered value may only be lowered
    STRICTER_RULES = "STRICTER_RULES"  # PermissionRule list: see Behavior 3
    ESCALATION_RULES = "ESCALATION_RULES"  # see Behavior 4

NARROWING_RULES: dict[str, NarrowingDirection] = {
    "authority.decision_scope": SUBSET, "authority.max_autonomy_level": NOT_HIGHER, "authority.may_approve": SUBSET,
    "authority.may_reject": SUBSET, "authority.may_create_work": SUBSET, "tool_permissions": STRICTER_RULES,
    "forbidden_actions": SUPERSET, "escalation_rules": ESCALATION_RULES,
}   # every other front-matter field: REPLACE; `role`, `id`, `type` may not change at all

def check_narrowing(default: Constitution, override: JsonDict) -> list[str]:
    """Returns violations as '<field>: <reason>' (empty = ok). Pure."""
def merge_escalation_rules(default: list[EscalationRule], override: list[EscalationRule]) -> list[EscalationRule]: ...

# src/walk/agents/lint.py
PROVIDER_NAME_PATTERN: re.Pattern[str]      # r"(?i)\b(claude|codex|gpt|anthropic|openai|gemini|fake-codex|fake-claude)\b"
REQUIRED_BODY_SECTIONS: tuple[str, ...] = ("Identity", "Mission", "Responsibilities", "Authority", "Professional Bias",
    "Core Beliefs", "Decision Principles", "Risk Tolerance", "Preferred Evidence", "Conflict Behavior",
    "Escalation Rules", "Forbidden Actions")          # D-3; "Working Guidance" optional
def provider_name_hits(text: str) -> list[str]: ...   # sorted unique lower-cased matches
def missing_body_sections(constitution: Constitution) -> list[str]: ...

# src/walk/cli/lints.py
def lint_constitution_overrides(roles_dir: Path) -> list[str]: ...   # '<file>: <finding>' per raw-text hit / narrowing violation
```

#### Behavior
1. `ConstitutionLoader.load(role)` with a project override: parse; `check_narrowing(default, override_front_matter)`; any violation → `ConstitutionError("<field>: <reason>; widening requires a HIGH-risk improvement approval (§104)")` listing all violations; else merge per `NARROWING_RULES` (REPLACE fields replace, others take the override value which is already proven narrower).
2. `SUBSET`, `SUPERSET`, `NOT_HIGHER` compare enum values; `max_autonomy_level` compares `AutonomyLevel` ints. `forbidden_actions` is `SUPERSET` (an override may add forbidden actions, never remove one) — this corrects the E01-S17 "subset" wording.
3. `STRICTER_RULES` for `tool_permissions`: key = `(tool, command_pattern)`. For each override rule: if the key exists in the default, the effect may only move along `ALLOW → REQUIRE_APPROVAL → DENY` (and an approver may only change from an agent role to USER); a new key may only have effect `DENY` or `REQUIRE_APPROVAL`. Default rules omitted by the override are removed only when their effect is `ALLOW`; omitting a default `DENY`/`REQUIRE_APPROVAL` rule is a violation.
4. `ESCALATION_RULES`: every default rule's `(condition, category)` must be present in the override with `to_level >=` the default's; extra rules are allowed. `merge_escalation_rules` returns default order followed by new override rules.
5. `role`, `id` and `type` differing from the default → violation `"<field>: immutable"`.
6. Raw override text (front matter + body) with any `provider_name_hits` → `ConstitutionError` naming the matches (D-5); kernel defaults are checked by the same function.
7. Every kernel default constitution has no `missing_body_sections` (lint test over `src/walk/agents/defaults/*.md`); a project override may omit sections (defaults are kept).
8. `render_constitution` emits D-3 sections in `REQUIRED_BODY_SECTIONS` order, then `## Working Guidance`, then project-appended sections in the order they appear in the override; same input → byte-identical output.
9. `walk doctor --strict` constitutions block: one line per role with a constitution (`<ROLE>: ok` or the findings), using `lint_constitutions_provider_names` + `lint_constitution_overrides`; any finding → exit 1 (E02-S15 strict semantics). `PROVIDER_NAME_PATTERN` exists only in `walk.agents.lint`; `walk.cli.lints` re-exports it.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given LEAD_DEV default and override adding `DESIGN` to `decision_scope` and raising `max_autonomy_level` to 2 When `check_narrowing` Then two violations naming both fields | `tests/agents/test_narrowing.py::test_widening_authority_reported_per_field` |
| 2 | Given an override removing a default `forbidden_actions` entry Then violation; adding one Then ok | `tests/agents/test_narrowing.py::test_forbidden_actions_superset_only` |
| 3 | Given default `ALLOW review.approve` and override `DENY review.approve` Then ok; override `ALLOW git.merge_protected` (default REQUIRE_APPROVAL) Then violation; new key with `ALLOW` Then violation | `tests/agents/test_narrowing.py::test_tool_permissions_stricter_only` |
| 4 | Given an override omitting a default `DENY` rule Then violation; omitting a default `ALLOW` rule Then ok | `tests/agents/test_narrowing.py::test_omitting_default_rules` |
| 5 | Given an override lowering "core architecture migration" from 3 to 2 Then violation; raising "cross-team scope increase" to 3 and adding a new rule Then ok and merged order = defaults then new | `tests/agents/test_narrowing.py::test_escalation_rules_may_only_tighten` |
| 6 | Given an override changing `role` Then violation `role: immutable` | `tests/agents/test_narrowing.py::test_identity_fields_immutable` |
| 7 | Given `.ai/agents/roles/lead_dev.md` with a widening When `load(LEAD_DEV)` Then `ConstitutionError` mentioning `§104` and every violating field | `tests/agents/test_constitution_loader.py::test_widening_error_lists_all_fields_and_route` |
| 8 | Given override body text "prefer Codex for refactors" When loaded Then `ConstitutionError` naming `codex` | `tests/agents/test_constitution_loader.py::test_override_body_provider_name_rejected` |
| 9 | Given every kernel default constitution Then `missing_body_sections == []` and `provider_name_hits == []` | `tests/agents/test_lint.py::test_kernel_defaults_complete_and_model_independent` |
| 10 | Given text "Use GPT-5 or fake-claude" Then hits `["fake-claude", "gpt"]` | `tests/agents/test_lint.py::test_provider_name_hits_sorted_unique` |
| 11 | Given an override appending `## Studio Conventions` When rendered Then section order is D-3, `Working Guidance`, `Studio Conventions`; rendered twice byte-identical | `tests/agents/test_rendering.py::test_render_constitution_appended_sections_last` |
| 12 | Given a roles dir with one clean and one widening override When `lint_constitution_overrides` Then exactly one finding prefixed by the widening file name | `tests/cli/test_lints.py::test_lint_constitution_overrides_reports_widening` |
| 13 | Given `walk.cli.lints.PROVIDER_NAME_PATTERN` Then it is the same object as `walk.agents.lint.PROVIDER_NAME_PATTERN` | `tests/cli/test_lints.py::test_single_provider_name_pattern` |

#### Evidence required
- Quality gate output.
- Demo: in a bootstrapped repo add `.ai/agents/roles/lead_dev.md` with `authority: {decision_scope: [TECH, DESIGN]}`; `walk doctor --strict` exits 1 printing `LEAD_DEV: authority.decision_scope: widening ...`; remove `DESIGN` → `LEAD_DEV: ok`, exit 0.

#### Notes
- ADR-0013 D-3–D-5 complete; D-4 "widening requires a HIGH-risk improvement approval (§104)" is enforced here as a hard refusal — the approval path itself is E10.
- `NEW NAME:` `walk.agents.narrowing` (`NarrowingDirection`, `NARROWING_RULES`, `check_narrowing`, `merge_escalation_rules`), `walk.agents.lint` (`PROVIDER_NAME_PATTERN` relocated from `walk.cli.lints`, `REQUIRED_BODY_SECTIONS`, `provider_name_hits`, `missing_body_sections`), `lint_constitution_overrides`; pattern additionally matches `gemini`, `fake-codex`, `fake-claude`.
- Pitfall: E01-S17 Behavior 2 called `forbidden_actions` narrowing a "subset"; the correct direction is superset. Existing test `test_override_may_narrow` must keep passing — adjust its fixture only if it removed a forbidden action, and say so in the commit body.
- Commit subject: `feat: enforce constitution narrowing, lint and section order (E05-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S08 — Conflict detection → debate opening from review/design disagreement

**Status:** TODO
**Type:** feat
**Requirements:** §6.7, §10.1 (detect conflicts, initiate debates), §45, §46, §133, §137 (Inv. 5), §138 (Infinite Debate, Over-Engineering)
**Depends on:** E05-S04, E03-S13
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
When a non-debate run challenges the work it was given — a LEAD_DEV design or review that disagrees with a feature requirement, an implementer that disputes review findings — by returning a `debate_position`, the kernel detects the conflict, blocks the work item, opens a debate between the challenger and the category counterpart seeded with the challenger's round-1 position, and limits how many debates one item may spawn.

#### Scope
- In: pure conflict detection, category inference, seeding round 1, blocking the item with `blocked_reason`, dedup against an open debate, per-item debate limit with direct Level-3 escalation, output-contract instruction on how to challenge.
- Out: debate runs and round progression (E05-S04); PO/USER escalation and unblocking on resolution (E05-S05); CLI (E05-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/debate/conflicts.py` | create | `Conflict`, `CONFLICT_CATEGORY_BY_PURPOSE`, `detect_conflict` |
| `src/walk/debate/models.py` | modify | `DebatePolicy.max_debates_per_item` |
| `src/walk/debate/__init__.py` | modify | re-exports |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`debate.max_debates_per_item: 2`) |
| `src/walk/runtime/conflict_handler.py` | create | `ConflictHandler` |
| `src/walk/runtime/output_applier.py` | modify | — (`DefaultOutputApplier.apply` calls `ConflictHandler.handle` before raising the status-mapped workflow event) |
| `src/walk/agents/templates/_output_contract.md.j2` | modify | — (challenge instructions) |
| `src/walk/cli/composition.py` | modify | — (builds `ConflictHandler`) |
| `tests/debate/test_conflicts.py` | create | — |
| `tests/runtime/test_conflict_handler.py` | create | — |
| `tests/runtime/test_applier_conflict.py` | create | — |
| `tests/agents/test_output_contract_challenge.py` | create | — |

#### Interface contract
`AgentOutput.debate_position` (DOMAIN-MODEL §4.2), `DebateManager.open/submit_position/list` (INTERFACES §1.9), `select_participants` (E05-S02), `normalise_position` (E05-S04), `WorkflowManager.raise_event` (INTERFACES §1.3) with event `block` and payload keys `resume_state`, `blocked_reason` (WBS §3.4). Deltas:
```python
# src/walk/debate/conflicts.py
CONFLICT_CATEGORY_BY_PURPOSE: dict[str, DecisionCategory] = {
    "DESIGN": DecisionCategory.DESIGN, "PLAN": DecisionCategory.PRODUCT, "REVIEW": DecisionCategory.TECH,
    "IMPLEMENT": DecisionCategory.TECH, "QC": DecisionCategory.QUALITY, "TRIAGE": DecisionCategory.QUALITY,
}

class Conflict(FrozenModel):
    work_item_id: WorkItemId
    challenger: AgentRole
    category: DecisionCategory
    topic: str                       # f"{item.id} {item.title}: {position.position}" truncated to 200 chars
    position: DebatePosition         # the challenger's raw position

def detect_conflict(*, purpose: str, role: AgentRole, output: AgentOutput, item: WorkItem) -> Conflict | None:
    """Pure. None when purpose == 'DEBATE', output.debate_position is None, or output.status not in
    {REJECTED, BLOCKED, NEEDS_INPUT, COMPLETED}. Category = first output.decisions[].category if any, else
    CONFLICT_CATEGORY_BY_PURPOSE[purpose] (PROCESS for unknown purposes)."""

# src/walk/debate/models.py
class DebatePolicy(WalkModel):                 # E05-S03 fields +
    max_debates_per_item: int = Field(default=2, ge=1, le=10, description="§138 Infinite Debate: debates one work item may open")

# src/walk/runtime/conflict_handler.py
class ConflictHandler:
    def __init__(self, debates: DebateManager, decisions: DecisionManager, workflow: WorkflowManager,
                 enabled_roles: Callable[[], list[AgentRole]], policy: DebatePolicy) -> None: ...
    async def handle(self, run: AgentRun, item: WorkItem, conflict: Conflict) -> DebateId | None:
        """Returns the opened debate id, or None when deduplicated or escalated (Behavior 3-4)."""
```

#### Behavior
1. `DefaultOutputApplier.apply`: after evidence/decisions/escalations are applied and before the status-mapped workflow event, `detect_conflict(...)`; when a conflict is found `ConflictHandler.handle` runs and the status-mapped event is **not** raised (the item is blocked instead); `AppliedEffects.workflow_event == "block"`.
2. `handle` normal path: `participants = select_participants(challenger, category, enabled_roles())`; `debate = debates.open(topic, category, participants, opened_by=challenger, work_item_id=item.id)`; the challenger's position is normalised (`normalise_position`, round 1, `run_id=run.id`) and submitted, so only the counterpart has a pending round-1 turn; `workflow.raise_event(item.id, "block", TransitionContext(actor_role=ORCHESTRATOR, source=KERNEL, run_id=run.id, payload={"resume_state": item.state, "blocked_reason": f"debate {debate.id}"}))`.
3. Dedup: when `debates.list(states=<non-terminal>, work_item_id=item.id)` is non-empty, no debate opens; the position is attached to the run as `Finding(severity="WARNING", summary=f"conflict ignored: debate {id} already open")`; the status-mapped event is still suppressed and the item is blocked only if not already `BLOCKED`.
4. Limit (§138): when the item already has `>= policy.max_debates_per_item` debates (any state), no debate opens; instead `decisions.escalate(EscalationRequest(to_level=USER, category, question=topic, options=[position.position, position.alternative] minus empties, recommendation=position.position), from_role=challenger, work_item_id=item.id, run_id=run.id)` and the item is blocked with `blocked_reason=f"escalation {escalation.id}"`.
5. A `debate_position` returned by a run whose status is `APPROVED` or `FAILED` is ignored (no conflict; approvals cannot simultaneously disagree, failures are retried).
6. The `_output_contract.md.j2` partial gains a "Challenging your input" paragraph: to disagree with a requirement, design or finding, fill `debate_position` (position, reasoning, evidence, cost, risk, alternative, confidence) and return `REJECTED` (reviewers/designers) or `BLOCKED` (implementers); the kernel opens a structured debate and the work item waits for its decision; never silently implement around a disagreement (§45, Invariant 5).
7. The opened debate's `ON_DEBATE_OPENED` and `DEBATE_POSITION` events are the only ledger/hook effects of this story (write points unchanged); the `block` transition writes `WORK_ITEM_TRANSITION` through the state machine as usual.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a LEAD_DEV `DESIGN` output `REJECTED` with `debate_position` and no decisions When `detect_conflict` Then category `DESIGN`, challenger LEAD_DEV, topic starts with the feature id | `tests/debate/test_conflicts.py::test_design_rejection_with_position_is_conflict` |
| 2 | Given the same output with a TECH proposal Then category `TECH` | `tests/debate/test_conflicts.py::test_first_proposal_category_wins` |
| 3 | Given purpose `DEBATE`, or no `debate_position`, or status `APPROVED` Then `None` | `tests/debate/test_conflicts.py::test_non_conflicts` |
| 4 | Given DESIGN_LEADER enabled When `handle` for a LEAD_DEV DESIGN conflict on FEAT-0001 Then debate participants `[LEAD_DEV, DESIGN_LEADER]`, one round-1 position by LEAD_DEV, FEAT-0001 `BLOCKED` with `blocked_reason == "debate DEB-0001"` and `resume_state == DESIGN` | `tests/runtime/test_conflict_handler.py::test_conflict_opens_seeded_debate_and_blocks_item` |
| 5 | Given DESIGN_LEADER disabled Then participants `[LEAD_DEV, ORCHESTRATOR]` | `tests/runtime/test_conflict_handler.py::test_conflict_falls_back_to_orchestrator` |
| 6 | Given an IN_ROUND debate already open on FEAT-0001 When another conflict arrives Then no new debate, WARNING finding "already open" | `tests/runtime/test_conflict_handler.py::test_conflict_deduplicated_against_open_debate` |
| 7 | Given FEAT-0001 already has 2 debates (RESOLVED) When a third conflict arrives Then no debate, one Level-3 escalation, item BLOCKED with `blocked_reason` starting "escalation " | `tests/runtime/test_conflict_handler.py::test_debate_limit_escalates_to_user` |
| 8 | Given a fake LEAD_DEV DESIGN run returning `REJECTED` + `debate_position` When applied Then `AppliedEffects.workflow_event == "block"`, the status-mapped event not raised, `DEBATE_OPENED` and one `DEBATE_POSITION` in the ledger | `tests/runtime/test_applier_conflict.py::test_applier_routes_conflict_to_debate` |
| 9 | Given a SENIOR_DEV IMPLEMENT output `BLOCKED` with a `debate_position` disputing review findings Then a TECH debate `[SENIOR_DEV, LEAD_DEV]` opens | `tests/runtime/test_applier_conflict.py::test_implementer_disputes_review_findings` |
| 10 | Given every template rendered When searching the output-contract partial Then "debate_position" and "Challenging your input" are present | `tests/agents/test_output_contract_challenge.py::test_output_contract_explains_challenge` |
| 11 | Given `policies.yaml` `debate: {max_debates_per_item: 0}` When loaded Then `ConfigError` | `tests/debate/test_conflicts.py::test_max_debates_per_item_bounds` |

#### Evidence required
- Quality gate output.
- Demo on the §133 fixture: after the fake LEAD_DEV design run, `walk work show FEAT-0001 --json` shows `state == "BLOCKED"` and `blocked_reason == "debate DEB-0001"`; `walk ledger query --kind DEBATE_OPENED --json` shows participants `["LEAD_DEV", "DESIGN_LEADER"]`.

#### Notes
- §10.1 "detect conflicts; initiate debates" is realised kernel-side (the Orchestrator role stays neutral and never authors positions); ARCHITECTURE §3.2 step 6 order is preserved — the conflict check sits between "decisions/escalations" and "workflow event".
- `NEW NAME:` `walk.debate.conflicts` (`Conflict`, `CONFLICT_CATEGORY_BY_PURPOSE`, `detect_conflict`), `DebatePolicy.max_debates_per_item` + `policies.yaml` key, `walk.runtime.conflict_handler.ConflictHandler`, `blocked_reason` formats `debate <id>` / `escalation <id>`.
- Pitfall: the item may already be `BLOCKED` (e.g. a NEEDS_INPUT path raised it earlier in the same apply); `block` from `BLOCKED` is not a table transition — check the state first.
- Commit subject: `feat: open debates from agent disagreement with per-item limit (E05-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S09 — `walk debates list/show`, `walk decisions override`

**Status:** TODO
**Type:** feat
**Requirements:** §44, §45, §46, §87, §93 (override decisions), §137 (Inv. 5, 9)
**Depends on:** E05-S03, E05-S01
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** QC

#### Goal
The user can inspect debates (state, rounds, every position, resulting decision) from the CLI and override any accepted decision, with the override executed by the daemon when one runs and in-process otherwise.

#### Scope
- In: `walk debates list [--state S...] [--item ID] [--json]`, `walk debates show DEB_ID [--json]`, `walk decisions override DEC_ID --outcome TEXT --rationale TEXT`, `CommandConsumer` handler `decisions.override`, `KernelStatus.open_debates` population.
- Out: `walk debates abandon` (not in INTERFACES §6; user abandons by denying the Level-3 approval, E05-S05); decision list/show (E04-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/cli/cmd_debates.py` | create | `list_debates`, `show_debate` (typer commands `list`, `show`) |
| `src/walk/cli/cmd_decisions.py` | modify | `override_decision` (typer command `override`) |
| `src/walk/cli/app.py` | modify | — (registers `debates` group) |
| `src/walk/orchestrator/commands.py` | modify | — (`CommandConsumer` handles `decisions.override` → `DecisionManager.override`) |
| `src/walk/orchestrator/service.py` | modify | — (`DefaultOrchestrator.status().open_debates` = non-terminal debate ids) |
| `tests/cli/test_cmd_debates.py` | create | — |
| `tests/cli/test_cmd_decisions_override.py` | create | — |
| `tests/orchestrator/test_commands_override.py` | create | — |

#### Interface contract
CLI rows of INTERFACES §6 (`walk decisions … override ID --outcome TEXT --rationale TEXT`, `walk debates list / show ID`); exit codes per INTERFACES §6; `DecisionManager.override` (INTERFACES §1.9); `KernelStatus.open_debates` (INTERFACES §1.1). Output shapes:
```text
walk debates list            -> table: ID | STATE | ROUND/MAX | CATEGORY | ITEM | PARTICIPANTS | DECISION
walk debates list --json     -> [{"id","state","round","max_rounds","category","work_item_id","participants","decision_id","opened_at"}]
walk debates show DEB_ID     -> header (topic, state, opened_by, budget id) + per round: role, confidence, agrees_with, position,
                                reasoning, cost, risk, alternative, evidence ids + resulting decision id/outcome
walk debates show --json     -> {"debate": Debate, "positions": [DebatePosition...]}   (model_dump(mode="json"))
walk decisions override ...  -> "DEC-0001 OVERRIDDEN -> DEC-0002 ACCEPTED (owner USER)"; --json -> new Decision
```
Command row: `commands.name = "decisions.override"`, `args = {"decision_id", "outcome", "rationale"}`.

#### Behavior
1. `debates list/show` read SQLite directly (read-only connection), never through the daemon; `list` orders by `opened_at` descending; `--state` accepts `DebateState` values (invalid → exit 1).
2. `show` of an unknown id → exit 1 with `debate not found: <id>`.
3. `decisions override`: with the kernel lock held by a daemon → `CommandClient` (`decisions.override`), result printed from `command_results`; without a daemon → in-process `build_kernel(...)` + `DecisionManager.override`.
4. Errors from `override` map to exit codes: `PermanentError` (not ACCEPTED, unknown id) → 1; nothing is written.
5. The override's ledger event (`USER_OVERRIDE`) and documents are produced by E05-S01; the CLI adds nothing else to the ledger.
6. `status().open_debates` lists ids of debates in `OPEN, IN_ROUND, CONSENSUS_CHECK, ESCALATED_PO, ESCALATED_USER`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given two debates (one RESOLVED, one IN_ROUND) When `walk debates list --json` Then two rows ordered newest first with `decision_id` set only on the resolved one | `tests/cli/test_cmd_debates.py::test_list_debates_json` |
| 2 | Given `--state IN_ROUND` Then one row; `--state NOPE` Then exit 1 | `tests/cli/test_cmd_debates.py::test_list_debates_state_filter` |
| 3 | Given a resolved debate with two rounds When `walk debates show DEB-0001` Then output contains both rounds, every role's position and the decision id | `tests/cli/test_cmd_debates.py::test_show_debate_rounds_and_decision` |
| 4 | Given an unknown id When `show` Then exit 1 and message `debate not found` | `tests/cli/test_cmd_debates.py::test_show_unknown_debate_exit_1` |
| 5 | Given no daemon and ACCEPTED `DEC-0001` When `walk decisions override DEC-0001 --outcome X --rationale Y` Then exit 0, `DEC-0002` ACCEPTED owner USER, `DEC-0001` OVERRIDDEN | `tests/cli/test_cmd_decisions_override.py::test_override_in_process` |
| 6 | Given a PROPOSED decision When override Then exit 1, no new decision | `tests/cli/test_cmd_decisions_override.py::test_override_non_accepted_exit_1` |
| 7 | Given a `decisions.override` command row When consumed by `CommandConsumer` Then `DecisionManager.override` called once and `command_results` holds the new decision id | `tests/orchestrator/test_commands_override.py::test_consumer_executes_override` |
| 8 | Given an IN_ROUND and a RESOLVED debate When `status()` Then `open_debates == ["DEB-0002"]` | `tests/orchestrator/test_commands_override.py::test_status_lists_open_debates` |

#### Evidence required
- Quality gate output.
- Demo: `walk debates list`, `walk debates show DEB-0001`, `walk decisions override DEC-0001 --outcome "Use addressables" --rationale "load time"`, `walk decisions list --json` on the E05-S05 fixture DB.

#### Notes
- INTERFACES §6 marks `walk debates` `[MVP minimal]`; WBS §3.7 lists `cmd_debates.py`.
- `NEW NAME:` command name `decisions.override`; typer function names `list_debates`, `show_debate`, `override_decision`.
- Commit subject: `feat: add debates cli and decision override command (E05-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-S10 — Epic gate: §133 debate test (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §133, §44, §45, §46, §50, §51, §10.2, §6.7, §136 ("Debate → persisted decision"), §137 (Inv. 5, 7), §138 (Infinite Debate)
**Depends on:** E05-S05, E05-S07, E05-S08, E05-S09
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
The §133 chain "feature requirement → Lead Dev disagrees → counter-position → structured debate → decision → persisted decision" runs end-to-end with fake adapters producing scripted positions, including the PO arbitration path and the user path, and every artefact (SQLite rows, `.ai/decisions/DEC-NNNN.md`, feature-context link, ledger sequence) is asserted.

#### Scope
- In: `tests/e2e/test_e05_gate.py`, fixtures `e05_scenario` (PO enabled) and `e05_user_scenario` (PO disabled) in `tests/e2e/conftest.py`.
- Out: production code (defects become `E05-Bxx` bugfix stories).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e05_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | `e05_scenario`, `e05_user_scenario` fixtures |
| `tests/fakes/fake_model_adapter.py` | modify | — (script selection by `(role, purpose, debate round)` if not already supported by E05-S04 `debate_output`) |

#### Interface contract
Fixture `e05_scenario(bootstrapped_repo) -> E05Scenario` (`WalkModel` in conftest): `handle: KernelHandle`, `feature_id: FeatureId`, `debate_id: DebateId`, `decision_id: DecisionId`, `repo: Path`. Project config written before kernel start: `.ai/agents/policies.yaml` → `roles: {PRODUCT_OWNER: {enabled: true}, DESIGN_LEADER: {enabled: true}}`, `debate: {max_rounds: 2}`. Adapters: `FakeModelAdapter` instances `fake-claude/sim` and `fake-codex/sim` (WBS §3.6), `LocalWorkProvider`, real temp git repo. Scripts:

| Run (role / purpose / round) | Scripted output |
|---|---|
| ORCHESTRATOR / PLAN | `COMPLETED`, one STORY draft, context updates `Intent`, `Design Goal` |
| DESIGN_LEADER / DESIGN (DISCOVERY) | `COMPLETED`, design goal "unlimited double jump" |
| LEAD_DEV / DESIGN (1st) | `REJECTED`, `debate_position`: "Cap double jump at 2 per airtime", confidence 0.8, cost "2 days physics rework avoided", risk "tunnelling at high velocity" |
| DESIGN_LEADER / DEBATE / r1, r2 | own position "Unlimited double jump is the core fantasy", confidence 0.7, `agrees_with_role=None` |
| LEAD_DEV / DEBATE / r2 | holds "Cap double jump at 2 per airtime", `agrees_with_role=None` |
| PRODUCT_OWNER / DEBATE (ESCALATED_PO) | `COMPLETED`, one DESIGN proposal "Allow 3 jumps per airtime; revisit after playtest", rationale "player value vs physics cost" |
| LEAD_DEV / DESIGN (2nd, after unblock) | `COMPLETED`, `Architecture` section update |

`e05_user_scenario` is identical except PRODUCT_OWNER disabled; after `ESCALATED_USER` the test runs `walk approve <APV> --note "Cap at 2"`.

#### Behavior
Scenario steps (each a test, executed in order via the fixture's cached state; `walk run --once` ticks until quiescent, max 30 ticks):
1. `walk feature add "Double jump" --gdd GDD/movement.md#double-jump` creates FEAT-0001; ticks run PLAN and DISCOVERY design.
2. The first LEAD_DEV DESIGN run returns `REJECTED` + `debate_position`: FEAT-0001 is `BLOCKED` with `blocked_reason == "debate DEB-0001"`; `DEB-0001` participants `[LEAD_DEV, DESIGN_LEADER]`, category `DESIGN`.
3. Round 1: LEAD_DEV's seeded position plus one DESIGN_LEADER `DEBATE` run; agreement 0.5 < 0.75 → round 2; round 2: one run per participant; no consensus at `round == max_rounds == 2` → `ESCALATED_PO`.
4. One PRODUCT_OWNER `DEBATE` run resolves: `DEB-0001` `RESOLVED`, `decision_id == "DEC-0001"`.
5. `DEC-0001`: `status ACCEPTED`, `owner PRODUCT_OWNER`, `autonomy_level PO`, `debate_id DEB-0001`, `participants [LEAD_DEV, DESIGN_LEADER]`, 2 positions, `related_work_items [FEAT-0001]`; row in `decisions`; `.ai/decisions/DEC-0001.md` exists with `type: decision`, `status: ACCEPTED` and the nine E04-S05 sections; `.ai/features/FEAT-0001.md` section `Important Decisions` contains `DEC-0001`.
6. FEAT-0001 is unblocked back to `DESIGN`; the second LEAD_DEV DESIGN run's `AgentInput.decisions` contains `DEC-0001`; it completes.
7. Ledger order for `DEB-0001` (filtered by kind): `DEBATE_OPENED`, `DEBATE_POSITION` ×4, `ESCALATION_RAISED{to_level: 2}`, `DECISION_RECORDED`, `DEBATE_RESOLVED`; budget `TASK:DEB-0001:REVIEW_LOOPS` consumed 2.
8. Invariant 5: no `decisions` row is `ACCEPTED` other than `DEC-0001`; `debate_positions` rows are not referenced as decisions; every ACCEPTED decision has an owner that is PRODUCT_OWNER, USER, KERNEL-with-debate, or a role whose `decision_scope` contains the category.
9. User path (`e05_user_scenario`): after round 2 → `ESCALATED_USER`, `walk approvals --pending --json` lists one `kind == "escalation"` request; `walk approve APV-0001 --note "Cap at 2"` → debate `RESOLVED`, decision owner `USER`, outcome "Cap at 2", `autonomy_level USER`, FEAT-0001 unblocked.
10. `walk debates show DEB-0001` and `walk decisions show DEC-0001` exit 0 and contain both rounds / the outcome.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the feature in DESIGN When LEAD_DEV rejects with a position Then FEAT-0001 BLOCKED and DEB-0001 opened with `[LEAD_DEV, DESIGN_LEADER]` | `tests/e2e/test_e05_gate.py::test_lead_dev_challenge_opens_debate` |
| 2 | Given two rounds without consensus Then DEB-0001 reached ESCALATED_PO after exactly 4 positions | `tests/e2e/test_e05_gate.py::test_two_rounds_without_consensus_escalate_to_po` |
| 3 | Given the PO arbitration Then DEB-0001 RESOLVED and DEC-0001 ACCEPTED owner PRODUCT_OWNER level PO | `tests/e2e/test_e05_gate.py::test_po_resolves_and_decision_accepted` |
| 4 | Given DEC-0001 Then SQLite row and `.ai/decisions/DEC-0001.md` agree on status, outcome and sections | `tests/e2e/test_e05_gate.py::test_decision_persisted_in_sqlite_and_ai_folder` |
| 5 | Given FEAT-0001 context Then `Important Decisions` lists DEC-0001 | `tests/e2e/test_e05_gate.py::test_decision_linked_to_feature_context` |
| 6 | Given resolution Then FEAT-0001 back in DESIGN and the next LEAD_DEV run receives DEC-0001 and completes | `tests/e2e/test_e05_gate.py::test_feature_unblocked_and_decision_in_context` |
| 7 | Given the ledger Then the DEB-0001 event sequence and REVIEW_LOOPS consumption match | `tests/e2e/test_e05_gate.py::test_ledger_sequence_and_round_budget` |
| 8 | Given all decisions Then only DEC-0001 is ACCEPTED and every ACCEPTED owner is an authority | `tests/e2e/test_e05_gate.py::test_opinion_is_not_decision_invariant` |
| 9 | Given PO disabled When the user approves the escalation with a note Then decision owner USER outcome "Cap at 2" and the feature unblocked | `tests/e2e/test_e05_gate.py::test_user_resolves_when_no_po` |
| 10 | Given the completed scenario When `walk debates show` / `walk decisions show` Then exit 0 with rounds and outcome | `tests/e2e/test_e05_gate.py::test_cli_shows_debate_and_decision` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e05_gate.py` (10 passed).
- Demo transcript on the fixture repo: `walk debates list`, `walk debates show DEB-0001`, `walk decisions show DEC-0001`, `cat .ai/decisions/DEC-0001.md | head -30`, `walk ledger query --kind DEBATE_OPENED --kind DEBATE_POSITION --kind ESCALATION_RAISED --kind DEBATE_RESOLVED --json`.

#### Notes
- WBS §9 maps §136 "Debate → persisted decision" to this story; WBS §4 E05 gate text ("two rounds without consensus escalate to PO") is realised with project `debate.max_rounds: 2`, proving the round limit is configurable (§46).
- Gate uses only fakes and a temp repo; no network. Any production change is a separate `bugfix` story; this commit touches tests only.
- Commit subject: `feat: add epic 05 gate test for structured debate (E05-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E05-R01 — Review E05

**Status:** TODO
**Type:** docs
**Requirements:** §137 (Inv. 5, 7), §23, §44–§46, §51, §138 (Infinite Debate)
**Depends on:** E05-S10
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the E05 implementer where possible, §23) verifies every E05 story against the Definition of Done and Invariants 5 and 7, recording defects as `bugfix` stories.

#### Scope
- In: stories E05-S01…S10 and their commits; `INTERFACES.md` / `DOMAIN-MODEL.md` / ADR-0010 / ADR-0013 deltas; WBS §6 register entries introduced by E05.
- Out: fixing defects (each becomes `E05-Bxx`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-05-multi-agent-reasoning.md` | modify | — (review record appended; `E05-Bxx` stories appended if any) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows, §6 register) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/DOMAIN-MODEL.md`, `docs/01-architecture/adr/ADR-0013-agent-constitution-schema.md` | modify (only if drift found) | — |
| `tests/architecture/test_decision_acceptance_paths.py` | create | — |
| `tests/architecture/test_debate_tables_as_data.py` | create | — |

#### Interface contract
Reviewer protocol, IMPLEMENTATION-PROTOCOL.md "Reviewer protocol" steps 1–5.

#### Behavior
1. For each story: `git show <sha>`; Files table == changed files (extra files need commit-body justification); every acceptance-criterion test exists and passes; coverage ≥ 90 % for touched modules.
2. Invariant 5 (Opinion ≠ Decision): the only code that sets `DecisionStatus.ACCEPTED` is `DefaultDecisionManager.record`; `DebatePosition` and `AgentOutput.decisions` never reach the `decisions` table as ACCEPTED without passing `record`.
3. Invariant 7 (bounded autonomy): every `Decision` and `Escalation` row carries an `autonomy_level`/`to_level`; `classify` consults `project_autonomy_max` on every call; every Level-3 escalation has an `ApprovalRequest(approver=USER)` (query over the E05 gate DB).
4. §46/§138: `debate_workflow.yaml` is loaded data (no state literal comparisons for debate transitions outside `walk/debate/state_machine.py`); `max_rounds` default 3 and configurable; every debate in the gate DB is terminal or has a scheduled actor.
5. Import table (ARCHITECTURE §2.2): `walk.debate` imports none of `permissions`, `agents`, `runtime`, `orchestrator`; `walk.decisions` does not import `walk.debate`; `import-linter` green. The `HookManager` constructor dependency of `DefaultDecisionManager` (E04-S05) and `DefaultDebateManager` (E05-S03) is checked against the import-linter contract as configured in E01-S01; a violation is a defect against those stories.
6. ADR-0013: all six shipped constitutions pass `missing_body_sections` and `provider_name_hits`; narrowing table covers every ADR-0013 D-4 field.
7. Debate id prefix: code and docs use `DEB-` (DOMAIN-MODEL §2); any remaining `DBT` reference is a defect.
8. `NEW NAME:` items of E05 are present in WBS §6 or listed in the review note for the architect.
9. Defects → `E05-Bxx` stories using the template; commit `docs: review epic 05 stories E05-S01..S10 (E05-R01)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each E05 story When the DoD checklist is applied Then every box is checked or an `E05-Bxx` story exists | manual checklist recorded in Evidence |
| 2 | Given `src/walk` When searching assignments of `DecisionStatus.ACCEPTED` Then they occur only in `walk/decisions/service.py` inside `record` | `tests/architecture/test_decision_acceptance_paths.py::test_accepted_status_set_only_by_record` |
| 3 | Given `src/walk/debate` When parsed for comparisons against `DebateState` members outside `state_machine.py` and `scheduling.py` Then none drive transitions | `tests/architecture/test_debate_tables_as_data.py::test_debate_transitions_only_from_table` |
| 4 | Given the E05 gate DB When querying Level-3 escalations Then each has a non-null `approval_request_id` | manual checklist recorded in Evidence |
| 5 | Given the quality gate on `main` Then green with overall coverage ≥ 85 % | manual checklist recorded in Evidence |

#### Evidence required
- Checklist per story (ID → DoD items → OK/defect id).
- Quality gate output on `main` after the review commit.
- List of `E05-Bxx` stories created (or "none") and NEW NAME items forwarded to the architect.

#### Notes
- Tests 2–3 are architecture tests created by the reviewer (review tasks may add tests, never production code).
- Commit subject: `docs: review epic 05 stories E05-S01..S10 (E05-R01)`.

#### Evidence (filled by implementer)
_pending_
