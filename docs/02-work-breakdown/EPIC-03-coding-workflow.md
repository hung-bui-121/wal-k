# EPIC-03 — Coding Workflow

**Roadmap stage:** §135 Stage 3 · **Status:** TODO · **Predecessor:** E02 (gate `E02-S16` DONE, `E02-R01` without BLOCKER bugfix stories)

## Goal
The §131 MVP feature lifecycle runs end-to-end on a real git repository with `LocalWorkProvider` (and `JiraWorkProvider` behind the same contract): plan → technical design → implementation → Lead Dev review → CI → QC → fix loop → feature complete, including the §132 failover.

## Requirements covered
§6.4, §6.5, §6.6, §10.1, §10.6, §10.7, §10.8, §23, §55, §56, §59, §60, §61, §62, §63, §64, §65, §129, §131, §132, §137 (Invariants 3, 4, 6), §138 (Infinite Fix Loop).

## Epic gate
`tests/e2e/test_e03_gate.py` (§131 with fakes) **and** `tests/e2e/test_e03_failover.py` (§132): a feature added via `walk feature add` is planned into two stories by the fake ORCHESTRATOR, designed by fake LEAD_DEV, implemented by fake `fake-codex`, reviewed by fake `fake-claude` (different model enforced), integrated (squash → push to local bare remote → local PR stub → `FakeUnityProvider` CI green), QC rejects once creating a BUG, bug is triaged/fixed/verified, QC passes, feature `COMPLETE` with done dimensions set. Failover: `fake-codex` run is interrupted after checkpoint 2 (kernel stopped), kernel restarts, `fake-claude` run has `handover_in_id`, same branch HEAD, finishes the story.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E03-S01 | `GitCliProvider` remote operations: push, PR, merge, `squash_wip` | E01-S23, E02-S14 | HIGH |
| E03-S02 | `LocalWorkProvider` and work-provider contract test suite | E01-S23, E01-S04 | HIGH |
| E03-S03 | `IntegrationManager`: ingest, reconcile, idempotency, `WorkPoller` | E03-S02, E01-S09 | HIGH |
| E03-S04 | `JiraWorkProvider` | E03-S02, E02-S01 | HIGH |
| E03-S05 | Jira webhooks: `WebhookReceiver`, `walk run --webhook-port`, bootstrap status validation | E03-S04, E03-S03, E01-S30 | HIGH |
| E03-S06 | Full MVP constitutions and task templates | E01-S17, E01-S18 | HIGH |
| E03-S07 | `TaskRouter` full table, `can_run_parallel`, cross-model review enforcement | E01-S29, E03-S06 | MEDIUM |
| E03-S08 | `OutputApplier` full: new tasks/bugs → work provider, change reconciliation, kernel commit | E01-S27, E03-S02, E03-S01 | HIGH |
| E03-S09 | Feature PLAN and DESIGN flow, `walk feature add` | E03-S08, E03-S07, E01-S16 | HIGH |
| E03-S10 | `UnityBatchProvider` and `com.walk.ci` editor package | E01-S23, E02-S02 | HIGH |
| E03-S11 | `LocalCiProvider.run_pipeline`, build/test hooks and evidence | E03-S10, E01-S06 | MEDIUM |
| E03-S12 | Story integration step: squash, push, PR, CI | E03-S11, E03-S01, E01-S29 | HIGH |
| E03-S13 | Lead Dev review flow | E03-S07, E03-S08 | MEDIUM |
| E03-S14 | QC flow and bug creation | E03-S08, E03-S07, E03-S11 | HIGH |
| E03-S15 | Bug loop: triage, fix, review, re-test, reopen | E03-S14 | HIGH |
| E03-S16 | Fix-loop circuit breaker and `walk work force-review` | E03-S15, E02-S11 | MEDIUM |
| E03-S17 | Feature completion and done dimensions | E03-S14, E03-S12 | MEDIUM |
| E03-S18 | Scheduler ordering and parallel worktrees | E03-S07, E01-S29 | MEDIUM |
| E03-S19 | Epic gate part 1: §131 MVP workflow e2e with fakes | E03-S09, E03-S12, E03-S13, E03-S16, E03-S17, E03-S18, E03-S03 | HIGH |
| E03-S20 | Epic gate part 2: §132 failover e2e (fake Codex → fake Claude) | E03-S19, E01-S28 | MEDIUM |
| E03-R01 | Review E03 (incl. ADR-0006 Codex residual-risk re-evaluation) | E03-S20 | MEDIUM |

## Reading order for implementers
1. `WBS.md` §2, §3 (esp. §3.4 payload keys, §3.5 ledger-vs-hooks rule, §3.6 fakes).
2. `INTERFACES.md` §2.2 `WorkProvider`, §2.3 `GitProvider`, §2.4 `UnityProvider`/`CiProvider`, §3.1–§3.3 state tables, §4 routing table, §5.1 scheduler.
3. ADR-0005 (work provider), ADR-0006 (permission boundary, D-2 kernel-executed side effects), ADR-0009 D-6 (Unity batchmode), ADR-0010 (unified state enum), ADR-0013 (constitutions).
4. `ARCHITECTURE.md` §3.2 (agent execution), §3.3 (work-provider flow), §4.1 (hook table), §4.3 (ledger write points), §5.4 (idempotency keys).
5. The story itself, then the §NN it cites.

Branch model used from E03-S09 on (all kinds): feature integration branch `feat/<FEAT-id>-<slug>` from `Project.default_branch`; story/task branch `story/<STORY-id>-<slug>` or `task/<TASK-id>-<slug>` from the parent feature branch; bug branch `bug/<BUG-id>-<slug>` from the related feature branch (or `default_branch` when `related_feature_id` is None). `NEW NAME:` per-kind branch prefixes (INTERFACES §1.13 only names `feat/<id>-<slug>`).

---

### E03-S01 — `GitCliProvider` remote operations: push, PR, merge, `squash_wip`

**Status:** TODO
**Type:** feat
**Requirements:** §59, §60, §90, §91, §137 (Invariant 9)
**Depends on:** E01-S23, E02-S14
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`GitCliProvider` implements the remaining `GitProvider` methods (`push`, `open_pr`, `merge`, `squash_wip`) so the kernel can take a story branch from WIP commits to a reviewed, CI-checked pull request against a local or remote repository, with protected-branch refusal and ledger traceability.

