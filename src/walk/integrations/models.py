"""Integration contracts (DOMAIN-MODEL §4.13; INTERFACES §2.2-§2.6 value objects, WBS §3.2)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from walk.common.ids import ApprovedArtifactId, FeatureId, Sha, SkillName, WorkItemId
from walk.common.models import Actor, FrozenModel, JsonDict, WalkModel


class ReadinessState(StrEnum):
    """Readiness of one environment component (§26)."""

    READY = "ready"
    MISSING = "missing"
    MISCONFIGURED = "misconfigured"
    UNKNOWN = "unknown"


class ComponentStatus(WalkModel):
    """Health of one tool, provider or service."""

    state: ReadinessState = Field(description="Readiness of the component.")
    version: str | None = Field(default=None, description="Detected version, if known.")
    detail: str = Field(default="", description="Human-readable reason or hint.")


class EnvironmentManifest(WalkModel):
    """§26 `.ai/project/environment.yaml`; produced by `walk doctor` / bootstrap preflight."""

    generated_at: datetime = Field(description="When the manifest was produced (UTC).")
    machine_id: str = Field(description="Identifier of the machine that produced it.")
    unity: ComponentStatus = Field(description="Unity editor installation.")
    unity_packages: dict[str, ComponentStatus] = Field(
        default_factory=dict, description="Unity packages by package name."
    )
    tools: dict[str, ComponentStatus] = Field(
        default_factory=dict, description="git, unity_cli, graphify, dotnet, …"
    )
    providers: dict[str, ComponentStatus] = Field(
        default_factory=dict, description="claude, codex, meshy, …"
    )
    work_provider: ComponentStatus = Field(description="The configured work provider.")
    credentials: dict[str, ReadinessState] = Field(
        default_factory=dict, description="Presence only — never values"
    )
    required_skills: dict[SkillName, ReadinessState] = Field(
        default_factory=dict, description="Readiness of each skill the project requires."
    )
    build_targets: dict[str, ReadinessState] = Field(
        default_factory=dict, description="Readiness of each Unity build target."
    )
    drift_from: str | None = Field(
        default=None, description="machine_id of the manifest this one was compared against (§27)"
    )
    drift_items: list[str] = Field(
        default_factory=list, description="Keys that differ from the compared manifest (§27)."
    )


class ProductionKit(WalkModel):
    """§24 what bootstrap creates/validates (ARCHITECTURE.md §8 paths)."""

    project_constitution_path: str = Field(description=".ai/project/constitution.md")
    project_constraints_path: str = Field(description="Section of project.md")
    agent_instruction_paths: list[str] = Field(description=".ai/agents/roles/*.md")
    skill_names: list[SkillName] = Field(description="Skills the kit ships or requires.")
    hook_config_path: str = Field(description=".ai/agents/hooks.yaml")
    approved_artifact_ids: list[ApprovedArtifactId] = Field(
        description="Approved artifacts present in the kit."
    )
    tool_config_path: str = Field(description=".ai/agents/permissions.yaml + models.yaml")
    environment_manifest_path: str = Field(description=".ai/project/environment.yaml")
    initial_memory_paths: list[str] = Field(description="project.md, kernel-versions.yaml")
    kernel_versions_path: str = Field(description=".ai/project/kernel-versions.yaml")
    kit_version: str = Field(description="Version of the production kit.")
    validated_at: datetime = Field(description="When the kit was last validated (UTC).")


class WorkProviderEvent(FrozenModel):
    """Normalised inbound work-state change (webhook or poll)."""

    provider: str = Field(description="Work provider name, e.g. 'local', 'jira'.")
    external_ref: str = Field(description="Provider-side reference of the work item.")
    kind: Literal["CREATED", "UPDATED", "TRANSITIONED", "COMMENTED", "DELETED"] = Field(
        description="What changed."
    )
    external_status: str | None = Field(description="Provider status name after the change.")
    fields: JsonDict = Field(description="Changed provider fields.")
    at: datetime = Field(description="When the change happened (UTC).")
    delivery_id: str = Field(description="Webhook delivery id / poll batch id for dedup")


class WorkItemRef(FrozenModel):
    """Reference to a work item in the work provider (INTERFACES §2.2)."""

    external_ref: str = Field(description="Provider-side key, e.g. 'GAME-12'.")
    url: str | None = Field(description="Browser URL of the item, if the provider has one.")


class CommitInfo(FrozenModel):
    """A commit created by the kernel (INTERFACES §2.3)."""

    sha: Sha = Field(description="Commit sha.")
    message: str = Field(description="Full commit message including trailers.")
    files: list[str] = Field(description="Repository-relative paths in the commit (POSIX).")


class PullRequestRef(FrozenModel):
    """A pull request (or local PR stub) for a branch (INTERFACES §2.3)."""

    number: int | None = Field(description="Provider PR number; None for a local stub.")
    url: str | None = Field(description="Browser URL of the PR, if any.")
    head: Sha = Field(description="Head commit of the PR.")
    base: str = Field(description="Target branch.")


class BuildTarget(StrEnum):
    """Unity build targets (INTERFACES §2.4)."""

    ANDROID = "Android"
    IOS = "iOS"
    STANDALONE_WIN64 = "StandaloneWindows64"
    STANDALONE_OSX = "StandaloneOSX"
    WEBGL = "WebGL"


class JobResult(FrozenModel):
    """Result of one Unity/CI job (INTERFACES §2.4)."""

    ok: bool = Field(description="Whether the job succeeded.")
    job_kind: Literal[
        "compile",
        "editmode_tests",
        "playmode_tests",
        "build",
        "asset_validation",
        "static_check",
        "perf_smoke",
    ] = Field(description="What the job did.")
    duration_s: float = Field(description="Job duration in seconds.")
    log_path: str = Field(description="Path of the job log.")
    artifact_paths: list[str] = Field(description="Paths of produced artifacts.")
    summary: str = Field(description="One-line human summary.")
    metrics: JsonDict = Field(description="Job-specific metrics (test counts, sizes, …).")


class AssetRequest(FrozenModel):
    """Request for a generated asset (INTERFACES §2.5)."""

    kind: Literal["model3d", "texture", "image", "animation", "audio"] = Field(
        description="Kind of asset to generate."
    )
    prompt: str = Field(description="Generation prompt.")
    reference_artifact_ids: list[ApprovedArtifactId] = Field(
        description="Approved artifacts used as references."
    )
    constraints: JsonDict = Field(description="triangle budget, texture size, style tags (§79)")
    work_item_id: WorkItemId = Field(description="Work item the asset is for.")


class AssetJob(FrozenModel):
    """A generation job at an asset provider (INTERFACES §2.5)."""

    provider: str = Field(description="Asset provider name.")
    job_id: str = Field(description="Provider-side job id.")
    state: Literal["QUEUED", "RUNNING", "DONE", "FAILED"] = Field(description="Job state.")
    cost_credits: float | None = Field(description="Provider credits charged, if known.")


class AssetProvenance(FrozenModel):
    """§80 metadata stored next to the asset as `<asset>.provenance.yaml` and as Evidence."""

    asset_path: str = Field(description="Repository path of the asset.")
    provider: str = Field(description="Asset provider that generated it.")
    prompt: str = Field(description="Generation prompt.")
    reference_concept: ApprovedArtifactId | None = Field(
        description="Approved concept used as reference, if any."
    )
    generated_by: Actor = Field(description="Who requested the generation.")
    approved_by: Actor | None = Field(description="Who approved the asset, if anyone yet.")
    version: int = Field(description="Asset version, starting at 1.")
    related_feature_id: FeatureId | None = Field(description="Feature the asset belongs to.")
    license_or_source: str = Field(description="License or source statement.")
    job_id: str = Field(description="Provider job that produced the asset.")


class GraphNode(FrozenModel):
    """Node of the code graph (INTERFACES §2.6)."""

    id: str = Field(description="Graph node id.")
    kind: Literal["file", "class", "method", "asset", "scene", "prefab", "community"] = Field(
        description="Node kind."
    )
    path: str | None = Field(description="Repository path, if the node maps to a file.")
    name: str = Field(description="Display name.")


class GraphEdge(FrozenModel):
    """Directed edge of the code graph (INTERFACES §2.6)."""

    src: str = Field(description="Source node id.")
    dst: str = Field(description="Destination node id.")
    kind: str = Field(description="imports / calls / references / depends_on")


class GraphNeighborhood(FrozenModel):
    """Nodes and edges around a set of seeds (INTERFACES §2.6)."""

    nodes: list[GraphNode] = Field(description="Nodes within the requested depth.")
    edges: list[GraphEdge] = Field(description="Edges between those nodes.")
    depth: int = Field(description="Depth that was expanded.")
