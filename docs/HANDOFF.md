# HANDOFF — current state and next steps

Updated: 2026-10-12. Read this first when resuming. It records where work stopped; the
procedure itself is in `docs/00-governance/IMPLEMENTATION-PROTOCOL.md`.

## Where we are

| Area | State |
|---|---|
| Planning | Complete: governance, architecture (ADR-0001..0020), 174 stories in 11 epics, traceability 140/140 |
| Epic 01 Kernel Core | DONE — 31 stories, gate E01-S31, review E01-R01, bugfixes E01-B01..B06 |
| Epic 02 Production Kit | E02-S01..S15 and E02-B01..B03 DONE. **E02-S16 (epic gate) BLOCKED** (2 of 8 gate assertions fail on kernel behaviour); E02-R01 (review) TODO, waits on S16 |
| Epics 03–11 | Not started |
| `main` | Pushed, working tree clean; last commit is the `docs: block E02-S16 ...` commit |

E02-S15 is recorded as `DONE (7e16573)`. E02-S16 is BLOCKED. Its Notes in
`EPIC-02-production-kit.md` hold both defects with evidence and the decision options:
- **AC 5.** A tick-scheduled LEAD_DEV run cannot complete in E02. Only SENIOR_DEV may raise the
  IMPLEMENT outcome events, and SENIOR_DEV is denied `git.merge_protected`.
- **AC 7.** The executor writes `ERROR{kind: BOUNDARY}`, not the `TOOL_DENIED` that ADR-0006
  D-5 requires on a boundary violation.

Work-in-progress gate code (conftest fixtures + `tests/e2e/test_e02_gate.py`, 6/8 passing) is
**not committed**. It is in the local stash `E02-S16 gate tests WIP (6/8 pass; AC5+AC7
blocked)` on this host (`git stash list`; restore with `git stash pop`).

## Next steps, in order

1. **Owner/architect decision on E02-S16 Notes** (AC 5 options A/B/C, AC 7 options A/B).
   Then unblock E02-S16 (`docs: unblock E02-S16 ...`), add any bugfix stories the decision
   needs (`E02-Bxx`), restore the stashed gate code, adjust AC 5/AC 7 to the decision, and
   finish the story.
2. **E02-R01**: review by a *different* agent/model than the implementer
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

## Waiting on the owner (besides the E02-S16 decision)

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
