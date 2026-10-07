import fnmatch
import os
import sys
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_codex_launcher import FakeCodexProcessLauncher
from tests.fakes.fake_model_adapter import fake_descriptor
from tests.runtime.executor_env import CODEX_MODEL, EnvFactory
from walk.agents import AgentInput
from walk.integrations import (
    CREDENTIAL_NAMES,
    UNITY_SECRET_NAMES,
    AsyncioSubprocessRunner,
)
from walk.integrations.subprocess import resolve_executable
from walk.model_router.adapters.codex import CodexAdapter
from walk.runtime.sandbox import AGENT_ENV_ALLOWLIST, WINDOWS_AGENT_ENV_ALLOWLIST, scrubbed_env

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
    env = {"WALKX_A": "a", "WALKX": "b", "XWALKX_A": "c", "HOMEPATH": "d"}

    assert scrubbed_env(env, allowlist=("WALKX_*",)) == {"WALKX_A": "a"}
    assert "UNITY_*" not in AGENT_ENV_ALLOWLIST


def test_unity_secrets_never_reach_agents() -> None:
    secrets = dict.fromkeys(UNITY_SECRET_NAMES, "secret")
    env = {**secrets, "UNITY_EDITOR_PATH": "/opt/unity", "UNITY_VERSION": "6000.0.1f1"}

    kept = scrubbed_env(env)

    assert kept == {"UNITY_EDITOR_PATH": "/opt/unity", "UNITY_VERSION": "6000.0.1f1"}
    assert set(UNITY_SECRET_NAMES) == {
        "UNITY_PASSWORD",
        "UNITY_SERIAL",
        "UNITY_LICENSE",
        "UNITY_EMAIL",
    }
    assert set(UNITY_SECRET_NAMES) <= set(CREDENTIAL_NAMES)
    for platform in ("win32", "linux"):
        assert not set(UNITY_SECRET_NAMES) & set(scrubbed_env(env, platform=platform))


def test_scrubbed_env_case_rules_follow_platform() -> None:
    env = {"Path": "C:/bin", "unity_editor_path": "u", "SystemRoot": "C:/Windows", "Secret": "s"}

    kept = scrubbed_env(env, platform="win32")
    assert kept == {"Path": "C:/bin", "unity_editor_path": "u", "SystemRoot": "C:/Windows"}

    assert scrubbed_env(env, platform="linux") == {}


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
    windows = WINDOWS_AGENT_ENV_ALLOWLIST if sys.platform == "win32" else ()
    allowed = {entry for entry in (*AGENT_ENV_ALLOWLIST, *windows) if not entry.endswith("*")}
    assert all(key.upper() in allowed or key.upper().startswith("UNITY_") for key in captured), (
        sorted(captured)
    )


WINDOWS_ENV = {
    "APPDATA": "C:/Users/u/AppData/Roaming",
    "LOCALAPPDATA": "C:/Users/u/AppData/Local",
    "PATHEXT": ".COM;.EXE;.BAT;.CMD",
    "ComSpec": "C:/Windows/system32/cmd.exe",
    "SystemRoot": "C:/Windows",
    "PATH": "C:/bin",
}
CREDENTIAL_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def test_scrubbed_env_keeps_windows_system_variables_on_win32() -> None:
    assert scrubbed_env(WINDOWS_ENV, platform="win32") == WINDOWS_ENV


def test_scrubbed_env_posix_ignores_windows_list() -> None:
    kept = scrubbed_env(WINDOWS_ENV, platform="linux")

    assert kept == {"PATH": "C:/bin"}
    for name in ("APPDATA", "LOCALAPPDATA", "PATHEXT", "ComSpec"):
        assert name not in kept


def test_scrubbed_env_drops_secrets_on_win32() -> None:
    secrets = {
        "ANTHROPIC_API_KEY": "sk-ant",
        "JIRA_API_TOKEN": "jira",
        "OPENAI_API_KEY": "sk-openai",
        "GITHUB_TOKEN": "ghp",
    }

    kept = scrubbed_env({**WINDOWS_ENV, **secrets}, platform="win32")

    assert kept == WINDOWS_ENV
    assert not set(secrets) & set(kept)


def test_allowlist_never_matches_a_credential_name() -> None:
    entries = (*AGENT_ENV_ALLOWLIST, *WINDOWS_AGENT_ENV_ALLOWLIST)
    candidates = (*CREDENTIAL_NAMES, *CREDENTIAL_WORDS)

    for entry in entries:
        assert not any(word in entry.upper() for word in CREDENTIAL_WORDS), entry
        for name in candidates:
            assert not fnmatch.fnmatchcase(name.upper(), entry.upper()), (entry, name)
    for name in CREDENTIAL_NAMES:
        assert scrubbed_env({name: "secret"}, platform="win32") == {}
        assert scrubbed_env({name: "secret"}, platform="linux") == {}


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "win32", reason="Windows provider CLIs")
@pytest.mark.parametrize("cli", ["claude", "codex"])
async def test_provider_clis_start_with_scrubbed_env_on_windows(cli: str) -> None:
    env = scrubbed_env(os.environ)
    if resolve_executable(cli, env) is None:
        pytest.skip(f"{cli} is not installed")

    result = await AsyncioSubprocessRunner().run([cli, "--version"], env=env, timeout_s=60)

    assert result.exit_code == 0, result.stderr
