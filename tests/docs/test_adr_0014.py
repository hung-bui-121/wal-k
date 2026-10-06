import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs" / "01-architecture" / "adr" / "ADR-0014-provider-cli-sdk-verification.md"
TEMPLATE_HEADINGS = ["## Context", "## Decision", "## Alternatives considered", "## Consequences"]
CODEX_FLAGS = [
    "codex exec --json",
    "--sandbox workspace-write",
    "--cd <dir>",
    "-c model=<id>",
    "-c model_reasoning_effort=",
    "--output-schema <file>",
    "codex exec resume <thread_id>",
    "JSON event line kinds",
    "exit codes",
    "network disabled by default under `workspace-write`",
]
SDK_OPTIONS = [
    "`cwd`",
    "`allowed_tools`",
    "`permission_mode`",
    "`can_use_tool`",
    "`model`",
    "`effort`",
    "`max_turns`",
    "`resume`",
    "session id",
    "usage fields",
    "`output_format`",
]


def _text() -> str:
    return ADR.read_text(encoding="utf-8")


def _section(text: str, heading: str, end: str) -> str:
    return text.split(heading, 1)[1].split(end, 1)[0]


def _rows(table_text: str) -> list[list[str]]:
    rows = []
    for line in table_text.splitlines():
        if line.startswith("| ") and not line.startswith("| Assumption") and "---" not in line:
            cells = line.replace("\\|", "\0").strip().strip("|").split("|")
            rows.append([cell.replace("\0", "|").strip() for cell in cells])
    return rows


def test_adr_has_template_structure() -> None:
    text = _text()
    assert "**Status:** Accepted" in text
    positions = [text.index(h) for h in TEMPLATE_HEADINGS]
    assert positions == sorted(positions)


def test_adr_covers_every_codex_flag() -> None:
    codex = _section(_text(), "### Codex CLI", "### Claude Agent SDK")
    for flag in CODEX_FLAGS:
        assert flag in codex, flag


def test_adr_covers_every_sdk_option() -> None:
    sdk = _section(_text(), "### Claude Agent SDK", "### Kernel")
    for option in SDK_OPTIONS:
        assert option in sdk, option


def test_every_deviation_names_affected_story() -> None:
    decision = _section(_text(), "## Decision", "## Alternatives considered")
    rows = _rows(decision)
    assert rows
    for row in rows:
        deviation, consequence = row[3], row[4]
        if deviation:
            assert re.search(r"E01-S2[12]", consequence), row[0]


def test_adr_approves_jinja2_dependency() -> None:
    kernel = _section(_text(), "### Kernel", "## Alternatives considered")
    assert re.search(r"`jinja2`.*\| (Accepted|Verified)", kernel)


def test_probe_scripts_exist_and_are_referenced() -> None:
    evidence = _text().split("## Evidence", 1)[1]
    for script in ("scripts/spikes/codex_probe.sh", "scripts/spikes/claude_probe.py"):
        assert (ROOT / script).is_file(), script
        assert script in evidence, script
