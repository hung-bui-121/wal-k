# ADR-0001 — Kernel Technology Stack

**Status:** Accepted (owner confirmed 2026-10-06)
**Date:** 2026-10-05
**Deciders:** Project owner
**Related requirements:** §4 (objectives 12, 13, 17), §122, §125, §127–129, §139

## Context

The requirements spec deliberately leaves the implementation language, persistence and
runtime shape open (§139). A plan that is reproducible across implementing models needs
these fixed up front, otherwise every story would re-decide them.

Constraints that drive the choice:

- Must drive Claude and Codex as interchangeable workers (§6.1, §128).
- Must integrate with Git, Jira, Unity CLI/MCP, Graphify (§129, §30).
- Must persist workflow state, checkpoints and an execution ledger durably (§54, §81, §89).
- Project memory must be human-readable and live in the game repository (§34–§35).
- Owner's existing tooling is Python backend + Unity C#.

## Decision

| Concern | Decision |
|---|---|
| Language / runtime | **Python 3.12+**, `asyncio` for concurrency |
| Package / env | `uv` + `pyproject.toml`, src layout: `src/walk/` (CLI command `walk`) |
| Schemas / validation | `pydantic` v2 for every kernel data contract |
| Durable kernel state | **SQLite** (stdlib `sqlite3`), one DB per project at `<game-repo>/.ai/kernel.db`: workflow state, checkpoints, ledger, budgets, cost |
| Project memory (`.ai/`) | **Markdown with YAML front matter**, human-readable, git-versioned |
| Kernel configuration | **YAML** (roles, constitutions, model policies, permissions, hooks) |
| Workflow engine | In-house explicit state machine (transition table + guards), persisted in SQLite. No third-party workflow framework |
| CLI | `typer` |
| HTTP | `httpx` (Jira REST v3, provider HTTP APIs) |
| Model adapters | Claude via `claude-agent-sdk` (Python). Codex via `codex exec --json` subprocess. Both behind one `ModelAdapter` protocol |
| Work provider | `WorkProvider` protocol with two implementations: `LocalWorkProvider` (file-backed, default for dev/tests) and `JiraWorkProvider` |
| Git | `git` CLI via subprocess, worktrees for parallel execution |
| Unity | Unity batchmode CLI (`com.walk.ci`) for all Editor automation; Unity MCP rejected (ADR-0015) |
| MCP client | `mcp` (official MCP Python SDK) for remote MCP servers, first used for OpenArt `[Stage 8]` — approved dependency per ADR-0017 |
| Tests | `pytest` + `pytest-asyncio`, coverage via `pytest-cov` |
| Static quality | `ruff` (lint + format), `mypy --strict` |
| Logging | stdlib `logging` emitting JSON lines; ledger is the source of truth, logs are diagnostics |

## Alternatives considered

- **TypeScript / Node** — first-class Codex SDK and MCP ecosystem. Rejected: owner's backend
  tooling is Python; Claude Agent SDK is equally available; Codex is fully drivable via CLI.
- **Postgres** — rejected for MVP: kernel is single-project-per-process; SQLite is zero-ops
  and reproducible across machines (§27). Revisit if multi-machine execution (§139) is adopted.
- **Third-party workflow engines (Temporal, Prefect)** — rejected: workflow must be a small,
  auditable, explicitly modeled state machine (§53); external engines add ops burden.
- **JSON for `.ai/`** — rejected: memory must be readable and reviewable by humans (§6.2, §36).

## Consequences

- All stories in `docs/02-work-breakdown/` assume this stack; changing it invalidates
  Epic 01 stories and must be done before Stage 1 starts.
- Every pydantic model is a public contract and lives under `src/walk/<module>/models.py`.
- Provider-specific code is confined to `src/walk/model_router/adapters/` and
  `src/walk/integrations/`; nothing else imports provider SDKs (Invariant 1, 11).
