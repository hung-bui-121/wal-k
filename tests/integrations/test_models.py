from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from walk.common.models import Actor
from walk.common.roles import AgentRole
from walk.integrations import (
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

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _manifest() -> EnvironmentManifest:
    return EnvironmentManifest(
        generated_at=AT,
        machine_id="host-1",
        unity=ComponentStatus(state=ReadinessState.READY, version="6000.0.23f1"),
        tools={"git": ComponentStatus(state=ReadinessState.READY, version="2.41.0")},
        providers={"codex": ComponentStatus(state=ReadinessState.MISSING, detail="not on PATH")},
        work_provider=ComponentStatus(state=ReadinessState.READY),
        credentials={"JIRA_TOKEN": ReadinessState.MISSING},
        required_skills={"git-hygiene": ReadinessState.READY},
        build_targets={"Android": ReadinessState.UNKNOWN},
        drift_from="host-0",
        drift_items=["tools.git.version"],
    )


def test_integration_models_round_trip() -> None:
    manifest = _manifest()
    job = JobResult(
        ok=True,
        job_kind="editmode_tests",
        duration_s=12.5,
        log_path=".walk/logs/editmode.xml",
        artifact_paths=["Builds/report.xml"],
        summary="42 passed",
        metrics={"passed": 42, "failed": 0},
    )
    graph = GraphNeighborhood(
        nodes=[
            GraphNode(id="n1", kind="file", path="Assets/A.cs", name="A.cs"),
            GraphNode(id="n2", kind="class", path=None, name="Player"),
        ],
        edges=[GraphEdge(src="n1", dst="n2", kind="references")],
        depth=1,
    )

    for model in (manifest, job, graph):
        assert type(model).model_validate_json(model.model_dump_json()) == model
    assert [target.value for target in BuildTarget] == [
        "Android",
        "iOS",
        "StandaloneWindows64",
        "StandaloneOSX",
        "WebGL",
    ]


def test_remaining_value_objects_round_trip() -> None:
    request = AssetRequest(
        kind="texture",
        prompt="mossy stone",
        reference_artifact_ids=["APR-0001"],
        constraints={"size": 1024},
        work_item_id="STORY-0001",
    )
    values = [
        WorkItemRef(external_ref="LOCAL-1", url=None),
        CommitInfo(sha="3f9c2e1", message="wip", files=["src/A.cs"]),
        PullRequestRef(number=None, url=None, head="3f9c2e1", base="main"),
        request,
        AssetProvenance(
            asset_path="Assets/T.png",
            provider="meshy",
            prompt="mossy stone",
            reference_concept=None,
            generated_by=Actor(role=AgentRole.KERNEL),
            approved_by=None,
            version=1,
            related_feature_id="FEAT-0001",
            license_or_source="generated",
            job_id="job-1",
        ),
        WorkProviderEvent(
            provider="local",
            external_ref="LOCAL-1",
            kind="TRANSITIONED",
            external_status="In Progress",
            fields={},
            at=AT,
            delivery_id="poll-1",
        ),
        ProductionKit(
            project_constitution_path=".ai/project/constitution.md",
            project_constraints_path=".ai/project/project.md",
            agent_instruction_paths=[".ai/agents/roles/lead_dev.md"],
            skill_names=["git-hygiene"],
            hook_config_path=".ai/agents/hooks.yaml",
            approved_artifact_ids=["APR-0001"],
            tool_config_path=".ai/agents/permissions.yaml",
            environment_manifest_path=".ai/project/environment.yaml",
            initial_memory_paths=[".ai/project/project.md"],
            kernel_versions_path=".ai/project/kernel-versions.yaml",
            kit_version="1.0",
            validated_at=AT,
        ),
    ]
    for value in values:
        assert type(value).model_validate_json(value.model_dump_json()) == value


def test_integration_models_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        JobResult(
            ok=True,
            job_kind="deploy",
            duration_s=1.0,
            log_path="x",
            artifact_paths=[],
            summary="",
            metrics={},
        )
    with pytest.raises(ValidationError):
        CommitInfo(sha="not-a-sha", message="m", files=[])
    with pytest.raises(ValidationError):
        ComponentStatus(state=ReadinessState.READY, colour="red")  # type: ignore[call-arg]  # extra field on purpose
