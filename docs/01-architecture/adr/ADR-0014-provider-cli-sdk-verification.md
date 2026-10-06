# ADR-0014 — Provider CLI and SDK Verification

**Status:** Accepted
**Date:** 2026-10-06
**Deciders:** Project owner, LeadDev
**Related requirements:** §6.1, §17, §21, §22, §128, §139

## Context

ADR-0004 D-7/D-8 and ADR-0011 assume specific Codex CLI flags and Claude Agent SDK options.
ADR-0004 D-8 defers exact verification to a Stage 1 spike (E01-S02). On 2026-10-06 the owner
decided that this spike verifies **in theory first**: official documentation, `--help`
output and static SDK introspection, with no login and no billable model call. Behaviour that
only a real run can show is checked when a concrete project is bootstrapped (E02-S02
preflight) and by the adapters' `@pytest.mark.integration` tests (E01-S21, E01-S22). Unity CLI
and other per-project tools are verified the same way, by the project preflight.

Verification methods used in the tables:

| Method | Meaning |
|---|---|
| `docs` | Official documentation page, read 2026-10-06 |
| `help` | `npx -y @openai/codex exec --help` / `exec resume --help`, no login required |
| `introspection` | `dataclasses.fields` / `typing.get_args` on the installed package, no `query()` call |
| `runtime check` | Not settled by the methods above; verified later by the named story |

## Decision

The adapters implement against the tables below. A `Deviation` row overrides the earlier
assumption and names the story that must implement the change.

### Codex CLI (`codex-cli 0.160.1`)

| Assumption | Source | Verified (version) | Deviation | Consequence (story) |
|---|---|---|---|---|
| `codex exec --json` emits JSON Lines on stdout | ADR-0004 D-7 | Verified (0.160.1, help + docs) | | E01-S22 parses JSONL |
| `--sandbox workspace-write` | ADR-0004 D-7 | Verified (0.160.1, help: `read-only`, `workspace-write`, `danger-full-access`) | | E01-S22 default `workspace-write` |
| `--cd <dir>` | ADR-0004 D-7 | Verified (0.160.1, help: `-C, --cd <DIR>`) | | E01-S22 |
| `-c model=<id>` | ADR-0004 D-7 | Verified (0.160.1, help: `-c, --config <key=value>`, value parsed as TOML; `-m, --model` also exists) | | E01-S22 keeps `-c model=<id>` |
| `-c model_reasoning_effort=<low\|medium\|high\|xhigh>` | ADR-0011 D-2 | Verified (docs: `minimal`, `low`, `medium`, `high`, `xhigh`; `xhigh` is model-dependent) | | E01-S22 maps VERY_HIGH → `xhigh` only when the model family lists it, else degrades to `high` (ADR-0011 D-4) |
| `--output-schema <file>` | ADR-0004 D-3 | Verified (0.160.1, help + docs) | | E01-S22 passes the schema; `.walk/output.json` stays the fallback channel |
| `codex exec resume <thread_id>` | ADR-0004 D-7 | Verified (0.160.1, help: `codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]`) | `resume` does not accept `--sandbox` or `--cd`; it accepts `-c`, `-m`, `--json`, `--output-schema`, `-o`, `--skip-git-repo-check` | E01-S22: `build_resume_command` sets the working directory through the subprocess `cwd` and the sandbox through `-c sandbox_mode="workspace-write"` |
| JSON event line kinds | ADR-0004 D-7 | Verified (docs): `thread.started` (`thread_id`), `turn.started`, `turn.completed` (`usage`: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`), `turn.failed`, `item.started` / `item.completed` (agent message, command execution, tool call, file change), `error` | | E01-S22 already uses the dotted names. The exact `item.type` strings (the story assumes `agent_message` and `exec_command`; the docs describe "command execution") are a runtime check in E01-S22's integration test, and unknown item types must be logged and skipped, never fatal |
| exit codes | ADR-0004 D-7 | runtime check | Not documented | E01-S22 treats any non-zero exit without `turn.completed` as failure; its integration test records the real codes |
| network disabled by default under `workspace-write` | ADR-0009 D-5 | runtime check | Not documented on the pages read | E01-S22 passes `-c sandbox_workspace_write.network_access=false` explicitly instead of relying on the default; E02-S02 preflight reports the effective value |
| authentication | ADR-0009 D-8 | Verified (docs): saved `codex login` state, or `CODEX_API_KEY` per invocation | | E02-S02 preflight reports login presence only |

### Claude Agent SDK (`claude-agent-sdk 0.2.163`)

| Assumption | Source | Verified (version) | Deviation | Consequence (story) |
|---|---|---|---|---|
| `query()` options object | ADR-0004 D-8 | Verified (0.2.163, introspection: `query(*, prompt, options, transport)`) | | E01-S21 |
| `cwd` | ADR-0004 D-8 | Verified (0.2.163, introspection) | | E01-S21 |
| `allowed_tools` | ADR-0006 D-4 | Verified (0.2.163, introspection + docs) | `allowed_tools` auto-approves listed tools and they never reach `can_use_tool`; it does not restrict the tool set | E01-S21: restrict the tool set with `tools=[...]`, pass `allowed_tools=[]`, so every call is decided by the kernel |
| `permission_mode` | ADR-0006 D-4 | Verified (0.2.163, introspection: `default`, `acceptEdits`, `plan`, `bypassPermissions`, `dontAsk`, `auto`) | | E01-S21 uses `default`, the mode that routes every non-pre-approved call to `can_use_tool` |
| `can_use_tool` | ADR-0006 D-4 | Verified (0.2.163, docs: `(tool_name, input, ToolPermissionContext) -> PermissionResultAllow \| PermissionResultDeny(message, interrupt)`) | | E01-S21 |
| `model` | ADR-0004 D-8 | Verified (0.2.163, introspection; `fallback_model` also exists) | | E01-S21 does not use `fallback_model`; fallback is kernel-owned (§21) |
| `effort` (`low\|medium\|high\|xhigh\|max`) | ADR-0011 D-2 | Verified (0.2.163, introspection: `EffortLevel` = `low`, `medium`, `high`, `xhigh`, `max`) | | E01-S21 maps per ADR-0011 D-2 |
| `max_turns` | ADR-0011 D-2 | Verified (0.2.163, introspection; `max_budget_usd` also exists) | | E01-S21 |
| `resume` | ADR-0004 D-6 | Verified (0.2.163, introspection; `fork_session` also exists) | | E01-S21 |
| session id in result/init messages | ADR-0004 D-6 | Verified (docs + introspection): `ResultMessage.session_id`; `SystemMessage(subtype="init").data` carries it | | E01-S21 reads `ResultMessage.session_id`, falls back to the init message |
| usage fields | ADR-0004 D-8 | Verified (docs + introspection): `ResultMessage.usage` (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`), `total_cost_usd`, `num_turns`, `duration_ms`, `is_error` | | E01-S21 meters tokens and cost from `ResultMessage` |
| structured output (`output_format`) | ADR-0004 D-3 | Verified (0.2.163, introspection + docs: `output_format={"type": "json_schema", "schema": ...}`, result in `ResultMessage.structured_output`) | | E01-S21 uses `output_format`; `.walk/output.json` remains the fallback |

