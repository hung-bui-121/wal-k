import os
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_codex_launcher import FakeCodexProcessLauncher
from tests.fakes.fake_model_adapter import fake_descriptor
from tests.runtime.executor_env import CODEX_MODEL, EnvFactory
from walk.agents import AgentInput
from walk.model_router.adapters.codex import CodexAdapter
from walk.runtime.sandbox import AGENT_ENV_ALLOWLIST, scrubbed_env

CODEX_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "codex"


def test_scrubbed_env_drops_secrets_and_keeps_allowlist() -> None:
    env = {
        "ANTHROPIC_API_KEY": "sk-ant",
        "JIRA_API_TOKEN": "jira",
        "PATH": "/usr/bin",
        "UNITY_EDITOR_PATH": "/opt/unity",
    }

    assert scrubbed_env(env) == {"PATH": "/usr/bin", "UNITY_EDITOR_PATH": "/opt/unity"}


def test_scrubbed_env_glob_matches_prefix_only() -> None:
    env = {"UNITY_": "a", "UNITY_LICENSE": "b", "UNITYX": "c", "XUNITY_A": "d", "HOMEPATH": "e"}

    assert scrubbed_env(env) == {"UNITY_": "a", "UNITY_LICENSE": "b"}
    assert "UNITY_*" in AGENT_ENV_ALLOWLIST


def test_scrubbed_env_case_rules_follow_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"Path": "C:/bin", "unity_editor": "u", "SystemRoot": "C:/Windows", "Secret": "s"}

    monkeypatch.setattr("sys.platform", "win32")
    assert scrubbed_env(env) == {"Path": "C:/bin", "unity_editor": "u", "SystemRoot": "C:/Windows"}

    monkeypatch.setattr("sys.platform", "linux")
    assert scrubbed_env(env) == {}


async def test_codex_subprocess_env_is_scrubbed(
    make_executor_env: EnvFactory, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sentinel-anthropic")
    monkeypatch.setenv("JIRA_API_TOKEN", "sentinel-jira")
    monkeypatch.setenv("UNITY_EDITOR_PATH", "/opt/unity")
    lines = (CODEX_FIXTURES / "exec_success.jsonl").read_text(encoding="utf-8").splitlines()
    launcher = FakeCodexProcessLauncher(lines)

    def prompt(agent_input: AgentInput) -> str:
        return agent_input.role.value

    adapter = CodexAdapter(
        launcher,
        [fake_descriptor(CODEX_MODEL, "codex")],
        fake_clock,
        system_prompt_builder=prompt,
        user_message_builder=prompt,
    )
    env = await make_executor_env(adapters={"codex": adapter})

    await env.run_to_end()

    assert launcher.launches
    captured = launcher.launches[0].env
    assert captured == scrubbed_env(os.environ)
    assert "ANTHROPIC_API_KEY" not in captured
    assert "JIRA_API_TOKEN" not in captured
    assert captured["UNITY_EDITOR_PATH"] == "/opt/unity"
    allowed = {entry for entry in AGENT_ENV_ALLOWLIST if not entry.endswith("*")}
    assert all(key.upper() in allowed or key.upper().startswith("UNITY_") for key in captured), (
        sorted(captured)
    )
