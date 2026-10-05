# Definition of Ready and Definition of Done

Applies to every story and task in `docs/02-work-breakdown/`. Mirrors the kernel's own
rules for the game projects it will run (§58, §6.4, §6.5), because the kernel must be
built the way it expects others to build.

## Definition of Ready (an implementer may start)

- [ ] Story has: ID, requirement references (`§NN`), goal, in/out scope, files list,
      interface contract, acceptance criteria, test spec, evidence list, dependencies.
- [ ] Every dependency story is `DONE` (checked in `WBS.md` status table).
- [ ] Referenced interfaces exist in `docs/01-architecture/INTERFACES.md` or are created
      by this story.
- [ ] No open question is marked `BLOCKING` on the story.

If any box is unchecked the story is `BLOCKED`; the implementer records why in the story
file and moves to the next ready story. Implementers do not invent high-impact
requirements (§58).

## Definition of Done (a story may be committed)

### Code
- [ ] Every file in the story's "Files" list exists with the specified public names and
      signatures. No extra public symbols beyond those listed.
- [ ] `ruff format --check`, `ruff check`, `mypy --strict` pass with zero findings.
- [ ] All public symbols have docstrings; all pydantic fields have descriptions.

### Tests
- [ ] Every acceptance criterion has the named test, and the test passes.
- [ ] Coverage for touched modules ≥ 90%, overall ≥ 85%.
- [ ] At least one negative-path test per error the story introduces.
- [ ] No test depends on network, real providers, wall clock or randomness.

### Documentation
- [ ] `docs/01-architecture/INTERFACES.md` / `DOMAIN-MODEL.md` updated if the story changed
      a contract.
- [ ] The story file's **Status** is set to `DONE` with the commit SHA, and `WBS.md`
      status table is updated, in the same commit.
- [ ] Any decision made during implementation that the story did not predetermine is
      recorded as a short ADR (`docs/01-architecture/adr/`) and linked from the story.

### Evidence (recorded in the story file under "Evidence")
- [ ] Output of the quality gate command (summary lines: ruff ok, mypy ok, N passed,
      coverage %).
- [ ] For stories with a CLI or runtime behavior: a transcript of the demo command(s)
      listed in the story.

### Delivery
- [ ] Single commit following `COMMIT-POLICY.md`, pushed to `origin`.

## What DONE does not mean

Done means the story's contract is met and verified by its tests. It does not mean the
implementer reviewed itself as "good"; review is a separate story type (`REVIEW` tasks in
each epic) and QC of the kernel as a whole happens at the epic gate (`WBS.md` §Epic gates).