### Kernel

| Assumption | Source | Verified (version) | Deviation | Consequence (story) |
|---|---|---|---|---|
| `jinja2` runtime dependency for ADR-0004 D-4 templates | E01-S01 | Accepted (`jinja2>=3.1` in `pyproject.toml`) | | ADR-0001 dependency list includes it |

## Alternatives considered

- **Authenticated probe runs now** — rejected by the owner on 2026-10-06: they spend provider
  quota before any project exists; the same facts are checked at project preflight.
- **Skip verification until the adapters** — rejected: E01-S21/S22 would be written against
  unchecked assumptions, and the `allowed_tools` finding changes the permission design.

## Consequences

- Amends, without rewriting: ADR-0001 (dependency list confirmed), ADR-0004 D-7/D-8 (Codex
  resume flags, dotted event names, SDK `tools`/`allowed_tools` usage), ADR-0006 D-4 (Claude
  enforcement uses `tools` + `permission_mode="default"` + `can_use_tool`), ADR-0011 D-2
  (Codex `minimal` exists but is unused; `xhigh` is model-dependent).
- E01-S21 and E01-S22 implement the `Consequence` column. Their integration tests settle every
  `runtime check` row on the owner's machine.
- E02-S02 preflight re-runs the non-billable probes (`codex --version`, `codex exec --help`
  flag presence, SDK option introspection) per project and reports drift from this ADR.

## Evidence

Probes (non-billable; no login): `scripts/spikes/codex_probe.sh` and
`scripts/spikes/claude_probe.py`. Transcript summary, 2026-10-06, Windows 11:

```
$ npx -y @openai/codex --version
codex-cli 0.160.1
$ npx -y @openai/codex exec --help        (flags present)
-c/--config  -m/--model  -s/--sandbox [read-only, workspace-write, danger-full-access]
-C/--cd  --skip-git-repo-check  --ephemeral  --output-schema  --json
-o/--output-last-message  --worktree  --add-dir
$ npx -y @openai/codex exec resume --help
Usage: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]
(--output-schema, --json, -o present; -s/--sandbox and -C/--cd absent)

$ uv run --no-project --with claude-agent-sdk python scripts/spikes/claude_probe.py
claude-agent-sdk 0.2.163
ClaudeAgentOptions: cwd, allowed_tools, disallowed_tools, permission_mode, can_use_tool,
  model, fallback_model, effort, thinking, max_turns, max_budget_usd, resume,
  fork_session, output_format, env, setting_sources, system_prompt  (all present)
PermissionMode ('default', 'acceptEdits', 'plan', 'bypassPermissions', 'dontAsk', 'auto')
EffortLevel ('low', 'medium', 'high', 'xhigh', 'max')
ResultMessage: duration_ms, is_error, num_turns, session_id, structured_output, subtype,
  total_cost_usd, usage
```

Documentation read: `learn.chatgpt.com/docs/non-interactive-mode` (Codex non-interactive
mode), `code.claude.com/docs/en/agent-sdk/python` (Python Agent SDK reference).
