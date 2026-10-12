# HANDOFF — current state and next steps

Updated: 2026-10-12. Read this first when resuming. It records where work stopped; the
procedure itself is in `docs/00-governance/IMPLEMENTATION-PROTOCOL.md`.

## Where we are

| Area | State |
|---|---|
| Planning | Complete: governance, architecture (ADR-0001..0020), 175 stories in 11 epics, traceability 140/140 |
| Epic 01 Kernel Core | DONE — 31 stories, gate E01-S31, review E01-R01, bugfixes E01-B01..B06 |
| Epic 02 Production Kit | E02-S01..S15 and E02-B01..B03 DONE. **E02-B04 (BLOCKER bugfix) TODO**, next. E02-S16 (epic gate) TODO, unblocked by the owner decision of 2026-10-12, depends on B04. E02-R01 (review) TODO, waits on S16 |
| Epics 03–11 | Not started |
| `main` | Pushed, working tree clean; last commit is the `docs: unblock E02-S16 ...` planning commit |

E02-S15 is recorded as `DONE (7e16573)`. E02-S16 was BLOCKED on two gate assertions. The owner
decided both on 2026-10-12, and the decisions are recorded in the E02-S16 Notes in
`EPIC-02-production-kit.md`:
- **AC 5 → option A (scenario change, no kernel change).** The gate now uses a SENIOR_DEV
  IMPLEMENT run requesting `git.delete_branch_protected`, which needs USER approval and is not
  denied for SENIOR_DEV. In E02 only SENIOR_DEV may end an IMPLEMENT run, and SENIOR_DEV is
  denied `git.merge_protected`.
- **AC 7 → option A (kernel bugfix E02-B04).** The executor writes one `TOOL_DENIED` per
  violating path when a run fails on the repository boundary (ADR-0006 D-5). It keeps
  `ERROR{kind: BOUNDARY}`. ARCHITECTURE §4.3 already lists the new write point.

Work-in-progress gate code (conftest fixtures + `tests/e2e/test_e02_gate.py`, 6/8 passing) is
**not committed**. It is in the local stash `E02-S16 gate tests WIP (6/8 pass; AC5+AC7
blocked)` on this host (`git stash list`; restore with `git stash pop`).

## Next steps, in order

1. **E02-B04** (BLOCKER bugfix, `bugfix: write tool denied event on boundary violation
   (E02-B04)`): add the executor `TOOL_DENIED` write for boundary violations, keep `ERROR`,
   and update INTERFACES §1.13 and ADR-0006 as the story lists.
2. **E02-S16** (only after E02-B04 is committed and pushed, so B04's `git add -A` cannot pick
   up the WIP files): restore the test code from the local stash `E02-S16 gate tests WIP (6/8 pass;
   AC5+AC7 blocked)` (`git stash list`, then `git stash pop`). Change the AC 5 test and the
   conftest fake to the SENIOR_DEV `git.delete_branch_protected` scenario: the fake picks its
   scenario by work item, not by role (Level-0 note in the story). AC 7 passes unchanged once
   E02-B04 is DONE. Then finish the story (8/8).
3. **E02-R01**: review by a *different* agent/model than the implementer
   (reviewer protocol). Defects become `E02-Bxx` bugfix stories.
4. Fix any `E02-Bxx` marked BLOCKER before Epic 03.
5. **Epic 03 Coding Workflow** — E03-S01 onward. Read the binding notes already added to
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

## Waiting on the owner

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
