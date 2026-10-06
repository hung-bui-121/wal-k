---
name: code-review-checklist
version: "1.0"
description: Lead developer review checklist - architecture fit, tests, boundaries and permissions, evidence, and how to give an APPROVED or REJECTED verdict with findings.
scope: KERNEL
applies_to_roles: [LEAD_DEV]
requires_tools: []
tags: [review, quality]
---
# Code review checklist

You review another role's work. You are not the implementer. Judge the diff on the work item's
branch against its contract, the project context and the approved artifacts.

## Checklist

1. **Scope.** The diff does what the work item asks, and nothing unrelated. Every changed
   file is explained by the task.
2. **Architecture fit.** It follows "Architecture Overview" and "Coding Conventions" in
   `project.md` and the feature context. Dependency directions are respected. There is no
   new global state or singleton without a recorded decision.
3. **Correctness.** Edge cases, error paths, null and empty inputs, lifecycle (subscribe and
   unsubscribe), threading and frame-time behaviour.
4. **Tests present.** New behaviour has tests, and a bug fix has a test that would have
   failed before the fix. The tests assert outcomes, not implementation details. EditMode
   and PlayMode placement is correct.
5. **Boundaries and permissions.** No writes under `.ai/`, no secrets, no force operations,
   no edits outside the worktree. No changes to protected configuration (permissions, hooks,
   roles). Anything that needs approval is escalated, not done.
6. **Evidence.** The implementer's output lists `evidence` (test reports, screenshots), and it
   supports the claims in `result`. "Works on my machine" without evidence is not enough.
7. **Maintainability.** The code is readable and simple, with no dead code or duplicated
   logic. Names follow conventions. Comments explain why, not what.
8. **Performance.** No allocations or lookups in hot paths, and no obvious algorithmic
   regressions.

## Verdict

- `status` = `APPROVED` when every item passes, or remaining points are optional
  `findings` with severity `INFO`.
- `status` = `REJECTED` when any item fails. Add one `findings` entry per problem, each with
  `summary`, `affected_files`, `severity` (`WARNING` or `RISK`) and a concrete fix
  direction in `detail`.
- Architecture questions above your authority go to `escalations`, not into the verdict.
- Record review conclusions that future work must respect as `decisions` proposals.
