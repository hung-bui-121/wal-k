# EPIC-02 — Production Kit

**Roadmap stage:** §135 Stage 2
**Goal.** A game repository can be bootstrapped into a validated, reproducible Production Kit: environment manifest, `.ai/` tree, canonical skills with projections and drift detection, MUST hooks, permission rule set with protected actions and approvals, approved-artifact registry, security hardening.
**Requirements.** §24–§29, §31–§33, §91–§93 (pause/resume/priority/policy subset), §105 (pins), §123–§124, §137 (Inv. 7, 10, 11), §138 (Model Lock-In), §139 (credentials).
**Epic gate.** `tests/e2e/test_e02_gate.py`: on a fresh temp repo with a `GDD/` folder, `walk bootstrap --provider local --key DEMO --name Demo --yes` creates the full `.ai/` tree and DB; `walk doctor` exits 0 and writes `environment.yaml`; skills are projected for both providers and `walk skills check-drift` is clean, then a hand-edited projection is reported `modified`; a fake run requesting `git.merge_protected` pauses with an `ApprovalRequest`, `walk approve APV-0001` resumes it; `walk pause`/`walk resume` write `USER_OVERRIDE`; an agent diff touching `.ai/agents/roles/` is rejected by `BoundaryAuditor`.
**Precondition.** E01-R01 is `DONE` with no `BLOCKER` bugfix stories. All E01 symbols referenced below exist (`Default*` services per `WBS.md` §3.1).

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E02-S01 | `CredentialStore` and agent environment allowlist | E01-S23, E01-S25 | MEDIUM |
| E02-S02 | Environment preflight and `EnvironmentManifest`, `walk doctor` (basic) | E02-S01, E01-S14 | HIGH |
| E02-S03 | `walk bootstrap`: Production Kit generation and `.ai/` initialisation | E02-S02, E01-S16, E01-S17 | HIGH |
| E02-S04 | `kernel-versions.yaml` and behavior-version pins | E02-S03 | MEDIUM |
| E02-S05 | `SkillRegistry` loading and builtin skills | E01-S14 | MEDIUM |
| E02-S06 | Skill projections for Claude and Codex, lock file, `walk skills list/sync` | E02-S05, E01-S21, E01-S22, E01-S25 | HIGH |
| E02-S07 | Skill drift detection, `walk skills check-drift`, startup check | E02-S06, E02-S02 | MEDIUM |
| E02-S08 | Builtin MUST hooks (ARCHITECTURE §4.1 table) | E01-S07, E01-S28, E01-S16 | HIGH |
| E02-S09 | Project hooks from `.ai/agents/hooks.yaml` | E02-S08 | MEDIUM |
| E02-S10 | Permission defaults, `permissions.yaml` loader, protected actions | E01-S15, E02-S03 | MEDIUM |
| E02-S11 | Approval requests and `walk approve/deny/approvals` | E02-S10, E01-S26 | HIGH |
| E02-S12 | Approved artifact registry and `walk artifacts` | E02-S10, E01-S16 | HIGH |
| E02-S13 | Human override CLI subset | E01-S30, E02-S11 | MEDIUM |
| E02-S14 | Security hardening: forbidden paths, git guard hooks, secret scan, command restrictions | E02-S10, E01-S23, E01-S25 | HIGH |
| E02-S15 | `walk doctor --fix --strict` | E02-S07, E02-S14, E02-S04 | MEDIUM |
| E02-S16 | Epic gate: bootstrap → doctor → skills → approval → override (e2e) | E02-S15, E02-S13, E02-S12, E02-S09 | MEDIUM |
| E02-R01 | Review E02 | E02-S16 | MEDIUM |

## Reading order for implementers

1. `WBS.md` §2–§3 (rules, binding conventions), then this header.
2. The story itself; its `§NN` sections; `ARCHITECTURE.md` §3.4 (startup), §4.1 (hooks), §4.2 (enforcement), §6 (security), §8 (`.ai/` layout); `INTERFACES.md` §1.8, §1.10–§1.12, §6; ADR-0003, ADR-0006, ADR-0007, ADR-0009 (D-7, D-8, D-10, D-11), ADR-0013.
3. Existing E01 files named in the story's Files table and their tests.

Parallel sets (WBS.md §8): `{S05→S06→S07} ∥ {S08→S09} ∥ {S10→S11→S12}` after S03; `{S01} ∥ {S05}`; `{S13} ∥ {S14}`.

---

### E02-S01 — `CredentialStore` and agent environment allowlist

**Status:** DONE (d3c559e)
**Type:** feat
**Requirements:** §91, §26, §139
**Depends on:** E01-S23, E01-S25
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Secrets are resolved only through `CredentialStore` (environment → OS keyring → absent) and agent subprocesses receive a scrubbed environment built from a fixed allowlist, so no provider or Jira credential can reach an agent.

#### Scope
- In: `CredentialStore`, credential name catalogue (ADR-0009 D-8), injectable keyring backend, `AGENT_ENV_ALLOWLIST`, `scrubbed_env`, wiring into `RunSession.env_allowlist` for both real adapters.
- Out: credential presence reporting in the manifest (E02-S02); secret-pattern scanning of written content (E02-S14); Jira credential use (E03-S04).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/credentials.py` | create | `CredentialStore`, `KeyringBackend` (Protocol), `SystemKeyringBackend`, `CREDENTIAL_NAMES` |
| `src/walk/integrations/__init__.py` | modify | re-export `CredentialStore`, `CREDENTIAL_NAMES` |
| `src/walk/runtime/sandbox.py` | modify | `AGENT_ENV_ALLOWLIST`, `scrubbed_env` |
| `src/walk/runtime/executor.py` | modify | — (passes `scrubbed_env(os.environ)` into `RunSession.env_allowlist`) |
| `src/walk/cli/composition.py` | modify | — (constructs `CredentialStore`, adds `KernelOverrides.keyring_backend`) |
| `src/walk/model_router/adapters/claude/transport.py` | create | `scrubbed_transport` (binding Note: the CLI process gets exactly the scrubbed mapping) |
| `src/walk/model_router/adapters/claude/client.py` | modify | — (`SdkClaudeClient(transport_factory=...)`; every query runs on `scrubbed_transport`) |
| `tests/fakes/fake_keyring.py` | create | `FakeKeyringBackend` |
| `tests/integrations/test_credentials.py` | create | — |
| `tests/runtime/test_sandbox_env.py` | create | — |
| `tests/model_router/adapters/claude/test_transport.py` | create | — |
| `tests/model_router/adapters/claude/test_adapter.py` | modify | — (SDK stub accepts the `transport` argument) |

#### Interface contract
```python
# src/walk/integrations/credentials.py
CREDENTIAL_NAMES: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "WALK_WEBHOOK_SECRET",
    "MESHY_API_KEY",
    "OPENART_OAUTH_CLIENT",
    "OPENART_OAUTH_REFRESH_TOKEN",
)
KEYRING_SERVICE: str = "walk"


class KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...


class SystemKeyringBackend:
    """Adapter over the `keyring` package (the only module importing `keyring`)."""

    def get_password(self, service: str, username: str) -> str | None: ...


class CredentialStore:
    def __init__(self, env: Mapping[str, str], backend: KeyringBackend | None) -> None: ...
    def get(self, name: str) -> SecretStr | None:
        """env[name] if set and non-empty, else backend.get_password(KEYRING_SERVICE, name), else None."""

    def present(self, name: str) -> bool: ...
    def presence(self) -> dict[str, ReadinessState]:
        """READY / MISSING for every CREDENTIAL_NAMES entry; never values."""


# src/walk/runtime/sandbox.py
AGENT_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH",
    "HOME",
    "TMP",
    "TEMP",
    "USERPROFILE",
    "SYSTEMROOT",
    "UNITY_*",
)


def scrubbed_env(os_env: Mapping[str, str]) -> dict[str, str]:
    """Keys equal to an allowlist entry or matching a trailing-`*` glob; values copied verbatim."""
```

#### Behavior
1. `get()` returns the env value when the variable exists and is non-empty; an empty string counts as absent and falls through to the keyring.
2. `get()` with no backend configured never raises; it returns `None` when env lookup misses.
3. A backend exception (keyring unavailable) is caught, logged at WARNING with `extra={"credential": name}`, and treated as absent.
4. `get()` for a name not in `CREDENTIAL_NAMES` raises `ConfigError("unknown credential name")`.
5. `presence()` returns exactly `len(CREDENTIAL_NAMES)` entries; `SecretStr` values never appear in `repr`, logs or the returned dict.
6. `scrubbed_env` keeps only allowlisted keys; glob entries match prefix (`UNITY_EDITOR_PATH` kept, `UNITYX` dropped); comparison is case-sensitive on POSIX and case-insensitive on Windows (`sys.platform == "win32"`).
7. `DefaultAgentExecutor` builds `RunSession.env_allowlist = scrubbed_env(os.environ)`; `CodexAdapter` spawns with exactly that mapping; `ClaudeAdapter` passes it as the SDK `env` option.
8. No module other than `credentials.py` imports `keyring` (ruff banned-api rule from ARCHITECTURE §2.3).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given env `JIRA_API_TOKEN=abc` When `get("JIRA_API_TOKEN")` Then `SecretStr("abc")` and backend not called | `tests/integrations/test_credentials.py::test_get_prefers_environment_over_keyring` |
| 2 | Given env unset and fake keyring holding the name When `get` Then keyring value returned | `tests/integrations/test_credentials.py::test_get_falls_back_to_keyring` |
| 3 | Given env empty string and keyring empty When `get` Then `None` | `tests/integrations/test_credentials.py::test_get_returns_none_when_absent` |
| 4 | Given backend raising `RuntimeError` When `get` Then `None` and a WARNING log record | `tests/integrations/test_credentials.py::test_get_treats_backend_error_as_absent` |
| 5 | Given name `FOO` When `get` Then `ConfigError` | `tests/integrations/test_credentials.py::test_get_unknown_name_raises_config_error` |
| 6 | Given two credentials present When `presence()` Then READY for those, MISSING for the rest, no values | `tests/integrations/test_credentials.py::test_presence_reports_states_without_values` |
| 7 | Given env with `ANTHROPIC_API_KEY`, `JIRA_API_TOKEN`, `PATH`, `UNITY_EDITOR_PATH` When `scrubbed_env` Then only `PATH` and `UNITY_EDITOR_PATH` remain | `tests/runtime/test_sandbox_env.py::test_scrubbed_env_drops_secrets_and_keeps_allowlist` |
| 8 | Given a Codex run via `FakeSubprocessRunner` When started Then the captured env has no key outside the allowlist | `tests/runtime/test_sandbox_env.py::test_codex_subprocess_env_is_scrubbed` |

#### Evidence required
- Quality gate output.
- Demo: `uv run python -c "from walk.integrations import CredentialStore; print(CredentialStore({'JIRA_EMAIL':'a@b'}, None).presence()['JIRA_EMAIL'])"` → `ReadinessState.READY`.

#### Notes
- Binding (E01-R01 planner note, confirmed by ADR-0014 sources): the Claude Agent SDK's `env` option is *merged onto* the inherited process environment, so passing `scrubbed_env(...)` as `env` scrubs nothing. For Claude, pass the SDK a custom `transport` (the `query(..., transport=...)` parameter, ADR-0014 SDK table) that launches the CLI subprocess with exactly `scrubbed_env(os.environ)` and does not inherit `os.environ`; keep the transport inside `src/walk/model_router/adapters/claude/` (add it to the Files table there as `create`). Add a test mirroring the Codex one: a sentinel secret variable in the kernel's environment is absent from the environment the Claude transport passes to its subprocess.
- ADR-0009 D-8; ARCHITECTURE §6 "Secret isolation".
- `NEW NAME:` `KeyringBackend`, `SystemKeyringBackend`, `CREDENTIAL_NAMES`, `KEYRING_SERVICE`, `AGENT_ENV_ALLOWLIST`, `scrubbed_env`, `KernelOverrides.keyring_backend`; from the binding Note: `walk.model_router.adapters.claude.transport` (`scrubbed_transport`, `TRANSPORT_MODULE`), `SdkClaudeClient(transport_factory=...)` with `TransportFactory`, `KernelHandle.credentials`.
- Commit subject: `feat: add credential store and scrubbed agent environment (E02-S01)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`):
```
340 files already formatted
All checks passed!
Success: no issues found in 338 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.89%
1037 passed, 3 deselected in 392.96s
```
Touched modules: `integrations/credentials.py` 100 %, `integrations/__init__.py` 100 %, `runtime/sandbox.py` 100 %, `runtime/executor.py` 99 % (lines 691, 710, 1127-1128 were already uncovered before this story), `model_router/adapters/claude/transport.py` 100 %, `model_router/adapters/claude/client.py` 100 %, `cli/composition.py` 100 %.

Demo:
```
$ uv run python -c "from walk.integrations import CredentialStore; print(CredentialStore({'JIRA_EMAIL':'a@b'}, None).presence()['JIRA_EMAIL'])"
ready
$ uv run python -c "...; print(repr(CredentialStore({'JIRA_EMAIL':'a@b'}, None).presence()['JIRA_EMAIL']))"
<ReadinessState.READY: 'ready'>
```
(`ReadinessState` is a `StrEnum`, so `print` shows the value `ready`; the member is `ReadinessState.READY`.)

Claude transport, checked against the real `claude-agent-sdk 0.2.163` in a throw-away environment (`uv run --with claude-agent-sdk`, scratch script, not committed; no login, no model call). `ANTHROPIC_API_KEY=sentinel-secret` was set in the kernel process. The transport's `_build_command` was replaced by a Python one-liner that prints the names of its environment variables:
```
command flags ok: True True          (--permission-prompt-tool stdio is in the real CLI command)
child env keys: ['HOME', 'PATH', 'SYSTEMROOT', 'TEMP', 'TMP', 'USERPROFILE']
secret leaked: False
```

Level-0 decisions:
- **Claude transport** (binding Note). `scrubbed_transport(options, env, *, module=None)` in `model_router/adapters/claude/transport.py` subclasses the SDK's `SubprocessCLITransport` lazily, because the SDK is an optional extra. It overrides only `connect`, which spawns the CLI with exactly `env`. The command line, framing and `close` stay the SDK's.
  - The SDK protocol markers that the default transport adds (`CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_AGENT_SDK_VERSION`, `CLAUDE_CODE_SDK_READS_SESSION_STATE`, `PWD`) are not added. The CLI gets exactly the scrubbed mapping, as the Note requires. The SDK's `Query` handles a CLI without session-state events.
  - The SDK's optional `claude -v` version probe is skipped. It would run with the inherited environment, and it only logs a warning.
  - As the SDK does for its own transport, a set `can_use_tool` makes the transport's options carry `permission_prompt_tool_name="stdio"`. `ClaudeSDKClient` does not apply the options to a custom transport.
  - `SdkClaudeClient` gets the keyword `transport_factory` (default `scrubbed_transport`), so tests inject a recorder. `ClaudeQueryOptions.env` now documents that nothing is inherited.
  - Risk: the subclass relies on SDK private members (`_find_cli`, `_reject_windows_batch_cli`, `_build_command`, `_process`, `_cli_path`, `_cwd`, `_stdout_stream`, `_stdin_stream`, `_ready`) and on the module globals `anyio`, `PIPE`, `TextReceiveStream`, `TextSendStream`. `claude-agent-sdk` is not pinned. `tests/model_router/adapters/claude/test_transport.py::test_real_sdk_transport_has_the_overridden_members` (`@pytest.mark.integration`) guards this on SDK upgrades.
- **AC 8** runs the real `DefaultAgentExecutor` (runtime `make_executor_env` harness) with a real `CodexAdapter` over `FakeCodexProcessLauncher` instead of `FakeSubprocessRunner`. The Codex adapter launches through `CodexProcessLauncher` (E01-S22), so that launcher is the spawn point to capture. `ANTHROPIC_API_KEY`/`JIRA_API_TOKEN` set in `os.environ` are absent from the launch env, and `UNITY_EDITOR_PATH` is kept.
- `DefaultAgentExecutor(env_allowlist=None)` now defaults to `scrubbed_env(os.environ)`, evaluated when each run starts. The composition root no longer passes `dict`. `tests/runtime/test_inputs.py::test_build_run_session_fields` had pinned the old empty environment and now asserts `scrubbed_env(os.environ)`.
- `CredentialStore` keeps a reference to the env mapping (it reads `os.environ` live), and an empty keyring value counts as absent. A keyring failure is logged with `credential` and `error_type` only, never the message. `present()` also raises `ConfigError` for unknown names.
- `KernelHandle.credentials` holds the store, for `walk doctor` (E02-S02) and the Jira provider (E03-S04).

For the owner / architect:
- With the scrubbed environment, `ANTHROPIC_API_KEY` resolved by `CredentialStore` never reaches the Claude CLI. Claude runs authenticate only through the CLI's own login (`claude login`), as Codex does. ARCHITECTURE §6 "Secret isolation" still says "Claude SDK runs inside the kernel process". The SDK actually spawns the Claude Code CLI as a subprocess, which this story now scrubs.
- On Windows the CLI child may need variables that are not in `AGENT_ENV_ALLOWLIST` (for example `APPDATA`, `LOCALAPPDATA`, `PATHEXT`, `COMSPEC`). The allowlist is fixed by this story. The `@pytest.mark.integration` round-trip tests of E01-S21/S22 settle this on the owner's machine.

---

### E02-S02 — Environment preflight and `EnvironmentManifest`, `walk doctor` (basic)

**Status:** DONE (bc1fcfe)
**Type:** feat
**Requirements:** §26, §27, §25, §139
**Depends on:** E02-S01, E01-S14
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`IntegrationManager.preflight` detects every §26 component, writes `.ai/project/environment.yaml`, reports drift against the previous manifest, and `walk doctor` prints the result with exit code 4 when a required component is missing.

#### Scope
- In: `DefaultIntegrationManager` class with `preflight` only; detectors; manifest write/read/drift; `walk doctor` without flags.
- Out: `ingest/reconcile/with_idempotency` (E03-S03); `--fix/--strict` (E02-S15); skill drift section (E02-S07); approved-artifact verification (E02-S12).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/preflight.py` | create | `detect_git`, `detect_unity`, `detect_codex_cli`, `detect_claude_sdk`, `detect_graphify`, `detect_dotnet`, `detect_credentials`, `detect_required_skills`, `REQUIRED_DEFAULT` |
| `src/walk/integrations/manifest.py` | create | `ManifestStore` |
| `src/walk/integrations/service.py` | create | `DefaultIntegrationManager` (only `preflight` implemented; other protocol methods raise `NotImplementedError` with the story id, replaced in E03-S03) |
| `src/walk/integrations/__init__.py` | modify | re-export `DefaultIntegrationManager`, `ManifestStore` |
| `src/walk/cli/cmd_doctor.py` | create | `doctor` |
| `src/walk/cli/app.py` | modify | register `doctor` |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultIntegrationManager`) |
| `tests/integrations/test_preflight.py` | create | — |
| `tests/integrations/test_manifest.py` | create | — |
| `tests/cli/test_cmd_doctor.py` | create | — |
| `src/walk/model_router/adapters/claude/client.py` | modify | `SDK_OPTIONS`, `missing_sdk_options` (Behavior 9 introspection; only this package may import the SDK) |
| `tests/model_router/adapters/claude/test_adapter.py` | modify | — |
| `tests/cli/test_composition.py` | modify | — |
| `pyproject.toml` | modify | — (import-linter allowance `walk.integrations -> walk.integrations.service`) |
| `docs/01-architecture/INTERFACES.md`, `docs/01-architecture/ARCHITECTURE.md` | modify | — (§1.12 `required` names; §2.3 `yaml` row) |

#### Interface contract
See INTERFACES.md §1.12 `IntegrationManager.preflight`. Deltas:
```python
# src/walk/integrations/preflight.py
REQUIRED_DEFAULT: tuple[str, ...] = (
    "git",
    "work_provider",
)  # keys that make doctor exit 4 when MISSING


async def detect_git(runner: SubprocessRunner) -> ComponentStatus: ...  # `git --version`
async def detect_unity(
    runner: SubprocessRunner, unity_path: str | None, project_path: str
) -> ComponentStatus: ...  # `<unity> -version`; reads ProjectSettings/ProjectVersion.txt
async def detect_codex_cli(runner: SubprocessRunner) -> ComponentStatus: ...  # `codex --version`
def detect_claude_sdk() -> ComponentStatus: ...  # importlib.metadata.version("claude-agent-sdk")
async def detect_graphify(runner: SubprocessRunner) -> ComponentStatus: ...  # `graphify --version`
async def detect_dotnet(runner: SubprocessRunner) -> ComponentStatus: ...  # `dotnet --version`
def detect_credentials(store: CredentialStore) -> dict[str, ReadinessState]: ...
def detect_required_skills(
    required: list[SkillName], available: list[SkillName]
) -> dict[SkillName, ReadinessState]: ...


# src/walk/integrations/manifest.py
class ManifestStore:
    def __init__(self, ai_root: Path, clock: Clock) -> None: ...
    def path(self) -> Path: ...  # <ai_root>/project/environment.yaml
    def read(self) -> EnvironmentManifest | None: ...
    def write(self, manifest: EnvironmentManifest) -> Path: ...  # atomic tmp + rename
    def diff(self, previous: EnvironmentManifest, current: EnvironmentManifest) -> list[str]:
        """'<section>.<key>: <old state/version> -> <new state/version>' for every changed component."""


# src/walk/integrations/service.py
class DefaultIntegrationManager:
    def __init__(
        self,
        *,
        runner: SubprocessRunner,
        credentials: CredentialStore,
        manifest_store: ManifestStore,
        tools: ToolRegistry,
        clock: Clock,
        machine_id: str,
        unity_path: str | None,
        project_path: str,
        required_skills: list[SkillName],
        available_skills: list[SkillName],
    ) -> None: ...
    async def preflight(self, required: list[str]) -> EnvironmentManifest: ...
```

#### Behavior
1. Each detector returns `READY` with `version` when the probe succeeds, `MISSING` when the executable is absent (`FileNotFoundError` from the runner), `MISCONFIGURED` when it exists but exits non-zero (detail = first stderr line), `UNKNOWN` on timeout (5 s).
2. `preflight(required)` runs all detectors concurrently (`asyncio.gather`), builds `EnvironmentManifest(generated_at=clock.now(), machine_id=…)`, sets `work_provider` from `.ai/project/work-provider.yaml` kind (`local` → READY; `jira` → READY only if the three Jira credentials are present, else MISCONFIGURED).
3. If a previous manifest exists, `drift_from = previous.machine_id` and `drift_items = ManifestStore.diff(previous, current)`; otherwise both unset.
4. The manifest is written before the function returns; `credentials` holds states only (rule S01-5).
5. `preflight` raises `ConfigError` listing the missing keys when any key in `required` is MISSING; the manifest is still written first.
6. `walk doctor` calls `preflight(REQUIRED_DEFAULT)`, prints a table (`component | state | version | detail`) grouped by section, and exits 0 when all required are READY, 4 when `ConfigError` from rule 5, 1 on any other `WalkError`. `--json` prints `EnvironmentManifest.model_dump_json()`.
7. `walk doctor` runs in-process (no daemon needed) and acquires `KernelLock` in shared mode only if the lock module supports it; otherwise it opens the DB read-only.
8. `tools` status for CLI tools comes from `ToolRegistry.all()` entries with `kind == CLI`: each `executable` is probed with `<exe> --version` through the runner.
9. Provider capability probe (ADR-0014, owner decision 2026-10-06: per-project runtime verification): when `codex` is READY, `codex exec --help` and `codex exec resume --help` are run and every flag in ADR-0014's Codex table must be present (missing flag → `MISCONFIGURED`, detail names the flag and ADR-0014); when the `claude` extra is installed, `ClaudeAgentOptions` is introspected for the ADR-0014 SDK options. No login and no model call; results are stored in the manifest so drift between machines is reported (§27).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given runner returning `git version 2.45.0` When `detect_git` Then READY with version `2.45.0` | `tests/integrations/test_preflight.py::test_detect_git_ready_with_version` |
| 2 | Given runner raising `FileNotFoundError` When `detect_codex_cli` Then MISSING | `tests/integrations/test_preflight.py::test_detect_missing_executable_reports_missing` |
| 3 | Given runner exit 1 with stderr When `detect_unity` Then MISCONFIGURED with detail | `tests/integrations/test_preflight.py::test_detect_nonzero_exit_reports_misconfigured` |
| 4 | Given runner timing out When `detect_dotnet` Then UNKNOWN | `tests/integrations/test_preflight.py::test_detect_timeout_reports_unknown` |
| 5 | Given no previous manifest When `preflight([])` Then file written, `drift_from is None` | `tests/integrations/test_manifest.py::test_preflight_writes_manifest_without_drift` |
| 6 | Given previous manifest with git 2.44 on machine A When `preflight` on machine B finds 2.45 Then `drift_from == "A"` and one drift item | `tests/integrations/test_manifest.py::test_preflight_reports_drift_against_previous` |
| 7 | Given git MISSING When `preflight(["git"])` Then `ConfigError` and manifest still written | `tests/integrations/test_preflight.py::test_preflight_required_missing_raises_after_writing` |
| 8 | Given all required READY When `walk doctor` Then exit 0 and table contains `git` | `tests/cli/test_cmd_doctor.py::test_doctor_exit_zero_when_ready` |
| 9 | Given git MISSING When `walk doctor` Then exit 4 | `tests/cli/test_cmd_doctor.py::test_doctor_exit_four_when_required_missing` |
| 10 | Given `--json` When `walk doctor` Then stdout parses as `EnvironmentManifest` | `tests/cli/test_cmd_doctor.py::test_doctor_json_output_is_manifest` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor` in a repo with git installed → table with `tools.git  ready  2.x`, exit 0; `walk doctor --json | head -c 200`.

#### Notes
- ADR-0009 D-8, D-9, D-11 (plugin versions recorded under `tools`); ARCHITECTURE §3.4 step 2.
- Jira status-map validation is E03-S05; the `work_provider` component here only checks kind + credentials.
- `NEW NAME:` `ManifestStore`, `REQUIRED_DEFAULT`, detector function names; from implementation: `detect_cli_tool`, `MISSING_COMPONENTS`, `SdkOptionProbe`, `DefaultIntegrationManager(sdk_option_probe=...)`, `SDK_OPTIONS`, `missing_sdk_options`, `open_integrations`, `KernelHandle.integrations`.
- Commit subject: `feat: add environment preflight manifest and doctor command (E02-S02)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`):
```
347 files already formatted
All checks passed!
Success: no issues found in 345 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.90%
1076 passed, 3 deselected in 395.86s
```
Touched modules: `integrations/preflight.py`, `manifest.py`, `service.py`, `__init__.py`, `cli/cmd_doctor.py`, `cli/composition.py`, `cli/app.py`, `model_router/adapters/claude/client.py` all 100 %.

