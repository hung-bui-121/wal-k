import itertools
from pathlib import Path

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_codex_launcher import FakeCodexProcessLauncher
from walk.common.enums import Effort
from walk.model_router import OUTPUT_RELATIVE_PATH, ProviderEffortConfig, RunSession
from walk.model_router.adapters.codex import CodexAdapter
from walk.model_router.adapters.codex.command import build_exec_command
from walk.model_router.adapters.codex.sandbox import sandbox_for_session
from walk.permissions import PermissionDecision, PermissionEffect, ToolCallRequest

CODEX = "codex/gpt-5-codex"


async def _allow(request: ToolCallRequest) -> PermissionDecision:
    del request
    return PermissionDecision(effect=PermissionEffect.ALLOW, matched_rule=None, reason="ok")


def _session(worktree: Path) -> RunSession:
    return RunSession(
        run_id="RUN-01J00000000000000000000000",
        worktree_path=str(worktree),
        allowed_tools=[],
        permission_authorizer=_allow,
        effort=Effort.MEDIUM,
        model_id=CODEX,
        max_turns=10,
        timeout_s=600,
        env_allowlist={},
        output_path=str(worktree / OUTPUT_RELATIVE_PATH),
    )


def _adapter(launcher: FakeCodexProcessLauncher, clock: FakeClock) -> CodexAdapter:
    return CodexAdapter(
        launcher,
        [],
        clock,
        system_prompt_builder=lambda _: "s",
        user_message_builder=lambda _: "u",
    )


def test_configure_sandbox_defaults(tmp_path: Path, fake_clock: FakeClock) -> None:
    adapter = _adapter(FakeCodexProcessLauncher(), fake_clock)

    sandbox = adapter.configure_sandbox(_session(tmp_path))

    assert sandbox.mode == "workspace-write"
    assert sandbox.cwd == str(tmp_path)
    assert sandbox.network_enabled is False
    assert sandbox.writable_roots == []
    cfg = ProviderEffortConfig(model_id=CODEX, params={"model_reasoning_effort": "medium"})
    argv = build_exec_command(cfg, sandbox, prompt_file="p", output_schema_path=None)
    pairs = list(itertools.pairwise(argv))
    assert ("--sandbox", "workspace-write") in pairs
    assert ("--cd", str(tmp_path)) in pairs
    assert ("-c", "sandbox_workspace_write.network_access=false") in pairs


def test_sandbox_for_session_options(tmp_path: Path) -> None:
    sandbox = sandbox_for_session(
        _session(tmp_path), network_enabled=True, extra_writable=["/cache"]
    )

    assert sandbox.network_enabled is True
    assert sandbox.writable_roots == ["/cache"]
    assert sandbox.cwd == str(tmp_path)
