from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.fakes.fake_model_adapter import fake_descriptor
from walk.common.enums import Capability, Effort
from walk.common.errors import PermanentError, TransientError
from walk.model_router import (
    AdapterHealth,
    AgentEvent,
    AgentEventKind,
    BlockedProvider,
    CapabilityRegistry,
    FallbackTrigger,
    NotResumable,
    ProviderEffortConfig,
    ProviderSessionRef,
    RoutingDecision,
    TaskProfile,
    UsageReport,
)
from walk.workflow import Risk

AT = datetime(2026, 1, 1, tzinfo=UTC)
RUN = "RUN-01J00000000000000000000000"


def test_event_kinds_and_triggers_match_architecture() -> None:
    assert [kind.value for kind in AgentEventKind] == [
        "STARTED",
        "TEXT",
        "TOOL_CALL_REQUESTED",
        "TOOL_CALL_RESULT",
        "CHECKPOINT_HINT",
        "USAGE",
        "PARTIAL_OUTPUT",
        "FINAL_OUTPUT",
        "ERROR",
        "ENDED",
    ]
    assert [trigger.value for trigger in FallbackTrigger] == [
        "QUOTA_EXHAUSTED",
        "TOKEN_LIMIT",
        "PROVIDER_OUTAGE",
        "TIMEOUT",
        "RATE_LIMIT",
        "CONTEXT_OVERFLOW",
        "TOOL_INCOMPATIBILITY",
        "BUDGET_RESTRICTION",
        "MODEL_DISABLED",
        "REPEATED_OUTPUT_INVALID",
    ]


def test_descriptor_validation_and_event_frozen() -> None:
    with pytest.raises(ValidationError, match=r"0\.\.5"):
        fake_descriptor("fake-codex/sim", "fake-codex", capabilities={Capability.CODING: 6})
    with pytest.raises(ValidationError, match=r"0\.\.5"):
        fake_descriptor("fake-codex/sim", "fake-codex", capabilities={Capability.CODING: -1})
    event = AgentEvent(kind=AgentEventKind.ENDED, run_id=RUN, at=AT)
    with pytest.raises(ValidationError):
        event.text = "changed"  # type: ignore[misc]  # frozen model on purpose
    with pytest.raises(ValidationError):
        AgentEvent(kind=AgentEventKind.TEXT, run_id=RUN, at=AT, thinking="x")  # type: ignore[call-arg]  # extra field on purpose


def test_router_value_objects_round_trip() -> None:
    descriptor = fake_descriptor("fake-codex/sim", "fake-codex", tags=["sim"])
    registry = CapabilityRegistry(models={descriptor.id: descriptor}, version="1.0")
    values = [
        registry,
        TaskProfile(
            required_capabilities=[Capability.CODING],
            required_tools=["edit"],
            required_skills=["git-hygiene"],
            estimated_context_tokens=1000,
            risk=Risk.LOW,
        ),
        RoutingDecision(
            model_id="fake-codex/sim",
            provider="fake-codex",
            effort=Effort.HIGH,
            reason="preferred",
            rejected=[("fake-claude/sim", "health")],
        ),
        ProviderSessionRef(provider="fake-codex", session_id="s1", resumable=True),
        UsageReport(
            input_tokens=1, output_tokens=2, cost_usd=0.1, turns=1, tool_calls=1, duration_s=0.5
        ),
        AdapterHealth(ok=True, provider="fake-codex", detail="ok", checked_at=AT),
        ProviderEffortConfig(model_id="fake-codex/sim", params={"effort": "high"}),
    ]
    for value in values:
        assert type(value).model_validate_json(value.model_dump_json()) == value
    assert descriptor.capabilities[Capability.VISUAL_REASONING] == 4
    assert descriptor.supports_effort_levels == list(Effort)


def test_router_errors_are_typed() -> None:
    assert issubclass(NotResumable, PermanentError)
    assert issubclass(BlockedProvider, TransientError)
    blocked = BlockedProvider("no candidate", detail={"rejected": [["fake-codex/sim", "health"]]})
    assert blocked.detail["rejected"] == [["fake-codex/sim", "health"]]