Demo on a fresh temporary git repository (real probes on the owner's Windows host, no bootstrap yet):
```
$ walk doctor --repo <tmp>/game
component                                state          version   detail
---------------------------------------  -------------  --------  -----------------------------------------------------
unity                                    misconfigured            error: unknown option '-version'
tools.git                                ready          2.41.0
tools.graphify                           ready          0.9.48
tools.dotnet                             ready          10.0.100
providers.codex                          missing                  executable not found: codex ([WinError 2] ...)
providers.claude                         missing                  claude-agent-sdk is not installed (the 'claude' extra)
work_provider                            unknown                  no work-provider.yaml; run 'walk bootstrap'
credentials.ANTHROPIC_API_KEY            missing
credentials.JIRA_BASE_URL                missing
...                                      (all eight credentials, presence only)
exit=0
$ walk doctor --repo <tmp>/game --json | head -c 200
{
  "generated_at": "2026-10-06T20:04:35.432519Z",
  "machine_id": "CPU12432",
  "unity": {
    "state": "misconfigured",
    "version": null,
    "detail": "error: unknown option '-version'"
```
`<tmp>/game/.ai/project/environment.yaml` was written. The `Unity` on this host's PATH is an npm "CLI for Unity" (1.0.0-beta.8), not the Unity Editor, so `Unity -version` fails and the result is honestly MISCONFIGURED. The editor path becomes configurable with E03-S10 (`unity_path` is `None` in the composition root until then).

Level-0 decisions:
- **Detector outcomes.** MISSING covers both `FileNotFoundError` from the runner and exit code 127, because `AsyncioSubprocessRunner` reports a missing executable as 127 (E01-S23). The version is the first `\d+(\.\d+)+` token of stdout (then stderr), plus an optional Unity-style suffix such as `f1` (`git version 2.45.0.windows.1` → `2.45.0`). A successful probe without a version token is READY with the first output line as detail. The probe timeout is 5 s.
- **Unity.** `<unity_path or "Unity"> -version`. `ProjectSettings/ProjectVersion.txt` (`m_EditorVersion`) is reported in the detail (`project editor <version>`). A mismatch is not judged here.
- **Codex capability probe (Behavior 9)** runs inside `detect_codex_cli` when `--version` succeeds:
  - `codex exec --help` must show `--json`, `--sandbox`, `--cd`, `--config`, `--output-schema`;
  - `codex exec resume --help` must show `--json`, `--config`, `--output-schema`.

  These are the flags `adapters/codex/command.py` uses (ADR-0014). A missing flag, or a failing help call, gives MISCONFIGURED and keeps the version, e.g. `codex exec --help lacks --cd (ADR-0014)`.
- **Claude SDK option introspection (Behavior 9).** `walk.integrations` may not import `claude_agent_sdk` (ARCHITECTURE §2.3), so `DefaultIntegrationManager` takes an additive keyword `sdk_option_probe: SdkOptionProbe | None = None`. The composition root wires `walk.model_router.adapters.claude.client.missing_sdk_options` to it. That function compares `dataclasses.fields(ClaudeAgentOptions)` with `SDK_OPTIONS`, the fields the adapter and its E02-S01 transport set, including `permission_prompt_tool_name`. It is called only when `detect_claude_sdk` (package metadata, no import) is READY. Gaps make `providers.claude` MISCONFIGURED (`ClaudeAgentOptions lacks ... (ADR-0014)`).
- **`required` names** (INTERFACES §1.12 updated):
  - `unity`, `work_provider`;
  - a `tools`/`providers` key;
  - `<section>.<key>`.

  An unknown name raises `ConfigError` before anything is written. A MISSING one raises `ConfigError` with `detail["missing_components"]` (`MISSING_COMPONENTS`, in `preflight.py`) after the manifest is written. Only MISSING fails; MISCONFIGURED and UNKNOWN are reported but do not fail (Behavior 5).
- **`work_provider`.** An absent `work-provider.yaml` gives UNKNOWN (`no work-provider.yaml; run 'walk bootstrap'`), not MISSING. Two reasons: `walk doctor` on a repository that is not yet bootstrapped reports the gap without failing on it, and E02-S03 runs `preflight(REQUIRED_DEFAULT)` (step c) before it writes the file (step e). Invalid YAML or an unknown kind gives MISCONFIGURED. `jira` without all three Jira credentials gives MISCONFIGURED listing the absent names.
- **Registry CLI tools (Behavior 8).** Every `kind == CLI` spec is probed with `<executable> --version` under its tool name (`detect_cli_tool`). Executables that have a dedicated detector are skipped (`git`, `graphify`, `dotnet`, `Unity`/`unity`; case-insensitive), so the packaged catalogue adds no duplicate probes. Dedicated results are keyed `tools.git`, `tools.graphify`, `tools.dotnet`, `unity`.
- **Drift lines.** State and version are compared; details are not. Single components read `unity: ...` and `work_provider: ...`. A key on one side only reads `absent`. Sections follow manifest field order. `walk doctor` prints them under `drift from <machine>:`.
- **Deferred methods.** `ingest`/`reconcile`/`with_idempotency` raise `ConfigError("implemented in E03-S03")`, not `NotImplementedError`, which keeps the E01 deferred-method pattern (E01-S29 Notes, E01-R01 Behavior 6). The protocol's provider attributes (`work`, `git`, ...) are not set yet (E03-S03).
- **Behavior 7.** `KernelLock` has no shared mode, and the preflight reads no database. So `walk doctor` opens no database at all: it reads only the environment and `.ai/project/*.yaml`. It replaces `environment.yaml` atomically and never contends with a running kernel. On exit 4 the table of the manifest just written is still printed, and the error goes to stderr.
- **Composition.** `open_integrations(repo, *, runner=None, keyring_backend=None, clock=None)` wires the doctor path. `build_kernel` also builds the manager (`KernelHandle.integrations`). `machine_id = socket.gethostname()` (as the daemon registers instances). Required and available skills stay `[]` until E02-S05/S07.
- **`.ai/project/environment.yaml` writer.** `ManifestStore.write` is the INTERFACES §1.12 writer of this configuration YAML (not a memory document, so not `MemoryManager.write`). It writes a temp file in the same folder and renames it. ARCHITECTURE §2.3 now lists `integrations/manifest.py` and `integrations/service.py` as `yaml` users. `pyproject.toml` gains the import-linter allowance `walk.integrations -> walk.integrations.service` (package re-export, like the other `Default*` services).
- **Windows `.cmd` shims.** Probes pass bare executable names, so `AsyncioSubprocessRunner` (`create_subprocess_exec`, no PATHEXT lookup) would report an npm-installed `codex.cmd` as MISSING. Resolving executables in the shared runner is outside this story. It is recorded for E02-S15 (`doctor --fix`) and E03-S10.

---

### E02-S03 — `walk bootstrap`: Production Kit generation and `.ai/` initialisation

**Status:** DONE (749ac28)
**Type:** feat
**Requirements:** §24, §25, §123, §124, §34, §35, §36
**Depends on:** E02-S02, E01-S16, E01-S17
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`walk bootstrap` turns a game repository into a Production Kit in one idempotent command: preflight, kernel defaults copied into `.ai/agents/`, `.ai/project/*` initialised from the GDD, `.ai/.gitignore`, DB created and migrated, `projects` row inserted, `ProductionKit` written.

#### Scope
- In: `Bootstrapper` in `walk.orchestrator.bootstrap` (ADR-0020), the composition helper `open_bootstrapper`, `cmd_bootstrap`, `.ai/` tree creation, `project.md`/`constitution.md` skeletons, `work-provider.yaml`, the empty `permissions.yaml` narrowing file, placeholder `kernel-versions.yaml` (content E02-S04), `production-kit.yaml`.
- Out: version pin content (E02-S04); the kernel permission defaults `src/walk/permissions/defaults.yaml` (E02-S10); skill projection (E02-S06, `walk skills sync`); Jira status validation (E03-S05); `com.walk.ci` package install (E03-S10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/bootstrap.py` | create | `Bootstrapper`, `BootstrapOptions`, `BootstrapResult`, `NO_COMMIT_SHA` |
| `src/walk/orchestrator/__init__.py` | modify | re-export `Bootstrapper`, `BootstrapOptions`, `BootstrapResult` |
| `src/walk/integrations/defaults/work-provider.yaml` | create | — (template: `kind: local`, commented Jira mapping per ADR-0005 D-3) |
| `src/walk/integrations/defaults/ai.gitignore` | create | — (`kernel.db*`, `kernel.lock`) |
| `src/walk/integrations/defaults/root.gitignore.fragment` | create | — (`.walk/`, `graphify-out/`) |
| `src/walk/memory/skeletons.py` | create | `project_skeleton`, `project_constitution_skeleton` |
| `src/walk/cli/composition.py` | modify | `open_bootstrapper` |
| `src/walk/cli/cmd_bootstrap.py` | create | `bootstrap` |
| `src/walk/cli/app.py` | modify | register `bootstrap` |
| `tests/orchestrator/test_bootstrap.py` | create | — |
| `tests/memory/test_skeletons.py` | create | — |
| `tests/cli/test_cmd_bootstrap.py` | create | — |

#### Interface contract
```python
# src/walk/orchestrator/bootstrap.py  (ADR-0020)
NO_COMMIT_SHA: Sha = Sha("0000000")  # stamped as head on documents of a repository without commits


class BootstrapOptions(WalkModel):
    repo_path: str
    project_key: ProjectKey
    name: str
    gdd_paths: list[str] = Field(
        default_factory=list, description="Relative to repo root; default: every *.md under GDD/"
    )
    provider: Literal["local", "jira"] = "local"
    unity_path: str | None = None
    yes: bool = False


class BootstrapResult(WalkModel):
    kit: ProductionKit
    manifest: EnvironmentManifest
    created_paths: list[str]
    unchanged_paths: list[str]


class Bootstrapper:
    def __init__(
        self,
        *,
        integrations: IntegrationManager,
        memory: MemoryManager,
        git: GitProvider,
        database: Database,
        migrations: MigrationRunner,
        projects: ProjectRepository,
        clock: Clock,
        kit_version: str,
    ) -> None: ...
    async def run(self, options: BootstrapOptions) -> BootstrapResult: ...


# src/walk/cli/composition.py
def open_bootstrapper(
    repo: Path,
    options: BootstrapOptions,
    *,
    runner: SubprocessRunner | None = None,
    keyring_backend: KeyringBackend | None = None,
    clock: Clock | None = None,
) -> Bootstrapper:
    """Wires the Default* services for one bootstrap (the only place that constructs `Bootstrapper`).
    Called by `cmd_bootstrap` after Behavior 3, 4 and 7 passed; opening the database creates `.ai/`."""


# src/walk/memory/skeletons.py
def project_skeleton(
    project_key: ProjectKey,
    name: str,
    gdd_paths: list[str],
    gdd_headings: list[str],
    actor: Actor,
    now: datetime,
) -> MemoryDocument:
    """type=project, id='project', all §36 H2 sections present; 'Goals' holds one bullet per top-level GDD heading; related.gdd = gdd_paths."""


def project_constitution_skeleton(
    project_key: ProjectKey, name: str, actor: Actor, now: datetime
) -> MemoryDocument:
    """type=project_constitution, id='constitution', sections: Product Authority, Constraints, Quality Bar, Forbidden."""
```
`Bootstrapper` imports only `models`/`protocols`/`errors` of other packages plus `walk.memory.skeletons` and `walk.persistence` (ARCHITECTURE §1.3, ADR-0020 D-1); the ARCHITECTURE §2.2 orchestrator row already allows every edge it needs.
CLI: `walk bootstrap [--gdd PATH]... --provider local|jira --name NAME --key KEY [--unity-path PATH] --yes` (INTERFACES §6).

#### Behavior
1. Order of steps (each idempotent): (a) create `.ai/` and `.walk/`; (b) `MigrationRunner.apply_pending` on the opened `Database`; (c) `integrations.preflight(REQUIRED_DEFAULT)` — failure aborts with exit 4 before any copy (`work_provider` is UNKNOWN, not MISSING, until step (e) writes `work-provider.yaml`, so a fresh repository passes; E02-S02 Evidence); (d) copy kernel defaults: `src/walk/agents/defaults/*.md` → `.ai/agents/roles/`, `agents/defaults/policies.yaml` → `.ai/agents/policies.yaml`, `model_router/defaults/models.yaml` → `.ai/agents/models.yaml`; write `.ai/agents/permissions.yaml` as the empty narrowing file of Behavior 9, empty `hooks.yaml` (`hooks: []`), empty `skills/` dir, `projections.lock.yaml` (`projections: []`, written by `ProjectionLock`); (e) `work-provider.yaml` with `kind: <provider>`; (f) `project.md`, `constitution.md` via `MemoryManager.write` (actor `USER`, `head = git.head(repo)`, `branch = git.current_branch(repo)`; on `GitError` because the repository has no commits: `head = NO_COMMIT_SHA`, `branch = Project.default_branch`); (g) `kernel-versions.yaml` placeholder `{}` (E02-S04 replaces); (h) `.ai/.gitignore`, append fragment to root `.gitignore` if lines absent; (i) `projects` row upsert through `ProjectRepository`; (j) `production-kit.yaml`.
2. Existing files are never overwritten; they are listed in `unchanged_paths`. A second run produces `created_paths == []` and exit 0.
3. Without `--yes`, a non-TTY stdin aborts with exit 1 and message `bootstrap requires --yes in non-interactive mode`; with a TTY the command prompts `Create Production Kit in <repo>? [y/N]`. `cmd_bootstrap` checks this before `open_bootstrapper`, so nothing is created.
4. `--key` must match `ProjectKey`; invalid → exit 1 before any filesystem change (checked by `cmd_bootstrap`).
5. GDD headings are collected from H1/H2 lines of every GDD file; when `--gdd` is omitted and `GDD/` exists, all `*.md` files under it are used; when neither exists, `Goals` contains the single bullet `- (no GDD provided)`.
6. `ProductionKit` fields are filled with repo-relative paths; `skill_names` = builtin skill names present under `src/walk/skills/builtin/` (names read from directories); `approved_artifact_ids = []`.
7. `--provider jira` additionally requires the three Jira credentials present (`CredentialStore.present`, checked by `cmd_bootstrap` before `open_bootstrapper`); absence → exit 4 with the missing names and nothing created (status-map validation added in E03-S05).
8. All writes go through `MemoryManager.write` (Markdown), the owning package's writer (`ProjectionLock.write`), or atomic `tmp + rename` helpers (YAML) — no direct `open().write` outside `walk.persistence`/`walk.memory` helpers (CONVENTIONS §2).
9. `.ai/agents/permissions.yaml` is never a copy of the kernel defaults (single source: the package file of E02-S10). It is the empty narrowing file of the E02-S10 `PermissionsFile` schema: the comment lines `# Project narrowing of the kernel permission defaults (ADR-0006 D-6).` and `# Rules may only add DENY/REQUIRE_APPROVAL or restate a default ALLOW (E02-S10).`, then `rules: []` and `protected_actions: []`.
10. A database whose `projects` row has a different key → `ConfigError("database belongs to project <key>")` before step (d) (one project per database, ADR-0002 D-1); the same key → the row is left unchanged.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an empty temp git repo with `GDD/combat.md` When `run(options)` Then every path of ARCHITECTURE §8 `[MVP]` + `agents/` exists | `tests/orchestrator/test_bootstrap.py::test_bootstrap_creates_full_ai_tree` |
| 2 | Given the same repo When `run` twice Then second `created_paths == []` and file hashes unchanged | `tests/orchestrator/test_bootstrap.py::test_bootstrap_is_idempotent` |
| 3 | Given preflight MISSING git When `run` Then `ConfigError` and no `.ai/agents/` created | `tests/orchestrator/test_bootstrap.py::test_bootstrap_aborts_on_preflight_failure` |
| 4 | Given GDD with headings `# Combat`, `## Shotgun` When `project_skeleton` Then `Goals` has bullet `Combat` and `related.gdd` lists the file | `tests/memory/test_skeletons.py::test_project_skeleton_seeds_goals_from_gdd_headings` |
| 5 | Given skeleton When parsed by `MemoryManager.read("project")` Then all ten §36 sections present in order | `tests/memory/test_skeletons.py::test_project_skeleton_has_all_sections_in_order` |
| 6 | Given `--provider jira` and no credentials When `walk bootstrap --yes` Then exit 4 listing `JIRA_BASE_URL` and no `.ai/` created | `tests/cli/test_cmd_bootstrap.py::test_bootstrap_jira_requires_credentials` |
| 7 | Given no `--yes` and non-TTY When `walk bootstrap` Then exit 1 and nothing created | `tests/cli/test_cmd_bootstrap.py::test_bootstrap_requires_yes_when_non_interactive` |
| 8 | Given `--key demo` (lowercase) When `walk bootstrap --yes` Then exit 1 | `tests/cli/test_cmd_bootstrap.py::test_bootstrap_rejects_invalid_project_key` |
| 9 | Given a successful run When reading `production-kit.yaml` Then it validates as `ProductionKit` with `kit_version` | `tests/orchestrator/test_bootstrap.py::test_bootstrap_writes_production_kit_file` |
| 10 | Given a successful run When querying `projects` Then one row with `key`, `repo_path`, `work_provider` | `tests/orchestrator/test_bootstrap.py::test_bootstrap_inserts_project_row` |
| 11 | Given a git repo without commits When `run` Then it succeeds and the `project.md` freshness head is `0000000` | `tests/orchestrator/test_bootstrap.py::test_bootstrap_without_commits_stamps_placeholder_head` |
| 12 | Given a successful run When reading `.ai/agents/permissions.yaml` Then it holds the two comment lines, `rules: []` and `protected_actions: []` only | `tests/orchestrator/test_bootstrap.py::test_bootstrap_writes_empty_permissions_narrowing` |
| 13 | Given a database whose `projects` row has key `OTHER` When `run` with key `DEMO` Then `ConfigError` and no `.ai/agents/` created | `tests/orchestrator/test_bootstrap.py::test_bootstrap_refuses_database_of_another_project` |

#### Evidence required
- Quality gate output.
- Demo: `walk bootstrap --provider local --key DEMO --name Demo --yes` → prints created paths; `tree .ai` (or `Get-ChildItem -Recurse .ai`) shows the layout; second run prints `nothing to do`.

#### Notes
- §25 ordering; ADR-0003 D-7/D-8; ARCHITECTURE §8; ADR-0020 (placement, constructor).
- `NEW NAME:` `Bootstrapper`, `BootstrapOptions`, `BootstrapResult`, `NO_COMMIT_SHA`, `open_bootstrapper`, `.ai/project/production-kit.yaml`, `walk.memory.skeletons`, defaults files under `integrations/defaults/`.
- Pitfall: a repo without commits has no HEAD, so `GitProvider.head` raises `GitError`; use `NO_COMMIT_SHA` and cover it in a test (AC 11).
- `import-linter`: `walk.orchestrator` has no row contract (it may import every lower package), but the "only the composition root wires service.py" contract applies, so `bootstrap.py` takes protocol-typed services and `open_bootstrapper` builds the `Default*` ones.
- Resolved block (architect, 2026-10-07). The implementer's BLOCKING note found four problems: an `integrations → memory` import (a cycle with `memory → integrations`), `integrations → improvement` from E02-S04, `WorkflowRepository` where the `projects` row needs `ProjectRepository`, and no way to resolve HEAD. ADR-0020 settles them. `Bootstrapper` moves to `src/walk/orchestrator/bootstrap.py`. The constructor takes `projects: ProjectRepository` and a required `git: GitProvider`. The templates stay under `integrations/defaults/` and the skeletons in `walk.memory.skeletons`. E02-S04, E03-S10, E03-S11, E04-S02 and E04-S11 now modify `src/walk/orchestrator/bootstrap.py`. Step (d) writes the empty narrowing file, because `src/walk/permissions/defaults.yaml` arrives with E02-S10 and stays the only source of defaults.
- Commit subject: `feat: add bootstrap command generating the production kit (E02-S03)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12.11):
```
370 files already formatted
All checks passed!
Success: no issues found in 369 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.85%
1178 passed, 5 deselected in 429.97s (0:07:09)
```
Touched modules: `orchestrator/bootstrap.py` 100 %, `cli/cmd_bootstrap.py` 100 %, `memory/skeletons.py` 100 %. All 13 acceptance tests pass, plus negative-path tests:
- a missing GDD file;
- an invalid `production-kit.yaml`;
- a failed atomic write (no temp file left behind);
- the same-key project row kept unchanged;
- the CLI's exit 4 on preflight, exit 1 on other kernel errors (a secret-shaped `--name` refused by `MemoryManager.write`), and the TTY prompt in both answers.

Demo on a temporary git repository under the system temp dir, outside this repository. It has one commit and `GDD/combat.md` with `# Combat`, `## Shotgun`, `# Exploration`. Real preflight probes ran; Codex is not installed on this host and no provider CLI was executed.
```
$ walk --repo <tmp>/game bootstrap --provider local --key DEMO --name Demo --yes
created:
  .walk/
  .ai/features/
  .ai/bugs/
  .ai/decisions/
  .ai/handovers/
  .ai/agents/roles/
  .ai/agents/skills/
  .ai/agents/roles/lead_dev.md
  .ai/agents/roles/orchestrator.md
  .ai/agents/roles/qc.md
  .ai/agents/roles/senior_dev.md
  .ai/agents/policies.yaml
  .ai/agents/models.yaml
  .ai/agents/permissions.yaml
  .ai/agents/hooks.yaml
  .ai/agents/projections.lock.yaml
  .ai/project/work-provider.yaml
  .ai/project/project.md
  .ai/project/constitution.md
  .ai/project/kernel-versions.yaml
  .ai/.gitignore
  .gitignore
  .ai/project/production-kit.yaml
exit=0
$ walk --repo <tmp>/game bootstrap --provider local --key DEMO --name Demo --yes
nothing to do
exit=0
$ find .ai .walk | sort
.ai
.ai/.gitignore
.ai/agents
.ai/agents/hooks.yaml
.ai/agents/models.yaml
.ai/agents/permissions.yaml
.ai/agents/policies.yaml
.ai/agents/projections.lock.yaml
.ai/agents/roles
.ai/agents/roles/lead_dev.md
.ai/agents/roles/orchestrator.md
.ai/agents/roles/qc.md
.ai/agents/roles/senior_dev.md
.ai/agents/skills
.ai/bugs
.ai/decisions
.ai/features
.ai/handovers
.ai/kernel.db
.ai/project
.ai/project/constitution.md
.ai/project/environment.yaml
.ai/project/kernel-versions.yaml
.ai/project/production-kit.yaml
.ai/project/project.md
.ai/project/work-provider.yaml
.walk
$ cat .gitignore
.walk/
graphify-out/
$ sed -n '/^## Goals/,/^## Platforms/p' .ai/project/project.md
## Goals

- Combat
- Exploration

## Platforms
```
Smoke check on the same repository: `walk doctor` exits 0 (`work_provider ready local`; skills `missing 5` per provider until `walk skills sync`), and `walk status` prints `project: DEMO`.

Level-0 decisions:
- **Step (a) and the kit folders.** Step (a) makes `.ai/` (already opened by the database) and `.walk/` (reported). The empty §8 `[MVP]` and kit folders are made at the start of step (d), after the preflight. These are `features/`, `bugs/`, `decisions/`, `handovers/`, `agents/roles/` and `agents/skills/`. This is why a failed preflight (AC 3) or a foreign database (AC 13) leaves no `.ai/agents/`. `.ai/` and `.ai/project/` are not reported, because they hold reported files and the database or preflight opens them anyway.
- **What `created_paths` / `unchanged_paths` list.** Repo-relative POSIX paths: the kit files, the empty folders (with a trailing `/`), and the root `.gitignore` when lines were appended. They do not list the database or `environment.yaml`. The preflight rewrites `environment.yaml` on every run by design (E02-S02), so a second run has `created_paths == []` while that file is refreshed.
- **Order of the project check.** Behavior 10 runs right after the migrations, before the preflight. A foreign database therefore aborts before `environment.yaml` is written. A row with the same key is left untouched; a new row is inserted with `created_at = clock.now()`.
- **Role, policy and model defaults** are copied byte for byte through an atomic temp-file rename. They are not memory documents: their front matter is the Constitution schema, and the file names are snake_case. So `MemoryManager.write` cannot address them. AC 1 checks that `ConstitutionLoader`, `PolicyLoader` and `load_models_config` accept the copies as project overrides. Package data is read with `importlib.resources`.
- **GDD.** `--gdd` paths must be files inside the repository (else `ConfigError`, exit 1). Without `--gdd`, every `*.md` under `GDD/` is used, recursively and sorted. The bootstrapper passes H1/H2 heading lines outside fenced code to `project_skeleton`. `Goals` gets one bullet per top-level heading: the H1 headings, or the H2 headings when no H1 exists. A GDD without headings gives `- (no headings found in the GDD)`; no GDD at all gives `- (no GDD provided)` (Behavior 5).
- **Skeleton details.** Both documents carry `extra.project_key`; the constitution title is `<name> constitution`. Sections other than `Goals` start empty. The constitution's four sections are a private constant in `walk.memory.skeletons`: `sections.py` is not in the Files table, and the type has no section schema there.
- **Production Kit fields.** `project_constraints_path = .ai/project/project.md#technical-constraints` (the field describes a section of `project.md`). `tool_config_path = .ai/agents/permissions.yaml` (a single path; `models.yaml` sits beside it). `initial_memory_paths = [project.md, kernel-versions.yaml]`, as the field description says. `kit_version = walk.__version__`. An existing `production-kit.yaml` is loaded and returned unchanged, and an invalid one raises `ConfigError`.
- **`work-provider.yaml`** is the package template (`kind: local` plus the commented ADR-0005 D-3 mapping, including the default `status_map`), with the `kind` line set to the provider.
- **No HEAD.** `GitError` from `head` or `current_branch` gives `NO_COMMIT_SHA` and `Project`'s default branch (`main`).
- **CLI.** An invalid key exits 1 with `invalid project key '<key>': expected 2-10 uppercase letters or digits`. The prompt is `typer.confirm("Create Production Kit in <repo>?", default=False)`, which prints `[y/N]`; a "no" exits 1 (`bootstrap aborted`). The Jira credential check uses the `JIRA_*` entries of `CREDENTIAL_NAMES` and exits 4 with `jira credentials missing: ...`. `--json` prints the `BootstrapResult`.
- **Typing gap, worked around in the composition root.** `DefaultIntegrationManager` does not yet satisfy the `IntegrationManager` protocol structurally: the `work`/`git`/... attributes are deferred to E03-S03 (E02-S02 Evidence). `open_bootstrapper` therefore passes it with `cast("IntegrationManager", ...)` and a comment. The bootstrapper calls only `preflight`. Strict mypy (`warn_redundant_casts`) will flag the cast once E03-S03 adds the attributes. The ADR-0020 constructor signature is unchanged.
- **Composition.** The private `_integrations` gains a keyword `unity_path` (`--unity-path` reaches the Unity probe). `open_bootstrapper` builds the ledger, `GitCliProvider`, `CredentialStore`, the memory manager (`open_memory`), `MigrationRunner` and `ProjectRepository` on the one database. The database connection lives for the one-shot command.

Also read: `walk/memory/{service,paths,sections,frontmatter}.py`, `walk/skills/lockfile.py`, `walk/workflow/repository.py`, `walk/integrations/{service,preflight}.py`, `walk/agents/constitution_loader.py`, `tests/integrations/test_preflight.py` (probe script reused), `tests/test_import_contracts.py`.

---

### E02-S04 — `kernel-versions.yaml` and behavior-version pins

**Status:** DONE (02077c1)
**Type:** feat
**Requirements:** §105, §24, §137
**Depends on:** E02-S03
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every builtin behaviour artifact is catalogued as a `BehaviorVersion`; bootstrap writes `.ai/project/kernel-versions.yaml` pinning the `DEFAULT` versions; startup validates pins; `walk version` lists them.

#### Scope
- In: improvement enums/models, `BehaviorVersionCatalog`, pin file schema + load + validate, bootstrap integration, startup step 3 check, `walk version`.
- Out: `register_version`, rollout stages, changelog (E10-S05); using pinned versions to select among multiple builtin versions (E10-S05 — until then exactly one version per artifact exists and must equal the pin).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/improvement/__init__.py` | create | re-exports |
| `src/walk/improvement/models.py` | create | `RolloutStage`, `ImprovementRisk`, `CandidateState`, `BehaviorVersion` |
| `src/walk/improvement/versions.py` | create | `BehaviorVersionCatalog`, `KernelVersionPins`, `PINS_PATH` |
| `src/walk/improvement/errors.py` | create | `VersionPinError` |
| `src/walk/orchestrator/bootstrap.py` | modify | — (step g writes pins from catalog; ADR-0020) |
| `pyproject.toml` | modify | — (import-linter: `walk.improvement` row contract, and `walk.improvement` added to the forbidden lists of the rows whose ARCHITECTURE §2.2 cell is `·`) |
| `src/walk/orchestrator/service.py` | modify | — (startup step 3 calls `KernelVersionPins.validate`) |
| `src/walk/cli/cmd_version.py` | create | `version` |
| `src/walk/cli/app.py` | modify | `--version` now delegates to `cmd_version` |
| `tests/improvement/test_versions.py` | create | — |
| `tests/cli/test_cmd_version.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 (`RolloutStage`, `ImprovementRisk`, `CandidateState`) and §4.14 `BehaviorVersion`, verbatim.
```python
# src/walk/improvement/versions.py
PINS_PATH: str = "project/kernel-versions.yaml"  # relative to .ai/


class BehaviorVersionCatalog:
    """Scans builtin behaviour files and yields one BehaviorVersion per artifact (stage=DEFAULT)."""

    def __init__(self, package_root: Path, clock: Clock) -> None: ...
    def scan(self) -> list[BehaviorVersion]:
        """WORKFLOW: walk/workflow/tables/*.yaml (`version`); CONSTITUTION: walk/agents/defaults/*.md (front matter `version`);
        SKILL: walk/skills/builtin/*/SKILL.md; PROMPT: walk/agents/templates/*.md.j2 (first-line comment `{# version: X.Y #}`);
        MODEL_ROUTING: walk/model_router/defaults/models.yaml; EFFORT_POLICY: walk/agents/defaults/policies.yaml;
        TOOL_USAGE: walk/tools/defaults/tools.yaml; CONTEXT_FORMAT: walk/context/ranking.yaml (if present)."""

    def key(self, v: BehaviorVersion) -> str: ...  # f"{v.kind.value}/{v.name}"


class KernelVersionPins(WalkModel):
    pins: dict[str, str] = Field(description="'<KIND>/<name>' -> 'MAJOR.MINOR'")

    @classmethod
    def from_catalog(cls, catalog: list[BehaviorVersion]) -> "KernelVersionPins": ...
    @classmethod
    def load(cls, ai_root: Path) -> "KernelVersionPins": ...
    def write(self, ai_root: Path) -> Path: ...
    def validate(self, catalog: list[BehaviorVersion]) -> None:
        """Raises VersionPinError listing: pins without catalog entry, catalog entries without pin, version mismatches."""
```
`walk version` output: `walk <kernel version>` then one line per pin `<KIND>/<name> <version>`; `--json` → `{"kernel": "...", "pins": {...}}`.

#### Behavior
1. Every artifact file lacking a `version` field makes `scan()` raise `ConfigError("<path>: missing version")` — this also protects E01 artefacts (ADR-0008 consequence).
2. `version` must match `^\d+\.\d+$`; otherwise `ConfigError`.
3. `content_sha256` is the SHA-256 of the file bytes; `source_path` is package-relative; `introduced_at = clock.now()` (not persisted in E02).
4. `from_catalog` pins every entry; `write` produces sorted keys for stable diffs.
5. `validate` collects all three problem classes before raising `VersionPinError(PermanentError)`; message lines are `missing pin: X`, `unknown pin: X`, `pin X wants 1.1, kernel provides 1.0`.
6. Bootstrap step (g) now writes real pins; an existing non-empty pin file is left untouched (idempotency rule S03-2).
7. Startup (`DefaultOrchestrator.start`, ARCHITECTURE §3.4 step 3) calls `validate`; failure aborts startup with exit 1 and the guidance `run 'walk version' and update .ai/project/kernel-versions.yaml`.
8. `walk version` works without a bootstrapped repo (prints kernel version only, pins section `(no project)`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the kernel package When `scan()` Then one entry per workflow table, constitution, builtin skill and template, each with `version` and sha | `tests/improvement/test_versions.py::test_catalog_scans_all_builtin_artifacts` |
| 2 | Given a temp table file without `version` When `scan()` Then `ConfigError` naming the path | `tests/improvement/test_versions.py::test_catalog_rejects_artifact_without_version` |
| 3 | Given catalog When `from_catalog().write()` then `load()` Then equal pins and sorted keys | `tests/improvement/test_versions.py::test_pins_roundtrip_sorted` |
| 4 | Given pins with an extra key When `validate` Then `VersionPinError` containing `unknown pin` | `tests/improvement/test_versions.py::test_validate_reports_unknown_pin` |
| 5 | Given pins missing one key When `validate` Then `VersionPinError` containing `missing pin` | `tests/improvement/test_versions.py::test_validate_reports_missing_pin` |
| 6 | Given a pin `1.1` for a `1.0` artifact When `validate` Then message `wants 1.1, kernel provides 1.0` | `tests/improvement/test_versions.py::test_validate_reports_version_mismatch` |
| 7 | Given bootstrapped repo When `walk version` Then kernel version line plus every pin | `tests/cli/test_cmd_version.py::test_version_lists_pins` |
| 8 | Given cwd outside any repo When `walk version` Then exit 0 and `(no project)` | `tests/cli/test_cmd_version.py::test_version_without_project` |
| 9 | Given a mismatched pin file When `DefaultOrchestrator.start()` Then startup raises `VersionPinError` before `ON_PROJECT_START` fires | `tests/improvement/test_versions.py::test_startup_fails_on_pin_mismatch` |

#### Evidence required
- Quality gate output.
- Demo: `walk version` → `walk 0.1.0` + lines such as `WORKFLOW/story_workflow 1.0`, `CONSTITUTION/LEAD_DEV 1.0`, `SKILL/walk-output-contract 1.0`.

#### Notes
- ADR-0008 D-3/D-4 (data model fixed now, tooling Stage 10); ARCHITECTURE §9.
- `NEW NAME:` `BehaviorVersionCatalog`, `KernelVersionPins`, `VersionPinError`, `PINS_PATH`, template version comment convention `{# version: X.Y #}`.
- Pitfall: creating `src/walk/improvement/__init__.py` makes `tests/test_import_contracts.py::test_contracts_match_dependency_table` treat `improvement` as an existing package, so the import-linter contracts in `pyproject.toml` must gain its row and its column in the same commit. The bootstrapper lives in `walk.orchestrator` (ADR-0020), which may import `improvement`.
- Commit subject: `feat: add behavior version catalog and kernel version pins (E02-S04)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12.11):
```
378 files already formatted
All checks passed!
Success: no issues found in 377 source files
Contracts: 21 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.85%
1202 passed, 5 deselected in 436.58s (0:07:16)
```
Touched modules: `improvement/*` 100 %, `cli/cmd_version.py` 100 %, `orchestrator/bootstrap.py` 100 %, `tools/service.py` 100 %. All 9 acceptance tests pass, plus negative paths: version not `MAJOR.MINOR` or not quoted, a template without the version comment, a constitution without front matter, policies without role versions, invalid YAML, an invalid pin file (CLI exit 1), and bootstrap replacing the `{}` placeholder while keeping an edited pin file. Import-linter: 21 contracts, including the new `improvement` row.

Demo on the temporary repository bootstrapped in the E02-S03 demo, outside this repository. It still had the E02-S03 `{}` placeholder:
```
$ cat .ai/project/kernel-versions.yaml
{}
$ walk --repo <tmp>/game bootstrap --provider local --key DEMO --name Demo --yes
created:
  .ai/project/kernel-versions.yaml
exit=0
$ walk --repo <tmp>/game version
walk 0.1.0
CONSTITUTION/LEAD_DEV 1.0
CONSTITUTION/ORCHESTRATOR 1.0
CONSTITUTION/QC 1.0
CONSTITUTION/SENIOR_DEV 1.0
EFFORT_POLICY/ART_DIRECTOR 1.0
... (one EFFORT_POLICY line per role of policies.yaml, 11 in all)
MODEL_ROUTING/models 1.0
PROMPT/ANALYSIS 1.0
... (9 PROMPT lines)
SKILL/code-review-checklist 1.0
SKILL/git-hygiene 1.0
SKILL/qc-exploratory-testing 1.0
SKILL/unity-csharp-conventions 1.0
SKILL/walk-output-contract 1.0
TOOL_USAGE/tools 1.0
WORKFLOW/bug_workflow 1.0
WORKFLOW/feature_workflow 1.0
WORKFLOW/phase_workflow 1.0
WORKFLOW/rc_workflow 1.0
WORKFLOW/story_workflow 1.0
exit=0
$ walk version            # cwd outside any repository
walk 0.1.0
(no project)
exit=0
```

Contract fixes and decisions for the owner:
- **`TOOL_USAGE` path and version.** This is a small additive fix, made in this commit. The story names `walk/tools/defaults/tools.yaml`, but the catalogue lives at `walk/tools/builtin/tools.yaml` (E01-S14) and had no `version`, so Behavior 1 made `scan()` fail on the real package. The fix: `version: "1.0"` in the builtin catalogue, and an optional `version: str | None` on the private `_ToolFile` schema in `tools/service.py`. Project `tools.yaml` files without `version` stay valid. Both files are outside the Files table and are named in the commit body.
- **`scheduled_states.yaml` is not catalogued.** The WORKFLOW glob is `workflow/tables/*_workflow.yaml`: the five transition tables, which are the "workflow tables" of AC 1. `scheduled_states.yaml` holds the E01-S29 routing rows. It is a top-level YAML list with no `version` field, and adding one would change its format and the router loader. As a result, routing-row changes are **not pinned** today. If they should be, the owner/architect decides on a format (for example `{version, rows}`) in a later story.
- **`EFFORT_POLICY` per role.** `policies.yaml` has no top-level version. Each role's `RuntimePolicy` has its own `version`, so the catalogue yields one entry per role (`EFFORT_POLICY/<ROLE>`), all with the file's sha. A role without `version`, or a file without `roles`, raises `missing version`.
- **Names.** CONSTITUTION uses the front matter `id` (`LEAD_DEV`); SKILL uses the folder name; PROMPT uses the template stem (`IMPLEMENT`); MODEL_ROUTING/TOOL_USAGE/CONTEXT_FORMAT use `models`/`tools`/`ranking`. Single-file artifacts that are absent are skipped (`context/ranking.yaml` does not exist yet). An absent file in the real package would surface at startup as `unknown pin`.
- **Strict version type.** `version` must be a quoted `MAJOR.MINOR` string; YAML `1.0` (a float) is rejected, because `1.10` would read as `1.1`.
- **Front matter** of constitutions and skills is parsed locally with `yaml`. `walk.memory.frontmatter` is not allowed: the `improvement → memory` cell permits only `models`/`protocols`/`errors`. ARCHITECTURE §2.3 `yaml` row now lists `walk/improvement/versions.py`.
- **Pin file semantics.** `load` returns empty pins for an absent file and for the `{}` placeholder; anything else invalid raises `ConfigError` (`invalid kernel version pins ...`). `write` is atomic, with sorted keys under `pins:`. `validate` reports `missing pin` (sorted), then `unknown pin` (sorted), then mismatches (sorted). Its `VersionPinError` message ends with `run 'walk version' and update .ai/project/kernel-versions.yaml`, and `detail["problems"]` holds the lines. The contract name `validate` shadows pydantic's deprecated v1 classmethod `BaseModel.validate`, so the method carries `# type: ignore[override]` with that reason.
- **Startup check placement.** E02-S07 established the pattern: §3.4 step 3 checks are a composition-built `startup_checks` callable. `build_kernel` (`cli/composition.py`, outside the Files table, named in the commit body) now chains `_version_pin_check` before the drift check. `orchestrator/service.py` changes only its docstring. **A repository without `kernel-versions.yaml` is not checked** (warning logged). That covers repositories that were never bootstrapped: the E01 e2e gate and CLI fixtures migrate a database without bootstrap. A present file, including the `{}` placeholder, is validated. A mismatch raises `VersionPinError` before `PROJECT_STARTED`/`ON_PROJECT_START`, and `walk run` exits 1 through `exit_with`.
- **Bootstrap step (g).** It writes `KernelVersionPins.from_catalog(scan())` when the file is absent or empty, and reports it in `created_paths`; a non-empty file is listed in `unchanged_paths` (Behavior 6). An E02-S03 test assertion (`kernel-versions.yaml == {}`) now checks the real pins. A new test, `test_bootstrap_replaces_placeholder_pins_and_keeps_real_ones`, was added to `tests/orchestrator/test_bootstrap.py`, which is outside the Files table.
- **`walk version`.** It prints the project's pins from `.ai/project/kernel-versions.yaml`, sorted, with `(no project)` without a pin file and `(no pins)` for the placeholder. `--json` gives `{"kernel": ..., "pins": {...}}`, with `pins: null` without a project. `walk --version` calls the same command for the current directory. INTERFACES §6 row updated.
- **Import contracts.** `pyproject.toml` has the new `improvement` row (forbids permissions, tools, integrations, context, runtime, orchestrator) and `walk.improvement` in the forbidden lists of the 18 rows whose §2.2 cell is `·`. It is also in the source lists of "nothing imports cli" and "only the composition root wires service.py". `tests/improvement/__init__.py` was created, like every other test package.

---

### E02-S05 — `SkillRegistry` loading and builtin skills

**Status:** DONE (65ef1d3)
**Type:** feat
**Requirements:** §28, §29, §30, §137
**Depends on:** E01-S14
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Canonical skills (`SKILL.md` + front matter) are loaded from kernel built-ins and `.ai/agents/skills/`, project skills shadow built-ins by name, `for_role` resolves role defaults plus required skills, and the five builtin skills ship with real content.

#### Scope
- In: `DefaultSkillRegistry.load/get/for_role`, front-matter schema, builtin skill folders, loader errors.
- Out: `project_all` (E02-S06), `check_drift` (E02-S07), skill version pinning behaviour (E10-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/skills/service.py` | create | `DefaultSkillRegistry` |
| `src/walk/skills/loader.py` | create | `SkillFrontMatter`, `parse_skill_file`, `discover_skill_dirs` |
| `src/walk/skills/errors.py` | create | `SkillLoadError` |
| `src/walk/skills/__init__.py` | modify | re-export `DefaultSkillRegistry`, `parse_skill_file` |
| `src/walk/skills/builtin/walk-output-contract/SKILL.md` | create | — |
| `src/walk/skills/builtin/unity-csharp-conventions/SKILL.md` | create | — |
| `src/walk/skills/builtin/git-hygiene/SKILL.md` | create | — |
| `src/walk/skills/builtin/qc-exploratory-testing/SKILL.md` | create | — |
| `src/walk/skills/builtin/code-review-checklist/SKILL.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`default_skills` per role, see Behavior 7) |
| `src/walk/cli/composition.py` | modify | — (constructs `DefaultSkillRegistry`) |
| `tests/skills/test_loader.py` | create | — |
| `tests/skills/test_service.py` | create | — |
| `tests/skills/test_builtin_skills.py` | create | — |

#### Interface contract
See INTERFACES.md §1.11 `SkillRegistry` (`load`, `get`, `for_role`). Deltas:
```python
# src/walk/skills/loader.py
class SkillFrontMatter(WalkModel):
    name: SkillName
    version: str = Field(pattern=r"^\d+\.\d+$")
    description: str = Field(min_length=1, max_length=300)
    scope: LearningScope
    applies_to_roles: list[AgentRole] = Field(default_factory=list)
    requires_tools: list[ToolName] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def discover_skill_dirs(root: Path) -> list[Path]: ...  # <root>/<kebab-name>/SKILL.md present
def parse_skill_file(
    path: Path,
) -> Skill: ...  # front matter + body; content_sha256 over file bytes


# src/walk/skills/service.py
class DefaultSkillRegistry:
    def __init__(
        self,
        builtin_root: Path,
        project_root: Path | None,
        role_defaults: Mapping[AgentRole, list[SkillName]],
    ) -> None: ...
```

#### Behavior
1. `load()` reads built-ins then project skills; a project skill with the same `name` replaces the builtin entry (`source_path` points to the project file). Result is cached until `load()` is called again.
2. Directory name must equal front-matter `name`; mismatch → `SkillLoadError(ConfigError)` naming both.
3. Missing/invalid front matter, body > 64 KB, or `scope: KERNEL` under the project root → `SkillLoadError`.
4. `get(name)` raises `ConfigError("unknown skill <name>")` when absent.
5. `for_role(role, required)` returns `role_defaults[role] ∪ required` in that order, de-duplicated; every `required` name must resolve, otherwise `ConfigError` listing the missing names (§29).
6. Builtin skill bodies (each ≤ 4 KB, Markdown):
   - `walk-output-contract`: the `AgentOutput` JSON schema field by field (`status` values and when to use each, `result`, `findings`, `changes`, `decisions` as proposals, `evidence`, `context_updates` with `doc_id/section/operation`, `new_tasks`, `new_bugs`, `escalations`, `next_actions`, `handover` required on `PARTIAL`, `effort_request`, `observations`, `no_context_change_reason`), the mandatory last step "write `<worktree>/.walk/output.json`", and the rule "never write under `.ai/` directly". `applies_to_roles`: all MVP roles.
   - `unity-csharp-conventions`: namespaces, assembly definitions, serialization, MonoBehaviour lifecycle, async/await vs coroutines, EditMode/PlayMode test placement. Roles: SENIOR_DEV, LEAD_DEV. `requires_tools: []`.
   - `git-hygiene`: work only on the provided branch, never switch branches, small commits are made by the kernel, no force operations, read `git status` before finishing. Roles: SENIOR_DEV, LEAD_DEV, QC. `requires_tools: ["git.status"]` is NOT used (kernel tool) — leave `requires_tools: []`.
   - `qc-exploratory-testing`: §65 question list, severity rubric mapped to `Severity`, reproduction-step format for `BugDraft.reproduction`. Roles: QC.
   - `code-review-checklist`: architecture fit, tests present, boundary/permission concerns, evidence check, verdict → `APPROVED`/`REJECTED` with findings. Roles: LEAD_DEV.
7. `policies.yaml` `default_skills`: ORCHESTRATOR `[walk-output-contract]`; LEAD_DEV `[walk-output-contract, code-review-checklist, unity-csharp-conventions, git-hygiene]`; SENIOR_DEV `[walk-output-contract, unity-csharp-conventions, git-hygiene]`; QC `[walk-output-contract, qc-exploratory-testing, git-hygiene]`.
8. `Skill.version` of every builtin is `1.0`; `BehaviorVersionCatalog` (E02-S04) picks them up without changes.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the five builtin folders When `load()` Then five `Skill`s with matching names and sha | `tests/skills/test_service.py::test_load_returns_builtin_skills` |
| 2 | Given a project skill named `git-hygiene` When `load()` Then the returned skill's `source_path` is the project file | `tests/skills/test_service.py::test_project_skill_shadows_builtin` |
| 3 | Given folder `foo/` with front matter `name: bar` When `parse_skill_file` Then `SkillLoadError` | `tests/skills/test_loader.py::test_parse_rejects_name_directory_mismatch` |
| 4 | Given project skill with `scope: KERNEL` When `load()` Then `SkillLoadError` | `tests/skills/test_loader.py::test_project_skill_cannot_claim_kernel_scope` |
| 5 | Given `get("nope")` Then `ConfigError` | `tests/skills/test_service.py::test_get_unknown_raises_config_error` |
| 6 | Given QC role and required `[unity-csharp-conventions]` When `for_role` Then defaults first then the required skill, no duplicates | `tests/skills/test_service.py::test_for_role_merges_defaults_and_required` |
| 7 | Given required `[missing-skill]` When `for_role` Then `ConfigError` listing it | `tests/skills/test_service.py::test_for_role_missing_required_raises` |
| 8 | Given each builtin SKILL.md When measured Then body ≤ 4096 bytes and `walk-output-contract` mentions every `AgentOutput` field name | `tests/skills/test_builtin_skills.py::test_builtin_skills_size_and_contract_coverage` |

#### Evidence required
- Quality gate output.
- Demo: `uv run python -c "from walk.skills import DefaultSkillRegistry; ..."` is not a CLI; `walk skills list` arrives in E02-S06 — record the test transcript of `test_builtin_skills.py` instead.

#### Notes
- ADR-0007 D-1, D-4, D-6; names per WBS.md §3.10 (`NEW NAME` already registered).
- `NEW NAME:` `SkillFrontMatter`, `parse_skill_file`, `discover_skill_dirs`, `SkillLoadError`.
- Commit subject: `feat: add skill registry loader and builtin skills (E02-S05)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`):
```
353 files already formatted
All checks passed!
Success: no issues found in 351 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.90%
1100 passed, 3 deselected in 395.07s
```
Touched modules: `skills/loader.py`, `skills/service.py`, `skills/errors.py`, `skills/__init__.py` 100 %; `cli/composition.py` 100 %.

Demo (no CLI until E02-S06): transcript of `uv run pytest tests/skills/test_builtin_skills.py -v`, plus the parsed builtin skills:
```
tests/skills/test_builtin_skills.py::test_builtin_skills_size_and_contract_coverage PASSED
tests/skills/test_builtin_skills.py::test_policies_name_the_builtin_default_skills[LEAD_DEV] PASSED
tests/skills/test_builtin_skills.py::test_policies_name_the_builtin_default_skills[ORCHESTRATOR] PASSED
tests/skills/test_builtin_skills.py::test_policies_name_the_builtin_default_skills[QC] PASSED
tests/skills/test_builtin_skills.py::test_policies_name_the_builtin_default_skills[SENIOR_DEV] PASSED
tests/skills/test_builtin_skills.py::test_qc_skill_lists_the_section_65_questions PASSED
6 passed

code-review-checklist     1.0  2135 bytes  sha e165f612ee02...
git-hygiene               1.0  1637 bytes  sha d987e561f05c...
qc-exploratory-testing    1.0  1936 bytes  sha cffd68d9341e...
unity-csharp-conventions  1.0  2364 bytes  sha f5df41c95c0b...
walk-output-contract      1.0  2856 bytes  sha c880fd620a62...
```

Level-0 decisions:
- **`content_sha256` is the SHA-256 of the body, not of the file bytes.** The interface comment says "content_sha256 over file bytes". The E01-S14 `Skill` model derives the hash from `body_markdown` and rejects any other value, and the model is the published contract (DOMAIN-MODEL §4.6). A front-matter-only edit therefore keeps the hash; the version field covers that case. CRLF is normalised to LF before parsing.
- `walk.skills` may not import `walk.memory` (§2.2), so the front matter is split locally: a `---` block at the top, parsed with `yaml.safe_load` (`skills` is an allowed `yaml` user, §2.3). Every failure is a `SkillLoadError(ConfigError)` that names the path. The 64 KB limit is on the UTF-8 body.
- `for_role` raises `ConfigError` with `detail["missing"]` listing every unresolved name, for defaults and required alike. A role without defaults gets `[]` plus `required`. `get`/`for_role` load lazily on first use; `load()` rebuilds the cache.
- `project_all` / `check_drift` raise `ConfigError("implemented in E02-S06/E02-S07")` (deferred-method pattern).
- **`walk-output-contract` also documents `debate_position`.** AC 8 requires every `AgentOutput` field, and Behavior 6's list omits that field.
- `requires_tools: []` for all five built-ins (Behavior 6). Scope is `KERNEL`, version `1.0`.
- Composition: `_agent_services` builds `DefaultSkillRegistry(walk/skills/builtin, .ai/agents/skills, role defaults)`. Role defaults are `PolicyLoader.load(role).default_skills` for every role except the actors `USER`/`KERNEL`. The registry is passed to `DefaultAgentManager(skills=...)`, so `instantiate` now validates skill names (§29). The E01 gate still passes with the new `default_skills`.

---

### E02-S06 — Skill projections for Claude and Codex, lock file, `walk skills list/sync`

**Status:** DONE (11d1d66)
**Type:** feat
**Requirements:** §28, §29, §137, §138
**Depends on:** E02-S05, E01-S21, E01-S22, E01-S25
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Each adapter projects canonical skills into the run worktree in its native format; `project_all` records projections in `skill_projections` and `.ai/agents/projections.lock.yaml`, excludes them from git, and `SandboxManager.create` performs it for every run.

#### Scope
- In: `ClaudeSkillProjector`, `CodexSkillProjector`, `project_all`, lock file, `.git/info/exclude`, sandbox hook-in, `walk skills list`, `walk skills sync`, roundtrip test.
- Out: drift detection (E02-S07); MCP-served skills (deferred, ADR-0007).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/adapters/claude/projector.py` | create | `ClaudeSkillProjector` |
| `src/walk/model_router/adapters/codex/projector.py` | create | `CodexSkillProjector`, `AGENTS_MD_START`, `AGENTS_MD_END`, `INLINE_LIMIT_BYTES` |
| `src/walk/model_router/adapters/claude/adapter.py` | modify | `ClaudeAdapter.skill_projector` returns `ClaudeSkillProjector` |
| `src/walk/model_router/adapters/codex/adapter.py` | modify | `CodexAdapter.skill_projector` returns `CodexSkillProjector` |
| `src/walk/skills/service.py` | modify | `DefaultSkillRegistry.project_all` |
| `src/walk/skills/lockfile.py` | create | `ProjectionLock`, `LOCK_PATH` |
| `src/walk/skills/repository.py` | create | `SkillProjectionRepository` |
| `src/walk/runtime/sandbox.py` | modify | — (`DefaultSandboxManager.create` calls `project_all` with the run's adapter projector) |
| `src/walk/cli/cmd_skills.py` | create | `skills_list`, `skills_sync` |
| `src/walk/cli/app.py` | modify | register `skills` group |
| `tests/fakes/fake_model_adapter.py` | modify | `FakeSkillProjector` (writes `<worktree>/.walk/fake-skills/<name>.md`) |
| `tests/model_router/adapters/claude/test_projector.py` | create | — |
| `tests/model_router/adapters/codex/test_projector.py` | create | — |
| `tests/skills/test_projection_roundtrip.py` | create | — |
| `tests/skills/test_lockfile.py` | create | — |
| `tests/cli/test_cmd_skills.py` | create | — |
| `src/walk/skills/protocols.py` | modify | `SkillProjector.render` (contract addition, see Evidence) |
| `src/walk/integrations/protocols.py`, `src/walk/integrations/git/provider.py`, `tests/fakes/fake_git_provider.py` | modify | `GitProvider.git_path` (Behavior 4, Pitfall) |
| `src/walk/cli/composition.py` | modify | `skill_projectors`, `open_skill_registry`; registry with projection deps; sandbox `project_skills` |
| `tests/integrations/git/test_provider.py`, `tests/model_router/test_fake_adapter.py`, `tests/skills/test_service.py` | modify | — |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.11 `render`, GitProvider `git_path`) |

#### Interface contract
See INTERFACES.md §1.11 `SkillProjector.project`, `SkillRegistry.project_all`; DOMAIN-MODEL §4.6 `SkillProjection`.
```python
# codex/projector.py
AGENTS_MD_START = "<!-- walk:skills:start -->"
AGENTS_MD_END = "<!-- walk:skills:end -->"
INLINE_LIMIT_BYTES = 4096


class CodexSkillProjector:
    provider = "codex"

    def project(
        self, skill: Skill, worktree_path: str
    ) -> SkillProjection: ...  # target_path = <worktree>/AGENTS.md (section) ; body > limit → also <worktree>/.walk/skills/<name>/SKILL.md
    def render_section(
        self, skills: list[Skill], worktree_path: str
    ) -> str: ...  # full managed section text


# claude/projector.py
class ClaudeSkillProjector:
    provider = "claude"

    def project(
        self, skill: Skill, worktree_path: str
    ) -> (
        SkillProjection
    ): ...  # target_path = <worktree>/.claude/skills/<name>/SKILL.md ; copies references/ scripts/


# src/walk/skills/lockfile.py
LOCK_PATH = "agents/projections.lock.yaml"


class ProjectionLock(WalkModel):
    projections: list[SkillProjection]

    @classmethod
    def load(cls, ai_root: Path) -> "ProjectionLock": ...
    def write(self, ai_root: Path) -> Path: ...
    def for_provider(self, provider: str) -> list[SkillProjection]: ...


# src/walk/skills/repository.py
class SkillProjectionRepository:
    def __init__(self, db: Database) -> None: ...
    async def upsert(self, uow: UnitOfWork, projections: list[SkillProjection]) -> None: ...
    async def list(self, provider: str | None = None) -> list[SkillProjection]: ...
```
CLI: `walk skills list [--json]` (name, version, scope, source, roles); `walk skills sync [--worktree PATH]` (projects all skills for every configured adapter into the given worktree, default repo root `.walk/projections/<provider>/`, and rewrites the lock file).

#### Behavior
1. `project()` is pure: it returns `SkillProjection` with `content_sha256` of the rendered content and `generated_from_sha256 = skill.content_sha256`; `project_all` performs the writes.
2. Claude target: `<worktree>/.claude/skills/<name>/SKILL.md` — rendered as the canonical front matter reduced to `name`, `description` plus the body verbatim; `references/` and `scripts/` copied if present.
3. Codex target: one managed section in `<worktree>/AGENTS.md` between the markers, containing for each skill `### <name> (v<version>)`, the description, and the body inline when `len(body.encode()) <= INLINE_LIMIT_BYTES`, otherwise the line `See .walk/skills/<name>/SKILL.md` and that file is written. Content outside the markers is preserved byte-for-byte; a missing `AGENTS.md` is created with only the section.
4. `project_all` writes atomically, appends every target (relative) path to `<worktree>/.git/info/exclude` once (worktrees: resolves the common git dir via `git rev-parse --git-path info/exclude` through `GitProvider`), upserts `skill_projections`, writes the lock file, and returns the projections.
5. Re-running `project_all` with unchanged skills produces identical files and identical hashes (determinism; no timestamps inside rendered content — `generated_at` lives only in the lock).
6. `DefaultSandboxManager.create` calls `project_all([adapter.skill_projector()], worktree, skills)` after `add_worktree` and before guard-hook installation; failure → `ConfigError` and the worktree is removed.
7. `walk skills sync` without a daemon runs in-process; with `--json` prints the lock content.
8. The `FakeSkillProjector` writes one file per skill so E01/E02 e2e tests can assert projection without real adapters.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a 1 KB skill When Claude `project` Then target under `.claude/skills/<name>/SKILL.md` and content starts with reduced front matter | `tests/model_router/adapters/claude/test_projector.py::test_claude_projection_target_and_content` |
| 2 | Given two skills, one 5 KB When Codex `render_section` Then small body inline, large one linked to `.walk/skills/<name>/SKILL.md` | `tests/model_router/adapters/codex/test_projector.py::test_codex_section_inlines_small_and_links_large` |
| 3 | Given existing `AGENTS.md` with user text When `project_all` Then text preserved and exactly one managed section | `tests/model_router/adapters/codex/test_projector.py::test_codex_preserves_content_outside_markers` |
| 4 | Given canonical skills When `project_all` twice Then identical file hashes and lock entries | `tests/skills/test_projection_roundtrip.py::test_projection_is_deterministic_for_both_providers` |
| 5 | Given `project_all` When reading `.git/info/exclude` Then every target path listed once | `tests/skills/test_projection_roundtrip.py::test_projection_targets_excluded_from_git` |
| 6 | Given lock written When `ProjectionLock.load` Then equals written model | `tests/skills/test_lockfile.py::test_lock_roundtrip` |
| 7 | Given a run with `FakeModelAdapter` When `SandboxManager.create` Then fake projection files exist in the worktree | `tests/skills/test_projection_roundtrip.py::test_sandbox_create_projects_skills` |
| 8 | Given projector raising When `SandboxManager.create` Then `ConfigError` and worktree removed | `tests/skills/test_projection_roundtrip.py::test_sandbox_create_removes_worktree_on_projection_failure` |
| 9 | Given bootstrapped repo When `walk skills list` Then five rows | `tests/cli/test_cmd_skills.py::test_skills_list_shows_builtins` |
| 10 | Given bootstrapped repo When `walk skills sync` Then lock file has entries for `claude` and `codex` | `tests/cli/test_cmd_skills.py::test_skills_sync_writes_lock_for_all_providers` |

#### Evidence required
- Quality gate output.
- Demo: `walk skills list`; `walk skills sync` → `projected 5 skills for 2 providers`; `cat .ai/agents/projections.lock.yaml | head`.

#### Notes
- ADR-0007 D-2; Invariant 11.
- `NEW NAME:` `ClaudeSkillProjector`, `CodexSkillProjector`, `AGENTS_MD_START/END`, `INLINE_LIMIT_BYTES`, `ProjectionLock`, `LOCK_PATH`, `SkillProjectionRepository`, `FakeSkillProjector`; from implementation: `SkillProjector.render`, `GitProvider.git_path`, `DefaultSkillRegistry(db=, ai_root=, exclude_path=)` with `ExcludePath`, `DefaultSandboxManager(project_skills=)`, `skills_app`, `skill_projectors`, `open_skill_registry`.
- Pitfall: in a linked worktree `.git` is a file; always resolve `info/exclude` through git, never by path concatenation.
- Commit subject: `feat: add provider skill projections and lock file (E02-S06)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`):
```
359 files already formatted
All checks passed!
Success: no issues found in 357 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.87%
1117 passed, 3 deselected in 404.99s
```
Touched modules: `skills/lockfile.py`, `skills/repository.py`, `skills/protocols.py`, `runtime/sandbox.py`, `integrations/git/provider.py`, `claude/projector.py`, `cli/composition.py`, `cli/app.py` 100 %; `skills/service.py` 99 %; `codex/projector.py` 98 %; `cli/cmd_skills.py` 96 %.

Demo on a scratch git repository. `walk bootstrap` is BLOCKED (E02-S03), so the database and project were seeded with the test helper `tests.cli.conftest.migrate`:
```
$ walk skills list --repo <tmp>/game
name                      version  scope   source                                                  roles
------------------------  -------  ------  ------------------------------------------------------  -----
code-review-checklist     1.0      KERNEL  ...\src\walk\skills\builtin\code-review-checklist\SKILL.md  LEAD_DEV
git-hygiene               1.0      KERNEL  ...\src\walk\skills\builtin\git-hygiene\SKILL.md         SENIOR_DEV,LEAD_DEV,QC
qc-exploratory-testing    1.0      KERNEL  ...
unity-csharp-conventions  1.0      KERNEL  ...
walk-output-contract      1.0      KERNEL  ...
$ walk skills sync --repo <tmp>/game
projected 5 skills for 2 providers
$ head .ai/agents/projections.lock.yaml
projections:
- skill: code-review-checklist
  provider: claude
  target_path: .claude/skills/code-review-checklist/SKILL.md
  content_sha256: 63a84e6a73d90d0baff38438e555e17d054d858247523e9c0df39468b7e55061
  generated_from_sha256: e165f612ee02731153f3c9e33db0c020e4955be908ff082bf1117a0065a7df50
  generated_at: '2026-10-06T20:49:32.570578Z'
$ tail -3 .git/info/exclude
/.claude/skills/unity-csharp-conventions/SKILL.md
/.claude/skills/walk-output-contract/SKILL.md
/AGENTS.md
```

Contract additions (INTERFACES updated in this commit):
- **`SkillProjector.render(skills, worktree_path) -> dict[str, bytes]`.** `project()` returns only a path and a hash, so `project_all` had no content to write. `render` returns every file of a provider's projection; it may read existing files (to keep the text around the Codex markers) and never writes. `project_all` performs every write (Behavior 1).
- **`GitProvider.git_path(path, name)`** = absolute `git rev-parse --git-path <name>`. Behavior 4 and the Pitfall require resolving `info/exclude` through `GitProvider`, which had no such method. Implemented in `GitCliProvider` and `FakeGitProvider`; tested from a linked worktree.
- **`DefaultSkillRegistry` gets keyword-only `db`, `ai_root`, `exclude_path`.** The last is a callable, because `walk.skills` may not import `GitProvider` (§2.2). Without them, `project_all` raises `ConfigError("skill projection is not configured ...")`.
- **`DefaultSandboxManager` gets keyword-only `project_skills`** (async `(run, item, worktree)`). It runs after `add_worktree` and before the guard hooks. Any failure becomes `ConfigError("skill projection failed: ...")`, and `create` removes the new worktree (the branch is kept). The existing `post_create` extension list keeps its E01 semantics.

Level-0 decisions:
- `adopt` projects too: for an existing worktree, and before the guard hooks of a re-added one. A fallback continuation may switch provider (codex → claude) and needs its own projection (Invariant 1 parity). On failure the worktree is kept, because it may hold uncommitted work.
- **Lock.** Target paths are worktree-relative POSIX paths, so the lock does not churn per run worktree. The DB rows keep absolute targets. Entries are merged per `(provider, skill, target)`: an entry whose hashes are unchanged keeps its `generated_at`, other providers' entries are kept, and the file is rewritten only when something changed. Re-runs are therefore byte-identical (AC 4). Orphan cleanup is E02-S07 (`regenerate`).
- **Exclude entries** are anchored `/<relative path>` lines, appended once and written atomically. Paths come from `render` (Claude `SKILL.md` plus copied `references/`/`scripts/` files, Codex `AGENTS.md` plus linked large skills).
- **Claude** content: front matter `name`, `description` (version dropped as Behavior 2 says), a blank line, then the body verbatim. YAML is dumped without line wrapping for stability. `references/` and `scripts/` are copied recursively from the canonical skill folder.
- **Codex.** Managed section = start marker, a `## Skills` header line, one `### <name> (v<version>)` / description / body-or-link entry per skill, end marker. Each projection's `content_sha256` is the sha of its own entry text, which is what E02-S07 Behavior 1 attributes drift to. A body over `INLINE_LIMIT_BYTES` becomes `See .walk/skills/<name>/SKILL.md`, with that file (reduced front matter + body) written alongside. An existing `AGENTS.md` keeps everything before the first start marker and after the last end marker, which collapses duplicates into one section. Without markers the section is appended after a blank line.
- **`walk skills sync`** projects for both kernel providers (`claude`, `codex`) whether or not the Claude SDK is installed, since projection needs no SDK. Targets are `--worktree` or `<repo>/.walk/projections/<provider>/`. It needs a bootstrapped repo (`.ai/kernel.db` with one project), otherwise exit 1 `no .ai/kernel.db; run 'walk bootstrap'`. `--json` prints the lock. `walk skills list --json` prints the summaries.
- Composition: `build_kernel` now creates the git provider before the agent services, so the registry can resolve exclude files. `_skill_projection(router, skills)` uses the run's adapter projector and `for_role(run.role, contract.required_skills)`. `FakeModelAdapter.skill_projector()` now returns `FakeSkillProjector`, and the E01 e2e gate passes with projection active.
- Superseded tests: `tests/skills/test_service.py::test_projection_and_drift_name_their_stories` becomes `test_drift_names_its_story`, and `tests/model_router/test_fake_adapter.py` no longer expects `skill_projector()` to raise.

For the owner:
- If a game repository tracks its own `AGENTS.md`, the Codex projection modifies a tracked file in the run worktree. `info/exclude` does not hide tracked files, so the managed section would reach the WIP commits. A repository that wants its own `AGENTS.md` needs a decision: for example, project into an untracked `AGENTS.override.md`, or exclude the managed block at commit time. Not addressed here.

---

### E02-S07 — Skill drift detection, `walk skills check-drift`, startup check

**Status:** DONE (9a8616c)
**Type:** feat
**Requirements:** §28, §27, §137, §138
**Depends on:** E02-S06, E02-S02
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`check_drift` reports missing, modified and orphaned projections against the lock; the CLI, startup step 3 and `walk doctor` use it; non-strict mode regenerates and logs a `CONTEXT_UPDATED` ledger event.

#### Scope
- In: `check_drift`, `walk skills check-drift [--strict]`, startup integration, doctor section.
- Out: `--fix` semantics in doctor (E02-S15 delegates to `skills sync`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/skills/service.py` | modify | `DefaultSkillRegistry.check_drift`, `DefaultSkillRegistry.regenerate` |
| `src/walk/skills/drift.py` | create | `compute_drift` |
| `src/walk/cli/cmd_skills.py` | modify | `skills_check_drift` |
| `src/walk/cli/cmd_doctor.py` | modify | — (adds `skills` section from `check_drift`) |
| `src/walk/orchestrator/service.py` | modify | — (startup step 3: `check_drift`; strict per `KernelSettings.strict`) |
| `src/walk/cli/composition.py` | modify | `KernelSettings.strict: bool = False` |
| `tests/skills/test_drift.py` | create | — |
| `tests/cli/test_cmd_skills_drift.py` | create | — |
| `src/walk/skills/protocols.py`, `src/walk/model_router/adapters/claude/projector.py`, `src/walk/model_router/adapters/codex/projector.py`, `tests/fakes/fake_model_adapter.py` | modify | `SkillProjector.scan` (contract addition, see Evidence) |
| `docs/01-architecture/ARCHITECTURE.md`, `docs/01-architecture/INTERFACES.md` | modify | — (§4.3 write point, §1.11 `scan`) |
| `tests/cli/test_cmd_doctor.py`, `tests/cli/test_cmd_work.py`, `tests/skills/test_service.py` | modify | — |

#### Interface contract
See INTERFACES.md §1.11 `SkillRegistry.check_drift`; DOMAIN-MODEL §4.6 `DriftReport`.
```python
# src/walk/skills/drift.py
def compute_drift(
    canonical: list[Skill], lock: list[SkillProjection], on_disk: Mapping[str, str | None]
) -> DriftReport:
    """on_disk: target_path -> sha256 of current file content (None if absent).
    missing  = canonical skills with no lock entry for the provider, or lock entry whose file is absent;
    modified = lock entries whose on-disk sha != recorded content_sha256, or whose generated_from_sha256 != canonical sha;
    orphaned = lock entries (or managed-section skills) with no canonical skill.
    ok = all three lists empty."""


class DefaultSkillRegistry:
    async def check_drift(
        self, projectors: list[SkillProjector], worktree_path: str
    ) -> DriftReport: ...
    async def regenerate(
        self, projectors: list[SkillProjector], worktree_path: str, report: DriftReport
    ) -> list[SkillProjection]:
        """project_all for affected skills; ledger CONTEXT_UPDATED payload {'skills_drift': report}."""
```
CLI: `walk skills check-drift [--strict] [--worktree PATH]` → exit 0 when `ok`; with drift: `--strict` → exit 1 after printing the report; without → regenerate, print `regenerated N projections`, exit 0.

#### Behavior
1. For Codex, "on-disk sha" of a skill is the sha of its sub-section text inside the managed block (so a hand edit of one skill is attributed to that skill); for Claude it is the file sha.
2. A canonical skill whose `content_sha256` changed since the lock was written is reported `modified` (lock `generated_from_sha256` mismatch), distinguishing the reason in `DriftReport` messages? — `DriftReport` has no messages; the CLI prints `modified (canonical changed)` vs `modified (projection edited)` by re-deriving the cause; the model itself is unchanged.
3. `regenerate` rewrites only skills in `missing ∪ modified`, deletes orphaned Claude files and removes orphaned Codex sub-sections, then rewrites the lock.
4. Startup step 3 runs `check_drift` on the repo-level projection directory `.walk/projections/<provider>/`; drift with `strict=True` → `ConfigError` aborts startup; otherwise `regenerate` and continue.
5. `walk doctor` prints a `skills` section: `ok` or counts per category; drift does not change doctor's exit code (that is `--strict`, E02-S15).
6. `check_drift` never writes; `regenerate` is the only mutating path.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given lock and intact files When `compute_drift` Then `ok` | `tests/skills/test_drift.py::test_drift_ok_when_lock_matches_disk` |
| 2 | Given a Claude projection file edited When `compute_drift` Then skill in `modified` | `tests/skills/test_drift.py::test_drift_detects_edited_claude_projection` |
| 3 | Given one Codex sub-section edited When `compute_drift` Then only that skill in `modified` | `tests/skills/test_drift.py::test_drift_attributes_codex_edit_to_single_skill` |
| 4 | Given canonical skill changed after lock When `compute_drift` Then `modified` | `tests/skills/test_drift.py::test_drift_detects_canonical_change` |
| 5 | Given lock entry for removed skill When `compute_drift` Then `orphaned` | `tests/skills/test_drift.py::test_drift_detects_orphaned_projection` |
| 6 | Given new canonical skill without projection When `compute_drift` Then `missing` | `tests/skills/test_drift.py::test_drift_detects_missing_projection` |
| 7 | Given drift When `regenerate` Then files restored, lock rewritten, one `CONTEXT_UPDATED` ledger event | `tests/skills/test_drift.py::test_regenerate_restores_and_logs` |
| 8 | Given drift When `walk skills check-drift --strict` Then exit 1 and report printed | `tests/cli/test_cmd_skills_drift.py::test_check_drift_strict_exits_one` |
| 9 | Given drift When `walk skills check-drift` Then exit 0 and `regenerated` message | `tests/cli/test_cmd_skills_drift.py::test_check_drift_regenerates_by_default` |
| 10 | Given drift and `strict=True` When `DefaultOrchestrator.start()` Then `ConfigError` before `ON_PROJECT_START` | `tests/skills/test_drift.py::test_startup_strict_fails_on_drift` |

#### Evidence required
- Quality gate output.
- Demo: `walk skills sync && walk skills check-drift` → `ok`; edit `.walk/projections/claude/.claude/skills/git-hygiene/SKILL.md`; `walk skills check-drift --strict` → `modified: git-hygiene`, exit 1.

#### Notes
- ADR-0007 D-3; Invariant 11; ARCHITECTURE §3.4 step 3.
- `NEW NAME:` `compute_drift`, `DefaultSkillRegistry.regenerate`, `KernelSettings.strict`; from implementation: `SkillProjector.scan`, `DefaultSkillRegistry(ledger=, clock=, project_key=)`, `DefaultOrchestrator(startup_checks=)`, `PROJECTIONS_DIR`, `skill_drift_reports`, `skills_check_drift`.
- Commit subject: `feat: add skill projection drift detection (E02-S07)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`):
```
362 files already formatted
All checks passed!
Success: no issues found in 360 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.84%
1131 passed, 3 deselected in 415.07s
```
Touched modules: `skills/drift.py`, `skills/protocols.py`, `orchestrator/service.py`, `cli/composition.py`, `cli/cmd_doctor.py`, `claude/projector.py` 100 %; `skills/service.py` 98 %; `cli/cmd_skills.py` 98 %; `codex/projector.py` 97 %.

Demo on the E02-S06 scratch repository (seeded with the test helper, because bootstrap is BLOCKED):
```
$ walk skills sync --repo <tmp>/game
projected 5 skills for 2 providers
$ walk skills check-drift --repo <tmp>/game
ok                                                       (exit 0)
$ echo "hand edit" >> .walk/projections/claude/.claude/skills/git-hygiene/SKILL.md
$ walk skills check-drift --strict --repo <tmp>/game
modified: git-hygiene (projection edited)                (exit 1)
$ walk skills check-drift --repo <tmp>/game
modified: git-hygiene (projection edited)
regenerated 1 projections                                (exit 0)
$ walk skills check-drift --strict --repo <tmp>/game
ok                                                       (exit 0)
```

Contract additions (INTERFACES / ARCHITECTURE updated in this commit):
- **`SkillProjector.scan(worktree_path) -> dict[str, str]`** maps each skill projected on disk to the sha256 of its content, as `project` hashes it. Behavior 1 needs Codex drift attributed to one sub-section, and `walk.skills` cannot parse a provider format (the Codex markers live in `model_router`, which `skills` may not import). Implemented for Claude (`SKILL.md` file bytes), Codex (the entry text inside the managed block; headings tolerate CRLF, so a converted section reads as *modified*, not *missing*) and `FakeSkillProjector`.
- **ARCHITECTURE §4.3** gains the write point `skills.SkillRegistry` (`DefaultSkillRegistry.regenerate`) → `CONTEXT_UPDATED` with payload `skills_drift`.
- `DefaultSkillRegistry` gets keyword-only `ledger`, `clock` and `project_key` (needed by `regenerate`).
- `DefaultOrchestrator` gets keyword-only `startup_checks`, awaited first in startup (before recovery, `PROJECT_STARTED` and `ON_PROJECT_START`). The composition root wires the drift check into it.
- Composition gains `PROJECTIONS_DIR` and `skill_drift_reports(repo)` (used by doctor).

Level-0 decisions:
- **`compute_drift` key convention.** `on_disk` keys are `<target_path>#<skill>`: the target file, anchored to the skill's projected content. Codex entries all share `AGENTS.md`, so a bare target path could not carry per-skill hashes (Behavior 1). Keys of skills found on disk but not locked carry an empty target (`#<name>`). They are orphaned when not canonical, and missing (no lock entry) when canonical. A modified entry that is also missing counts as missing only.
- `check_drift` runs `compute_drift` per projector over that provider's lock entries and merges the reports (sorted, de-duplicated). It never writes. It needs only `ai_root`, so doctor uses a registry without a database.
- **`regenerate`.** Per provider it re-projects the canonical skills already locked for that provider, plus `missing` and `modified`. Unchanged files are rewritten byte-identical; the Codex section is rebuilt whole, which removes orphaned sub-sections. An orphaned entry's own file is deleted. When it lies in a folder named after the skill (`.claude/skills/<name>/`), the folder goes too, including copied `references/`/`scripts/`. Orphaned lock entries of the regenerated providers are pruned. One `CONTEXT_UPDATED` (actor KERNEL) is written per `regenerate` call. On-disk orphans with no lock entry are reported but not deleted (their location is provider-specific).
- **Startup step 3.** One projector per provider that serves an enabled model (`router.adapter_for(...).skill_projector()`) is checked on `<repo>/.walk/projections/<provider>/`. `KernelSettings.strict=True` → `ConfigError("skill projections drift for <provider> (strict startup)")` before `PROJECT_STARTED`. Otherwise drift is regenerated, with one ledger event per drifted provider; a fresh repository therefore projects everything on first start. There is no `walk run --strict` flag (not in the Files table; E02-S15 owns strict mode in doctor).
- **`walk skills check-drift`** checks both kernel providers (claude, codex), like `sync`, in `--worktree` or the repo-level folders. The cause of a modification is re-derived from the lock: a lock entry whose `generated_from_sha256` differs from the canonical sha means `canonical changed`, otherwise `projection edited`. `regenerated N projections` counts the drift items regenerated (missing + modified + orphaned, per provider).
- **`walk doctor`** prints a `skills:` section with one line per provider: `ok` or `missing N, modified N, orphaned N`. A skills or lock error prints `skills: error: ...`. Neither changes the exit code, and `--json` output stays the manifest.
- Superseded test: `tests/skills/test_service.py::test_drift_names_its_story` (deferred-method check) is removed; `tests/skills/test_drift.py::test_check_drift_and_regenerate_require_wiring` replaces it.
- `tests/cli/test_cmd_work.py` `repo` fixture now runs `git init`. Its daemon test starts a kernel, and startup step 3 resolves `info/exclude` through git, so a kernel started outside a git repository now fails fast. A game repository is always a git repository (bootstrap and preflight require git).

---

### E02-S08 — Builtin MUST hooks (ARCHITECTURE §4.1 table)

**Status:** DONE (e6babf7)
**Type:** feat
**Requirements:** §32, §41, §22, §137
**Depends on:** E01-S07, E01-S28, E01-S16
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every MUST attachment of ARCHITECTURE §4.1 whose dependencies exist by E02 is registered as a `required=True` builtin hook with priority < 50 and cannot be disabled by project configuration. Each one fires in its trigger path without stopping the run whose task fired it and without repeating a checkpoint the kernel already took. Every other §4.1 attachment is listed in the deferral table with its owner.

#### Scope
- In: `walk.orchestrator.builtin_hooks` (`BuiltinHookDeps`, `builtin_hooks`, `register_builtins`, `MUST_HOOK_IDS`; ADR-0016); the default attachment `builtin.memory_index`; the hook execution rules (Behavior 3–4); payload fixes in `CheckpointManager` (`wip_commit_done`) and `RecoveryManager` (`checkpoint_id`, `handover_id` on `ON_MODEL_FALLBACK`); the executor guard against stopping a run from its own task; the deferral table.
- Out: ledger writes (done at §4.3 write points, WBS.md §3.5); project hooks (E02-S09); approval waiter, expiry and resume (E02-S11); firing `ON_PROJECT_PAUSE`/`ON_TASK_CANCELLED` from `walk pause`/`walk work cancel` (E02-S13); handovers on PAUSE/BUDGET (E04-S07); attachments in the deferral table.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/builtin_hooks.py` | create | `BuiltinHookDeps`, `builtin_hooks`, `register_builtins`, `MUST_HOOK_IDS` |
| `src/walk/orchestrator/__init__.py` | modify | re-export `BuiltinHookDeps`, `register_builtins` |
| `src/walk/cli/composition.py` | modify | — (builds `BuiltinHookDeps` and calls `register_builtins(hook_manager, deps)` once, after all services exist and before project hooks load; ADR-0016) |
| `src/walk/runtime/checkpoints.py` | modify | — (`ON_AGENT_CHECKPOINT` payload gains `wip_commit_done`) |
| `src/walk/runtime/recovery.py` | modify | — (`ON_MODEL_FALLBACK` payload gains `checkpoint_id`, `handover_id`) |
| `src/walk/runtime/executor.py` | modify | — (`pause`/`cancel` called from the run's own task raise `ConfigError` instead of awaiting that task; PARTIAL output: HANDOFF checkpoint before apply, run ends `HANDED_OVER`, owner decision option A) |
| `src/walk/runtime/output_applier.py` | modify | — (`apply(..., handoff: Checkpoint \| None = None)`: the HANDOFF checkpoint's ids go into the transition payload; owner decision option A) |
| `src/walk/runtime/protocols.py` | modify | — (`OutputApplier.apply` gains `handoff`; `AgentExecutor.pause/cancel` docstrings) |
| `src/walk/workflow/service.py` | modify | — (the transition payload builder forwards `checkpoint_id`/`handover_id` from `TransitionContext.payload` into the row hooks' payload; owner decision option A) |
| `docs/01-architecture/ARCHITECTURE.md` | modify | — (§4.1 `ON_AGENT_HANDOFF` row: the PARTIAL path) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.13 `AgentExecutor.pause/cancel`: the own-task `ConfigError`; PARTIAL path; `OutputApplier.apply(handoff=)`; `ON_AGENT_CHECKPOINT` payload; §1.3 forwarded hook keys; §5.3 recovery fallback payload) |
| `tests/hooks/test_builtins.py` | create | — |
| `tests/hooks/test_builtins_required.py` | create | — |
| `tests/hooks/test_builtins_pause_paths.py` | create | — (real executor with the builtins registered: budget exhaustion and protected-action approval inside a run) |
| `tests/runtime/test_executor.py` | modify | — (own-task guard) |
| `tests/runtime/test_recovery.py` | modify | — (fallback payload keys) |
| `tests/hooks/conftest.py` | create | — (runtime fixtures, `HoldingAdapter`, `make_builtin_env`) |
| `tests/runtime/executor_env.py` | modify | — (`approval_sleep` option, `builtin_deps` helper) |
| `tests/cli/test_cmd_work.py` | modify | — (the fixture repository gets an initial commit: `ON_TASK_START` now branches from `main`) |

#### Interface contract
```python
# src/walk/orchestrator/builtin_hooks.py  (ADR-0016)
class BuiltinHookDeps(WalkModel):
    """Protocol-typed service handles the builtin hooks call (arbitrary_types_allowed)."""

    hooks: HookManager  # nested fire ON_MODEL_FALLBACK → ON_AGENT_HANDOFF
    checkpoints: CheckpointManager
    memory: MemoryManager
    git: GitProvider
    executor: AgentExecutor
    permissions: PermissionManager
    telemetry: TelemetryManager
    workflow: WorkflowManager  # ON_TASK_START reads the work item (branch)
    runs: AgentRunRepository  # E02-S08 implementation: the run of an END/HANDOFF checkpoint
    default_branch: str  # Project.default_branch, base of ensure_branch


MUST_HOOK_IDS: tuple[str, ...]  # ids of the MUST table below, in table order


def builtin_hooks(
    deps: BuiltinHookDeps,
) -> list[tuple[Hook, Callable[[HookContext], Awaitable[None]]]]: ...
def register_builtins(manager: HookManager, deps: BuiltinHookDeps) -> None: ...
```
`BuiltinHookDeps` drops the ADR-0016 sketch's `budgets` field: budget facts arrive in the `ON_BUDGET_EXHAUSTED` payload. A later story adds it back when a hook needs it (E07-S02).

Registered MUST hooks (all `required=True`, `kind="builtin"`, `fail_policy=FAIL_CLOSED`, priority 10):

| HookName | id | Callable behaviour |
|---|---|---|
| `ON_PROJECT_PAUSE` | `builtin.pause_all_runs` | `executor.pause(run.id)` for every run in `executor.running()`. The executor cancels the adapter, writes the PAUSE checkpoint and sets `PAUSED_BY_USER`; the hook writes no checkpoint of its own |
| `ON_TASK_START` | `builtin.ensure_branch` | `item = workflow.get(ctx.work_item_id)`; `git.ensure_branch(branch_name_for(item), base=deps.default_branch, idempotency_key=f"git.branch:{item.id}")`. This is the key `SandboxManager.create` uses, so whichever runs first creates the branch |
| `ON_TASK_COMPLETE` | `builtin.remaining_work_check` | `memory.read(ctx.work_item_id)` (`DocumentNotFound` → no-op); section `Remaining Work` non-empty and not `- none` → `telemetry.counter("remaining_work_nonempty", work_item=<id>)` plus a WARNING log. Never fails; the §6.5 guard decides |
| `ON_AGENT_CHECKPOINT` | `builtin.wip_commit` | guard: `ctx.payload["wip_commit_done"] is True`, else `HookFailed` (the commit is made inside `CheckpointManager.checkpoint`) |
| `ON_AGENT_END` | `builtin.final_checkpoint` | no-op when `ctx.payload` carries `checkpoint_id` (the executor's END checkpoint, E01-S27 Behavior 10(b)); else `checkpoints.checkpoint(run, END)` |
| `ON_AGENT_HANDOFF` | `builtin.handoff_checkpoint_and_handover` | no-op when `ctx.payload` carries both `checkpoint_id` and `handover_id`; else `checkpoints.checkpoint(run, HANDOFF, handover=ctx.payload["handover"])` (which writes the handover document) |
| `ON_MODEL_FALLBACK` | `builtin.fallback_chain` | `hooks.fire(ON_AGENT_HANDOFF, ctx)` with the payload forwarded unchanged. Both callers (executor and `RecoveryManager`) send `checkpoint_id` + `handover_id`, so the chained handoff hook is a no-op and project hooks on `ON_AGENT_HANDOFF` still see the fallback |
| `ON_BUDGET_EXHAUSTED` | `builtin.budget_escalate` | only when `ctx.payload["hard_action"] == "BLOCK"`: `permissions.request_approval(<the budget payload>, kind="ESCALATION", approver=USER, requested_by=KERNEL, run_id=ctx.run_id, work_item_id=ctx.work_item_id)`, unless `permissions.pending(USER)` already holds an `ESCALATION` whose payload has the same `budget_id`. Never checkpoints and never stops a run |
| `ON_PROTECTED_ACTION_REQUESTED` | `builtin.approval_recorded` | guard: payload carries `approval_id` and `kind` (the request is persisted and `APPROVAL_REQUESTED` written before the hook fires). Never pauses: the requester does (Behavior 3) |
| `ON_TASK_CANCELLED` | `builtin.cancel_cleanup` | `executor.cancel(ctx.run_id, ctx.payload["reason"])` when `ctx.run_id` is in `executor.running()`, else no-op; the executor removes the worktree and keeps the branch |
| `ON_RECOVERY_RESUME` | `builtin.load_handover` | `mode == "handover"`: `ctx.payload["handover_id"]` must resolve via `memory.read_handover`; `mode == "native"`: `handover_id` may be `None` and nothing is read |

Default attachment registered here (not MUST): `ON_PROJECT_START` → `builtin.memory_index`, `required=False`, priority 60, `fail_policy=LOG_AND_CONTINUE`, `memory.rebuild_index()`.

§4.1 attachments not registered here, with the place that covers them:

| §4.1 attachment | Covered by |
|---|---|
| `ON_AGENT_START` → freshness check, may fire `ON_CONTEXT_STALE` | `ContextManager.build` runs its freshness probe and fires `ON_CONTEXT_STALE` before `ON_AGENT_START` fires (E01-S24). `MemoryManager.assess_freshness` arrives in E04-S03; until then it raises `ConfigError("implemented in E04-S03")`, so a FAIL_CLOSED hook calling it would fail every run with memory documents in context. The `ON_AGENT_START` builtin is registered by E04-S04 (its Behavior 1) |
| `ON_CONTEXT_UPDATED` → freshness stamp, index update | done inside `MemoryManager.write`, in the same transaction (E01-S16, WBS.md §3.5); a per-write `rebuild_index()` would repeat it. The counter builtin is E04-S04 |
| `ON_PHASE_START` → `PHASE_BASELINE` approved artifact | E07-S02. It needs `MemoryManager.approve_artifact` (E02-S12, which this story does not depend on) and the full manifest |
| `ON_STATE_TRANSITION` → `WorkProvider.transition` | E03-S03 |
| `ON_TASK_BLOCKED` → `WorkProvider.transition` + comment | E03-S03 |
| `ON_TASK_FAILED` → escalation | E03-S16 |
| `ON_READY_FOR_QC` → QC run with a different model | E03-S07 |
| `ON_BUG_CREATED` → `WorkProvider.create` + bug skeleton | E03-S14 / E04-S01 |
| `ON_COMMIT`/`ON_PR_OPENED`/`ON_MERGED` → `relevant_files` refresh | E04-S04 |
| `ON_BUILD_*`/`ON_TEST_RESULT` → evidence | E03-S11 |
| `ON_CONTEXT_STALE` → `requires_verification` | E04-S04 |
| `ON_DEBATE_*`, `ON_DECISION_RECORDED`, `ON_ESCALATION` | E04-S05 / E05 |
| `ON_PHASE_REVIEW_START`/`COMPLETE`/`GATE_DECISION` | E07 |
| `ON_IMPROVEMENT_OBSERVATION` | E04-S13 |
| `ON_EFFORT_CHANGE`, `ON_BUDGET_THRESHOLD`, `ON_TOOL_*` | ledger only → write points; nothing to register |

#### Behavior
1. `register_builtins` registers every MUST row and the default attachment; `MUST_HOOK_IDS` lists exactly the MUST ids; calling it twice raises `ConfigError("builtin hooks already registered")`.
2. Each callable receives `HookContext` and reads only documented payload keys; a missing key on the path that reads it raises `HookFailed` (FAIL_CLOSED) with the key name. `HookContext` is frozen: a hook never reports back through the payload.
3. Execution context (no self-wait). Hooks run synchronously in the task that fires them. `ON_BUDGET_EXHAUSTED` (after `BudgetManager.meter` commits, from the executor's metering and from `_end`), `ON_PROTECTED_ACTION_REQUESTED` (from `ToolInvoker.authorize`), `ON_AGENT_START/CHECKPOINT/END/HANDOFF` and `ON_MODEL_FALLBACK` fire inside a run's own task. Builtins on them never call `AgentExecutor.pause/cancel`; they record, verify or request, and the caller acts after `fire` returns:
   - budget: the executor's `_meter` raises `BudgetExhausted` and `_block_budget` cancels the adapter, takes the one PAUSE checkpoint and ends the run `BLOCKED_BUDGET` (or the router falls back, E01-S27);
   - approval: `ToolInvoker.authorize` sets `PAUSED_FOR_APPROVAL`, takes the PAUSE checkpoint and waits on the `ApprovalWaiter` while the run stays alive (E01-S26).
   `builtin.pause_all_runs` and `builtin.cancel_cleanup` do call the executor. They attach to `ON_PROJECT_PAUSE`/`ON_TASK_CANCELLED`, which only `Orchestrator.pause()` and `cancel_work_item()` (E02-S13) fire, from the command-consumer task. Defence in depth: `DefaultAgentExecutor.pause/cancel` raise `ConfigError("run <id> cannot stop itself from its own task")` when `asyncio.current_task()` is the run's task. A misplaced fire therefore fails closed instead of hanging.
4. No duplicate checkpoints (ARCHITECTURE §4.1). A builtin creates a checkpoint only on the END/HANDOFF path when the payload shows that none was taken. `pause_all_runs` and `cancel_cleanup` leave the PAUSE checkpoint to the executor; `budget_escalate` and `approval_recorded` create none. A no-op returns normally, so `HOOK_EXECUTED` (status OK) is recorded; the no-op path reads no key, so the rule 2 check applies only on the checkpointing path.
5. `builtin.pause_all_runs` continues through all running runs even if one pause fails, then raises `HookFailed` listing the failed run ids.
6. `builtin.ensure_branch` uses the ARCHITECTURE §5.4 key shared with `SandboxManager.create`, so a repeated `ON_TASK_START` (REWORK) and the sandbox are no-ops after the first call.
7. `builtin.budget_escalate` keeps at most one PENDING `ESCALATION` per `budget_id`. Hard actions `DOWNGRADE_EFFORT` and `FALLBACK_MODEL` are no-ops (the executor and router act on `BudgetExhausted`). The hook also escalates when the run has already ended (e.g. `EXECUTION_TIME_S` metered in `_end`), because the budget stays exhausted for the next run.
8. `request_approval` inside `budget_escalate` fires `ON_PROTECTED_ACTION_REQUESTED` after its unit of work commits; `approval_recorded` is a guard, so the chain ends there.
9. Hooks never write ledger events directly (WBS.md §3.5); `HookManager.fire` records `HOOK_EXECUTED`/`HOOK_FAILED`.
10. `HookManager.register(hook)` with `kind="project"` and `id` equal to a required builtin id, or `enabled=False` targeting a required id, raises `ConfigError` (enforced in E01-S07; re-tested here with the real builtin set).
11. `RecoveryManager` adds `checkpoint_id` (the latest checkpoint of the interrupted run, after the handover is ensured) and `handover_id` to its `ON_MODEL_FALLBACK` payload; the executor already sends both.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a kernel with fakes When `register_builtins` Then `hooks_for(name)` contains each `MUST_HOOK_IDS` entry with `required=True` and priority < 50, and the ids equal the MUST table | `tests/hooks/test_builtins.py::test_all_must_hooks_registered_required_low_priority` |
| 2 | Given registration done When inspecting `ON_PROJECT_START` Then `builtin.memory_index` is `required=False`, priority 60, `LOG_AND_CONTINUE` | `tests/hooks/test_builtins.py::test_memory_index_is_a_default_attachment` |
| 3 | Given registration done When `register_builtins` again Then `ConfigError` | `tests/hooks/test_builtins.py::test_register_builtins_twice_raises` |
| 4 | Given two running fake runs When `fire(ON_PROJECT_PAUSE)` from the test task Then both runs are `PAUSED_BY_USER` and exactly two `PAUSE` checkpoints exist | `tests/hooks/test_builtins.py::test_project_pause_pauses_all_running_runs` |
| 5 | Given a story entering IMPLEMENTING When `fire(ON_TASK_START)` twice Then the branch exists once and the second call is a no-op | `tests/hooks/test_builtins.py::test_task_start_ensures_branch_idempotently` |
| 6 | Given a fallback payload with `handover` but no ids When `fire(ON_MODEL_FALLBACK)` Then a `HANDOFF` checkpoint and `HO-0001.md` exist | `tests/hooks/test_builtins.py::test_model_fallback_chains_handoff_checkpoint_and_handover` |
| 7 | Given `fire(ON_AGENT_HANDOFF)` without `handover` and without ids Then `HookFailed` naming `handover` | `tests/hooks/test_builtins.py::test_handoff_without_handover_fails_closed` |
| 8 | Given a fake run whose usage exhausts a `BLOCK` budget When the real executor runs it with the builtins registered Then within 5 s the run is `BLOCKED_BUDGET`, the run has exactly one `PAUSE` checkpoint, exactly one pending `ApprovalRequest(kind=ESCALATION, approver=USER)` exists and `builtin.approval_recorded` ran once with `OK` | `tests/hooks/test_builtins_pause_paths.py::test_budget_exhausted_blocks_once_and_escalates_without_deadlock` |
| 9 | Given a fake run requesting a tool that requires approval When the real executor runs it with the builtins registered Then within 5 s the run is `PAUSED_FOR_APPROVAL` with one `PAUSE` checkpoint, its task is still alive and `builtin.approval_recorded` ran with `OK` | `tests/hooks/test_builtins_pause_paths.py::test_protected_action_pause_is_done_by_the_tool_invoker` |
| 10 | Given `ON_BUDGET_EXHAUSTED` with `hard_action` `FALLBACK_MODEL` When fired Then no approval request exists | `tests/hooks/test_builtins.py::test_budget_exhausted_non_block_does_not_escalate` |
| 11 | Given `ON_BUDGET_EXHAUSTED` for the same `BLOCK` budget fired twice Then exactly one pending `ESCALATION` exists | `tests/hooks/test_builtins.py::test_budget_escalation_is_once_per_budget` |
| 12 | Given a running run When its own task calls `executor.pause(run_id)` Then `ConfigError` is raised at once and the run is not left waiting on itself | `tests/runtime/test_executor.py::test_pause_from_the_runs_own_task_raises` |
| 13 | Given recovery that switches model When `ON_MODEL_FALLBACK` fires Then the payload has `checkpoint_id` and `handover_id`, and the chained handoff hook creates no checkpoint | `tests/runtime/test_recovery.py::test_recovery_fallback_payload_carries_checkpoint_and_handover` |
| 14 | Given `ON_RECOVERY_RESUME` with `mode=native` and `handover_id=None` Then `OK`; with `mode=handover` and `handover_id=None` Then `HookFailed` | `tests/hooks/test_builtins.py::test_load_handover_accepts_native_resume_without_handover` |
| 15 | Given a feature document whose `Remaining Work` lists an item When `fire(ON_TASK_COMPLETE)` Then counter `remaining_work_nonempty` is 1 and the result is `OK`; given no document Then `OK` | `tests/hooks/test_builtins.py::test_task_complete_counts_remaining_work_without_failing` |
| 16 | Given `ON_TASK_CANCELLED` for a running run Then it is `CANCELLED` with its worktree removed; for a run id not running Then `OK` and nothing changes | `tests/hooks/test_builtins.py::test_task_cancelled_cancels_running_run_only` |
| 17 | Given `ON_AGENT_CHECKPOINT` with `wip_commit_done=False` Then `HookFailed`; with `True` Then `OK` | `tests/hooks/test_builtins.py::test_wip_commit_guard` |
| 18 | Given project hook with id `builtin.final_checkpoint` and `enabled=False` When `register` Then `ConfigError` | `tests/hooks/test_builtins_required.py::test_project_cannot_disable_required_builtin` |
| 19 | Given `fire(ON_AGENT_END)` without `checkpoint_id` Then exactly one `END` checkpoint and no direct ledger write by the hook (ledger count unchanged except `HOOK_EXECUTED`, `CHECKPOINT_CREATED`) | `tests/hooks/test_builtins_required.py::test_hooks_do_not_duplicate_ledger_events` |
| 20 | Given an `ON_AGENT_END` payload with `checkpoint_id` and an `ON_MODEL_FALLBACK` payload with `checkpoint_id` and `handover_id` When both are fired Then no new checkpoint row and no new `.ai/handovers/` document exist, `ON_AGENT_HANDOFF` was fired once, and all three builtin executions are `OK` | `tests/hooks/test_builtins_required.py::test_checkpoint_hooks_noop_when_executor_already_checkpointed` |
| 21 | Given a fake IMPLEMENT run whose output is PARTIAL When the real executor runs it with the builtins registered Then the run ends `HANDED_OVER` (`AGENT_RUN_ENDED` outcome `OK`, status `PARTIAL`, not FAILED), the item took the `partial` transition (IMPLEMENTING), the `partial` row's `ON_AGENT_HANDOFF` saw `checkpoint_id` + `handover_id`, the builtin handoff hook ran `OK` without a second checkpoint, and `HO-0001.md` exists with the output's `remaining_work` (owner decision, option A) | `tests/hooks/test_builtins_pause_paths.py::test_partial_implement_run_hands_over_without_failing` |

#### Evidence required
- Quality gate output.
- Demo: `walk run --once` on a bootstrapped repo then `walk ledger query --kind HOOK_EXECUTED --limit 5` → shows `builtin.memory_index` under `ON_PROJECT_START`.

#### Notes
- **Owner decision 2026-10-07 (unblocks this story): option A.** Before applying a PARTIAL output, the executor takes a HANDOFF checkpoint that builds and writes the handover document (`HO-xxxx.md`, via the existing E01-S28 handover path); the workflow's `partial` transition then fires its hooks with payload `{from, to, event, checkpoint_id, handover_id}`. `builtin.handoff_checkpoint_and_handover` sees both ids and is a no-op (rule from E01-R01/B05), so it stays fail-closed for any transition that arrives without them. Add `src/walk/runtime/executor.py` and the workflow transition payload builder to the Files table as `modify`, update INTERFACES §5.3 and ARCHITECTURE §4.1, and add one AC: a PARTIAL implement run ends `HANDED_OVER`/`PARTIAL` (not FAILED), the item reaches the `partial` target state, and the handover document exists with `remaining_work`. Options B and C are rejected.
- Binding (E01-R01 planner note): E01 checkpoints never send `wip_commit_done`. This story adds it: `CheckpointManager.checkpoint` puts `wip_commit_done: bool` (True when the WIP commit was created or there was nothing to commit) into the `ON_AGENT_CHECKPOINT` payload. `builtin.wip_commit` stays fail-closed on `False` and treats a missing key as a contract error raised during development tests, never as a silent pass.
- ARCHITECTURE §4.1 (table and execution rule), §4.3; ADR-0009 D-7; ADR-0016 (module placement and single registration call site); WBS.md §3.5.
- `NEW NAME:` `BuiltinHookDeps` (incl. `hooks`, `workflow`, `default_branch`), `builtin_hooks`, `MUST_HOOK_IDS`, builtin hook ids (`builtin.*`, incl. `builtin.pause_all_runs`, `builtin.budget_escalate`, `builtin.approval_recorded`), payload keys `context_doc_ids`, `wip_commit_done`, `handover`, `handover_id`, `checkpoint_id`, `reason`, `mode`, counter `remaining_work_nonempty`.
- Pitfall: `ON_MODEL_FALLBACK → ON_AGENT_HANDOFF` and `ON_BUDGET_EXHAUSTED → ON_PROTECTED_ACTION_REQUESTED` are nested `fire`s; `HookManager.fire` must stay re-entrant (no shared mutable state).
- Pitfall: AC 8 and AC 9 guard against deadlock. Wrap each in `asyncio.wait_for(..., 5)` so a regression fails the test instead of hanging the suite.
- Resolved block (architect, 2026-10-07). The implementer's BLOCKING note is settled as follows:
  - `budget_block` and `pause_for_approval` called `executor.pause` from inside the run's own task (a deadlock) and repeated E01's PAUSE checkpoint. They are replaced by `builtin.budget_escalate` (requests only the ESCALATION approval) and `builtin.approval_recorded` (a guard). The executor and the tool invoker keep the pause, which they already perform (Behavior 3).
  - The old AC 7, which expected a hook-made checkpoint, is now AC 8: one PAUSE checkpoint, made by the executor.
  - `executor.pause/cancel` now fail fast on self-wait (AC 12).
  - (a) The freshness hook is deferred to E04-S04, because `ContextManager.build` already fires `ON_CONTEXT_STALE`.
  - (b) The recovery fallback payload carries both ids (AC 13).
  - (c) `load_handover` accepts native resume (AC 14).
  - (d) `builtin.index_update` is dropped: `write()` already updates the index.
  - (e) `builtin.memory_index` is a default attachment with its own AC 2.
  - Two further fixes from the review:
    - the `ON_PHASE_START` baseline needs `approve_artifact` (E02-S12, not a dependency), so it is deferred to E07-S02;
    - `remaining_work_check` can no longer set a payload flag (`HookContext` is frozen), so it counts and logs instead.
  - `ON_PROJECT_PAUSE` now pauses each run through the executor rather than checkpointing runs that keep running.
- **RESOLVED by the owner decision above (option A, implemented).** Former BLOCKING note (implementer, 2026-10-07, second pass): **the story workflow's `partial` row fires `ON_AGENT_HANDOFF` with a payload that `builtin.handoff_checkpoint_and_handover` must reject, so registering the builtin as specified fails every PARTIAL IMPLEMENT run.**
  - **Path, checked against the code.**
    - `story_workflow.yaml` row `IMPLEMENTING --partial--> IMPLEMENTING` lists `hooks: [on_agent_handoff]`; TASK items use the same table.
    - `DefaultOutputApplier.apply` raises `partial` for a PARTIAL IMPLEMENT output, from inside the run's own task (`DefaultAgentExecutor._complete`, after the END checkpoint).
    - `DefaultWorkflowManager` fires the row's hooks from `uow.after_commit` with the payload `{from, to, event}` only (`workflow/service.py`). `TransitionContext.payload` (`handover_present`, ...) is not forwarded, and the hook payload has no `handover`, `checkpoint_id` or `handover_id`.
    - With no ids, the builtin needs `ctx.payload["handover"]`, which is absent, so it raises `HookFailed`. That is exactly AC 7 ("without `handover` and without ids → `HookFailed`") and the Binding note ("a missing key is a contract error, never a silent pass").
    - `HookFailed` propagates out of the after-commit callback and out of `apply`. `_complete` catches only `GuardRejected`, so `_drive` → `_fail_safely` ends the run **FAILED**. The item's `partial` transition has already committed, so the item stays IMPLEMENTING with a failed run.
    - Today (no builtin) the run completes, but the PARTIAL `output.handover` is never written as a handover document: the END checkpoint takes no handover, and nothing else writes it. The story does not cover this firing site: the deferral table and Behavior 3–4 discuss only executor and recovery handoffs.
  - **Decision needed (architect).** It changes a hook/transition contract across `workflow`, `runtime` and possibly a versioned workflow table, so it is not Level 0. Options:
    - (A, proposed) On a PARTIAL IMPLEMENT output, the executor takes a `HANDOFF` checkpoint with `output.handover` before `apply`, like `_fall_back`, instead of (or before) the END checkpoint. It passes `checkpoint_id`/`handover_id` in `TransitionContext.payload`, and `DefaultWorkflowManager` forwards those keys into the row hooks' payload. The builtin is then a no-op there, project hooks see the handoff, and the PARTIAL handover is persisted. Files: `runtime/executor.py` (already listed), `workflow/service.py`, INTERFACES §1.3/§1.13, a PARTIAL executor test.
    - (B) Remove `on_agent_handoff` from the `partial` row: a table change, so `story_workflow` 1.0 → 1.1 and an E02-S04 pin bump. The executor then fires `ON_AGENT_HANDOFF` itself with both ids on the PARTIAL path, and the PARTIAL handover is persisted as in (A).
    - (C, not recommended) Make the builtin a no-op when the payload carries `event` (transition-fired). It contradicts AC 7 and the Binding note, and it hides the lost handover.
  - **Verified as specified, ready once this is settled:**
    - `ON_TASK_START` (`start_implementation`/`start_fix`/`rework_planned` rows, scheduler task): `ensure_branch` with the shared `git.branch:<id>` key.
    - `ON_TASK_COMPLETE` rows: `remaining_work_check` never fails.
    - `ON_TASK_CANCELLED` (feature `cancel` row, `run_id=None`): a no-op.
    - `ON_BUDGET_EXHAUSTED` payload carries `budget_id` and `hard_action` (`budgets/service.py`).
    - The executor's `ON_MODEL_FALLBACK` payload carries `checkpoint_id` and `handover_id`, and its `ON_AGENT_END` payload carries `checkpoint_id`.
    - `RecoveryManager` lacks both ids on `ON_MODEL_FALLBACK`; this story adds them.
    - `ON_RECOVERY_RESUME` carries `mode` and `handover_id`.
  - No E02-S08 code was committed.
- Commit subject: `feat: register builtin must hooks (E02-S08)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12):
```
383 files already formatted
All checks passed!
Success: no issues found in 382 source files
Contracts: 21 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.85%
1230 passed, 5 deselected in 475.14s (0:07:55)
```
Touched modules: `orchestrator/builtin_hooks.py` 100 %, `runtime/checkpoints.py` 100 %, `runtime/output_applier.py` 100 %, `workflow/service.py` 100 %, `runtime/executor.py` 99 % and `runtime/recovery.py` 97 % (the uncovered lines are pre-existing E01 defensive branches). All 21 acceptance tests pass, plus negative paths: `ON_TASK_START` without a work item, `ON_BUDGET_EXHAUSTED` without `hard_action`, `ON_PROTECTED_ACTION_REQUESTED` without `approval_id`, an unknown or missing handover on `ON_RECOVERY_RESUME`, an unknown recovery mode, a handoff for an unknown run, an unreadable feature document on `ON_TASK_COMPLETE`, and a pause failure for one of two runs (Behavior 5: the other run is still paused, the failed id is reported).

Demo on a temporary repository outside this repository (`git init`, one empty commit, `GDD/game.md`):
```
$ walk --repo <tmp>/game bootstrap --provider local --key DEMO --name Demo --yes
created:
  ...
exit=0
$ walk --repo <tmp>/game run --once
started 0 run(s)
exit=0
$ walk --repo <tmp>/game ledger query --kind HOOK_EXECUTED --limit 5
seq  at                                kind           actor   item  run  outcome
5    2026-10-06T23:58:05.191725+00:00  HOOK_EXECUTED  KERNEL             OK
$ walk --repo <tmp>/game ledger query --kind HOOK_EXECUTED --limit 5 --json   (payload of seq 5)
  "payload": {"hook_name": "on_project_start", "hook_id": "builtin.memory_index",
              "kind": "builtin", "status": "OK", "fail_policy": "log_and_continue", "message": ""}
```
`walk run --once` also logs `skipping unparsable memory document` for documents under `.ai/` that `rebuild_index` does not skip (for example the role constitutions in `.ai/agents/roles/`). This is E01-S16 behaviour, not a failure, and is left for the owner.

Decisions and contract changes (owner decision option A, plus small additive fixes):
- **PARTIAL output (option A).** `_complete` takes a `HANDOFF` checkpoint instead of the `END` checkpoint for every PARTIAL output; `AgentOutput` validation guarantees a handover. The handover is built by `build_handover(run, "PARTIAL", output)`, so `remaining_work`, `next_action`, hypotheses and risks come from the output's own handover. The output is then applied with `OutputApplier.apply(..., handoff=<checkpoint>)` (new optional keyword), which adds `checkpoint_id`/`handover_id` to the `TransitionContext.payload`. `DefaultWorkflowManager` forwards exactly these two keys into the row hooks' payload (`{from, to, event, checkpoint_id, handover_id}`), so `builtin.handoff_checkpoint_and_handover` is a no-op on the `partial` row and stays fail-closed everywhere else.
- **PARTIAL run end state.** The run ends `HANDED_OVER` with `AGENT_RUN_ENDED` outcome `OK` and payload `status: PARTIAL`. Outcome `OK` keeps it out of the `failed_handoffs` metric. Like every `HANDED_OVER` run (E01-B01), it keeps its worktree, which the item's next parentless run adopts. The handover stays open; the scheduler's existing `latest_open_handover` / `close_handover` step hands it to the next run. `ON_AGENT_END` still fires with the HANDOFF `checkpoint_id`, so `builtin.final_checkpoint` is a no-op.
- **`BuiltinHookDeps.runs`.** This is an additive field (`AgentRunRepository`) that the story contract did not list. `builtin.final_checkpoint` and `builtin.handoff_checkpoint_and_handover` must load the `AgentRun` for `CheckpointManager.checkpoint`, and no protocol method returns a run by id. It is recorded in the interface contract above and in NAME-REGISTER. All fields are `SkipValidation[...]` because the protocols are not runtime-checkable.
- **`wip_commit_done`.** It is `True` once `commit_all` returned, either with a WIP commit or with nothing staged. Defining it as "tree clean after the commit" was rejected: files excluded by `FORBIDDEN_COMMIT_PATHSPECS` (e.g. `*.env`, `.walk/**` in a repository that does not ignore it) would leave the tree dirty and fail every checkpoint. The guard therefore catches a checkpoint path that skipped the commit step or omitted the key.
- **Own-task guard.** `DefaultAgentExecutor._stopping` raises `ConfigError("run <id> cannot stop itself from its own task")` when `asyncio.current_task()` is the run's task. This covers both `pause` and `cancel`, before any state change.
- **Recovery payload.** `MODEL_FALLBACK` (ledger) and `ON_MODEL_FALLBACK` (hook) share one payload, which now carries `checkpoint_id` (the interrupted run's latest checkpoint after the handover is ensured) and `handover_id`. The existing recovery test assertion was updated.
- **`register_builtins` twice.** The check is done before anything is registered, so a second call leaves the manager unchanged and raises `ConfigError("builtin hooks already registered")`.
- **`builtin.remaining_work_check`** is a no-op without a work item id or when the document is missing. An unreadable document is logged and is also a no-op ("never fails"). `- none` (case-insensitive) counts as cleared.
- **Files outside the original table** (listed in the Files table above and the commit body): `runtime/output_applier.py`, `runtime/protocols.py` and `workflow/service.py` (option A transport); `docs/01-architecture/ARCHITECTURE.md` §4.1; and test support (`tests/hooks/conftest.py` with a `HoldingAdapter`, `tests/runtime/executor_env.py`, `tests/cli/test_cmd_work.py`). The `test_cmd_work.py` fixture repository had no commit, so the new `ON_TASK_START` builtin could not branch from `main`. It now has an initial empty commit, like every real game repository.

---

### E02-S09 — Project hooks from `.ai/agents/hooks.yaml`

**Status:** DONE (340ea67)
**Type:** feat
**Requirements:** §32, §24, §137
**Depends on:** E02-S08
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Projects declare additional hooks in `.ai/agents/hooks.yaml` as shell commands or allowlisted kernel actions; they run with timeouts and fail policies, receive the `HookContext` through `WALK_HOOK_*` environment variables, and can never replace or disable required builtins.

#### Scope
- In: YAML schema, `load_project_hooks`, shell execution, kernel-action dispatch, timeout handling, startup loading (ARCHITECTURE §3.4 step 3).
- Out: builtin hooks (E02-S08); improvement-related kernel actions (E10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/hooks/project.py` | create | `ProjectHooksFile`, `ProjectHookSpec`, `KERNEL_ACTIONS`, `HOOK_ENV_PREFIX`, `hook_env` |
| `src/walk/hooks/service.py` | modify | `DefaultHookManager.load_project_hooks`, `DefaultHookManager.set_kernel_actions` |
| `src/walk/hooks/__init__.py` | modify | re-export `ProjectHooksFile` |
| `src/walk/cli/composition.py` | modify | — (loads project hooks after builtins; registers kernel actions) |
| `tests/hooks/test_project_hooks.py` | create | — |
| `tests/hooks/test_project_hooks_exec.py` | create | — |

#### Interface contract
See INTERFACES.md §1.11 `HookManager.load_project_hooks`, `HookManager.fire`; DOMAIN-MODEL §4.6 `Hook`.
```python
# src/walk/hooks/project.py
HOOK_ENV_PREFIX = "WALK_HOOK_"
KERNEL_ACTIONS: tuple[str, ...] = ("memory.rebuild_index", "skills.sync", "telemetry.counter")


class ProjectHookSpec(WalkModel):
    name: HookName
    id: str = Field(pattern=r"^project\.[a-z0-9-]+$")
    command: str | None = None
    kernel_action: str | None = None
    priority: int = Field(default=100, ge=50)
    fail_policy: HookFailPolicy = HookFailPolicy.LOG_AND_CONTINUE
    timeout_s: int = Field(default=120, ge=1, le=3600)
    enabled: bool = True
    # exactly one of command / kernel_action (model_validator)


class ProjectHooksFile(WalkModel):
    hooks: list[ProjectHookSpec] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "ProjectHooksFile": ...
    def to_hooks(self) -> list[Hook]: ...


def hook_env(ctx: HookContext, base_env: Mapping[str, str]) -> dict[str, str]:
    """base_env + WALK_HOOK_NAME, WALK_HOOK_PROJECT_KEY, WALK_HOOK_WORK_ITEM_ID, WALK_HOOK_RUN_ID, WALK_HOOK_PHASE_ID,
    WALK_HOOK_ROLE, WALK_HOOK_AT, WALK_HOOK_PAYLOAD (JSON)."""


class DefaultHookManager:
    def set_kernel_actions(
        self, actions: Mapping[str, Callable[[HookContext], Awaitable[None]]]
    ) -> None: ...
```

#### Behavior
1. `load_project_hooks(path)` returns `[]` when the file is absent; invalid YAML or schema → `ConfigError` with the offending hook `id`.
2. `priority < 50` or `id` not starting with `project.` → validation error → `ConfigError` (project hooks always run after builtins).
3. `kernel_action` not in `KERNEL_ACTIONS` → `ConfigError("unknown kernel action")`.
4. Shell hooks run through `SubprocessRunner` with `cwd = repo root`, env from `hook_env(ctx, scrubbed_env(os.environ))` (no secrets), `timeout_s`; exit 0 → `OK`; non-zero → `FAILED` (message = last stderr line); timeout → `TIMEOUT`.
5. `FAIL_CLOSED` project hooks raise `HookFailed` after recording; `LOG_AND_CONTINUE` record and continue (E01-S07 semantics confirmed with project hooks).
6. `enabled: false` disables a project hook; targeting a builtin id is rejected (E02-S08 rule 7).
7. `telemetry.counter` action increments counter `hook.<id>`; `memory.rebuild_index` and `skills.sync` call the respective services.
8. Composition loads `.ai/agents/hooks.yaml` after `register_builtins`; registration order does not affect execution order (priority sort).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given valid `hooks.yaml` with one command hook When `load_project_hooks` Then one `Hook(kind="project")` | `tests/hooks/test_project_hooks.py::test_load_valid_file` |
| 2 | Given missing file When `load_project_hooks` Then `[]` | `tests/hooks/test_project_hooks.py::test_load_missing_file_returns_empty` |
| 3 | Given hook with both `command` and `kernel_action` When load Then `ConfigError` | `tests/hooks/test_project_hooks.py::test_load_rejects_command_and_action_together` |
| 4 | Given `priority: 10` When load Then `ConfigError` | `tests/hooks/test_project_hooks.py::test_load_rejects_priority_below_fifty` |
| 5 | Given `kernel_action: foo.bar` When load Then `ConfigError` | `tests/hooks/test_project_hooks.py::test_load_rejects_unknown_kernel_action` |
| 6 | Given command hook and fake runner exit 0 When `fire` Then result `OK` and env contains `WALK_HOOK_NAME` and no `JIRA_API_TOKEN` | `tests/hooks/test_project_hooks_exec.py::test_command_hook_runs_with_context_env` |
| 7 | Given command hook exceeding timeout When `fire` Then `TIMEOUT` and `HOOK_FAILED` ledger | `tests/hooks/test_project_hooks_exec.py::test_command_hook_timeout` |
| 8 | Given `fail_policy: fail_closed` and exit 1 When `fire` Then `HookFailed` | `tests/hooks/test_project_hooks_exec.py::test_fail_closed_project_hook_raises` |
| 9 | Given `kernel_action: telemetry.counter` When `fire` Then counter `hook.project.x` incremented | `tests/hooks/test_project_hooks_exec.py::test_kernel_action_counter` |

#### Evidence required
- Quality gate output.
- Demo: add `hooks: [{name: on_project_start, id: project.echo, command: "echo hello"}]`; `walk run --once`; `walk ledger query --kind HOOK_EXECUTED` shows `project.echo`.

#### Notes
- ADR-0009 D-7; ARCHITECTURE §4.1 failure policy paragraph.
- `NEW NAME:` `ProjectHooksFile`, `ProjectHookSpec`, `KERNEL_ACTIONS`, `HOOK_ENV_PREFIX`, `hook_env`, `set_kernel_actions`.
- Commit subject: `feat: load project hooks from hooks.yaml (E02-S09)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12):
```
386 files already formatted
All checks passed!
Success: no issues found in 385 source files
Contracts: 21 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.85%
1255 passed, 5 deselected in 483.00s (0:08:03)
```
Touched modules: `hooks/project.py` 100 %, `hooks/service.py` 100 %, `cli/composition.py` 100 %. All 9 acceptance tests pass, plus negative paths: a hook with neither command nor action, invalid YAML, a non-mapping file, `hooks` not a list, unknown top-level keys, a `builtin.*` id, `timeout_s: 0`, an unknown hook name, a non-mapping hook entry, a duplicate id, a disabled hook (registered, not run), a kernel action that is not wired, `set_kernel_actions` with an unknown name, a command hook on a manager without a runner, and a `LOG_AND_CONTINUE` failure followed by the next hook. The composition-root tests check that `JIRA_API_TOKEN` from the kernel environment never reaches a hook command, and that all three kernel actions are wired.

Demo on the E02-S08 demo repository (outside this repository), Windows host, real shell:
```
$ cat .ai/agents/hooks.yaml
hooks: [{name: on_project_start, id: project.echo, command: "echo hello"}]
$ walk --repo <tmp>/game run --once
started 0 run(s)
exit=0
$ walk --repo <tmp>/game ledger query --kind HOOK_EXECUTED --json   (seq, hook_id, status)
5   builtin.memory_index  OK
7   builtin.memory_index  OK
9   builtin.memory_index  OK
10  project.echo          OK
```

Decisions (Level 0, recorded for the owner):
- **Command runner injection.** `walk.hooks` may not import `walk.integrations` (ARCHITECTURE §2.2) or call `asyncio.create_subprocess_exec` (TID251). `DefaultHookManager` therefore gains three keyword-only constructor arguments: `command_runner`, `cwd` and `base_env`. The runner is typed by a private structural protocol that matches `SubprocessRunner`. The composition root passes the kernel's runner, the repository root and `scrubbed_env(os.environ)`, so project commands get the agent allowlist and never secrets. Without a runner, a command hook fails by its policy (`no command runner`).
- **Shell.** A `command` is a shell command line, run as `%COMSPEC% /d /s /c <command>` on Windows (COMSPEC from the scrubbed environment, default `cmd.exe`) and as `/bin/sh -c <command>` elsewhere.
- **Failure message and timeout.** A non-zero exit is `FAILED`, with the last non-empty stderr line as its message (or `exit code N` when stderr is empty). The runner's `Timeout` and the manager's own deadline both record `TIMEOUT`.
- **Kernel actions.** An action receives the hook's context with `payload["hook_id"]` set to the project hook's id; this is how `telemetry.counter` names `hook.<id>`. The actions are built in the composition root (`_kernel_actions`). `skills.sync` does what `walk skills sync` does without `--worktree`: it projects all skills into `.walk/projections/<provider>` and rewrites the lock. `load_project_hooks` validates the whole file before it registers anything, then registers and returns the hooks.
- **Obsolete test.** The E01-S07 stub test `tests/hooks/test_service.py::test_load_project_hooks_not_supported_yet` asserted the "available from E02-S09" error, so it was removed; it is named in the commit body. `src/walk/hooks/protocols.py` (docstring) and `INTERFACES.md` §1.11 were updated.

---

### E02-S10 — Permission defaults, `permissions.yaml` loader, protected actions

**Status:** DONE (pending)
**Type:** feat
**Requirements:** §31, §92, §91, §63, §137
**Depends on:** E01-S15, E02-S03
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The kernel ships the ADR-0006 D-6 rule set in `defaults.yaml`; projects may only narrow it through `.ai/agents/permissions.yaml`; protected actions always evaluate to `REQUIRE_APPROVAL(approver=USER)` and cannot be downgraded.

#### Scope
- In: defaults file, loader + narrowing merge, `ProtectedAction` defaults, `decide()` protected-action branch, default command patterns.
- Out: approval lifecycle (E02-S11); worktree path checks and guard hooks (E02-S14).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/permissions/defaults.yaml` | create | — |
| `src/walk/permissions/loader.py` | create | `PermissionsFile`, `load_defaults`, `load_project_rules`, `merge_narrowing`, `DEFAULT_PROTECTED_ACTIONS` |
| `src/walk/permissions/service.py` | modify | `DefaultPermissionManager.__init__(rules, protected_actions, …)`, protected-action branch in `decide` |
| `src/walk/permissions/__init__.py` | modify | re-export loader symbols |
| `src/walk/cli/composition.py` | modify | — (loads defaults + project file) |
| `tests/permissions/test_loader.py` | create | — |
| `tests/permissions/test_defaults_rules.py` | create | — |
| `tests/permissions/test_protected_actions.py` | create | — |

#### Interface contract
See INTERFACES.md §1.10 `PermissionManager`; DOMAIN-MODEL §4.5 `PermissionRule`, `ProtectedAction`.
```python
# src/walk/permissions/loader.py
class PermissionsFile(WalkModel):
    rules: list[PermissionRule] = Field(default_factory=list)
    protected_actions: list[ProtectedAction] = Field(
        default_factory=list
    )  # project may ADD, never remove


DEFAULT_PROTECTED_ACTIONS: tuple[str, ...] = (
    "git.merge_protected",
    "git.delete_branch_protected",
    "repo.delete_data",
    "store.publish",
    "credentials.change",
    "monetization.change",
    "jira.delete",
    "permissions.alter",
)


def load_defaults() -> PermissionsFile: ...  # package resource defaults.yaml
def load_project_rules(path: Path) -> PermissionsFile: ...  # [] when absent
def merge_narrowing(defaults: PermissionsFile, project: PermissionsFile) -> PermissionsFile:
    """Project rule with effect DENY/REQUIRE_APPROVAL: added. Project rule with effect ALLOW: accepted only if an identical
    (role, tool) ALLOW exists in defaults (acts as a restatement, may remove command/path patterns = narrowing) — otherwise ConfigError.
    Project protected_actions appended; any default protected action missing from the merged list → ConfigError."""
```
`defaults.yaml` rows (effect per role; `*` = all roles):

| role | tool | effect | notes |
|---|---|---|---|
| SENIOR_DEV | `Read`,`Edit`,`Write`,`Glob`,`Grep` | ALLOW | `path_patterns: ["**"]` (worktree-relative) |
| SENIOR_DEV | `bash` | ALLOW | `command_patterns`: `^(dotnet|unity|Unity|graphify|git (status|diff|log|add|stash)|pytest|npm test|ls|cat|rg|grep|find)\b` |
| SENIOR_DEV | `git.commit` | ALLOW | kernel executes |
| SENIOR_DEV | `git.merge_protected`,`git.push_protected`,`jira.close_feature`,`review.approve`,`review.reject`,`qc.*` | DENY | |
| LEAD_DEV | as SENIOR_DEV ALLOW rows + `review.approve`,`review.reject`,`jira.create_task` | ALLOW | |
| LEAD_DEV | `jira.close_feature` | DENY | QC only |
| LEAD_DEV | `git.merge_protected` | REQUIRE_APPROVAL | approver USER |
| QC | `Read`,`Glob`,`Grep` | ALLOW | |
| QC | `bash` | ALLOW | test/run patterns only: `^(dotnet test|unity|Unity|pytest|npm test|ls|cat|rg|grep|find)\b` |
| QC | `jira.create_bug`,`jira.reopen`,`qc.approve`,`qc.reject` | ALLOW | |
| QC | `Edit`,`Write`,`git.commit` | DENY | QC does not fix code |
| ORCHESTRATOR | `jira.create_*`,`jira.transition`,`work.plan`,`Read`,`Glob`,`Grep` | ALLOW | |
| ORCHESTRATOR | `Edit`,`Write`,`bash` | DENY | |
| PRODUCT_OWNER, DESIGN_LEADER, ART_DIRECTOR | `Read`,`Glob`,`Grep`,`decision.propose` | ALLOW | |
| same | `Edit`,`Write`,`bash` | DENY | |
| `*` | `bash` | DENY | `command_patterns`: `rm\s+-rf\s+/`, `git\s+push\s+.*--force`, `\bcurl\b`, `\bwget\b`, `^(pip|uv|npm|dotnet)\s+(install|add)\b`, `git\s+merge\b` |
| `*` | each `DEFAULT_PROTECTED_ACTIONS` entry | REQUIRE_APPROVAL | approver USER |

#### Behavior
1. `load_defaults()` validates the shipped file at import of the service; a malformed default is a packaging error surfaced as `ConfigError` at startup.
2. `merge_narrowing` applies the rules in its docstring; the result is de-duplicated on `(role, tool, effect, command_patterns, path_patterns)`.
3. `decide()` first checks `request.tool` (or `ToolSpec.protected_action` resolved by the caller into `request.tool`) against protected actions → `REQUIRE_APPROVAL(approver=action.approver, reason="protected action")` regardless of any ALLOW rule; then applies E01-S15 specificity/DENY-wins evaluation.
4. A project rule attempting `effect: ALLOW` for a protected action → `ConfigError("protected action cannot be downgraded")`.
5. Bash `DENY` patterns for `*` apply to every role in addition to role ALLOW patterns (DENY wins, ADR-0006 D-3).
6. Role-specific ALLOW for `bash` without a matching ALLOW pattern → DENY with reason `command not allowlisted`.
7. `rules_for(role, extra)` (E01-S15) now receives the merged file; `extra` (constitution `tool_permissions`) is merged with the same narrowing function.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given shipped defaults When `load_defaults` Then validates and contains a rule for every (role, tool) row above | `tests/permissions/test_loader.py::test_defaults_file_loads_and_covers_table` |
| 2 | Given project rule `SENIOR_DEV bash DENY ^npm` When `merge_narrowing` Then rule present in result | `tests/permissions/test_loader.py::test_project_can_add_deny` |
| 3 | Given project rule `QC Edit ALLOW` When `merge_narrowing` Then `ConfigError` | `tests/permissions/test_loader.py::test_project_cannot_widen_with_new_allow` |
| 4 | Given project file omitting `store.publish` from protected actions When merge Then `ConfigError` | `tests/permissions/test_loader.py::test_default_protected_actions_cannot_be_removed` |
| 5 | Given SENIOR_DEV `git.commit` When `decide` Then ALLOW | `tests/permissions/test_defaults_rules.py::test_senior_dev_may_commit` |
| 6 | Given SENIOR_DEV `review.approve` When `decide` Then DENY | `tests/permissions/test_defaults_rules.py::test_senior_dev_cannot_approve_review` |
| 7 | Given QC `Edit` When `decide` Then DENY; QC `jira.create_bug` ALLOW | `tests/permissions/test_defaults_rules.py::test_qc_read_only_but_may_create_bug` |
| 8 | Given LEAD_DEV `bash` `git push --force origin main` When `decide` Then DENY (global pattern) | `tests/permissions/test_defaults_rules.py::test_force_push_denied_for_all_roles` |
| 9 | Given SENIOR_DEV `bash` `curl http://x` When `decide` Then DENY; `dotnet test` ALLOW | `tests/permissions/test_defaults_rules.py::test_bash_command_patterns` |
| 10 | Given LEAD_DEV `git.merge_protected` When `decide` Then `REQUIRE_APPROVAL` with approver USER even with a project ALLOW attempt rejected at load | `tests/permissions/test_protected_actions.py::test_protected_action_requires_user_approval` |
| 11 | Given project adds protected action `analytics.purge` When ORCHESTRATOR requests it Then `REQUIRE_APPROVAL` | `tests/permissions/test_protected_actions.py::test_project_added_protected_action` |

#### Evidence required
- Quality gate output.
- Demo: `cat .ai/agents/permissions.yaml` after bootstrap shows the empty narrowing file (E02-S03 Behavior 9); `walk doctor` loads defaults + that file without error.

#### Notes
- ADR-0006 D-3, D-6; ADR-0013 D-4; ARCHITECTURE §6 (protected actions list).
- `NEW NAME:` `PermissionsFile`, `load_defaults`, `load_project_rules`, `merge_narrowing`, `DEFAULT_PROTECTED_ACTIONS`, tool names `decision.propose`, `work.plan`, `qc.*`.
- E02-S03 never copies `defaults.yaml` into a project. It writes `.ai/agents/permissions.yaml` as an empty narrowing file (two comment lines, `rules: []`, `protected_actions: []`); `load_project_rules` must accept it, and `defaults.yaml` stays the single source of the kernel rules.
- Commit subject: `feat: add default permission rules and protected actions (E02-S10)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12):
```
390 files already formatted
All checks passed!
Success: no issues found in 389 source files
Contracts: 21 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.85%
1280 passed, 5 deselected in 475.99s (0:07:55)
```
Touched modules: `permissions/loader.py` 100 %, `permissions/service.py` 100 %, `cli/composition.py` 100 %. All 11 acceptance tests pass, plus negative paths: an ALLOW restatement that adds command patterns or drops all patterns, redefining a default protected action with another approver, a project ALLOW glob over a project-added protected action, invalid YAML, a non-mapping file, unknown top-level keys, `rules` not a list, a non-mapping rule, a rule without a role, a rule with both `role` and `roles`, an empty `tools` list, an unknown role, and REQUIRE_APPROVAL without an approver. The bootstrap narrowing file (comments, `rules: []`, `protected_actions: []`), an empty file and an absent file all narrow nothing.

Demo on the E02-S08 demo repository (outside this repository):
```
$ cat .ai/agents/permissions.yaml
# Project narrowing of the kernel permission defaults (ADR-0006 D-6).
# Rules may only add DENY/REQUIRE_APPROVAL or restate a default ALLOW (E02-S10).
rules: []
protected_actions: []
$ walk --repo <tmp>/game doctor
...
exit=0
$ walk --repo <tmp>/game run --once          # build_kernel loads defaults.yaml + permissions.yaml
started 0 run(s)
$ printf 'rules:\n  - {role: QC, tool: edit, effect: ALLOW}\n' > .ai/agents/permissions.yaml
$ walk --repo <tmp>/game run --once
walk.common.errors.ConfigError: project rule QC edit ALLOW widens the kernel defaults
exit=1                                        (file restored afterwards)
```
`walk doctor` does not read the permission files yet. They are loaded by `build_kernel`, so the kernel refuses to start on an invalid or widening file; `walk run` logs this as an error with a traceback, which is the existing E01-S30 handling of startup errors. The demo therefore shows `walk run --once`.

Decisions (Level 0 unless marked):
- **Tool names.** `defaults.yaml` uses the catalogue names (`read`, `edit`, `write`, `glob`, `grep`, `bash`; E01-S14 `tools.yaml`; the Claude bridge lower-cases native names). The story table's `Read`/`Edit` would never match a request.
- **File format.** An entry names `role` or `roles` and `tool` or `tools`, plus the `PermissionRule` fields. Role `"*"` expands to every agent role (every `AgentRole` except the USER/KERNEL actors), because `PermissionRule.role` is an `AgentRole`. The same format applies to the project file; `PermissionsFile` holds the expanded rules.
- **Protected actions keep a role DENY.** Behavior 3 says "regardless of any ALLOW rule". The existing E01-S15 behaviour is kept: a protected action turns ALLOW/REQUIRE_APPROVAL into REQUIRE_APPROVAL by its approver, and a role-specific DENY stays a DENY (`SENIOR_DEV git.merge_protected` → DENY, as the table lists; E01-S15 test `test_protected_action_never_relaxes_a_deny`). `decide` needed no change: the `*` REQUIRE_APPROVAL rows of the defaults give every role a matching rule. `merge_narrowing` generates the same rows, with the action's approver, for a project-added protected action (AC 11), so it no longer hits "no matching rule". `service.py` only renames the constructor parameter to `protected_actions` and documents it.
- **ALLOW restatement.** A project ALLOW for (role, tool) is accepted only when the defaults have an ALLOW for the same (role, tool). It replaces those default rows, so it really narrows: `decide` unions ALLOW patterns, and keeping both rows would widen nothing but also narrow nothing. Its command patterns must be a non-empty subset of the defaults' patterns; its path patterns must be non-empty, and must be a subset of the defaults' patterns unless the default is `**`. Anything else is `ConfigError` ("widens" / "adds patterns").
- **AC 4 reading.** Project `protected_actions` are appended, so a project file cannot "omit" a default action. The bootstrap file's `protected_actions: []` must stay valid (Notes). Two cases raise `ConfigError`: a merged list missing a `DEFAULT_PROTECTED_ACTIONS` entry (e.g. defaults without `store.publish`), and a project entry redefining a default action with another approver, which would downgrade it. Restating it with the same approver is accepted.
- **Behavior 7.** `rules_for(role, extra)` now receives the merged kernel rules. The constitution's `extra` rules keep E01-S15's narrowing (a widening extra is dropped with a warning) instead of `merge_narrowing`'s `ConfigError`. Several builtin constitutions restate `bash` ALLOW with their own patterns, so raising would make agent instantiation fail. `decide` evaluates only the kernel rules, as before.
- **Kernel rule source.** The composition root used every constitution's `tool_permissions` as the kernel rule set ("until E02-S10"). It now uses `merge_narrowing(load_defaults(), load_project_rules(.ai/agents/permissions.yaml))` and passes the merged protected actions (it passed `[]` before). `load_defaults()` runs at kernel construction, so a malformed shipped file surfaces there as `ConfigError`. INTERFACES §1.10 documents the source.

---

### E02-S11 — Approval requests and `walk approve/deny/approvals`

**Status:** TODO
**Type:** feat
**Requirements:** §92, §31, §51, §93, §137
**Depends on:** E02-S10, E01-S26
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `REQUIRE_APPROVAL` decision creates a persisted `ApprovalRequest`, pauses the run with a `PAUSE` checkpoint, and `walk approve|deny` resolves it and wakes the waiting tool invocation; unanswered requests expire to DENY.

#### Scope
- In: full `request_approval/decide_approval/pending`, `EventApprovalWaiter` (event-driven implementation of the `ApprovalWaiter` protocol from E01-S26) in runtime, expiry, CLI (in-process and via `CommandClient`), `ON_PROTECTED_ACTION_REQUESTED` payload.
- Out: escalation-kind approvals routing (E05-S02); artifact-change approvals content (E02-S12 uses this API).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/permissions/service.py` | modify | `DefaultPermissionManager.request_approval/decide_approval/pending/expire_due` |
| `src/walk/permissions/repository.py` | modify | `ApprovalRequestRepository.list_pending`, `expire_before` |
| `src/walk/runtime/approvals.py` | create | `EventApprovalWaiter` (implements `walk.runtime.tool_invoker.ApprovalWaiter`; replaces `PollingApprovalWaiter` in the composition root) |
| `src/walk/runtime/tool_invoker.py` | modify | — (`authorize` awaits `ApprovalWaiter.wait(approval_id, timeout)`) |
| `src/walk/orchestrator/commands.py` | modify | — (`approve`, `deny` commands) |
| `src/walk/orchestrator/service.py` | modify | — (`Scheduler.tick` calls `expire_due`) |
| `src/walk/cli/cmd_approvals.py` | create | `approve`, `deny`, `approvals` |
| `src/walk/cli/app.py` | modify | register commands |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`approval_timeout_s: 86400` kernel default) |
| `tests/permissions/test_approvals.py` | create | — |
| `tests/runtime/test_approval_waiter.py` | create | — |
| `tests/cli/test_cmd_approvals.py` | create | — |

#### Interface contract
See INTERFACES.md §1.10 `PermissionManager.request_approval/decide_approval/pending`; DOMAIN-MODEL §4.5 `ApprovalRequest`.
```python
# src/walk/permissions/service.py (deltas)
class DefaultPermissionManager:
    async def expire_due(self, now: datetime) -> list[ApprovalRequest]:
        """PENDING with expires_at <= now → EXPIRED; ledger APPROVAL_DECIDED outcome=DENIED payload {'reason': 'expired'}."""


# src/walk/runtime/approvals.py
class EventApprovalWaiter:  # implements ApprovalWaiter protocol (E01-S26)
    """In-process registry of asyncio.Events keyed by ApprovalRequestId; resolved by decide_approval through a callback."""

    def register(self, approval_id: ApprovalRequestId) -> None: ...
    async def wait(self, approval_id: ApprovalRequestId, timeout_s: int) -> ApprovalState:
        """Returns APPROVED/DENIED/EXPIRED; timeout → EXPIRED (and the request is expired in the DB)."""

    def resolve(self, approval_id: ApprovalRequestId, state: ApprovalState) -> None: ...
```
CLI: `walk approve APV_ID [--note TEXT]`, `walk deny APV_ID [--note TEXT]`, `walk approvals [--pending] [--json]`.

#### Behavior
1. `request_approval` allocates `APV-NNNN` via `IdSequenceStore`, sets `expires_at = requested_at + approval_timeout_s`, persists PENDING, writes `APPROVAL_REQUESTED`, fires `ON_PROTECTED_ACTION_REQUESTED` after commit (payload keeps `approval_id`, `kind`, `approver` and adds `tool`; `run_id` is on the context). Its builtin `builtin.approval_recorded` (E02-S08) only verifies the request and never pauses (it runs inside the run's task). `ToolInvoker.authorize` then sets `PAUSED_FOR_APPROVAL`, creates the `PAUSE` checkpoint and awaits `ApprovalWaiter.wait`.
2. `decide_approval(id, approve, by, note)`: PENDING → APPROVED/DENIED, `decided_at`, `decided_by`, ledger `APPROVAL_DECIDED` (`outcome` OK/DENIED, actor `USER`), then `EventApprovalWaiter.resolve`; run state returns to `RUNNING` through `executor.resume(run_id)`; a non-PENDING request → `PermanentError("approval already decided")`.
3. APPROVED → `authorize` returns `PermissionDecision(effect=ALLOW, approval_request_id=id)`; DENIED/EXPIRED → `DENY` + `TOOL_DENIED` ledger + `ON_TOOL_DENIED`.
4. `expire_due` runs every scheduler tick and on `wait` timeout; expiry is idempotent.
5. After a kernel restart the waiter registry is empty: `RecoveryManager` (E01-S28) re-registers waiters for runs in `PAUSED_FOR_APPROVAL` with PENDING requests and re-enters `wait`; APPROVED-while-down requests resume immediately.
6. CLI: when a daemon lock is held, `approve/deny` go through `CommandClient` (`commands.name = "approve"`), else in-process (DB write + waiter not needed). `approvals --pending` reads the DB directly.
7. Exit codes: unknown id → 1; already decided → 2.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a fake run requesting `git.merge_protected` When tool call authorised Then `ApprovalRequest` PENDING persisted, run `PAUSED_FOR_APPROVAL`, `PAUSE` checkpoint, `APPROVAL_REQUESTED` ledger | `tests/permissions/test_approvals.py::test_require_approval_pauses_run_and_persists_request` |
| 2 | Given pending request When `decide_approval(approve=True)` Then `authorize` returns ALLOW with `approval_request_id` and run `RUNNING` | `tests/permissions/test_approvals.py::test_approve_resumes_run_with_allow` |
| 3 | Given pending request When `decide_approval(approve=False)` Then DENY, `TOOL_DENIED` ledger | `tests/permissions/test_approvals.py::test_deny_results_in_tool_denied` |
| 4 | Given decided request When `decide_approval` again Then `PermanentError` | `tests/permissions/test_approvals.py::test_decide_twice_raises` |
| 5 | Given request with `expires_at` in the past When `expire_due(now)` Then EXPIRED and `APPROVAL_DECIDED` outcome DENIED | `tests/permissions/test_approvals.py::test_expire_due_marks_expired` |
| 6 | Given waiter and `FakeClock` When `wait` times out Then returns EXPIRED | `tests/runtime/test_approval_waiter.py::test_wait_timeout_returns_expired` |
| 7 | Given run paused for approval, kernel restarted, request approved meanwhile When recovery runs Then run resumes without new request | `tests/runtime/test_approval_waiter.py::test_recovery_reregisters_and_resumes_approved` |
| 8 | Given pending request When `walk approve APV-0001 --note ok` Then exit 0 and state APPROVED | `tests/cli/test_cmd_approvals.py::test_approve_command` |
| 9 | Given unknown id When `walk deny APV-9999` Then exit 1 | `tests/cli/test_cmd_approvals.py::test_deny_unknown_exits_one` |
| 10 | Given two pending, one decided When `walk approvals --pending --json` Then two entries | `tests/cli/test_cmd_approvals.py::test_approvals_pending_lists_only_pending` |

#### Evidence required
- Quality gate output.
- Demo: in e2e transcript — `walk approvals --pending` showing `APV-0001 PROTECTED_ACTION git.merge_protected`, then `walk approve APV-0001 --note "ok"` → `APV-0001 APPROVED`.

#### Notes
- ADR-0006 D-4, D-7; ARCHITECTURE §6 protected actions paragraph.
- `NEW NAME:` `EventApprovalWaiter` (the `ApprovalWaiter` protocol itself is defined by E01-S26), `expire_due`, `approval_timeout_s` policy key, command names `approve`/`deny` in `CommandConsumer`.
- Pitfall: `wait` must not hold a DB connection; poll the DB on wake-up to tolerate decisions made in-process by the CLI while the daemon is running.
- Commit subject: `feat: add approval request lifecycle and approve commands (E02-S11)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S12 — Approved artifact registry and `walk artifacts`

**Status:** TODO
**Type:** feat
**Requirements:** §33, §24, §137, §139
**Depends on:** E02-S10, E01-S16
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Approved artifacts are first-class: `MemoryManager.approve_artifact` writes `.ai/approved/APR-NNNN.md` plus a hashed payload folder, writes under `approved/` without a change decision are refused, startup/doctor verify hashes and flag drift as `INVALID`, and `walk artifacts` lists/approves/verifies.

#### Scope
- In: `approve_artifact`, `verify_approved_artifacts`, `ApprovedArtifactRepository`, `write()` guard for `approved/`, CLI group, startup step integration.
- Out: `ApprovedArtifact` as context items (E04-S08); `PHASE_BASELINE` creation (E07-S02 registers the `ON_PHASE_START` builtin that calls this API; deferred from E02-S08); change-request workflow via decisions (E05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/approved.py` | create | `hash_payload`, `approved_doc`, `APPROVED_DIR` |
| `src/walk/memory/repository.py` | modify | `ApprovedArtifactRepository` |
| `src/walk/memory/service.py` | modify | `DefaultMemoryManager.approve_artifact/verify_approved_artifacts`, `write` guard |
| `src/walk/memory/errors.py` | modify | `ApprovedArtifactDrift`, `ApprovalNotAuthorized` |
| `src/walk/orchestrator/service.py` | modify | — (startup step 3: `verify_approved_artifacts`) |
| `src/walk/cli/cmd_doctor.py` | modify | — (`approved` section) |
| `src/walk/cli/cmd_artifacts.py` | create | `artifacts_list`, `artifacts_approve`, `artifacts_verify` |
| `src/walk/cli/app.py` | modify | register `artifacts` group |
| `tests/memory/test_approved.py` | create | — |
| `tests/memory/test_approved_write_guard.py` | create | — |
| `tests/cli/test_cmd_artifacts.py` | create | — |

#### Interface contract
See INTERFACES.md §1.8 `MemoryManager.approve_artifact`, `verify_approved_artifacts`, `write`; DOMAIN-MODEL §4.7 `ApprovedArtifact`.
```python
# src/walk/memory/approved.py
APPROVED_DIR = "approved"


def hash_payload(root: Path, payload_paths: list[str]) -> str:
    """SHA-256 over sorted (relative path, file bytes) pairs; raises ConfigError if a path is missing."""


def approved_doc(artifact: ApprovedArtifact, actor: Actor, now: datetime) -> MemoryDocument:
    """type=approved, id=artifact.id, sections: Summary, Scope, Related Requirements, Payload, Change History;
    front_matter.extra = {kind, scope, approved_by, content_sha256, supersedes, change_request_decision}."""


class ApprovedArtifactRepository:
    async def upsert(self, uow: UnitOfWork, artifact: ApprovedArtifact) -> None: ...
    async def get(self, artifact_id: ApprovedArtifactId) -> ApprovedArtifact: ...
    async def list(
        self, *, status: ApprovalStatus | None = None, scope: str | None = None
    ) -> list[ApprovedArtifact]: ...
```
CLI: `walk artifacts list [--json]`; `walk artifacts approve PATH... --kind KIND --title TITLE --scope SCOPE [--supersedes APR_ID]` (actor USER; copies payload files into `.ai/approved/APR-NNNN/`); `walk artifacts verify` (exit 0 ok / 2 drift).

#### Behavior
1. `approve_artifact(artifact, actor)`: authority check — `actor.role == USER`, or `Constitution(actor.role).authority.may_approve` contains `artifact.kind.value`; otherwise `ApprovalNotAuthorized(PermissionDenied)`.
2. The id `APR-NNNN` is allocated if `artifact.id` is a placeholder (`APR-0000`); payload files are copied into `.ai/approved/<id>/`, `content_sha256 = hash_payload`, `status = APPROVED`, `version` = previous version + 1 when `supersedes` is set (and the superseded row becomes `SUPERSEDED`), else 1.
3. The metadata document is written through `write()` with an internal bypass token for the `approved/` guard (`_approved_write=True` keyword only usable by `approve_artifact`); ledger `ARTIFACT_APPROVED` payload `{id, kind, sha}`.
4. `write(doc)` for any path under `approved/` from any other caller is refused with `PermissionDenied("approved artifacts change only through approve_artifact")` unless `doc.front_matter.extra["change_request_decision"]` is a `DecisionId` that exists (E04-S05 provides lookup; until then any syntactically valid id is accepted and a WARNING is logged).
5. `verify_approved_artifacts()` recomputes hashes for all `APPROVED` artifacts; mismatch or missing payload → `memory_index.freshness_status = INVALID` for the metadata doc, `ON_CONTEXT_STALE` fired with `{doc_id, status: INVALID, reason: "approved artifact drift"}`, returns the drifted ids. Status in `approved_artifacts` is unchanged (re-approval restores).
6. Startup step 3 calls `verify_approved_artifacts`; drift never aborts startup but is printed by `walk doctor` under `approved`.
7. `BoundaryAuditor` forbidden path `.ai/approved/**` is confirmed in E02-S14.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given USER actor and two payload files When `approve_artifact` Then `APR-0001.md` + `APR-0001/` exist, row APPROVED, sha equals `hash_payload`, `ARTIFACT_APPROVED` ledger | `tests/memory/test_approved.py::test_approve_writes_doc_payload_row_and_ledger` |
| 2 | Given SENIOR_DEV actor When `approve_artifact(kind=ART_DIRECTION)` Then `ApprovalNotAuthorized` | `tests/memory/test_approved.py::test_approve_requires_authority` |
| 3 | Given LEAD_DEV actor whose `may_approve` includes `ARCHITECTURE_DIRECTION` When approve that kind Then APPROVED | `tests/memory/test_approved.py::test_role_with_may_approve_can_approve_kind` |
| 4 | Given `supersedes=APR-0001` When approve Then new version 2 and APR-0001 `SUPERSEDED` | `tests/memory/test_approved.py::test_supersede_bumps_version_and_marks_previous` |
| 5 | Given payload path missing When `hash_payload` Then `ConfigError` | `tests/memory/test_approved.py::test_hash_payload_missing_file_raises` |
| 6 | Given a doc path under `approved/` When `write` without change decision Then `PermissionDenied` | `tests/memory/test_approved_write_guard.py::test_write_under_approved_refused_without_decision` |
| 7 | Given a payload file modified on disk When `verify_approved_artifacts` Then id returned, index INVALID, `ON_CONTEXT_STALE` fired | `tests/memory/test_approved.py::test_verify_detects_payload_drift` |
| 8 | Given intact artifacts When `verify_approved_artifacts` Then `[]` | `tests/memory/test_approved.py::test_verify_clean_returns_empty` |
| 9 | Given files When `walk artifacts approve a.png --kind UI_CONCEPT --title X --scope FEAT-0001` Then exit 0 and `walk artifacts list` shows APR-0001 | `tests/cli/test_cmd_artifacts.py::test_artifacts_approve_and_list` |
| 10 | Given drift When `walk artifacts verify` Then exit 2 listing the id | `tests/cli/test_cmd_artifacts.py::test_artifacts_verify_exit_two_on_drift` |

#### Evidence required
- Quality gate output.
- Demo: `walk artifacts approve GDD/concept.png --kind GAMEPLAY_CONCEPT --title "Core loop" --scope project` → `APR-0001 approved (sha …)`; `walk artifacts verify` → `ok`.

#### Notes
- ADR-0003 D-4, D-5; Invariant 10; ARCHITECTURE §7 row 10.
- `NEW NAME:` `walk artifacts` group (WBS §6), `hash_payload`, `approved_doc`, `APPROVED_DIR`, `ApprovedArtifactRepository`, `ApprovedArtifactDrift`, `ApprovalNotAuthorized`, `_approved_write` internal flag.
- Commit subject: `feat: add approved artifact registry and artifacts commands (E02-S12)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S13 — Human override CLI subset

**Status:** TODO
**Type:** feat
**Requirements:** §93, §6.12, §137
**Depends on:** E01-S30, E02-S11
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The user can pause/resume the project or one agent, cancel a work item, change priority, change a role's model policy and the project autonomy level from the CLI; every action is recorded as `USER_OVERRIDE` and routed through the daemon when it is running.

#### Scope
- In: `walk pause/resume [--agent]`, `walk work cancel`, `walk work priority`, `walk policy set-model`, `walk policy set-autonomy`, `CommandConsumer` handlers, hooks `ON_PROJECT_PAUSE/RESUME`, `ON_TASK_CANCELLED`.
- Out: `walk work force-review` (E03-S16); `walk phase stop` (E07-S05); `walk decisions override` (E05-S09).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/service.py` | modify | `DefaultOrchestrator.pause/resume/cancel_work_item/set_priority/set_autonomy` |
| `src/walk/orchestrator/commands.py` | modify | — (handlers `pause`, `resume`, `work.cancel`, `work.priority`, `policy.set_model`, `policy.set_autonomy`) |
| `src/walk/agents/policy_file.py` | create | `PoliciesFile`, `update_model_policy` |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.set_priority`, `ProjectRepository.set_autonomy_level_max`, `ProjectRepository.set_paused` |
| `src/walk/cli/cmd_run.py` | modify | `pause`, `resume` |
| `src/walk/cli/cmd_work.py` | modify | `work_cancel`, `work_priority` |
| `src/walk/cli/cmd_policy.py` | create | `policy_set_model`, `policy_set_autonomy` |
| `src/walk/cli/app.py` | modify | register commands |
| `tests/orchestrator/test_overrides.py` | create | — |
| `tests/agents/test_policy_file.py` | create | — |
| `tests/cli/test_cmd_overrides.py` | create | — |

#### Interface contract
See INTERFACES.md §1.1 `Orchestrator.pause/resume/cancel_work_item`. Deltas:
```python
class DefaultOrchestrator:
    async def set_priority(
        self, work_item_id: WorkItemId, priority: Priority, *, actor: str
    ) -> WorkItem: ...
    async def set_autonomy(self, level: AutonomyLevel, *, actor: str) -> Project: ...


# src/walk/agents/policy_file.py
class PoliciesFile(WalkModel):
    roles: dict[AgentRole, RuntimePolicy]

    @classmethod
    def load(cls, path: Path) -> "PoliciesFile": ...
    def write(self, path: Path) -> Path: ...


def update_model_policy(
    path: Path, role: AgentRole, preferred: list[ModelId], fallback: list[ModelId]
) -> RuntimePolicy: ...
```
CLI (INTERFACES §6): `walk pause [--agent RUN_ID]`, `walk resume [--agent RUN_ID]`, `walk work cancel ID --reason TEXT`, `walk work priority ID P0|P1|P2|P3`, `walk policy set-model ROLE --preferred M... [--fallback M...]`, `walk policy set-autonomy 0|1|2|3`.

#### Behavior
1. `pause()` without run: `projects.paused = 1`, fire `ON_PROJECT_PAUSE` from the command-consumer task (never from a run task, E02-S08 Behavior 3), whose builtin `builtin.pause_all_runs` calls `AgentExecutor.pause` for each running run: one `PAUSE` checkpoint each, written by the executor, and `PAUSED_BY_USER`; `resume()` clears the flag, fires `ON_PROJECT_RESUME`, re-queues paused runs via the scheduler (idempotency key with incremented `state_version` is not needed — the run resumes natively or via handover per E01-S28).
2. `pause(run_id)`: `PAUSE` checkpoint, run `PAUSED_BY_USER`; `resume(run_id)` → `AgentExecutor.resume_native(latest checkpoint)`; unknown run → exit 1.
3. `cancel_work_item(id, reason)`: raise workflow event `cancel` as USER (guards apply: COMPLETE/CANCELLED items → `GuardRejected`, exit 2), fire `ON_TASK_CANCELLED` from the command-consumer task with `run_id` = the item's running run (or `None`) and payload `{reason}` (builtin `builtin.cancel_cleanup` cancels that run; the executor removes the worktree and keeps the branch).
4. `set_priority`: updates `work_items.priority` + json; next tick re-sorts. `set_autonomy`: updates `Project.autonomy_level_max`.
5. `set-model`: validates every model id exists and is enabled in the `CapabilityRegistry`, rewrites `.ai/agents/policies.yaml` for that role only (other roles byte-identical), effective on the next scheduled run.
6. Every command writes `USER_OVERRIDE` with payload `{"command": "<name>", "args": {...}}`, `actor_role = USER` (write point `orchestrator`, ARCHITECTURE §4.3).
7. With a daemon running, commands go through `CommandClient` and the consumer executes rules 1–6; without a daemon, `pause/resume --agent` exit 3 (daemon required), all others run in-process.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given two running fake runs When `pause()` Then project paused, both `PAUSED_BY_USER`, two `PAUSE` checkpoints, one `USER_OVERRIDE` | `tests/orchestrator/test_overrides.py::test_pause_project_checkpoints_and_pauses_runs` |
| 2 | Given paused project When `resume()` Then flag cleared and next `tick` restarts runs | `tests/orchestrator/test_overrides.py::test_resume_project_restarts_runs` |
| 3 | Given one run When `pause(run_id)`/`resume(run_id)` Then only that run paused then resumed natively | `tests/orchestrator/test_overrides.py::test_pause_resume_single_agent` |
| 4 | Given an IMPLEMENTING story with a run When `cancel_work_item` Then state CANCELLED, run CANCELLED, worktree removed, branch kept | `tests/orchestrator/test_overrides.py::test_cancel_work_item_cleans_up` |
| 5 | Given a COMPLETE story When `cancel_work_item` Then `GuardRejected` | `tests/orchestrator/test_overrides.py::test_cancel_complete_item_rejected` |
| 6 | Given story P2 When `set_priority(P0)` Then persisted and `USER_OVERRIDE` written | `tests/orchestrator/test_overrides.py::test_set_priority_persists_and_logs` |
| 7 | Given policies file When `update_model_policy(SENIOR_DEV, …)` Then only SENIOR_DEV changed | `tests/agents/test_policy_file.py::test_update_model_policy_changes_single_role` |
| 8 | Given unknown model id When `walk policy set-model SENIOR_DEV --preferred nope/x` Then exit 1 | `tests/cli/test_cmd_overrides.py::test_set_model_rejects_unknown_model` |
| 9 | Given `walk policy set-autonomy 1` Then `Project.autonomy_level_max == 1` and `USER_OVERRIDE` | `tests/cli/test_cmd_overrides.py::test_set_autonomy` |
| 10 | Given no daemon When `walk pause --agent RUN-…` Then exit 3 | `tests/cli/test_cmd_overrides.py::test_pause_agent_requires_daemon` |

#### Evidence required
- Quality gate output.
- Demo: `walk pause` → `project paused`; `walk ledger query --kind USER_OVERRIDE --limit 1` → payload `{"command": "pause"}`; `walk resume`.

#### Notes
- ARCHITECTURE §6 "Human override"; ADR-0011 D-6 (policy changes apply on next run).
- `NEW NAME:` `set_priority`, `set_autonomy`, `PoliciesFile`, `update_model_policy`, command handler names.
- Commit subject: `feat: add human override commands (E02-S13)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S14 — Security hardening: forbidden paths, git guard hooks, secret scan, command restrictions

**Status:** TODO
**Type:** feat
**Requirements:** §91, §92, §31, §60, §137, §138
**Depends on:** E02-S10, E01-S23, E01-S25
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Repository boundary, protected branches, secret isolation and command restrictions are enforced mechanically: `BoundaryAuditor` ships the default forbidden-path set, every worktree gets git guard hooks, `push` refuses protected branches, and one shared secret scanner protects `.ai/` writes and agent diffs.

#### Scope
- In: `DEFAULT_FORBIDDEN_PATHS`, `allowed_paths` from policy, `install_guard_hooks` (sh scripts), `push` protected check, `contains_secret`, `BoundaryAuditor` secret scan of added files, `SandboxManager.create` guard-hook installation, projection targets that the game repository tracks (Behavior 9–12).
- Out: remote push mechanics/PR (E03-S01); Codex sandbox flags (E01-S26, verified by ADR-0014).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/boundary.py` | modify | `DEFAULT_FORBIDDEN_PATHS`, `EVIDENCE_EXCEPTIONS`, `DefaultBoundaryAuditor.audit` (secret scan added) |
| `src/walk/memory/secrets.py` | create | `contains_secret`, `SECRET_PATTERNS` |
| `src/walk/memory/service.py` | modify | — (`write` uses `contains_secret`) |
| `src/walk/integrations/git/provider.py` | modify | `GitCliProvider.install_guard_hooks`, `GitCliProvider.push` protected check |
| `src/walk/integrations/git/hooks/pre-commit.sh` | create | — |
| `src/walk/integrations/git/hooks/pre-push.sh` | create | — |
| `src/walk/runtime/sandbox.py` | modify | — (`create` calls `install_guard_hooks(path, project.protected_branches)`) |
| `src/walk/agents/models.py` | modify | `RuntimePolicy.allowed_paths: list[str]` (default `["**"]`) |
| `src/walk/agents/defaults/policies.yaml` | modify | — (`allowed_paths` per role; QC `[]`) |
| `tests/runtime/test_boundary.py` | create | — |
| `tests/memory/test_secrets.py` | create | — |
| `tests/integrations/git/test_guard_hooks.py` | create | — |
| `src/walk/integrations/protocols.py`, `src/walk/integrations/git/provider.py`, `tests/fakes/fake_git_provider.py` | modify | `GitProvider.hide_local_changes` |
| `src/walk/skills/service.py` | modify | `DefaultSkillRegistry(hide_tracked=...)`, `HideTracked` (`project_all` hides tracked targets before writing) |
| `src/walk/cli/composition.py` | modify | — (wires `hide_tracked`: run worktrees only, Behavior 10) |
| `docs/01-architecture/INTERFACES.md` | modify | — (§2.3 `GitProvider.hide_local_changes`) |
| `tests/skills/test_projection_tracked_targets.py` | create | — |
| `tests/integrations/git/test_provider.py` | modify | — |

#### Interface contract
See INTERFACES.md §1.13 `BoundaryAuditor.audit`, §2.3 `GitProvider.install_guard_hooks`, `GitProvider.push`.
```python
# src/walk/runtime/boundary.py
DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (
    ".ai/**",
    ".walk/**",
    "**/*.env",
    "ProjectSettings/*Secrets*",
    ".ai/agents/**",
    ".ai/approved/**",
)
EVIDENCE_EXCEPTIONS: tuple[str, ...] = (".ai/features/*/evidence/**", ".ai/bugs/*/evidence/**")


class DefaultBoundaryAuditor:
    def __init__(
        self,
        *,
        forbidden: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
        exceptions: tuple[str, ...] = EVIDENCE_EXCEPTIONS,
    ) -> None: ...
    def audit(
        self,
        worktree_path: str,
        changed_files: list[str],
        allowed_paths: list[str],
        forbidden_paths: list[str],
    ) -> list[str]:
        """violations: path outside worktree (absolute/..), path matching forbidden (unless matching an exception),
        path not matching any allowed glob, or 'SECRET:<path>' when contains_secret(file) for added/modified files."""


# src/walk/memory/secrets.py
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("anthropic_key", r"sk-ant-[A-Za-z0-9_-]{20,}"),
    ("openai_key", r"sk-[A-Za-z0-9]{32,}"),
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"),
    ("github_token", r"gh[pousr]_[A-Za-z0-9]{36,}"),
    ("jira_token", r"ATATT3[A-Za-z0-9_-]{20,}"),
    ("private_key", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    (
        "generic_assignment",
        r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]",
    ),
)


