import ast
import asyncio
import importlib.util
import shutil
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

import walk
from tests.cli.conftest import CODEX_MODEL, OverridesFactory, add_story, migrate
from tests.fakes.fake_keyring import FakeKeyringBackend
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from tests.integrations.test_preflight import script_environment
from walk.agents import AgentInput, ConstitutionLoader, ExpectedOutput, ModelPolicy
from walk.cli.composition import (
    DEFAULT_READY_ENV_KEYS,
    KernelSettings,
    build_kernel,
    open_integrations,
)
from walk.common.enums import Effort
from walk.common.errors import ConfigError
from walk.common.roles import AgentRole
from walk.context import ContextBundle, ContextRequest
from walk.effort import EffortPolicy, EffortRequest
from walk.model_router import TaskProfile
from walk.persistence import Database, UnitOfWork
from walk.runtime import AgentRunState
from walk.workflow import Project, ProjectRepository, Risk, Story, StoryContract, WorkItemState

SERVICES = (
    "settings",
    "project_key",
    "kernel_instance",
    "db",
    "ledger",
    "telemetry",
    "evidence",
    "hooks",
    "workflow",
    "budgets",
    "costs",
    "effort",
    "tools",
    "permissions",
    "memory",
    "agents",
    "router",
    "git",
    "context",
    "checkpoints",
    "tool_invoker",
    "executor",
    "recovery",
    "scheduler",
    "orchestrator",
    "status_builder",
    "credentials",
)
SRC = Path(walk.__file__).resolve().parent
AGENT_DEFAULTS = SRC / "agents" / "defaults"


def _profile() -> TaskProfile:
    return TaskProfile(
        required_capabilities=[],
        required_tools=[],
        required_skills=[],
        estimated_context_tokens=0,
        risk=Risk.MEDIUM,
    )


def _input() -> AgentInput:
    constitution = ConstitutionLoader(AGENT_DEFAULTS, None).load(AgentRole.SENIOR_DEV)
    request = ContextRequest(
        work_item_id="STORY-0001", role=AgentRole.SENIOR_DEV, effort=Effort.MEDIUM, token_budget=1
    )
    return AgentInput(
        run_id="RUN-01J0000000000000000000000A",
        role=AgentRole.SENIOR_DEV,
        constitution=constitution,
        authority=constitution.authority,
        task=Story(
            id="STORY-0001", project_key="DEMO", title="t", contract=StoryContract(goal="g")
        ),
        workflow_state=WorkItemState.IMPLEMENTING,
        phase=None,
        context=ContextBundle(
            request=request,
            items=[],
            total_tokens_estimate=0,
            excluded_count=0,
            head_commit="a" * 40,
            built_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        approved_artifacts=[],
        decisions=[],
        skills=[],
        allowed_tools=[],
        permissions=[],
        budget=[],
        effort=Effort.MEDIUM,
        required_evidence=[],
        expected_output=ExpectedOutput(status_options=[], deliverables=[], required_evidence=[]),
        worktree_path="/wt",
        branch="b",
        instructions_markdown="Do the work",
    )


async def test_build_kernel_wires_all_services_with_fakes(
    kernel_repo: Path, fake_overrides: OverridesFactory
) -> None:
    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=fake_overrides())
    try:
        assert all(getattr(handle, name) is not None for name in SERVICES)
        assert handle.project_key == "DEMO"
        assert handle.kernel_instance == "test-instance"
        migrations = handle.db.connect().execute("SELECT COUNT(*) FROM schema_migrations")
        assert migrations.fetchone()[0] >= 1
        assert handle.executor.running() == []
        assert asyncio.all_tasks() == {asyncio.current_task()}
        policy = ModelPolicy(preferred=[CODEX_MODEL], fallback=["fake-claude/sim"])
        decision = await handle.router.select(
            AgentRole.SENIOR_DEV, policy, _profile(), Effort.MEDIUM
        )
        assert decision.model_id == CODEX_MODEL
        assert handle.router.registry().models["codex/gpt-5-codex"].enabled is False
    finally:
        await handle.aclose()


async def test_build_kernel_resolves_credentials_through_keyring_override(
    kernel_repo: Path, fake_overrides: OverridesFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    backend = FakeKeyringBackend({"JIRA_API_TOKEN": "from-fake-keyring"})
    overrides = fake_overrides(keyring_backend=backend)

    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=overrides)
    try:
        secret = handle.credentials.get("JIRA_API_TOKEN")
        assert secret is not None
        assert secret.get_secret_value() == "from-fake-keyring"
        assert backend.calls == [("walk", "JIRA_API_TOKEN")]
    finally:
        await handle.aclose()


