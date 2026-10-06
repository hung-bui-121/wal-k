import importlib.metadata
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_keyring import FakeKeyringBackend
from tests.fakes.fake_subprocess import FakeSubprocessRunner
from walk.common.errors import ConfigError, Timeout
from walk.integrations import (
    CredentialStore,
    DefaultIntegrationManager,
    ManifestStore,
    ReadinessState,
    WorkProviderEvent,
)
from walk.integrations.preflight import (
    REQUIRED_DEFAULT,
    detect_claude_sdk,
    detect_codex_cli,
    detect_credentials,
    detect_dotnet,
    detect_git,
    detect_graphify,
    detect_required_skills,
    detect_unity,
)
from walk.tools import DefaultToolRegistry, ToolKind, ToolSpec, load_tool_specs

AT = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
CODEX_EXEC_HELP = (
    "Usage: codex exec [OPTIONS] [PROMPT]\n"
    "  -c, --config <key=value>\n  -s, --sandbox <SANDBOX_MODE>\n  -C, --cd <DIR>\n"
    "      --output-schema <FILE>\n      --json\n"
)
CODEX_RESUME_HELP = (
    "Usage: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]\n"
    "  -c, --config <key=value>\n      --output-schema <FILE>\n      --json\n"
)
JIRA = {"JIRA_BASE_URL": "https://x", "JIRA_EMAIL": "a@b", "JIRA_API_TOKEN": "t"}


def script_environment(
    runner: FakeSubprocessRunner,
    *,
    git: str | None = "git version 2.45.0",
    unity: str | None = "6000.0.23f1",
    codex: str | None = "codex-cli 0.160.1",
    graphify: str | None = "graphify 0.4.1",
    dotnet: str | None = "8.0.401",
    unity_binary: str = "Unity",
) -> FakeSubprocessRunner:
    """Answer every preflight probe; ``None`` makes that executable missing."""
    missing = FileNotFoundError("not found")
    for argv, out in (
        (["git", "--version"], git),
        ([unity_binary, "-version"], unity),
        (["codex", "--version"], codex),
        (["graphify", "--version"], graphify),
        (["dotnet", "--version"], dotnet),
    ):
        if out is None:
            runner.script(argv, error=missing)
        else:
            runner.script(argv, stdout=out + "\n")
    runner.script(["codex", "exec", "--help"], stdout=CODEX_EXEC_HELP)
    runner.script(["codex", "exec", "resume", "--help"], stdout=CODEX_RESUME_HELP)
    return runner


def write_work_provider(repo: Path, kind: str) -> None:
    path = repo / ".ai" / "project" / "work-provider.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"kind: {kind}\n", encoding="utf-8")


def build_manager(
    repo: Path,
    runner: FakeSubprocessRunner,
    *,
    clock: FakeClock | None = None,
    machine_id: str = "machine-a",
    env: dict[str, str] | None = None,
    tools: list[ToolSpec] | None = None,
    unity_path: str | None = None,
    required_skills: list[str] | None = None,
    available_skills: list[str] | None = None,
    sdk_option_probe: object = None,
) -> DefaultIntegrationManager:
    """A manager over ``repo`` with fakes for every external dependency."""
    time = clock or FakeClock(AT)
    extra: dict[str, object] = {}
    if sdk_option_probe is not None:
        extra["sdk_option_probe"] = sdk_option_probe
    return DefaultIntegrationManager(
        runner=runner,
        credentials=CredentialStore(env or {}, FakeKeyringBackend()),
        manifest_store=ManifestStore(repo / ".ai", time),
        tools=DefaultToolRegistry(load_tool_specs([]) if tools is None else tools),
        clock=time,
        machine_id=machine_id,
        unity_path=unity_path,
        project_path=str(repo),
        required_skills=list(required_skills or []),
        available_skills=list(available_skills or []),
        **extra,  # type: ignore[arg-type]  # optional keyword under test
    )


async def test_detect_git_ready_with_version() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["git", "--version"], stdout="git version 2.45.0.windows.1\n")

    status = await detect_git(runner)

    assert status.state is ReadinessState.READY
    assert status.version == "2.45.0"
    assert runner.calls[0].timeout_s == 5


async def test_detect_missing_executable_reports_missing() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["codex"], error=FileNotFoundError("codex"))

    status = await detect_codex_cli(runner)

    assert status.state is ReadinessState.MISSING
    assert status.version is None


async def test_detect_exit_127_reports_missing() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["graphify"], exit_code=127, stderr="executable not found: graphify")

    status = await detect_graphify(runner)

    assert status.state is ReadinessState.MISSING
    assert "graphify" in status.detail


async def test_detect_nonzero_exit_reports_misconfigured(tmp_path: Path) -> None:
    runner = FakeSubprocessRunner()
    runner.script(["/opt/Unity", "-version"], exit_code=1, stderr="license error\nsecond line\n")

    status = await detect_unity(runner, "/opt/Unity", str(tmp_path))

    assert status.state is ReadinessState.MISCONFIGURED
    assert status.detail == "license error"


