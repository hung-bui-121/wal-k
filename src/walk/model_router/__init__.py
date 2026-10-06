"""Model routing and the provider adapter boundary (§14-§17, §21-§23; ADR-0004, ADR-0011)."""

from walk.model_router.costing import estimate_usage_cost_usd, usage_to_cost_record
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
from walk.model_router.registry import (
    FAMILY_PATTERN,
    FamilyLevel,
    ModelsConfig,
    build_registry,
    load_models_config,
    resolve_family,
)
from walk.model_router.service import ERROR_TRIGGER_MAP, DefaultModelRouter

__all__ = [
    "ERROR_TRIGGER_MAP",
    "FAMILY_PATTERN",
    "OUTPUT_RELATIVE_PATH",
    "AdapterHealth",
    "AgentEvent",
    "AgentEventKind",
    "BlockedProvider",
    "CapabilityRegistry",
    "DefaultModelRouter",
    "FallbackTrigger",
    "FamilyLevel",
    "ModelAdapter",
    "ModelDescriptor",
    "ModelRouter",
    "ModelsConfig",
    "NotResumable",
    "ProviderEffortConfig",
    "ProviderSessionRef",
    "RoutingDecision",
    "RunSession",
    "TaskProfile",
    "UsageReport",
    "build_registry",
    "estimate_usage_cost_usd",
    "load_models_config",
    "parse_agent_output",
    "read_output_file",
    "resolve_family",
    "usage_to_cost_record",
]
