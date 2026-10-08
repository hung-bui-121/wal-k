# HANDOFF — current state and next steps

Updated: 2026-10-08. Read this first when resuming. It records where work stopped; the
procedure itself is in `docs/00-governance/IMPLEMENTATION-PROTOCOL.md`.

## Where we are

| Area | State |
|---|---|
| Planning | Complete: governance, architecture (ADR-0001..0020), 174 stories in 11 epics, traceability 140/140 |
| Epic 01 Kernel Core | DONE — 31 stories, gate E01-S31, review E01-R01, bugfixes E01-B01..B06 |
| Epic 02 Production Kit | E02-S01..S15 and E02-B01..B03 DONE. **E02-S16 (epic gate) and E02-R01 (review) TODO** |
| Epics 03–11 | Not started |
| `main` | Pushed, working tree clean, last commit `7e16573` (E02-S15) |

E02-S15 still reads `DONE (pending)`; the next commit replaces it with `7e16573` in both
the epic file and `WBS.md` §5 (protocol §5.3).

## Next steps, in order

1. **E02-S16** — Epic 02 gate (e2e under `tests/e2e/`). Implement with the protocol.
2. **E02-R01** — review by a *different* agent/model than the implementer
   (reviewer protocol). Defects become `E02-Bxx` bugfix stories.
3. Fix any `E02-Bxx` marked BLOCKER before Epic 03.
4. **Epic 03 Coding Workflow** — E03-S01 onward. Read the binding notes already added to
   E03-S07 (version `scheduled_states.yaml`), E03-S13 (REVIEW variant of the E01-B01 test)
   and E03-S18 (clean up FAILED/BLOCKED worktrees).

## Owner decisions in force

- Tech stack ADR-0001 accepted. Unity automation via Unity CLI, not MCP (ADR-0015).
  OpenArt via remote MCP `https://mcp.openart.ai/mcp`, OAuth 2.1 PKCE (ADR-0017).
- Provider tools are verified **in theory first** (docs, `--help`, SDK introspection; no login,
  no billable call). Real runs happen at project preflight (`walk doctor`, E02-S02) and in
  adapter `@pytest.mark.integration` tests (ADR-0014).
- Commits: one per story, `feat:` / `bugfix:` / `docs:` / `chore:`, pushed immediately,
  **no attribution lines** (hook enforced). `requirements/` is git-ignored.
- Context-switch guard (global `~/.claude/CLAUDE.md`): a request that targets a different
  repo/task than the current one must be confirmed by the owner before any action.

## Waiting on the owner (not blocking E02-S16)

- Install Codex CLI (`npm i -g @openai/codex`) and `codex login` when real provider tests
  are wanted; then run the integration tests listed in E02-B01/E02-B02 Evidence, e.g.
  `uv run pytest -m integration tests/runtime/test_sandbox_env.py -k windows -v`.
- On this machine `walk doctor` reports `unity` misconfigured: the `Unity` on PATH is an npm
  "CLI for Unity" tool, not the Editor. Pass `--unity-path` when bootstrapping a real project.
- E02-S04: game repos bootstrapped before E02-S04 must re-run `walk bootstrap` to fill
  `kernel-versions.yaml`.

## How work has been run (lessons)

- One `code-implementer` agent per batch of stories, **sequential** (all agents share one
  working tree; parallel agents would commit each other's half-done files).
- After each epic gate: a `tech-lead-reviewer` runs the `Rxx` task, then bugfix stories.
- Agents get cut off by provider rate limits; every story is committed and pushed on its
  own, so the last pushed commit is always a safe resume point. Check `git status` first.
- Before every docs commit: `py -3 scripts/validate_wbs.py` (checks template, dependencies,
  and that epic and WBS statuses agree). Regenerate `scripts/build_traceability.py` and
  `scripts/build_name_register.py` after story changes.
- Quality gate: `sh scripts/check.sh` (ruff format, ruff, mypy strict, lint-imports, pytest).
  On this Windows host the full run takes several minutes when Unity editors are open.
- Python for ad-hoc scripts: `py -3` or `uv run python` (plain `python` may be Python 2);
  console is cp1252, set `PYTHONIOENCODING=utf-8` for non-ASCII output.
