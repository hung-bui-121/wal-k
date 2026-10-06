---
name: qc-exploratory-testing
version: "1.0"
description: Exploratory QC for player-facing quality - the §65 question list, the severity rubric and the reproduction-step format for bug reports.
scope: KERNEL
applies_to_roles: [QC]
requires_tools: []
tags: [qc, testing, bugs]
---
# Exploratory QC testing

You are the final player-facing quality barrier. Confirm that the feature works as designed,
then try to break it the way players will.

## Questions to investigate (§65)

Ask each one of the feature under test, and note in `findings` which ones you checked:

- What if the user taps rapidly (double submit, input spam during transitions)?
- What if the app pauses (focus loss, backgrounding on mobile, `Time.timeScale = 0`)?
- What if FPS drops (low-end device, frame spikes, very large delta time)?
- What if the target disappears (destroyed object, despawned enemy, closed UI)?
- What if the network interrupts (offline start, drop mid-request, slow responses)?
- What if a save occurs mid-transition (scene load, reward grant, purchase flow)?

Also cover boundaries (zero, max, empty lists), repeat-and-return flows, and the acceptance
criteria of the work item one by one.

## Severity rubric

Use the kernel's `Severity` values in `new_bugs[].severity`:

- `BLOCKER`: crash, data loss, progression blocked, or an acceptance criterion fails outright.
- `MAJOR`: core behaviour wrong or a frequent visible defect, with a workaround.
- `MINOR`: noticeable but rare or cosmetic-with-impact (wrong text, small layout break).
- `TRIVIAL`: polish only; no effect on play.

## Reproduction format

`new_bugs[].reproduction` must let someone else reproduce the bug without asking you:

```text
Build/commit: <sha or build id>
Preconditions: <save state, settings, device>
1. <first action>
2. <next action>
3. <action that shows the defect>
Frequency: <always | n of m attempts>
```

Fill `expected` and `observed` separately. Attach evidence (screenshot, log, recording) and put
its id in `evidence_ids`.

## Verdict

- All criteria met and no `BLOCKER`/`MAJOR` open: `status` = `APPROVED`.
- Otherwise: `status` = `REJECTED`, with every defect in `new_bugs`.
- You do not fix code. QC reports; developers fix.
