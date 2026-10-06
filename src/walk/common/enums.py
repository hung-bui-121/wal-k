"""Cross-cutting enumerations shared by most packages (DOMAIN-MODEL §3)."""

from enum import StrEnum


class Effort(StrEnum):
    """Provider-independent effort levels (§17); adapters translate them (ADR-0011)."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class LearningScope(StrEnum):
    """Project learning versus kernel learning (§110)."""

    PROJECT = "PROJECT"
    KERNEL = "KERNEL"


class ImprovementScope(StrEnum):
    """What may be improved (§100); also the kind of a behavior version (§105)."""

    WORKFLOW = "WORKFLOW"
    CONSTITUTION = "CONSTITUTION"
    SKILL = "SKILL"
    PROMPT = "PROMPT"
    CONTEXT_FORMAT = "CONTEXT_FORMAT"
    STORY_TEMPLATE = "STORY_TEMPLATE"
    MODEL_ROUTING = "MODEL_ROUTING"
    EFFORT_POLICY = "EFFORT_POLICY"
    TOOL_USAGE = "TOOL_USAGE"
    HOOK = "HOOK"
    QUALITY_GATE = "QUALITY_GATE"


class Capability(StrEnum):
    """Model capability dimensions (§16)."""

    CODING = "CODING"
    ARCHITECTURE = "ARCHITECTURE"
    REPOSITORY_NAVIGATION = "REPOSITORY_NAVIGATION"
    LONG_CONTEXT_REASONING = "LONG_CONTEXT_REASONING"
    DESIGN_REASONING = "DESIGN_REASONING"
    VISUAL_REASONING = "VISUAL_REASONING"
    TOOL_USE = "TOOL_USE"
    REVIEW = "REVIEW"
    PLANNING = "PLANNING"
