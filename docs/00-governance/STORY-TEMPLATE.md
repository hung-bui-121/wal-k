# Story Template

Every story in `docs/02-work-breakdown/EPIC-*.md` uses exactly this structure and heading
order. Fields marked **(required)** in this template must be non-empty; the marker itself is
not copied into story files (headings there are plain, e.g. `#### Goal`). This is the kernel's own
"Executable Story Contract" (§57) applied to building the kernel.

```markdown
### <ID> — <Short title>

**Status:** TODO | BLOCKED | IN_PROGRESS | DONE (<commit sha>)
**Type:** feat | bugfix | docs | chore
**Requirements:** §NN, §NN (required)
**Depends on:** <IDs or "none"> (required)
**Effort:** LOW | MEDIUM | HIGH | VERY_HIGH   **Risk:** LOW | MEDIUM | HIGH
**Owner role:** <SeniorDev | LeadDev | QC>   **Reviewer role:** <LeadDev | QC>

#### Goal
One or two sentences: what exists after this story that did not exist before.

#### Scope
- In: ...
- Out: ... (name the story that covers it)

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/<module>/<file>.py` | create / modify | `ClassName`, `function_name` |
| `tests/<module>/test_<file>.py` | create | — |

#### Interface contract
Exact signatures / schemas the implementation must expose (Python code block or table).
Reference `docs/01-architecture/INTERFACES.md` sections instead of copying when the
contract is already defined there.

#### Behavior
Numbered rules, edge cases, error cases. Each rule is testable.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given ... When ... Then ... | `tests/<module>/test_<file>.py::test_<name>` |

#### Evidence required
- Quality gate output
- Demo command(s): `walk ...` and expected output, if applicable

#### Notes
Design hints, references to ADRs, known pitfalls. Never new requirements.

#### Evidence (filled by implementer)
Paste gate summary + demo transcript here when marking DONE.
```

## Rules for writing stories

- Interface-contract code blocks in stories may be abbreviated sketches (`...` for
  parameters an earlier story already defined, one-line `def ...: ...` stubs). The exact,
  parseable signatures live in `docs/01-architecture/INTERFACES.md` and `DOMAIN-MODEL.md`;
  when a sketch and those documents disagree, the story wins and the implementer updates
  the architecture document in the same commit.

0. Required sections (non-empty): Goal, Files, Interface contract, Acceptance criteria,
   Evidence required, plus the header fields Requirements and Depends on. `scripts/validate_wbs.py`
   checks heading presence and order.

1. A story is 0.5–2 days of work for one implementer. Split anything larger.
2. The **Files** table is exhaustive. Reviewers reject commits touching unlisted files
   without justification in the commit body.
3. Acceptance criteria are observable behaviors, not implementation steps. Each maps to
   exactly one test function name.
4. Stories do not depend on stories in later epics.
5. Prefer vertical slices that leave the kernel runnable (`walk` CLI still works) over
   horizontal layers.
