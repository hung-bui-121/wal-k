# ADR-0006 — Permission Enforcement at the Tool Boundary

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§31: permissions must be enforceable by the kernel, not only prompts, with allow / deny / conditional effects. §91–§92: least privilege, tool allowlist, repository boundary, protected branches, secret isolation, command restrictions, protected actions requiring user approval. §63: QC may create bugs but implementers may not close their own work (Invariant 4). Provider capabilities differ: the Claude Agent SDK offers a per-call `can_use_tool` hook; `codex exec` offers only sandbox configuration.

## Decision

**D-1 Policy vs enforcement.** Policy (`PermissionRule`, `ProtectedAction`, evaluation `decide()`) lives in `walk.permissions`. Enforcement happens at four kernel-controlled points, listed in `ARCHITECTURE.md` §4.2: `ToolInvoker.invoke` (kernel tools), `ClaudeAdapter.can_use_tool → ToolInvoker.authorize` (Claude native tools), `CodexAdapter.configure_sandbox` + `BoundaryAuditor` (Codex native tools), and `GitProvider` guard hooks + protected-branch checks (all providers).

**D-2 Agents do not perform side effects outside the worktree; the kernel does.** Commits, pushes, PRs, merges, Jira creates/transitions/comments, Unity builds and asset generation are executed by the kernel from structured `AgentOutput` intents (`changes`, `new_bugs`, `new_tasks`, `decisions`, `evidence`) and workflow events. Consequently agents never hold Jira/Git-remote/store credentials (§91 secret isolation), and the permission check for those operations is evaluated against the *acting role* inside `OutputApplier`/`ToolInvoker` (e.g. `jira.create_bug` ALLOW for QC, DENY for SENIOR_DEV; `review.approve` only LEAD_DEV).

**D-3 Rule semantics.** `PermissionRule(role, tool pattern, effect, command_patterns, path_patterns, approver)`. Evaluation: collect rules for role whose `tool` pattern matches (exact > dotted prefix glob > `*`); among the most specific, `DENY > REQUIRE_APPROVAL > ALLOW`; shell commands must match an ALLOW `command_patterns` entry and no DENY entry; file paths must be inside the worktree and match `path_patterns` if given. No matching rule → DENY (default deny). Protected actions (§92) are `REQUIRE_APPROVAL` with `approver=USER` and cannot be downgraded by project config.

**D-4 Conditional = approval request.** `REQUIRE_APPROVAL` creates an `ApprovalRequest`, pauses the run (`PAUSED_FOR_APPROVAL`, checkpoint `PAUSE`), fires `ON_PROTECTED_ACTION_REQUESTED`; `walk approve|deny` resolves it; timeout (`approval_timeout_s`, default 24 h) → DENY.

**D-5 Codex compensating controls.** Because Codex tool calls cannot be pre-authorised: sandbox `workspace-write` with `cwd=worktree`, network disabled by default (enabled per role only when `ToolSpec.requires_network` tools are allowed), scrubbed environment (no credentials), git guard hooks installed in the worktree (block protected-branch commits/pushes), and a mandatory post-run `BoundaryAuditor` pass over `git status`/diff: any write outside `allowed_paths` or matching `forbidden_paths` (`.ai/**` except evidence folders, `.walk/**`, `**/*.env`, `ProjectSettings/*Secrets*`) → run `FAILED_BOUNDARY`, changes reverted, `TOOL_DENIED` ledger event, improvement observation. Shell command restrictions for Codex are therefore *advisory* (prompt) + *post-hoc* (audit); this residual risk is accepted for MVP and recorded here.

**D-6 Default rule set** (kernel `walk/permissions/defaults.yaml`, overridable in `.ai/agents/permissions.yaml`):

| Role | ALLOW | DENY | REQUIRE_APPROVAL |
|---|---|---|---|
| SENIOR_DEV | file tools in worktree; `bash` for build/test/graph commands; `git.commit` (via kernel) | `git.merge_protected`, `git.push_protected`, `jira.close_feature`, `review.approve`, `rm -rf`, `git push --force`, network fetch | — |
| LEAD_DEV | as SENIOR_DEV + `review.approve`, `review.reject`, `jira.create_task` | `jira.close_feature` (QC only) | `git.merge_protected` (approver USER) |
| QC | read tools; `bash` test/run commands; `jira.create_bug`, `jira.reopen`, `qc.approve`, `qc.reject` | file write tools (QC does not fix code) | `jira.close_feature` → ALLOW via `qc_passed` event only |
| ORCHESTRATOR | `jira.create_*`, `jira.transition`, `work.plan` | all file write tools | `permissions.alter`, `phase.*` user-only |
| PRODUCT_OWNER / DESIGN_LEADER / ART_DIRECTOR | read tools; decision recording in own scope | file write tools | `monetization.change` (USER) |
| all | — | `credentials.change`, `repo.delete_data`, `store.publish`, `jira.delete` unless approved | those same actions require USER approval |

**D-7 Audit.** Every decision produces `TOOL_INVOKED` (ALLOW) or `TOOL_DENIED` (DENY) ledger events with the matched rule; approvals produce `APPROVAL_REQUESTED/DECIDED`.

## Alternatives

- **Prompt-only permissions:** rejected — §31 explicitly forbids relying on prompts.
- **Kernel MCP server exposing Jira/Git tools to agents:** deferred to Stage 5+ — adds a network surface and per-provider plumbing; kernel-applied intents cover MVP needs with fewer moving parts.
- **Containers for every run:** deferred (ADR-0009 §D-5) — Unity projects are large; worktree + sandbox mode is sufficient for MVP.
- **Allow Codex network access by default:** rejected — undermines secret isolation.

## Consequences

- `AgentOutput.changes` must match the real diff; `OutputApplier` reconciles against `git status` and logs discrepancies as findings.
- Review/QC verdicts are workflow events raised by the kernel from `AgentOutput.status ∈ {APPROVED, REJECTED}` with the role check in the transition table, which is how Invariant 4 is enforced mechanically.
- Codex residual risk must be re-evaluated when `codex` gains per-call approval hooks (tracked as a Stage 3 review item).

## Related requirements

§8, §30–§31, §63, §77, §91–§93, §137 (Invariants 4, 7, 9, 14), §139 "sandbox technology".
