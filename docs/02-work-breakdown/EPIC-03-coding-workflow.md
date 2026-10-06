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

---

### E03-S06 — Full MVP constitutions and task templates

**Status:** TODO
**Type:** feat
**Requirements:** §10.1, §10.6, §10.7, §10.8, §12, §23, §63, §65, §126, §137 (Invariants 1, 4)
**Depends on:** E01-S17, E01-S18
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The four MVP constitutions (ORCHESTRATOR, LEAD_DEV, SENIOR_DEV, QC) carry the complete §10 role content in ADR-0013 form, and the six coding-workflow task templates (`IMPLEMENT`, `REVIEW`, `QC`, `PLAN`, `DESIGN`, `TRIAGE`) tell each role exactly which `AgentOutput` fields the kernel flows of E03-S08…S17 consume.

#### Scope
- In: full front matter + body sections for the four MVP roles; `tool_permissions` mirroring ADR-0006 D-6; `forbidden_actions`; QC "Working Guidance" with the §65 investigation list; template bodies for the six purposes; template/constitution consistency tests.
- Out: `DEBATE` (E05), `ANALYSIS`/`RETRO` (E07) templates; PRODUCT_OWNER/DESIGN_LEADER constitutions (E05-S06); context-first/stale-verification instructions (E04-S14); `TRIAGE` structured verdict field (E03-S15 adds it and amends the template).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/defaults/orchestrator.md` | modify | — |
| `src/walk/agents/defaults/lead_dev.md` | modify | — |
| `src/walk/agents/defaults/senior_dev.md` | modify | — |
| `src/walk/agents/defaults/qc.md` | modify | — |
| `src/walk/agents/templates/IMPLEMENT.md.j2` | modify | — |
| `src/walk/agents/templates/REVIEW.md.j2` | modify | — |
| `src/walk/agents/templates/QC.md.j2` | modify | — |
| `src/walk/agents/templates/PLAN.md.j2` | modify | — |
| `src/walk/agents/templates/DESIGN.md.j2` | modify | — |
| `src/walk/agents/templates/TRIAGE.md.j2` | modify | — |
| `src/walk/agents/templates/_output_contract.md.j2` | create | — (shared partial: how to write `.walk/output.json`, included by every template) |
| `tests/agents/test_defaults.py` | modify | — |
| `tests/agents/test_templates_e03.py` | create | — |

#### Interface contract
Constitution file format: ADR-0013 D-2 (front matter) and D-3 (body sections, in order). Template rendering: `AgentManager.render_instructions(agent, item, purpose)` (INTERFACES §1.2) with the Jinja context `{agent, item, purpose, feature_doc_id, bug_doc_id, required_evidence, status_options, handover}`.

Constitution content fixed by this story (front matter values; body elaborates):

| Role | `authority.decision_scope` | `max_autonomy_level` | `may_approve` | `may_create_work` | `tool_permissions` (ADR-0006 D-6) | `forbidden_actions` (minimum) |
|---|---|---|---|---|---|---|
| ORCHESTRATOR | `[PROCESS]` | 1 | `[]` | `[EPIC, FEATURE, STORY, TASK]` | ALLOW `jira.create_*`, `jira.transition`, `work.plan`; DENY all file write tools; REQUIRE_APPROVAL(USER) `permissions.alter` | "decide gameplay or architecture", "approve or reject implementations", "close a feature" |
| LEAD_DEV | `[TECH]` | 1 | `[review.approve, ARCHITECTURE_DIRECTION]` | `[TASK, BUG]` | as SENIOR_DEV + ALLOW `review.approve`, `review.reject`, `jira.create_task`; DENY `jira.close_feature`; REQUIRE_APPROVAL(USER) `git.merge_protected` | "approve own implementation", "close a feature without QC acceptance", "merge to a protected branch without approval" |
| SENIOR_DEV | `[]` | 0 | `[]` | `[]` | ALLOW file tools in worktree, `bash` build/test/graph commands, `git.commit`; DENY `git.merge_protected`, `git.push_protected`, `jira.close_feature`, `review.approve`, `rm -rf`, `git push --force`, network fetch | "declare own work complete", "edit `.ai/agents/**`", "modify tests to make them pass" |
| QC | `[]` | 0 | `[qc.approve]` | `[BUG]` | ALLOW read tools, `bash` test/run commands, `jira.create_bug`, `jira.reopen`, `qc.approve`, `qc.reject`; DENY all file write tools | "fix code", "close a bug without reproduction evidence", "approve without evidence" |

Template output requirements (what each template MUST instruct; verified by rendering tests):

| Purpose | Status options | Mandatory output fields |
|---|---|---|
| `PLAN` (FEATURE/IDEA) | `COMPLETED`, `BLOCKED`, `NEEDS_INPUT` | `new_tasks`: ≥ 1 `WorkItemDraft(kind=STORY, parent_id=<feature>)` each with full `StoryContract` (`goal`, `acceptance_criteria`, `required_evidence ⊇ [AUTOMATED_TEST]`, `owner_role=SENIOR_DEV`, `reviewer_role=LEAD_DEV`, `complexity`); `context_updates` on `<FEAT-id>` sections `Intent`, `Design Goal` |
| `DESIGN` (FEATURE/DESIGN) | `COMPLETED`, `BLOCKED`, `REJECTED` | `context_updates` on `<FEAT-id>` section `Architecture` (REPLACE) plus `Affected Systems`, `Relevant Files`; `decisions` proposals for TECH choices |
| `IMPLEMENT` (STORY/TASK/BUG) | `COMPLETED`, `PARTIAL`, `BLOCKED`, `NEEDS_INPUT`, `FAILED` | `changes` matching the real diff; `evidence` ≥ 1 `AUTOMATED_TEST`; `context_updates` (`Implementation Notes`, `Relevant Files`; for BUG: `Root Cause`, `Fix`, `Regression Risk`); `handover` when `PARTIAL`; `escalations` when `BLOCKED`/`NEEDS_INPUT`; never run `git commit`/`push` (the kernel commits) |
| `REVIEW` (READY_FOR_REVIEW) | `APPROVED`, `REJECTED` | `findings` (≥ 1 when `REJECTED`, each with `affected_files`); `context_updates` on the parent doc section `Implementation Notes` (APPEND) when `REJECTED`; no `changes` |
| `QC` (QC) | `APPROVED`, `REJECTED` | `evidence` ≥ 1 `QC_REPORT` (plus `REPRODUCTION_PROOF` when verifying a BUG); `new_bugs` ≥ 1 when `REJECTED`; `context_updates` on the parent doc `QC Notes`; no `changes` |
| `TRIAGE` (BUG/DISCOVERY) | `COMPLETED`, `NEEDS_INPUT` | severity + owner verdict (structured field added by E03-S15); `context_updates` on `<BUG-id>` sections `Problem`, `Hypotheses` |

#### Behavior
1. Every default constitution validates through `ConstitutionLoader` (E01-S17) with `version: "1.0"`, all ADR-0013 D-3 body sections present in order, and no provider/model name anywhere (ADR-0013 D-5 lint).
2. `Constitution.tool_permissions` of each role equals the D-6 row for that role expressed as `PermissionRule`s with `role` set; `PermissionManager.rules_for(role, extra=constitution.tool_permissions)` yields no widening relative to `permissions/defaults.yaml` (E02-S10 narrowing check passes).
3. `Constitution.preferred_evidence`: LEAD_DEV `[AUTOMATED_TEST, REPRODUCIBLE_BENCHMARK, PROFILER_RESULT]`; SENIOR_DEV `[AUTOMATED_TEST, LOG]`; QC `[QC_REPORT, GAMEPLAY_RECORDING, SCREENSHOT, REPRODUCTION_PROOF, AUTOMATED_TEST]`; ORCHESTRATOR `[PROJECT_DATA]`.
4. QC body `## Working Guidance` contains the six §65 questions verbatim and the §10.8 sentence "QC identifies existence and severity of issues; the business decision whether to fix belongs to PO/Design/Lead Dev".
5. LEAD_DEV body `## Professional Bias` contains the §10.6 "guard against over-engineering" clause; `## Forbidden Actions` includes approving own implementation (Invariant 4).
6. Every template includes `_output_contract.md.j2`, which states: the last action of the run is writing `<worktree>/.walk/output.json` conforming to `AgentOutput`; `status` must be one of the template's status options; `no_context_change_reason` is required when `context_updates` is empty; thinking/reasoning is never written to the file.
7. Each template renders deterministically (same inputs → identical text) and contains the field list of the table above; unknown purpose → `ConfigError` (unchanged from E01-S18).
8. `REVIEW` and `QC` templates instruct the agent to inspect `git diff <base>...HEAD` / run tests inside the worktree only, and state that the verdict is applied by the kernel (ADR-0006 consequence) — the agent never transitions work items itself.
9. `IMPLEMENT` renders the §22 handover continuation block ("continue from `handover.next_action`") only when `handover` is present in the render context.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the four default constitutions When loaded Then all validate, body sections appear in ADR-0013 D-3 order and `version == "1.0"` | `tests/agents/test_defaults.py::test_mvp_constitutions_full_sections_in_order` |
| 2 | Given each role When `tool_permissions` compared with ADR-0006 D-6 rows Then exact match on `(tool, effect, approver)` | `tests/agents/test_defaults.py::test_tool_permissions_match_adr_0006` |
| 3 | Given each constitution When merged via `rules_for(role, extra=…)` Then no rule widens `permissions/defaults.yaml` | `tests/agents/test_defaults.py::test_constitution_permissions_do_not_widen_defaults` |
| 4 | Given the QC constitution Then `Working Guidance` contains all six §65 questions | `tests/agents/test_defaults.py::test_qc_working_guidance_contains_section_65_questions` |
| 5 | Given all four constitutions When scanned with the provider-name lint Then zero hits | `tests/agents/test_defaults.py::test_constitutions_have_no_provider_names` |
| 6 | For each purpose in the table When rendered for a sample item Then the text lists every mandatory field and the exact status options | `tests/agents/test_templates_e03.py::test_templates_list_mandatory_fields_and_statuses` |
| 7 | Given any template When rendered twice with the same input Then byte-identical | `tests/agents/test_templates_e03.py::test_templates_render_deterministically` |
| 8 | Given `IMPLEMENT` with and without `handover` Then the continuation block is present only with a handover | `tests/agents/test_templates_e03.py::test_implement_template_handover_block_conditional` |
| 9 | Given every template Then it includes the output-contract partial mentioning `.walk/output.json` and `no_context_change_reason` | `tests/agents/test_templates_e03.py::test_output_contract_partial_included_everywhere` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor --strict` on a bootstrapped repo → `constitutions: ok (4 roles, no provider names)`; paste the rendered `REVIEW` template for `STORY-0001` (first 40 lines) captured by `tests/agents/test_templates_e03.py`.

#### Notes
- ADR-0013 D-2–D-5, ADR-0006 D-6, ADR-0004 D-4 (prompt assembly is kernel-owned), WBS.md §3.9.
- `NEW NAME:` template partial `_output_contract.md.j2`; `may_approve` value `qc.approve` for QC (ADR-0013 example lists `review.approve` only).
- Also read: E01-S18 is not yet written in `EPIC-01-kernel-core.md`; template file names follow WBS.md §3.9 (`src/walk/agents/templates/<purpose>.md.j2`). If E01-S18 lands them elsewhere, update this Files table in the same commit and say so in the commit body.
- Pitfall: constitutions must not reference `fake-codex`/`fake-claude` either; the lint pattern (E02-S15 `PROVIDER_NAME_PATTERN`) catches `codex|claude|gpt|anthropic|openai`.
- Commit subject: `feat: complete mvp constitutions and coding task templates (E03-S06)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S07 — `TaskRouter` full table, `can_run_parallel`, cross-model review enforcement

**Status:** TODO
**Type:** feat
**Requirements:** §10.1, §23, §29, §60, §63, §137 (Invariant 4)
**Depends on:** E01-S29, E03-S06
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`TaskRouter` resolves every INTERFACES §4 row for FEATURE/STORY/TASK/BUG from `scheduled_states.yaml` (including fallback roles and contract-driven roles), refuses to route a review or QC to the role that implemented the item, decides pairwise parallel safety per §60, and the scheduler enforces §23 cross-model review mechanically with a user-resolvable escape hatch.

#### Scope
- In: `DefaultTaskRouter.route/can_run_parallel` complete; `implementer_of`; `contract_paths`; `TaskProfile` construction incl. `implementer_model_id`; scheduler-side cross-model check; `ON_READY_FOR_QC` builtin; `RoutingDecision.rejected` entry for cross-model deferral.
- Out: raising `start_review`/`start_fix` on admission (E03-S13/S15); scheduler ordering and worktree parallelism (E03-S18); PHASE/DEBATE routing rows (E05/E07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/router.py` | modify | `DefaultTaskRouter.route`, `DefaultTaskRouter.can_run_parallel`, `DefaultTaskRouter.implementer_of`, `contract_paths` |
| `src/walk/orchestrator/scheduler.py` | modify | `Scheduler.check_cross_model` |
| `src/walk/orchestrator/errors.py` | modify | `CrossModelReviewUnsatisfiable(GuardRejected)` |
| `src/walk/model_router/service.py` | modify | — (`DefaultModelRouter.select` appends `(model_id, "cross_model_review")` to `RoutingDecision.rejected` when the implementer model is deferred) |
| `src/walk/hooks/builtins.py` | modify | `builtin.qc_cross_model` (on `ON_READY_FOR_QC`) |
| `tests/orchestrator/test_router.py` | create | — |
| `tests/orchestrator/test_cross_model.py` | create | — |
| `tests/model_router/test_select_cross_model.py` | create | — |
| `tests/hooks/test_builtins_ready_for_qc.py` | create | — |

#### Interface contract
See `INTERFACES.md` §1.1 `TaskRouter` (`route`, `can_run_parallel`) and §4 routing table; `RouteDecision`, `TaskProfile` (DOMAIN-MODEL §4.10). Additions:

```python
class DefaultTaskRouter:
    def __init__(self, scheduled_states: Path, agents: AgentManager, runs: AgentRunRepository, workflow: WorkflowManager) -> None: ...
    def route(self, item: WorkItem, state: WorkItemState) -> RouteDecision: ...
    def can_run_parallel(self, a: WorkItem, b: WorkItem) -> bool: ...
    async def implementer_of(self, item: WorkItem) -> tuple[AgentRole, ModelId] | None:
        """(role, model_id) of the latest run with purpose IMPLEMENT on `item` (for FEATURE: over its children); None when no such run."""

def contract_paths(item: WorkItem) -> set[str]:
    """Repo-relative paths mentioned in contract.goal/acceptance_criteria/constraints/description matching PATH_PATTERN."""

class Scheduler:
    def check_cross_model(self, route: RouteDecision, routing: RoutingDecision) -> None:
        """Raises CrossModelReviewUnsatisfiable when route.cross_model_review and routing.model_id == route.profile.implementer_model_id."""
```

`PATH_PATTERN = r"(?:Assets|Packages|ProjectSettings|src|tests)/[\w./-]+\.(?:cs|asmdef|prefab|unity|asset|json|yaml|md|py)"` (module constant in `router.py`).

#### Behavior
1. `route` reads `scheduled_states.yaml` (E01-S10): `role` literal, or `contract.owner_role` / `contract.reviewer_role` resolved from the item's `StoryContract`; `fallback_role` is used when the primary role is not in `AgentManager.list_roles()` (DISCOVERY → ORCHESTRATOR in MVP). `(kind, state)` without a row → `UnknownTransition`-like `ConfigError("no scheduled role for …")`.
2. `RouteDecision.profile` = `TaskProfile(required_capabilities = purpose defaults {IMPLEMENT: [CODING, TOOL_USE], REVIEW: [REVIEW, CODING], QC: [REVIEW, TOOL_USE], PLAN: [PLANNING], DESIGN: [ARCHITECTURE], TRIAGE: [REVIEW]}, required_tools = RuntimePolicy.allowed_tools ∩ ToolRegistry, required_skills = contract.required_skills, estimated_context_tokens = 0, risk = item.risk, implementer_model_id = implementer_of(item)[1] for purposes REVIEW/QC else None)`. `RouteDecision.cross_model_review = RuntimePolicy(role).model_policy.cross_model_review`.
3. Invariant 4: for purposes `REVIEW`/`QC`, if the resolved role equals `implementer_of(item)[0]` → `PermissionDenied("reviewer role equals implementer role")`; `route` is pure apart from the repository lookup and never mutates the item.
4. `can_run_parallel(a, b)` is `False` when: `a.id == b.id`; `b.id ∈ a.contract.dependencies` or vice versa (transitively through one level of parents is not required); both have the same ancestor FEATURE and `contract_paths(a) ∩ contract_paths(b)` is non-empty; `a.branch == b.branch` (both non-None); either item is a BUG whose `related_feature_id` equals the other's ancestor FEATURE and the other is in `IMPLEMENTING` (a fix and a story on the same feature branch never run together). Otherwise `True`. Symmetric.
5. `Scheduler.check_cross_model` runs after `ModelRouter.select` and before `AgentExecutor.start` for `REVIEW`/`QC` routes: same model as implementer and `cross_model_review=True` → `CrossModelReviewUnsatisfiable`. The scheduler then (a) writes telemetry counter `scheduler.cross_model_unsatisfiable`, (b) creates one `ApprovalRequest(kind="ESCALATION", approver=USER, payload={"reason": "cross_model_review_unsatisfiable", "work_item_id", "implementer_model_id"})` per `(item, state_version)` (idempotent via `schedule:` key suffix `:cross_model`), and (c) skips the item this tick. When that request is APPROVED, the next tick routes with `cross_model_review=False` for this item and the `start_review` guard receives `cross_model_review=False` (E03-S13). DENIED → item stays; user may `walk policy set-model`.
6. `DefaultModelRouter.select` (INTERFACES §5.3 step 3): when the implementer model is deferred and another candidate wins, `RoutingDecision.rejected` contains `(implementer_model_id, "cross_model_review")` so the `MODEL_SELECTED` ledger payload documents the §23 preference.
7. `builtin.qc_cross_model` (`ON_READY_FOR_QC`, required, priority 20): asserts `implementer_of(item)` resolves for STORY/TASK/BUG (fails closed with `HookFailed("no implementer run")`); for FEATURE it is a no-op when the feature has no child runs; writes payload key `implementer_model_id` into `ctx.payload` for diagnostics. It does not schedule anything (the scheduler does on the next tick).
8. `implementer_of` for FEATURE returns the latest IMPLEMENT run across its child STORY/TASK items and related BUGs; the QC run for a feature therefore prefers a model different from the most recent implementer.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | For every FEATURE/STORY/TASK/BUG row of INTERFACES §4 When `route(item, state)` Then role and purpose match the table | `tests/orchestrator/test_router.py::test_route_matches_interfaces_routing_table` |
| 2 | Given DESIGN_LEADER not in `list_roles()` When `route(FEATURE, DISCOVERY)` Then ORCHESTRATOR/DESIGN | `tests/orchestrator/test_router.py::test_route_uses_fallback_role_when_role_disabled` |
| 3 | Given a STORY whose contract `owner_role=LEAD_DEV` and `reviewer_role=LEAD_DEV` with an IMPLEMENT run by LEAD_DEV When `route(READY_FOR_REVIEW)` Then `PermissionDenied` | `tests/orchestrator/test_router.py::test_route_refuses_reviewer_equal_to_implementer` |
| 4 | Given an IMPLEMENT run with model `fake-codex/sim` When `route(QC)` Then `profile.implementer_model_id == "fake-codex/sim"` and `cross_model_review` from policy | `tests/orchestrator/test_router.py::test_route_profile_carries_implementer_model` |
| 5 | Given two stories of one feature mentioning `Assets/Scripts/Jump.cs` in both contracts When `can_run_parallel` Then `False`; disjoint paths → `True` | `tests/orchestrator/test_router.py::test_can_run_parallel_overlapping_contract_paths` |
| 6 | Given `b.id ∈ a.contract.dependencies` Then `False` both directions | `tests/orchestrator/test_router.py::test_can_run_parallel_dependency_edge_symmetric` |
| 7 | Given two items with the same `branch` Then `False` | `tests/orchestrator/test_router.py::test_can_run_parallel_same_branch_false` |
| 8 | Given `cross_model_review=True`, implementer `fake-codex/sim`, select returns `fake-codex/sim` When `check_cross_model` Then `CrossModelReviewUnsatisfiable`, one ESCALATION approval created, no run started | `tests/orchestrator/test_cross_model.py::test_unsatisfiable_cross_model_creates_escalation_and_skips` |
| 9 | Given that approval APPROVED When next tick Then review run starts with the same model and `start_review` payload `cross_model_review=False` | `tests/orchestrator/test_cross_model.py::test_approved_escalation_allows_same_model_review` |
| 10 | Given `cross_model_review=False` and same model Then no error and run starts | `tests/orchestrator/test_cross_model.py::test_disabled_cross_model_allows_same_model` |
| 11 | Given two healthy candidates and `implementer_model_id` equal to the preferred one When `select` Then the other model is chosen and `rejected` contains `(preferred, "cross_model_review")` | `tests/model_router/test_select_cross_model.py::test_select_defers_implementer_model_and_records_reason` |
| 12 | Given a STORY with no IMPLEMENT run When `fire(ON_READY_FOR_QC)` Then `HookFailed("no implementer run")`; with a run → OK and payload has `implementer_model_id` | `tests/hooks/test_builtins_ready_for_qc.py::test_qc_cross_model_hook_requires_implementer_run` |

#### Evidence required
- Quality gate output.
- Demo: on the E01 gate fixture with both fakes, `walk ledger query --kind MODEL_SELECTED --item STORY-0001 --json` shows the REVIEW run's payload `rejected: [["fake-codex/sim", "cross_model_review"]]`.

#### Notes
- INTERFACES §4, §5.1 steps 5–6, §5.3 step 3; ARCHITECTURE §3.2 "Concurrency" and §7 Invariant 4; ADR-0009 D-4.
- `NEW NAME:` `DefaultTaskRouter.implementer_of`, `contract_paths`, `PATH_PATTERN`, `Scheduler.check_cross_model`, `CrossModelReviewUnsatisfiable`, builtin hook id `builtin.qc_cross_model`, approval payload reason `cross_model_review_unsatisfiable`, purpose → capability defaults table (Behavior 2).
- Also read: E01-S29 is not yet written; `router.py`/`scheduler.py`/`errors.py` under `src/walk/orchestrator/` are the assumed E01-S29 file names (ARCHITECTURE §1.3 layout). Adjust the Files table if E01-S29 differs and say so in the commit body.
- Pitfall: `can_run_parallel` is evaluated against every running item each tick — keep it free of I/O (contract paths are computed from the in-memory item).
- Commit subject: `feat: complete task router and cross-model review enforcement (E03-S07)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S08 — `OutputApplier` full: new tasks/bugs → work provider, change reconciliation, kernel commit

**Status:** TODO
**Type:** feat
**Requirements:** §55, §59, §63, §90, §91, §126, §137 (Invariants 3, 4, 9)
**Depends on:** E01-S27, E03-S02, E03-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every structured `AgentOutput` intent is executed by the kernel in the ARCHITECTURE §3.2 step-6 order — context updates, evidence, decisions (held as proposals), new work items into the work provider, escalations, reconciled file changes committed by the kernel — after which the workflow event implied by `(kind, state, purpose, status)` is raised from a data table, with every external write permission-checked against the acting role and idempotent.

#### Scope
- In: `DefaultOutputApplier.apply` complete; `output_events.yaml` + loader; `reconcile_changes`; `commit_changes`; guard payload keys of WBS.md §3.4 written by the applier; `ON_STATE_TRANSITION`/`ON_TASK_BLOCKED`/`ON_COMMIT` builtins syncing the work provider; `raise_event` hook payload pass-through.
- Out: QC-specific bug flow and `QC_RESULT`/`BUG_CREATED` ledger (E03-S14); review-specific effects (E03-S13); triage verdict (E03-S15); feature PLAN/DESIGN effects (E03-S09); `DecisionManager.propose` (E04-S05) and `Orchestrator.handle_escalation` (E05-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/output_applier.py` | modify | `DefaultOutputApplier.apply`, `DefaultOutputApplier.reconcile_changes`, `DefaultOutputApplier.commit_changes`, `DefaultOutputApplier.guard_payload` |
| `src/walk/runtime/output_events.py` | create | `OutputEventTable`, `load_output_event_table`, `OUTPUT_EVENTS_PATH` |
| `src/walk/runtime/tables/output_events.yaml` | create | — |
| `src/walk/runtime/models.py` | modify | `ChangeDiscrepancy`, `OutputApplyReport` |
| `src/walk/workflow/service.py` | modify | — (`raise_event` merges `ctx.payload` into the transition hooks' `HookContext.payload`; E01-S09 rule 3 widened) |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.set_external_ref` |
| `src/walk/hooks/builtins.py` | modify | `BuiltinHookDeps.work`, `BuiltinHookDeps.integrations`, `BuiltinHookDeps.workflow`; hooks `builtin.work_provider_sync`, `builtin.task_blocked_sync`, `builtin.commit_comment` |
| `src/walk/cli/composition.py` | modify | — (wires the new deps; constructs `DefaultOutputApplier` with `ToolInvoker`, `IntegrationManager`, `GitProvider`) |
| `tests/runtime/test_output_applier_full.py` | create | — |
| `tests/runtime/test_output_events.py` | create | — |
| `tests/hooks/test_builtins_work_provider.py` | create | — |
| `tests/workflow/test_service_transitions.py` | modify | — |

#### Interface contract
See `INTERFACES.md` §1.13 `OutputApplier.apply(run, output) -> AppliedEffects` and `AppliedEffects`. Additions:

```python
class ChangeDiscrepancy(FrozenModel):
    path: str
    declared: Literal["ADDED", "MODIFIED", "DELETED", "RENAMED"] | None   # None = changed on disk but not declared
    observed: Literal["ADDED", "MODIFIED", "DELETED", "RENAMED"] | None   # None = declared but not changed on disk

class OutputApplyReport(FrozenModel):
    effects: AppliedEffects
    discrepancies: list[ChangeDiscrepancy]
    denied_intents: list[str]            # e.g. "jira.create_bug", recorded as findings on the run
    guard_rejection: str | None          # reason when the implied event was rejected

class OutputEventTable(FrozenModel):
    version: str
    def event_for(self, kind: WorkItemKind, state: WorkItemState, purpose: str, status: AgentOutputStatus) -> str | None: ...

def load_output_event_table(path: Path = OUTPUT_EVENTS_PATH) -> OutputEventTable: ...   # every (kind, state, event) must exist in the workflow tables → ConfigError otherwise

class DefaultOutputApplier:
    async def apply(self, run: AgentRun, output: AgentOutput) -> AppliedEffects: ...          # protocol method; stores the OutputApplyReport on run.output metadata
    async def reconcile_changes(self, run: AgentRun, output: AgentOutput) -> list[ChangeDiscrepancy]: ...
    async def commit_changes(self, run: AgentRun, item: WorkItem, output: AgentOutput) -> Sha | None: ...
    def guard_payload(self, run: AgentRun, output: AgentOutput, evidence_kinds: list[EvidenceKind]) -> JsonDict: ...
```

`output_events.yaml` (`NEW NAME:`; `version: "1.0"`):

```yaml
rows:
  - {kind: [STORY, TASK, BUG], state: IMPLEMENTING,    purpose: IMPLEMENT, status: COMPLETED,   event: submit_for_review}
  - {kind: [STORY, TASK, BUG], state: IMPLEMENTING,    purpose: IMPLEMENT, status: PARTIAL,     event: partial}
  - {kind: [STORY, TASK, BUG], state: IMPLEMENTING,    purpose: IMPLEMENT, status: [BLOCKED, NEEDS_INPUT], event: block}
  - {kind: [STORY, TASK, BUG], state: LEAD_DEV_REVIEW, purpose: REVIEW,    status: APPROVED,    event: review_approved}
  - {kind: [STORY, TASK, BUG], state: LEAD_DEV_REVIEW, purpose: REVIEW,    status: REJECTED,    event: review_rejected}
  - {kind: [STORY, TASK],      state: QC,              purpose: QC,        status: APPROVED,    event: qc_passed}
  - {kind: [STORY, TASK],      state: QC,              purpose: QC,        status: REJECTED,    event: qc_rejected}
  - {kind: BUG,                state: QC,              purpose: QC,        status: APPROVED,    event: verified}
  - {kind: BUG,                state: QC,              purpose: QC,        status: REJECTED,    event: reopen}
  - {kind: BUG,                state: DISCOVERY,       purpose: TRIAGE,    status: COMPLETED,   event: triaged}
  - {kind: FEATURE,            state: IDEA,            purpose: PLAN,      status: COMPLETED,   event: start_discovery}
  - {kind: FEATURE,            state: IDEA,            purpose: PLAN,      status: [BLOCKED, NEEDS_INPUT], event: block}
  - {kind: FEATURE,            state: DISCOVERY,       purpose: DESIGN,    status: COMPLETED,   event: discovery_done}
  - {kind: FEATURE,            state: DESIGN,          purpose: DESIGN,    status: COMPLETED,   event: design_approved}
  - {kind: FEATURE,            state: DESIGN,          purpose: DESIGN,    status: [BLOCKED, REJECTED], event: block}
  - {kind: FEATURE,            state: QC,              purpose: QC,        status: APPROVED,    event: qc_passed}
  - {kind: FEATURE,            state: QC,              purpose: QC,        status: REJECTED,    event: qc_rejected}
```
`status: FAILED` has no row anywhere (the run fails; no workflow event).

Kernel commit message format (`NEW NAME:`): `<prefix>(<ITEM-ID>): <first line of output.result, ≤ 60 chars>` with prefix `impl` (IMPLEMENT on STORY/TASK), `fix` (IMPLEMENT on BUG), `design` (DESIGN), `plan` (PLAN); trailer `Walk-Work-Item: <ITEM-ID>` added by `GitProvider.commit_all`.

#### Behavior
1. Order inside `apply` (ARCHITECTURE §3.2 step 6), each step isolated so a failure in step *n* is recorded and later steps still run, except steps 7–8 which abort on `BoundaryViolation`:
   1. `context_updates` → `MemoryManager.apply_updates(updates, actor=Actor(run.role, run.model_id, run.id), head=git.head(worktree), branch=run.branch)`; `memory_docs` = returned paths. Empty updates with `no_context_change_reason is None` and `status != FAILED` → `Finding(severity=WARNING, "no context change reason")` and telemetry counter `output.no_context_reason`.
   2. `evidence` → `EvidenceManager.record(draft, actor, work_item_id=item.id, phase_id=item.phase_id, commit=head)` each; `evidence_ids` collected. A draft whose `path_or_uri` is outside the worktree or missing → skipped with a `Finding(RISK)`.
   3. `decisions` → kept as `DecisionProposal`s on `run.output` (status PROPOSED, Invariant 5); `decision_ids = []` until E04-S05 wires `DecisionManager.propose`.
   4. `new_tasks` → for each draft: `ToolInvoker.authorize(ToolCallRequest(run_id, role=run.role, tool="jira.create_task", kind=KERNEL, arguments=draft, worktree_path))`; `DENY` → intent skipped, listed in `denied_intents`, `Finding(RISK, "denied: jira.create_task")` (the `TOOL_DENIED` ledger is written by `ToolInvoker`); `ALLOW` → `WorkflowManager.create(draft, actor=run.role, phase_id=item.phase_id)` with `parent_id` defaulting to the run's item (FEATURE) or its ancestor FEATURE, then `IntegrationManager.with_idempotency(f"work.create:{new.id}", "work.create", lambda: work.create(new, idempotency_key=…))` → `WorkflowRepository.set_external_ref(new.id, ref.external_ref)`; `work.link(new, parent, "PARENT", idempotency_key=f"work.link:{new.id}:{parent.id}:PARENT")`. Drafts with `contract.reviewer_role == contract.owner_role` → `ConfigError` recorded as `Finding(RISK)` and skipped (Invariant 4 at creation).
   5. `new_bugs` → same authorisation with tool `jira.create_bug`; `WorkflowManager.create(BugDraft, …)` sets `related_feature_id` (draft value or the run item's ancestor FEATURE), `found_in_run_id=run.id`, `found_against_commit=head`; provider `create` + `link(bug, feature, "RELATES")`. The `triage` auto-event and `BUG_CREATED` ledger belong to E03-S14; here the bug is created in `IDEA` only.
   6. `escalations` → stored on `run.output`; `escalation_ids = []` (routing arrives in E05-S02); payload key `escalations_non_empty=True`.
   7. `changes` → `reconcile_changes`: observed = `git.status(worktree)` ∪ `git.diff_names(worktree, base=run_start_head)` mapped to ADDED/MODIFIED/DELETED/RENAMED; declared = `output.changes`; every mismatch → `ChangeDiscrepancy` + `Finding(WARNING, "changes mismatch")`; telemetry counter `output.change_discrepancy` with the count. Observed paths matching `forbidden_paths` → `BoundaryViolation` (defence in depth after E01-S27's audit) → run `FAILED_BOUNDARY`, `git checkout -- .` + `git clean -fd` in the worktree, no commit, no workflow event.
   8. `commit_changes`: observed changes non-empty → `git.commit_all(worktree, message, trailer_work_item=item.id, idempotency_key=f"git.commit:{run.id}:{latest_checkpoint_seq}")` → `commit_sha`; `COMMIT` ledger is written by `GitCliProvider` (E01-S23) and `ON_COMMIT` fires. Clean worktree → `commit_sha=None`. Roles whose rules DENY `git.commit` (QC, ORCHESTRATOR) with observed changes → `BoundaryViolation` as in 7 (read-only roles must not change files).
   9. `guard_payload` → `{output_status, has_commit, evidence_kinds_present (recorded ∪ EvidenceManager.for_item kinds), handover_present, escalations_non_empty, reproduction_evidence (REPRODUCTION_PROOF present), implementer_role, implementer_model_id (run role/model for IMPLEMENT purposes), run_id}` plus purpose-specific keys added by E03-S09/S13/S14/S15.
   10. `event = OutputEventTable.event_for(kind, state, purpose, status)`; `None` → `workflow_event=None`; else `WorkflowManager.raise_event(item.id, event, TransitionContext(actor_role=run.role, source=AGENT, run_id=run.id, payload=guard_payload ∪ {"handover": output.handover.model_dump() if any}))`.
2. `GuardRejected` from step 10: if a `block` row exists for `(kind, state)` → raise `block` with payload `{"escalations_non_empty": True, "blocked_reason": reason}` and a synthesized `EscalationRequest(to_level=PO, category=PROCESS, question=f"output rejected by guard: {reason}")` stored on the run; otherwise the run ends `FAILED` with `failure_reason=f"guard_rejected: {reason}"` and `ON_TASK_FAILED` fires (ledger `ERROR` by `AgentExecutor`). `OutputApplyReport.guard_rejection` records the reason either way; the item never silently stays schedulable with a stale `state_version`.
3. `PermissionDenied` from step 10 (role not allowed for the event, e.g. a SENIOR_DEV output mapped to `review_approved` because the table was mis-edited) is a kernel defect: run `FAILED`, ledger `ERROR`, telemetry counter `output.permission_denied`, no retry.
4. `partial` → the `handover` payload reaches `builtin.handoff_checkpoint_and_handover` (E02-S08) through the widened `raise_event` hook payload; a `PARTIAL` output without `handover` → `OutputInvalid` is already rejected by E01-S27 validation (re-tested here).
5. `builtin.work_provider_sync` (`ON_STATE_TRANSITION`, required, priority 30): `IntegrationManager.with_idempotency(f"work.transition:{item.id}:{transition_seq}", "work.transition", lambda: work.transition(item, to_state, idempotency_key=…))`; provider "no-op when equal" makes external-origin transitions safe (E03-S03 Notes). `TransientError` from the provider → `HookFailed`? No: provider sync is `LOG_AND_CONTINUE` for transient errors (counter `work_sync.transient`, retried by `WorkPoller.reconcile`), `FAIL_CLOSED` for `PermanentError`.
6. `builtin.task_blocked_sync` (`ON_TASK_BLOCKED`, required, priority 30): `work.transition(item, BLOCKED)` + `work.comment(item, f"BLOCKED: {blocked_reason}\n{escalation questions}", idempotency_key=f"work.comment:{item.id}:{ledger_seq}")`.
7. `builtin.commit_comment` (`ON_COMMIT`, default, `required=False`, priority 60): `work.comment(item, f"commit {sha[:7]}: {message}", idempotency_key=f"work.comment:{item.id}:{ledger_seq}")`.
8. Everything in steps 4–6 and the hooks goes through `IntegrationManager.with_idempotency`; replaying `apply` for the same run (recovery) creates no duplicate work items, links, comments or commits.
9. `AppliedEffects` is returned with `created_work_items` in creation order; `AgentRun.output` persists the `OutputApplyReport` under `run.output` metadata (`runs show` prints discrepancies and denied intents).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `output_events.yaml` When loaded Then every `(kind, state, event)` exists in the corresponding workflow table and `FAILED` maps to `None` everywhere | `tests/runtime/test_output_events.py::test_output_event_table_consistent_with_workflow_tables` |
| 2 | Given a row with event `nope` When loaded Then `ConfigError` naming the row | `tests/runtime/test_output_events.py::test_output_event_table_rejects_unknown_event` |
| 3 | Given a SENIOR_DEV IMPLEMENT run with `COMPLETED`, one context update, one AUTOMATED_TEST evidence and a dirty worktree When `apply` Then memory doc written, evidence recorded, kernel commit `impl(STORY-0001): …` with trailer, `COMMIT` ledger, story `READY_FOR_REVIEW`, `AppliedEffects.commit_sha` set | `tests/runtime/test_output_applier_full.py::test_apply_implement_completed_commits_and_submits_for_review` |
| 4 | Given declared `changes` differing from `git status` When `apply` Then two `ChangeDiscrepancy` rows, `Finding(WARNING)` on run, commit still made | `tests/runtime/test_output_applier_full.py::test_reconcile_changes_records_discrepancies` |
| 5 | Given an observed change under `.ai/agents/` When `apply` Then run `FAILED_BOUNDARY`, worktree reverted, no commit, no transition | `tests/runtime/test_output_applier_full.py::test_forbidden_path_change_fails_boundary_without_commit` |
| 6 | Given a QC run whose worktree has file changes When `apply` Then `BoundaryViolation` (QC may not change files) | `tests/runtime/test_output_applier_full.py::test_read_only_role_changes_rejected` |
| 7 | Given an ORCHESTRATOR PLAN run with two STORY drafts When `apply` Then two stories created (IDEA, `parent_id` = feature), provider rows with `walk:<id>` labels, PARENT links, `created_work_items` ordered | `tests/runtime/test_output_applier_full.py::test_new_tasks_created_in_provider_with_parent_links` |
| 8 | Given a SENIOR_DEV run with `new_bugs` When `apply` Then `TOOL_DENIED` ledger for `jira.create_bug`, no bug created, `denied_intents == ["jira.create_bug"]` | `tests/runtime/test_output_applier_full.py::test_new_bugs_denied_for_senior_dev` |
| 9 | Given a QC run with `new_bugs` When `apply` Then BUG created in IDEA with `related_feature_id`, `found_in_run_id`, `found_against_commit`, provider RELATES link | `tests/runtime/test_output_applier_full.py::test_new_bugs_created_by_qc_with_provenance` |
| 10 | Given a draft with `reviewer_role == owner_role` When `apply` Then skipped with `Finding(RISK)` and no item created | `tests/runtime/test_output_applier_full.py::test_draft_with_same_reviewer_and_owner_rejected` |
| 11 | Given `PARTIAL` with handover When `apply` Then `partial` raised, `ON_AGENT_HANDOFF` builtin received `handover`, `HO-0001.md` written, `HANDOFF` checkpoint | `tests/runtime/test_output_applier_full.py::test_partial_output_passes_handover_to_hooks` |
| 12 | Given `COMPLETED` without AUTOMATED_TEST evidence When `apply` Then `submit_for_review` guard rejected → `block` raised with synthesized escalation, item `BLOCKED`, `guard_rejection` set | `tests/runtime/test_output_applier_full.py::test_guard_rejection_blocks_item_with_reason` |
| 13 | Given a QC APPROVED output on a STORY without QC_REPORT evidence When `apply` Then run `FAILED` with `failure_reason` starting `guard_rejected:` and `ERROR` ledger (no `block` row in QC) | `tests/runtime/test_output_applier_full.py::test_guard_rejection_without_block_row_fails_run` |
| 14 | Given `apply` already executed for a run When `apply` again (recovery replay) Then no duplicate items, links, comments or commits | `tests/runtime/test_output_applier_full.py::test_apply_is_idempotent_on_replay` |
| 15 | Given a committed transition When `ON_STATE_TRANSITION` fires Then `work.transition` called once with key `work.transition:<id>:<seq>`; firing again with the same seq → no provider call | `tests/hooks/test_builtins_work_provider.py::test_state_transition_syncs_provider_idempotently` |
| 16 | Given `block` with reason When `ON_TASK_BLOCKED` fires Then provider status BLOCKED and one comment starting `BLOCKED:` | `tests/hooks/test_builtins_work_provider.py::test_task_blocked_syncs_status_and_comment` |
| 17 | Given provider raising `ProviderUnavailable` When `ON_STATE_TRANSITION` fires Then transition remains committed, counter `work_sync.transient`, no `HookFailed` | `tests/hooks/test_builtins_work_provider.py::test_transient_provider_error_does_not_fail_closed` |
| 18 | Given `raise_event` with `payload={"handover": …}` When transition hooks fire Then `HookContext.payload` contains `from`, `to`, `event` and `handover` | `tests/workflow/test_service_transitions.py::test_transition_hooks_receive_caller_payload` |

#### Evidence required
- Quality gate output.
- Demo: after a fake IMPLEMENT run on the E01 gate fixture — `git log --format='%s%n%(trailers)' story/STORY-0001-… -1` shows `impl(STORY-0001): …` + `Walk-Work-Item: STORY-0001`; `walk work show STORY-0001` shows `READY_FOR_REVIEW`; `cat .walk/work/LOCAL-2.md` front matter `status: READY_FOR_REVIEW`; `walk runs show RUN-… --json` includes `discrepancies: []`.

#### Notes
- ARCHITECTURE §3.2 step 6, §4.1 (`ON_STATE_TRANSITION`, `ON_TASK_BLOCKED`, `ON_COMMIT` rows), §4.3, §5.4; ADR-0006 D-2 (kernel-executed side effects; permission evaluated against the acting role), ADR-0006 consequence ("`AgentOutput.changes` must match the real diff"); ADR-0005 D-6; WBS.md §3.4, §3.5.
- Ownership fix: E02-S08 lists `ON_STATE_TRANSITION → WorkProvider.transition` and `ON_TASK_BLOCKED` under E03-S03, while E03-S03 Notes assign them to E03-S08. They are implemented **here** (E03-S03 has no `hooks/builtins.py` in its Files table). E03-S01 Scope already assigns `ON_COMMIT → WorkProvider.comment` to E03-S08.
- `NEW NAME:` `output_events.yaml` / `OutputEventTable` / `load_output_event_table` / `OUTPUT_EVENTS_PATH`; `ChangeDiscrepancy`, `OutputApplyReport`; `DefaultOutputApplier.reconcile_changes/commit_changes/guard_payload`; `WorkflowRepository.set_external_ref`; builtin ids `builtin.work_provider_sync`, `builtin.task_blocked_sync`, `builtin.commit_comment`; idempotency key `work.link:{from}:{to}:{kind}` (ARCHITECTURE §5.4 has none for links); kernel commit message format `<prefix>(<ID>): <summary>`; `BuiltinHookDeps.work/integrations/workflow`; payload keys `implementer_role`, `implementer_model_id`, `run_id`, `blocked_reason` written by the applier (WBS §3.4 lists the scheduler as the writer of `implementer_*` — the applier writes them for IMPLEMENT runs so later REVIEW/QC guards can read them from the transition history).
- Also read: E01-S27 is not yet written; `src/walk/runtime/output_applier.py` and `models.py` are the assumed file names. E01-S27's "OutputApplier core" presumably hard-codes the IMPLEMENT rows; this story replaces that with the YAML table — delete the hard-coded mapping in the same commit.
- Pitfall: `with_idempotency` joins the active `UnitOfWork` (E03-S03 rule 5). Steps 4–5 must each open their own UoW so a provider failure for the second draft does not roll back the first item.
- Commit subject: `feat: apply agent output effects via work provider and kernel commits (E03-S08)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S09 — Feature PLAN and DESIGN flow, `walk feature add`

**Status:** TODO
**Type:** feat
**Requirements:** §10.1, §10.6, §37, §52, §55, §57, §58, §59, §131
**Depends on:** E03-S08, E03-S07, E01-S16
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A user feature entered with `walk feature add` becomes `Feature(IDEA)` with a feature context document and a work-provider row, is planned by ORCHESTRATOR into stories (`PLAN`), passes discovery, receives a LEAD_DEV technical design (`DESIGN` → `FeatureContext` `Architecture`), and on `design_approved` the kernel creates the feature integration branch and moves every child story to `READY` — the "User Feature → Plan → Jira → LeadDev Technical Design" head of §131.

#### Scope
- In: `Orchestrator.submit_feature`; `walk feature add` (offline create and `--execute` via daemon); feature context skeleton; branch naming for every kind (`branch_name_for`, `slugify`); `builtin.ensure_branch` uses the per-kind base branch; `RunCompletionHandler` (single post-apply dispatch point) with the PLAN/DESIGN entries; PLAN/DESIGN guard payload keys in `DefaultOutputApplier.guard_payload`.
- Out: story implementation, review, integration (E03-S12/S13); feature `READY → IMPLEMENTING` and later feature transitions (E03-S17); typed `FeatureContext` parsing (E04-S01); GDD-compiled features (E06-S04); DESIGN_LEADER role (E05-S06 — MVP uses the ORCHESTRATOR fallback for `DISCOVERY`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/branches.py` | create | `slugify`, `branch_name_for`, `base_branch_for`, `BRANCH_PREFIXES` |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.set_branch` |
| `src/walk/workflow/__init__.py` | modify | re-export `branch_name_for`, `base_branch_for`, `slugify` |
| `src/walk/orchestrator/completion.py` | create | `RunCompletionHandler`, `CompletionContext` |
| `src/walk/orchestrator/feature_flow.py` | create | `FeatureFlow`, `FEATURE_CONTEXT_SKELETON_SECTIONS`, `USER_FEATURE_LABEL` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.submit_feature`; run-completion path calls `RunCompletionHandler.handle` |
| `src/walk/orchestrator/commands.py` | modify | — (command kind `feature.add` → `submit_feature` + `wake`) |
| `src/walk/runtime/output_applier.py` | modify | — (`guard_payload` adds `feature_context_sections`, `approved_artifact_ids`, `user_feature` for FEATURE runs) |
| `src/walk/hooks/builtins.py` | modify | — (`builtin.ensure_branch` uses `branch_name_for`/`base_branch_for`) |
| `src/walk/cli/cmd_feature.py` | create | `feature_app`, `feature_add` |
| `src/walk/cli/app.py` | modify | — (registers `feature` group) |
| `src/walk/cli/composition.py` | modify | — (wires `RunCompletionHandler`, `FeatureFlow`) |
| `tests/workflow/test_branches.py` | create | — |
| `tests/orchestrator/test_feature_flow.py` | create | — |
| `tests/orchestrator/test_completion.py` | create | — |
| `tests/cli/test_cmd_feature.py` | create | — |
| `tests/hooks/test_builtins.py` | modify | — |

#### Interface contract
`Orchestrator.submit_feature(title, description, gdd_refs) -> Feature` per `INTERFACES.md` §1.1; CLI `walk feature add TITLE --description TEXT --gdd REF... --execute` per `INTERFACES.md` §6; transitions per §3.1–§3.2; routing per §4 (FEATURE IDEA → ORCHESTRATOR/PLAN, DISCOVERY → DESIGN_LEADER else ORCHESTRATOR/DESIGN, DESIGN → LEAD_DEV/DESIGN). Additions:

```python
# src/walk/workflow/branches.py
BRANCH_PREFIXES: dict[WorkItemKind, str] = {FEATURE: "feat", STORY: "story", TASK: "task", BUG: "bug"}
def slugify(title: str, *, max_len: int = 40) -> str: ...            # lowercase ASCII, [a-z0-9-], runs of '-' collapsed, trimmed; "" → "item"
def branch_name_for(item: WorkItem) -> str: ...                      # f"{BRANCH_PREFIXES[kind]}/{item.id}-{slugify(item.title)}"; EPIC → ConfigError
def base_branch_for(item: WorkItem, parent_feature: Feature | None, default_branch: str) -> str: ...
    # FEATURE → default_branch; STORY/TASK → parent_feature.branch (ConfigError when None); BUG → related feature branch or default_branch

# src/walk/workflow/repository.py
class WorkflowRepository:
    async def set_branch(self, work_item_id: WorkItemId, branch: str) -> None: ...   # no transition, no ledger; updates updated_at

# src/walk/orchestrator/completion.py
class CompletionContext(FrozenModel):
    run: AgentRun
    item: WorkItem                      # re-read after OutputApplier.apply
    effects: AppliedEffects
class RunCompletionHandler:
    """Single post-apply dispatch point: (item.kind, run.purpose, effects.workflow_event) -> flow callable. Later stories register entries."""
    def register(self, kind: WorkItemKind, purpose: str, event: str | None, fn: Callable[[CompletionContext], Awaitable[None]]) -> None: ...
    async def handle(self, run: AgentRun, effects: AppliedEffects) -> None: ...      # duplicate registration → ConfigError

# src/walk/orchestrator/feature_flow.py
USER_FEATURE_LABEL = "user-feature"
FEATURE_CONTEXT_SKELETON_SECTIONS: tuple[str, ...] = ("Intent", "Design Goal", "Relevant GDD", "Current Status", "Architecture",
    "Affected Systems", "Dependencies", "Relevant Files", "Important Decisions", "Implementation Notes", "Known Risks",
    "QC Notes", "Evidence", "Remaining Work")                                          # §37 order
class FeatureFlow:
    def __init__(self, workflow: WorkflowManager, repo: WorkflowRepository, memory: MemoryManager, integrations: IntegrationManager,
                 git: GitProvider, project: Project, clock: Clock) -> None: ...
    async def create_user_feature(self, title: str, description: str, gdd_refs: list[GddRef]) -> Feature: ...
    async def on_design_approved(self, ctx: CompletionContext) -> None: ...
    def register(self, handler: RunCompletionHandler) -> None: ...                     # registers (FEATURE, "DESIGN", "design_approved")
```

Command row `feature.add` payload: `{"title", "description", "gdd": [str], "execute": bool}`; result `{"feature_id", "external_ref"}`.

#### Behavior
1. `create_user_feature`: `WorkflowManager.create(WorkItemDraft(kind=FEATURE, title, description), actor=USER, phase_id=project.current_phase_id)` with `labels=[USER_FEATURE_LABEL]` and `gdd_refs`; `context_path = .ai/features/<FEAT-id>.md`; then `MemoryManager.apply_updates([ContextUpdate(doc_id=<FEAT-id>, section="Intent", operation=REPLACE, content_markdown=description)], actor=Actor(USER), head=git.head(repo), branch=project.default_branch)` which creates the skeleton (E01-S16) — the skeleton has exactly `FEATURE_CONTEXT_SKELETON_SECTIONS` in order; then `IntegrationManager.with_idempotency(f"work.create:{id}", "work.create", …work.create…)` and `set_external_ref`. Ledger `WORK_ITEM_CREATED` (write point) and `CONTEXT_UPDATED` only.
2. `DefaultOrchestrator.submit_feature` = `create_user_feature` + `wake()`. The PLAN run is started by the next scheduler tick through the normal route (FEATURE/IDEA → ORCHESTRATOR/PLAN); `submit_feature` never calls `AgentExecutor` directly (single admission path, INTERFACES §5.1).
3. `walk feature add` without `--execute`: daemon running → `CommandClient` sends `feature.add` with `execute=false` (the consumer creates the feature but does not wake); daemon not running → a short-lived kernel (`build_kernel` without starting the scheduler) calls `FeatureFlow.create_user_feature`. Prints `FEAT-0001 (LOCAL-1) IDEA`; `--json` prints the result object. Empty title → exit 1.
4. `walk feature add --execute` without a running daemon → exit 3 ("daemon required"); with a daemon → `feature.add` with `execute=true` → `submit_feature`.
5. PLAN run (ORCHESTRATOR on FEATURE/IDEA): effects are applied by `DefaultOutputApplier` (E03-S08): stories created in `IDEA` with `parent_id=<FEAT-id>`, provider rows + PARENT links; event `start_discovery` (guard `in_phase_scope`). A PLAN output with zero `new_tasks` and status `COMPLETED` is a guard failure surfaced as `block` (`Finding(RISK, "plan produced no stories")`, payload `escalations_non_empty=True`) — the applier checks this before raising `start_discovery`.
6. DESIGN run on FEATURE/DISCOVERY (ORCHESTRATOR fallback in MVP): event `discovery_done`; `guard_payload` supplies `user_feature = USER_FEATURE_LABEL in feature.labels` for guard `has_gdd_refs_or_user_feature`.
7. DESIGN run on FEATURE/DESIGN (LEAD_DEV): `guard_payload` supplies `feature_context_sections` = H2 headings of `.ai/features/<FEAT-id>.md` whose body is non-empty after `context_updates` were applied, and `approved_artifact_ids` = ids of `ApprovedArtifact`s linked to the feature (empty in MVP); `technical_design_section_present` therefore passes only when `Architecture` was written. Event `design_approved` (allowed role LEAD_DEV).
8. `FeatureFlow.on_design_approved` (registered for `(FEATURE, "DESIGN", "design_approved")`): (a) `git.ensure_branch(branch_name_for(feature), base=project.default_branch, idempotency_key=f"git.branch:{feature.id}")` and `set_branch(feature.id, …)`; (b) for each child STORY/TASK in `IDEA` ordered by id: `set_branch(child.id, branch_name_for(child))`, then `raise_event(child.id, "ready", TransitionContext(actor_role=run.role, source=AGENT, run_id=run.id, payload={}))`; `GuardRejected` (Definition of Ready, §58) → `raise_event(child.id, "block", …payload={"blocked_reason": <reason>, "escalations_non_empty": True})`. One child failing never prevents the others.
9. `on_design_approved` is idempotent: re-running it (recovery replay) leaves already-`READY` children untouched (only `IDEA` children are processed) and `ensure_branch` replays its key.
10. `branch_name_for` is deterministic and ≤ 64 chars: `feat/FEAT-0001-double-jump`, `story/STORY-0002-jump-input-buffer`, `bug/BUG-0001-…`. `base_branch_for(STORY)` with a parent feature lacking `branch` → `ConfigError("feature branch not created")`.
11. `builtin.ensure_branch` (E02-S08) now resolves `name = item.branch or branch_name_for(item)` and `base = base_branch_for(item, parent_feature, default_branch)` (parent feature resolved through `BuiltinHookDeps.workflow`); behaviour for items whose `branch` was set earlier is unchanged.
12. `RunCompletionHandler.handle` is called exactly once per run after `OutputApplier.apply` returned, with the re-read item; no registered entry → no-op; an exception from an entry is logged, counted (`completion.error`) and re-raised to the orchestrator, which records `ERROR` through the executor write point — the transition already committed by the applier is never rolled back.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given titles with spaces, unicode and 80 chars When `slugify` Then lowercase ASCII with single hyphens, ≤ 40 chars; empty → `item` | `tests/workflow/test_branches.py::test_slugify_normalises_titles` |
| 2 | Given a FEATURE, STORY, TASK and BUG When `branch_name_for` Then prefixes `feat/`, `story/`, `task/`, `bug/` with id and slug; EPIC → `ConfigError` | `tests/workflow/test_branches.py::test_branch_name_for_each_kind` |
| 3 | Given a STORY whose feature has a branch, a BUG with and without `related_feature_id` When `base_branch_for` Then feature branch / feature branch / default branch; feature without branch → `ConfigError` | `tests/workflow/test_branches.py::test_base_branch_for_kinds` |
| 4 | Given an empty project When `create_user_feature("Double jump", "…")` Then `FEAT-0001` in IDEA with label `user-feature`, `.ai/features/FEAT-0001.md` with the 14 §37 sections in order and `Intent` filled, provider row `LOCAL-1` linked via `external_ref` | `tests/orchestrator/test_feature_flow.py::test_create_user_feature_creates_item_context_and_provider_row` |
| 5 | Given `submit_feature` When the next tick runs with fake adapters Then one PLAN run for ORCHESTRATOR on FEAT-0001 is started and no run was started by `submit_feature` itself | `tests/orchestrator/test_feature_flow.py::test_submit_feature_plan_run_started_by_scheduler` |
| 6 | Given a PLAN output with two STORY drafts When applied Then two stories in IDEA under the feature and the feature in DISCOVERY | `tests/orchestrator/test_feature_flow.py::test_plan_output_creates_stories_and_starts_discovery` |
| 7 | Given a PLAN output `COMPLETED` with no `new_tasks` When applied Then the feature is BLOCKED with reason containing `plan produced no stories` | `tests/orchestrator/test_feature_flow.py::test_plan_without_stories_blocks_feature` |
| 8 | Given a user feature in DISCOVERY When the ORCHESTRATOR DESIGN output is applied Then `discovery_done` passes via `user_feature=True` and the feature is in DESIGN | `tests/orchestrator/test_feature_flow.py::test_discovery_done_for_user_feature` |
| 9 | Given a LEAD_DEV DESIGN output without an `Architecture` update When applied Then `design_approved` is rejected and the feature is BLOCKED | `tests/orchestrator/test_feature_flow.py::test_design_without_architecture_section_blocks` |
| 10 | Given a LEAD_DEV DESIGN output writing `Architecture` When applied and completion handled Then feature in READY, branch `feat/FEAT-0001-…` exists from `main`, both stories READY with `branch` set | `tests/orchestrator/test_feature_flow.py::test_design_approved_creates_feature_branch_and_readies_stories` |
| 11 | Given one story with empty `acceptance_criteria` When `on_design_approved` Then that story BLOCKED with the DoR reason and the other story READY | `tests/orchestrator/test_feature_flow.py::test_design_approved_blocks_story_failing_definition_of_ready` |
| 12 | Given `on_design_approved` already handled When handled again Then no extra transitions and no extra `git branch` subprocess | `tests/orchestrator/test_feature_flow.py::test_design_approved_flow_idempotent` |
| 13 | Given two registrations for the same key When `register` Then `ConfigError`; given an unregistered key When `handle` Then no-op | `tests/orchestrator/test_completion.py::test_completion_handler_dispatch_and_duplicates` |
| 14 | Given an entry raising When `handle` Then counter `completion.error`, exception re-raised, item state unchanged by the handler | `tests/orchestrator/test_completion.py::test_completion_handler_error_does_not_roll_back_transition` |
| 15 | Given no daemon When `walk feature add "Double jump" --description x` Then exit 0, prints `FEAT-0001 (LOCAL-1) IDEA` | `tests/cli/test_cmd_feature.py::test_feature_add_offline_creates_feature` |
| 16 | Given no daemon When `walk feature add X --execute` Then exit 3 | `tests/cli/test_cmd_feature.py::test_feature_add_execute_requires_daemon` |
| 17 | Given a fake running daemon (command consumer in-process) When `walk feature add X --execute --json` Then a `feature.add` command row with `execute=true` is consumed and the JSON result has `feature_id` | `tests/cli/test_cmd_feature.py::test_feature_add_execute_via_command_consumer` |
| 18 | Given a STORY under a feature with a branch When `fire(ON_TASK_START)` Then `ensure_branch(story/STORY-…, base=feat/FEAT-…)` | `tests/hooks/test_builtins.py::test_task_start_branch_uses_per_kind_base` |

#### Evidence required
- Quality gate output.
- Demo on a bootstrapped temp repo: `walk feature add "Double jump" --description "Player can jump twice"` → `FEAT-0001 (LOCAL-1) IDEA`; `walk work show FEAT-0001`; `cat .ai/features/FEAT-0001.md` (14 sections); after `walk run --once` ×3 with fake adapters configured by the test fixture: `walk work list --kind STORY` shows two READY stories and `git branch --list 'feat/*' 'story/*'` lists the feature branch.

#### Notes
- §131, INTERFACES §1.1 `submit_feature`, §3.1, §3.2 (`ready`), §4; ARCHITECTURE §3.2 step 6–7; ADR-0005 (provider row for user features); EPIC-03 header "Branch model".
- `NEW NAME:` `walk.workflow.branches` (`slugify`, `branch_name_for`, `base_branch_for`, `BRANCH_PREFIXES`); `WorkflowRepository.set_branch`; `RunCompletionHandler`, `CompletionContext` (the single post-apply path later stories E03-S13/S14/S15/S17 and E11 register on); `FeatureFlow`, `USER_FEATURE_LABEL`, `FEATURE_CONTEXT_SKELETON_SECTIONS`; IPC command kind `feature.add`; guard payload key `user_feature` (WBS §3.4 has no row for `has_gdd_refs_or_user_feature`; if E01-S10 implemented the guard on `feature.labels` instead, keep the label and drop the key — say so in the commit body).
- Also read: E01-S29/S30 are not yet written; `orchestrator/service.py`, `orchestrator/commands.py`, `cli/composition.py` are the assumed file names (WBS §3.7). If E01-S29 already has a run-completion callback, `RunCompletionHandler.handle` is called from it rather than adding a second path.
- Pitfall: stories created by PLAN have no `branch`; never compute the base branch at story creation time (the feature branch does not exist until `design_approved`).
- Commit subject: `feat: add feature plan and design flow with feature add cli (E03-S09)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S10 — `UnityBatchProvider` and `com.walk.ci` editor package

**Status:** TODO
**Type:** feat
**Requirements:** §26, §62, §129, §137 (Invariant 9)
**Depends on:** E01-S23, E02-S02
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel can compile, run EditMode/PlayMode tests and build a Unity project in batchmode through the small editor package `com.walk.ci` (ADR-0009 D-6), parsing a JSON result file per job into `JobResult`; the package is shipped with the kernel, installed into `Packages/com.walk.ci/` by bootstrap, and a deterministic `FakeUnityProvider` exists for every later test.

#### Scope
- In: `UnityBatchProvider.detect/compile/run_tests/build`; result-file schema and parser; `com.walk.ci` C# package (`WalK.CI.Compile`, `RunTests`, `Build`, `ValidateAssets` stub); packaging of the package as kernel data; `install_ci_package` + bootstrap call; preflight `unity` component uses `detect`; `FakeUnityProvider`.
- Out: job orchestration, ledger `BUILD_RESULT`/`TEST_RESULT` and evidence (E03-S11 — this provider writes no ledger events); asset validation logic (E08-S06; here `ValidateAssets` writes a `not_implemented` result and `validate_assets` raises `NotSupported`); Unity MCP (Stage 8).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/unity/__init__.py` | create | `UnityBatchProvider`, `UnityResultFile`, `install_ci_package`, `ci_package_source` |
| `src/walk/integrations/unity/provider.py` | create | `UnityBatchProvider`, `UNITY_METHODS` |
| `src/walk/integrations/unity/results.py` | create | `UnityResultFile`, `UnityTestCase`, `parse_result_file`, `RESULT_SCHEMA_VERSION` |
| `src/walk/integrations/unity/install.py` | create | `install_ci_package`, `ci_package_source`, `CI_PACKAGE_NAME` |
| `src/walk/integrations/errors.py` | modify | `UnityNotFound(ConfigError)`, `UnityJobFailed(TransientError)` |
| `src/walk/integrations/preflight.py` | modify | — (`detect_unity` delegates the project checks to `UnityBatchProvider.detect`) |
| `src/walk/integrations/bootstrap.py` | modify | `BootstrapResult.ci_package_version` (`Bootstrapper` calls `install_ci_package` when a Unity project is detected) |
| `src/walk/cli/cmd_bootstrap.py` | modify | — (prints `com.walk.ci: installed <version>` / `skipped (no unity project)`) |
| `pyproject.toml` | modify | — (hatch `force-include`: `unity/com.walk.ci` → `walk/_data/com.walk.ci`) |
| `unity/com.walk.ci/package.json` | create | — (`name: com.walk.ci`, `version: 1.0.0`, `unity: 2022.3`) |
| `unity/com.walk.ci/Editor/com.walk.ci.Editor.asmdef` | create | — (Editor-only, references `UnityEditor.TestRunner`, `UnityEngine.TestRunner`) |
| `unity/com.walk.ci/Editor/WalkCI.cs` | create | `WalK.CI` static class: `Compile`, `RunTests`, `Build`, `ValidateAssets` |
| `unity/com.walk.ci/README.md` | create | — (argument and result-file contract) |
| `tests/fakes/fake_unity_provider.py` | create | `FakeUnityProvider`, `FakeUnityJob` |
| `tests/integrations/unity/__init__.py` | create | — |
| `tests/integrations/unity/test_provider.py` | create | — |
| `tests/integrations/unity/test_results.py` | create | — |
| `tests/integrations/unity/test_install.py` | create | — |
| `tests/integrations/unity/fixtures/*.json` | create | recorded result files (compile ok/error, editmode pass/fail, build ok) |
| `tests/fakes/test_fake_unity_provider.py` | create | — |

#### Interface contract
`UnityProvider` and `JobResult` per `INTERFACES.md` §2.4 (unchanged). Additions:

```python
# results.py
RESULT_SCHEMA_VERSION = "1"
class UnityTestCase(FrozenModel):
    name: str
    outcome: Literal["Passed", "Failed", "Skipped", "Inconclusive"]
    duration_s: float
    message: str = ""
class UnityResultFile(FrozenModel):
    """JSON written by WalK.CI to the path given by -walkResult."""
    schema_version: str
    job: Literal["compile", "editmode_tests", "playmode_tests", "build", "asset_validation"]
    ok: bool
    summary: str
    errors: list[str] = []
    tests: list[UnityTestCase] = []
    artifacts: list[str] = []          # paths relative to the project root
    metrics: JsonDict = {}             # e.g. {"passed": 12, "failed": 0, "build_size_bytes": 123}
def parse_result_file(path: Path) -> UnityResultFile: ...   # missing / invalid / schema_version mismatch → OutputInvalid

# provider.py
UNITY_METHODS = {"compile": "WalK.CI.Compile", "tests": "WalK.CI.RunTests", "build": "WalK.CI.Build", "asset_validation": "WalK.CI.ValidateAssets"}
class UnityBatchProvider:
    def __init__(self, runner: SubprocessRunner, clock: Clock, *, unity_path: Path | None, results_dir: Path, timeout_s: int = 3600) -> None: ...
    def command_for(self, project_path: str, method: str, result_path: Path, log_path: Path, extra: list[str]) -> list[str]: ...
    # UnityProvider methods per INTERFACES §2.4

# install.py
CI_PACKAGE_NAME = "com.walk.ci"
def ci_package_source() -> Path: ...                         # importlib.resources path of walk/_data/com.walk.ci (repo checkout: <repo>/unity/com.walk.ci)
def install_ci_package(project_path: Path) -> str: ...      # copies into Packages/com.walk.ci/ when absent or older; returns installed version

# tests/fakes/fake_unity_provider.py
class FakeUnityJob(WalkModel):
    ok: bool = True
    summary: str = "ok"
    tests_passed: int = 3
    tests_failed: int = 0
class FakeUnityProvider:
    def __init__(self, clock: Clock, log_dir: Path, *, jobs: dict[str, FakeUnityJob] | None = None, status: ReadinessState = ReadinessState.READY) -> None: ...
    calls: list[tuple[str, str, JsonDict]]                   # (method, project_path, args) assertion helper
    def script(self, job_kind: str, job: FakeUnityJob, *, times: int | None = None) -> None: ...   # override next `times` calls (None = always)
```

Command line (`command_for`): `<unity_path> -batchmode -nographics -projectPath <project> -executeMethod <method> -logFile <log_path> -walkResult <result_path> [extra]`; `run_tests` adds `-walkTestMode EditMode|PlayMode` and optional `-walkTestFilter <filter>`; `build` adds `-walkBuildTarget <BuildTarget value> -walkOutput <output_path> [-walkDevelopment]`. `-quit` is never passed: `WalK.CI` calls `EditorApplication.Exit(code)` itself after writing the result (test runs are asynchronous).

#### Behavior
1. `detect(project_path)`: `unity_path` None or not a file → `ComponentStatus(state=MISSING, detail="unity editor not found")`; `ProjectSettings/ProjectVersion.txt` absent → `MISCONFIGURED("not a unity project")`; `Packages/com.walk.ci/package.json` absent → `MISCONFIGURED("com.walk.ci not installed")`; else `READY` with `version` parsed from `ProjectVersion.txt` (`m_EditorVersion`).
2. Every job: result path `<results_dir>/<job>-<ulid>.json`, log path `<results_dir>/<job>-<ulid>.log`; runs `SubprocessRunner.run(argv, cwd=project_path, timeout_s=timeout_s)`; then `parse_result_file`. Returns `JobResult(ok=result.ok and exit_code == 0, job_kind, duration_s from SubprocessResult.duration_ms, log_path, artifact_paths, summary, metrics)`.
3. Exit code ≠ 0 with a valid result file → `JobResult(ok=False)` (a failing test run is a result, not an exception). Exit code ≠ 0 and missing/invalid result file → `UnityJobFailed` (`TransientError`) with the last 20 log lines; subprocess `Timeout` propagates unchanged.
4. `unity_path` None → every job raises `UnityNotFound` before spawning anything.
5. `run_tests(mode="PlayMode")` → `job_kind="playmode_tests"`; `EditMode` → `"editmode_tests"`; `metrics` contains `passed`, `failed`, `skipped` counts computed from `tests` (the file's own metrics are overridden by the computed ones when they disagree, with a log warning).
6. `build(target, output_path, development=True)` → `artifact_paths` = result `artifacts` resolved against `project_path` (absolute); a successful build with no artifact → `ok=False`, summary `"build produced no artifact"`.
7. `validate_assets` raises `NotSupported("asset validation arrives in E08-S06")`.
8. `UnityBatchProvider` performs no ledger writes and no evidence records (E03-S11 is the write point); it never runs git and never writes outside `results_dir` and the given `output_path`.
9. `install_ci_package(project_path)`: copies the package tree to `Packages/com.walk.ci/` when missing or when the installed `package.json` version is lower than the shipped one; never overwrites a higher version (logs and returns the installed version); does not touch `Packages/manifest.json` (local packages under `Packages/` are auto-discovered by Unity). Idempotent.
10. `walk bootstrap` calls `install_ci_package` only when `ProjectSettings/ProjectVersion.txt` exists; non-Unity repos print `com.walk.ci: skipped (no unity project)`.
11. `WalkCI.cs`: reads `-walkResult` (required; absent → exit 2 without writing), compiles via `AssetDatabase.Refresh` + `CompilationPipeline` errors, runs tests via `TestRunnerApi` with a callback collector, builds via `BuildPipeline.BuildPlayer`; always writes a `UnityResultFile` JSON with `schema_version "1"` then `EditorApplication.Exit(ok ? 0 : 1)`; exceptions are caught and written as `ok=false, errors=[message]`.
12. `FakeUnityProvider` implements `UnityProvider` with no subprocess: writes a one-line log file per call under `log_dir`, returns deterministic `JobResult`s from the scripted `FakeUnityJob` per job kind (`compile`, `editmode_tests`, `playmode_tests`, `build`), records `calls`, uses the injected `Clock` for `duration_s = 0.0`; `build` returns one artifact path `<log_dir>/build/<target>/game.bin` (created).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given no unity path / no ProjectVersion / no package / all present When `detect` Then MISSING / MISCONFIGURED / MISCONFIGURED / READY with editor version | `tests/integrations/unity/test_provider.py::test_detect_states` |
| 2 | Given a fake runner returning exit 0 and fixture `compile_ok.json` When `compile` Then `JobResult(ok=True, job_kind="compile")` and argv contains `-executeMethod WalK.CI.Compile`, `-walkResult`, no `-quit` | `tests/integrations/unity/test_provider.py::test_compile_builds_command_and_parses_result` |
| 3 | Given exit 1 and fixture `editmode_fail.json` When `run_tests("EditMode")` Then `ok=False`, `job_kind="editmode_tests"`, `metrics.failed == 1`, no exception | `tests/integrations/unity/test_provider.py::test_failing_tests_return_result_not_exception` |
| 4 | Given exit 1 and no result file When `compile` Then `UnityJobFailed` whose message has the log tail | `tests/integrations/unity/test_provider.py::test_missing_result_file_raises_unity_job_failed` |
| 5 | Given `unity_path=None` When any job Then `UnityNotFound` and the runner was not called | `tests/integrations/unity/test_provider.py::test_no_unity_path_raises_before_spawn` |
| 6 | Given `PlayMode` with filter When `run_tests` Then argv has `-walkTestMode PlayMode -walkTestFilter <f>` and `job_kind="playmode_tests"` | `tests/integrations/unity/test_provider.py::test_playmode_arguments_and_kind` |
| 7 | Given fixture `build_ok.json` When `build(STANDALONE_WIN64, out)` Then argv has `-walkBuildTarget StandaloneWindows64 -walkOutput out -walkDevelopment` and absolute `artifact_paths` | `tests/integrations/unity/test_provider.py::test_build_arguments_and_artifacts` |
| 8 | Given a build result with `ok=true` and no artifacts When `build` Then `ok=False` with summary `build produced no artifact` | `tests/integrations/unity/test_provider.py::test_build_without_artifact_is_failure` |
| 9 | When `validate_assets` Then `NotSupported` | `tests/integrations/unity/test_provider.py::test_validate_assets_not_supported` |
| 10 | Given result files missing a field / wrong `schema_version` When `parse_result_file` Then `OutputInvalid` naming the field | `tests/integrations/unity/test_results.py::test_parse_result_file_rejects_invalid` |
| 11 | Given file metrics disagreeing with the test list When parsed through the provider Then computed counts win | `tests/integrations/unity/test_results.py::test_test_counts_computed_from_cases` |
| 12 | Given an empty Unity project When `install_ci_package` twice Then `Packages/com.walk.ci/package.json` version `1.0.0` and the second call copies nothing | `tests/integrations/unity/test_install.py::test_install_ci_package_idempotent` |
| 13 | Given an installed higher version When `install_ci_package` Then files untouched and the higher version returned | `tests/integrations/unity/test_install.py::test_install_never_downgrades` |
| 14 | Given `ci_package_source()` Then it contains `package.json`, `Editor/WalkCI.cs` defining `Compile`, `RunTests`, `Build`, `ValidateAssets` and the asmdef is Editor-only | `tests/integrations/unity/test_install.py::test_ci_package_layout` |
| 15 | Given a repo without `ProjectSettings/ProjectVersion.txt` When `walk bootstrap --yes` Then output contains `com.walk.ci: skipped` and no `Packages/` dir is created | `tests/integrations/unity/test_install.py::test_bootstrap_skips_non_unity_repo` |
| 16 | Given `FakeUnityProvider` scripted `editmode_tests` failing once When called twice Then first `ok=False`, second `ok=True`, `calls` has two entries, log files exist | `tests/fakes/test_fake_unity_provider.py::test_fake_unity_provider_scripting` |

#### Evidence required
- Quality gate output.
- Demo (manual, owner machine with Unity installed; recorded in Evidence, not in CI): `walk bootstrap --unity-path "<Unity.exe>" --yes` on a sample Unity project → `com.walk.ci: installed 1.0.0`; `walk doctor` shows `unity: READY (<editor version>)`; one `WalK.CI.Compile` result JSON pasted. Without Unity: `walk doctor` → `unity: MISSING`.

#### Notes
- ADR-0009 D-6 and consequence (`unity/com.walk.ci/` in the kernel repo), INTERFACES §2.4, ARCHITECTURE §4.3 (`UnityBatchProvider`/`CiProvider` write point — this story leaves the ledger to `LocalCiProvider`, E03-S11, to avoid duplicate `BUILD_RESULT`).
- `NEW NAME:` `UnityResultFile`, `UnityTestCase`, `parse_result_file`, `RESULT_SCHEMA_VERSION`, `UNITY_METHODS`, `UnityBatchProvider.command_for`, `install_ci_package`, `ci_package_source`, `CI_PACKAGE_NAME`, `UnityNotFound`, `UnityJobFailed`, `FakeUnityJob`, Unity CLI arguments `-walkResult/-walkTestMode/-walkTestFilter/-walkBuildTarget/-walkOutput/-walkDevelopment`, kernel data path `walk/_data/com.walk.ci`, `BootstrapResult.ci_package_version` (WBS §6 row "com.walk.ci lives at unity/com.walk.ci/").
- `detect_unity` (E02-S02) keeps detecting the editor binary; the project/package checks move into `UnityBatchProvider.detect` so preflight and the provider never disagree.
- Pitfall: Unity on Windows holds the project lock (`Temp/UnityLockfile`); two jobs on the same project path must never run concurrently — `LocalCiProvider` (E03-S11) serialises jobs per project path; this provider documents but does not enforce it.
- Pitfall: never pass `-quit` together with `-executeMethod` for test runs; the editor would exit before `TestRunnerApi` callbacks fire.
- Commit subject: `feat: add unity batch provider and com.walk.ci package (E03-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S11 — `LocalCiProvider.run_pipeline`, build/test hooks and evidence

**Status:** TODO
**Type:** feat
**Requirements:** §6.6, §62, §81, §86, §90, §137 (Invariant 9)
**Depends on:** E03-S10, E01-S06
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`LocalCiProvider` runs a configured list of §62 jobs for one commit — Unity jobs through `UnityProvider`, other jobs as shell commands from `.ai/project/ci.yaml` — idempotently per job, fires the build/test hooks, writes `BUILD_RESULT`/`TEST_RESULT` ledger events and records every job result as evidence, so CI is a deterministic kernel step rather than an agent.

#### Scope
- In: `LocalCiProvider` (`CiProvider` implementation); `CiConfig` + loader for `.ai/project/ci.yaml` with kernel default; job-name → `JobResult.job_kind` mapping incl. `build:<BuildTarget>`; per-job idempotency (`ci.job:` keys); `ON_BUILD_START/SUCCESS/FAILURE`, `ON_TEST_RESULT` firing; evidence + ledger; MUST-hook attachments for the build/test hooks; per-project-path job serialisation.
- Out: deciding `integration_passed`/`ci_failed` (E03-S12 story level, E03-S17 feature level); CI/compute cost records (E09-S03); RC builds for all targets (E11-S03); remote CI services (not planned for MVP).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/ci.py` | create | `LocalCiProvider`, `CiConfig`, `CiJobSpec`, `load_ci_config`, `job_kind_for`, `CI_CONFIG_PATH` |
| `src/walk/integrations/defaults/ci.yaml` | create | — (kernel default config, copied by bootstrap) |
| `src/walk/integrations/bootstrap.py` | modify | — (writes `.ai/project/ci.yaml` from the default when absent) |
| `src/walk/integrations/protocols.py` | modify | — (`CiProvider.run_pipeline` gains keyword-only `work_item_id: WorkItemId \| None = None`) |
| `src/walk/integrations/errors.py` | modify | `CiJobUnknown(ConfigError)` |
| `src/walk/integrations/__init__.py` | modify | re-export `LocalCiProvider`, `CiConfig`, `load_ci_config` |
| `src/walk/hooks/builtins.py` | modify | hooks `builtin.build_evidence_recorded` (ON_BUILD_SUCCESS, ON_BUILD_FAILURE), `builtin.test_evidence_recorded` (ON_TEST_RESULT) |
| `src/walk/cli/composition.py` | modify | — (constructs `LocalCiProvider` with the real `UnityBatchProvider` or `KernelOverrides.unity`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§2.4 `run_pipeline` signature: `work_item_id` kwarg) |
| `tests/integrations/test_ci.py` | create | — |
| `tests/integrations/test_ci_config.py` | create | — |
| `tests/hooks/test_builtins_ci.py` | create | — |

#### Interface contract
`CiProvider.run_pipeline` per `INTERFACES.md` §2.4 plus one keyword-only argument (documented in INTERFACES in this commit):

```python
async def run_pipeline(self, worktree_path: str, commit: Sha, jobs: list[str], *, idempotency_key: str,
                       work_item_id: WorkItemId | None = None) -> list[JobResult]: ...
```

```python
CI_CONFIG_PATH = ".ai/project/ci.yaml"
class CiJobSpec(FrozenModel):
    runner: Literal["unity", "shell"]
    kind: Literal["compile", "editmode_tests", "playmode_tests", "build", "asset_validation", "static_check", "perf_smoke"]
    command: list[str] = []            # shell only; argv, executed with cwd=worktree_path
    timeout_s: int = 1800
    required: bool = True              # a failing non-required job is reported but does not fail the pipeline verdict
class CiConfig(FrozenModel):
    version: str
    story_jobs: list[str]
    feature_jobs: list[str]
    jobs: dict[str, CiJobSpec]
    def resolve(self, name: str) -> CiJobSpec: ...   # "build:<BuildTarget>" → unity/build spec; unknown → CiJobUnknown
def load_ci_config(repo_root: Path) -> CiConfig: ...  # project file if present else kernel default; invalid → ConfigError
def job_kind_for(name: str, config: CiConfig) -> str: ...

class LocalCiProvider:
    def __init__(self, unity: UnityProvider | None, runner: SubprocessRunner, evidence: EvidenceManager, ledger: LedgerManager,
                 hooks: HookManager, idempotency: IdempotencyStore, clock: Clock, *, repo_root: Path, project_key: ProjectKey,
                 results_dir: Path) -> None: ...
    @staticmethod
    def verdict(results: list[JobResult], config: CiConfig, jobs: list[str]) -> bool: ...   # all required jobs ok
```

Kernel default `ci.yaml`:
```yaml
version: "1.0"
story_jobs: [compile, editmode_tests]
feature_jobs: [compile, editmode_tests, playmode_tests]
jobs:
  compile:        {runner: unity, kind: compile}
  editmode_tests: {runner: unity, kind: editmode_tests}
  playmode_tests: {runner: unity, kind: playmode_tests}
```

Ledger payloads: `BUILD_RESULT {job, job_kind, ok, commit, duration_s, summary, evidence_id, log_path}` for kinds `compile, build, asset_validation, static_check, perf_smoke`; `TEST_RESULT {job, job_kind, ok, commit, passed, failed, skipped, evidence_id}` for `editmode_tests, playmode_tests`. Evidence kinds: tests → `AUTOMATED_TEST`; `build` with artifacts → `BUILD_ARTIFACT` (path = first artifact) plus `LOG`; everything else → `LOG`; `perf_smoke` → `PERFORMANCE_METRICS`.

#### Behavior
1. `run_pipeline` executes `jobs` in the given order, sequentially; jobs of one `worktree_path` are serialised by a per-path `asyncio.Lock` held by the provider instance (Unity project lock, E03-S10 pitfall).
2. Per job: key `f"{idempotency_key}:{job}"` (callers pass `ci.job:{work_item_id}:{head_sha}`, ARCHITECTURE §5.4); when the key exists the stored `JobResult` (JSON in `result_ref`) is returned without running the job, firing hooks or writing ledger/evidence again.
3. Before a job of a build-like kind: `fire(ON_BUILD_START, payload={job, commit, work_item_id})`. The job runs: `runner: unity` → `UnityProvider.compile/run_tests/build` (`build:<target>` → `build(project, BuildTarget(target), output_path=<results_dir>/build/<work_item_id or "adhoc">/<target>/, development=True)`); `runner: shell` → `SubprocessRunner.run(command, cwd=worktree_path, timeout_s)` with `JobResult(ok=exit_code == 0, summary=last stderr/stdout line, log_path=<results_dir>/<job>-<ulid>.log containing stdout+stderr)`.
4. `UnityNotFound`/`UnityJobFailed`/`Timeout` from a job → the job yields `JobResult(ok=False, summary=f"{type}: {message}")` (CI infrastructure failure is a red result, not a crash); `CiJobUnknown` and `ConfigError` propagate before any job runs (the whole `jobs` list is resolved first).
5. After each job, in one `UnitOfWork`: `EvidenceManager.record(EvidenceDraft(kind, path_or_uri, description=f"{job} @ {commit[:7]}", metrics=result.metrics), actor=Actor(KERNEL), work_item_id, commit=commit)`; ledger `BUILD_RESULT` or `TEST_RESULT` (this provider is the ARCHITECTURE §4.3 write point; `UnityBatchProvider` writes nothing); idempotency key stored. Then hooks after commit: build-like → `ON_BUILD_SUCCESS`/`ON_BUILD_FAILURE` with payload `{job, ok, evidence_id, work_item_id, commit}`; tests → `ON_TEST_RESULT` with the same keys.
6. A failing job does not stop the pipeline when `required: false`; a failing required job stops the remaining jobs (fail-fast) — skipped jobs are absent from the returned list. `verdict` is `True` iff every required job in `jobs` is present and `ok`.
7. `builtin.build_evidence_recorded` / `builtin.test_evidence_recorded` (required, priority 20, FAIL_CLOSED): assert `ctx.payload["evidence_id"]` exists via `EvidenceManager.get`; they write nothing (WBS §3.5 — the ledger and evidence come from the write point). `ci_failed` is **not** raised by these hooks; the integration step decides (E03-S12/S17).
8. `load_ci_config`: unknown job names referenced in `story_jobs`/`feature_jobs` → `ConfigError`; `runner: shell` without `command` → `ConfigError`; `build:<X>` with `X` not a `BuildTarget` value → `CiJobUnknown`.
9. `unity is None` and a `runner: unity` job requested → that job's result is `ok=False, summary="unity provider not configured"` (rule 4).
10. Bootstrap writes `.ai/project/ci.yaml` from the default only when absent (never overwrites).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `FakeUnityProvider` all green When `run_pipeline(jobs=["compile","editmode_tests"])` Then two results, one `BUILD_RESULT` and one `TEST_RESULT` ledger event, evidence kinds `LOG` and `AUTOMATED_TEST`, hooks `ON_BUILD_START`, `ON_BUILD_SUCCESS`, `ON_TEST_RESULT` fired once each in order | `tests/integrations/test_ci.py::test_pipeline_runs_jobs_records_evidence_and_ledger` |
| 2 | Given the pipeline already ran for key K When `run_pipeline` with K again Then the same results, no new ledger/evidence rows, `FakeUnityProvider.calls` unchanged | `tests/integrations/test_ci.py::test_pipeline_idempotent_per_job_key` |
| 3 | Given `compile` failing When `run_pipeline(["compile","editmode_tests"])` Then one result `ok=False`, `ON_BUILD_FAILURE` fired, `editmode_tests` not run, `verdict` False | `tests/integrations/test_ci.py::test_required_job_failure_is_fail_fast` |
| 4 | Given a non-required `lint` shell job failing When run with `compile` after it Then both results present and `verdict` True | `tests/integrations/test_ci.py::test_non_required_job_failure_does_not_fail_verdict` |
| 5 | Given a shell job When run Then `SubprocessRunner` called with `cwd=worktree_path` and the log file contains stdout and stderr | `tests/integrations/test_ci.py::test_shell_job_runs_in_worktree_and_logs` |
| 6 | Given `UnityProvider` raising `UnityNotFound` When `compile` runs Then result `ok=False` with summary prefix `UnityNotFound` and no exception | `tests/integrations/test_ci.py::test_infrastructure_failure_becomes_red_result` |
| 7 | Given job `build:StandaloneWindows64` When run Then `UnityProvider.build` called with that target and evidence `BUILD_ARTIFACT` recorded | `tests/integrations/test_ci.py::test_build_target_job_name_resolves` |
| 8 | Given jobs `["compile","nope"]` When `run_pipeline` Then `CiJobUnknown` and no job ran | `tests/integrations/test_ci.py::test_unknown_job_rejected_before_running` |
| 9 | Given two concurrent `run_pipeline` calls on the same worktree When awaited Then job executions never overlap | `tests/integrations/test_ci.py::test_jobs_serialised_per_worktree` |
| 10 | Given no project `ci.yaml` When `load_ci_config` Then kernel default; given a project file Then it wins | `tests/integrations/test_ci_config.py::test_load_ci_config_project_overrides_default` |
| 11 | Given `story_jobs` naming an undefined job / a shell job without command When loaded Then `ConfigError` | `tests/integrations/test_ci_config.py::test_ci_config_validation_errors` |
| 12 | Given `ON_TEST_RESULT` payload with an unknown `evidence_id` When fired Then `HookFailed`; with a recorded id Then ok and no ledger write besides `HOOK_EXECUTED` | `tests/hooks/test_builtins_ci.py::test_ci_hooks_assert_evidence_without_writing` |

#### Evidence required
- Quality gate output.
- Demo on the E02 gate fixture repo with `FakeUnityProvider` wired via `KernelOverrides` (script in the test): `walk ledger query --kind BUILD_RESULT --kind TEST_RESULT --json` shows both events with `evidence_id`; `cat .ai/project/ci.yaml` shows the default.

#### Notes
- §62 ("CI does not need to be an LLM agent"), INTERFACES §2.4 docstring (hooks + evidence), ARCHITECTURE §4.1 (`ON_BUILD_*`, `ON_TEST_RESULT` rows), §4.3, §5.4 (`ci.job:` key); WBS §3.5; E02-S08 deferral table (`ON_BUILD_*`/`ON_TEST_RESULT → evidence` assigned here).
- `NEW NAME:` `LocalCiProvider`, `.ai/project/ci.yaml`, `CiConfig`, `CiJobSpec`, `load_ci_config`, `job_kind_for`, `CI_CONFIG_PATH`, `CiJobUnknown`, job-name form `build:<BuildTarget>` (relied on by E11-S03), builtin hook ids `builtin.build_evidence_recorded`, `builtin.test_evidence_recorded`, `run_pipeline(..., work_item_id=)` kwarg (INTERFACES change made in this commit).
- Pitfall: the per-job key includes the job **name**, not the kind, so `build:Android` and `build:iOS` on the same commit are distinct.
- Commit subject: `feat: add local ci provider with build and test evidence (E03-S11)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S12 — Story integration step: squash, push, PR, CI, `integration_passed`/`ci_failed`

**Status:** TODO
**Type:** feat
**Requirements:** §6.4, §59, §60, §62, §90, §92, §131, §137 (Invariants 4, 9)
**Depends on:** E03-S11, E03-S01, E01-S29
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A STORY/TASK/BUG that reaches `INTEGRATION` (after Lead Dev approval) is integrated by a non-agent kernel step: WIP commits squashed into one commit, branch pushed, PR opened against the parent feature branch, story CI jobs run on the squashed head, and on green the PR is merged into the feature branch and `integration_passed` is raised — on red or merge conflict `ci_failed` sends the item to `REWORK` with the failure written to the work provider and the feature context.

#### Scope
- In: `IntegrationStep` (start, run, recovery-safe re-run, protected-base path); scheduler admission of `INTEGRATION` items for STORY/TASK/BUG as kernel steps; `GitProvider.merge_base`; squash commit message; failure feedback (provider comment + `Implementation Notes` append); integration worktree lifecycle.
- Out: feature-level integration on the feature branch and the feature → default-branch merge (E03-S17); the review that leads to `INTEGRATION` (E03-S13); QC after `integration_passed` (E03-S14); `ON_PR_OPENED`/`ON_MERGED` relevant-files refresh (E04-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/integration.py` | create | `IntegrationStep`, `IntegrationOutcome`, `IntegrationResult`, `squash_message` |
| `src/walk/orchestrator/scheduler.py` | modify | — (tick: `INTEGRATION` items of kinds STORY/TASK/BUG → `IntegrationStep.start`; then `IntegrationStep.complete_protected_merges()`) |
| `src/walk/orchestrator/service.py` | modify | — (owns step tasks; `stop(drain)` awaits or cancels them; `status().active_runs` unaffected) |
| `src/walk/integrations/protocols.py` | modify | `GitProvider.merge_base` |
| `src/walk/integrations/git/provider.py` | modify | `GitCliProvider.merge_base` |
| `tests/fakes/fake_git_provider.py` | modify | `FakeGitProvider.merge_base` |
| `src/walk/cli/composition.py` | modify | — (constructs `IntegrationStep`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§2.3 `merge_base`) |
| `tests/orchestrator/test_integration_step.py` | create | — |
| `tests/integrations/git/test_provider_remote.py` | modify | — |

#### Interface contract
Transitions `INTEGRATION → integration_passed (ci_green) → QC` and `INTEGRATION → ci_failed → REWORK` per `INTERFACES.md` §3.2/§3.3 (allowed role KERNEL); idempotency keys per ARCHITECTURE §5.4 (`git.pr:`, `git.merge:`, `ci.job:`, `work.comment:`). Additions:

```python
# src/walk/integrations/protocols.py (GitProvider)
async def merge_base(self, a: str, b: str, path: str) -> Sha:
    """`git merge-base a b`; refs or shas; no common ancestor → GitError."""

# src/walk/orchestrator/integration.py
class IntegrationOutcome(StrEnum):
    PASSED = "PASSED"                      # CI green, merged (or merge pending approval on a protected base)
    CI_FAILED = "CI_FAILED"
    MERGE_CONFLICT = "MERGE_CONFLICT"

class IntegrationResult(FrozenModel):
    work_item_id: WorkItemId
    outcome: IntegrationOutcome
    head: Sha                              # squashed head of the item branch
    base_branch: str
    pr: PullRequestRef | None
    merged_sha: Sha | None
    job_results: list[JobResult]
    pending_approval_id: ApprovalRequestId | None
    reason: str | None

def squash_message(item: WorkItem) -> str: ...      # f"{item.kind.lower()}({item.id}): {item.title[:60]}"

class IntegrationStep:
    def __init__(self, workflow: WorkflowManager, repo: WorkflowRepository, integrations: IntegrationManager, git: GitProvider,
                 ci: CiProvider, ci_config: CiConfig, memory: MemoryManager, permissions: PermissionManager,
                 telemetry: TelemetryManager, project: Project, clock: Clock, *, worktrees_root: Path) -> None: ...
    def start(self, item: WorkItem) -> bool: ...                       # schedules run(item) as a task; False when already in flight for (item.id, state_version)
    async def run(self, item: WorkItem) -> IntegrationResult: ...      # the step itself (tests call it directly)
    async def complete_protected_merges(self) -> int: ...              # merges PRs whose PROTECTED_ACTION approval is APPROVED; returns count
    def in_flight(self) -> list[WorkItemId]: ...
```

#### Behavior
1. Admission: each tick, after agent admission, the scheduler lists items in `INTEGRATION` of kinds STORY/TASK/BUG and calls `start(item)`; in-flight dedupe is in-memory by `(item.id, state_version)`; integration steps do not count against `max_parallel_agents`. Steps targeting the same base branch run one at a time (per-base `asyncio.Lock`) so merges into a feature branch are serialised.
2. `run(item)`: base branch = `base_branch_for(item, parent_feature, project.default_branch)` (E03-S09); worktree `<worktrees_root>/int-<item.id>` via `git.add_worktree(path, item.branch)` (a leftover worktree from a crashed step is removed first with `force=True`); always removed in `finally`.
3. Squash: `fork = merge_base(base_branch, item.branch, path)`; `head = squash_wip(path, item.branch, fork, squash_message(item))` (one commit per item, trailer `Walk-Work-Item` kept, E03-S01 rule 7).
4. `push(path, item.branch, protected_branches=project.protected_branches)`; `pr = open_pr(item.branch, base_branch, title=squash_message(item), body=<goal + acceptance criteria bullets + "Evidence: <ids>">, idempotency_key=f"git.pr:{item.id}:{head}")`.
5. CI: `ci.run_pipeline(path, head, ci_config.story_jobs, idempotency_key=f"ci.job:{item.id}:{head}", work_item_id=item.id)`; green = `LocalCiProvider.verdict(results, ci_config, story_jobs)`.
6. Green and base not protected: `merged = git.merge(pr, strategy="squash", idempotency_key=f"git.merge:{item.id}:{pr.url or pr.head}")`; then `raise_event(item.id, "integration_passed", TransitionContext(actor_role=KERNEL, source=KERNEL, payload={"ci_green": True, "evidence_kinds_present": [...], "pr_url", "merged_sha": merged, "expected_state_version": item.state_version}))` → `QC` (hook `ON_READY_FOR_QC`, E03-S07).
7. Green and base protected (`fnmatch` against `project.protected_branches`; only a BUG without `related_feature_id` in MVP): no merge; `PermissionManager.request_approval(kind="PROTECTED_ACTION", approver=USER, requested_by_role=KERNEL, run_id=None, work_item_id=item.id, payload={"action": "git.merge_protected", "pr": pr.model_dump(), "head": head})` (idempotent per `(item, head)`); `integration_passed` is raised with `merged_sha=None` (QC tests the PR head). `complete_protected_merges()` merges every APPROVED request once (`git.merge` key as in rule 6), DENIED/EXPIRED requests are left with a counter `integration.merge_denied` and a provider comment.
8. Red: `ci_failed` with payload `{"ci_green": False, "failed_jobs": [...], "evidence_id": <first failed job evidence>, "expected_state_version"}` → `REWORK` (hook `ON_BUILD_FAILURE`); `work.comment(item, "CI failed on <head[:7]>: <job>: <summary>", idempotency_key=f"work.comment:{item.id}:{ledger_seq}")`; `MemoryManager.apply_updates([ContextUpdate(doc_id=<feature or bug doc>, section="Implementation Notes", operation=APPEND, content_markdown="- CI failed for <ID> at <head[:7]>: <job>: <summary>")], actor=Actor(KERNEL), head, branch=item.branch)` (BUG docs use section `Investigations`).
9. Merge conflict (`GitError`/`ToolCrashed` from `merge`): outcome `MERGE_CONFLICT`, handled as rule 8 with reason `merge_conflict: <stderr tail>`; the PR stays open.
10. Recovery safety: the step records no `schedule:` key; re-running `run` after a crash replays every inner key (`squash_wip` on an already-squashed branch is a no-op, PR/merge/CI keys replay) and the final `raise_event` uses `expected_state_version`, so a duplicate attempt after the event committed raises `GuardRejected("stale state_version")`, which the step treats as already done (logged, no error).
11. Any other exception (e.g. push `ToolCrashed`) leaves the item in `INTEGRATION`, increments `integration.error`, and is retried on the next tick with exponential backoff (1, 2, 4 … 60 ticks max, per item, in memory); after 5 consecutive failures the step raises `ci_failed` with reason `integration_error: <type>`.
12. The step never writes ledger events itself: `COMMIT`/`PR_OPENED`/`MERGED` come from `GitCliProvider`, `BUILD_RESULT`/`TEST_RESULT` from `LocalCiProvider`, `WORK_ITEM_TRANSITION` from the state machine (ARCHITECTURE §4.3).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a story branch with 3 WIP commits off `feat/FEAT-0001-…`, bare `origin`, `FakeUnityProvider` green When `run` Then one squashed commit `story(STORY-0002): …`, branch pushed, PR stub against the feature branch, feature branch contains the change, story in `QC`, outcome `PASSED` | `tests/orchestrator/test_integration_step.py::test_green_pipeline_merges_into_feature_branch_and_passes` |
| 2 | Given the feature branch advanced by another merged story When `run` Then `squash_wip` base is the merge-base and the squashed diff contains only this story's files | `tests/orchestrator/test_integration_step.py::test_squash_uses_merge_base_not_feature_head` |
| 3 | Given `editmode_tests` scripted red When `run` Then story in `REWORK`, `ci_failed` payload lists `editmode_tests`, provider comment `CI failed on …`, feature doc `Implementation Notes` has the appended line, no merge | `tests/orchestrator/test_integration_step.py::test_red_pipeline_raises_ci_failed_with_feedback` |
| 4 | Given two stories touching the same line merged in sequence When the second `run` Then outcome `MERGE_CONFLICT`, item in `REWORK`, reason starts `merge_conflict:` | `tests/orchestrator/test_integration_step.py::test_merge_conflict_becomes_ci_failed` |
| 5 | Given a BUG without `related_feature_id` (base `main`, protected) When `run` green Then no merge, one `PROTECTED_ACTION` approval with action `git.merge_protected`, bug in `QC`; after `decide_approval(APPROVED)` `complete_protected_merges()` returns 1 and `main` contains the fix | `tests/orchestrator/test_integration_step.py::test_protected_base_merge_waits_for_approval` |
| 6 | Given a step that crashed after the merge but before the event When `run` again Then no second PR/merge/CI execution and the story ends in `QC` once | `tests/orchestrator/test_integration_step.py::test_rerun_after_crash_replays_keys` |
| 7 | Given the event already committed When `run` again Then `stale state_version` is swallowed and no extra transition row exists | `tests/orchestrator/test_integration_step.py::test_duplicate_completion_is_noop` |
| 8 | Given two items in `INTEGRATION` for the same feature When one tick starts both Then their merges never overlap and both reach `QC` | `tests/orchestrator/test_integration_step.py::test_steps_serialised_per_base_branch` |
| 9 | Given `push` raising `ToolCrashed` 5 times When ticks proceed Then the item stays `INTEGRATION` for 4 attempts and then `ci_failed` with reason `integration_error: ToolCrashed` | `tests/orchestrator/test_integration_step.py::test_repeated_infrastructure_error_ends_in_ci_failed` |
| 10 | Given a successful run Then ledger has `COMMIT`, `PR_OPENED`, `MERGED`, `BUILD_RESULT`, `TEST_RESULT`, `WORK_ITEM_TRANSITION(INTEGRATION→QC)` and no ledger event with a write point outside ARCHITECTURE §4.3 | `tests/orchestrator/test_integration_step.py::test_ledger_events_only_from_write_points` |
| 11 | Given the integration worktree When `run` returns or raises Then `<worktrees_root>/int-<id>` no longer exists | `tests/orchestrator/test_integration_step.py::test_integration_worktree_always_removed` |
| 12 | Given two branches forked from `main` When `merge_base` Then the fork sha; unrelated histories → `GitError` | `tests/integrations/git/test_provider_remote.py::test_merge_base_returns_fork_point` |

#### Evidence required
- Quality gate output.
- Demo on a temp repo with bare remote (script in the test module, `--repo <tmp>`): `walk work show STORY-0002` lists `INTEGRATION → QC (integration_passed, KERNEL)`; `git log --oneline feat/FEAT-0001-<slug> -3` shows `story(STORY-0002): …`; `cat .walk/prs/story/STORY-0002-<slug>.json` shows `merged_sha`; `walk ledger query --item STORY-0002 --kind PR_OPENED --kind MERGED --kind TEST_RESULT`.

#### Notes
- INTERFACES §3.2 note "Integration for stories = squash WIP, push branch, open PR (kernel), run CI (§62); merge into the feature/integration branch is automatic for non-protected branches; merge to protected base is a protected action"; ADR-0002 D-4; ADR-0006 D-2 (kernel performs merges), §92; ARCHITECTURE §5.4.
- `NEW NAME:` `IntegrationStep`, `IntegrationOutcome`, `IntegrationResult`, `squash_message` (format `<kind>(<ID>): <title>`), `GitProvider.merge_base` (INTERFACES change in this commit), integration worktree path `.walk/worktrees/int-<ID>`, approval payload action `git.merge_protected` with `run_id=None`, counters `integration.error`, `integration.merge_denied`, payload keys `failed_jobs`, `pr_url`, `merged_sha`.
- Also read: E01-S29 is not yet written; `orchestrator/scheduler.py` and `service.py` are the assumed names (WBS §3.7). The tick's agent admission (INTERFACES §5.1) is unchanged; this story appends a kernel-step phase after step 14.
- Pitfall: `ci_failed` from `INTEGRATION` on a BUG has no hook in `bug_workflow` (INTERFACES §3.3) — do not rely on `ON_BUILD_FAILURE` for bugs; the provider comment and context append in rule 8 are done by the step for every kind.
- Commit subject: `feat: add story integration step with squash pr ci and merge (E03-S12)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S13 — Lead Dev review flow

**Status:** TODO
**Type:** feat
**Requirements:** §6.4, §10.6, §23, §61, §63, §126, §137 (Invariant 4)
**Depends on:** E03-S07, E03-S08
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** QC

#### Goal
A STORY/TASK/BUG in `READY_FOR_REVIEW` is admitted by the scheduler as a LEAD_DEV `REVIEW` run: the kernel raises `start_review` with the role/model facts the Invariant 4 guards need, the review run is read-only, and its verdict moves the item to `INTEGRATION` (`review_approved`) or back to `REWORK` (`review_rejected`) with the findings delivered to the work provider and the item's context document — §61 `READY_FOR_REVIEW → LEAD_DEV_REVIEW → INTEGRATION/REWORK` with the cross-model guard.

#### Scope
- In: data-driven admission events (`ADMISSION_EVENTS`) with the `READY_FOR_REVIEW → start_review` rows; `start_review` payload (implementer/reviewer role and model, `cross_model_review` incl. the E03-S07 approved-escalation override); read-only purposes in the output applier; `ReviewFlow` completion entries (findings → provider comment + context append); rework input carries the review findings.
- Out: model selection and the cross-model escalation request (E03-S07); bug-specific admission rows `start_fix` (E03-S15); disagreement between reviewer and implementer escalating to debate (E05-S08); integration after approval (E03-S12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/scheduler.py` | modify | `ADMISSION_EVENTS`, `Scheduler.admission_payload` |
| `src/walk/orchestrator/review_flow.py` | create | `ReviewFlow`, `REVIEW_FINDINGS_SECTION` |
| `src/walk/workflow/tables/scheduled_states.yaml` | modify | — (rows STORY/TASK `LEAD_DEV_REVIEW → contract.reviewer_role/REVIEW`, BUG `LEAD_DEV_REVIEW → LEAD_DEV/REVIEW` for stranded-item recovery) |
| `src/walk/runtime/output_applier.py` | modify | `READ_ONLY_PURPOSES` (module constant); `guard_payload` adds `reviewer_role`, `reviewer_model_id` for REVIEW runs |
| `src/walk/cli/composition.py` | modify | — (registers `ReviewFlow` on the `RunCompletionHandler`) |
| `tests/orchestrator/test_admission.py` | create | — |
| `tests/orchestrator/test_review_flow.py` | create | — |
| `tests/runtime/test_output_applier_review.py` | create | — |

#### Interface contract
Transitions `READY_FOR_REVIEW → start_review → LEAD_DEV_REVIEW`, `LEAD_DEV_REVIEW → review_approved → INTEGRATION`, `→ review_rejected → REWORK` per `INTERFACES.md` §3.2/§3.3; routing rows STORY/TASK `READY_FOR_REVIEW → contract.reviewer_role/REVIEW`, BUG `READY_FOR_REVIEW → LEAD_DEV/REVIEW` (§4); guard payload keys per WBS §3.4. Additions:

```python
# src/walk/orchestrator/scheduler.py
ADMISSION_EVENTS: dict[tuple[WorkItemKind, WorkItemState], str] = {
    (STORY, READY): "start_implementation", (STORY, REWORK): "start_implementation",
    (TASK, READY): "start_implementation",  (TASK, REWORK): "start_implementation",
    (STORY, READY_FOR_REVIEW): "start_review", (TASK, READY_FOR_REVIEW): "start_review",
    (BUG, READY_FOR_REVIEW): "start_review",
}   # E03-S15 adds (BUG, READY|REWORK) → "start_fix"; FEATURE rows have no admission event (the run's output raises the event)

class Scheduler:
    def admission_payload(self, item: WorkItem, route: RouteDecision, routing: RoutingDecision, *, cross_model_override: bool) -> JsonDict:
        """start_review: {implementer_role, reviewer_role, implementer_model_id, reviewer_model_id, cross_model_review, expected_state_version};
        start_implementation/start_fix: {budget_ok, branch_available, expected_state_version} (E01-S29 keys, unchanged)."""

# src/walk/orchestrator/review_flow.py
REVIEW_FINDINGS_SECTION = "Implementation Notes"          # BUG documents use "Investigations"
class ReviewFlow:
    def __init__(self, workflow: WorkflowManager, integrations: IntegrationManager, memory: MemoryManager, git: GitProvider,
                 telemetry: TelemetryManager, orchestrator_wake: Callable[[], Awaitable[None]]) -> None: ...
    async def on_review_rejected(self, ctx: CompletionContext) -> None: ...
    async def on_review_approved(self, ctx: CompletionContext) -> None: ...
    def register(self, handler: RunCompletionHandler) -> None: ...   # (STORY|TASK|BUG, "REVIEW", review_rejected|review_approved)

# src/walk/runtime/output_applier.py
READ_ONLY_PURPOSES: frozenset[str] = frozenset({"REVIEW", "QC", "TRIAGE", "PLAN"})
```

#### Behavior
1. Admission (INTERFACES §5.1 steps 5–13, extended): when `ADMISSION_EVENTS` has a row for `(item.kind, item.state)`, the scheduler — after `ModelRouter.select` and `Scheduler.check_cross_model` (E03-S07) succeed and before `AgentExecutor.start` — raises that event with `TransitionContext(actor_role=KERNEL, source=KERNEL, run_id=None, payload=admission_payload(...))`; the run is then started on the resulting state (`LEAD_DEV_REVIEW` for reviews). `GuardRejected`/`PermissionDenied` from the admission event → no run, counter `scheduler.admission_rejected`, the `schedule:` key is **not** recorded (the item is retried next tick after the cause is fixed).
2. `admission_payload` for `start_review`: `implementer_role, implementer_model_id = DefaultTaskRouter.implementer_of(item)`; `reviewer_role = route.role`; `reviewer_model_id = routing.model_id`; `cross_model_review = False` when an APPROVED `cross_model_review_unsatisfiable` escalation exists for `(item, state_version)` (E03-S07 rule 5), else `route.cross_model_review`.
3. A review run whose role equals the implementer role never starts (route raises `PermissionDenied`, E03-S07 rule 3); a same-model review with `cross_model_review=True` is rejected by guard `reviewer_model_differs_or_disabled` even if `check_cross_model` were bypassed (defence in depth, tested).
4. Read-only purposes: for runs with `purpose ∈ READ_ONLY_PURPOSES` any observed worktree change → `BoundaryViolation("<purpose> runs must not change files")` → run `FAILED_BOUNDARY`, worktree reverted, no commit, no workflow event (E03-S08 rule 7 path), regardless of the role's `git.commit` permission. This keeps a LEAD_DEV reviewer from "fixing while reviewing" (§6.4).
5. REVIEW output `APPROVED` → `review_approved` (guard `output_status_is_approved`, role LEAD_DEV) → `INTEGRATION`; `ReviewFlow.on_review_approved` comments `Review approved by <role> (<model_id>)` on the provider (key `work.comment:{id}:{ledger_seq}`) and wakes the orchestrator so the integration step (E03-S12) starts in the next tick.
6. REVIEW output `REJECTED` → `review_rejected` → `REWORK`. `ReviewFlow.on_review_rejected`: provider comment `Review rejected:` + one bullet per finding `<severity> <summary> (<affected_files>)`; if the output contains no `context_updates` targeting the item's context document (feature doc for STORY/TASK via parent, bug doc for BUG), the kernel appends the same bullets under `REVIEW_FINDINGS_SECTION` (`Investigations` for bugs) with `Actor(KERNEL)`. A rejection with zero findings is still a rejection (reviewer authority) but adds `Finding(WARNING, "rejection without findings")` and counter `review.rejected_without_findings`.
7. The next `IMPLEMENT` run for the item after `REWORK` receives the rejecting review's findings: the scheduler passes a `Handover(reason="REASSIGN", findings=<review findings>, next_action="Address review findings", from_run_id=<review run>, …)` built by `CheckpointManager.build_handover(review_run, "REASSIGN", review_output)` and persisted once per review run (key `handover:{review_run_id}:0`); the IMPLEMENT template's continuation block therefore lists the findings (E03-S06 rule 9).
8. REVIEW runs never carry `new_bugs` effects for STORY/TASK reviews beyond what LEAD_DEV is permitted (`jira.create_task` ALLOW; `jira.create_bug` is resolved by `PermissionManager` per ADR-0006 D-6 — LEAD_DEV has `may_create_work: [TASK, BUG]`, the applier only executes what `ToolInvoker.authorize` allows).
9. Stranded reviews: an item in `LEAD_DEV_REVIEW` with `assigned_run_id is None` (admission event committed but `AgentExecutor.start` failed, or the kernel died between the two) is routed by the new `scheduled_states.yaml` rows to a REVIEW run with no admission event; `ready_items` therefore never strands it.
10. Every review transition carries `run_id` of the review run; `walk work show <id>` lists `start_review (KERNEL)`, `review_approved|review_rejected (LEAD_DEV, RUN-…)`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `ADMISSION_EVENTS` When compared with the story/bug tables Then every event exists for its `(kind, state)` with `KERNEL` in allowed roles | `tests/orchestrator/test_admission.py::test_admission_events_consistent_with_tables` |
| 2 | Given a STORY in `READY_FOR_REVIEW` implemented by SENIOR_DEV on `fake-codex/sim` When a tick runs Then `start_review` raised with payload `implementer_role=SENIOR_DEV, reviewer_role=LEAD_DEV, implementer_model_id=fake-codex/sim, reviewer_model_id=fake-claude/sim, cross_model_review=True`, story in `LEAD_DEV_REVIEW`, one REVIEW run started | `tests/orchestrator/test_admission.py::test_review_admission_raises_start_review_with_model_facts` |
| 3 | Given `check_cross_model` bypassed and the same model selected When `start_review` is raised Then `GuardRejected`, no run, no `schedule:` key recorded | `tests/orchestrator/test_admission.py::test_same_model_review_rejected_by_guard_defence_in_depth` |
| 4 | Given an APPROVED `cross_model_review_unsatisfiable` escalation When the tick runs Then payload `cross_model_review=False` and the review starts on the same model | `tests/orchestrator/test_admission.py::test_approved_escalation_sets_cross_model_false` |
| 5 | Given a REVIEW output `APPROVED` When applied and completed Then story in `INTEGRATION`, provider comment `Review approved by LEAD_DEV`, orchestrator woken | `tests/orchestrator/test_review_flow.py::test_review_approved_moves_to_integration` |
| 6 | Given a REVIEW output `REJECTED` with two findings and no context updates When completed Then story in `REWORK`, provider comment with both bullets, feature doc `Implementation Notes` appended by `KERNEL` | `tests/orchestrator/test_review_flow.py::test_review_rejected_feeds_findings_back` |
| 7 | Given a REVIEW output `REJECTED` with a context update on the feature doc When completed Then no kernel append (no duplicate) | `tests/orchestrator/test_review_flow.py::test_review_rejected_no_duplicate_context_append` |
| 8 | Given a `REJECTED` output with zero findings When applied Then still `REWORK`, `Finding(WARNING, "rejection without findings")`, counter incremented | `tests/orchestrator/test_review_flow.py::test_rejection_without_findings_still_rejects` |
| 9 | Given a BUG review rejection When completed Then the append goes to the bug doc section `Investigations` | `tests/orchestrator/test_review_flow.py::test_bug_review_findings_go_to_investigations` |
| 10 | Given a story in `REWORK` after rejection When the next IMPLEMENT run starts Then `AgentInput.handover.reason == "REASSIGN"` and `handover.findings` equal the review findings | `tests/orchestrator/test_review_flow.py::test_rework_run_receives_review_findings_handover` |
| 11 | Given a LEAD_DEV REVIEW run that modified a file When applied Then `FAILED_BOUNDARY`, worktree reverted, story still `LEAD_DEV_REVIEW` | `tests/runtime/test_output_applier_review.py::test_review_run_must_not_change_files` |
| 12 | Given a REVIEW run When `guard_payload` Then it contains `reviewer_role` and `reviewer_model_id` of the run | `tests/runtime/test_output_applier_review.py::test_review_guard_payload_has_reviewer_facts` |
| 13 | Given a STORY in `LEAD_DEV_REVIEW` with no assigned run When a tick runs Then a REVIEW run starts without raising an admission event | `tests/orchestrator/test_admission.py::test_stranded_lead_dev_review_is_readmitted` |

#### Evidence required
- Quality gate output.
- Demo with both fakes on the E01 gate fixture extended by the test: `walk work show STORY-0001` shows `READY_FOR_REVIEW → LEAD_DEV_REVIEW (start_review, KERNEL)` and `LEAD_DEV_REVIEW → REWORK (review_rejected, LEAD_DEV)`; `cat .walk/work/LOCAL-2.md` shows the `Review rejected:` comment; `walk handover show STORY-0001` shows reason `REASSIGN`.

#### Notes
- §61, §23, Invariant 4 (ARCHITECTURE §7 row 4), ADR-0006 consequence ("review/QC verdicts are workflow events raised by the kernel"), INTERFACES §5.1, E03-S07 rule 5.
- `NEW NAME:` `ADMISSION_EVENTS`, `Scheduler.admission_payload`, `ReviewFlow`, `REVIEW_FINDINGS_SECTION`, `READ_ONLY_PURPOSES`, `scheduled_states.yaml` rows for `LEAD_DEV_REVIEW`, handover reason `REASSIGN` used for review feedback (value exists in `Handover.reason`), idempotency key `handover:{review_run_id}:0` (ARCHITECTURE §5.4 format with checkpoint_seq 0), counters `scheduler.admission_rejected`, `review.rejected_without_findings`.
- Also read: E01-S29 presumably hard-codes `start_implementation` on admission; replace it with the `ADMISSION_EVENTS` lookup in this commit (no behaviour change for READY/REWORK stories).
- Pitfall: the admission event and `AgentExecutor.start` are two steps (rule 9 covers the gap); never record the `schedule:` key before `start` returned.
- Commit subject: `feat: add lead dev review flow with cross-model guard (E03-S13)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S14 — QC flow and bug creation

**Status:** TODO
**Type:** feat
**Requirements:** §6.4, §6.6, §10.8, §63, §64, §65, §81, §126, §137 (Invariants 4, 9)
**Depends on:** E03-S08, E03-S07, E03-S11
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An item in `QC` gets an independent QC run (different role, preferably different model) whose evidence-backed verdict raises `qc_passed` or `qc_rejected`; every bug QC files becomes a `BUG` that is immediately moved `IDEA → DISCOVERY` by the kernel with a bug context document and a work-provider row, and the orchestrator's run-completion path writes the `QC_RESULT` and `BUG_CREATED` ledger events (ARCHITECTURE §4.3).

#### Scope
- In: QC verdict preconditions (QC_REPORT evidence) in the output applier; QC guard payload keys; `QcFlow` completion entries for STORY/TASK/FEATURE/BUG QC runs (ledger `QC_RESULT`, provider comment, rework handover); `BugIntake` (kernel `triage` event, ledger `BUG_CREATED`, bug context skeleton); default bug contract; `ON_BUG_CREATED` and `ON_QC_RESULT` MUST attachments.
- Out: the bug loop after `DISCOVERY` — triage verdict, fix, re-test `verified`/`reopen` (E03-S15); fix-loop limit escalation (E03-S16); feature-level `qc_passed` done-dimension handling (E03-S17); typed `BugContext` (E04-S01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/qc_flow.py` | create | `QcFlow`, `BugIntake`, `BUG_CONTEXT_INTAKE_SECTIONS` |
| `src/walk/runtime/output_applier.py` | modify | — (QC precondition rule; `guard_payload` adds `created_bug_ids`, `qc_report_present`) |
| `src/walk/workflow/service.py` | modify | — (`create(BugDraft)` fills `contract.acceptance_criteria` and `contract.required_evidence`) |
| `src/walk/hooks/builtins.py` | modify | hooks `builtin.bug_created` (ON_BUG_CREATED), `builtin.qc_evidence_recorded` (ON_QC_RESULT) |
| `src/walk/cli/composition.py` | modify | — (registers `QcFlow`, `BugIntake` on the `RunCompletionHandler`) |
| `tests/orchestrator/test_qc_flow.py` | create | — |
| `tests/runtime/test_output_applier_qc.py` | create | — |
| `tests/hooks/test_builtins_bugs.py` | create | — |
| `tests/workflow/test_service_create.py` | modify | — |

#### Interface contract
Transitions per `INTERFACES.md` §3.2 (`QC → qc_passed → COMPLETE`, `QC → qc_rejected → REWORK | BLOCKED`), §3.1 (feature QC rows — event raised here, dimension logic E03-S17), §3.3 (`IDEA → triage → DISCOVERY`, role KERNEL, hook ON_BUG_CREATED); routing §4 (`QC → QC/QC` for FEATURE/STORY/TASK/BUG); ledger write point `orchestrator.Orchestrator (QC output applied)` for `QC_RESULT`, `BUG_CREATED` (ARCHITECTURE §4.3). Additions:

```python
# src/walk/orchestrator/qc_flow.py
BUG_CONTEXT_INTAKE_SECTIONS = ("Problem", "Reproduction", "Expected Behavior", "Observed Behavior")   # §38 names, filled from BugDraft

class QcFlow:
    def __init__(self, workflow: WorkflowManager, integrations: IntegrationManager, ledger: LedgerManager,
                 checkpoints: CheckpointManager, telemetry: TelemetryManager, clock: Clock) -> None: ...
    async def on_qc_completed(self, ctx: CompletionContext) -> None: ...       # any kind, purpose QC, event in {qc_passed, qc_rejected, verified, reopen}
    def register(self, handler: RunCompletionHandler) -> None: ...

class BugIntake:
    def __init__(self, workflow: WorkflowManager, memory: MemoryManager, ledger: LedgerManager, git: GitProvider) -> None: ...
    async def on_bugs_created(self, ctx: CompletionContext) -> None: ...       # any purpose; acts on BUG ids in effects.created_work_items
    async def intake(self, bug: Bug, *, run: AgentRun | None) -> None: ...     # triage event + BUG_CREATED ledger (idempotent)
    def register(self, handler: RunCompletionHandler) -> None: ...            # registered as a catch-all entry (event=None matches any)
```

`RunCompletionHandler.register(kind, purpose, event=None, …)` with `event=None` is a wildcard entry that runs after the exact-match entry (extension of E03-S09, same class).

Ledger payloads (`NEW NAME:` payload shapes):
- `QC_RESULT {verdict: "APPROVED"|"REJECTED", workflow_event, run_id, model_id, evidence_ids, bug_ids, findings: int, fix_loops, reopen_count?}` with `work_item_id`, `role=QC`.
- `BUG_CREATED {bug_id, severity, related_feature_id, found_in_run_id, found_against_commit, external_ref}` with `work_item_id=<bug id>`.

Default bug contract (in `create(BugDraft)`): `goal = title` (unchanged), `acceptance_criteria = [f"Reproduction no longer reproduces: {reproduction}", f"Expected behaviour holds: {expected}"]`, `required_evidence = [AUTOMATED_TEST]` (regression test, guard `regression_test_evidence`), `owner_role` left to triage (E01-S08 rule 2), `reviewer_role = LEAD_DEV`, `priority` from severity (`BLOCKER→P0, MAJOR→P1, MINOR→P2, TRIVIAL→P3`).

#### Behavior
1. QC admission: items in `QC` are routed to `QC/QC` (no admission event — `QC` is already the run state); `ModelRouter.select` defers the implementer's model (E03-S07) and the scheduler enforces `check_cross_model` for QC routes as for reviews. The QC run is read-only (E03-S13 `READ_ONLY_PURPOSES`).
2. QC precondition (output applier, before the workflow event): a QC output with status `APPROVED` or `REJECTED` must have recorded at least one `QC_REPORT` evidence in this run; otherwise `Finding(RISK, "QC verdict without QC_REPORT evidence")`, no workflow event, run `FAILED` with `failure_reason="qc_without_report"` and the item stays in `QC` (rescheduled next tick; §6.6 evidence over assertion).
3. `guard_payload` for QC runs adds `qc_report_present`, `created_bug_ids` (ids of BUGs created in step 5 of the applier, in order) and `reproduction_evidence` (REPRODUCTION_PROOF recorded in this run — consumed by E03-S15).
4. STORY/TASK QC `APPROVED` → `qc_passed` (guards `output_status_is_approved`, `required_evidence_present` against `contract.required_evidence` using evidence of the item incl. CI evidence from E03-S11) → `COMPLETE`. `REJECTED` → `qc_rejected` (`fix_loops_below_max` → `REWORK` + `fix_loops += 1`; at max → `BLOCKED`, E03-S16).
5. QC reports story-blocking defects as `findings` and files `new_bugs` for defects that are separate work (§10.8; QC template, E03-S06). Bugs are created by the applier (E03-S08 rule 5) with `related_feature_id`, `found_in_run_id`, `found_against_commit`; a QC output may file bugs with either verdict.
6. `BugIntake.intake(bug)` (completion catch-all for every run whose `created_work_items` contains BUG ids, any purpose): when the bug is in `IDEA` → `raise_event(bug.id, "triage", TransitionContext(actor_role=KERNEL, source=KERNEL, run_id=run.id, payload={"created_bug_ids": [bug.id]}))` → `DISCOVERY` (fires `ON_BUG_CREATED`); then ledger `BUG_CREATED` (payload above). Idempotent: a bug not in `IDEA` and an existing `BUG_CREATED` event for it → no-op.
7. `builtin.bug_created` (`ON_BUG_CREATED`, required, priority 20, FAIL_CLOSED) for each id in `ctx.payload["created_bug_ids"]`: `IntegrationManager.with_idempotency(f"work.create:{bug.id}", …)` (replays the applier's create; creates when the applier's create failed transiently) and `link(bug, feature, "RELATES")` replay; writes the bug document skeleton when `.ai/bugs/<BUG-id>.md` is absent via `MemoryManager.apply_updates` with `BUG_CONTEXT_INTAKE_SECTIONS` filled from the bug (`Problem` = title, `Reproduction`, `Expected Behavior`, `Observed Behavior`) using `Actor(KERNEL)`. Missing `created_bug_ids` → `HookFailed("created_bug_ids")`. The story `qc_rejected` row also lists `on_bug_created` (INTERFACES §3.2); with the applier's payload this hook processes the same ids and the later `triage` firing replays as no-ops.
8. `QcFlow.on_qc_completed`: writes `QC_RESULT` (one per QC run; idempotent by `(run_id)` check against the ledger); provider comment `QC <verdict>: <result first line>` + bug refs (key `work.comment:{id}:{ledger_seq}`); for `qc_rejected` on STORY/TASK, persists a `Handover(reason="REASSIGN", findings=<QC findings>, remaining_work=[<bug ids>], next_action="Address QC findings")` via `CheckpointManager.build_handover(qc_run, "REASSIGN", output)` (key `handover:{qc_run_id}:0`) so the rework IMPLEMENT run receives it (same mechanism as E03-S13 rule 7).
9. `builtin.qc_evidence_recorded` (`ON_QC_RESULT`, required, priority 20): asserts `QC_REPORT ∈ ctx.payload["evidence_kinds_present"]`; writes nothing (WBS §3.5; rule 2 guarantees it holds).
10. FEATURE QC runs use the same precondition, bug creation and `QC_RESULT`; the feature events `qc_passed`/`qc_rejected` are raised by the applier from `output_events.yaml` (E03-S08) and their dimension/guard handling belongs to E03-S17.
11. BUG QC runs (re-test) use the same precondition and `QC_RESULT`; `verified`/`reopen` semantics are E03-S15.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a STORY in `QC` implemented on `fake-codex/sim` When a tick runs Then one QC run for role QC on `fake-claude/sim` | `tests/orchestrator/test_qc_flow.py::test_qc_run_routed_to_qc_on_different_model` |
| 2 | Given a QC `APPROVED` output with `QC_REPORT` evidence and CI `AUTOMATED_TEST` evidence on the story When applied and completed Then story `COMPLETE`, one `QC_RESULT{verdict: APPROVED}` ledger event, provider comment `QC APPROVED` | `tests/orchestrator/test_qc_flow.py::test_qc_approved_completes_story_and_records_result` |
| 3 | Given a QC `APPROVED` output without `QC_REPORT` When applied Then no transition, run `FAILED` with `qc_without_report`, story still `QC` | `tests/runtime/test_output_applier_qc.py::test_qc_verdict_requires_qc_report` |
| 4 | Given a QC `REJECTED` output with one finding and one `new_bugs` draft When applied and completed Then story `REWORK` with `fix_loops == 1`, `BUG-0001` in `DISCOVERY` with `related_feature_id`, `found_in_run_id`, `found_against_commit`, `.ai/bugs/BUG-0001.md` with the four intake sections, provider row with `walk:BUG-0001`, ledger `QC_RESULT{verdict: REJECTED, bug_ids: [BUG-0001]}` and `BUG_CREATED` | `tests/orchestrator/test_qc_flow.py::test_qc_rejected_creates_bug_and_triages` |
| 5 | Given a QC `APPROVED` output that also files a MINOR bug When completed Then story `COMPLETE` and the bug in `DISCOVERY` | `tests/orchestrator/test_qc_flow.py::test_qc_approved_with_bug_files_bug_and_passes` |
| 6 | Given the completion replayed (recovery) When `on_qc_completed` and `intake` run again Then one `QC_RESULT`, one `BUG_CREATED`, one provider row, no extra transition | `tests/orchestrator/test_qc_flow.py::test_qc_completion_idempotent` |
| 7 | Given a story `qc_rejected` When the next IMPLEMENT run starts Then `AgentInput.handover.reason == "REASSIGN"` with the QC findings and bug ids in `remaining_work` | `tests/orchestrator/test_qc_flow.py::test_rework_after_qc_rejection_receives_handover` |
| 8 | Given a LEAD_DEV REVIEW run that filed a bug When completed Then `BugIntake` triages it and writes `BUG_CREATED` (not only QC runs) | `tests/orchestrator/test_qc_flow.py::test_bug_intake_applies_to_any_purpose` |
| 9 | Given a QC run When `guard_payload` Then `qc_report_present`, `created_bug_ids` in creation order and `reproduction_evidence` present | `tests/runtime/test_output_applier_qc.py::test_qc_guard_payload_keys` |
| 10 | Given `ON_BUG_CREATED` with `created_bug_ids` whose provider create previously failed transiently When fired Then the provider row is created; fired again Then no second row; missing key → `HookFailed` | `tests/hooks/test_builtins_bugs.py::test_bug_created_hook_idempotent_provider_create_and_skeleton` |
| 11 | Given `ON_QC_RESULT` with and without `QC_REPORT` in `evidence_kinds_present` Then ok / `HookFailed`, and no ledger write besides `HOOK_EXECUTED` | `tests/hooks/test_builtins_bugs.py::test_qc_result_hook_asserts_report_evidence` |
| 12 | Given `create(BugDraft(severity=BLOCKER, …))` Then `contract.acceptance_criteria` has the reproduction and expected lines, `required_evidence == [AUTOMATED_TEST]`, `priority == P0`, `owner_role is None` | `tests/workflow/test_service_create.py::test_create_bug_fills_default_contract` |

#### Evidence required
- Quality gate output.
- Demo with fakes (fixture in `tests/orchestrator/test_qc_flow.py`, `--repo <tmp>`): `walk work show STORY-0001` → `QC → REWORK (qc_rejected, QC)`; `walk work list --kind BUG` → `BUG-0001 DISCOVERY`; `cat .ai/bugs/BUG-0001.md`; `walk ledger query --kind QC_RESULT --kind BUG_CREATED --json`.

#### Notes
- §63 (QC can create bug, reopen story, reject feature, demand evidence), §64, §65, §10.8; ARCHITECTURE §4.1 (`ON_READY_FOR_QC`, `ON_QC_RESULT`, `ON_BUG_CREATED`), §4.3; ADR-0010 (bug states on the unified enum); E02-S08 deferral table (`ON_BUG_CREATED → WorkProvider.create + bug skeleton` assigned to E03-S14/E04-S01 — E04-S01 later replaces the skeleton with the typed `BugContext`).
- `NEW NAME:` `QcFlow`, `BugIntake`, `BUG_CONTEXT_INTAKE_SECTIONS`, wildcard `event=None` registration on `RunCompletionHandler`, builtin hook ids `builtin.bug_created`, `builtin.qc_evidence_recorded`, payload keys `created_bug_ids`, `qc_report_present`, failure reason `qc_without_report`, `QC_RESULT`/`BUG_CREATED` payload shapes, severity → priority mapping.
- E11-S04 relies on `QcFlow.on_qc_completed` being the single place where QC output is handled after apply.
- Pitfall: `BUG_CREATED` must be written after the `triage` transition committed, from the orchestrator — never from the hook (WBS §3.5) and never from the applier (not a §4.3 write point for this kind).
- Commit subject: `feat: add qc flow and kernel bug intake (E03-S14)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S15 — Bug loop: triage, fix, review, re-test, reopen

**Status:** TODO
**Type:** feat
**Requirements:** §10.6, §10.8, §38, §63, §64, §126, §137 (Invariants 4, 6)
**Depends on:** E03-S14
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `BUG` in `DISCOVERY` runs the whole §64 loop on the unified state enum (ADR-0010 D-2): LEAD_DEV triage sets severity and owner through a structured verdict, the kernel starts the fix on a `bug/` branch, the fix needs a root cause and a regression test, Lead Dev reviews it, the integration step merges it into the feature branch, and QC re-tests — `verified` closes the bug with reproduction evidence, `reopen` sends it back to `REWORK`, and QC can `regression_reopen` a closed bug.

#### Scope
- In: `TriageVerdict` and `AgentOutput.triage`; `AgentOutput.reopen_bugs`; triage application (severity, owner role, branch, provider assignment); `start_fix` admission rows; BUG IMPLEMENT guard payload (bug-document sections); `verified`/`reopen`/`regression_reopen` handling; `BugFlow` completion entries; TRIAGE/QC template amendments.
- Out: `wont_fix` execution (needs `DecisionManager.record`, E04-S05 — here a `wont_fix` proposal only raises an escalation request); reopen/fix-loop limit escalation (E03-S16); typed `BugContext` sections (E04-S01); debate on disputed severity (E05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/models.py` | modify | `TriageVerdict`, `AgentOutput.triage`, `AgentOutput.reopen_bugs` |
| `src/walk/agents/templates/TRIAGE.md.j2` | modify | — (instructs the `triage` field; status options unchanged) |
| `src/walk/agents/templates/QC.md.j2` | modify | — (bug re-test: `REPRODUCTION_PROOF`; `reopen_bugs` for regressions) |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.apply_triage` |
| `src/walk/runtime/output_applier.py` | modify | — (triage application before the event; `reopen_bugs` → `regression_reopen`; BUG `guard_payload` keys) |
| `src/walk/orchestrator/scheduler.py` | modify | — (`ADMISSION_EVENTS` rows `(BUG, READY)`, `(BUG, REWORK)` → `start_fix`) |
| `src/walk/orchestrator/bug_flow.py` | create | `BugFlow`, `BUG_OWNER_ROLES` |
| `src/walk/cli/composition.py` | modify | — (registers `BugFlow`) |
| `docs/01-architecture/DOMAIN-MODEL.md` | modify | — (§4.2 `TriageVerdict`, `AgentOutput.triage`, `AgentOutput.reopen_bugs`) |
| `tests/orchestrator/test_bug_flow.py` | create | — |
| `tests/runtime/test_output_applier_bug.py` | create | — |
| `tests/agents/test_contract_models.py` | modify | — |
| `tests/agents/test_templates_e03.py` | modify | — |

#### Interface contract
Bug lifecycle `bug_workflow v1.0` per `INTERFACES.md` §3.3; routing §4 (BUG `DISCOVERY → LEAD_DEV/TRIAGE`, `READY|REWORK → contract.owner_role/IMPLEMENT`, `READY_FOR_REVIEW → LEAD_DEV/REVIEW`, `QC → QC/QC`); guard payload keys WBS §3.4 (`feature_context_sections` for `root_cause_section_present`, `evidence_kinds_present` for `regression_test_evidence`, `reproduction_evidence`, `max_reopen`). Additions:

```python
# src/walk/agents/models.py
class TriageVerdict(WalkModel):
    """Structured TRIAGE result (§10.8: QC finds severity; Lead Dev triages owner and may confirm or change severity)."""
    severity: Severity
    owner_role: AgentRole
    rationale: str
    propose_wont_fix: bool = False

class AgentOutput(WalkModel):  # existing; two new fields
    triage: TriageVerdict | None = Field(default=None, description="Required for purpose TRIAGE with status COMPLETED")
    reopen_bugs: list[BugId] = Field(default_factory=list, description="QC only: closed bugs that regressed (raises regression_reopen)")

# src/walk/workflow/repository.py
class WorkflowRepository:
    async def apply_triage(self, bug_id: BugId, severity: Severity, owner_role: AgentRole) -> Bug: ...  # sets severity, owner_role, contract.owner_role, priority from severity

# src/walk/orchestrator/bug_flow.py
BUG_OWNER_ROLES: frozenset[AgentRole] = frozenset({AgentRole.SENIOR_DEV, AgentRole.LEAD_DEV})
class BugFlow:
    def __init__(self, workflow: WorkflowManager, repo: WorkflowRepository, integrations: IntegrationManager, memory: MemoryManager,
                 permissions: PermissionManager, checkpoints: CheckpointManager, git: GitProvider) -> None: ...
    async def on_triaged(self, ctx: CompletionContext) -> None: ...
    async def on_wont_fix_proposed(self, ctx: CompletionContext) -> None: ...
    async def on_verified(self, ctx: CompletionContext) -> None: ...
    async def on_reopen(self, ctx: CompletionContext) -> None: ...
    def register(self, handler: RunCompletionHandler) -> None: ...
```

#### Behavior
1. Triage run (LEAD_DEV, BUG/DISCOVERY): before raising `triaged` the applier validates `output.triage`: missing with status `COMPLETED` → `Finding(RISK, "triage verdict missing")`, guards `severity_set`/`owner_role_set` receive `False`; `owner_role ∉ BUG_OWNER_ROLES` → `Finding(RISK, "owner role cannot fix bugs")` and `owner_role_set=False`. Valid → `WorkflowRepository.apply_triage(...)` then payload `severity_set=True, owner_role_set=True`. No `block` row exists in `DISCOVERY`, so a rejected `triaged` fails the run (E03-S08 rule 2) and the bug is re-triaged next tick.
2. `propose_wont_fix=True` → `triaged` is not raised; the run ends `COMPLETED` with no workflow event; `BugFlow.on_wont_fix_proposed` (registered for `(BUG, "TRIAGE", None)`, acting only when `triage.propose_wont_fix`) creates one `ApprovalRequest(kind="ESCALATION", approver=USER, payload={"reason": "wont_fix_proposed", "bug_id", "rationale"})` and a provider comment; the bug stays in `DISCOVERY` and is excluded from scheduling while that request is `PENDING` (scheduler check). DENIED → re-triage on the next tick with `rationale` passed as a finding; APPROVED → stays excluded until `wont_fix` is raised by USER/PO with a recorded QUALITY decision (E04-S05).
3. `BugFlow.on_triaged` (`(BUG, "TRIAGE", "triaged")`): `set_branch(bug.id, branch_name_for(bug))`; `work.assign(bug, owner_role, idempotency_key=f"work.assign:{bug.id}:{state_version}")`; provider comment `Triaged: <severity>, owner <role>: <rationale>`.
4. Admission: `(BUG, READY)` and `(BUG, REWORK)` raise `start_fix` (KERNEL, guards `dependencies_complete`, `budget_available` on READY) before the IMPLEMENT run starts; `ON_TASK_START` creates `bug/<BUG-id>-<slug>` from the related feature branch (E03-S09 `base_branch_for`).
5. Fix run (owner role, BUG/IMPLEMENTING): `guard_payload` adds `feature_context_sections` = non-empty H2 sections of `.ai/bugs/<BUG-id>.md` after the run's context updates; `submit_for_review` therefore needs `Root Cause` written (`root_cause_section_present`), a kernel commit (`has_commit`) and `AUTOMATED_TEST` evidence (`regression_test_evidence`); failure → `block` (bug table `IMPLEMENTING → block`) with the guard reason (E03-S08 rule 2).
6. Review (E03-S13) and integration (E03-S12) apply unchanged to bugs; the QC re-test run (BUG/QC) must record `REPRODUCTION_PROOF` to pass: `APPROVED` → `verified` (guard `reproduction_no_longer_reproduces_evidence` reads `reproduction_evidence`) → `COMPLETE`; `APPROVED` without `REPRODUCTION_PROOF` → guard rejection → run `FAILED` (no block row in bug `QC`), bug stays `QC`.
7. `REJECTED` → `reopen` (`reopen_below_max` → `REWORK`, `reopen_count += 1`; at max → `BLOCKED` + `ON_TASK_FAILED`, E03-S16). `BugFlow.on_reopen` persists a `Handover(reason="REASSIGN", findings=<QC findings>, next_action="Re-fix: reproduction still fails")` (key `handover:{qc_run_id}:0`) for the next fix run.
8. `BugFlow.on_verified`: appends `- Verified by <run_id> (<model_id>) at <head[:7]>; evidence <ids>` to section `Verification` of the bug document with `Actor(KERNEL)` unless the QC output already updated `Verification`; provider comment `Verified`.
9. `reopen_bugs` (QC runs only): each id is authorised as tool `jira.reopen` for the QC role via `ToolInvoker.authorize` (ADR-0006 D-6 ALLOW for QC; DENY → `denied_intents`); the bug must be `COMPLETE` (else `Finding(WARNING)`, skipped); then `raise_event(id, "regression_reopen", TransitionContext(actor_role=QC, source=AGENT, run_id, payload={"created_bug_ids": [id]}))` → `DISCOVERY` (hook `ON_BUG_CREATED` replays as no-op for provider create and skeleton, E03-S14 rule 7). For non-QC runs the applier ignores `reopen_bugs` and records `Finding(RISK, "reopen_bugs ignored for role")` (the run is not failed).
10. All bug transitions carry `run_id`; `walk work show BUG-0001` lists the full chain `IDEA → DISCOVERY → READY → IMPLEMENTING → READY_FOR_REVIEW → LEAD_DEV_REVIEW → INTEGRATION → QC → COMPLETE`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `AgentOutput` JSON with a `triage` object and `reopen_bugs` When parsed Then the fields round-trip; a `triage` with an unknown severity → `OutputInvalid` | `tests/agents/test_contract_models.py::test_agent_output_triage_and_reopen_fields` |
| 2 | Given the TRIAGE and QC templates When rendered Then TRIAGE names the `triage` field with `severity`, `owner_role`, `rationale`, `propose_wont_fix` and QC mentions `REPRODUCTION_PROOF` and `reopen_bugs` | `tests/agents/test_templates_e03.py::test_triage_and_qc_templates_mention_bug_loop_fields` |
| 3 | Given a BUG in `DISCOVERY` and a TRIAGE output `{severity: MAJOR, owner_role: SENIOR_DEV}` When applied and completed Then bug `READY`, `severity=MAJOR`, `contract.owner_role=SENIOR_DEV`, `branch=bug/BUG-0001-…`, provider label `walk-role:SENIOR_DEV`, comment `Triaged:` | `tests/orchestrator/test_bug_flow.py::test_triage_sets_owner_severity_branch_and_ready` |
| 4 | Given a TRIAGE output without `triage` When applied Then `triaged` rejected, run `FAILED`, bug still `DISCOVERY` | `tests/runtime/test_output_applier_bug.py::test_triage_without_verdict_fails_run` |
| 5 | Given a TRIAGE verdict with `owner_role=QC` When applied Then `Finding(RISK, "owner role cannot fix bugs")` and bug still `DISCOVERY` | `tests/runtime/test_output_applier_bug.py::test_triage_rejects_non_fixing_owner_role` |
| 6 | Given `propose_wont_fix=True` When completed Then no transition, one `ESCALATION` approval with reason `wont_fix_proposed`, bug not admitted while pending | `tests/orchestrator/test_bug_flow.py::test_wont_fix_proposal_escalates_and_parks_bug` |
| 7 | Given a READY bug When a tick runs Then `start_fix` raised, branch `bug/BUG-0001-…` created from `feat/FEAT-0001-…`, IMPLEMENT run started for SENIOR_DEV | `tests/orchestrator/test_bug_flow.py::test_start_fix_admission_creates_bug_branch_from_feature` |
| 8 | Given a fix output without a `Root Cause` update When applied Then `submit_for_review` rejected and bug `BLOCKED` with reason naming `root_cause_section_present` | `tests/runtime/test_output_applier_bug.py::test_fix_requires_root_cause_section` |
| 9 | Given a fix output with `Root Cause`, a commit and `AUTOMATED_TEST` evidence When applied Then bug `READY_FOR_REVIEW` | `tests/runtime/test_output_applier_bug.py::test_fix_with_root_cause_and_regression_test_submits` |
| 10 | Given a bug driven through review (fake LEAD_DEV APPROVED), integration (`FakeUnityProvider` green) and QC `APPROVED` with `REPRODUCTION_PROOF` When ticks run Then bug `COMPLETE`, the fix is on the feature branch, `Verification` section appended, transition chain as Behavior 10 | `tests/orchestrator/test_bug_flow.py::test_full_bug_loop_to_verified` |
| 11 | Given QC `APPROVED` on a bug without `REPRODUCTION_PROOF` When applied Then run `FAILED` with `guard_rejected:` and bug still `QC` | `tests/runtime/test_output_applier_bug.py::test_verify_requires_reproduction_proof` |
| 12 | Given QC `REJECTED` on a bug with `reopen_count=0`, `max_reopen=3` When completed Then bug `REWORK`, `reopen_count=1`, next fix run has a `REASSIGN` handover with the QC findings | `tests/orchestrator/test_bug_flow.py::test_reopen_sends_bug_to_rework_with_handover` |
| 13 | Given a COMPLETE bug and a QC run with `reopen_bugs=[BUG-0001]` When applied Then bug `DISCOVERY` via `regression_reopen` (actor QC), `TOOL_INVOKED` for `jira.reopen`; a SENIOR_DEV output with `reopen_bugs` → ignored with `Finding(RISK)` | `tests/runtime/test_output_applier_bug.py::test_regression_reopen_by_qc_only` |

#### Evidence required
- Quality gate output.
- Demo (fixture from `test_full_bug_loop_to_verified`, `--repo <tmp>`): `walk work show BUG-0001` prints the 9-transition chain; `cat .ai/bugs/BUG-0001.md` shows `Root Cause`, `Fix`, `Verification`; `git log --oneline feat/FEAT-0001-<slug> -2` shows `bug(BUG-0001): …`.

#### Notes
- §64 loop (QC → BUG → Triage → Assign → Fix → Review → QC Re-test → Close/Reopen) mapped by ADR-0010 D-2: Triage=DISCOVERY, Assigned=READY, Fix=IMPLEMENTING, Review=READY_FOR_REVIEW/LEAD_DEV_REVIEW, Re-test=QC, Close=COMPLETE, Reopen=REWORK. ADR-0006 D-6 (`jira.reopen` ALLOW for QC). E03-S06 Scope Out assigns the TRIAGE structured verdict to this story.
- `NEW NAME:` `TriageVerdict`, `AgentOutput.triage`, `AgentOutput.reopen_bugs` (DOMAIN-MODEL updated in this commit), `WorkflowRepository.apply_triage`, `BugFlow`, `BUG_OWNER_ROLES`, idempotency key `work.assign:{id}:{state_version}` (ARCHITECTURE §5.4 has no assign key), approval payload reason `wont_fix_proposed`.
- Pitfall: `submit_for_review` for BUG has different guards than for STORY (INTERFACES §3.3 vs §3.2); `output_events.yaml` maps both to the same event — the guard set comes from the bug table, so never special-case kinds in the applier beyond the payload keys.
- Commit subject: `feat: add bug triage fix review and retest loop (E03-S15)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S16 — Fix-loop circuit breaker and `walk work force-review`

**Status:** TODO
**Type:** feat
**Requirements:** §51, §63, §64, §92, §93, §137 (Invariants 7, 14), §138 (Infinite Fix Loop)
**Depends on:** E03-S15, E02-S11
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
QC rejection loops are bounded: when a story/task/feature hits `max_fix_loops` or a bug hits `max_reopen`, the item goes `BLOCKED`, `ON_TASK_FAILED` raises a `ROOT_CAUSE_REVIEW` escalation request to the user (naming LEAD_DEV as the root-cause owner), and an approved request returns the item to `REWORK` for one more attempt; independently, the user can push an in-progress implementation into review with `walk work force-review` (§93).

#### Scope
- In: configurable limits (`circuit_breakers` in `policies.yaml`, defaults 3) supplied as guard payload; feature `qc_rejected` increments `fix_loops`; resume target `REWORK` for limit blocks; `builtin.root_cause_escalation` on `ON_TASK_FAILED`; resolution of approved/denied root-cause requests; `Orchestrator.force_review` + `walk work force-review` incl. feature fan-out and run hand-off; `USER_OVERRIDE` ledger.
- Out: routing escalations to an ORCHESTRATOR/LEAD_DEV agent run (`Orchestrator.handle_escalation`, E05-S02); debate circuit breaker (E05); fallback limit (E01-S28); effort bump on repeated failure (E07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/models.py` | modify | `CircuitBreakerLimits` |
| `src/walk/agents/policy_loader.py` | modify | `load_circuit_breakers` |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`circuit_breakers: {max_fix_loops: 3, max_reopen: 3}`) |
| `src/walk/workflow/state_machine.py` | modify | — (effect `store_resume_state_rework`) |
| `src/walk/workflow/tables/story_workflow.yaml` | modify | — (`qc_rejected → BLOCKED` row: effect `store_resume_state_rework`) |
| `src/walk/workflow/tables/feature_workflow.yaml` | modify | — (`qc_rejected → REWORK`: effect `increment_fix_loops`; `qc_rejected → BLOCKED`: effect `store_resume_state_rework`) |
| `src/walk/workflow/tables/bug_workflow.yaml` | modify | — (`reopen → BLOCKED`: effect `store_resume_state_rework`) |
| `src/walk/runtime/output_applier.py` | modify | — (`guard_payload` adds `max_fix_loops`, `max_reopen` from `CircuitBreakerLimits`) |
| `src/walk/hooks/builtins.py` | modify | hook `builtin.root_cause_escalation` (ON_TASK_FAILED); `BuiltinHookDeps.limits` |
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.force_review`, `DefaultOrchestrator.resolve_root_cause_escalations` |
| `src/walk/orchestrator/scheduler.py` | modify | — (tick step 0: `resolve_root_cause_escalations()`) |
| `src/walk/orchestrator/commands.py` | modify | — (command kind `work.force_review`) |
| `src/walk/cli/cmd_work.py` | modify | `work_force_review` |
| `src/walk/cli/composition.py` | modify | — (loads limits; wires `BuiltinHookDeps.limits`) |
| `tests/orchestrator/test_circuit_breaker.py` | create | — |
| `tests/orchestrator/test_force_review.py` | create | — |
| `tests/hooks/test_builtins_task_failed.py` | create | — |
| `tests/cli/test_cmd_work_force_review.py` | create | — |
| `tests/workflow/test_tables.py` | modify | — |

#### Interface contract
`Orchestrator.force_review(work_item_id)` per `INTERFACES.md` §1.1; CLI `walk work force-review ID` per §6 (exit codes: 0 ok, 2 guard rejected, 3 daemon required for a running run); transitions per §3.1 (`force_review` with `has_children_in(IMPLEMENTING)`, `qc_rejected` rows), §3.2 (`IMPLEMENTING → force_review → READY_FOR_REVIEW`, `qc_rejected` rows, `BLOCKED → unblock`), §3.3 (`reopen` rows); ARCHITECTURE §5.5 (`max_fix_loops` → `ON_TASK_FAILED` with escalation `ROOT_CAUSE_REVIEW` to Lead Dev, then user). Additions:

```python
# src/walk/agents/models.py
class CircuitBreakerLimits(FrozenModel):
    max_fix_loops: int = Field(default=3, ge=1, description="QC rejections per STORY/TASK/FEATURE before BLOCKED (§138)")
    max_reopen: int = Field(default=3, ge=1, description="QC re-test rejections per BUG before BLOCKED (§138)")

# src/walk/agents/policy_loader.py
def load_circuit_breakers(kernel_default: Path, project_file: Path | None) -> CircuitBreakerLimits: ...
    # project value may only be <= kernel default (narrowing, same rule as ADR-0013 D-4); larger → ConfigError

# src/walk/orchestrator/service.py
class DefaultOrchestrator:
    async def force_review(self, work_item_id: WorkItemId) -> None: ...                 # protocol method
    async def resolve_root_cause_escalations(self) -> int: ...                         # returns number of items unblocked
```

Effect `store_resume_state_rework` (`NEW NAME:`, registered next to `store_resume_state`): writes `resume_state = REWORK` into the transition payload and on the item, so `unblock` (pseudo-target `PREVIOUS`, E01-S09 rule 4) returns the item to `REWORK`.

Approval request created by the hook: `ApprovalRequest(kind="ESCALATION", approver=USER, requested_by_role=KERNEL, run_id=<failed run or None>, work_item_id, payload={"reason": "ROOT_CAUSE_REVIEW", "limit": "max_fix_loops"|"max_reopen", "count", "max", "to_role": "LEAD_DEV", "last_qc_run_id", "bug_ids"})`.

#### Behavior
1. Limits: `CircuitBreakerLimits` is loaded once at composition (kernel default merged with `.ai/agents/policies.yaml`'s `circuit_breakers`, narrowing only); `guard_payload` for every QC run includes `max_fix_loops` and `max_reopen` (WBS §3.4 keys). The guards themselves are unchanged (E01-S09/S10).
2. STORY/TASK: `qc_rejected` with `fix_loops < max_fix_loops` → `REWORK` and `fix_loops += 1`; with `fix_loops >= max_fix_loops` → `BLOCKED` with `resume_state=REWORK` and hook `ON_TASK_FAILED`. FEATURE: same, now incrementing the feature's own `fix_loops` (children's counters untouched, E01-S10 rule 6). BUG: `reopen` with `reopen_count >= max_reopen` → `BLOCKED`, `resume_state=REWORK`, `ON_TASK_FAILED`.
3. `builtin.root_cause_escalation` (`ON_TASK_FAILED`, required, priority 20, FAIL_CLOSED): when the transition payload shows `event ∈ {qc_rejected, reopen}` and `to == BLOCKED` → creates the approval request above (idempotent per `(work_item_id, state_version)` via `PermissionManager.pending()` lookup), comments on the provider `Circuit breaker: <count>/<max> QC rejections — root-cause review requested (APV-…)` (key `work.comment:{id}:{ledger_seq}`), assigns the provider item to `LEAD_DEV` (`work.assign`), counter `circuit_breaker.tripped`. For other `ON_TASK_FAILED` firings (run failed, retries exhausted, E03-S08 rule 2) it only increments `task_failed.unrouted` and comments `Run failed: <failure_reason>` — routing those to an agent is E05-S02.
4. `resolve_root_cause_escalations()` (first step of every tick): for each `ESCALATION` request with `payload.reason == "ROOT_CAUSE_REVIEW"` decided since the last tick (idempotency key `escalation.resolve:{approval_id}`): `APPROVED` → `raise_event(item, "unblock", TransitionContext(actor_role=USER, source=USER, payload={"blocker_resolved": True, "approval_id"}))` → `REWORK`; the counter is not reset, so the next rejection blocks again immediately (one extra attempt per approval). `DENIED`/`EXPIRED` → item stays `BLOCKED`, provider comment `Root-cause review denied`; the user may `walk work cancel`.
5. `force_review(id)` for STORY/TASK in `IMPLEMENTING`: if a run is active for the item → `AgentExecutor.pause(run_id)` (checkpoint `PAUSE` with WIP commit, ADR-0002) then `AgentExecutor.cancel(run_id, "force_review")`; then `raise_event(id, "force_review", TransitionContext(actor_role=USER, source=USER))` → `READY_FOR_REVIEW`; ledger `USER_OVERRIDE {command: "force_review", work_item_id, cancelled_run_id}` (orchestrator write point, as E02-S13). The next tick starts the LEAD_DEV review on the WIP head (E03-S13).
6. `force_review(id)` for FEATURE: guard `has_children_implementing`; every child STORY/TASK in `IMPLEMENTING` gets rule 5 (pause + cancel its run), then the feature `force_review` event applies effect `force_children_review` (E01-S10) moving those children to `READY_FOR_REVIEW`; the feature state itself is unchanged. One `USER_OVERRIDE` per call listing all children.
7. `force_review` on an item in any other state, or on a BUG (no `force_review` row in `bug_workflow`) → `GuardRejected` → CLI exit 2 with the reason; nothing paused or cancelled.
8. `walk work force-review ID`: daemon running → command `work.force_review` via `CommandClient`; daemon not running and no active run → executed directly in a short-lived kernel; daemon not running but the DB shows a `RUNNING` run for the item → exit 3 (a run owned by a dead daemon is recovered on next start, never force-cancelled offline).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given kernel default and a project `circuit_breakers.max_fix_loops: 2` When loaded Then 2; project value 5 → `ConfigError` | `tests/orchestrator/test_circuit_breaker.py::test_limits_load_narrowing_only` |
| 2 | Given a STORY with `fix_loops=2`, limit 3 When QC rejects Then `REWORK`, `fix_loops=3`; when QC rejects again Then `BLOCKED` with `resume_state=REWORK` | `tests/orchestrator/test_circuit_breaker.py::test_story_blocks_at_fix_loop_limit` |
| 3 | Given a FEATURE in `QC` When QC rejects Then feature `REWORK` with `fix_loops=1` and children counters unchanged | `tests/orchestrator/test_circuit_breaker.py::test_feature_qc_rejection_increments_feature_fix_loops` |
| 4 | Given a BUG with `reopen_count=3`, limit 3 When QC rejects the re-test Then `BLOCKED`, `resume_state=REWORK` | `tests/orchestrator/test_circuit_breaker.py::test_bug_blocks_at_reopen_limit` |
| 5 | Given a story blocked by the limit When `ON_TASK_FAILED` fired Then one `ESCALATION` approval with reason `ROOT_CAUSE_REVIEW`, `to_role=LEAD_DEV`, provider comment `Circuit breaker:`, provider assignee role `LEAD_DEV`; firing again creates no second request | `tests/hooks/test_builtins_task_failed.py::test_limit_block_creates_single_root_cause_request` |
| 6 | Given `ON_TASK_FAILED` from a failed run (not a limit block) When fired Then no approval request, counter `task_failed.unrouted`, comment `Run failed:` | `tests/hooks/test_builtins_task_failed.py::test_other_task_failures_are_commented_only` |
| 7 | Given the root-cause request APPROVED When the next tick runs Then the story is `REWORK` (transition source `USER`) and an IMPLEMENT run starts; a further QC rejection blocks it again | `tests/orchestrator/test_circuit_breaker.py::test_approved_root_cause_review_grants_one_more_attempt` |
| 8 | Given the request DENIED When ticks run Then the story stays `BLOCKED` and is never admitted | `tests/orchestrator/test_circuit_breaker.py::test_denied_root_cause_review_keeps_item_blocked` |
| 9 | Given a STORY `IMPLEMENTING` with a running fake run at tool call 5 When `force_review` Then a `PAUSE` checkpoint with a WIP commit, run `CANCELLED`, story `READY_FOR_REVIEW`, ledger `USER_OVERRIDE{command: force_review}` | `tests/orchestrator/test_force_review.py::test_force_review_story_pauses_and_moves_to_review` |
| 10 | Given a FEATURE with two children `IMPLEMENTING` and one `READY` When `force_review(FEAT)` Then both implementing children `READY_FOR_REVIEW`, the READY child unchanged, feature state unchanged, one `USER_OVERRIDE` listing both | `tests/orchestrator/test_force_review.py::test_force_review_feature_fans_out_to_implementing_children` |
| 11 | Given a STORY in `QC` or a BUG in `IMPLEMENTING` When `force_review` Then `GuardRejected` and no run touched | `tests/orchestrator/test_force_review.py::test_force_review_rejected_outside_implementing_or_for_bug` |
| 12 | Given no daemon and a story without a running run When `walk work force-review STORY-0001` Then exit 0; with a `RUNNING` run row Then exit 3; for a story in QC Then exit 2 | `tests/cli/test_cmd_work_force_review.py::test_force_review_cli_exit_codes` |
| 13 | Given the tables When loaded Then the limit-`BLOCKED` rows carry `store_resume_state_rework` and feature `qc_rejected → REWORK` carries `increment_fix_loops` | `tests/workflow/test_tables.py::test_circuit_breaker_effects_present` |

#### Evidence required
- Quality gate output.
- Demo with fakes scripted to reject QC 4× (fixture in `test_circuit_breaker.py`, `--repo <tmp>`): `walk work show STORY-0001` → `BLOCKED (fix_loops 3/3)`; `walk approvals --pending` lists the `ROOT_CAUSE_REVIEW` request; `walk approve APV-0001 --note "one more try"`; `walk run --once`; `walk work show STORY-0001` → `REWORK`. `walk work force-review STORY-0002` → `STORY-0002: IMPLEMENTING -> READY_FOR_REVIEW`.

#### Notes
- §138 "Infinite Fix Loop" (retry limits, root-cause escalation, circuit breakers); ARCHITECTURE §5.5; §4.1 `ON_TASK_FAILED` row (E02-S08 deferral table assigns `ON_TASK_FAILED → escalation` to this story); §93 force review; ADR-0006 D-4 (approval requests); E01-S09 rule 4 (`unblock` to stored resume state).
- `NEW NAME:` `CircuitBreakerLimits`, `load_circuit_breakers`, `policies.yaml` key `circuit_breakers`, effect `store_resume_state_rework`, builtin hook id `builtin.root_cause_escalation`, `BuiltinHookDeps.limits`, `DefaultOrchestrator.resolve_root_cause_escalations`, IPC command kind `work.force_review`, approval payload reason `ROOT_CAUSE_REVIEW` (ARCHITECTURE §5.5 names the escalation), idempotency key `escalation.resolve:{approval_id}`, counters `circuit_breaker.tripped`, `task_failed.unrouted`.
- Also read: E02-S13 (`cmd_work.py` override commands and `USER_OVERRIDE` writing in `DefaultOrchestrator`) — follow its CLI/daemon split exactly.
- Pitfall: `force_review` must pause before cancel; cancelling first loses the uncommitted worktree changes the reviewer is supposed to see.
- Commit subject: `feat: add fix loop circuit breaker and work force-review (E03-S16)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S17 — Feature completion and done dimensions

**Status:** TODO
**Type:** feat
**Requirements:** §6.4, §6.5, §6.6, §37, §59, §62, §63, §92, §131, §137 (Invariant 6)
**Depends on:** E03-S14, E03-S12
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** QC

#### Goal
A feature follows its children through the rest of `feature_workflow`: it starts implementing with its first story, enters `INTEGRATION` when all children are integrated, runs feature-level CI on the feature integration branch once every child is complete, gets an independent feature-level QC, and reaches `COMPLETE` only when every applicable §6.5 done dimension is set with evidence and no blocker bug is open (Invariant 6) — with feature-level rework through bugs and a user-approved merge of the feature branch into the protected default branch.

#### Scope
- In: `FeatureProgress` (tick-driven, idempotent feature reconciliation: `start_implementation`, `all_children_integrated`, feature CI, `integration_passed`/`ci_failed`, `rework_planned`, post-`COMPLETE` merge request); `children_states` / `open_blocker_bug_count` payload facts; FEATURE Definition of Ready; feature required evidence; done-dimension setting points (`FUNCTIONAL`, `INTEGRATED`, `TESTED`, `QC_ACCEPTED`); feature CI failure → kernel-filed BUG.
- Out: `DESIGN_VALIDATED`/`UX_COMPLETE` (E05/E08 with DESIGN_LEADER), `ART_COMPLETE` (E08-S07), `PERFORMANCE_ACCEPTABLE` (E09); `PHASE_REVIEW`/`USER_GATE` projections (E07); feature QC run mechanics (E03-S14); circuit breaker on feature `qc_rejected` (E03-S16).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/feature_progress.py` | create | `FeatureProgress`, `FeatureCiResult`, `FEATURE_REQUIRED_EVIDENCE` |
| `src/walk/orchestrator/scheduler.py` | modify | — (tick step 0b: `FeatureProgress.sync_all()` before admission) |
| `src/walk/orchestrator/integration.py` | modify | — (`complete_protected_merges` also merges approved FEATURE PRs into `default_branch`) |
| `src/walk/orchestrator/bug_flow.py` | modify | — (`on_triaged` asks `FeatureProgress.plan_rework` for the related feature) |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.children_states`, `DefaultWorkflowManager.open_blocker_bug_count` |
| `src/walk/workflow/protocols.py` | modify | — (`WorkflowManager.children_states`, `open_blocker_bug_count`) |
| `src/walk/workflow/readiness.py` | modify | — (FEATURE checks: `requirement_complete` = description non-empty, `children_present`, `design_approved` = has passed `DESIGN`) |
| `src/walk/workflow/guards.py` | modify | — (`required_evidence_present` for FEATURE uses `payload["required_evidence_kinds"]`) |
| `src/walk/runtime/output_applier.py` | modify | — (FEATURE QC `APPROVED`: `set_done_dimension(QC_ACCEPTED, evidence)` before the event; payload `children_states`, `open_blocker_bug_count`) |
| `src/walk/cli/composition.py` | modify | — (constructs `FeatureProgress`) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.3 `children_states`, `open_blocker_bug_count`) |
| `tests/orchestrator/test_feature_progress.py` | create | — |
| `tests/workflow/test_service_children.py` | create | — |
| `tests/workflow/test_readiness.py` | modify | — |
| `tests/runtime/test_output_applier_feature_qc.py` | create | — |

#### Interface contract
`feature_workflow v1.0` per `INTERFACES.md` §3.1; `WorkflowManager.set_done_dimension` §1.3; `DoneDimension` (DOMAIN-MODEL §3); guard payload keys WBS §3.4 (`children_states`, `ci_green`, `evidence_kinds_present`, `open_blocker_bug_count`). Additions:

```python
# src/walk/workflow/protocols.py (WorkflowManager)
async def children_states(self, feature_id: FeatureId) -> dict[WorkItemId, WorkItemState]:
    """Child STORY/TASK items plus BUGs with related_feature_id == feature_id; CANCELLED items excluded."""
async def open_blocker_bug_count(self, feature_id: FeatureId) -> int:
    """BUGs with related_feature_id == feature_id, severity BLOCKER, state not in {COMPLETE, CANCELLED}."""

# src/walk/orchestrator/feature_progress.py
FEATURE_REQUIRED_EVIDENCE: tuple[EvidenceKind, ...] = (EvidenceKind.AUTOMATED_TEST,)

class FeatureCiResult(FrozenModel):
    feature_id: FeatureId
    head: Sha
    green: bool
    job_results: list[JobResult]
    evidence_ids: list[EvidenceId]

class FeatureProgress:
    def __init__(self, workflow: WorkflowManager, repo: WorkflowRepository, git: GitProvider, ci: CiProvider, ci_config: CiConfig,
                 evidence: EvidenceManager, memory: MemoryManager, integrations: IntegrationManager,
                 permissions: PermissionManager, project: Project, clock: Clock, *, worktrees_root: Path) -> None: ...
    async def sync_all(self) -> int: ...                           # features in READY/IMPLEMENTING/INTEGRATION/COMPLETE; returns transitions raised
    async def sync(self, feature: Feature) -> str | None: ...      # event raised or None
    async def run_feature_ci(self, feature: Feature) -> FeatureCiResult: ...
    async def plan_rework(self, feature_id: FeatureId, *, actor_role: AgentRole, run_id: RunId | None) -> bool: ...
```

Done-dimension setting points (`NEW NAME:` rule set; MVP default `applicable_dimensions = [FUNCTIONAL, INTEGRATED, TESTED, QC_ACCEPTED]`):

| Dimension | Set when | Evidence id |
|---|---|---|
| `FUNCTIONAL` | feature CI starts and every child STORY/TASK is `COMPLETE` (each passed its own QC) | latest child `QC_REPORT` |
| `INTEGRATED` | feature CI on the feature branch is green | compile/build `LOG` or `BUILD_ARTIFACT` of that run |
| `TESTED` | feature CI green and every test job of `feature_jobs` passed | `AUTOMATED_TEST` of that run |
| `QC_ACCEPTED` | feature QC output `APPROVED` with `QC_REPORT` (set by the applier before `qc_passed`) | the run's `QC_REPORT` |

#### Behavior
1. `sync_all()` runs at the start of every tick (after E03-S16 escalation resolution) and is idempotent: every event uses `expected_state_version`; nothing happens when the facts are unchanged.
2. `READY → start_implementation` (KERNEL): raised when any child STORY/TASK is in `IMPLEMENTING` or later; payload `children_states`; guards `definition_of_ready` (FEATURE checks: description non-empty, ≥ 1 child, feature passed `DESIGN` — E01-S10 `definition_of_ready_checks` extended for kind FEATURE) and `children_created`.
3. `IMPLEMENTING → all_children_integrated` (KERNEL): when `children_states` is non-empty and every value ∈ {INTEGRATION, QC, COMPLETE} (guard `all_stories_integrated`; open related bugs count as children, so a feature waits for its bug fixes).
4. Feature `INTEGRATION`: `sync` waits (returns `None`) until every child is `COMPLETE`; then `run_feature_ci`: worktree `<worktrees_root>/int-<FEAT-id>` on `feature.branch`, `ci.run_pipeline(path, head, ci_config.feature_jobs, idempotency_key=f"ci.job:{feature.id}:{head}", work_item_id=feature.id)`, worktree removed in `finally`.
5. Green → `set_done_dimension(FUNCTIONAL)`, `INTEGRATED`, `TESTED` (table above; a dimension not in `applicable_dimensions` is skipped, never an error) then `integration_passed` (KERNEL) with payload `{ci_green: True, evidence_kinds_present, required_evidence_kinds: FEATURE_REQUIRED_EVIDENCE}` → `QC` (`ON_READY_FOR_QC`; the feature QC run is admitted by E03-S14 rules with a model different from the most recent implementer, E03-S07 rule 8).
6. Red → `ci_failed` (KERNEL) → `REWORK`; the kernel files `BugDraft(title="Feature CI failed: <job>", severity=MAJOR, reproduction="<job> on <feature.branch> @ <head[:7]>", expected="job passes", observed=<summary>, related_feature_id=feature.id, against_commit=head)` via `WorkflowManager.create(actor=KERNEL)` + `BugIntake.intake` (E03-S14), and provider comment `Feature CI failed`.
7. Feature `REWORK` → `rework_planned` (allowed ORCHESTRATOR, LEAD_DEV): `plan_rework(feature_id, actor_role, run_id)` is called by `BugFlow.on_triaged` (E03-S15) when the triaged bug's related feature is in `REWORK`; it raises `rework_planned` with `actor_role` = the triage run's role (LEAD_DEV) and payload `children_states`; guard `rework_children_created` passes when ≥ 1 child is in {READY, IMPLEMENTING, REWORK}. Feature QC rejections (E03-S14/S16) reach `REWORK` the same way: their bugs are triaged, then `rework_planned` fires.
8. Feature QC `APPROVED` (applier, before raising `qc_passed`): `set_done_dimension(QC_ACCEPTED, evidence_id=<QC_REPORT>)`; payload adds `open_blocker_bug_count`; guards `output_status_is_approved`, `all_applicable_dimensions_done`, `no_open_blocker_bugs`. A missing dimension or an open blocker bug → guard rejection → run `FAILED` (`guard_rejected: …` names the dimension/bug count, E03-S08 rule 2), feature stays `QC`, `QC_ACCEPTED` stays set (QC did accept), `ON_TASK_FAILED` comments the reason (E03-S16 rule 3).
9. `COMPLETE`: `ON_TASK_COMPLETE` fires (E02-S08 `remaining_work_check`); `FeatureProgress` replaces the feature doc section `Current Status` with `Complete — dimensions: <list with evidence ids>` (`Actor(KERNEL)`), opens a PR `feature.branch → project.default_branch` (`git.pr:{FEAT-id}:{head}`) and, because the default branch is protected, creates one `PROTECTED_ACTION` approval `{action: "git.merge_protected", pr, head}`; `IntegrationStep.complete_protected_merges()` (E03-S12) merges it after `walk approve`. Feature completion never waits for that merge (the merge is a release decision, §92).
10. `walk work show FEAT-0001` prints `done_dimensions` with the evidence id per dimension.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a feature with two stories, one bug related to it and one cancelled story When `children_states` Then three entries (cancelled excluded); `open_blocker_bug_count` counts only open BLOCKER bugs | `tests/workflow/test_service_children.py::test_children_states_and_open_blocker_count` |
| 2 | Given a FEATURE without description or without children or never in DESIGN When `check_definition_of_ready` Then each failing check named; complete feature → ok | `tests/workflow/test_readiness.py::test_feature_definition_of_ready_checks` |
| 3 | Given a READY feature and a child moving to IMPLEMENTING When `sync_all` Then feature `IMPLEMENTING`; a second `sync_all` raises nothing | `tests/orchestrator/test_feature_progress.py::test_feature_starts_with_first_child_idempotently` |
| 4 | Given children in INTEGRATION and QC When `sync_all` Then feature `INTEGRATION`; with one child still IMPLEMENTING Then unchanged | `tests/orchestrator/test_feature_progress.py::test_all_children_integrated_moves_feature_to_integration` |
| 5 | Given a feature in INTEGRATION with a child still in QC When `sync_all` Then no feature CI runs | `tests/orchestrator/test_feature_progress.py::test_feature_ci_waits_for_all_children_complete` |
| 6 | Given all children COMPLETE and `FakeUnityProvider` green When `sync_all` Then `feature_jobs` ran on `feat/FEAT-0001-…` head, `FUNCTIONAL`, `INTEGRATED`, `TESTED` set with evidence ids, feature `QC` | `tests/orchestrator/test_feature_progress.py::test_green_feature_ci_sets_dimensions_and_passes` |
| 7 | Given `playmode_tests` red When feature CI runs Then feature `REWORK`, a MAJOR BUG `Feature CI failed: playmode_tests` in `DISCOVERY` related to the feature, no dimension set | `tests/orchestrator/test_feature_progress.py::test_red_feature_ci_files_bug_and_reworks` |
| 8 | Given a feature in REWORK and its bug triaged by LEAD_DEV When `on_triaged` completes Then feature `IMPLEMENTING` via `rework_planned` with actor `LEAD_DEV` | `tests/orchestrator/test_feature_progress.py::test_triaged_bug_plans_feature_rework` |
| 9 | Given a feature QC `APPROVED` output with `QC_REPORT` and the other three dimensions set When applied Then `QC_ACCEPTED` set and feature `COMPLETE` | `tests/runtime/test_output_applier_feature_qc.py::test_feature_qc_approved_sets_qc_accepted_and_completes` |
| 10 | Given `TESTED` missing When feature QC `APPROVED` is applied Then run `FAILED` with reason naming `TESTED`, feature stays `QC`, `QC_ACCEPTED` set | `tests/runtime/test_output_applier_feature_qc.py::test_feature_qc_blocked_by_missing_dimension` |
| 11 | Given an open BLOCKER bug related to the feature When feature QC `APPROVED` is applied Then run `FAILED` naming `no_open_blocker_bugs` | `tests/runtime/test_output_applier_feature_qc.py::test_feature_qc_blocked_by_open_blocker_bug` |
| 12 | Given a feature reaching `COMPLETE` When `sync_all` Then `Current Status` section updated, PR stub `feat/… → main`, one `PROTECTED_ACTION` approval; after `decide_approval(APPROVED)` `complete_protected_merges()` merges into `main` | `tests/orchestrator/test_feature_progress.py::test_complete_feature_requests_protected_merge` |
| 13 | Given `applicable_dimensions` without `TESTED` When feature CI is green Then `TESTED` not written and no error | `tests/orchestrator/test_feature_progress.py::test_non_applicable_dimension_skipped` |

#### Evidence required
- Quality gate output.
- Demo (fixture from `test_complete_feature_requests_protected_merge`, `--repo <tmp>`): `walk work show FEAT-0001` → `COMPLETE` with four dimensions and evidence ids; `walk approvals --pending` lists the `git.merge_protected` request; `walk approve APV-…`; `walk run --once`; `git log --oneline main -3` shows the merged feature.

#### Notes
- §6.5 (Feature Done = sum of applicable dimensions), Invariant 6 (ARCHITECTURE §7 row 6), INTERFACES §3.1 (feature rows, `KERNEL` actor for `start_implementation`, `all_children_integrated`, `integration_passed`, `ci_failed`), §3.2 note (merge to protected base is a protected action), ADR-0006 §92 list.
- `NEW NAME:` `FeatureProgress`, `FeatureCiResult`, `FEATURE_REQUIRED_EVIDENCE`, `WorkflowManager.children_states`, `WorkflowManager.open_blocker_bug_count` (INTERFACES updated in this commit), payload key `required_evidence_kinds`, done-dimension setting-point table, FEATURE Definition-of-Ready checks `children_present`/`design_approved`, feature integration worktree `.walk/worktrees/int-<FEAT-id>`.
- WBS §3.4 lists `WorkflowManager` as writer of `children_states`/`open_blocker_bug_count`; this story adds the two query methods that compute them.
- Pitfall: `FUNCTIONAL` is only meaningful once every child passed story-level QC — never set it at `all_children_integrated` time.
- Commit subject: `feat: add feature progression ci and done dimensions (E03-S17)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S18 — Scheduler ordering and parallel worktrees

**Status:** TODO
**Type:** feat
**Requirements:** §56, §60, §64, §137 (Invariant 4)
**Depends on:** E03-S07, E01-S29
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The scheduler admits work in the INTERFACES §4 order (resolved blockers first, then bugs by severity, then everything else by priority and age, deterministic tie-break), honours `max_parallel_agents`, per-role `max_parallel_runs` and `can_run_parallel` without letting one conflicting item starve the rest, and two independent stories run concurrently in separate git worktrees on separate branches (§60).

#### Scope
- In: `Scheduler.order`; per-role running counts (`Scheduler.running_by_role`); admission loop with skip reasons (`TickReport`); MVP default `max_parallel_runs: 2` for SENIOR_DEV; concurrency proof with two fake runs in two worktrees; per-tick telemetry.
- Out: configurable parallelism and per-role limits beyond the MVP defaults (E07-S01); containers (ADR-0009 D-5, Stage 7); integration-step serialisation (E03-S12, already per base branch); routing and cross-model checks (E03-S07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/scheduler.py` | modify | `Scheduler.order`, `Scheduler.running_by_role`, `Scheduler.last_report`, `ORDER_GROUPS`, `SkipReason` |
| `src/walk/orchestrator/models.py` | modify | `TickReport` |
| `src/walk/agents/defaults/policies.yaml` | modify | — (SENIOR_DEV `max_parallel_runs: 2`; LEAD_DEV, QC, ORCHESTRATOR stay 1) |
| `src/walk/runtime/sandbox.py` | modify | — (`create` refuses a branch already checked out by another live worktree with `GuardRejected("branch in use")`) |
| `src/walk/cli/cmd_status.py` | modify | — (`walk status --verbose` prints the last `TickReport`) |
| `tests/fakes/fake_model_adapter.py` | modify | — (per-run script cursor so concurrent runs never share state; no-op if E01-S19 already isolates runs) |
| `tests/orchestrator/test_scheduler_order.py` | create | — |
| `tests/orchestrator/test_scheduler_parallel.py` | create | — |
| `tests/runtime/test_sandbox.py` | modify | — |

#### Interface contract
Scheduler tick per `INTERFACES.md` §5.1 (steps 3–6), ordering rule and limits per §4 ("Scheduling order"), ADR-0009 D-4; `TaskRouter.can_run_parallel` per E03-S07. Additions:

```python
# src/walk/orchestrator/models.py
class TickReport(FrozenModel):
    at: datetime
    considered: list[WorkItemId]                         # in admission order
    admitted: list[tuple[WorkItemId, RunId]]
    skipped: list[tuple[WorkItemId, str]]                # (item, SkipReason value)

# src/walk/orchestrator/scheduler.py
class SkipReason(StrEnum):
    CAPACITY = "capacity"                 # running_count >= max_parallel_agents
    ROLE_BUSY = "role_busy"               # running_by_role[role] >= RuntimePolicy.max_parallel_runs
    CONFLICT = "conflict"                 # not can_run_parallel with a running item
    ITEM_RUNNING = "item_running"         # item already has an active run
    ALREADY_SCHEDULED = "already_scheduled"
    ADMISSION_REJECTED = "admission_rejected"
    CROSS_MODEL = "cross_model"
    BUDGET = "budget"
    PARKED = "parked"                     # e.g. wont_fix proposal pending (E03-S15)

ORDER_GROUPS = ("UNBLOCKED", "BUG", "OTHER")

class Scheduler:
    def order(self, items: list[WorkItem], *, unblocked_ids: set[WorkItemId]) -> list[WorkItem]: ...
        # key = (group index, severity rank for BUG (BLOCKER=0..TRIVIAL=3) else 0, priority (P0=0..P3=3), created_at, id)
    def running_by_role(self) -> dict[AgentRole, int]: ...      # from AgentExecutor.running()
    @property
    def last_report(self) -> TickReport | None: ...
```

#### Behavior
1. `order`: group `UNBLOCKED` = items whose latest transition is `unblock` (resolved blockers, INTERFACES §4 "BLOCKED resolution first") and that have not been admitted since; group `BUG` = remaining BUGs ordered by severity then priority; group `OTHER` = everything else (FEATURE/STORY/TASK) by priority then `created_at`; final tie-break by `id`. Pure and deterministic (same input → same order).
2. Admission loop (INTERFACES §5.1 steps 4–6): iterate in `order`; stop admitting when `running_count >= max_parallel_agents` (remaining items recorded as `CAPACITY`); skip (not stop) items whose role is at `max_parallel_runs`, items that fail `can_run_parallel` against any running item, items with an active run, and items whose `schedule:` key exists — each with its `SkipReason`. A skipped item never prevents a later item from being admitted (no head-of-line blocking).
3. `running_by_role` counts runs in `RUNNING` and `PAUSED_FOR_APPROVAL` (a paused run still holds its worktree and its role slot); `CANCELLED`/terminal runs never count.
4. Runs admitted in the same tick are checked pairwise: the second candidate is tested with `can_run_parallel` against both running items and items admitted earlier in the same tick.
5. MVP defaults: `max_parallel_agents = 2` (`KernelSettings.max_parallel`), SENIOR_DEV `max_parallel_runs = 2`, LEAD_DEV/QC/ORCHESTRATOR `1` — so two implementations can run concurrently while reviews and QC are serialised per role.
6. Worktrees: each admitted run gets `<repo>/.walk/worktrees/<run_id>` on its item branch (E01-S25 `SandboxManager.create`); `create` raises `GuardRejected("branch in use")` when another live worktree has the same branch checked out (defence in depth behind `can_run_parallel`'s same-branch rule) and the scheduler records `ADMISSION_REJECTED`.
7. Every tick stores a `TickReport` in memory (`last_report`), increments `scheduler.admitted` and `scheduler.skipped.<reason>` counters, and logs one structured line `extra={"admitted": n, "skipped": {...}}`; nothing is written to the ledger (admission is already visible through `AGENT_RUN_STARTED`).
8. `walk status --verbose` prints the last report as `considered / admitted / skipped(reason)` lines; `walk status --json` is unchanged (`KernelStatus` contract).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an unblocked STORY P3, a MINOR BUG P1, a BLOCKER BUG P2, a STORY P0 and a STORY P0 created later When `order` Then `[unblocked story, BLOCKER bug, MINOR bug, P0 story (older), P0 story (newer)]` | `tests/orchestrator/test_scheduler_order.py::test_order_groups_severity_priority_age` |
| 2 | Given two items equal on every key but id When `order` twice with shuffled input Then identical output ordered by id | `tests/orchestrator/test_scheduler_order.py::test_order_deterministic_tie_break` |
| 3 | Given `max_parallel_agents=2` and three ready stories When a tick runs Then two admitted and the third skipped with `capacity` | `tests/orchestrator/test_scheduler_order.py::test_capacity_limit_reported` |
| 4 | Given LEAD_DEV busy with one review and a second story in `READY_FOR_REVIEW` plus a READY story When a tick runs Then the review is skipped `role_busy` and the READY story is admitted | `tests/orchestrator/test_scheduler_order.py::test_role_busy_does_not_block_later_items` |
| 5 | Given a running story touching `Assets/Scripts/Jump.cs` and a higher-priority story of the same feature with the same path plus a disjoint story When a tick runs Then the conflicting story is skipped `conflict` and the disjoint one admitted | `tests/orchestrator/test_scheduler_order.py::test_conflicting_item_skipped_without_head_of_line_blocking` |
| 6 | Given two conflicting READY stories and nothing running When one tick runs Then only the first is admitted (pairwise check within the tick) | `tests/orchestrator/test_scheduler_order.py::test_same_tick_candidates_checked_pairwise` |
| 7 | Given a run in `PAUSED_FOR_APPROVAL` for SENIOR_DEV and limit 2 When `running_by_role` Then SENIOR_DEV counts 1 | `tests/orchestrator/test_scheduler_order.py::test_paused_runs_hold_role_slot` |
| 8 | Given two independent READY stories with disjoint contract paths and `fake-codex` scripted with 12 tool calls each When one tick runs Then two `AGENT_RUN_STARTED` events, both runs `RUNNING` at the same time, worktrees `.walk/worktrees/<run1>` and `<run2>` on `story/STORY-0002-…` and `story/STORY-0003-…`, and each branch's WIP commits contain only its own files | `tests/orchestrator/test_scheduler_parallel.py::test_two_stories_run_concurrently_in_separate_worktrees` |
| 9 | Given a live worktree on `story/STORY-0002-…` When `SandboxManager.create` for another run on the same branch Then `GuardRejected("branch in use")` | `tests/runtime/test_sandbox.py::test_create_refuses_branch_checked_out_elsewhere` |
| 10 | Given a tick When finished Then `last_report` lists considered/admitted/skipped and counters `scheduler.admitted`, `scheduler.skipped.capacity` match | `tests/orchestrator/test_scheduler_order.py::test_tick_report_and_counters` |

#### Evidence required
- Quality gate output.
- Demo (fixture from `test_two_stories_run_concurrently_in_separate_worktrees`, `--repo <tmp>`): `walk status --verbose` while both runs are active → two active runs and the last tick report; `git worktree list` shows two run worktrees on two `story/` branches.

#### Notes
- INTERFACES §4 "Scheduling order", §5.1; ARCHITECTURE §3.2 "Concurrency"; ADR-0009 D-4/D-5; §60.
- `NEW NAME:` `TickReport`, `SkipReason`, `ORDER_GROUPS`, `Scheduler.order`, `Scheduler.running_by_role` (extended by E07-S01), `Scheduler.last_report`, counters `scheduler.admitted`, `scheduler.skipped.<reason>`, SENIOR_DEV default `max_parallel_runs: 2`.
- Also read: E01-S29/S30 are not yet written; `orchestrator/scheduler.py`, `orchestrator/models.py` and `cli/cmd_status.py` are the assumed file names (WBS §3.7). If E01-S29 already sorts items, replace its key with `order` in this commit.
- Pitfall: the FakeModelAdapter must not share mutable per-run state between concurrent runs (E01-S19 Behavior 6 keeps a per-run tool-call index for `resume`; verify it is keyed by `run_id`).
- Commit subject: `feat: add scheduler ordering and parallel worktree admission (E03-S18)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S19 — Epic gate part 1: §131 MVP workflow e2e with fakes

**Status:** TODO
**Type:** feat
**Requirements:** §6.4, §6.5, §23, §55, §59–§65, §131, §136, §137 (Invariants 3, 4, 6, 9)
**Depends on:** E03-S09, E03-S12, E03-S13, E03-S16, E03-S17, E03-S18, E03-S03
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end test proves the §131 lifecycle on a real temporary git repository with a bare remote, `LocalWorkProvider`, `FakeUnityProvider` and two scripted fake model adapters: `walk feature add` → plan into two stories → discovery → LEAD_DEV technical design → two parallel `fake-codex` implementations → `fake-claude` reviews → squash/push/PR/CI/merge → story QC → feature CI → feature QC rejects once with a BUG → triage → fix → review → re-test verified → feature QC passes → `COMPLETE` with all done dimensions, every step visible in the ledger, the work provider, `.ai/` and git.

#### Scope
- In: `tests/e2e/test_e03_gate.py`; `e03_scenario` fixture and `run_until_idle` driver in `tests/e2e/conftest.py`; `ScriptBook` and two `FakeScript` fields in the fake adapter; assertions on states, transitions, ledger, provider mirror, `.ai/` files, git history, Invariant 4 model separation, provider reconciliation.
- Out: production code changes (any defect found → bugfix story `E03-Bxx`); the §132 failover (E03-S20); Jira (opt-in parity tests stay in E03-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e03_gate.py` | create | — |
| `tests/e2e/conftest.py` | modify | fixtures `e03_scenario`, `e03_policies`; `E03Scenario`; helper `run_until_idle` |
| `tests/fakes/fake_model_adapter.py` | modify | `ScriptBook`, `FakeScript.path_template`, `FakeScript.writes_files`, `FakeScript.evidence_files` |
| `tests/fakes/test_fake_model_adapter_scriptbook.py` | create | — |

#### Interface contract
Uses only public kernel APIs: `build_kernel(settings, overrides=KernelOverrides(...))` (WBS §3.6), the `walk` CLI via typer `CliRunner`, `KernelHandle.orchestrator.tick()`, `WorkflowManager.get/query`, `LedgerManager.query`, `PermissionManager.pending/decide_approval`. Test-side additions:

```python
# tests/fakes/fake_model_adapter.py
class FakeScript(WalkModel):                      # existing (E01-S19) + three fields
    path_template: str = "src/Fake{i}.cs"         # formatted with i (1-based tool call) and item (work item id)
    writes_files: bool = True                     # False → ALLOWed tool calls write nothing (REVIEW/QC/PLAN/TRIAGE runs)
    evidence_files: dict[str, str] = {}           # relative path under the worktree's .walk/evidence/ → content, written before FINAL_OUTPUT

class ScriptBook:
    """Callable[[AgentInput], FakeScript] for FakeModelAdapter: picks the script by (role, purpose, item id, visit)."""
    def __init__(self) -> None: ...
    def add(self, role: AgentRole, purpose: str, item_id: str | None, script: FakeScript | Callable[[AgentInput], FakeScript], *, visit: int | None = None) -> None: ...
    def __call__(self, agent_input: AgentInput) -> FakeScript: ...        # no match → AssertionError naming (role, purpose, item, visit)
    visits: dict[tuple[str, str, str], int]                                  # (role, purpose, item) → runs served

# tests/e2e/conftest.py
class E03Scenario(WalkModel):                     # arbitrary_types_allowed
    handle: KernelHandle
    repo: Path
    remote: Path
    codex: FakeModelAdapter                       # provider "fake-codex", descriptor fake-codex/sim
    claude: FakeModelAdapter                      # provider "fake-claude", descriptor fake-claude/sim
    unity: FakeUnityProvider
    book: ScriptBook
    feature_id: str
    story_ids: list[str]
    bug_id: str | None
async def run_until_idle(handle: KernelHandle, *, max_ticks: int = 300) -> int: ...
    # tick → await all runs/integration steps started by the tick → repeat until a tick admits nothing and no step is in flight; returns ticks used; exceeding max_ticks → AssertionError with the last TickReport
```

Policies written by `e03_policies` through `walk policy set-model` (E02-S13): SENIOR_DEV preferred `fake-codex/sim` fallback `fake-claude/sim`; LEAD_DEV, QC, ORCHESTRATOR preferred `fake-claude/sim` fallback `fake-codex/sim`; `cross_model_review: true` for LEAD_DEV and QC. `KernelSettings.max_parallel = 2`.

#### Behavior
Scenario (module-scoped fixture `e03_scenario`; each test asserts one facet of the cached end state, plus step snapshots recorded by the fixture in `E03Scenario` order):
1. **Setup.** `tmp_game_repo_with_remote` (E03-S01) + `ProjectSettings/ProjectVersion.txt` stub + `Bootstrapper` (`--provider local --key DEMO --name Demo --yes`); `ci.yaml` default (story jobs `compile, editmode_tests`; feature jobs `+ playmode_tests`); `FakeUnityProvider` all green; overrides inject both adapters, `FakeClock`, `SequentialIdFactory`, the fake Unity provider.
2. **User feature.** `walk --repo <tmp> feature add "Double jump" --description "Player can jump a second time in mid-air"` → `FEAT-0001 (LOCAL-1) IDEA`.
3. **Plan.** ORCHESTRATOR/PLAN (`fake-claude`): `COMPLETED`, `new_tasks` = STORY "Double jump physics" (paths `Assets/Scripts/Jump/DoubleJump.cs`, required evidence `AUTOMATED_TEST`) and STORY "Jump input buffer" (`Assets/Scripts/Input/JumpBuffer.cs`); context updates `Intent`, `Design Goal` → `STORY-0001`, `STORY-0002` in IDEA, provider rows `LOCAL-2`, `LOCAL-3` with PARENT links; feature `DISCOVERY`.
4. **Discovery and design.** ORCHESTRATOR/DESIGN on `DISCOVERY` → `DESIGN`; LEAD_DEV/DESIGN writes `Architecture` (REPLACE) and `Relevant Files` → `design_approved` → feature `READY`, branch `feat/FEAT-0001-double-jump` from `main`, both stories `READY` with `story/…` branches.
5. **Parallel implementation.** One tick admits both SENIOR_DEV/IMPLEMENT runs on `fake-codex/sim` (E03-S18) in two worktrees; each run makes 3 tool calls writing its own `path_template` files, `AUTOMATED_TEST` evidence file, `changes` matching the diff → kernel commits `impl(STORY-000n): …` → `READY_FOR_REVIEW`; feature `IMPLEMENTING` (E03-S17).
6. **Review.** LEAD_DEV/REVIEW on `fake-claude/sim` (`writes_files=False`) `APPROVED` for both → `INTEGRATION`.
7. **Integration.** Per story: squash to `story(STORY-000n): …`, push to the bare remote, PR stub against the feature branch, `compile` + `editmode_tests` green, merge into `feat/FEAT-0001-double-jump` (serialised), `integration_passed` → `QC`.
8. **Story QC.** QC/QC on `fake-claude/sim` `APPROVED` with `QC_REPORT` → both stories `COMPLETE`.
9. **Feature CI and QC rejection.** Feature `INTEGRATION`; feature CI green → `FUNCTIONAL`, `INTEGRATED`, `TESTED` set → `QC`. Feature QC visit 1 `REJECTED` with `QC_REPORT`, one finding and `new_bugs=[BugDraft("Double jump allowed after landing", severity=MAJOR, …)]` → feature `REWORK` (`fix_loops=1`), `BUG-0001` in `DISCOVERY` with `.ai/bugs/BUG-0001.md`, `BUG_CREATED`.
10. **Bug loop.** LEAD_DEV/TRIAGE `triage={MAJOR, SENIOR_DEV}` → bug `READY`, feature `rework_planned` → `IMPLEMENTING`; SENIOR_DEV/IMPLEMENT on `fake-codex/sim` writes `Root Cause`, `Fix`, regression `AUTOMATED_TEST` → `READY_FOR_REVIEW`; LEAD_DEV review `APPROVED`; integration merges `bug(BUG-0001): …` into the feature branch; QC re-test `APPROVED` with `REPRODUCTION_PROOF` + `QC_REPORT` → `verified` → `COMPLETE`.
11. **Completion.** Feature `INTEGRATION` → feature CI on the new head green → `QC`; feature QC visit 2 `APPROVED` → `QC_ACCEPTED` → `qc_passed` → `COMPLETE`; one pending `PROTECTED_ACTION` approval for `git.merge_protected` (feature → `main`) is left pending (release decision).
12. **Quiescence.** `run_until_idle` returns; a final `IntegrationManager.reconcile(since=None)` ingests the provider rows and produces no transition and no `EXTERNAL_REJECTED` row (kernel and provider agree).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a `ScriptBook` with entries for two visits of the same (role, purpose, item) When called three times Then visits 1, 2 served and the third raises `AssertionError` naming the key; `writes_files=False` runs leave the worktree clean; `path_template` uses `{item}` | `tests/fakes/test_fake_model_adapter_scriptbook.py::test_scriptbook_dispatch_and_new_script_fields` |
| 2 | Given the scenario When finished Then `FEAT-0001`, `STORY-0001`, `STORY-0002`, `BUG-0001` are `COMPLETE`, feature `fix_loops == 1`, stories `fix_loops == 0`, bug `reopen_count == 0` | `tests/e2e/test_e03_gate.py::test_final_states` |
| 3 | Given the feature Then the transition chain is `IDEA→DISCOVERY→DESIGN→READY→IMPLEMENTING→INTEGRATION→QC→REWORK→IMPLEMENTING→INTEGRATION→QC→COMPLETE` with events and actor roles per INTERFACES §3.1 | `tests/e2e/test_e03_gate.py::test_feature_transition_chain` |
| 4 | Given each story Then chain `IDEA→READY→IMPLEMENTING→READY_FOR_REVIEW→LEAD_DEV_REVIEW→INTEGRATION→QC→COMPLETE` with `ready` by LEAD_DEV, `submit_for_review` by SENIOR_DEV, `review_approved` by LEAD_DEV, `integration_passed` by KERNEL, `qc_passed` by QC | `tests/e2e/test_e03_gate.py::test_story_transition_chains` |
| 5 | Given the bug Then chain `IDEA→DISCOVERY→READY→IMPLEMENTING→READY_FOR_REVIEW→LEAD_DEV_REVIEW→INTEGRATION→QC→COMPLETE`, `found_in_run_id` = feature QC visit 1, `related_feature_id = FEAT-0001` | `tests/e2e/test_e03_gate.py::test_bug_loop_chain` |
| 6 | Given the feature Then `done_dimensions` has `FUNCTIONAL`, `INTEGRATED`, `TESTED`, `QC_ACCEPTED` all true and each set evidence id resolves to an `evidence` row of the expected kind | `tests/e2e/test_e03_gate.py::test_done_dimensions_with_evidence` |
| 7 | Given every REVIEW, QC and TRIAGE run Then its role differs from the item's implementer role and its `model_id` (`fake-claude/sim`) differs from the implementer model (`fake-codex/sim`); `MODEL_SELECTED` payloads for REVIEW/QC list `["fake-codex/sim", "cross_model_review"]` in `rejected` | `tests/e2e/test_e03_gate.py::test_invariant_4_role_and_model_separation` |
| 8 | Given the ledger Then counts: `WORK_ITEM_CREATED == 4`, `BUG_CREATED == 1`, `QC_RESULT == 5`, `PR_OPENED == 4`, `MERGED == 3`, `AGENT_RUN_STARTED` by role `ORCHESTRATOR 2, LEAD_DEV 5, SENIOR_DEV 3, QC 5`, `MODEL_FALLBACK == 0`, `ERROR == 0`, and every `WORK_ITEM_TRANSITION` has a matching `work_item_transitions` row | `tests/e2e/test_e03_gate.py::test_ledger_trail` |
| 9 | Given the two story IMPLEMENT runs Then both `AGENT_RUN_STARTED` events come from the same tick and their run intervals overlap, in worktrees on different branches | `tests/e2e/test_e03_gate.py::test_story_implementations_ran_in_parallel` |
| 10 | Given git Then `feat/FEAT-0001-double-jump` contains exactly one commit each `story(STORY-0001)`, `story(STORY-0002)`, `bug(BUG-0001)` with trailer `Walk-Work-Item`, the bare remote has the three item branches, `main` is unchanged, and `.walk/prs/` holds four stubs (three merged, feature → main unmerged) | `tests/e2e/test_e03_gate.py::test_git_history_and_prs` |
| 11 | Given `.ai/` Then `features/FEAT-0001.md` has non-empty `Intent`, `Architecture`, `Relevant Files`, `QC Notes` and `Current Status` starting `Complete`; `bugs/BUG-0001.md` has `Root Cause`, `Fix`, `Verification`; every evidence file referenced by the ledger exists under `.ai/features/…/evidence/` or `.ai/bugs/…/evidence/` | `tests/e2e/test_e03_gate.py::test_ai_documents` |
| 12 | Given `.walk/work/LOCAL-1..4.md` Then every status is `COMPLETE`, LOCAL-2/3 have PARENT `LOCAL-1`, LOCAL-4 RELATES `LOCAL-1`, comments include `Review approved`, `QC REJECTED`, `Triaged:`, `Verified` | `tests/e2e/test_e03_gate.py::test_work_provider_mirror` |
| 13 | Given the end state When `IntegrationManager.reconcile(since=None)` Then no new transition rows and no `EXTERNAL_REJECTED` source anywhere | `tests/e2e/test_e03_gate.py::test_provider_reconcile_is_noop` |
| 14 | Given the end state When `walk --repo <tmp> status --json` and `walk approvals --pending --json` Then no active runs, no blocked items, exactly one pending `PROTECTED_ACTION` with action `git.merge_protected` | `tests/e2e/test_e03_gate.py::test_status_and_pending_merge_approval` |
| 15 | Given `run_until_idle` Then it finished in ≤ 300 ticks and the `ScriptBook` served every scripted entry exactly once (no unused script, no unexpected run) | `tests/e2e/test_e03_gate.py::test_script_book_fully_consumed` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e03_gate.py` (14 passed) and `tests/fakes/test_fake_model_adapter_scriptbook.py`.
- Transcript on the scenario repo kept by `pytest --basetemp=<dir>`: `walk work show FEAT-0001`, `walk work list --json`, `walk ledger query --kind QC_RESULT --kind BUG_CREATED --kind MERGED`, `git -C <repo> log --oneline feat/FEAT-0001-double-jump`, `cat .ai/features/FEAT-0001.md`.

#### Notes
- §131 MVP workflow, §136 rows "Jira work created · Agents assigned · Implementation begins" and "Agents review each other · QC independently validates · Bugs re-enter workflow" (WBS §9); WBS §3.6 (e2e uses fakes + real temp git repo); E04-S15 reuses `e03_scenario` up to step 5.
- `NEW NAME:` `ScriptBook`, `FakeScript.path_template`, `FakeScript.writes_files`, `FakeScript.evidence_files`, `E03Scenario`, fixtures `e03_scenario`, `e03_policies`, helper `run_until_idle`.
- Item ids `FEAT-0001`, `STORY-0001`, `STORY-0002`, `BUG-0001` follow per-prefix `id_sequences` (DOMAIN-MODEL §2); provider refs `LOCAL-1` (feature), `LOCAL-2`/`LOCAL-3` (stories), `LOCAL-4` (bug).
- This story's commit touches tests only; any production fix needed is a separate bugfix story (`E03-Bxx`) linked from E03-R01.
- Pitfall: `run_until_idle` must await integration-step tasks as well as agent runs, otherwise the test exits while a merge is in flight and becomes flaky.
- Commit subject: `feat: add epic 03 gate e2e for mvp workflow (E03-S19)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-S20 — Epic gate part 2: §132 failover e2e (fake Codex → fake Claude)

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §6.2, §21, §22, §41, §89, §132, §136, §137 (Invariants 1, 2, 12)
**Depends on:** E03-S19, E01-S28
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end test proves the §132 failover inside the §131 workflow: a SENIOR_DEV implementation on `fake-codex` is interrupted by a kernel crash after its second periodic checkpoint; on restart, with the Codex provider unhealthy, recovery hands the run over to `fake-claude` in the **same role**, with a structured handover read from `.ai/handovers/`, on the same branch HEAD; the continuing run finishes the story, which then goes through cross-model review, integration and QC to `COMPLETE` — proving persistent context, role-model separation, fallback and handover.

#### Scope
- In: `tests/e2e/test_e03_failover.py`; `e03_failover_scenario` fixture (single-story plan) and crash/restart helpers; `interrupt_after_tool_calls` and hang support in the fake adapter; a test-only abandon switch on `KernelHandle.close`.
- Out: stale-context detection and `.ai/`-only knowledge after restart (E04-S15 extends this scenario); native session resume on the same model (E01-S28 unit tests); budget/context-overflow fallbacks (E01-S28).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/test_e03_failover.py` | create | — |
| `tests/e2e/conftest.py` | modify | fixture `e03_failover_scenario`; `FailoverScenario`; helpers `simulate_crash`, `restart_kernel` |
| `tests/fakes/fake_model_adapter.py` | modify | `FakeScript.hang_after_tool_calls`, `FakeModelAdapter.hung`, `interrupt_after_tool_calls` |
| `tests/fakes/test_fake_model_adapter_interrupt.py` | create | — |
| `src/walk/cli/composition.py` | modify | `KernelHandle.close(abandon_runs: bool = False)` |

#### Interface contract
Recovery per ARCHITECTURE §5.3 and fallback per `INTERFACES.md` §5.3 (E01-S28); `Handover` per DOMAIN-MODEL §4.2; `.ai/handovers/HO-NNNN.md` per ARCHITECTURE §8. Additions:

```python
# tests/fakes/fake_model_adapter.py
class FakeScript(WalkModel):                         # + one field
    hang_after_tool_calls: int | None = None         # after this many tool calls: set adapter.hung, then await forever (simulated hung process)
class FakeModelAdapter:
    hung: asyncio.Event                              # set when a run hangs (test synchronisation)
def interrupt_after_tool_calls(n: int, *, base: FakeScript) -> FakeScript: ...   # copy of base with hang_after_tool_calls=n (reused by E04-S15)

# src/walk/cli/composition.py
class KernelHandle:
    async def close(self, *, abandon_runs: bool = False) -> None:
        """abandon_runs=True (tests only): cancel kernel tasks without checkpoints or run-state changes, close the DB and release
        KernelLock — the on-disk state equals a killed process. Default False = current graceful close."""

# tests/e2e/conftest.py
class FailoverScenario(WalkModel):                   # arbitrary_types_allowed
    first: E03Scenario                               # handle before the crash (closed)
    second: KernelHandle                             # restarted kernel, new kernel_instance
    story_id: str
    interrupted_run_id: str
    checkpoint2_head: str                            # head_sha of the second PERIODIC checkpoint, captured before the crash
async def simulate_crash(scenario: E03Scenario) -> None: ...          # await codex.hung; handle.close(abandon_runs=True)
async def restart_kernel(scenario: E03Scenario) -> KernelHandle: ...  # build_kernel with the same repo/adapters, new kernel_instance
```

#### Behavior
Scenario (module-scoped fixture `e03_failover_scenario`; each test asserts one facet):
1. **Setup and plan.** Same setup and policies as E03-S19 (`checkpoint_every_tool_calls = 10`); the PLAN script creates one story `STORY-0001` "Double jump physics"; discovery and design as in E03-S19 → story `READY`.
2. **Codex implementation.** SENIOR_DEV/IMPLEMENT on `fake-codex/sim` with `interrupt_after_tool_calls(20, base=FakeScript(tool_calls=30, path_template="Assets/Scripts/Jump/Codex{i}.cs"))`: checkpoints `START` (seq 1), `PERIODIC` (seq 2, after call 10), `PERIODIC` (seq 3, after call 20) each with a WIP commit; then the adapter hangs. "Checkpoint 2" in the gate text = the second `PERIODIC` checkpoint; the fixture records its `head_sha` as `checkpoint2_head`.
3. **Crash.** `simulate_crash`: the run row stays `RUNNING` with the old `kernel_instance`; no `AGENT_RUN_ENDED`, no `END` checkpoint.
4. **Restart with Codex down.** `codex.set_healthy(False)`; `restart_kernel` → startup recovery (ARCHITECTURE §3.4 step 5, §5.3): old run → `INTERRUPTED` (ledger `ERROR{kind: INTERRUPTED}`); native resume impossible (provider unhealthy) → handover built from the checkpoint and written to `.ai/handovers/HO-0001.md`; `ModelRouter` selects `fake-claude/sim` (fallback, `MODEL_FALLBACK{trigger: PROVIDER_OUTAGE, from: fake-codex/sim}`); new run started with `handover`, `parent_run_id` = old run; old run ends `HANDED_OVER`; `RECOVERY_RESUMED` written.
5. **Claude continues.** The new run is SENIOR_DEV on `fake-claude/sim` with script `FakeScript(tool_calls=10, path_template="Assets/Scripts/Jump/Claude{i}.cs")` whose output lists only its own 10 files in `changes`; its worktree starts at `checkpoint2_head` on `story/STORY-0001-double-jump-physics`; the run completes → kernel commit → `READY_FOR_REVIEW`.
6. **Provider recovers; rest of §131.** After the new run started the fixture sets `codex.set_healthy(True)`; the review is routed to LEAD_DEV on `fake-codex/sim` (cross-model against the latest implementer `fake-claude/sim`), `APPROVED`; integration squashes all WIP and final commits into one `story(STORY-0001): …` commit, CI green, merged into the feature branch; story QC on `fake-codex/sim` `APPROVED` → `COMPLETE`; feature CI green, feature QC `APPROVED` → feature `COMPLETE`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `interrupt_after_tool_calls(3, base=…)` When the fake runs Then exactly 3 `TOOL_CALL_RESULT` events, `hung` is set, no `FINAL_OUTPUT`, and cancelling the consumer ends the generator without emitting `ENDED` | `tests/fakes/test_fake_model_adapter_interrupt.py::test_interrupt_after_tool_calls_hangs_without_final_output` |
| 2 | Given the crash When the DB is inspected before restart Then the codex run is `RUNNING` with the old `kernel_instance`, has checkpoints seq 1–3 (`START`, `PERIODIC`, `PERIODIC`) and the story branch HEAD equals `checkpoint2_head` | `tests/e2e/test_e03_failover.py::test_crash_leaves_running_run_and_wip_commits` |
| 3 | Given the restart Then the old run is `HANDED_OVER` after an `ERROR{kind: INTERRUPTED}` event, and the ledger has exactly one `RECOVERY_RESUMED`, one `MODEL_FALLBACK{trigger: PROVIDER_OUTAGE, from: fake-codex/sim}` and one `HANDOVER_CREATED` | `tests/e2e/test_e03_failover.py::test_recovery_ledger_trail` |
| 4 | Given the new run Then `role == SENIOR_DEV`, `model_id == fake-claude/sim`, `provider == fake-claude`, `parent_run_id` = interrupted run, `handover_in_id == HO-0001` | `tests/e2e/test_e03_failover.py::test_same_role_different_model_continues` |
| 5 | Given the new run's `AgentInput.handover` Then it equals `from_document(read .ai/handovers/HO-0001.md)`, `from_model_id == fake-codex/sim`, `worktree_head == checkpoint2_head`, `branch` = story branch, `modified_files` = the 20 `Codex{i}.cs` paths, non-empty `remaining_work` and `next_action`, and the document contains no `thinking` text | `tests/e2e/test_e03_failover.py::test_handover_document_contents` |
| 6 | Given the new run's worktree at start Then HEAD equals `checkpoint2_head` and the 20 codex files are present | `tests/e2e/test_e03_failover.py::test_continuation_starts_from_checkpoint_head` |
| 7 | Given `.ai/features/FEAT-0001.md` Then the `Architecture` written by LEAD_DEV before the crash is byte-identical after restart and the new run's `AgentInput.context` contains the feature document | `tests/e2e/test_e03_failover.py::test_persistent_context_survives_restart` |
| 8 | Given the story review Then it ran on `fake-codex/sim` for role LEAD_DEV (implementer model = `fake-claude/sim`) | `tests/e2e/test_e03_failover.py::test_cross_model_review_after_failover` |
| 9 | Given the end state Then `STORY-0001` and `FEAT-0001` are `COMPLETE`, the feature branch has one `story(STORY-0001): …` commit whose tree contains all 20 `Codex{i}.cs` and 10 `Claude{i}.cs` files, and the story branch's pre-squash history (captured by the fixture) had `wip(STORY-0001): checkpoint …` commits from both runs | `tests/e2e/test_e03_failover.py::test_story_and_feature_complete_with_combined_work` |
| 10 | Given both kernels' ledgers (same DB) Then `AGENT_RUN_STARTED` for SENIOR_DEV is 2 (codex, claude), the `HANDOVER_CREATED` payload `from_run_id`/`to_run_id` link the two runs, and `walk handover show STORY-0001` prints `HO-0001` with reason `RECOVERY` | `tests/e2e/test_e03_failover.py::test_handover_traceability_cli` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e03_failover.py` (9 passed) and `tests/fakes/test_fake_model_adapter_interrupt.py`.
- Transcript on the scenario repo (`pytest --basetemp=<dir>`): `walk runs list --item STORY-0001`, `walk handover show STORY-0001`, `cat .ai/handovers/HO-0001.md`, `walk ledger query --kind RECOVERY_RESUMED --kind MODEL_FALLBACK --kind HANDOVER_CREATED`.

#### Notes
- §132 success criteria (persistent context, role-model separation, fallback, handover); WBS §9 row "Context persists · Model fallback works" (E03-S20, E04-S15); ARCHITECTURE §5.3 resume algorithm, INTERFACES §5.3 steps 5–10; ADR-0004 (no chain-of-thought in handovers), ADR-0002 (WIP commits make checkpoints durable).
- `NEW NAME:` `FakeScript.hang_after_tool_calls`, `FakeModelAdapter.hung`, `interrupt_after_tool_calls` (reused by E04-S15), `FailoverScenario`, `e03_failover_scenario`, `simulate_crash`, `restart_kernel`, `KernelHandle.close(abandon_runs=...)`.
- `KernelHandle.close(abandon_runs=True)` is the only production change: a killed process cannot be simulated in-process otherwise. If E01-S28/S30 already provide an equivalent abandon hook, use it and drop the `composition.py` row (say so in the commit body). Any other production defect → bugfix story `E03-Bxx`.
- Handover reason: this gate expects `RECOVERY` (handover built during startup recovery). If E01-S28 records `FALLBACK` for the recovery-with-unhealthy-provider path, align E01-S28 and this assertion through a bugfix story rather than loosening the test.
- E04-S15 runs this scenario up to step 3, then edits a `relevant_files` entry before step 4.
- Cross-epic alignment: E04-S15 Behavior 1 says "checkpoint `seq == 2` … tool call 20" and stops the kernel with `Orchestrator.stop(drain=False)`. With the `START` checkpoint at seq 1 the checkpoint after call 20 is seq 3, and `stop()` checkpoints and pauses runs (INTERFACES §1.1), which recovery does not treat as interrupted (ARCHITECTURE §5.3 step 1). E04-S15 must use `simulate_crash` and seq 3 — fix E04-S15's text before it starts (non-blocking for E03).
- Commit subject: `feat: add epic 03 failover gate e2e codex to claude (E03-S20)`.

#### Evidence (filled by implementer)
_pending_

---

### E03-R01 — Review E03 (incl. ADR-0006 Codex residual-risk re-evaluation)

**Status:** TODO
**Type:** docs
**Requirements:** §6.3, §6.4, §6.5, §23, §31, §55–§65, §91, §131, §132, §137 (Invariants 3, 4, 6), §138 (Infinite Fix Loop)
**Depends on:** E03-S20
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (a different model than the implementer of the majority of E03 stories) verifies E03-S01…S20 against the Definition of Done and Invariants 3, 4 and 6, confirms both epic-gate tests are green and stable, records the ADR-0006 Codex residual-risk re-evaluation that ADR-0006 schedules as a "Stage 3 review item", and files every defect as an `E03-B*` bugfix story.

#### Scope
- In: review of E03-S01…S20 commits; Invariants 3, 4, 6; ledger write-point and idempotency audits over the E03 code; gate stability; Jira parity run when a tenant is available; ADR-0006 D-5 re-evaluation recorded in ADR-0006 (or a superseding ADR); cross-epic text inconsistencies found while reviewing (reported, not fixed in other epic files); bugfix story creation.
- Out: fixing defects (bugfix stories `E03-B*`); re-planning E04+ (planner; inconsistencies are listed in this task's Evidence for E04's owner); implementing new Codex controls (a superseding ADR names the follow-up work, which the planner schedules).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-03-coding-workflow.md` | modify | — (this task's Evidence; appended `E03-B*` stories) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows for E03-R01 and any `E03-B*`; §6 register rows for `NEW NAME:` items of E03-S09…S20 not yet listed) |
| `docs/01-architecture/adr/ADR-0006-permission-enforcement-at-tool-boundary.md` | modify | — (dated section "Re-evaluation 1 (E03-R01)": Codex version checked, findings, decision keep/supersede) |
| `docs/01-architecture/adr/ADR-00NN-codex-per-call-authorisation.md` | create (only if the re-evaluation supersedes D-5) | — (next free ADR number after ADR-0014) |

#### Interface contract
Reviewer protocol: `docs/00-governance/IMPLEMENTATION-PROTOCOL.md` "Reviewer protocol" steps 1–5. Per-story checklist: DoD "Code", "Tests", "Documentation", "Evidence", "Delivery" boxes; every acceptance-criteria row's test exists by exact node id and passes (`uv run pytest <nodeid>`); Files-table conformance of `git show --stat <sha>`; every `NEW NAME:` of the story present in WBS §6 or added by this task; every story that changed a contract updated `INTERFACES.md`/`DOMAIN-MODEL.md` in the same commit (E03-S11 `run_pipeline` kwarg, E03-S12 `merge_base`, E03-S15 `TriageVerdict`/`AgentOutput` fields, E03-S17 `children_states`/`open_blocker_bug_count`).

ADR-0006 re-evaluation record (section appended to ADR-0006):
```text
## Re-evaluation 1 (E03-R01, <date>)
Codex CLI version checked: <codex --version>; per-call approval / tool-authorisation hook available: yes|no (<evidence: `codex exec --help` excerpt or release note>)
E03 exposure: Codex runs in E03 gates: <n>; BoundaryAuditor rejections in tests: <n> (tests listed); TOOL_DENIED for Codex native tools: n/a (not pre-authorisable)
Residual risk: unchanged | reduced | increased — <reason>
Decision: keep D-5 as accepted residual risk until <trigger> | supersede D-5 by ADR-00NN
```

#### Behavior
1. Reviewer selection: different agent instance and model than the implementer of ≥ 50 % of E03 stories (IMPLEMENTATION-PROTOCOL, §23); recorded in Evidence.
2. For every story S01–S20: `git show <sha>` touches only Files-table paths (or the commit body justifies extras); public symbols match the Interface contract; each AC test exists by exact name and passes; coverage ≥ 90 % for touched modules (`uv run pytest --cov=walk --cov-report=term-missing`); one row per story in the Evidence table (story → sha → DoD result → defects).
3. Gates: `uv run pytest tests/e2e/test_e03_gate.py tests/e2e/test_e03_failover.py` passes three consecutive times on `main` with identical results (no flakiness); total duration recorded.
4. Invariant 3 (Work State ≠ Project Knowledge): `lint-imports` passes with the `workflow`/`memory` sibling contract; no `walk.integrations` module imports `walk.memory`; no `WorkProvider` call inside `src/walk/memory/`; no `.ai/` write from the ingest path (`IntegrationManager.ingest`, `WorkPoller`) — grep results pasted.
5. Invariant 4 (Implementation ≠ Verification): every REVIEW/QC/TRIAGE run in both gates has a role different from the implementer and, with `cross_model_review` on, a different model; `READ_ONLY_PURPOSES` enforced (E03-S13 test); no code path raises `review_approved`, `qc_passed`, `verified` with an actor other than the table's allowed role (grep for `raise_event(` call sites with literal events; each call site listed).
6. Invariant 6 (Feature Complete ≠ Code Complete): the only path to feature `COMPLETE` is `qc_passed` with `all_applicable_dimensions_done`; no direct `state` update of `work_items` outside `walk.workflow` (grep `UPDATE work_items` and `.state =`); done dimensions in the gate carry evidence ids that resolve.
7. Ledger write points: every `LedgerManager.append`/`ledger.append(` call site in `src/walk/` maps to a row of ARCHITECTURE §4.3 (E03 additions: `GitCliProvider` PR/merge, `LocalCiProvider` build/test, `QcFlow`/`BugIntake` QC/bug); hooks write no ledger events except via `HookManager` (WBS §3.5).
8. Idempotency: every external write introduced in E03 (provider create/transition/comment/assign/link, git branch/commit/PR/merge, CI jobs, handovers, escalation resolution) uses a key from ARCHITECTURE §5.4 or a key registered as `NEW NAME:`; the replay tests (E03-S08 AC 14, E03-S12 AC 6, E03-S14 AC 6) pass.
9. Jira parity: with a Jira test tenant available, `WALK_TEST_JIRA=1 uv run pytest -m integration tests/integrations/jira/test_jira_contract.py` passes; otherwise "not run — no tenant" is recorded (not a defect).
10. ADR-0006 Codex residual-risk re-evaluation: (a) run `codex --version` and `codex exec --help` (or read the CLI release notes) and record whether a per-call approval/authorisation hook exists; (b) list the E03 tests that exercise `BoundaryAuditor`/`FAILED_BOUNDARY` for Codex-style runs (E03-S08 AC 5–6, E03-S13 AC 11) and confirm they pass; (c) confirm Codex runs keep `workspace-write`, network off and a scrubbed environment in the E03 composition (`CodexAdapter.configure_sandbox` call site); (d) decide: no hook → keep D-5, append the re-evaluation record with the next trigger ("re-check at E07-X01 or on the next Codex major release"); hook available → create the superseding ADR proposing `CodexAdapter` per-call authorisation through `ToolInvoker.authorize`, mark D-5 "Superseded by ADR-00NN", and list the follow-up implementation as an open item for the planner (no story is added to a later epic by this task).
11. Cross-epic findings (e.g. E04-S15's checkpoint numbering and stop/crash wording versus E03-S20) are listed in Evidence with the exact text to change; they are not edited in other epic files by this task.
12. Each defect → one `E03-Bnn` story using STORY-TEMPLATE, `Depends on: E03-R01`, linked from this task's Evidence; `BLOCKER` severity noted when it breaks a gate test or an invariant. E04 may start only when no `BLOCKER` `E03-B*` story is open (WBS §2 rule 2).
13. Commit `docs: review epic 03 stories s01-s20 (E03-R01)` and push.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each story commit When diffed against its Files table Then no unlisted file without justification | manual checklist recorded in Evidence |
| 2 | Given the §131 gate When run three times on `main` Then green each time with identical results | `tests/e2e/test_e03_gate.py::test_final_states` |
| 3 | Given the §132 gate When run three times on `main` Then green each time | `tests/e2e/test_e03_failover.py::test_same_role_different_model_continues` |
| 4 | Given both gates Then every REVIEW/QC/TRIAGE run differs from the implementer in role and model (Invariant 4) | `tests/e2e/test_e03_gate.py::test_invariant_4_role_and_model_separation` |
| 5 | Given the feature end state Then all applicable dimensions are set with resolvable evidence (Invariant 6) | `tests/e2e/test_e03_gate.py::test_done_dimensions_with_evidence` |
| 6 | Given the end state When reconciling the work provider Then no transition and no `EXTERNAL_REJECTED` (kernel and provider agree, Invariant 3) | `tests/e2e/test_e03_gate.py::test_provider_reconcile_is_noop` |
| 7 | Given `src/walk/` When import contracts and the grep audits of Behavior 4–7 run Then zero violations | manual checklist recorded in Evidence |
| 8 | Given the fix-loop limit When QC rejects past `max_fix_loops` Then the item blocks and a `ROOT_CAUSE_REVIEW` request exists (§138) | `tests/orchestrator/test_circuit_breaker.py::test_story_blocks_at_fix_loop_limit` |
| 9 | Given ADR-0006 When the re-evaluation is done Then a dated "Re-evaluation 1 (E03-R01)" section with Codex version, evidence and decision exists (and, if superseded, the new ADR is linked from D-5) | manual checklist recorded in Evidence |
| 10 | Given the boundary audit for Codex-style runs Then the forbidden-path and read-only-role tests pass | `tests/runtime/test_output_applier_full.py::test_forbidden_path_change_fails_boundary_without_commit` |

#### Evidence required
- Gate output of the full suite on `main` after E03-S20, plus three consecutive runs of both e2e gate modules.
- Table: story → sha → DoD result → defects (ids); reviewer agent/model vs implementer models.
- Grep/import-linter transcripts for Behavior 4–8.
- `codex --version` and the `codex exec --help` excerpt used for the re-evaluation; the ADR-0006 diff.
- Jira parity result or "not run — no tenant".
- List of cross-epic inconsistencies with proposed text.

#### Notes
- Reviewer must be a different agent instance/model than the implementer of ≥ 50 % of E03 stories (IMPLEMENTATION-PROTOCOL "Reviewer protocol", §23).
- ADR-0006 Consequences: "Codex residual risk must be re-evaluated when `codex` gains per-call approval hooks (tracked as a Stage 3 review item)" — this task is that item; ADR-0006 D-5 records the accepted residual risk; ADR-0014 (E01-S02 spike) holds the Codex flags verified at Stage 1 and is the baseline for the comparison.
- Do not fix in place; create `E03-B*` stories. The superseding ADR (if any) is a decision record only.
- Commit subject: `docs: review epic 03 stories s01-s20 (E03-R01)`.

#### Evidence (filled by implementer)
_pending_

---

