"""`codex exec` command lines (ADR-0004 D-8, ADR-0014 verified flags for codex-cli 0.160.1).

``-c`` values are parsed by the CLI as TOML (falling back to the raw string), so string values
that must stay strings are quoted. The prompt is read from stdin (the trailing ``-``).
"""

import json
from typing import Final

from walk.model_router.adapters.codex.sandbox import CodexSandboxConfig
from walk.model_router.models import ProviderEffortConfig

CODEX_BINARY: Final = "codex"

_STDIN_PROMPT: Final = "-"


def build_exec_command(
    cfg: ProviderEffortConfig,
    sandbox: CodexSandboxConfig,
    *,
    prompt_file: str,
    output_schema_path: str | None,
) -> list[str]:
    """Argv of a fresh ``codex exec --json`` run.

    ``prompt_file`` is not on the command line: the CLI reads the prompt from stdin (``-``)
    and the launcher feeds that file to stdin (`CodexProcessLauncher.launch`'s ``stdin_path``).
    """
    del prompt_file  # delivered on stdin by the launcher; see the docstring
    argv = [CODEX_BINARY, "exec", "--json", "--sandbox", sandbox.mode, "--cd", sandbox.cwd]
    argv += _model_flags(cfg)
    argv += _sandbox_flags(sandbox)
    if output_schema_path is not None:
        argv += ["--output-schema", output_schema_path]
    return [*argv, _STDIN_PROMPT]


def build_resume_command(
    thread_id: str, cfg: ProviderEffortConfig, sandbox: CodexSandboxConfig
) -> list[str]:
    """Argv of ``codex exec resume <thread_id> --json``.

    ADR-0014: ``resume`` accepts neither ``--sandbox`` nor ``--cd``; the sandbox mode goes
    through ``-c sandbox_mode=...`` and the working directory through the process cwd.
    """
    argv = [CODEX_BINARY, "exec", "resume", thread_id, "--json"]
    argv += ["-c", f"sandbox_mode={json.dumps(sandbox.mode)}"]
    argv += _model_flags(cfg)
    argv += _sandbox_flags(sandbox)
    return [*argv, _STDIN_PROMPT]


def _model_flags(cfg: ProviderEffortConfig) -> list[str]:
    model = cfg.model_id.split("/", 1)[1]
    flags = ["-c", f"model={model}"]
    effort = cfg.params.get("model_reasoning_effort")
    if effort is not None:
        flags += ["-c", f"model_reasoning_effort={effort}"]
    return flags


def _sandbox_flags(sandbox: CodexSandboxConfig) -> list[str]:
    network = "true" if sandbox.network_enabled else "false"
    flags = ["-c", f"sandbox_workspace_write.network_access={network}"]
    if sandbox.writable_roots:
        # A JSON array of strings is a valid TOML array of basic strings.
        roots = json.dumps(sandbox.writable_roots)
        flags += ["-c", f"sandbox_workspace_write.writable_roots={roots}"]
    return flags
