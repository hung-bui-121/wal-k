from pathlib import Path

from walk.runtime.sandbox import AGENT_ENV_ALLOWLIST, WINDOWS_AGENT_ENV_ALLOWLIST

ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = ROOT / "docs" / "01-architecture" / "ARCHITECTURE.md"
ADR_0009 = (
    ROOT / "docs" / "01-architecture" / "adr" / "ADR-0009-runtime-topology-and-open-questions.md"
)


def _row(path: Path, first_cell: str) -> str:
    """The markdown table row whose first cell is ``first_cell``."""
    prefix = f"| {first_cell} |"
    rows = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(prefix)
    ]
    assert len(rows) == 1, f"expected one {prefix!r} row in {path.name}, found {len(rows)}"
    return rows[0]


def test_secret_isolation_row_describes_cli_subprocesses() -> None:
    row = _row(ARCHITECTURE, "Secret isolation")

    assert "subprocess" in row
    assert "scrubbed_transport" in row
    assert "inside the kernel process" not in row


def test_secret_isolation_row_lists_the_agent_allowlist() -> None:
    row = _row(ARCHITECTURE, "Secret isolation")

    missing = [
        e for e in (*AGENT_ENV_ALLOWLIST, *WINDOWS_AGENT_ENV_ALLOWLIST) if f"`{e}`" not in row
    ]
    assert not missing, f"ARCHITECTURE §6 'Secret isolation' lacks {missing}"


def test_adr_0009_states_no_provider_key_injection() -> None:
    row = _row(ADR_0009, "D-8")

    assert "`ANTHROPIC_API_KEY` is never passed to an agent subprocess" in row
    assert "claude login" in row
