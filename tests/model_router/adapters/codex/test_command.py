import itertools

from walk.model_router import ProviderEffortConfig
from walk.model_router.adapters.codex.command import (
    CODEX_BINARY,
    build_exec_command,
    build_resume_command,
)
from walk.model_router.adapters.codex.sandbox import DEFAULT_SANDBOX_MODE, CodexSandboxConfig

HIGH = ProviderEffortConfig(model_id="codex/gpt-5-codex", params={"model_reasoning_effort": "high"})


def _pairs(argv: list[str]) -> list[tuple[str, str]]:
    return list(itertools.pairwise(argv))


def test_build_exec_command_flags() -> None:
    sandbox = CodexSandboxConfig(cwd="/wt")
    argv = build_exec_command(
        HIGH, sandbox, prompt_file="/wt/.walk/prompt.md", output_schema_path="/wt/.walk/s.json"
    )

    assert argv[:4] == [CODEX_BINARY, "exec", "--json", "--sandbox"]
    assert sandbox.mode == DEFAULT_SANDBOX_MODE == "workspace-write"
    pairs = _pairs(argv)
    assert ("--sandbox", "workspace-write") in pairs
    assert ("--cd", "/wt") in pairs
    assert ("-c", "model=gpt-5-codex") in pairs
    assert ("-c", "model_reasoning_effort=high") in pairs
    assert ("-c", "sandbox_workspace_write.network_access=false") in pairs
    assert ("--output-schema", "/wt/.walk/s.json") in pairs
    assert not any(a.startswith("sandbox_workspace_write.writable_roots") for a in argv)
    assert argv[-1] == "-"


def test_build_exec_command_optional_flags() -> None:
    sandbox = CodexSandboxConfig(
        cwd="/wt", network_enabled=True, writable_roots=["/cache", 'C:\\a "b"']
    )
    argv = build_exec_command(HIGH, sandbox, prompt_file="/wt/p.md", output_schema_path=None)

    pairs = _pairs(argv)
    assert ("-c", "sandbox_workspace_write.network_access=true") in pairs
    assert ("-c", 'sandbox_workspace_write.writable_roots=["/cache", "C:\\\\a \\"b\\""]') in pairs
    assert "--output-schema" not in argv
    assert argv[-1] == "-"


def test_build_resume_command() -> None:
    sandbox = CodexSandboxConfig(cwd="/wt")
    argv = build_resume_command("thr_1", HIGH, sandbox)

    assert argv[:5] == [CODEX_BINARY, "exec", "resume", "thr_1", "--json"]
    assert "--sandbox" not in argv
    assert "--cd" not in argv
    pairs = _pairs(argv)
    assert ("-c", 'sandbox_mode="workspace-write"') in pairs
    assert ("-c", "sandbox_workspace_write.network_access=false") in pairs
    assert ("-c", "model=gpt-5-codex") in pairs
    assert ("-c", "model_reasoning_effort=high") in pairs
    assert argv[-1] == "-"


def test_commands_without_reasoning_param_omit_it() -> None:
    plain = ProviderEffortConfig(model_id="codex/gpt-5-codex", params={})
    argv = build_exec_command(
        plain, CodexSandboxConfig(cwd="/wt"), prompt_file="p", output_schema_path=None
    )
    assert not any(a.startswith("model_reasoning_effort") for a in argv)