#### Scope
- In: `push`, `open_pr`, `merge`, `squash_wip`; `COMMIT`/`PR_OPENED`/`MERGED` ledger write point; `ON_COMMIT`/`ON_PR_OPENED`/`ON_MERGED` hook firing; idempotency keys `git.pr:*`, `git.merge:*`; `gh` detection; local PR stub.
- Out: `git.merge_protected` approval decision (E02-S11 + `ToolInvoker`, consumed in E03-S12/S17); provider comment on commit (E03-S08 registers `ON_COMMIT → WorkProvider.comment`); relevant-files refresh on PR/merge (E04-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/git/provider.py` | modify | `GitCliProvider.push`, `GitCliProvider.open_pr`, `GitCliProvider.merge`, `GitCliProvider.squash_wip`, `GitCliProvider.detect_gh` |
| `src/walk/integrations/git/pr_stub.py` | create | `LocalPrStub`, `write_pr_stub`, `read_pr_stub` |
| `src/walk/integrations/errors.py` | modify | `ProtectedBranchRefused(PermissionDenied)` |
| `tests/conftest.py` | modify | fixture `tmp_game_repo_with_remote` |
| `tests/integrations/git/test_provider_remote.py` | create | — |
| `tests/integrations/git/test_pr_stub.py` | create | — |

#### Interface contract
See `INTERFACES.md` §2.3 `GitProvider` (`push`, `open_pr`, `merge`, `squash_wip` signatures unchanged). Additions:

```python
class LocalPrStub(FrozenModel):
    """Local stand-in for a hosted PR when `gh` is absent (dev / tests). Stored at <repo>/.walk/prs/<branch>.json."""
    branch: str
    base: str
    head: Sha
    title: str
    body: str
    created_at: datetime
    merged_sha: Sha | None = None

class GitCliProvider:
    async def detect_gh(self) -> bool: ...   # `gh --version` exit 0 and `gh auth status` exit 0, cached per instance
```

`ProtectedBranchRefused(PermissionDenied)` carries `branch: str` and `pattern: str`.

#### Behavior
1. `push(path, branch, *, protected_branches)`: if `branch` matches any glob in `protected_branches` (`fnmatch`), raise `ProtectedBranchRefused` before touching the remote. Otherwise `git push --set-upstream origin <branch>`; a second call with no new commits is a no-op (remote ref equals local HEAD → no subprocess push).
2. `push` when no `origin` remote exists: succeed without network (log `extra={"remote": None}`) — supports repo-only dev mode.
3. `open_pr(branch, base, title, body, *, idempotency_key)`: wrapped in `IntegrationManager.with_idempotency`; when `detect_gh()` is true run `gh pr create --head <branch> --base <base> --title … --body …` and parse the URL/number; else write `LocalPrStub` to `.walk/prs/<branch>.json` and return `PullRequestRef(number=None, url="file://<abs path>", head=<branch HEAD>, base=base)`. Ledger `PR_OPENED` (payload: branch, base, head, url); fire `ON_PR_OPENED`.
4. `open_pr` called twice with the same key returns the stored `PullRequestRef` without a second `gh`/stub write.
5. `merge(pr, *, strategy, idempotency_key)`: creates a temporary worktree on `pr.base`, runs `git merge --squash <pr.head>` + commit (strategy `squash`) or `git merge --no-ff <pr.head>` (strategy `merge`), pushes `pr.base` if `origin` exists, removes the temp worktree, updates the stub's `merged_sha` when stub-backed; returns the merge commit sha. Ledger `MERGED`; fire `ON_MERGED`. Idempotent by key.
6. `merge` never checks protection itself: the caller (`ToolInvoker` for tool `git.merge_protected`) decides. `merge` into a protected base **without** an approved `ApprovalRequest` is prevented by the guard hooks installed by E02-S14 (`pre-push`), which this story's tests confirm by expecting `ProtectedBranchRefused` from `push` in the merge path when the base is protected and `origin` exists.
7. `squash_wip(path, branch, base, message)`: all commits on `branch` after `base` (`git rev-list base..branch`) are collapsed into one commit via `git reset --soft <base>` + `git commit -m <message>` keeping the `Walk-Work-Item` trailer of the last squashed commit; returns the new sha. When `base..branch` is empty → returns current HEAD unchanged. When the branch has non-`wip(` commits they are squashed too (rule: integration always produces one commit per story).
8. `squash_wip` on a dirty worktree raises `GuardRejected("worktree dirty")`.
9. Every subprocess failure maps to `ToolCrashed` (`TransientError`) with the stderr tail in the message; nothing is swallowed.
10. `COMMIT` ledger event (already written by `commit_all` in E01-S23) and the new `PR_OPENED`/`MERGED` events are the only ledger writes in this package (ARCHITECTURE §4.3).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a story branch with 3 commits and a bare `origin` When `push` Then `origin/<branch>` equals local HEAD and a second `push` spawns no `git push` | `tests/integrations/git/test_provider_remote.py::test_push_sets_upstream_and_is_idempotent` |
| 2 | Given `protected_branches=["main","release/*"]` When `push(branch="release/1.0")` Then `ProtectedBranchRefused` and no subprocess runs | `tests/integrations/git/test_provider_remote.py::test_push_protected_branch_refused` |
| 3 | Given no `origin` remote When `push` Then it returns without error and logs `remote=None` | `tests/integrations/git/test_provider_remote.py::test_push_without_remote_is_noop` |
| 4 | Given `gh` absent When `open_pr` Then `.walk/prs/<branch>.json` exists, `PullRequestRef.number is None`, `url` starts with `file://`, ledger has `PR_OPENED`, `ON_PR_OPENED` fired once | `tests/integrations/git/test_provider_remote.py::test_open_pr_writes_local_stub_and_ledger` |
| 5 | Given a fake runner reporting `gh` present When `open_pr` Then `gh pr create` is invoked with head/base/title/body and the returned URL is parsed | `tests/integrations/git/test_provider_remote.py::test_open_pr_uses_gh_when_available` |
| 6 | Given `open_pr` already executed for key K When `open_pr` with K again Then the same `PullRequestRef` is returned and no stub rewrite | `tests/integrations/git/test_provider_remote.py::test_open_pr_idempotent_by_key` |
| 7 | Given a stub PR When `merge(strategy="squash")` Then base has exactly one new commit, stub `merged_sha` set, ledger `MERGED`, `ON_MERGED` fired | `tests/integrations/git/test_provider_remote.py::test_merge_squash_into_base` |
| 8 | Given a stub PR When `merge(strategy="merge")` Then base HEAD is a merge commit with two parents | `tests/integrations/git/test_provider_remote.py::test_merge_no_ff_into_base` |
| 9 | Given 3 `wip(...)` commits after base When `squash_wip` Then one commit after base, message as given, trailer `Walk-Work-Item` preserved, tree identical | `tests/integrations/git/test_provider_remote.py::test_squash_wip_collapses_commits` |
| 10 | Given branch equals base When `squash_wip` Then HEAD unchanged | `tests/integrations/git/test_provider_remote.py::test_squash_wip_nothing_to_squash` |
| 11 | Given a dirty worktree When `squash_wip` Then `GuardRejected` | `tests/integrations/git/test_provider_remote.py::test_squash_wip_dirty_worktree_rejected` |
| 12 | Given `git` exits non-zero When any remote op Then `ToolCrashed` with stderr tail | `tests/integrations/git/test_provider_remote.py::test_subprocess_failure_maps_to_tool_crashed` |
| 13 | Given a stub file When `read_pr_stub` Then round-trips `LocalPrStub` | `tests/integrations/git/test_pr_stub.py::test_stub_roundtrip` |

#### Evidence required
- Quality gate output.
- Demo (temp repo with bare remote): `walk ledger query --kind PR_OPENED --kind MERGED --json` after running `tests/integrations/git/test_provider_remote.py` against `--repo <tmp>` shows both events with `payload.branch`.

#### Notes
- ADR-0002 D-4 (WIP commits squashed before PR), ADR-0005 (no hosted-PR dependency in tests), ADR-0006 D-1 (guard hooks defence in depth).
- `NEW NAME:` `LocalPrStub` and path `.walk/prs/<branch>.json`; `ProtectedBranchRefused`; `GitCliProvider.detect_gh`.
- Pitfall: `git merge --squash` leaves staged changes without committing; commit explicitly with the kernel actor's message.
- Commit subject: `feat: add git remote operations and pr stub (E03-S01)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S02 — `LocalWorkProvider` and work-provider contract test suite

**Status:** TODO
**Type:** feat
**Requirements:** §55, §90, §129, §137 (Invariant 3)
**Depends on:** E01-S23, E01-S04
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A file-and-SQLite-backed `LocalWorkProvider` implements the full `WorkProvider` protocol and a reusable contract test suite guarantees behavioural parity for every provider implementation (ADR-0005 D-7).

#### Scope
- In: migration `0002_local_work_provider.sql`; `LocalWorkProvider` (all methods); `.walk/work/<external_ref>.md` mirror; `WorkProviderContract` scenario class; local test subclass.
- Out: `JiraWorkProvider` (E03-S04); ingest/reconcile (E03-S03); provider calls from `OutputApplier` (E03-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/persistence/migrations/project/0002_local_work_provider.sql` | create | — |
| `src/walk/integrations/local_work.py` | create | `LocalWorkProvider`, `LOCAL_STATUS_MAP` |
| `src/walk/integrations/__init__.py` | modify | re-export `LocalWorkProvider` |
| `tests/integrations/work_provider_contract.py` | create | `WorkProviderContract` |
| `tests/integrations/test_local_work_provider.py` | create | — |

#### Interface contract
See `INTERFACES.md` §2.2 `WorkProvider`. Implementation:

```python
class LocalWorkProvider:
    provider: str = "local"
    def __init__(self, db: Database, repo_path: Path, clock: Clock, uow_factory: Callable[[], UnitOfWork]) -> None: ...
    # all WorkProvider methods; parse_webhook raises NotSupported
    def status_map(self) -> dict[WorkItemState, str]: ...   # LOCAL_STATUS_MAP: identity names, e.g. IMPLEMENTING -> "IMPLEMENTING"

class WorkProviderContract:
    """Subclass per provider; override `make_provider()`; scenarios are async test methods prefixed `test_`."""
    async def make_provider(self) -> WorkProvider: ...
```

Migration `0002_local_work_items`: `external_ref TEXT PRIMARY KEY, work_item_id TEXT NOT NULL, status TEXT NOT NULL, assignee_role TEXT, labels_json TEXT NOT NULL, json TEXT NOT NULL, updated_at TEXT NOT NULL`; `local_work_comments(id INTEGER PK AUTOINCREMENT, external_ref, marker TEXT, markdown, at)`; `local_work_links(from_ref, to_ref, kind, PRIMARY KEY(from_ref,to_ref,kind))`; index on `updated_at`.

#### Behavior
1. `create(item, *, idempotency_key)`: if a row with label `walk:<item.id>` exists → return its ref (reconciliation); else allocate `LOCAL-<n>` from `id_sequences(prefix="LOCAL")`, insert row with labels `["walk:<id>", "walk-role:<owner_role>"]` + `item.labels`, write mirror file, return `WorkItemRef(external_ref, url=file://…)`. Idempotency by key is handled by `IntegrationManager.with_idempotency` (E03-S03); the provider's own label check makes a duplicate create safe even without it.
2. `update` rewrites title/description/priority/labels/parent in `json` + mirror; unknown field names raise `ConfigError`.
3. `transition(item, to_state)`: no-op (no row update, no `updated_at` bump) when `status == status_map()[to_state]`; else update status + `updated_at`.
4. `assign(item, role)`: replaces any `walk-role:*` label with `walk-role:<role>` and sets `assignee_role`.
5. `comment(item, markdown)`: the markdown is stored with a marker `<!-- walk:<ledger_seq> -->` extracted from the text when present; a second comment with the same marker is not stored.
6. `link(from, to, kind)`: upsert into `local_work_links`; `PARENT` also sets `parent_ref` in `from`'s json.
7. `get(external_ref)` returns the row json; unknown ref → `ConfigError`.
8. `query(states, kinds, limit)` returns rows ordered by `updated_at` desc then `external_ref`.
9. `changes_since(since)` returns `WorkProviderEvent(kind="UPDATED"|"TRANSITIONED", external_status=status, delivery_id=f"local:{external_ref}:{updated_at}")` for rows with `updated_at > since` (all rows when `since is None`), ordered by `updated_at` asc.
10. `parse_webhook` raises `NotSupported`.
11. Mirror file `.walk/work/<external_ref>.md`: YAML front matter (`external_ref, work_item_id, status, assignee_role, labels, updated_at`) + body = description + `## Comments` list. Written atomically via `walk.persistence.atomic_write` (E01-S04).
12. `health()` → `ComponentStatus(state=READY)` when `.walk/work/` is writable, else `MISCONFIGURED`.
13. Contract scenarios (methods of `WorkProviderContract`): `test_create_twice_same_item_returns_same_ref`, `test_create_reconciles_by_label`, `test_transition_noop_when_status_equal`, `test_transition_changes_status`, `test_comment_dedup_by_marker`, `test_changes_since_orders_ascending`, `test_link_kinds_roundtrip`, `test_assign_sets_role_label`, `test_update_rejects_unknown_field`, `test_get_unknown_ref_raises`, `test_status_map_covers_all_states`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a STORY When `create` twice Then one row, same `external_ref` | `tests/integrations/test_local_work_provider.py::test_create_twice_same_item_returns_same_ref` |
| 2 | Given a row labelled `walk:STORY-0001` inserted directly When `create(STORY-0001)` Then no new row | `tests/integrations/test_local_work_provider.py::test_create_reconciles_by_label` |
| 3 | Given status `IMPLEMENTING` When `transition(IMPLEMENTING)` Then `updated_at` unchanged | `tests/integrations/test_local_work_provider.py::test_transition_noop_when_status_equal` |
| 4 | Given status `READY` When `transition(IMPLEMENTING)` Then status + mirror updated | `tests/integrations/test_local_work_provider.py::test_transition_changes_status` |
| 5 | Given comment with marker `<!-- walk:7 -->` stored When same comment again Then one comment row | `tests/integrations/test_local_work_provider.py::test_comment_dedup_by_marker` |
| 6 | Given three rows updated at t1<t2<t3 When `changes_since(t1)` Then two events ascending | `tests/integrations/test_local_work_provider.py::test_changes_since_orders_ascending` |
| 7 | Given two items When `link(BLOCKS)`, `link(PARENT)` Then both present in `get()` | `tests/integrations/test_local_work_provider.py::test_link_kinds_roundtrip` |
| 8 | Given item When `assign(QC)` Then exactly one `walk-role:QC` label | `tests/integrations/test_local_work_provider.py::test_assign_sets_role_label` |
| 9 | Given item When `update(fields={"bogus": 1})` Then `ConfigError` | `tests/integrations/test_local_work_provider.py::test_update_rejects_unknown_field` |
| 10 | Given no row When `get("LOCAL-99")` Then `ConfigError` | `tests/integrations/test_local_work_provider.py::test_get_unknown_ref_raises` |
| 11 | Given provider When `status_map()` Then keys == all `WorkItemState` members | `tests/integrations/test_local_work_provider.py::test_status_map_covers_all_states` |
| 12 | Given provider When `parse_webhook` Then `NotSupported` | `tests/integrations/test_local_work_provider.py::test_parse_webhook_not_supported` |
| 13 | Given fresh DB When migration 0002 applied Then tables `local_work_items`, `local_work_comments`, `local_work_links` exist and `schema_migrations` has version 2 | `tests/integrations/test_local_work_provider.py::test_migration_0002_creates_tables` |
| 14 | Given `create` When mirror read Then front matter fields match row | `tests/integrations/test_local_work_provider.py::test_mirror_file_written_atomically` |

#### Evidence required
- Quality gate output.
- Demo: `walk db migrate` prints `applied 0002_local_work_provider`; after a `create` via test, `cat .walk/work/LOCAL-1.md` shows front matter.

#### Notes
- ADR-0005 D-2, D-6, D-7. `LOCAL_STATUS_MAP` values are the enum names so `apply_external_transition` (E03-S03) can invert it trivially.
- `tests/integrations/work_provider_contract.py` is not collected directly (no `test_` prefix in filename); subclasses are.
- Commit subject: `feat: add local work provider and contract suite (E03-S02)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S03 — `IntegrationManager`: ingest, reconcile, idempotency, `WorkPoller`

**Status:** TODO
**Type:** feat
**Requirements:** §55, §56, §89, §90, §137 (Invariant 3)
**Depends on:** E03-S02, E01-S09
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Inbound work-provider changes (webhook or poll) are deduplicated, mapped to kernel transitions through `WorkflowManager.apply_external_transition`, rejected changes are synced back, and every external write is wrapped in a persisted idempotency key.

#### Scope
- In: `DefaultIntegrationManager.ingest/reconcile/with_idempotency`; `WorkPoller`; `webhook_deliveries` + `work_provider_sync` usage; `DefaultWorkflowManager.apply_external_transition`; `external_events.yaml`; `Scheduler.wake` on ingest.
- Out: HTTP receiver (E03-S05); Jira provider (E03-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/service.py` | modify | `DefaultIntegrationManager.ingest`, `.reconcile`, `.with_idempotency` |
| `src/walk/integrations/poller.py` | create | `WorkPoller` |
| `src/walk/integrations/repository.py` | modify | `WebhookDeliveryRepository`, `WorkProviderSyncRepository` |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.apply_external_transition` |
| `src/walk/workflow/tables/external_events.yaml` | create | — |
| `src/walk/workflow/external.py` | create | `ExternalEventMap`, `load_external_event_map` |
| `tests/integrations/test_service_ingest.py` | create | — |
| `tests/integrations/test_poller.py` | create | — |
| `tests/workflow/test_external.py` | create | — |

#### Interface contract
See `INTERFACES.md` §1.12 `IntegrationManager` (`ingest`, `reconcile`, `with_idempotency`) and §1.3 `WorkflowManager.apply_external_transition`. Additions:

```python
class WorkPoller:
    def __init__(self, integrations: IntegrationManager, sync_repo: WorkProviderSyncRepository, clock: Clock, poll_interval_s: int = 60) -> None: ...
    async def start(self) -> None: ...          # creates the asyncio task; first iteration = startup reconcile since last_sync_at
    async def stop(self) -> None: ...
    async def poll_once(self) -> int: ...       # returns ingested count

class ExternalEventMap(FrozenModel):
    """(from_state, to_state) -> event name, loaded from workflow/tables/external_events.yaml per WorkItemKind."""
    version: str
    entries: dict[WorkItemKind, dict[tuple[WorkItemState, WorkItemState], str]]
    def event_for(self, kind: WorkItemKind, from_state: WorkItemState, to_state: WorkItemState) -> str | None: ...
```

`external_events.yaml` shape: `version: "1.0"`, `story: [{from: READY, to: IMPLEMENTING, event: start_implementation}, …]`, `feature: […]`, `bug: […]` covering every (from,to) pair in INTERFACES §3.1–§3.3 whose `Who` includes a human/agent role (KERNEL-only transitions are not externally triggerable and are absent on purpose).

#### Behavior
1. `ingest(event)`: if `event.delivery_id` exists in `webhook_deliveries` → return (no transition, counter `ingest.duplicate`). Else insert the delivery row, then: look up work item by `external_ref` (index `ix_work_items_external`); unknown ref → log + counter `ingest.unknown_ref`, return. For `kind in {TRANSITIONED, UPDATED}` with `external_status` → `WorkflowManager.apply_external_transition`. For `UPDATED` with `fields.priority` → update `WorkItem.priority` (Jira is authoritative for priority, ADR-0005 D-5). `COMMENTED`/`CREATED`/`DELETED` → counter only. Finally `Orchestrator.wake()`.
2. `apply_external_transition(external_ref, external_status, event)`: invert `work.status_map()` (status name → state; unknown status → `ConfigError`); if state equals current → return `None`; find `event_for(kind, current, target)`; `None` → rejection path. Otherwise `raise_event(item.id, ev, TransitionContext(actor_role=KERNEL, source=EXTERNAL, payload={"external": event.model_dump()}))`.
3. Rejection path (no event or `GuardRejected`/`PermissionDenied` from `raise_event`): insert a `work_item_transitions` row `from=current,to=current,event="external_rejected",source=EXTERNAL_REJECTED,reason=<why>`; call `work.transition(item, current, idempotency_key=f"work.transition:{item.id}:{seq}")` to resync the provider; `work.comment(item, "kernel rejected: <reason>", idempotency_key=f"work.comment:{item.id}:{ledger_seq}")`; return the rejection row. Ledger `WORK_ITEM_TRANSITION` with `outcome="DENIED"` written by `StateMachine` write point.
4. `reconcile(since)`: `events = work.changes_since(since)`; ingest each; set `work_provider_sync.last_sync_at = max(event.at)` (or `now` when empty); return count.
5. `with_idempotency(key, operation, fn)`: `SELECT result_ref FROM idempotency_keys WHERE key=?` → return if present; else `result = await fn()`, insert `(key, operation, result, now)` **in the caller's current `UnitOfWork`** (the manager receives the active UoW via `contextvar` set by `UnitoOfWork.__aenter__`, E01-S04); when no UoW is active it opens its own.
6. `with_idempotency` when `fn` raises: nothing is stored; the exception propagates.
7. `WorkPoller.start`: first `poll_once()` immediately with `since=last_sync_at` (startup reconcile, ARCHITECTURE §5.3 step 7), then every `poll_interval_s` using the kernel `Clock`/`asyncio.sleep`; exceptions from `poll_once` are logged and the loop continues (`TransientError` → counter `poller.transient`, others → counter `poller.error`).
8. `WorkPoller.stop` cancels the task and awaits it.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a delivery id already stored When `ingest` Then no transition and no provider call | `tests/integrations/test_service_ingest.py::test_ingest_duplicate_delivery_ignored` |
| 2 | Given STORY `READY` and event status `IMPLEMENTING` When `ingest` Then item `IMPLEMENTING`, transition row `source=EXTERNAL`, `wake()` called once | `tests/integrations/test_service_ingest.py::test_ingest_applies_external_transition` |
| 3 | Given STORY `IMPLEMENTING` and event status `COMPLETE` When `ingest` Then item unchanged, row `external_rejected`, provider `transition(IMPLEMENTING)` and comment "kernel rejected" called | `tests/integrations/test_service_ingest.py::test_ingest_rejected_transition_resyncs_provider` |
| 4 | Given unknown `external_ref` When `ingest` Then returns, counter `ingest.unknown_ref` incremented, no error | `tests/integrations/test_service_ingest.py::test_ingest_unknown_ref_counted` |
| 5 | Given event with `fields.priority="P0"` When `ingest` Then `WorkItem.priority == P0` | `tests/integrations/test_service_ingest.py::test_ingest_updates_priority_from_provider` |
| 6 | Given status equal to current When `apply_external_transition` Then returns `None` and no row | `tests/workflow/test_external.py::test_external_same_state_returns_none` |
| 7 | Given unknown status name When `apply_external_transition` Then `ConfigError` | `tests/workflow/test_external.py::test_external_unknown_status_config_error` |
| 8 | Given `external_events.yaml` When loaded Then every entry's (from,to,event) exists in the corresponding transition table and no KERNEL-only transition is present | `tests/workflow/test_external.py::test_external_event_map_consistent_with_tables` |
| 9 | Given provider with 2 changed rows When `reconcile(since)` Then 2 ingested and `last_sync_at` == latest event time | `tests/integrations/test_service_ingest.py::test_reconcile_updates_sync_marker` |
| 10 | Given key present When `with_idempotency` Then `fn` not called, stored result returned | `tests/integrations/test_service_ingest.py::test_with_idempotency_replays_result` |
| 11 | Given `fn` raises When `with_idempotency` Then no key stored and exception propagates | `tests/integrations/test_service_ingest.py::test_with_idempotency_failure_not_recorded` |
| 12 | Given active `UnitOfWork` rolled back When `with_idempotency` ran inside it Then key absent | `tests/integrations/test_service_ingest.py::test_with_idempotency_joins_caller_transaction` |
| 13 | Given poller started with `FakeClock` When started Then `poll_once` runs immediately with `since=last_sync_at`, then after `poll_interval_s` | `tests/integrations/test_poller.py::test_poller_startup_reconcile_then_interval` |
| 14 | Given `poll_once` raising `ProviderUnavailable` When loop iterates Then loop continues and counter `poller.transient` incremented | `tests/integrations/test_poller.py::test_poller_survives_transient_error` |

#### Evidence required
- Quality gate output.
- Demo: with `walk run --once --poll-interval 1` on a repo whose `.walk/work/LOCAL-1.md` status was edited by hand to `IMPLEMENTING` via the provider API test helper, `walk work show STORY-0001` lists a transition with `source=EXTERNAL`.

#### Notes
- ARCHITECTURE §3.3, ADR-0005 D-4/D-5/D-6, ADR-0002 D-7.
- `NEW NAME:` `external_events.yaml`, `ExternalEventMap`, `load_external_event_map`, `WebhookDeliveryRepository`, `WorkProviderSyncRepository`, `WorkPoller.poll_once`.
- Pitfall: do not call `WorkProvider.transition` for the accepted path here — `ON_STATE_TRANSITION` (E03-S08) does it and the provider's "no-op when equal" rule makes it safe.
- Commit subject: `feat: add work provider ingest, reconcile and poller (E03-S03)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S04 — `JiraWorkProvider`

**Status:** TODO
**Type:** feat
**Requirements:** §55, §90, §91, §129, §137 (Invariant 3)
**Depends on:** E03-S02, E02-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Jira Cloud becomes a drop-in `WorkProvider` with the ADR-0005 D-3 mapping, label-based reconciliation, hidden comment markers, and credentials from `CredentialStore`; it passes the same contract suite as `LocalWorkProvider` when a tenant is configured.

#### Scope
- In: `JiraClient` (httpx), `JiraWorkProvider` (all methods except `parse_webhook`, E03-S05), `work-provider.yaml` schema + loader, transition-id cache, retry/backoff mapping, recorded-transport unit tests, opt-in parity run.
- Out: webhooks (E03-S05); bootstrap status validation (E03-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/jira/__init__.py` | create | `JiraWorkProvider`, `JiraClient`, `JiraMapping` |
| `src/walk/integrations/jira/client.py` | create | `JiraClient` |
| `src/walk/integrations/jira/mapping.py` | create | `JiraMapping`, `DEFAULT_STATUS_MAP`, `load_work_provider_config` |
| `src/walk/integrations/jira/provider.py` | create | `JiraWorkProvider` |
| `src/walk/integrations/models.py` | modify | `WorkProviderConfig` |
| `tests/integrations/jira/test_client.py` | create | — |
| `tests/integrations/jira/test_mapping.py` | create | — |
| `tests/integrations/jira/test_jira_work_provider.py` | create | — |
| `tests/integrations/jira/test_jira_contract.py` | create | — (`@pytest.mark.integration`) |
| `tests/integrations/jira/fixtures/*.json` | create | recorded responses |

#### Interface contract
See `INTERFACES.md` §2.2 `WorkProvider`.

```python
class WorkProviderConfig(WalkModel):
    """`.ai/project/work-provider.yaml`."""
    provider: Literal["local", "jira"] = "local"
    jira_project_key: str | None = None
    issue_types: dict[WorkItemKind, str] = Field(default_factory=lambda: {EPIC: "Epic", FEATURE: "Story", STORY: "Sub-task", TASK: "Sub-task", BUG: "Bug"})
    status_map: dict[WorkItemState, str] = Field(default_factory=lambda: dict(DEFAULT_STATUS_MAP))
    assignee_accounts: dict[AgentRole, str] = Field(default_factory=dict)
    kernel_id_field: str | None = Field(default=None, description="Custom field id; None = label walk:<ID>")
    priority_map: dict[Priority, str] = Field(default_factory=lambda: {P0: "Highest", P1: "High", P2: "Medium", P3: "Low"})

class JiraClient:
    def __init__(self, base_url: str, email: str, token: SecretStr, transport: httpx.AsyncBaseTransport | None = None, clock: Clock | None = None) -> None: ...
    async def get(self, path: str, **params: object) -> JsonDict: ...
    async def post(self, path: str, body: JsonDict) -> JsonDict: ...
    async def put(self, path: str, body: JsonDict) -> JsonDict: ...
    async def search(self, jql: str, fields: list[str], max_results: int = 200) -> list[JsonDict]: ...

class JiraWorkProvider:
    provider: str = "jira"
    def __init__(self, client: JiraClient, mapping: JiraMapping, clock: Clock) -> None: ...
    @classmethod
    def from_credentials(cls, store: CredentialStore, config: WorkProviderConfig, clock: Clock) -> "JiraWorkProvider": ...
```

#### Behavior
1. `from_credentials` reads `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` via `CredentialStore.get`; any absent → `ConfigError` naming the missing credential (never its value).
2. `JiraClient` retries on HTTP 429 and 5xx with backoff 1 s, 2 s, 4 s (max 3 attempts, `Retry-After` honoured); after exhaustion raises `RateLimited` (429) or `ProviderUnavailable` (5xx). 401/403 → `PermissionDenied`; 404 → `ConfigError`; other 4xx → `PermanentError` with the Jira `errorMessages` joined.
3. `create`: JQL `project = <KEY> AND labels = "walk:<id>"`; hit → return its key. Else `POST /rest/api/3/issue` with issue type per `issue_types[kind]`, labels `walk:<id>`, `walk-feature`/`walk-bug` per kind, `walk-role:<owner_role>`, parent per ADR-0005 D-3 (Epic parent for Feature, Feature parent for Story/Task sub-tasks, "relates to" link for Bug → Feature), priority via `priority_map`, fixVersion = `<PHASE-id> <name>` when `item.phase_id` set (created if missing).
4. `transition(item, to_state)`: GET current status; equal to `status_map[to_state]` → no-op. Else resolve transition id via `GET /issue/{key}/transitions` cached per `(issue type, from status, to status)`; missing → `ConfigError("no transition from X to Y")`; `POST` transition.
5. `assign`: `assignee_accounts[role]` when configured → set assignee; always replace `walk-role:*` label.
6. `comment`: marker `<!-- walk:<seq> -->` kept in the ADF body as a text node; before posting, page through existing comments for the marker; present → no-op.
7. `link`: `BLOCKS` → issue link type "Blocks"; `RELATES` → "Relates"; `PARENT` → `PUT` `fields.parent`.
8. `changes_since(since)`: JQL `project = <KEY> AND labels = walk AND updated >= "<since - 2m>"` (all `walk:*` issues when `since is None`), each → `WorkProviderEvent(kind=TRANSITIONED, external_status=fields.status.name, delivery_id=f"jira:{key}:{updated}")`.
9. `status_map()` returns `config.status_map`; `query` uses JQL with status/kind filters.
10. `health()`: `GET /rest/api/3/myself` → `READY` with `version=<accountId masked>`; auth failure → `MISCONFIGURED`.
11. `parse_webhook` raises `NotSupported` until E03-S05.
12. No request/response body is ever logged at INFO or above; DEBUG logs redact `Authorization`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given store lacking `JIRA_API_TOKEN` When `from_credentials` Then `ConfigError` mentions `JIRA_API_TOKEN` and not any value | `tests/integrations/jira/test_jira_work_provider.py::test_missing_credential_config_error` |
| 2 | Given transport returning 429 then 200 When `get` Then one retry and success | `tests/integrations/jira/test_client.py::test_retry_on_429_then_success` |
| 3 | Given transport returning 503 ×3 When `get` Then `ProviderUnavailable` | `tests/integrations/jira/test_client.py::test_5xx_exhausted_maps_provider_unavailable` |
| 4 | Given 401 When `get` Then `PermissionDenied` | `tests/integrations/jira/test_client.py::test_401_maps_permission_denied` |
| 5 | Given search returns an issue labelled `walk:STORY-0001` When `create(STORY-0001)` Then no POST issued and its key returned | `tests/integrations/jira/test_jira_work_provider.py::test_create_reconciles_by_label` |
| 6 | Given FEATURE with parent EPIC When `create` Then POST body has issuetype Story, labels incl. `walk-feature`, parent key | `tests/integrations/jira/test_jira_work_provider.py::test_create_feature_mapping` |
| 7 | Given BUG with `related_feature_id` When `create` Then issue link "Relates" created to the feature key | `tests/integrations/jira/test_jira_work_provider.py::test_create_bug_links_feature` |
| 8 | Given issue status "In Progress" When `transition(IMPLEMENTING)` Then no transitions request | `tests/integrations/jira/test_jira_work_provider.py::test_transition_noop_when_equal` |
| 9 | Given transitions list lacking target When `transition` Then `ConfigError` | `tests/integrations/jira/test_jira_work_provider.py::test_transition_missing_config_error` |
| 10 | Given two transitions to the same target When second call Then transitions endpoint fetched once (cache) | `tests/integrations/jira/test_jira_work_provider.py::test_transition_id_cached` |
| 11 | Given existing comment containing marker When `comment` with same marker Then no POST | `tests/integrations/jira/test_jira_work_provider.py::test_comment_dedup_by_marker` |
| 12 | Given recorded search response with 2 issues When `changes_since` Then 2 events with `delivery_id` `jira:<key>:<updated>` | `tests/integrations/jira/test_jira_work_provider.py::test_changes_since_events` |
| 13 | Given `work-provider.yaml` with renamed statuses When loaded Then `status_map` overrides defaults and still covers all states | `tests/integrations/jira/test_mapping.py::test_status_map_override_complete` |
| 14 | Given `WALK_TEST_JIRA=1` and credentials When contract suite runs Then all `WorkProviderContract` scenarios pass (skipped otherwise) | `tests/integrations/jira/test_jira_contract.py::test_contract_parity_jira` |
| 15 | Given DEBUG logging When any request Then log records contain no `Authorization` header value | `tests/integrations/jira/test_client.py::test_logs_redact_authorization` |

#### Evidence required
- Quality gate output (integration tests skipped by default).
- Demo (optional, with tenant): `WALK_TEST_JIRA=1 uv run pytest tests/integrations/jira -m integration -q` transcript; `walk doctor` shows `work_provider: ready` for `--provider jira`.

#### Notes
- ADR-0005 D-3, D-6; ADR-0009 D-8 (credential names); ARCHITECTURE §2.3 (`httpx` only under `integrations/jira/`).
- `NEW NAME:` `WorkProviderConfig`, `JiraClient`, `JiraMapping`, `DEFAULT_STATUS_MAP`, `load_work_provider_config`.
- Pitfall: Jira Cloud REST v3 comment bodies are ADF JSON, not Markdown — convert headings/lists minimally and keep the marker as a plain text node.
- Commit subject: `feat: add jira work provider (E03-S04)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S05 — Jira webhooks: `WebhookReceiver`, `walk run --webhook-port`, bootstrap status validation

**Status:** TODO
**Type:** feat
**Requirements:** §55, §56, §87, §91
**Depends on:** E03-S04, E03-S03, E01-S30
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel optionally listens for Jira webhooks (and serves a read-only `/status`), validates the shared secret, deduplicates deliveries and feeds `IntegrationManager.ingest`; bootstrap and doctor verify that the Jira workflow contains every status the kernel maps to.

#### Scope
- In: `WebhookReceiver` (stdlib asyncio HTTP server, two routes); `JiraWorkProvider.parse_webhook`; `walk run --webhook-port`; `GET /status`; bootstrap `--provider jira` status validation; `walk doctor` status-map gap report.
- Out: JWT issuer configuration UI (only verification when `WALK_WEBHOOK_JWT_SECRET` present); TLS (operator terminates TLS in front).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/webhook.py` | create | `WebhookReceiver`, `HttpRequest`, `HttpResponse` |
| `src/walk/integrations/jira/provider.py` | modify | `JiraWorkProvider.parse_webhook`, `JiraWorkProvider.missing_statuses` |
| `src/walk/integrations/service.py` | modify | `DefaultIntegrationManager.validate_work_provider` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.start` (starts receiver when configured) |
| `src/walk/cli/cmd_run.py` | modify | option `--webhook-port` |
| `src/walk/cli/cmd_bootstrap.py` | modify | provider validation output |
| `src/walk/cli/cmd_doctor.py` | modify | status-map gap section |
| `src/walk/cli/composition.py` | modify | `KernelSettings.webhook_port` wiring |
| `tests/integrations/test_webhook.py` | create | — |
| `tests/integrations/jira/test_parse_webhook.py` | create | — |
| `tests/cli/test_cmd_bootstrap_jira.py` | create | — |

#### Interface contract
```python
class HttpRequest(FrozenModel):
    method: str; path: str; query: dict[str, str]; headers: dict[str, str]; body: bytes

class HttpResponse(FrozenModel):
    status: int; body: bytes; content_type: str = "application/json"

class WebhookReceiver:
    """Minimal HTTP/1.1 server on asyncio.start_server. Routes: POST /webhooks/jira, GET /status. Everything else -> 404."""
    def __init__(self, port: int, secret: SecretStr | None, jwt_secret: SecretStr | None, integrations: IntegrationManager,
                 status_provider: Callable[[], KernelStatus], max_body_bytes: int = 1_048_576) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def handle(self, request: HttpRequest) -> HttpResponse: ...   # pure routing, unit-testable

class JiraWorkProvider:
    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[WorkProviderEvent]: ...
    async def missing_statuses(self) -> list[str]: ...  # status_map values absent from the project's workflow statuses
```

`IntegrationManager.validate_work_provider() -> list[str]` returns missing statuses (empty for local).

#### Behavior
1. Request parsing: request line + headers + body up to `Content-Length` (reject > `max_body_bytes` with 413); malformed → 400; HTTP/1.1 keep-alive not supported (`Connection: close`).
2. `POST /webhooks/jira` without `?secret=<WALK_WEBHOOK_SECRET>` (constant-time compare) → 401 and no ingest. When `jwt_secret` configured, `Authorization: JWT <token>` is verified (HS256, `exp` honoured) using stdlib `hmac`/`base64`/`json`; invalid → 401.
3. Valid webhook: `events = work.parse_webhook(headers, body)`; each → `IntegrationManager.ingest`; respond 202 with `{"accepted": n}`. `parse_webhook` raising `NotSupported` (local provider) → 404.
4. `parse_webhook` maps Jira event types: `jira:issue_updated` with a `status` changelog item → `TRANSITIONED` (external_status = `toString`), other `issue_updated` → `UPDATED` (fields incl. priority name), `jira:issue_created` → `CREATED`, `comment_created` → `COMMENTED`, `jira:issue_deleted` → `DELETED`; `delivery_id` = header `X-Atlassian-Webhook-Identifier` or `sha256(body)` when absent; issues without a `walk:*` label → empty list.
5. `GET /status` → `status_provider()` as JSON (`KernelStatus.model_dump_json`), 200, no auth (read-only, §87).
6. `walk run --webhook-port N` sets `KernelSettings.webhook_port`; `DefaultOrchestrator.start` starts the receiver after recovery and stops it in `stop()`; port in use → `ConfigError` → exit 1.
7. `missing_statuses()`: `GET /rest/api/3/project/<KEY>/statuses` → set of names; returns `status_map` values not in the set.
8. `walk bootstrap --provider jira`: after preflight calls `validate_work_provider()`; non-empty → prints `Missing Jira statuses: …` and exits 4 (preflight failed) unless `--yes` (then warning, continues). `walk doctor` prints the same list under `work_provider` and sets `ComponentStatus(state=MISCONFIGURED, detail=...)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given valid secret and a status-change payload When `handle` Then 202 `{"accepted":1}` and `ingest` called with `TRANSITIONED` | `tests/integrations/test_webhook.py::test_valid_webhook_ingested` |
| 2 | Given wrong secret When `handle` Then 401 and no ingest | `tests/integrations/test_webhook.py::test_wrong_secret_rejected` |
| 3 | Given jwt configured and expired token When `handle` Then 401 | `tests/integrations/test_webhook.py::test_expired_jwt_rejected` |
| 4 | Given body larger than `max_body_bytes` When parsed Then 413 | `tests/integrations/test_webhook.py::test_oversized_body_rejected` |
| 5 | Given `GET /status` When `handle` Then 200 JSON parsable into `KernelStatus` | `tests/integrations/test_webhook.py::test_status_endpoint_returns_kernel_status` |
| 6 | Given `GET /nope` When `handle` Then 404 | `tests/integrations/test_webhook.py::test_unknown_route_404` |
| 7 | Given local provider When `POST /webhooks/jira` Then 404 | `tests/integrations/test_webhook.py::test_local_provider_webhook_not_supported` |
| 8 | Given real socket on an ephemeral port When `start` and a client posts Then same behaviour as `handle` | `tests/integrations/test_webhook.py::test_server_roundtrip_over_socket` |
| 9 | Given `issue_updated` changelog with status item When `parse_webhook` Then one `TRANSITIONED` event with `external_status` and identifier header as `delivery_id` | `tests/integrations/jira/test_parse_webhook.py::test_status_change_event` |
| 10 | Given issue without `walk:*` label When `parse_webhook` Then `[]` | `tests/integrations/jira/test_parse_webhook.py::test_non_walk_issue_ignored` |
| 11 | Given missing identifier header When `parse_webhook` Then `delivery_id == sha256(body)` | `tests/integrations/jira/test_parse_webhook.py::test_delivery_id_fallback_hash` |
| 12 | Given project statuses lacking "Rework" When `missing_statuses` Then `["Rework"]` | `tests/integrations/jira/test_parse_webhook.py::test_missing_statuses_detected` |
| 13 | Given `walk bootstrap --provider jira` with missing statuses and no `--yes` When run Then exit 4 and list printed | `tests/cli/test_cmd_bootstrap_jira.py::test_bootstrap_jira_missing_statuses_exit_4` |
| 14 | Given port already bound When `walk run --webhook-port` Then `ConfigError` exit 1 | `tests/cli/test_cmd_bootstrap_jira.py::test_run_webhook_port_in_use_exit_1` |

#### Evidence required
- Quality gate output.
- Demo: `walk run --once --webhook-port 8765 &` then `curl -s localhost:8765/status | head -c 200` shows `{"project_key": …`; `curl -X POST 'localhost:8765/webhooks/jira?secret=bad'` → `401`.

#### Notes
- ADR-0005 D-4, ADR-0009 D-3 (optional HTTP listener only for webhooks and `/status`), ADR-0009 D-8 (`WALK_WEBHOOK_SECRET`).
- `NEW NAME:` `WebhookReceiver` placed at `src/walk/integrations/webhook.py`; `HttpRequest`, `HttpResponse`; `WALK_WEBHOOK_JWT_SECRET` credential; `JiraWorkProvider.missing_statuses`; `IntegrationManager.validate_work_provider`.
- Decision recorded here: no new HTTP framework dependency; a minimal parser restricted to two routes is sufficient and auditable. Re-evaluate if more endpoints appear (E09-S04).
- Commit subject: `feat: add webhook receiver and provider status validation (E03-S05)`.

#### Evidence (filled by implementer)
_pending_
