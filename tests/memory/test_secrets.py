from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from walk.common.errors import BoundaryViolation, PermissionDenied
from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.memory import (
    SECRET_PATTERNS,
    DefaultMemoryManager,
    MemoryDocType,
    MemoryIndexRepository,
    SecretDetected,
    contains_secret,
    find_secrets,
    skeleton_for,
)
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository

# Assembled at runtime so that this file itself does not look like it holds secrets.
SAMPLES = {
    "anthropic_key": "sk-ant-" + "a1" * 12,
    "openai_key": "sk-" + "a" * 40,
    "aws_access_key": "AKIA" + "ABCDEFGHIJKLMNOP",
    "github_token": "ghp_" + "b" * 36,
    "jira_token": "ATATT3" + "c" * 24,
    "private_key": "-----BEGIN RSA " + "PRIVATE KEY-----",
    "generic_assignment": 'api_key = "' + "z9" * 8 + '"',
}
LOREM = "Lorem ipsum dolor sit amet, the player jumps; risk-ok token: short; sk-short, AKIA123."


def test_contains_secret_patterns_and_negative() -> None:
    assert [name for name, _ in SECRET_PATTERNS] == list(SAMPLES)
    for name, sample in SAMPLES.items():
        assert contains_secret(f"config: {sample}\n") == name, name
        assert find_secrets(f"config: {sample}\n") == [name], name
    assert contains_secret(LOREM) is None
    assert find_secrets(LOREM) == []


@pytest.mark.parametrize("text", ["task-1234567890123456789012345678901234", "risk-" + "d" * 40])
def test_word_boundary_avoids_false_positives(text: str) -> None:
    assert contains_secret(text) is None


def _written(ai_root: Path) -> bool:
    return any(ai_root.rglob("FEAT-0001*"))


async def test_memory_write_refuses_secret(db: Database, fake_clock: FakeClock) -> None:
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), fake_clock)
    memory = DefaultMemoryManager(
        db.path.parent,
        MemoryIndexRepository(db),
        ledger,
        DefaultHookManager(HookExecutionRepository(db), ledger, fake_clock),
        IdSequenceStore(db),
        fake_clock,
        project_key="DEMO",
    )
    actor = Actor(role=AgentRole.SENIOR_DEV)
    doc = skeleton_for(
        MemoryDocType.FEATURE, "FEAT-0001", "Jump", actor, datetime(2026, 1, 1, tzinfo=UTC)
    )
    doc.sections["Implementation Notes"] = f"use {SAMPLES['github_token']} for the API"

    with pytest.raises(PermissionDenied, match="secret-like content: github_token") as raised:
        await memory.write(doc, actor=actor, head="3f9c2e1", branch="main")

    assert isinstance(raised.value, SecretDetected)
    assert isinstance(raised.value, BoundaryViolation)
    assert not _written(Path(db.path.parent))
