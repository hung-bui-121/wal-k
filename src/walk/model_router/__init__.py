"""Model routing and the provider adapter boundary (§14-§17, §21-§23; ADR-0004, ADR-0011)."""

from walk.model_router.costing import estimate_usage_cost_usd, usage_to_cost_record
from walk.model_router.errors import BlockedProvider, NotResumable
from walk.model_router.models import (
    MAX_FALLBACKS_PER_RUN,
    AdapterHealth,
    AgentEvent,
    AgentEventKind,
    CapabilityRegistry,
    FallbackRequest,
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
from walk.model_router.service import (
    ERROR_TRIGGER_MAP,
    PROVIDER_WIDE_TRIGGERS,
    DefaultModelRouter,
)

__all__ = [
    "ERROR_TRIGGER_MAP",
    "FAMILY_PATTERN",
    "MAX_FALLBACKS_PER_RUN",
    "OUTPUT_RELATIVE_PATH",
    "PROVIDER_WIDE_TRIGGERS",
    "AdapterHealth",
    "AgentEvent",
    "AgentEventKind",
    "BlockedProvider",
    "CapabilityRegistry",
    "DefaultModelRouter",
    "FallbackRequest",
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
