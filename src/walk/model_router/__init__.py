"""Model routing and the provider adapter boundary (§14-§17, §21-§23; ADR-0004, ADR-0011)."""

from walk.model_router.errors import BlockedProvider, NotResumable
from walk.model_router.models import (
    AdapterHealth,
    AgentEvent,
    AgentEventKind,
    CapabilityRegistry,
    FallbackTrigger,
    ModelDescriptor,
    ProviderEffortConfig,
    ProviderSessionRef,
    RoutingDecision,
    RunSession,
    TaskProfile,
    UsageReport,
)
from walk.model_router.output import OUTPUT_RELATIVE_PATH, parse_agent_output, read_output_file
from walk.model_router.protocols import ModelAdapter, ModelRouter

__all__ = [
    "OUTPUT_RELATIVE_PATH",
    "AdapterHealth",
    "AgentEvent",
    "AgentEventKind",
    "BlockedProvider",
    "CapabilityRegistry",
    "FallbackTrigger",
    "ModelAdapter",
    "ModelDescriptor",
    "ModelRouter",
    "NotResumable",
    "ProviderEffortConfig",
    "ProviderSessionRef",
    "RoutingDecision",
    "RunSession",
    "TaskProfile",
    "UsageReport",
    "parse_agent_output",
    "read_output_file",
]
