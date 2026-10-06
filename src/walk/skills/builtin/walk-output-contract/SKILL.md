---
name: walk-output-contract
version: "1.0"
description: How every agent run reports its result to the WAL-K kernel through .walk/output.json (the AgentOutput contract). Mandatory for every role.
scope: KERNEL
applies_to_roles: [ORCHESTRATOR, LEAD_DEV, SENIOR_DEV, QC]
requires_tools: []
tags: [kernel, output, contract]
---
# WAL-K output contract

The kernel reads your result only from one JSON object (`AgentOutput`). Prose in the chat is
not read. Your **last step** is always: write `<worktree>/.walk/output.json` with that object.

## Fields

- `status` (required), one of:
  - `COMPLETED`: the task is done and verified.
  - `PARTIAL`: you stopped before the end; `handover` is then required.
  - `BLOCKED`: something outside your authority stops you; say what in `escalations` or `next_actions`.
  - `FAILED`: you could not do it; explain why in `result`.
  - `NEEDS_INPUT`: a human decision is needed; put the question in `escalations`.
  - `APPROVED` / `REJECTED`: review and QC verdicts only.
- `result` (required): a short Markdown summary of what you did and what you found.
- `findings`: facts worth keeping (`summary`, `detail`, `affected_files`, `severity` INFO/WARNING/RISK).
- `changes`: files you changed (`path`, `change` ADDED/MODIFIED/DELETED/RENAMED, `summary`).
  The kernel makes the commits; do not commit yourself.
- `decisions`: **proposals** only (`category`, `topic`, `position`, `rationale`,
  `autonomy_level`). The kernel or a human records the actual decision.
- `evidence`: proof of the work (`kind`, `path_or_uri`, `description`), e.g. test reports and
  screenshots under the worktree.
- `context_updates`: changes to project memory, as `doc_id` (`FEAT-0001`, `BUG-0002`,
  `project`), `section` (an exact H2 heading), `operation` (`REPLACE` or `APPEND`) and
  `content_markdown`. The kernel applies them.
- `no_context_change_reason`: required when `context_updates` is empty and `status` is not
  `FAILED`. Say why memory needs no change.
- `new_tasks`: work you discovered (`kind`, `title`, `description`, optional `parent_id`).
- `new_bugs`: defects (`title`, `severity`, `reproduction`, `expected`, `observed`).
- `escalations`: questions above your autonomy level (`to_level`, `category`, `question`,
  `options`, `recommendation`).
- `next_actions`: what should happen next and which role should do it.
- `handover`: required on `PARTIAL`. Give the state a fresh agent needs to continue.
- `effort_request`: ask for `UPGRADE` or `DOWNGRADE` of effort with a `reason`.
- `debate_position`: only in debate runs, when the task asks for it.
- `observations`: process frictions (`observed`, `potential_cause`, `possible_improvement`,
  `scope`) for kernel improvement.

## Rules

1. Never write under `.ai/` directly. Project memory changes go through `context_updates`;
   the boundary audit fails a run that touches `.ai/`.
2. Use only ids you were given or that exist; never invent work item or evidence ids.
3. Keep the JSON valid: no comments, no trailing commas, UTF-8.
4. If you cannot finish, prefer `PARTIAL` with a complete `handover` over a vague `FAILED`.
5. Write `.walk/output.json` last, after every file change and test run.