async def test_build_kernel_disables_missing_claude_sdk(
    kernel_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_find_spec = importlib.util.find_spec

    def without_claude(name: str, package: str | None = None) -> object:
        if name == "claude_agent_sdk":
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", without_claude)
    handle = build_kernel(KernelSettings(repo_path=kernel_repo))
    try:
        models = handle.router.registry().models
        claude = [d for d in models.values() if d.provider == "claude"]
        assert claude
        assert all(not d.enabled for d in claude)
        assert handle.router.adapter_for("codex/gpt-5-codex").provider == "codex"
    finally:
        await handle.aclose()


async def test_build_kernel_wires_claude_when_sdk_present(
    kernel_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda *_: object())
    constitution = kernel_repo / ".ai" / "project" / "constitution.md"
    constitution.parent.mkdir(parents=True, exist_ok=True)
    constitution.write_bytes(
        b"---\nid: constitution\ntype: project_constitution\n---\n\n## Rules\n\nNo crunch.\n"
    )
    handle = build_kernel(KernelSettings(repo_path=kernel_repo))
    try:
        claude = handle.router.adapter_for("claude/claude-opus-5-5")
        assert claude.provider == "claude"
        assert handle.router.registry().models["claude/claude-opus-5-5"].enabled is True
        agent_input = _input()
        system = claude._system_prompt_builder(agent_input)  # type: ignore[attr-defined]  # noqa: SLF001 - the wired builder
        user = claude._user_message_builder(agent_input)  # type: ignore[attr-defined]  # noqa: SLF001 - the wired builder
        assert "## Project Constitution" in system
        assert "No crunch." in system
        assert user.startswith("Do the work\n\n## Agent Role")
        probe = claude._client._probe  # type: ignore[attr-defined]  # noqa: SLF001 - the wired version probe
        exit_code, stdout, _ = await probe([sys.executable, "--version"])
        assert exit_code == 0
        assert "Python" in stdout
    finally:
        await handle.aclose()


async def test_build_kernel_reads_project_overrides(
    kernel_repo: Path, fake_overrides: OverridesFactory
) -> None:
    policies = kernel_repo / ".ai" / "agents" / "policies.yaml"
    policies.write_bytes(policies.read_bytes() + b"    checkpoint_every_tool_calls: 3\n")
    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=fake_overrides())
    try:
        policy = handle.agents.load_runtime_policy(AgentRole.SENIOR_DEV)
        assert policy.checkpoint_every_tool_calls == 3
        assert policy.model_policy.preferred == [CODEX_MODEL]
    finally:
        await handle.aclose()


def _wired_packages(path: Path) -> set[str]:
    """Packages whose ``service.py`` (directly or via a ``Default*`` re-export) ``path`` uses."""
    own = path.relative_to(SRC).parts[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        parts = node.module.split(".")
        if parts[0] != "walk" or len(parts) < 2 or parts[1] == own:
            continue
        if parts[-1] == "service" or any(a.name.startswith("Default") for a in node.names):
            found.add(parts[1])
    return found


def test_composition_is_only_multi_service_importer() -> None:
    wiring = {
        path.relative_to(SRC).as_posix()
        for path in SRC.rglob("*.py")
        if len(_wired_packages(path)) > 1
    }

    assert wiring == {"cli/composition.py"}


async def test_aclose_leaves_runs_recoverable(
    kernel_repo: Path, fake_overrides: OverridesFactory
) -> None:
    await add_story(kernel_repo, 1, "Double jump")
    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=fake_overrides())
    assert await handle.orchestrator.tick() == 1
    (run,) = handle.executor.running()

    await handle.aclose()
    await handle.aclose()

    db = Database(kernel_repo / ".ai" / "kernel.db")
    try:
        state = db.connect().execute("SELECT state FROM agent_runs WHERE id = ?", (run.id,))
        assert state.fetchone()[0] == AgentRunState.RUNNING.value
    finally:
        db.close()


async def test_build_kernel_requires_single_project(tmp_game_repo: Path) -> None:
    migrate(tmp_game_repo, project=False)

    with pytest.raises(ConfigError, match="walk bootstrap"):
        build_kernel(KernelSettings(repo_path=tmp_game_repo))

    db = Database(tmp_game_repo / ".ai" / "kernel.db")
    async with UnitOfWork(db) as uow:
        for key in ("ONE", "TWO"):
            await ProjectRepository(db).insert(
                Project(key=key, name=key, repo_path=str(tmp_game_repo)), uow
            )
    db.close()
    with pytest.raises(ConfigError, match="exactly one project"):
        build_kernel(KernelSettings(repo_path=tmp_game_repo))


async def test_kernel_defaults_for_environment_effort_and_sleep(
    kernel_repo: Path, fake_overrides: OverridesFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    overrides = fake_overrides(ready_env_keys=None, sleep=None)
    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=overrides)
    try:
        assert handle.executor._ready_env_keys() == set(DEFAULT_READY_ENV_KEYS)  # noqa: SLF001 - wired default
        await handle.executor._sleep(0)  # noqa: SLF001 - the jittered default sleep
        upgraded = await handle.effort.request_change(
            "RUN-01J0000000000000000000000A",
            Effort.MEDIUM,
            EffortRequest(direction="UPGRADE", target=Effort.HIGH, reason="hard bug"),
            EffortPolicy(auto_approve_upgrade_within_budget=False),
            {},
        )
        assert upgraded is Effort.MEDIUM
    finally:
        await handle.aclose()
    monkeypatch.setattr(shutil, "which", lambda _: None)
    handle = build_kernel(KernelSettings(repo_path=kernel_repo), overrides=overrides)
    try:
        assert handle.executor._ready_env_keys() == set()  # noqa: SLF001 - no git on PATH
    finally:
        await handle.aclose()


async def test_open_integrations_wires_the_preflight(tmp_path: Path) -> None:
    fake_runner = script_environment(FakeSubprocessRunner())
    manager = open_integrations(
        tmp_path, runner=fake_runner, keyring_backend=FakeKeyringBackend({"JIRA_EMAIL": "a@b"})
    )

    manifest = await manager.preflight(["git"])

    assert manifest.machine_id == socket.gethostname()
    assert manifest.credentials["JIRA_EMAIL"] == "ready"
    assert (tmp_path / ".ai" / "project" / "environment.yaml").is_file()