def contains_secret(text: str) -> str | None: ...  # pattern name or None


# GitProvider (INTERFACES §2.3) addition
async def hide_local_changes(self, path: str, files: list[str]) -> list[str]:
    """Mark those of `files` (worktree-relative) that are tracked in the index of the worktree at `path`
    with `git update-index --skip-worktree`; return them. Untracked files are left alone (info/exclude covers them)."""


# src/walk/skills/service.py
HideTracked = Callable[[str, list[str]], Awaitable[list[str]]]  # (worktree, relative targets) -> hidden
```
Guard hook scripts: `pre-commit.sh` aborts when current branch matches any protected pattern (`main`, `release/*` expanded from `WALK_PROTECTED_BRANCHES` written into the script at install time); `pre-push.sh` aborts when any pushed ref matches a protected pattern. Both exit 1 with message `walk: protected branch <name>`.

#### Behavior
1. `audit` normalises paths (POSIX separators, resolved against worktree); any path resolving outside the worktree is a violation.
2. Forbidden match wins over allowed; exceptions win over forbidden (`.ai/features/FEAT-0001/evidence/shot.png` is allowed).
3. `allowed_paths` default `["**"]` for SENIOR_DEV/LEAD_DEV; QC `[]` (any write is a violation — QC does not fix code, ADR-0006 D-6).
4. Secret scan reads added/modified files ≤ 1 MB as UTF-8 (errors ignored); binary files are skipped; a hit yields violation `SECRET:<path>`.
5. `MemoryManager.write` refuses content where `contains_secret(doc body or front matter)` → `PermissionDenied("secret-like content: <pattern>")` (ADR-0003 D-4).
6. `install_guard_hooks` resolves the worktree's hooks dir via `git rev-parse --git-path hooks`, writes both scripts with `0o755`, substituting the protected patterns; idempotent (same content → no rewrite). Existing non-walk hooks are preserved by chaining (`exec <hooks>/pre-commit.local` if present).
7. `push(path, branch, protected_branches)` raises `PermissionDenied` when `branch` matches any protected pattern before invoking git (remote mechanics E03-S01).
8. `SandboxManager.create` installs guard hooks after projection; failure → `ConfigError` and worktree removed.
9. Tracked projection targets. A game repository may track its own `AGENTS.md` (or a `.claude/skills/<name>/SKILL.md` with a builtin's name). `info/exclude` cannot hide a tracked file, so the Codex managed section shows up as a change to the forbidden path `AGENTS.md`. Every audited checkpoint of a Codex run would then end `FAILED_BOUNDARY`, and without the audit `commit_all` would commit the section. Rule: `project_all` passes every rendered target to `hide_tracked(worktree, targets)` before writing. The tracked targets get `--skip-worktree` in that worktree's own index (each linked worktree has one), so `status`, `diff_names`, `commit_all` and `discard_changes` ignore the projection. Codex still reads the real `AGENTS.md`, with the repository's text kept around the markers (E02-S06 Behavior 3).
10. Only run worktrees under `.walk/worktrees/` are marked. When the target worktree is any other path and a target is tracked (e.g. `walk skills sync --worktree .` in the main checkout), `hide_tracked` raises `ConfigError("<path> is tracked; skills are projected into run worktrees only")` and nothing is written. The user's checkout never gets a hidden index flag. The default `walk skills sync` target `.walk/projections/<provider>/` has no tracked files.
11. Accepted consequence: an agent edit to a hidden file inside a run worktree is invisible to `BoundaryAuditor`. It is never committed and disappears with the worktree. Edits inside the managed section are still reported as drift by E02-S07, which compares file content.
12. Git operations that move HEAD inside a run worktree (E03-S01 `squash_wip`, rebase) clear the flag (`--no-skip-worktree`) and restore the file first, then re-project.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given changed `../outside.txt` When `audit` Then violation | `tests/runtime/test_boundary.py::test_audit_rejects_path_outside_worktree` |
| 2 | Given changed `.ai/agents/roles/lead_dev.md` When `audit` Then violation | `tests/runtime/test_boundary.py::test_audit_rejects_agents_dir` |
| 3 | Given changed `.ai/features/FEAT-0001/evidence/a.png` When `audit` Then no violation | `tests/runtime/test_boundary.py::test_audit_allows_evidence_exception` |
| 4 | Given QC `allowed_paths=[]` and one changed file When `audit` Then violation | `tests/runtime/test_boundary.py::test_audit_qc_may_not_write` |
| 5 | Given added file containing `sk-ant-…` When `audit` Then `SECRET:<path>` | `tests/runtime/test_boundary.py::test_audit_flags_secret_in_added_file` |
| 6 | Given each pattern sample When `contains_secret` Then pattern name; given lorem text Then None | `tests/memory/test_secrets.py::test_contains_secret_patterns_and_negative` |
| 7 | Given doc with a token in body When `MemoryManager.write` Then `PermissionDenied` | `tests/memory/test_secrets.py::test_memory_write_refuses_secret` |
| 8 | Given a real temp worktree When `install_guard_hooks(["main","release/*"])` Then both scripts exist, executable, contain patterns; second call no rewrite | `tests/integrations/git/test_guard_hooks.py::test_install_guard_hooks_idempotent` |
| 9 | Given hooks installed and checkout `main` When `git commit` via runner Then exit 1 with `protected branch` | `tests/integrations/git/test_guard_hooks.py::test_pre_commit_blocks_protected_branch` |
| 10 | Given `push(path, "main", ["main"])` Then `PermissionDenied` and git not invoked | `tests/integrations/git/test_guard_hooks.py::test_push_refuses_protected_branch` |
| 11 | Given a run worktree of a repository that tracks `AGENTS.md` When `project_all` runs for codex Then the managed section is in the file, `git status` of the worktree is clean, and `commit_all` returns None | `tests/skills/test_projection_tracked_targets.py::test_tracked_agents_md_is_hidden_in_run_worktree` |
| 12 | Given the main checkout with a tracked `AGENTS.md` When `project_all` targets it Then `ConfigError` and the file bytes are unchanged | `tests/skills/test_projection_tracked_targets.py::test_projection_refuses_tracked_target_outside_run_worktrees` |
| 13 | Given tracked `a.txt` and untracked `b.txt` When `hide_local_changes(path, ["a.txt", "b.txt"])` Then it returns `["a.txt"]` and an edit of `a.txt` is absent from `status` | `tests/integrations/git/test_provider.py::test_hide_local_changes_marks_only_tracked_files` |

#### Evidence required
- Quality gate output.
- Demo: after `walk run --once` with a scheduled fake run, `ls .walk/worktrees/<run>/.git` hooks dir (via `git rev-parse --git-path hooks`) shows `pre-commit`, `pre-push`.

#### Notes
- From E02-B02 (2026-10-07): the existing `UNITY_*` allowlist entry passes Unity CI licence secrets (`UNITY_PASSWORD`, `UNITY_SERIAL`, `UNITY_LICENSE`, `UNITY_EMAIL`) to agents. Replace the wildcard with an explicit list of non-secret Unity variables, add the Unity secret names to the credential catalogue, and add a test that none of them survive `scrubbed_env`.
- ARCHITECTURE §6 table, §4.2 last row; ADR-0006 D-5; ADR-0009 consequence (sh on Windows via Git for Windows).
- `NEW NAME:` `DEFAULT_FORBIDDEN_PATHS`, `EVIDENCE_EXCEPTIONS`, `walk.memory.secrets` (`contains_secret`, `SECRET_PATTERNS`), `RuntimePolicy.allowed_paths`, hook script files.
- Pitfall: test 9 requires `sh` on PATH; mark `@pytest.mark.skipif(shutil.which("sh") is None)` — not `integration`, since Git for Windows ships `sh`.
- Tracked `AGENTS.md` (architect, 2026-10-07; found in E02-S06 Evidence). `skip-worktree` was chosen because it is git-native, independent of the provider, and keeps Codex reading the file it is verified to read (ADR-0014). Rejected alternatives:
  - Projecting into `AGENTS.override.md`. Per Codex documentation, Codex reads one instructions file per directory, so the override would replace the repository's text instead of extending it, and that behaviour is not verified for the pinned CLI.
  - A separate `AGENTS.walk.md` included by reference. `AGENTS.md` has no include mechanism, and adding the reference would itself modify the tracked file.
  - Bootstrap refusing such repositories. That blocks every repository that already uses Codex.
- `NEW NAME:` `GitProvider.hide_local_changes`, `HideTracked`, `DefaultSkillRegistry(hide_tracked=...)`.
- Commit subject: `feat: enforce repository boundary guard hooks and secret scan (E02-S14)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S15 — `walk doctor --fix --strict`

**Status:** TODO
**Type:** feat
**Requirements:** §26, §27, §28, §91, §105, §137
**Depends on:** E02-S07, E02-S14, E02-S04
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`walk doctor --fix` repairs guard hooks, skill projections, the memory index and the manifest; `--strict` adds lints (import-linter contracts, constitution provider-name check, `models.yaml` validation, version pins, skill drift) and fails on any finding.

#### Scope
- In: `--fix`, `--strict`, lint implementations, exit codes, `doctor` sections for `skills`, `approved`, `versions`, `lints`.
- Out: Jira status-map gap report (E03-S05).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/cli/cmd_doctor.py` | modify | `doctor` (`--fix`, `--strict`), `DoctorReport` |
| `src/walk/cli/lints.py` | create | `lint_constitutions_provider_names`, `lint_models_yaml`, `run_import_linter`, `PROVIDER_NAME_PATTERN` |
| `src/walk/cli/composition.py` | modify | — (exposes services needed by fixes) |
| `tests/cli/test_cmd_doctor_fix.py` | create | — |
| `tests/cli/test_lints.py` | create | — |

#### Interface contract
```python
# src/walk/cli/cmd_doctor.py
class DoctorReport(WalkModel):
    manifest: EnvironmentManifest
    skills: DriftReport
    approved_drift: list[ApprovedArtifactId]
    version_pins_ok: bool
    lints: list[str]  # empty when clean
    fixes_applied: list[str]
    exit_code: int


# src/walk/cli/lints.py
PROVIDER_NAME_PATTERN = r"(?i)\b(claude|anthropic|codex|openai|gpt|sonnet|opus)\b"


def lint_constitutions_provider_names(
    constitutions: list[Constitution],
) -> list[str]: ...  # ADR-0013 D-5
def lint_models_yaml(registry: CapabilityRegistry) -> list[str]:
    """every enabled model: prices > 0, supports_effort_levels non-empty, context_window_tokens > max_output_tokens > 0."""


async def run_import_linter(runner: SubprocessRunner, repo_root: Path) -> list[str]:
    """`lint-imports --config pyproject.toml`; returns broken contract lines; [] if clean; ConfigError if tool missing."""
```
CLI: `walk doctor [--fix] [--strict] [--json]`. Exit: 0 clean; 4 required component missing; 1 any strict lint finding or fix failure.

#### Behavior
1. `--fix` runs, in order: `install_guard_hooks` for every existing worktree under `.walk/worktrees/` and the repo root hooks dir; `skills regenerate` for drift; `memory.rebuild_index()`; re-run preflight to refresh `environment.yaml`. Each fix appended to `fixes_applied`; a failing fix is recorded and does not stop the others; any failure → exit 1.
2. `--strict` runs all lints after fixes; findings printed under `lints`; drift (skills or approved) and pin problems are findings under `--strict`.
3. Without `--strict`, lints are not executed (doctor stays fast); drift is reported informationally.
4. `run_import_linter` is executed only when `import-linter` is installed (dev environment); absence under `--strict` → finding `import-linter not installed` (ConfigError mapped to a finding, exit 1).
5. `--json` prints `DoctorReport`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given missing guard hooks in a worktree When `walk doctor --fix` Then hooks installed and listed in `fixes_applied` | `tests/cli/test_cmd_doctor_fix.py::test_fix_installs_guard_hooks` |
| 2 | Given skill drift When `walk doctor --fix` Then projections regenerated | `tests/cli/test_cmd_doctor_fix.py::test_fix_regenerates_skill_projections` |
| 3 | Given stale `memory_index` row When `--fix` Then index rebuilt | `tests/cli/test_cmd_doctor_fix.py::test_fix_rebuilds_memory_index` |
| 4 | Given clean repo When `walk doctor --strict` Then exit 0 and `lints == []` | `tests/cli/test_cmd_doctor_fix.py::test_strict_clean_exit_zero` |
| 5 | Given constitution body mentioning a provider name When `lint_constitutions_provider_names` Then one finding | `tests/cli/test_lints.py::test_constitution_provider_name_lint` |
| 6 | Given model with zero price When `lint_models_yaml` Then finding | `tests/cli/test_lints.py::test_models_yaml_lint_prices` |
| 7 | Given fake runner returning broken contract output When `run_import_linter` Then findings; given missing tool Then `ConfigError` | `tests/cli/test_lints.py::test_import_linter_wrapper` |
| 8 | Given mismatched pins When `walk doctor --strict` Then exit 1 and `version_pins_ok == False` | `tests/cli/test_cmd_doctor_fix.py::test_strict_fails_on_pin_mismatch` |
| 9 | Given `--json` When doctor Then output parses as `DoctorReport` | `tests/cli/test_cmd_doctor_fix.py::test_doctor_json_report` |

#### Evidence required
- Quality gate output.
- Demo: `walk doctor --fix --strict` on the bootstrapped demo repo → sections `tools`, `providers`, `skills: ok`, `approved: ok`, `versions: ok`, `lints: none`, exit 0.

#### Notes
- ADR-0009 D-10; ADR-0013 D-5; ADR-0011 consequence (`walk doctor` validates `models.yaml`).
- `NEW NAME:` `DoctorReport`, `walk.cli.lints`, `PROVIDER_NAME_PATTERN`.
- Commit subject: `feat: add doctor fix and strict lint modes (E02-S15)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-S16 — Epic gate: bootstrap → doctor → skills → approval → override (e2e)

**Status:** TODO
**Type:** feat
**Requirements:** §24, §25, §26, §28, §31, §32, §33, §91, §92, §93, §136, §137
**Depends on:** E02-S15, E02-S13, E02-S12, E02-S09
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end test module proves the Production Kit: a fresh repository is bootstrapped, validated, projected, protected and overridable exactly as the epic gate describes.

#### Scope
- In: `tests/e2e/test_e02_gate.py`, shared e2e fixtures, CLI invocation helper, documentation of the gate transcript.
- Out: any new kernel behaviour (defects found here become `E02-B*` stories via E02-R01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/conftest.py` | modify | `bootstrapped_repo`, `cli` (typer `CliRunner` wrapper returning exit code + stdout), `kernel_with_fakes` |
| `tests/e2e/test_e02_gate.py` | create | — |
| `docs/02-work-breakdown/EPIC-02-production-kit.md` | modify | — (Evidence section of this story) |

#### Interface contract
```python
# tests/e2e/conftest.py
@pytest.fixture
def bootstrapped_repo(tmp_game_repo: Path) -> Path:
    """tmp_game_repo (E01) + GDD/combat.md + `walk bootstrap --provider local --key DEMO --name Demo --yes` executed."""


@pytest.fixture
def kernel_with_fakes(bootstrapped_repo: Path) -> KernelHandle:
    """build_kernel(KernelSettings(repo_path=…), overrides=KernelOverrides(adapters={'fake-codex': FakeModelAdapter(...), 'fake-claude': FakeModelAdapter(...)}, keyring_backend=FakeKeyringBackend()))."""
```

#### Behavior
Each gate assertion is one test; tests run in file order but must not depend on each other's side effects (each uses its own fixture instance).
1. Bootstrap creates every `[MVP]` + `agents/` path of ARCHITECTURE §8, `.ai/.gitignore`, `kernel.db`, `production-kit.yaml`, pins.
2. `walk doctor` exits 0 (git present in CI image; unity MISSING is not required) and `environment.yaml` validates.
3. `walk skills sync` then `walk skills check-drift --strict` exits 0; lock has `claude` and `codex` entries.
4. Editing one Claude projection file then `walk skills check-drift --strict` exits 1 and names the skill.
5. A `FakeModelAdapter` script for LEAD_DEV emits `TOOL_CALL_REQUESTED(tool="git.merge_protected")`; after one tick the run is `PAUSED_FOR_APPROVAL`, `walk approvals --pending` lists `APV-0001`; `walk approve APV-0001` → run completes; ledger contains `APPROVAL_REQUESTED`, `APPROVAL_DECIDED`, `TOOL_INVOKED`.
6. `walk pause` then `walk resume` → two `USER_OVERRIDE` events with commands `pause`, `resume`.
7. A fake SENIOR_DEV run whose scripted tool writes `.ai/agents/roles/senior_dev.md` ends `FAILED_BOUNDARY`, the file change is reverted, `TOOL_DENIED` ledger event present.
8. A project hook `project.echo` on `on_project_start` appears in `HOOK_EXECUTED` after `walk run --once`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given fresh repo When bootstrap Then full tree per Behavior 1 | `tests/e2e/test_e02_gate.py::test_bootstrap_creates_production_kit` |
| 2 | Given bootstrapped repo When `walk doctor` Then exit 0 and manifest file valid | `tests/e2e/test_e02_gate.py::test_doctor_passes_and_writes_manifest` |
| 3 | Given sync When `check-drift --strict` Then exit 0 with both providers in lock | `tests/e2e/test_e02_gate.py::test_skill_projections_clean_for_both_providers` |
| 4 | Given edited projection When `check-drift --strict` Then exit 1 naming skill | `tests/e2e/test_e02_gate.py::test_edited_projection_detected_as_modified` |
| 5 | Given fake run requesting protected action When tick + approve Then run completes with approval trail | `tests/e2e/test_e02_gate.py::test_protected_action_pauses_and_approval_resumes` |
| 6 | Given `walk pause`/`walk resume` Then two `USER_OVERRIDE` events | `tests/e2e/test_e02_gate.py::test_pause_resume_recorded_as_user_override` |
| 7 | Given fake run writing under `.ai/agents/roles/` Then `FAILED_BOUNDARY` and change reverted | `tests/e2e/test_e02_gate.py::test_boundary_auditor_rejects_agents_dir_write` |
| 8 | Given project hook on `on_project_start` When `walk run --once` Then `HOOK_EXECUTED` for `project.echo` | `tests/e2e/test_e02_gate.py::test_project_hook_executes_on_start` |

#### Evidence required
- Quality gate output including `tests/e2e/test_e02_gate.py` 8 passed.
- Demo transcript (pasted into Evidence): `walk bootstrap … --yes`, `walk doctor`, `walk skills check-drift --strict`, `walk approvals --pending`, `walk approve APV-0001 --note ok`, `walk ledger query --kind USER_OVERRIDE`.

#### Notes
- Gate text: WBS.md §4 E02. Uses only fakes and a real temp git repo (WBS.md §3.6).
- Commit subject: `feat: add epic 02 production kit gate test (E02-S16)`.

#### Evidence (filled by implementer)
_pending_

---

### E02-R01 — Review E02

**Status:** TODO
**Type:** docs
**Requirements:** §24–§29, §31–§33, §91–§93, §105, §137
**Depends on:** E02-S16
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (different model than the implementer of the majority of E02 stories) verifies every E02 story against the Definition of Done and the epic's invariants, and records defects as `E02-B*` bugfix stories.

#### Scope
- In: review of E02-S01…S16 commits; invariant checks 7, 10, 11; MUST-hook completeness; secret hygiene; bugfix story creation.
- Out: fixing defects (bugfix stories), re-planning (planner).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-02-production-kit.md` | modify | — (this task's Evidence; appended `E02-B*` stories) |
| `docs/02-work-breakdown/WBS.md` | modify | — (status rows for E02-R01 and any `E02-B*`) |

#### Interface contract
Reviewer protocol: `docs/00-governance/IMPLEMENTATION-PROTOCOL.md` "Reviewer protocol" steps 1–5. Checklist per story: DoD "Code", "Tests", "Documentation", "Evidence", "Delivery" boxes; per acceptance-criteria row the named test exists and passes (`uv run pytest <nodeid>`).

#### Behavior
1. For every story S01–S16: `git show <sha>` touches only Files-table paths (or the commit body justifies extras); public symbols match the Interface contract; each acceptance test exists by exact name and passes; coverage ≥ 90 % for touched modules (`pytest --cov=walk --cov-report=term-missing`).
2. Invariant 7: every protected action resolves to `REQUIRE_APPROVAL(USER)` and `set-autonomy` is the only path changing `autonomy_level_max`.
3. Invariant 10: no code path other than `approve_artifact` writes under `.ai/approved/`; `verify_approved_artifacts` runs at startup.
4. Invariant 11: no provider-specific skill content outside `adapters/*/projector.py`; `walk skills check-drift` clean on the demo repo.
5. MUST hooks: every row of ARCHITECTURE §4.1 is registered in `src/walk/orchestrator/builtin_hooks.py` or listed in the E02-S08 deferral table with a story id; `src/walk/hooks/` imports nothing from `walk.runtime`, `walk.integrations` or `walk.orchestrator` (ADR-0016).
6. Secret hygiene: `grep -rE` over `tests/` and `.ai/` fixtures with `SECRET_PATTERNS` yields only the deliberate test samples inside `tests/memory/test_secrets.py` and `tests/runtime/test_boundary.py`.
7. Each defect → one `E02-Bnn` story using the template, `Depends on: E02-R01`, linked here; `BLOCKER` severity noted when it breaks the gate.
8. Commit `docs: review epic 02 stories s01-s16 (E02-R01)` and push.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each story commit When diffed against its Files table Then no unlisted file without justification | `tests/e2e/test_e02_gate.py::test_bootstrap_creates_production_kit` (re-run as part of review; manual check recorded in Evidence) |
| 2 | Given each acceptance row When `pytest <nodeid>` Then passes | `tests/e2e/test_e02_gate.py::test_doctor_passes_and_writes_manifest` |
| 3 | Given the demo repo When `walk doctor --strict` Then exit 0 | `tests/cli/test_cmd_doctor_fix.py::test_strict_clean_exit_zero` |
| 4 | Given §4.1 table When compared with `walk.orchestrator.builtin_hooks` + deferral table Then every row accounted for | `tests/hooks/test_builtins.py::test_all_must_hooks_registered_required_low_priority` |
| 5 | Given fixtures When scanned for secrets Then only deliberate samples | `tests/memory/test_secrets.py::test_contains_secret_patterns_and_negative` |

#### Evidence required
- Gate output of the full suite on `main` after the last E02 story.
- Table in Evidence: story → sha → DoD result → defects (ids).
- `walk doctor --strict` transcript on the demo repo.

#### Notes
- Reviewer must be a different agent instance/model than the implementer of ≥ 50 % of E02 stories (IMPLEMENTATION-PROTOCOL, §23).
- Do not fix in place; create `E02-B*` stories.

#### Evidence (filled by implementer)
_pending_

---

### E02-B01 — Subprocess runner resolves Windows `.cmd`/`.bat` shims

**Status:** DONE (1960027)
**Type:** bugfix
**Requirements:** §26, §27, §91
**Depends on:** E02-S02
**Effort:** MEDIUM   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
On Windows, tools installed as npm or other batch shims (`codex.cmd`, `graphify.cmd`, …) are found and run by the shared `AsyncioSubprocessRunner`, so `walk doctor` reports them READY instead of MISSING. A batch shim never receives an argument that `cmd.exe` would reinterpret.

#### Scope
- In: executable resolution in `AsyncioSubprocessRunner.run` (`shutil.which`, `PATHEXT`), the batch-argument guard, the same guard in `AsyncioCodexProcessLauncher` (which already resolves through `shutil.which` but passes arguments unchecked), a shim test helper.
- Out: the Claude CLI (the SDK transport resolves it and rejects batch CLIs itself, E02-S01 Evidence); the Unity editor path (E03-S10); `doctor --fix` (E02-S15); the agent environment variables a shim needs (E02-B02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/subprocess.py` | modify | `AsyncioSubprocessRunner.run`, `resolve_executable`, `unsafe_batch_argument`, `BATCH_UNSAFE_CHARS` |
| `src/walk/model_router/adapters/codex/process.py` | modify | — (`launch` and `_quick` refuse unsafe arguments to a resolved `.cmd`/`.bat`; local copy of the check, `model_router` may not import `integrations`) |
| `tests/fakes/fake_shim.py` | create | `write_shim` (a `.cmd` file on Windows, an executable `#!/bin/sh` script elsewhere) |
| `tests/integrations/test_subprocess.py` | modify | — |
| `tests/integrations/test_preflight.py` | modify | — |
| `tests/model_router/adapters/codex/test_process.py` | create | — |

