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
**Requirements:** §135 (Stage 5), §58 (Definition of Ready applied to stories)
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
5. Specifically verify (these were planned from WBS §3 and architecture docs because `EPIC-01` S18–S31 and `EPIC-03` S06–S20 story bodies were not yet written at planning time): `src/walk/debate/models.py` + `__init__.py` exist (created by E01-S18 for `AgentInput.debate`); `src/walk/agents/templates/DEBATE.md.j2` exists (E01-S18); `src/walk/orchestrator/{service,scheduler,router,commands}.py` module names (E01-S29/S30); `src/walk/runtime/applier.py` (E01-S27); the E01-S11 generic state-machine constructor signature used for `DebateState`.

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
| `src/walk/runtime/applier.py` | modify | — (`DefaultOutputApplier` calls `propose` per `output.decisions`, `escalate` per `output.escalations`; fills `AppliedEffects.decision_ids/escalation_ids`) |
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
1. `open(topic, category, participants, *, opened_by, work_item_id, max_rounds=None)`: validates `len(set(participants)) >= 2` (`DebateStateError` otherwise, except Behavior 3); allocates `DBT-NNNN` (`IdFactory`, prefix `DBT`, width 4); `max_rounds = max_rounds if not None else policy.max_rounds`; `consensus_threshold = policy.consensus_threshold`; `BudgetManager.ensure(BudgetScope.TASK, debate.id, BudgetPolicy(per_task={REVIEW_LOOPS: max_rounds or 1, COST_USD: policy.cost_usd}))` → `budget_id`; persists OPEN; raises `start_round` → IN_ROUND, `round = 1`; in the same transaction ledger `DEBATE_OPENED{topic, category, participants, work_item_id, max_rounds}`; after commit fires `ON_DEBATE_OPENED` with payload `{"debate_id", "work_item_id", "participants"}`. Returns the IN_ROUND debate.
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
| 6 | When `open("ECS or MonoBehaviour", TECH, [LEAD_DEV, SENIOR_DEV], opened_by=SENIOR_DEV, work_item_id=STORY-0001)` Then `DBT-0001` IN_ROUND round 1, budget `TASK:DBT-0001:REVIEW_LOOPS` limit 3, `DEBATE_OPENED` written, `ON_DEBATE_OPENED` fired once | `tests/debate/test_service_lifecycle.py::test_open_starts_round_one_with_budget` |
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
| 17 | Given a `Decision(debate_id="DBT-0001")` When `record(by=Actor(KERNEL))` Then ACCEPTED; `by=Actor(LEAD_DEV)` Then `AuthorityViolation`; no `debate_id` and `by=Actor(KERNEL)` Then `AuthorityViolation` | `tests/decisions/test_service_record_debate.py::test_record_debate_path_actors` |
| 18 | Given repository round trips for `Debate` and `DebatePosition` Then equal after reload; `for_round` returns only that round | `tests/debate/test_repository.py::test_repository_roundtrip_and_round_filter` |
| 19 | Given project `policies.yaml` with `debate: {max_rounds: 2}` When `load_debate_policy` Then `max_rounds == 2`, other fields default; `max_rounds: 99` Then `ConfigError` | `tests/agents/test_policy_loader.py::test_debate_policy_merge_and_bounds` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --kind DEBATE_OPENED --kind DEBATE_POSITION --kind DEBATE_RESOLVED --json` after the lifecycle test fixture DB shows the three kinds for `DBT-0001`; `sqlite3 .ai/kernel.db "select id,state,round from debates"`.

#### Notes
- ADR-0010 D-3/D-4; INTERFACES §1.9, §3.5; DOMAIN-MODEL §4.8, §6.2 (`debates`, `debate_positions`); ARCHITECTURE §5.5 (`max_rounds` default 3). Epic planning decisions: debate budgets at `BudgetScope.TASK` with `scope_id = <DebateId>`; guards registered through `walk.workflow.guards.register_guard`; table under `src/walk/workflow/tables/`.
- `NEW NAME:` `DebatePosition.agrees_with_role` (WBS §6 attributes it to E05-S04 — the field is added here so `close_round` is testable; E05-S04 produces it from agent output), `DebatePolicy` + `policies.yaml` `debate:` block + `PolicyLoader.load_debate_policy`, `walk.debate.{consensus,guards,state_machine}`, errors `DebateStateError`/`NotParticipant`/`DuplicatePosition`, id prefix `DBT` (DOMAIN-MODEL §2 has no `DebateId` row), extra table rows `OPEN --escalate--> ESCALATED_PO|ESCALATED_USER` with guard `arbitration_only`, `DefaultDebateManager.get/list/positions_for`.
- Parallelism: this story and E05-S02 both modify `src/walk/cli/composition.py`; merge S02 first (WBS §8 set `{S01→S02} ∥ {S03→S04→S05}` holds for all other files).
- Pitfall: `resolve` must call `record` inside the debate transaction's `UnitOfWork` only if `DecisionManager.record` accepts an outer unit of work; otherwise record first, then commit the debate state — never leave a RESOLVED debate without `decision_id`.
- Commit subject: `feat: add debate manager with lifecycle table and consensus (E05-S03)`.

#### Evidence (filled by implementer)
_pending_

---
