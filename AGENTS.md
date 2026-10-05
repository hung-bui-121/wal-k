# AGENTS.md — Instructions for any agent working in this repository

WAL-K is an AI game-studio production kernel (Python). This file is read by every coding
agent (Claude Code, Codex, others) before doing anything. The goal of these rules is that
the output does not depend on which model does the work.

## Read first, every session
1. `docs/00-governance/IMPLEMENTATION-PROTOCOL.md` — the exact procedure per story.
2. `docs/00-governance/CONVENTIONS.md` — code, test and layout rules (enforced by tooling).
3. `docs/00-governance/DEFINITION-OF-DONE.md` — when a story may be committed.
4. `docs/00-governance/COMMIT-POLICY.md` — message format, enforced by a git hook.

## Where things are
- Requirements: `requirements/WAL_K_REQ.md` (local only, git-ignored). Stories summarize
  the sections they need; the summary in the story is authoritative when the file is absent.
- Architecture, domain model, interfaces, ADRs: `docs/01-architecture/`.
- Work breakdown (epics, stories, status): `docs/02-work-breakdown/`, start at `WBS.md`.
- Requirement → story traceability: `docs/03-traceability/REQ-TRACEABILITY.md`.
- Kernel source: `src/walk/`. Tests: `tests/` (mirror of `src/walk/`).

## Non-negotiables
- Work one story at a time, in WBS order, tests first, exactly the files the story lists.
- Never invent requirements. Ambiguity above autonomy level 0 → mark story BLOCKED, commit,
  move on (protocol §4.2).
- Quality gate must be green before every commit:
  `uv run ruff format --check . && uv run ruff check . && uv run mypy src tests && uv run pytest`
- One commit per story, then push immediately. Format `feat: ...` / `bugfix: ...` /
  `docs: ...` / `chore: ...`. No attribution, signature or AI-tool names in messages.
- Never commit secrets, provider transcripts, or `requirements/`.
- Provider SDKs are imported only under `src/walk/model_router/adapters/` and
  `src/walk/integrations/`.

## Setup
```
uv sync
git config core.hooksPath scripts/git-hooks
```
