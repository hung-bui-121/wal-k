"""Agent roles (§10, §11, §101)."""

from enum import StrEnum


class AgentRole(StrEnum):
    """Roles that own work, decisions and ledger entries.

    `USER` and `KERNEL` are actors only; they are never instantiated as agents.
    """

    ORCHESTRATOR = "ORCHESTRATOR"
    PRODUCT_OWNER = "PRODUCT_OWNER"
    SCRUM_MASTER = "SCRUM_MASTER"
    DESIGN_LEADER = "DESIGN_LEADER"
    ART_DIRECTOR = "ART_DIRECTOR"
    LEAD_DEV = "LEAD_DEV"
    SENIOR_DEV = "SENIOR_DEV"
    QC = "QC"
    UA_RELEASE = "UA_RELEASE"
    GAME_DIRECTOR = "GAME_DIRECTOR"
    PROCESS_ARCHITECT = "PROCESS_ARCHITECT"
    USER = "USER"
    KERNEL = "KERNEL"