#### Interface contract
```python
# src/walk/integrations/subprocess.py
BATCH_UNSAFE_CHARS: str = '%!"&|<>^\r\n'  # characters cmd.exe re-parses in batch-file arguments
_EXIT_REFUSED: Final = 126  # POSIX "found but cannot be executed"


def resolve_executable(name: str, env: Mapping[str, str] | None) -> str | None:
    """Absolute path of `name`: `shutil.which(name, path=<PATH of env when env is given and has one,
    else the kernel's PATH>)`. On Windows `shutil.which` applies the kernel's PATHEXT, so `codex`
    finds `codex.cmd`; the env PATH key is matched case-insensitively there. None when not found."""


def unsafe_batch_argument(executable: str, args: list[str]) -> int | None:
    """Index of the first arg containing a BATCH_UNSAFE_CHARS character when `executable` ends with
    .cmd/.bat (case-insensitive); None otherwise. Pure; independent of the running platform."""
```
`SubprocessRunner.run` keeps its signature and its "a non-zero exit is a result" contract (INTERFACES unchanged).

#### Behavior
1. `run` resolves `argv[0]` with `resolve_executable(argv[0], env)` and spawns the resolved path with `argv[1:]`; `SubprocessResult.argv` keeps the argv as given.
2. Not found → exit 127, stderr `executable not found: <name>`, nothing spawned (the existing convention, now decided before spawning).
3. `unsafe_batch_argument(resolved, argv[1:])` not None → exit 126, stderr `refused: argument <index> is unsafe for batch file <name>`, nothing spawned. Callers already treat non-zero as failure: a detector reports MISCONFIGURED with that detail, and git raises `GitError` (`git.exe` is never a shim). This prevents argument injection through `cmd.exe` (the CVE-2024-24576 class).
4. When `env` is given, the lookup uses its `PATH`, because the child runs with that environment. Without `env`, or when it lacks `PATH`, the lookup uses the kernel's `PATH`.
5. `AsyncioCodexProcessLauncher.launch` applies rule 3 to its resolved executable and raises `PermissionError` (an `OSError`, so `CodexAdapter` maps it to `ProviderUnavailable` as it does today); `_quick` returns `(False, <message>)`.
6. On POSIX the behaviour is unchanged apart from rule 4 (`shutil.which` with the same PATH that `exec` would search).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given Windows and a temp dir on PATH holding `fake-tool.cmd` that prints `fake-tool 1.2.3` When `run(["fake-tool", "--version"])` Then exit 0 and stdout contains `1.2.3` | `tests/integrations/test_subprocess.py::test_run_resolves_windows_cmd_shim` |
| 2 | Given a shim only on `env["PATH"]` (not on the kernel PATH) When `run([...], env=env)` Then it is found and exits 0 | `tests/integrations/test_subprocess.py::test_run_resolves_against_the_env_path` |
| 3 | Given an unknown executable When `run` Then exit 127 and stderr starts with `executable not found` | `tests/integrations/test_subprocess.py::test_run_unknown_executable_reports_127` |
| 4 | Given Windows and a `.cmd` shim that writes a marker file When `run([shim, "a&b"])` Then exit 126, stderr contains `refused`, and the marker file does not exist | `tests/integrations/test_subprocess.py::test_run_refuses_unsafe_argument_to_batch_shim` |
| 5 | Given `C:/x/codex.CMD` with args `["exec", "a%PATH%"]` Then `unsafe_batch_argument` is 1; given `codex.exe` Then None | `tests/integrations/test_subprocess.py::test_unsafe_batch_argument_detection` |
| 6 | Given Windows and only a `dotnet.cmd` shim on PATH When `detect_dotnet(AsyncioSubprocessRunner())` Then READY with its version | `tests/integrations/test_preflight.py::test_detect_reports_ready_for_cmd_shim` |
| 7 | Given Windows and a `codex.cmd` shim When `launch` gets an argument containing `&` Then `PermissionError` and no process is started | `tests/model_router/adapters/codex/test_process.py::test_launch_refuses_unsafe_argument_to_batch_shim` |

#### Evidence required
- Quality gate output.
- Demo on the owner's Windows host with Codex installed through npm: `walk doctor` shows `providers.codex  ready  <version>` (E02-S02 Evidence showed `missing`).

#### Notes
- Found in E02-S02 Evidence ("Windows `.cmd` shims"). `create_subprocess_exec` hands a bare name to `CreateProcess`, which does not apply `PATHEXT`.
- Windows-only tests use `@pytest.mark.skipif(sys.platform != "win32", reason="Windows shim")`, not `integration`. AC 2, 3 and 5 run everywhere.
- A `.cmd` child needs `SystemRoot`/`ComSpec` in its environment. Tests that pass an explicit `env` include them; agent spawns get them from E02-B02.
- `NEW NAME:` `resolve_executable`, `unsafe_batch_argument`, `BATCH_UNSAFE_CHARS` (`walk.integrations.subprocess`), exit code 126 for a refused batch call, `tests/fakes/fake_shim.py` (`write_shim`).
- Commit subject: `bugfix: resolve windows batch shims in subprocess runner (E02-B01)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12.11):
```
364 files already formatted
All checks passed!
Success: no issues found in 362 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.84%
1142 passed, 3 deselected in 415.46s (0:06:55)
```
Touched modules: `integrations/subprocess.py` 100 %, `model_router/adapters/codex/process.py` 100 %.
All seven acceptance tests pass on this Windows host (AC 1, 4, 6 and 7 are `skipif(sys.platform != "win32")`; AC 2, 3 and 5 run everywhere).

Demo on a temporary git repository outside this repository. Codex is **not installed** on this host, and this batch's instructions forbid running real provider CLIs, so the owner-host demo with npm Codex was replaced by a fake `codex.cmd` batch shim (answers `--version` and `exec --help` with the ADR-0014 flags) put first on `PATH`:
```
$ PATH="<scratch>/b01shims:$PATH" walk doctor --repo <tmp>/game
component                                state          version   detail
---------------------------------------  -------------  --------  ------------------------------------------------------
tools.git                                ready          2.41.0
tools.graphify                           ready          0.9.48
tools.dotnet                             ready          10.0.100
providers.codex                          ready          0.160.1
  providers.codex: missing -> ready 0.160.1
exit=0
```
Before this change the same probe gave `providers.codex  missing  executable not found: codex` (E02-S02 Evidence). The real npm-Codex demo is still open for the owner's host.

Level-0 decisions:
- **Refusal message index.** `unsafe_batch_argument` returns an index into `args` (`argv[1:]`), as AC 5 fixes. The stderr message `refused: argument <n> is unsafe for batch file <name>` reports the **argv position** (`n = index + 1`), so `run([shim, "a&b"])` says `argument 1`. `AsyncioCodexProcessLauncher` uses the same numbering in its `PermissionError`.
- **One lookup per call.** `run` resolves `argv[0]` once, then decides 127 / 126 / spawn. A `FileNotFoundError` from the spawn itself (the file vanished after the lookup) is still reported as 127, with the OS reason appended.
- **Codex launcher.** The local copy is a private `_spawnable(executable, args)` (resolve, then refuse). `launch` raises `PermissionError`, and `_quick` catches `FileNotFoundError` and `PermissionError` and returns `(False, <message>)`. The probe arguments are constants, so a refusal there cannot happen in practice. `launch` keeps resolving on the kernel's `PATH` (Behavior 4 applies to the runner only).
- **`write_shim(directory, name, *, output, marker=None) -> Path`.** On Windows it writes `<name>.cmd` with `@echo off`, `echo <output>` and, with `marker`, `type nul > "<marker>"`. Elsewhere it writes an executable `#!/bin/sh` script.
- **No re-export.** The new names stay in `walk.integrations.subprocess`. `walk/integrations/__init__.py` is not in the Files table.

File outside the Files table (named in the commit body): `tests/model_router/adapters/claude/test_adapter.py::test_sdk_client_available_checks_cli`. The test patches the global `shutil.which` with a one-argument lambda that answers `sys.executable` for **every** name. The runner it uses as a probe now calls `shutil.which(name, path=...)`, so the lambda raised `TypeError`, and it would also have resolved `no-such-cli.exe` to Python. The stub now answers only the `claude` lookup and delegates every other name to the real `which`. All assertions are unchanged.

---

### E02-B02 — Agent environment allowlist keeps the Windows variables provider CLIs need

**Status:** DONE (e5e5a7d)
**Type:** bugfix
**Requirements:** §91, §139
**Depends on:** E02-S01
**Effort:** LOW   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
On Windows, the Claude and Codex CLIs, and the tools they spawn, start under the scrubbed agent environment, because the allowlist also keeps the non-secret Windows system variables they need. The POSIX allowlist is unchanged, and no credential can pass on any platform.

#### Scope
- In: `WINDOWS_AGENT_ENV_ALLOWLIST`, platform-aware `scrubbed_env`, a guard test that no allowlist entry can match a credential, a Windows round-trip check of both CLIs.
- Out: shim resolution (E02-B01); the ARCHITECTURE §6 text (E02-B03); provider login (outside the kernel).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/sandbox.py` | modify | `WINDOWS_AGENT_ENV_ALLOWLIST`, `scrubbed_env` (keyword `platform`) |
| `tests/runtime/test_sandbox_env.py` | modify | — |

#### Interface contract
Checked against the code (`src/walk/runtime/sandbox.py`). `AGENT_ENV_ALLOWLIST` already holds `PATH`, `HOME`, `TMP`, `TEMP`, `USERPROFILE`, `SYSTEMROOT` and `UNITY_*`, and Windows comparison is already case-insensitive. Missing are `APPDATA`, `LOCALAPPDATA`, `PATHEXT` and `COMSPEC`.
```python
# src/walk/runtime/sandbox.py
WINDOWS_AGENT_ENV_ALLOWLIST: tuple[str, ...] = ("APPDATA", "LOCALAPPDATA", "PATHEXT", "COMSPEC")


def scrubbed_env(os_env: Mapping[str, str], *, platform: str = sys.platform) -> dict[str, str]:
    """AGENT_ENV_ALLOWLIST, plus WINDOWS_AGENT_ENV_ALLOWLIST when platform == "win32"; keys compare
    case-insensitively on win32 (`ComSpec`, `SystemRoot` match); values and key spelling copied verbatim."""
```

#### Behavior
1. On `win32` both lists apply; on every other platform only `AGENT_ENV_ALLOWLIST` applies, and the output for a given environment is unchanged.
2. `DefaultAgentExecutor` keeps calling `scrubbed_env(os.environ)`; the Claude transport and the Codex launcher receive the result unchanged (E02-S01 Behavior 7).
3. No allowlist entry, exact or glob, matches a `CREDENTIAL_NAMES` entry or a name containing `KEY`, `TOKEN`, `SECRET` or `PASSWORD`. A test enforces this, so a later addition cannot leak a credential.
4. A variable is added to either list only with evidence from AC 5 (a CLI fails without it) and only if it satisfies rule 3. Variables such as `USERNAME`, `WINDIR` or `PROGRAMDATA` are not added on speculation.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given an env with `APPDATA`, `LOCALAPPDATA`, `PATHEXT`, `ComSpec`, `SystemRoot` and `PATH` When `scrubbed_env(env, platform="win32")` Then all six are kept with their original key spelling | `tests/runtime/test_sandbox_env.py::test_scrubbed_env_keeps_windows_system_variables_on_win32` |
| 2 | Given the same env When `scrubbed_env(env, platform="linux")` Then `APPDATA`, `LOCALAPPDATA`, `PATHEXT`, `ComSpec` are dropped | `tests/runtime/test_sandbox_env.py::test_scrubbed_env_posix_ignores_windows_list` |
| 3 | Given `ANTHROPIC_API_KEY`, `JIRA_API_TOKEN`, `OPENAI_API_KEY`, `GITHUB_TOKEN` in the env When `scrubbed_env(env, platform="win32")` Then none of them is present | `tests/runtime/test_sandbox_env.py::test_scrubbed_env_drops_secrets_on_win32` |
| 4 | Given both allowlists When matched against every `CREDENTIAL_NAMES` entry and the words `KEY`, `TOKEN`, `SECRET`, `PASSWORD` Then no entry matches | `tests/runtime/test_sandbox_env.py::test_allowlist_never_matches_a_credential_name` |
| 5 | Given Windows with the CLI installed (skipped otherwise) When `claude --version` and `codex --version` run with exactly `scrubbed_env(os.environ)` Then each exits 0 | `tests/runtime/test_sandbox_env.py::test_provider_clis_start_with_scrubbed_env_on_windows` |

#### Evidence required
- Quality gate output.
- AC 5 transcript on the owner's Windows host (`uv run pytest -m integration tests/runtime/test_sandbox_env.py -k windows -v`), listing which CLIs ran and which were skipped as not installed.

#### Notes
- Raised in E02-S01 Evidence ("For the owner / architect"). The variables come from how the CLIs start on Windows: `PATHEXT` and `COMSPEC` are needed by Node's and Rust's process spawning (shell and `.cmd` children), and `APPDATA`/`LOCALAPPDATA` by npm-installed CLIs and their config lookup.
- AC 5 is `@pytest.mark.integration` and `skipif(sys.platform != "win32")`; it makes no model call and needs no login.
- ADR-0009 D-8; ARCHITECTURE §6 "Secret isolation" (text updated by E02-B03).
- `NEW NAME:` `WINDOWS_AGENT_ENV_ALLOWLIST`, `scrubbed_env(..., platform=)`.
- Commit subject: `bugfix: keep windows system variables in agent environment (E02-B02)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12.11):
```
364 files already formatted
All checks passed!
Success: no issues found in 362 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.84%
1146 passed, 5 deselected in 422.80s (0:07:02)
```
Touched module: `runtime/sandbox.py` 100 % in the full suite. AC 1–4 pass. AC 5 (`test_provider_clis_start_with_scrubbed_env_on_windows`, parametrized `[claude]` and `[codex]`) is `integration` + `skipif(sys.platform != "win32")`. It is deselected by the gate and collects correctly (`pytest --collect-only -m integration -k windows` lists both cases).

**AC 5 transcript: not run in this batch.** This batch's instructions forbid running real provider CLIs, and AC 5 runs `claude --version` and `codex --version`. On this host `claude` is installed (`~/.local/bin/claude.exe`) and `codex` is not, so `[codex]` would skip as not installed. The owner runs `uv run pytest -m integration tests/runtime/test_sandbox_env.py -k windows -v` to close this evidence item.

Level-0 decisions:
- **`platform` default.** The contract fixes `platform: str = sys.platform`, which is evaluated once at import. That is correct at run time, because the platform never changes. The E02-S01 test `test_scrubbed_env_case_rules_follow_platform` patched `sys.platform` after import, so it now passes `platform="win32"` / `platform="linux"` instead. Its assertions are unchanged.
- **Codex env test.** `test_codex_subprocess_env_is_scrubbed` checks that every key the launcher receives is allowlisted. On win32 its allowed set now also includes `WINDOWS_AGENT_ENV_ALLOWLIST`. Equality with `scrubbed_env(os.environ)` and the absence of the sentinel secrets are still asserted.
- **AC 4 matching.** Each entry of both lists is matched, upper-cased and with `fnmatch` semantics, against every `CREDENTIAL_NAMES` entry and the bare words `KEY`, `TOKEN`, `SECRET`, `PASSWORD`. No entry text may contain those words. In addition, every credential name passed through `scrubbed_env` on `win32` and `linux` comes out empty.
- **AC 5 runner.** The test resolves the CLI against the scrubbed `PATH` (`resolve_executable`, E02-B01) and skips when it is absent. It runs `<cli> --version` through `AsyncioSubprocessRunner` with `env=scrubbed_env(os.environ)` and a 60 s timeout.

For the owner / architect: the existing glob `UNITY_*` (E02-S01, kept unchanged because Behavior 1 freezes the POSIX output) lets through any `UNITY_`-prefixed variable. That includes the Unity CI licensing secrets `UNITY_PASSWORD`, `UNITY_SERIAL` and `UNITY_LICENSE` (the game-ci convention). AC 4 passes as specified, because it matches entries against credential *names*. Behavior 3's wider wording ("a name containing ... PASSWORD") is not true of the glob, though. Narrowing the glob, or adding a credential-word deny filter, changes the POSIX output and needs a story decision. E02-S14 (security hardening) is the natural place.

---

### E02-B03 — ARCHITECTURE §6: Claude runs as a CLI subprocess under the scrubbed environment

**Status:** DONE (aba2c85)
**Type:** bugfix
**Requirements:** §91, §139
**Depends on:** E02-S01, E02-B02
**Effort:** LOW   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
ARCHITECTURE §6 and ADR-0009 D-8 describe the real process model. The Claude Agent SDK spawns the Claude Code CLI as a subprocess through the kernel's `scrubbed_transport` (E02-S01), so the environment allowlist and its threat model cover both provider CLIs and every tool process they spawn.

#### Scope
- In: the §6 "Secret isolation" row, a residual-risk sentence, the ADR-0009 D-8 consequence for `ANTHROPIC_API_KEY`, ADR-0004 D-7 transport mention, a docs test keeping §6 in sync with the allowlist.
- Out: any code change (the transport exists since E02-S01; the allowlist changes in E02-B02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/01-architecture/ARCHITECTURE.md` | modify | — (§6 "Secret isolation" row) |
| `docs/01-architecture/adr/ADR-0009-runtime-topology-and-open-questions.md` | modify | — (D-8: `ANTHROPIC_API_KEY` is reported, never injected into an agent subprocess) |
| `docs/01-architecture/adr/ADR-0004-model-adapter-boundary-and-handover.md` | modify | — (D-7: the CLI subprocess is launched through `scrubbed_transport`) |
| `tests/docs/test_architecture_security.py` | create | — |

#### Interface contract
No code interface. Target wording of the §6 "Secret isolation" mechanism cell:
- Credentials: unchanged sentence (`CredentialStore`: environment, then OS keyring; never `.ai/`; write-time secret scan).
- Process model: both providers run as **subprocesses** of the kernel. Codex is `codex exec` through `CodexProcessLauncher`; Claude is the Claude Code CLI, which the Agent SDK spawns through the kernel's `scrubbed_transport`. Each child gets exactly `scrubbed_env(os.environ)`, with nothing inherited: `AGENT_ENV_ALLOWLIST` (`PATH`, `HOME`, `TMP`, `TEMP`, `USERPROFILE`, `SYSTEMROOT`, `UNITY_*`) plus `WINDOWS_AGENT_ENV_ALLOWLIST` on Windows. Every process the CLI starts for the agent (shell and Bash tools) inherits that environment.
- Authentication: both CLIs authenticate with their own login state (`codex login`, `claude login`). The kernel injects no provider key, because a key in the CLI environment would be readable by the agent's shell tools. `ANTHROPIC_API_KEY` is resolved by `CredentialStore` for presence reporting only.
- Residual risk: the CLI login state is a file in the user's home directory. A provider-native shell tool runs as the same OS user and can read it. Command restrictions (`PermissionRule.command_patterns`), the Codex sandbox and the post-run `BoundaryAuditor` limit what an agent does, not what it can read. This is accepted for the single-user local daemon (ADR-0009).

#### Behavior
1. §6 no longer says the Claude SDK "runs inside the kernel process"; it states the subprocess model and the scrubbing as above.
2. The allowlist in §6 names every entry of `AGENT_ENV_ALLOWLIST` and `WINDOWS_AGENT_ENV_ALLOWLIST` (AC 2 keeps them in sync).
3. ADR-0009 D-8 gains a dated consequence line: `ANTHROPIC_API_KEY` is never passed to an agent subprocess, and Claude authenticates through `claude login`.
4. ADR-0004 D-7 names `scrubbed_transport` as the launcher of the Claude CLI.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given ARCHITECTURE §6 When reading the "Secret isolation" row Then it contains `subprocess` and `scrubbed_transport` and not `inside the kernel process` | `tests/docs/test_architecture_security.py::test_secret_isolation_row_describes_cli_subprocesses` |
| 2 | Given `AGENT_ENV_ALLOWLIST` and `WINDOWS_AGENT_ENV_ALLOWLIST` When reading the same row Then every entry appears in it | `tests/docs/test_architecture_security.py::test_secret_isolation_row_lists_the_agent_allowlist` |
| 3 | Given ADR-0009 When reading D-8 Then it states that `ANTHROPIC_API_KEY` is not passed to agent subprocesses | `tests/docs/test_architecture_security.py::test_adr_0009_states_no_provider_key_injection` |

#### Evidence required
- Quality gate output (the docs tests run in the normal suite).
- The diff of the §6 row in the commit body.

#### Notes
- Raised in E02-S01 Evidence ("For the owner / architect"). The SDK's own `env` option merges onto the inherited environment, which is why E02-S01 replaced the transport.
- Commit subject: `bugfix: describe claude cli subprocess in security model (E02-B03)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Windows 11 host, Python 3.12.11):
```
364 files already formatted
All checks passed!
Success: no issues found in 363 source files
Contracts: 20 kept, 0 broken.
Required test coverage of 85% reached. Total coverage: 99.84%
1149 passed, 5 deselected in 418.67s (0:06:58)
```
`tests/docs/test_architecture_security.py`: 3 passed (AC 1–3). No source module changed.

The diff of the §6 "Secret isolation" row is in the commit body. Before the change, the row said that the Claude SDK "runs inside the kernel process" and listed `PATH`, `HOME`, `TMP` and "Unity vars". After the change, it describes:
- the subprocess model for both providers (`CodexProcessLauncher`; the Claude Code CLI via `scrubbed_transport`);
- `scrubbed_env(os.environ)` with every entry of `AGENT_ENV_ALLOWLIST` and `WINDOWS_AGENT_ENV_ALLOWLIST`, inherited by the CLI's shell tools;
- authentication through `codex login` / `claude login`, with `ANTHROPIC_API_KEY` used for presence reporting only;
- the residual risk: login state is readable by a same-user shell tool, accepted for the single-user daemon.

ADR-0009 D-8 now says `ANTHROPIC_API_KEY` is used for "presence reporting only" instead of "optional; Claude SDK may also use its own login". It also has a dated consequence: *(2026-10-07, E02-B03)* `ANTHROPIC_API_KEY` is never passed to an agent subprocess. ADR-0004 D-7 gains one sentence naming `scrubbed_transport` as the launcher of the Claude Code CLI subprocess. The rest of D-7 is unchanged.

Level-0 decisions:
- **Row lookup.** The docs tests find a table row by its first cell (`| Secret isolation |`, `| D-8 |`) and require exactly one such row, so a duplicated or renamed row fails loudly.
- **Allowlist check.** It reads `AGENT_ENV_ALLOWLIST` and `WINDOWS_AGENT_ENV_ALLOWLIST` from `walk.runtime.sandbox` and requires each entry as inline code (`` `UNITY_*` ``), so a future allowlist change fails the test until §6 is updated.
- **ADR-0009 sentence.** AC 3 matches the exact sentence `` `ANTHROPIC_API_KEY` is never passed to an agent subprocess `` plus `claude login` in the D-8 row.