async def test_detect_timeout_reports_unknown() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["dotnet"], error=Timeout("subprocess timed out"))

    status = await detect_dotnet(runner)

    assert status.state is ReadinessState.UNKNOWN
    assert "5 s" in status.detail


async def test_detect_unity_reports_project_editor_version(tmp_path: Path) -> None:
    settings = tmp_path / "ProjectSettings"
    settings.mkdir()
    (settings / "ProjectVersion.txt").write_text(
        "m_EditorVersion: 6000.0.23f1\nm_EditorVersionWithRevision: 6000.0.23f1 (abc)\n",
        encoding="utf-8",
    )
    runner = FakeSubprocessRunner()
    runner.script(["Unity", "-version"], stdout="6000.0.23f1\n")

    status = await detect_unity(runner, None, str(tmp_path))

    assert status.state is ReadinessState.READY
    assert status.version == "6000.0.23f1"
    assert status.detail == "project editor 6000.0.23f1"


async def test_detect_codex_checks_adr_0014_flags() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["codex", "--version"], stdout="codex-cli 0.160.1\n")
    runner.script(["codex", "exec", "--help"], stdout=CODEX_EXEC_HELP.replace("--cd", "--dir"))
    runner.script(["codex", "exec", "resume", "--help"], stdout=CODEX_RESUME_HELP)

    status = await detect_codex_cli(runner)

    assert status.state is ReadinessState.MISCONFIGURED
    assert status.version == "0.160.1"
    assert "--cd" in status.detail
    assert "ADR-0014" in status.detail


async def test_detect_codex_ready_when_all_flags_present() -> None:
    runner = script_environment(FakeSubprocessRunner())

    status = await detect_codex_cli(runner)

    assert status.state is ReadinessState.READY
    assert status.version == "0.160.1"
    assert ["codex", "exec", "resume", "--help"] in runner.argvs


async def test_detect_codex_help_failure_is_misconfigured() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["codex", "--version"], stdout="codex-cli 0.160.1\n")
    runner.script(["codex", "exec", "--help"], exit_code=2, stderr="unknown command exec\n")

    status = await detect_codex_cli(runner)

    assert status.state is ReadinessState.MISCONFIGURED
    assert "unknown command exec" in status.detail


def test_detect_claude_sdk_reads_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def installed(name: str) -> str:
        assert name == "claude-agent-sdk"
        return "0.2.163"

    def absent(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.version", installed)
    ready = detect_claude_sdk()
    monkeypatch.setattr("importlib.metadata.version", absent)
    missing = detect_claude_sdk()

    assert ready.state is ReadinessState.READY
    assert ready.version == "0.2.163"
    assert missing.state is ReadinessState.MISSING


def test_detect_credentials_and_required_skills() -> None:
    store = CredentialStore({"JIRA_EMAIL": "a@b"}, None)

    credentials = detect_credentials(store)
    skills = detect_required_skills(["git-hygiene", "walk-output-contract"], ["git-hygiene"])

    assert credentials["JIRA_EMAIL"] is ReadinessState.READY
    assert credentials["JIRA_API_TOKEN"] is ReadinessState.MISSING
    assert skills == {
        "git-hygiene": ReadinessState.READY,
        "walk-output-contract": ReadinessState.MISSING,
    }


async def test_preflight_required_missing_raises_after_writing(tmp_path: Path) -> None:
    write_work_provider(tmp_path, "local")
    manager = build_manager(tmp_path, script_environment(FakeSubprocessRunner(), git=None))

    with pytest.raises(ConfigError, match="git") as raised:
        await manager.preflight(["git"])

    assert raised.value.detail["missing_components"] == ["git"]
    written = ManifestStore(tmp_path / ".ai", FakeClock(AT)).read()
    assert written is not None
    assert written.tools["git"].state is ReadinessState.MISSING


async def test_preflight_builds_every_section(tmp_path: Path) -> None:
    write_work_provider(tmp_path, "local")
    runner = script_environment(FakeSubprocessRunner())
    runner.script(["mytool", "--version"], stdout="mytool 1.2\n")
    tools = [
        *load_tool_specs([]),
        ToolSpec(name="my-tool", kind=ToolKind.CLI, executable="mytool", description="x"),
    ]
    manager = build_manager(
        tmp_path,
        runner,
        env={"JIRA_EMAIL": "a@b"},
        tools=tools,
        required_skills=["git-hygiene"],
        sdk_option_probe=list,
    )

    manifest = await manager.preflight(list(REQUIRED_DEFAULT))

    assert manifest.generated_at == AT
    assert manifest.machine_id == "machine-a"
    assert set(manifest.tools) == {"git", "graphify", "dotnet", "my-tool"}
    assert manifest.tools["my-tool"].version == "1.2"
    assert manifest.unity.state is ReadinessState.READY
    assert set(manifest.providers) == {"codex", "claude"}
    assert manifest.work_provider.state is ReadinessState.READY
    assert manifest.credentials["JIRA_EMAIL"] is ReadinessState.READY
    assert manifest.required_skills == {"git-hygiene": ReadinessState.MISSING}
    assert sorted(argv[0] for argv in runner.argvs if argv[-1] == "--version") == [
        "codex",
        "dotnet",
        "git",
        "graphify",
        "mytool",
    ]


async def test_preflight_reports_claude_option_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.2.163")
    write_work_provider(tmp_path, "local")
    gaps = build_manager(
        tmp_path,
        script_environment(FakeSubprocessRunner()),
        sdk_option_probe=lambda: ["output_format"],
    )
    complete = build_manager(
        tmp_path, script_environment(FakeSubprocessRunner()), sdk_option_probe=list
    )

    claude_gaps = (await gaps.preflight([])).providers["claude"]
    claude_ok = (await complete.preflight([])).providers["claude"]

    assert claude_gaps.state is ReadinessState.MISCONFIGURED
    assert "output_format" in claude_gaps.detail
    assert "ADR-0014" in claude_gaps.detail
    assert claude_ok.state is ReadinessState.READY
    assert claude_ok.version == "0.2.163"


@pytest.mark.parametrize(
    ("content", "env", "state"),
    [
        ("kind: local\n", {}, ReadinessState.READY),
        ("kind: jira\n", JIRA, ReadinessState.READY),
        ("kind: jira\n", {"JIRA_EMAIL": "a@b"}, ReadinessState.MISCONFIGURED),
        ("kind: carrier-pigeon\n", {}, ReadinessState.MISCONFIGURED),
        ("kind: [unclosed\n", {}, ReadinessState.MISCONFIGURED),
        (None, {}, ReadinessState.UNKNOWN),
    ],
)
async def test_preflight_work_provider_states(
    tmp_path: Path, content: str | None, env: dict[str, str], state: ReadinessState
) -> None:
    if content is not None:
        path = tmp_path / ".ai" / "project" / "work-provider.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")
    manager = build_manager(tmp_path, script_environment(FakeSubprocessRunner()), env=env)

    manifest = await manager.preflight([])

    assert manifest.work_provider.state is state
    if state is ReadinessState.MISCONFIGURED and content == "kind: jira\n":
        assert "JIRA_API_TOKEN" in manifest.work_provider.detail


