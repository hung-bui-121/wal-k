"""Role constitutions, runtime policies, agent instances and the §126 execution contract.

§8-§15, §22, §126; ADR-0004, ADR-0013.
"""

from walk.agents.constitution_loader import ConstitutionLoader
from walk.agents.errors import ConstitutionError
from walk.agents.handover import HANDOVER_SECTION_FIELDS, from_document, to_document
from walk.agents.models import (
    AgentInput,
    AgentInstance,
    AgentOutput,
    AgentOutputStatus,
    Constitution,
    ExpectedOutput,
    FileChange,
    Finding,
    Handover,
    ModelPolicy,
    NextAction,
    ObservationDraft,
    RuntimePolicy,
    ToolCallSummary,
)
from walk.agents.policy_loader import PolicyLoader
from walk.agents.protocols import AgentManager
from walk.agents.rendering import (
    INPUT_SECTION_ORDER,
    TEMPLATE_PURPOSES,
    TemplateRenderer,
    render_constitution,
    render_input_sections,
)
from walk.agents.service import DefaultAgentManager

__all__ = [
    "HANDOVER_SECTION_FIELDS",
    "INPUT_SECTION_ORDER",
    "TEMPLATE_PURPOSES",
    "AgentInput",
    "AgentInstance",
    "AgentManager",
    "AgentOutput",
    "AgentOutputStatus",
    "Constitution",
    "ConstitutionError",
    "ConstitutionLoader",
    "DefaultAgentManager",
    "ExpectedOutput",
    "FileChange",
    "Finding",
    "Handover",
    "ModelPolicy",
    "NextAction",
    "ObservationDraft",
    "PolicyLoader",
    "RuntimePolicy",
    "TemplateRenderer",
    "ToolCallSummary",
    "from_document",
    "render_constitution",
    "render_input_sections",
    "to_document",
]
