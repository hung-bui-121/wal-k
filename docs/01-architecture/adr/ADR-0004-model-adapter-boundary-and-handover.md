# ADR-0004 — Model Adapter Boundary and Handover Format

**Status:** Proposed (owner confirmation required before Stage 1)
**Date:** 2026-10-05
**Deciders:** Project owner, system architect

## Context

§6.1 and Invariant 1 require role and model to be independent; §12, §128 require Claude and Codex behind adapters; §21–§22 require first-class fallback with a structured handover that never serialises private chain-of-thought; §126 defines the structured agent input/output contract; §139 leaves "exact model adapter API" open. ADR-0001 fixed the concrete drivers: Claude via `claude-agent-sdk` (Python, in-process), Codex via `codex exec --json` subprocess.

Two provider realities shape the boundary: the Claude Agent SDK exposes a per-tool-call authorisation callback and session resume; `codex exec` is a non-interactive CLI with sandbox modes and thread resume but no per-call callback.

## Decision

**D-1 One `ModelAdapter` protocol** (`INTERFACES.md` §2.1) with: `descriptors()`, `health()`, `map_effort()`, `run(AgentInput, RunSession) -> AsyncIterator[AgentEvent]`, `resume(ProviderSessionRef, …)`, `cancel()`, `usage()`, `skill_projector()`, `parse_output()`. Adapters are stateless with respect to role and workflow; they receive everything through `AgentInput`.

**D-2 Normalised event stream.** Adapters translate provider streams into `AgentEvent` (`STARTED, TEXT, TOOL_CALL_REQUESTED, TOOL_CALL_RESULT, CHECKPOINT_HINT, USAGE, PARTIAL_OUTPUT, FINAL_OUTPUT, ERROR, ENDED`). Thinking/reasoning blocks are dropped at the adapter boundary and never appear in any event (§22). `TEXT` is logged to diagnostics only, never persisted in the ledger or memory.

**D-3 Structured output contract.** The run's deliverable is an `AgentOutput` JSON object (§126). Adapters may use native structured-output features where available; the **mandatory fallback channel** is the file `<worktree>/.walk/output.json`, which the kernel prompt instructs the agent to write last. `parse_output` validates with pydantic; on failure the executor issues one repair turn quoting the field errors; a second failure maps to `FallbackTrigger.REPEATED_OUTPUT_INVALID`.

**D-4 Prompt assembly is kernel-owned.** The system prompt = rendered `Constitution` (identity, mission, responsibilities, authority, bias, beliefs, principles, evidence preferences, conflict behaviour, forbidden actions) + project constitution + task template (`walk/agents/templates/<purpose>.md.j2`, versioned as `BehaviorVersion kind=PROMPT`). The user message = serialised `AgentInput` sections in §40 order. Adapters add only provider-mechanical wrappers (e.g. Codex `AGENTS.md` projection of skills).

**D-5 Handover format** is the `Handover` model (§22 fields verbatim: Task, Current State, Completed Work, Modified Files, Findings, Hypotheses, Decisions, Risks, Remaining Work, Next Action) plus `worktree_head`, `branch`, `reason`, `from_model_id`. It is built by `CheckpointManager.build_handover` from kernel-observed facts (run's accumulated `Finding`s, `git diff --name-only`, recorded decisions) and the agent's last `PARTIAL_OUTPUT`/`AgentOutput.handover` — never from transcripts. A new run receives it as `AgentInput.handover`, and the task template instructs the agent to continue from `next_action`.

**D-6 Provider-side resume is an optimisation, not the contract.** `ProviderSessionRef` (Claude session id, Codex thread id) is stored in checkpoints; `resume()` is attempted only for the same model when healthy. Correctness never depends on it.

**D-7 Claude adapter specifics.** Uses `claude-agent-sdk` `query()` with: `cwd = worktree`, `allowed_tools` from `RunSession.allowed_tools`, `permission_mode` restricted, `can_use_tool` callback → `RunSession.permission_authorizer` (the kernel's `ToolInvoker.authorize`), model + effort per ADR-0011, `max_turns`, session id captured for resume. Skills are projected to `<worktree>/.claude/skills/<name>/SKILL.md`.

**D-8 Codex adapter specifics.** Spawns `codex exec --json --sandbox workspace-write --cd <worktree> -c model=<m> -c model_reasoning_effort=<e> [--output-schema <AgentOutput schema>]` with scrubbed env; parses JSON event lines into `AgentEvent`s; tool calls are reported post-hoc as `TOOL_CALL_RESULT` (no pre-authorisation possible — see ADR-0006 for compensating controls); `codex exec resume <thread_id>` for native resume. Skills are projected into `<worktree>/AGENTS.md` (managed section) and `.codex/` where supported. Exact flags are verified in a Stage 1 spike story; the adapter owns the mapping.

**D-9 Usage and cost.** Adapters emit `USAGE` with tokens; `CostManager.record_usage` converts to USD using `ModelDescriptor` prices (overridable in `models.yaml`), so pricing never lives in adapter code.

**D-10 Plugin point.** Additional adapters register via entry point group `walk.adapters` (ADR-0009 §D-11).

## Alternatives

- **Provider-specific agent classes per role** (e.g. `ClaudeLeadDev`): rejected — violates Invariant 1.
- **Letting agents call Jira/Git directly through provider MCP tools:** rejected for MVP — would require per-provider permission plumbing and credentials in agent environments (§91); kernel applies `AgentOutput` intents instead (ADR-0006 D-2).
- **Persisting full transcripts for handover:** rejected — §22 forbids requiring chain-of-thought serialisation; transcripts are provider-shaped and non-portable.
- **Driving Codex through an SDK / app-server protocol:** deferred — CLI is sufficient and stable; revisit if per-call authorisation becomes available.

## Consequences

- `AgentOutput` schema is a public, versioned contract; changes require a `BehaviorVersion` bump (kind `PROMPT`/`CONTEXT_FORMAT`).
- Codex runs have weaker in-flight control; compensated by sandbox + boundary audit + kernel-executed side effects (ADR-0006).
- §132 failover test and §128 demonstrations are implementable without provider-specific branches in `runtime`.

## Related requirements

§4 (12–13), §6.1, §17, §21–§23, §28, §126, §128, §132, §137 (Invariants 1, 2, 11, 12), §139.
