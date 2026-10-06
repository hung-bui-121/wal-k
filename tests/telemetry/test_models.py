import re
from datetime import UTC, datetime
from pathlib import Path

from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.telemetry import (
    EVIDENCE_RANK,
    Evidence,
    EvidenceKind,
    LedgerEvent,
    LedgerEventKind,
    Report,
)

DOMAIN_MODEL = Path(__file__).resolve().parents[2] / "docs" / "01-architecture" / "DOMAIN-MODEL.md"


def _documented_members(enum_name: str) -> list[str]:
    text = DOMAIN_MODEL.read_text(encoding="utf-8")
    block = text[text.index(f"class {enum_name}(StrEnum):") :]
    # The class ends at the code fence or at the next top-level statement, whichever is first.
    ends = [i for i in (block.find("```"), block.find("\n\n\n")) if i != -1]
    block = block[: min(ends)]
    return re.findall(r"^    ([A-Z_]+) = ", block, flags=re.MULTILINE)


def test_ledger_event_kinds_match_domain_model() -> None:
    documented = _documented_members("LedgerEventKind")
    assert len(documented) == 48
    assert [kind.name for kind in LedgerEventKind] == documented
    assert all(kind.value == kind.name for kind in LedgerEventKind)


def test_evidence_kinds_match_domain_model() -> None:
    assert [kind.name for kind in EvidenceKind] == _documented_members("EvidenceKind")


def test_evidence_rank_is_total_and_ordered() -> None:
    assert set(EVIDENCE_RANK) == set(EvidenceKind)
    top = max(EVIDENCE_RANK.values())
    assert [k for k, v in EVIDENCE_RANK.items() if v == top] == [EvidenceKind.PLAYER_TELEMETRY]
    assert min(EVIDENCE_RANK, key=EVIDENCE_RANK.__getitem__) is EvidenceKind.PREFERENCE
    assert EVIDENCE_RANK[EvidenceKind.AUTOMATED_TEST] > EVIDENCE_RANK[EvidenceKind.EXPERT_REASONING]


def test_evidence_rank_property_uses_table() -> None:
    evidence = Evidence(
        id="EVD-000001",
        kind=EvidenceKind.PLAYTEST,
        description="playtest notes",
        uri=".ai/features/FEAT-0001/evidence/playtest.md",
        sha256=None,
        produced_by=Actor(role=AgentRole.QC),
        produced_at=datetime(2026, 1, 1, tzinfo=UTC),
        work_item_id="FEAT-0001",
        phase_id=None,
        commit=None,
    )
    assert evidence.rank == 6


def test_ledger_event_defaults_id_and_time_but_tracks_them_as_unset() -> None:
    event = LedgerEvent(kind=LedgerEventKind.ERROR, project_key="DEMO", actor_role=AgentRole.KERNEL)
    assert event.seq is None
    assert re.fullmatch(r"LED-[0-9A-HJKMNP-TV-Z]{26}", event.id)
    assert event.at.tzinfo is not None
    assert "id" not in event.model_fields_set
    assert "at" not in event.model_fields_set


def test_report_is_frozen_value() -> None:
    report = Report(
        kind="task",
        subject_id="STORY-0001",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        markdown="",
        data={"events": []},
    )
    assert report.model_dump(mode="json")["generated_at"] == "2026-01-01T00:00:00Z"
