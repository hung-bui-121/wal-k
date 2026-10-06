# WAL-K Planning Documentation

Everything an implementer needs before writing code, in reading order. The goal of this
tree is that the resulting kernel is the same regardless of which model or person
implements it.

| Folder | Purpose | Start with |
|---|---|---|
| `00-governance/` | How work is done: per-story procedure, code conventions, Definition of Ready/Done, commit policy, templates | `IMPLEMENTATION-PROTOCOL.md` |
| `01-architecture/` | What is built: packages, domain model, service protocols, state machines, algorithms, ADRs | `README.md` → `ARCHITECTURE.md` |
| `02-work-breakdown/` | In what order: 11 epics (one per roadmap stage), every story as an executable contract, status table | `WBS.md` |
| `03-traceability/` | Generated: requirement → stories matrix, story-level name register | `REQ-TRACEABILITY.md`, `NAME-REGISTER.md` |

## Reading order for a new implementer

1. `../AGENTS.md` (repo root, 2 minutes).
2. `00-governance/IMPLEMENTATION-PROTOCOL.md`, then `CONVENTIONS.md`, `DEFINITION-OF-DONE.md`,
   `COMMIT-POLICY.md`.
3. `01-architecture/adr/ADR-0001-tech-stack.md`, `ARCHITECTURE.md`, `DOMAIN-MODEL.md`,
   `INTERFACES.md`. Remaining ADRs when a story cites them.
4. `02-work-breakdown/WBS.md` §1–§3 (rules and planning conventions), then the current
   epic file.

## Maintaining the plan

| Task | Command |
|---|---|
| Validate every story against the template, dependency rules and WBS table | `py -3 scripts/validate_wbs.py` |
| Regenerate the requirement → story matrix | `py -3 scripts/build_traceability.py` |
| Regenerate the story-level name register | `py -3 scripts/build_name_register.py` |

Both run from the repo root. `validate_wbs.py` must pass before any `docs:` commit that
touches `02-work-breakdown/`.

## Source of truth

The master requirements specification (`requirements/WAL_K_REQ.md`, 140 sections) is kept
locally and git-ignored. Stories cite it as `§NN` and summarise what they need, so the plan
is usable without the file.
