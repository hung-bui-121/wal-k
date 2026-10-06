"""Validate docs/02-work-breakdown consistency.

Checks (exit 1 on any failure):
  1. Every ID in WBS.md section 5 status table has exactly one ``### <ID> —`` section in an epic file.
  2. Every story section has all STORY-TEMPLATE headings in order.
  3. ``Depends on`` IDs exist and point to the same or an earlier epic, and match the WBS table.
  4. Acceptance-criteria test cells match ``tests/<path>.py::test_<name>``.
  5. Requirements field cites at least one ``§NN``.
  6. Status values are legal.

Usage: ``py -3 scripts/validate_wbs.py [--quiet]``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WBS_DIR = ROOT / "docs" / "02-work-breakdown"
ID_RE = re.compile(r"E\d{2}-[SRXB]\d{2}")
HEADINGS = [
    "#### Goal",
    "#### Scope",
    "#### Files",
    "#### Interface contract",
    "#### Behavior",
    "#### Acceptance criteria",
    "#### Evidence required",
    "#### Notes",
    "#### Evidence (filled by implementer)",
]
MANUAL_RE = re.compile(r"manual|gate output|checklist|in Evidence", re.IGNORECASE)
TEST_RE = re.compile(r"^`tests/[\w/.\-]+\.py::test_\w+`$")
STATUS_RE = re.compile(
    r"^(TODO|BLOCKED|IN_PROGRESS|DONE \((?:[0-9a-f]{7,40}|pending)\)|DROPPED)(?:\s|$)"
)


def load_status_table(wbs: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    for line in wbs.splitlines():
        if line.startswith("## 5."):
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if in_table and line.startswith("| E"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6 and ID_RE.fullmatch(cells[0]):
                rows[cells[0]] = {
                    "title": cells[1],
                    "type": cells[2],
                    "deps": cells[3],
                    "effort": cells[4],
                    "status": cells[5],
                }
    return rows


def split_stories(text: str) -> dict[str, str]:
    parts = re.split(r"(?m)^(?=### E\d{2}-[SRXB]\d{2} )", text)
    out: dict[str, str] = {}
    for p in parts:
        m = re.match(r"### (E\d{2}-[SRXB]\d{2}) ", p)
        if m:
            out[m.group(1)] = p
    return out


def main() -> int:
    quiet = "--quiet" in sys.argv
    errors: list[str] = []
    wbs = (WBS_DIR / "WBS.md").read_text(encoding="utf-8")
    table = load_status_table(wbs)
    sections: dict[str, tuple[str, str]] = {}
    epic_files = sorted(WBS_DIR.glob("EPIC-*.md"))
    for f in epic_files:
        for sid, body in split_stories(f.read_text(encoding="utf-8")).items():
            if sid in sections:
                errors.append(f"{sid}: defined twice ({sections[sid][0]} and {f.name})")
            sections[sid] = (f.name, body)

    for sid in table:
        if sid not in sections:
            errors.append(f"{sid}: in WBS status table but no section in any epic file")
    for sid in sections:
        if sid not in table:
            errors.append(
                f"{sid}: section exists in {sections[sid][0]} but missing from WBS status table"
            )

    for sid, (fname, body) in sections.items():
        pos = -1
        for h in HEADINGS:
            i = body.find(h + "\n")
            if i < 0:
                i = body.find(h + " (required)\n")
            if i < 0:
                errors.append(f"{sid} ({fname}): missing heading '{h}'")
            elif i < pos:
                errors.append(f"{sid} ({fname}): heading out of order '{h}'")
            else:
                pos = i
        m = re.search(r"\*\*Status:\*\*\s*(.+)", body)
        if not m or not STATUS_RE.match(m.group(1).strip()):
            errors.append(f"{sid} ({fname}): illegal or missing Status")
        m = re.search(r"\*\*Requirements:\*\*\s*(.+)", body)
        if not m or "§" not in m.group(1):
            errors.append(f"{sid} ({fname}): Requirements must cite §NN")
        m = re.search(r"\*\*Depends on:\*\*\s*(.+)", body)
        if not m:
            errors.append(f"{sid} ({fname}): missing Depends on")
        else:
            deps = ID_RE.findall(m.group(1))
            epic = int(sid[1:3])
            for d in deps:
                if d not in table and d not in sections:
                    errors.append(f"{sid} ({fname}): depends on unknown {d}")
                elif int(d[1:3]) > epic:
                    errors.append(f"{sid} ({fname}): depends on later epic {d}")
            if sid in table:
                tdeps = set(ID_RE.findall(table[sid]["deps"]))
                if tdeps != set(deps):
                    errors.append(
                        f"{sid} ({fname}): Depends on differs from WBS table "
                        f"({sorted(deps)} vs {sorted(tdeps)})"
                    )
        ac = body.split("#### Acceptance criteria", 1)[-1]
        ac = ac.split("#### Evidence required", 1)[0]
        is_manual_task = sid[4] in "RX"
        rows = [ln for ln in ac.splitlines() if re.match(r"^\|\s*\d+\s*\|", ln)]
        if not rows:
            errors.append(f"{sid} ({fname}): no acceptance-criteria rows")
        for r in rows:
            cells = [c.strip() for c in r.strip().strip("|").split("|")]
            if len(cells) < 3:
                errors.append(f"{sid} ({fname}): malformed AC row: {r[:60]}")
                continue
            test = cells[-1]
            if is_manual_task and MANUAL_RE.search(test):
                continue
            if not TEST_RE.match(test):
                errors.append(
                    f"{sid} ({fname}): AC row {cells[0]} test cell not "
                    f"`tests/<path>.py::test_<name>`: {test[:80]}"
                )

    if errors:
        for e in errors:
            print("ERROR", e)
        print(
            f"\n{len(errors)} error(s); {len(sections)} stories checked in {len(epic_files)} epic files"
        )
        return 1
    if not quiet:
        print(f"OK: {len(sections)} stories, {len(table)} table rows, all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
