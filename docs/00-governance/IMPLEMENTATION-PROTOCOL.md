# Implementation Protocol

The fixed procedure an implementing agent follows for every story. Following it exactly is
what makes the output independent of which model implements. Deviation is a defect.

## 0. Session start (once per session)

1. Read `AGENTS.md` (repo root), then this file, `CONVENTIONS.md`, `DEFINITION-OF-DONE.md`,
   `COMMIT-POLICY.md`.
2. Run `git config core.hooksPath scripts/git-hooks` and `git pull --ff-only`.
3. Run the quality gate (`CONVENTIONS.md` §5). If it fails on `main`, stop and create a
   `bugfix` story in the current epic before doing anything else.

## 1. Pick the story

1. Open `docs/02-work-breakdown/WBS.md`, find the lowest-numbered story whose status is
   `TODO` and whose dependencies are all `DONE`.
2. Verify Definition of Ready. If not ready, set `BLOCKED` with the reason, commit as
   `docs: block <ID> pending <reason>`, push, and move to the next candidate.
3. Set the story status to `IN_PROGRESS` (in the epic file). Do not commit yet.

## 2. Load context (context-first, §40)

Read, in this order, only what the story references:
1. The story itself, fully.
2. The `§NN` requirement sections it cites (in `requirements/WAL_K_REQ.md` if present
   locally; otherwise the summary in the story is authoritative).
3. The `INTERFACES.md` / `DOMAIN-MODEL.md` sections it names.
4. The ADRs it names.
5. The source files in its **Files** table that already exist, plus their tests.

Do not read the whole repository. If understanding requires a file outside the story's
list, note it under the story's **Notes** as "Also read: ...".

## 3. Tests first

1. Create the test file(s) from the **Files** table.
2. Write one test per acceptance criterion using the exact test names from the story.
   Tests must fail before implementation (run them; confirm red).
3. Add the negative-path tests required by `DEFINITION-OF-DONE.md`.

## 4. Implement

1. Create/modify only the files in the **Files** table, exposing exactly the public symbols
   listed with the signatures from the interface contract.
2. If the contract is ambiguous:
   - Autonomy Level 0 (naming of privates, internal structure, local helpers): decide and
     proceed.
   - Anything that changes a public signature, a schema, a state transition, a permission
     or a dependency: do **not** guess. Record the question in the story **Notes**, mark the
     story `BLOCKED`, commit `docs: block <ID> ...`, push, and pick the next story.
3. Run the quality gate until green. Fix root causes; never weaken or skip tests.

## 5. Document

1. Update `INTERFACES.md` / `DOMAIN-MODEL.md` if a contract changed (same commit).
2. Fill the story's **Evidence** section: gate summary lines and demo transcript.
3. Set story **Status** to `DONE (<sha>)` — use `pending` for the sha, then amend after
   the commit is created, or simply write the short sha of `HEAD` after committing and
   include it in the following story's commit. The WBS status table is updated in the same
   commit as the story.

## 6. Commit and push (no approval needed)

```
git add -A
git commit -m "<type>: <subject> (<ID>)" [-m "<body>"]
git push origin HEAD
```

- `type` is the story's **Type**. Message rules: `COMMIT-POLICY.md`.
- If the hook rejects the message, fix the message; never bypass the hook.
- If push is rejected (non-fast-forward), `git pull --rebase`, re-run the gate, push again.

## 7. Repeat

Return to step 1. Stop only when no story is `TODO`-and-ready in the current epic, then
report: stories completed (IDs + shas), stories blocked (IDs + reasons), gate summary.

## Reviewer protocol (REVIEW tasks)

A `REVIEW` task in an epic is executed by a different agent instance (ideally a different
model, §23) than the one that implemented the reviewed stories:

1. Read the reviewed stories and their commits (`git show <sha>`).
2. Check each DoD item mechanically; check each acceptance criterion against its test.
3. Check invariants in `ARCHITECTURE.md` §Invariants for the touched modules.
4. For each defect found, create a `bugfix` story in the epic file (using the template)
   and link it from the REVIEW task. Do not fix in place.
5. Commit `docs: review <epic> stories <range>` and push.
