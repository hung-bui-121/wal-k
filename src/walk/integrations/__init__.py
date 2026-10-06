"""Provider boundary: integration protocols, credentials, subprocesses and the git provider."""

from walk.integrations.credentials import CREDENTIAL_NAMES, CredentialStore
from walk.integrations.errors import GitError, NotSupported
from walk.integrations.git import GitCliProvider
from walk.integrations.git.guard_hooks import GUARD_HOOK_MARKER, render_guard_hook
from walk.integrations.git.provider import FORBIDDEN_COMMIT_PATHSPECS, WORK_ITEM_TRAILER
from walk.integrations.manifest import ManifestStore
from walk.integrations.models import (
    AssetJob,
    AssetProvenance,
    AssetRequest,
    BuildTarget,
    CommitInfo,
    ComponentStatus,
    EnvironmentManifest,
    GraphEdge,
    GraphNeighborhood,
    GraphNode,
    JobResult,
    ProductionKit,
    PullRequestRef,
    ReadinessState,
    WorkItemRef,
    WorkProviderEvent,
)
from walk.integrations.protocols import (
    AssetProvider,
    CiProvider,
    CodeGraphProvider,
    GitProvider,
    IntegrationManager,
    UnityProvider,
    WorkProvider,
)
from walk.integrations.service import DefaultIntegrationManager
from walk.integrations.subprocess import (
    AsyncioSubprocessRunner,
    SubprocessResult,
    SubprocessRunner,
)

__all__ = [
    "CREDENTIAL_NAMES",
    "FORBIDDEN_COMMIT_PATHSPECS",
    "GUARD_HOOK_MARKER",
    "WORK_ITEM_TRAILER",
    "AssetJob",
    "AssetProvenance",
    "AssetProvider",
    "AssetRequest",
    "AsyncioSubprocessRunner",
    "BuildTarget",
    "CiProvider",
    "CodeGraphProvider",
    "CommitInfo",
    "ComponentStatus",
    "CredentialStore",
    "DefaultIntegrationManager",
    "EnvironmentManifest",
    "GitCliProvider",
    "GitError",
    "GitProvider",
    "GraphEdge",
    "GraphNeighborhood",
    "GraphNode",
    "IntegrationManager",
    "JobResult",
    "ManifestStore",
    "NotSupported",
    "ProductionKit",
    "PullRequestRef",
    "ReadinessState",
    "SubprocessResult",
    "SubprocessRunner",
    "UnityProvider",
    "WorkItemRef",
    "WorkProvider",
    "WorkProviderEvent",
    "render_guard_hook",
]