async def test_preflight_rejects_unknown_required_key(tmp_path: Path) -> None:
    manager = build_manager(tmp_path, script_environment(FakeSubprocessRunner()))

    with pytest.raises(ConfigError, match="unknown preflight component"):
        await manager.preflight(["warp-drive"])


async def test_preflight_resolves_dotted_required_keys(tmp_path: Path) -> None:
    write_work_provider(tmp_path, "local")
    manager = build_manager(tmp_path, script_environment(FakeSubprocessRunner(), codex=None))

    with pytest.raises(ConfigError) as raised:
        await manager.preflight(["unity", "providers.codex", "credentials.JIRA_EMAIL"])

    assert raised.value.detail["missing_components"] == [
        "providers.codex",
        "credentials.JIRA_EMAIL",
    ]


async def test_deferred_methods_name_their_story(tmp_path: Path) -> None:
    manager = build_manager(tmp_path, FakeSubprocessRunner())
    event = WorkProviderEvent(
        provider="local",
        external_ref="X-1",
        kind="UPDATED",
        external_status=None,
        fields={},
        at=AT,
        delivery_id="d-1",
    )

    async def fn() -> str:
        return "ref"

    with pytest.raises(ConfigError, match="E03-S03"):
        await manager.ingest(event)
    with pytest.raises(ConfigError, match="E03-S03"):
        await manager.reconcile(None)
    with pytest.raises(ConfigError, match="E03-S03"):
        await manager.with_idempotency("k", "op", fn)


async def test_detect_edge_outputs() -> None:
    runner = FakeSubprocessRunner()
    runner.script(["git", "--version"], exit_code=3)
    runner.script(["dotnet", "--version"], stdout="unversioned build\n")
    runner.script(["codex", "--version"], stdout="codex-cli 0.160.1\n")
    runner.script(["codex", "exec", "--help"], error=Timeout("subprocess timed out"))

    git = await detect_git(runner)
    dotnet = await detect_dotnet(runner)
    codex = await detect_codex_cli(runner)

    assert git.state is ReadinessState.MISCONFIGURED
    assert git.detail == "exit code 3"
    assert dotnet.state is ReadinessState.READY
    assert dotnet.version is None
    assert dotnet.detail == "unversioned build"
    assert codex.state is ReadinessState.MISCONFIGURED
    assert codex.detail.startswith("codex exec --help: ")
    assert "timed out" in codex.detail


async def test_preflight_sdk_probe_failure_is_misconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.2.163")

    def broken() -> list[str]:
        msg = "claude-agent-sdk is not installed (install the 'claude' extra)"
        raise ConfigError(msg)

    manager = build_manager(
        tmp_path, script_environment(FakeSubprocessRunner()), sdk_option_probe=broken
    )

    claude = (await manager.preflight([])).providers["claude"]

    assert claude.state is ReadinessState.MISCONFIGURED
    assert "not installed" in claude.detail
