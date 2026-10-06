# EPIC-01 — Kernel Core

**Roadmap stage:** §135 Stage 1 · **Status:** TODO · **Owner:** planning (2026-10-05)

## Goal
A runnable `walk` kernel process that persists workflow state in SQLite, drives one agent run through a `ModelAdapter` (Fake, Claude, Codex) with permission enforcement, budgets, checkpoints, fallback + handover, and records everything in the ledger.

## Requirements covered
§4, §6.1, §6.2, §6.8, §6.11, §7–§9, §12–§23, §30, §31 (enforcement point), §40 (skeleton), §41, §47, §52–§54, §57–§58, §60 (worktree per run), §66 (data model), §76 (data model), §81–§82, §84–§86, §87 (status), §89–§90, §122, §125–§126, §128, §137 (Inv. 1, 2, 9, 12), §138 (Model Lock-In, Tool Failure), §139 (spike).

## Epic gate
`tests/e2e/test_e01_gate.py`: `build_kernel` with two `FakeModelAdapter`s; a STORY in `READY` is scheduled, runs to `FINAL_OUTPUT(COMPLETED)` with 12 tool calls (→ 2 periodic checkpoints + WIP commits), transitions to `READY_FOR_REVIEW`; a second STORY's run is scripted to fail with `PROVIDER_OUTAGE` after 3 tool calls → fallback to the second fake with a `Handover`, second run continues and completes; `walk status --json`, `walk ledger query`, `walk work show` reflect all of it; import-linter contracts pass.

## Story index

| ID | Title | Depends on | Effort |
|---|---|---|---|
| E01-S01 | Project scaffold, `walk.common`, quality gate, `walk --version` | none | HIGH |
| E01-S02 | Provider CLI/SDK spike → ADR-0014 | none | MEDIUM |
| E01-S03 | SQLite `Database`, `MigrationRunner`, `0001_init.sql`, `walk db migrate/backup` | E01-S01 | HIGH |
| E01-S04 | `UnitOfWork`, `Repository[T]`, `IdSequenceStore`, `IdempotencyStore` | E01-S03 | MEDIUM |
| E01-S05 | Execution ledger: `LedgerManager`, `walk ledger tail/query` | E01-S04 | MEDIUM |
| E01-S06 | `TelemetryManager` and `EvidenceManager` | E01-S05 | MEDIUM |
| E01-S07 | Hooks runtime core: `HookManager` | E01-S05 | MEDIUM |
| E01-S08 | Work-item aggregates, repository, `WorkflowManager.create/get/query`, `walk work list/show` | E01-S04, E01-S05 | HIGH |
| E01-S09 | `StateMachine`, YAML tables, guard registry, `raise_event`, `story_workflow`, `walk work transition` | E01-S07, E01-S08 | HIGH |
| E01-S10 | `feature_workflow`/`bug_workflow` tables, remaining guards, DoR, `ready_items`, done dimensions | E01-S09 | HIGH |
| E01-S11 | Phases and release candidates: models, tables, `walk phase list/start/gate` | E01-S09 | MEDIUM |
| E01-S12 | Budgets and cost: `BudgetManager`, `CostManager`, `walk cost` | E01-S05, E01-S07 | HIGH |
| E01-S13 | Effort resolution: `EffortManager` | E01-S10, E01-S12 | MEDIUM |
| E01-S14 | Tool and skill catalogues: `ToolRegistry`, `tools.yaml`, `Skill`/`SkillProjector` models | E01-S12 | MEDIUM |
| E01-S15 | Permission policy core: `PermissionManager.decide/rules_for` | E01-S14 | MEDIUM |
| E01-S16 | Memory core: front matter, `MemoryDocument`, atomic `write`, `apply_updates`, handovers, index | E01-S05, E01-S07 | HIGH |
| E01-S17 | Constitutions and runtime policies: loaders, merge rules, MVP role defaults | E01-S13, E01-S15 | HIGH |
| E01-S18 | Agent execution contract: `AgentInput/AgentOutput/Handover`, templates, `instantiate` | E01-S14, E01-S16, E01-S17, E01-S24 | HIGH |
| E01-S19 | `ModelAdapter` protocol, `RunSession`, `AgentEvent`, `FakeModelAdapter` | E01-S18 | MEDIUM |
| E01-S20 | Model router: `CapabilityRegistry`, `models.yaml`, `select`, `classify_error`, costing | E01-S19, E01-S12 | HIGH |
| E01-S21 | `ClaudeAdapter` (claude-agent-sdk) | E01-S19, E01-S02 | HIGH |
| E01-S22 | `CodexAdapter` (`codex exec --json`) | E01-S19, E01-S02 | HIGH |
| E01-S23 | Integration protocols and `GitCliProvider` local operations | E01-S04, E01-S05 | HIGH |
| E01-S24 | Context manager skeleton: mandatory items, token budget, `ContextBundle` | E01-S08, E01-S16 | MEDIUM |
| E01-S25 | Runtime persistence: `AgentRun` repository, `SandboxManager`, `CheckpointManager`, `BoundaryAuditor` | E01-S18, E01-S20, E01-S23 | HIGH |
| E01-S26 | `ToolInvoker`: permission enforcement point, Claude `can_use_tool` bridge, Codex sandbox config | E01-S15, E01-S25, E01-S07, E01-S12 | HIGH |
| E01-S27 | `AgentExecutor` event loop, output validation/repair, `OutputApplier` core | E01-S26, E01-S20, E01-S24, E01-S06 | HIGH |
| E01-S28 | Fallback, handover and recovery | E01-S27 | HIGH |
| E01-S29 | `TaskRouter`, `Scheduler`, `Orchestrator` service | E01-S28, E01-S13, E01-S10, E01-S11 | HIGH |
| E01-S30 | Daemon and composition root: `build_kernel`, `KernelLock`, `CommandConsumer`, `walk run`, `walk status` | E01-S29 | HIGH |
| E01-S31 | Epic gate: kernel loop with fake adapters incl. fallback (e2e), import-linter contracts | E01-S30, E01-S21, E01-S22 | MEDIUM |
| E01-R01 | Review E01 | E01-S31 | MEDIUM |

## Reading order for implementers
1. `AGENTS.md` (repo root), then `docs/00-governance/IMPLEMENTATION-PROTOCOL.md`, `CONVENTIONS.md`, `DEFINITION-OF-DONE.md`, `COMMIT-POLICY.md`.
2. `docs/02-work-breakdown/WBS.md` §2–§3 (binding rules and planning conventions), then this file: the story being implemented, fully.
3. The `§NN` sections the story cites in `requirements/WAL_K_REQ.md` (summary in the story is authoritative when the file is absent).
4. The `INTERFACES.md` / `DOMAIN-MODEL.md` sections and ADRs the story names. Nothing else.

Conventions that apply to every story below (from WBS §3): implementation classes are `Default<Protocol>`; `Capability` lives in `walk.common.enums`; `EffortPolicy` in `walk.effort.models`; `BudgetPolicy` in `walk.budgets.models`; guards read `TransitionContext.payload` keys from WBS §3.4; ledger events are written only at ARCHITECTURE §4.3 write points; all subprocess calls go through `SubprocessRunner`; fakes live in `tests/fakes/`; epic gates in `tests/e2e/`.

---

### E01-S01 — Project scaffold, `walk.common`, quality gate, `walk --version`

**Status:** DONE (54f3361)
**Type:** chore
**Requirements:** §4 (objectives 12, 13), §7, §122, §125, §137 (Inv. 1), §2 (production orchestration kernel, not a coding-agent framework)
**Depends on:** none
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A `uv`-managed Python 3.12 package `walk` exists with the full quality gate green, the `walk.common` primitives every other package imports, shared test fixtures, and a `walk --version` CLI entry point.

#### Scope
- In: `pyproject.toml`, `src/walk/` skeleton, `walk.common` (ids, clock, errors, models, roles, enums), `tests/conftest.py`, `tests/fakes/fake_clock.py`, `tests/fakes/fake_id_factory.py`, `scripts/check.sh`, `scripts/check.ps1`, `.gitignore` additions, `walk --version`.
- Out: persistence (E01-S03), import-linter contracts (E01-S31), any other package.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `pyproject.toml` | create | — |
| `.gitignore` | modify | — |
| `src/walk/__init__.py` | create | `__version__` |
| `src/walk/py.typed` | create | — |
| `src/walk/common/__init__.py` | create | re-exports of all symbols below |
| `src/walk/common/models.py` | create | `WalkModel`, `FrozenModel`, `utcnow`, `JsonDict`, `Actor` |
| `src/walk/common/ids.py` | create | all `Annotated` id types of DOMAIN-MODEL §1.2, `IdFactory`, `new_ulid`, `format_seq_id`, `parse_prefix`, `ULID_PATTERN` |
| `src/walk/common/clock.py` | create | `Clock`, `SystemClock` |
| `src/walk/common/errors.py` | create | `WalkError`, `TransientError`, `ProviderUnavailable`, `RateLimited`, `Timeout`, `QuotaExhausted`, `ToolCrashed`, `PermanentError`, `PermissionDenied`, `GuardRejected`, `OutputInvalid`, `BoundaryViolation`, `ConfigError`, `RecoverableInterruption` |
| `src/walk/common/roles.py` | create | `AgentRole` |
| `src/walk/common/enums.py` | create | `Effort`, `LearningScope`, `ImprovementScope`, `Capability` |
| `src/walk/cli/__init__.py` | create | — |
| `src/walk/cli/app.py` | create | `app`, `main` |
| `tests/__init__.py`, `tests/common/__init__.py`, `tests/cli/__init__.py`, `tests/fakes/__init__.py` | create | — |
| `tests/conftest.py` | create | fixtures `tmp_repo`, `fake_clock`, `sequential_ids` |
| `tests/fakes/fake_clock.py` | create | `FakeClock` |
| `tests/fakes/fake_id_factory.py` | create | `SequentialIdFactory` |
| `tests/common/test_ids.py` | create | — |
| `tests/common/test_clock.py` | create | — |
| `tests/common/test_errors.py` | create | — |
| `tests/common/test_models.py` | create | — |
| `tests/cli/test_app.py` | create | — |
| `tests/test_scaffold.py` | create | — |
| `scripts/check.sh` | create | — |
| `scripts/check.ps1` | create | — |

#### Interface contract
`pyproject.toml` outline (values are normative):
```toml
[project]
name = "walk"; version = "0.1.0"; requires-python = ">=3.12"
dependencies = ["pydantic>=2.7", "typer>=0.12", "pyyaml>=6", "httpx>=0.27", "python-ulid>=2", "keyring>=25", "jinja2>=3.1"]
[project.optional-dependencies]
claude = ["claude-agent-sdk"]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "ruff", "mypy", "import-linter", "types-PyYAML"]
[project.scripts]
walk = "walk.cli.app:main"
[tool.ruff]
line-length = 100; target-version = "py312"; src = ["src", "tests"]
[tool.ruff.lint]
select = ["ALL"]
ignore = ["D203",   # conflicts with D211 (blank line before class docstring)
          "D213",   # conflicts with D212 (summary on first line)
          "COM812", # handled by the formatter
          "ISC001", # handled by the formatter
          "PLR0913",# protocol methods mirror INTERFACES.md signatures with many args
          "ANN401", # JsonDict payloads are Any by contract
          "TD002", "TD003", "FIX002"]  # TODOs carry story ids, not authors/links
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004", "D1", "ARG001", "INP001"]
[tool.mypy]
strict = true; python_version = "3.12"; plugins = ["pydantic.mypy"]
[tool.pytest.ini_options]
asyncio_mode = "auto"; testpaths = ["tests"]
addopts = "--cov=walk --cov-report=term-missing --cov-fail-under=85"
markers = ["integration: needs real external services; skipped by default"]
[tool.coverage.run]
omit = ["scripts/*"]
```
```python
# src/walk/common/ids.py
ULID_PATTERN: str = r"[0-9A-HJKMNP-TV-Z]{26}"
def new_ulid() -> str: ...                                   # 26 Crockford base32 chars, time-ordered (python-ulid)
def format_seq_id(prefix: str, n: int, width: int) -> str: ... # "FEAT", 12, 4 -> "FEAT-0012"; n < 1 -> ValueError
def parse_prefix(id_: str) -> str: ...                        # "FEAT-0012" -> "FEAT"; "OBS-K-0001" -> "OBS-K"; no dash -> ValueError
class IdFactory(Protocol):
    def next_sequence(self, prefix: str) -> str: ...
    def new_ulid(self) -> str: ...
# src/walk/common/clock.py
class Clock(Protocol):
    def now(self) -> datetime: ...          # tz-aware UTC
class SystemClock:
    def now(self) -> datetime: ...
# src/walk/common/models.py — DOMAIN-MODEL §1.1 verbatim (WalkModel, FrozenModel, utcnow, JsonDict, Actor)
# src/walk/common/errors.py — ARCHITECTURE §5.1 taxonomy; every class has a docstring and accepts (message: str, *, detail: JsonDict | None = None)
# src/walk/common/roles.py, enums.py — DOMAIN-MODEL §3 (AgentRole, Effort, LearningScope, ImprovementScope) + Capability (RELOCATE, WBS §3.2)
# src/walk/cli/app.py
app: typer.Typer                            # root; options --repo PATH, --json, --verbose stored in ctx.obj
def main() -> None: ...                     # entry point; `walk --version` prints "walk <__version__>" and exits 0
# tests/fakes
class FakeClock:   def __init__(self, start: datetime) -> None; def now(self) -> datetime; def advance(self, seconds: float) -> None
class SequentialIdFactory: def next_sequence(self, prefix: str) -> str  # FEAT-0001, FEAT-0002 … width from DOMAIN-MODEL §2 table
                           def new_ulid(self) -> str                      # deterministic increasing ULIDs
```

#### Behavior
1. `uv sync --all-extras` succeeds offline for everything except `claude-agent-sdk` (optional extra).
2. `scripts/check.sh` / `check.ps1` run, in order: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src tests`, `uv run pytest`; stop at the first failure; exit code is the failing command's exit code.
3. `new_ulid()` returns 26 characters matching `ULID_PATTERN`; two calls 1 ms apart sort lexicographically in creation order.
4. `format_seq_id` zero-pads to `width` and never truncates (`format_seq_id("EVD", 1234567, 6) == "EVD-1234567"`); `n < 1` raises `ValueError`.
5. `parse_prefix` returns everything before the last `-<digits>` group.
6. Every error class in ARCHITECTURE §5.1 exists with the stated parent; `WalkError.detail` defaults to `{}`.
7. `WalkModel` rejects unknown fields (`extra="forbid"`) and validates on assignment; `FrozenModel` raises on mutation.
8. `Actor` serialises enum members by value.
9. `walk --version` prints `walk 0.1.0`; `walk` with no arguments prints help and exits 0.
10. `tmp_repo` fixture creates a temp directory with `git init -b main`, `user.name`/`user.email` configured, and one initial commit.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the package, When `new_ulid()` is called twice with a 1 ms gap, Then both match `ULID_PATTERN` and the second sorts after the first | `tests/common/test_ids.py::test_new_ulid_is_26_chars_and_time_ordered` |
| 2 | When `format_seq_id("FEAT", 12, 4)`, Then `"FEAT-0012"` | `tests/common/test_ids.py::test_format_seq_id_zero_pads` |
| 3 | When `format_seq_id("X", 0, 4)`, Then `ValueError` | `tests/common/test_ids.py::test_format_seq_id_rejects_non_positive` |
| 4 | When `parse_prefix("OBS-K-0001")`, Then `"OBS-K"`; `parse_prefix("nodash")` raises `ValueError` | `tests/common/test_ids.py::test_parse_prefix_handles_compound_prefix_and_rejects_garbage` |
| 5 | Given `"FEAT-12"`, When validated as `FeatureId`, Then validation error (min width 4) | `tests/common/test_ids.py::test_feature_id_pattern_enforces_min_width` |
| 6 | When `SystemClock().now()`, Then tzinfo is UTC | `tests/common/test_clock.py::test_system_clock_returns_utc_aware` |
| 7 | Given `FakeClock`, When `advance(5)`, Then `now()` moved by 5 s exactly | `tests/common/test_clock.py::test_fake_clock_advances_deterministically` |
| 8 | For every error class, Then `issubclass` matches the ARCHITECTURE §5.1 tree (parametrised over all 13 leaves) | `tests/common/test_errors.py::test_error_hierarchy_matches_taxonomy` |
| 9 | When `WalkModel` subclass receives an unknown field, Then `ValidationError` | `tests/common/test_models.py::test_walk_model_forbids_extra_fields` |
| 10 | When a `FrozenModel` attribute is assigned, Then `ValidationError` | `tests/common/test_models.py::test_frozen_model_is_immutable` |
| 11 | When `Actor(role=AgentRole.QC).model_dump()`, Then `{"role": "QC", "model_id": None, "run_id": None}` | `tests/common/test_models.py::test_actor_serialises_by_value` |
| 12 | When `CliRunner.invoke(app, ["--version"])`, Then exit 0 and output contains `walk 0.1.0` | `tests/cli/test_app.py::test_version_prints_version` |
| 13 | When `scripts/check.sh` and `check.ps1` are read, Then each contains the four gate commands in order | `tests/test_scaffold.py::test_check_scripts_invoke_all_gate_commands` |
| 14 | When `pyproject.toml` is parsed, Then `select == ["ALL"]`, `strict == true`, `asyncio_mode == "auto"`, `--cov-fail-under=85` present | `tests/test_scaffold.py::test_pyproject_enforces_quality_gate` |
| 15 | Given `tmp_repo`, Then `git rev-parse HEAD` succeeds and branch is `main` | `tests/test_scaffold.py::test_tmp_repo_fixture_is_initialised_git_repo` |

#### Evidence required
- Quality gate output (`scripts/check.sh` summary: ruff ok, mypy ok, N passed, coverage %).
- Demo: `uv run walk --version` → `walk 0.1.0`.

#### Notes
- ADR-0001 (stack), ADR-0009 D-1/D-2/D-17 (common package, src layout, ULIDs).
- `RELOCATE: Capability → walk.common.enums` (WBS §3.2); `NEW NAME:` dependency `jinja2` recorded in ADR-0014 by E01-S02.
- Pitfall: `pydantic.mypy` plugin is required for `strict` to accept `Field(default_factory=…)` typing.
- Commit: `chore: scaffold package, common primitives and quality gate (E01-S01)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
26 files already formatted
All checks passed!
Success: no issues found in 23 source files
Required test coverage of 85% reached. Total coverage: 100.00%
33 passed in 1.57s
```
Demo:
```
$ uv run walk --version
walk 0.1.0
```
Level-0 decisions (no contract change):
- `pyproject.toml` uses `hatchling` as build backend, `mypy_path = "src"`, pydocstyle `google`, and pytest `-m 'not integration'` so integration tests are skipped by default (§ markers).
- Extra ruff ignores, each justified inline: `CPY001` (no copyright headers), `N818` (exception names fixed by ARCHITECTURE §5.1), `FBT001/FBT002` for `src/walk/cli/**` (typer boolean flags), `S603/S607` for tests (git subprocess in `tmp_repo`), a tooling ignore set for `scripts/**`, and `extend-exclude = ["docs", "*.md"]` (planning sketches are not formatted code).
- `walk.common.errors` imports `JsonDict` from `walk.common.models` (single definition).
- `walk` with no arguments prints help and exits 0 via an `invoke_without_command` callback (click 8.2 exits 2 for `no_args_is_help`).
- Extra tests beyond the AC table: assignment validation, `utcnow` tz, error `detail` copy, no-args help, `main()` entry point.

---

### E01-S02 — Provider CLI/SDK spike → ADR-0014

**Status:** BLOCKED
**Type:** docs
**Requirements:** §6.1, §17, §21–§22, §128, §139
**Depends on:** none
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
Every Codex CLI flag and Claude Agent SDK option assumed by ADR-0004 D-7/D-8 and ADR-0011 is verified against the installed tools, and the results (verified / deviation / consequence) are recorded in ADR-0014 so E01-S21/S22 implement against facts.

#### Scope
- In: probe scripts, manual execution against real CLIs, ADR-0014, approval of the `jinja2` dependency.
- Out: adapter code (E01-S21, E01-S22).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/01-architecture/adr/ADR-0014-provider-cli-sdk-verification.md` | create | — |
| `scripts/spikes/codex_probe.sh` | create | — |
| `scripts/spikes/claude_probe.py` | create | — |
| `tests/docs/__init__.py` | create | — |
| `tests/docs/test_adr_0014.py` | create | — |

#### Interface contract
ADR-0014 follows `docs/00-governance/ADR-TEMPLATE.md`, `Status: Accepted`, and contains one table per provider with columns `Assumption | Source | Verified (version) | Deviation | Consequence (story)`. Rows required:

| Provider | Assumption rows |
|---|---|
| Codex CLI | `codex exec --json`; `--sandbox workspace-write`; `--cd <dir>`; `-c model=<id>`; `-c model_reasoning_effort=<low\|medium\|high\|xhigh>`; `--output-schema <file>`; `codex exec resume <thread_id>`; JSON event line kinds (thread id event, tool/command events, usage/token event, final message event); exit codes; network disabled by default under `workspace-write` |
| Claude Agent SDK | `query()` options `cwd`, `allowed_tools`, `permission_mode`, `can_use_tool`, `model`, `effort` (`low\|medium\|high\|xhigh\|max`), `max_turns`, `resume`; session id present in result/init messages; usage fields (input/output/cache-read tokens, cost); structured output mechanism (`output_format`/schema) or absence thereof |
| Kernel | `jinja2` approved as runtime dependency (ADR-0004 D-4 templates) |

Probe scripts print each flag probe and its raw output; they are run manually (real CLIs required) and the transcript is pasted into the ADR under "Evidence".

#### Behavior
1. Each assumption row states `Verified` with the tool version, or `Deviation` with the observed behaviour.
2. Every `Deviation` row names the affected story (`E01-S21` or `E01-S22`) and the required mapping change in the adapter.
3. If `--output-schema` is unavailable, the ADR records that `<worktree>/.walk/output.json` is the only output channel for Codex (ADR-0004 D-3 fallback remains the contract).
4. If the SDK lacks `effort`, the ADR records the alternative parameter and E01-S21 maps `Effort` to it.
5. The ADR "Consequences" section lists the ADRs it amends (ADR-0001 dependency list, ADR-0004, ADR-0011) without rewriting them.
6. Probe scripts are excluded from coverage (`[tool.coverage.run] omit`) and never imported by `src/`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the ADR file, When read, Then it has `Status: Accepted` and the ADR-TEMPLATE headings in order | `tests/docs/test_adr_0014.py::test_adr_has_template_structure` |
| 2 | Then every Codex flag string listed in the contract appears in the Codex table | `tests/docs/test_adr_0014.py::test_adr_covers_every_codex_flag` |
| 3 | Then every SDK option string listed in the contract appears in the SDK table | `tests/docs/test_adr_0014.py::test_adr_covers_every_sdk_option` |
| 4 | Then every row whose Deviation cell is non-empty names `E01-S21` or `E01-S22` | `tests/docs/test_adr_0014.py::test_every_deviation_names_affected_story` |
| 5 | Then the ADR contains a `jinja2` row marked Verified/Accepted | `tests/docs/test_adr_0014.py::test_adr_approves_jinja2_dependency` |
| 6 | Then both probe scripts exist and are referenced from the ADR Evidence section | `tests/docs/test_adr_0014.py::test_probe_scripts_exist_and_are_referenced` |

#### Evidence required
- Quality gate output.
- Manual transcript of `scripts/spikes/codex_probe.sh` and `uv run python scripts/spikes/claude_probe.py` pasted into the ADR (versions of `codex --version` and the SDK package).

#### Notes
- Architect flag: ADR-0004 D-8 says "Exact flags are verified in a Stage 1 spike story; the adapter owns the mapping" — this is that story.
- Pitfall: do not store provider transcripts containing repository content; probes run in an empty temp dir.
- Commit: `docs: record provider cli and sdk verification in ADR-0014 (E01-S02)`.

#### Evidence (filled by implementer)
BLOCKED on 2026-10-06 (owner action required, not a planning gap):
- Codex CLI is not installed on the implementation machine, and the runtime rows (JSON event kinds, `codex exec resume`, usage event, exit codes) need an authenticated `codex login` on the owner's OpenAI account.
- The Claude Agent SDK rows (session id, usage and cost fields, structured output) need a real `query()` run, which spends the owner's Claude quota.
- Unblock: owner installs Codex CLI (`npm i -g @openai/codex`), runs `codex login`, and confirms that the probes may spend a few requests on both accounts. Only E01-S21 and E01-S22 depend on this story; E01-S03..S20 proceed.

---

### E01-S03 — SQLite `Database`, `MigrationRunner`, `0001_init.sql`, `walk db migrate/backup`

**Status:** DONE (2edcc6c)
**Type:** feat
**Requirements:** §54, §81, §89, §137 (Inv. 9)
**Depends on:** E01-S01
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The project database `<repo>/.ai/kernel.db` can be created and migrated to the full DOMAIN-MODEL §6.2 schema with WAL mode, pragmas and immutability triggers, from code and from the CLI.

#### Scope
- In: `Database`, `MigrationRunner`, project migration `0001_init.sql`, kernel migration folder with `0001_init.sql` for the kernel DB subset, `walk db migrate`, `walk db backup PATH`.
- Out: `UnitOfWork`/repositories (E01-S04), `KernelLock` (E01-S30), dashboard views (E09-S04), local work provider table (E03-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/persistence/__init__.py` | create | re-exports |
| `src/walk/persistence/database.py` | create | `Database`, `DbKind` |
| `src/walk/persistence/migrations.py` | create | `MigrationRunner`, `Migration` |
| `src/walk/persistence/migrations/__init__.py` | create | — |
| `src/walk/persistence/migrations/project/0001_init.sql` | create | — |
| `src/walk/persistence/migrations/kernel/0001_init.sql` | create | — |
| `src/walk/persistence/errors.py` | create | `MigrationError` |
| `src/walk/cli/cmd_db.py` | create | `db_app` |
| `src/walk/cli/app.py` | modify | registers `db_app` |
| `src/walk/cli/composition.py` | create | `open_database(repo: Path, *, read_only: bool = False) -> Database` |
| `tests/persistence/__init__.py` | create | — |
| `tests/persistence/test_database.py` | create | — |
| `tests/persistence/test_migrations.py` | create | — |
| `tests/cli/test_cmd_db.py` | create | — |
| `tests/conftest.py` | modify | fixture `db` (migrated in-memory/temp project DB) |

#### Interface contract
```python
DbKind = Literal["project", "kernel"]


class Database:
    def __init__(self, path: Path, *, read_only: bool = False) -> None: ...
    @property
    def path(self) -> Path: ...
    def connect(self) -> sqlite3.Connection:
        """Opens (or returns the process-wide) connection with PRAGMA journal_mode=WAL, foreign_keys=ON,
        synchronous=NORMAL, busy_timeout=5000; row_factory=sqlite3.Row; isolation_level=None (explicit BEGIN)."""

    def close(self) -> None: ...
    def backup_to(self, target: Path) -> None: ...  # sqlite3.Connection.backup


class Migration(FrozenModel):
    version: int
    name: str
    sql_path: str
    py_path: str | None


class MigrationRunner:
    def __init__(self, db: Database, kind: DbKind) -> None: ...
    def discover(
        self,
    ) -> list[
        Migration
    ]: ...  # files NNNN_<name>.sql under migrations/<kind>/, sorted, contiguous from 1
    def applied(self) -> list[int]: ...
    def apply_pending(self) -> list[int]:
        """Applies each missing migration in one BEGIN IMMEDIATE transaction per file; inserts schema_migrations row;
        sets PRAGMA user_version = latest; raises ConfigError (wrapping MigrationError) on failure after rollback."""
```
`0001_init.sql` (project) contains exactly the DDL of DOMAIN-MODEL §6.2 for: `schema_migrations, id_sequences, kernel_instances, idempotency_keys, projects, phases, work_items, work_item_transitions, release_candidates, agent_runs, checkpoints, handovers, ledger_events, cost_records, budgets, evidence, decisions, decision_work_items, debates, debate_positions, escalations, approval_requests, approved_artifacts, memory_index, hook_executions, commands, command_results, skill_projections, work_provider_sync, webhook_deliveries, improvement_observations, improvement_candidates, patterns, retrospectives, behavior_versions` with all indexes and the triggers `work_item_transitions_immutable`, `checkpoints_immutable`, `ledger_events_no_update`, `ledger_events_no_delete`, `cost_records_immutable`, `evidence_immutable`, plus `BEFORE DELETE` abort triggers for `work_item_transitions`, `checkpoints`, `cost_records`, `evidence` (ADR-0002 D-3). Kernel `0001_init.sql`: `schema_migrations, id_sequences, improvement_observations, improvement_candidates, patterns, retrospectives, behavior_versions, experiments, kernel_changelog`.

CLI: `walk db migrate` (exit 0, prints applied versions or `up to date`), `walk db backup PATH` (exit 0, prints target path; exit 1 if DB missing).

#### Behavior
1. `connect()` on a missing file creates it and its parent directory `.ai/`; with `read_only=True` it opens `file:…?mode=ro` and never creates.
2. Pragmas are applied on every new connection; `PRAGMA journal_mode` returns `wal`.
3. `discover()` raises `ConfigError` when numbering has a gap or duplicate.
4. `apply_pending()` is idempotent: second call returns `[]` and changes nothing.
5. A failing SQL statement rolls back the whole migration file; `schema_migrations` has no row for it; `user_version` unchanged; `ConfigError` raised with the migration name in `detail`.
6. A paired `NNNN_<name>.py` exposing `migrate(conn)` is executed after its SQL in the same transaction; `backup_to` is called before any migration with a `.py` step.
7. `UPDATE`/`DELETE` on `ledger_events`, `checkpoints`, `cost_records`, `evidence`, `work_item_transitions` raise `sqlite3.IntegrityError` (trigger abort).
8. `walk db migrate` with `--repo` pointing to a dir without `.ai/` creates it (bootstrap proper is E02-S03).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a temp repo, When `Database.connect()`, Then `.ai/kernel.db` exists and `journal_mode == "wal"` and `foreign_keys == 1` | `tests/persistence/test_database.py::test_connect_creates_db_with_wal_and_pragmas` |
| 2 | Given no DB file, When `Database(path, read_only=True).connect()`, Then `ConfigError` and no file created | `tests/persistence/test_database.py::test_read_only_never_creates_file` |
| 3 | When `backup_to(target)`, Then target is a valid SQLite DB with the same tables | `tests/persistence/test_database.py::test_backup_copies_database` |
| 4 | When `apply_pending()` on an empty DB, Then returns `[1]` and every table in the contract list exists | `tests/persistence/test_migrations.py::test_apply_pending_creates_all_tables` |
| 5 | Then `PRAGMA user_version == 1` and `schema_migrations` has one row named `init` | `tests/persistence/test_migrations.py::test_apply_pending_records_version` |
| 6 | When `apply_pending()` again, Then `[]` | `tests/persistence/test_migrations.py::test_apply_pending_is_idempotent` |
| 7 | Given a migrations dir with `0001`, `0003`, When `discover()`, Then `ConfigError` | `tests/persistence/test_migrations.py::test_discover_rejects_gap_in_numbering` |
| 8 | Given an extra migration with invalid SQL, When `apply_pending()`, Then `ConfigError`, no partial objects, `user_version` unchanged | `tests/persistence/test_migrations.py::test_failed_migration_rolls_back` |
| 9 | Given a migration with a `.py` step, When applied, Then `migrate(conn)` ran and a backup file exists | `tests/persistence/test_migrations.py::test_python_step_runs_after_sql_with_backup` |
| 10 | For each of the five append-only tables, When `UPDATE` or `DELETE`, Then `sqlite3.IntegrityError` | `tests/persistence/test_migrations.py::test_append_only_tables_reject_update_and_delete` |
| 11 | When `MigrationRunner(db, "kernel").apply_pending()`, Then kernel tables exist and project-only tables do not | `tests/persistence/test_migrations.py::test_kernel_migrations_create_kernel_subset` |
| 12 | When `walk db migrate --repo <tmp>`, Then exit 0 and output lists `0001_init` | `tests/cli/test_cmd_db.py::test_db_migrate_applies_and_prints` |
| 13 | When `walk db backup <path>` without DB, Then exit 1 | `tests/cli/test_cmd_db.py::test_db_backup_fails_without_database` |

#### Evidence required
- Quality gate output.
- Demo: `walk db migrate --repo ./demo` → `applied: 0001_init`; `walk db migrate --repo ./demo` → `up to date`; `walk db backup ./demo/backup.db` → `backup written: ./demo/backup.db`.

#### Notes
- ADR-0002 D-1/D-2/D-3/D-8; DOMAIN-MODEL §6.
- Pitfall: `isolation_level=None` so `BEGIN IMMEDIATE` is explicit (E01-S04 `UnitOfWork` relies on it). Windows: close connections before `backup_to`/file moves.
- Commit: `feat: add sqlite database and migration runner with initial schema (E01-S03)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21, SQLite 3.49.1):
```
36 files already formatted
All checks passed!
Success: no issues found in 33 source files
Required test coverage of 85% reached. Total coverage: 99.24%
69 passed in 2.31s
```
Touched modules: `persistence/database.py` 100%, `persistence/migrations.py` 97%, `cli/cmd_db.py` 100%, `cli/composition.py` 100%.

Demo (Windows, run in an empty scratch dir):
```
$ walk db migrate --repo ./demo
applied: 0001_init
$ walk db migrate --repo ./demo
up to date
$ walk db backup ./demo/backup.db --repo ./demo
backup written: demo\backup.db
$ walk db backup ./x.db --repo ./nodb
error: database does not exist: nodb\.ai\kernel.db      (exit 1)
```
Deviation from the Files table (no contract change):
- `src/walk/persistence/migrations/__init__.py` is **not** created. A package directory `migrations/` with an `__init__.py` shadows the module `migrations.py` (CPython's path finder prefers the package), which would make `walk.persistence.migrations.MigrationRunner` unimportable. `migrations/` is a plain data folder holding `project/` and `kernel/` SQL files; hatchling ships it in the wheel because it sits inside `src/walk`.

Level-0 decisions:
- The four `BEFORE DELETE` triggers required by ADR-0002 D-3 but absent from DOMAIN-MODEL §6.2 are named `<table>_no_delete` and abort with `'immutable'`. The DDL is otherwise copied verbatim from §6.2; the `-- PK`/`-- K`/`-- dedup` placement markers were dropped.
- Each migration runs as `executescript("BEGIN IMMEDIATE;" + sql)`, then the Python step, the `schema_migrations` row, `PRAGMA user_version`, `COMMIT`. `executescript()` silently commits an open transaction (verified on 3.12), so `BEGIN` has to be inside the script. Migration files must not contain transaction control.
- `applied_at` uses `datetime.now(tz=UTC)`: the contract constructor `MigrationRunner(db, kind)` takes no `Clock`.
- The backup before a Python-step migration is written to `<db>.pre-NNNN.bak` (NNNN = first pending version), overwriting an older one.
- `discover()` also rejects a duplicate version, a `NNNN_<name>.py` without a matching `.sql`, and a missing kind folder (`ConfigError`); files that don't match `NNNN_<name>.(sql|py)` are ignored. The migration root is the private module constant `_MIGRATIONS_ROOT`, which tests monkeypatch.
- `Database.connect()` also turns `OSError` (for example `.ai` exists as a file) and pragma failures (a read-only connection cannot switch a rollback-journal DB to WAL) into `ConfigError`. `check_same_thread` stays at its default; the async `UnitOfWork` (E01-S04) runs on the event-loop thread.
- `open_database()` returns a connected `Database`, so a missing read-only DB fails at open time.
- The global `--repo` is a root-callback option, which click only accepts before the subcommand. `walk db migrate` and `walk db backup` therefore also accept `--repo` after the subcommand (AC 12 syntax); the subcommand value wins, otherwise the global one is used. Errors print `error: <message>` to stderr and exit 1 (INTERFACES §6).
- Also read: INTERFACES §6 (CLI exit codes), ARCHITECTURE §1.2/§2 (package rules, sqlite confinement).

---

### E01-S04 — `UnitOfWork`, `Repository[T]`, `IdSequenceStore`, `IdempotencyStore`

**Status:** DONE (1513909)
**Type:** feat
**Requirements:** §54, §90, §137 (Inv. 9)
**Depends on:** E01-S03
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Transactional building blocks shared by every repository: one SQLite transaction per unit of work, a generic aggregate-JSON repository base, sequence ID allocation inside the transaction, and the idempotency-key store.

#### Scope
- In: `UnitOfWork`, `Repository[T]`, `IdSequenceStore`, `IdempotencyStore`.
- Out: concrete repositories (owning stories), `with_idempotency` facade (E03-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/persistence/uow.py` | create | `UnitOfWork` |
| `src/walk/persistence/repository.py` | create | `Repository` |
| `src/walk/persistence/ids.py` | create | `IdSequenceStore`, `SEQUENCE_WIDTHS` |
| `src/walk/persistence/idempotency.py` | create | `IdempotencyStore`, `IdempotencyRecord` |
| `src/walk/persistence/__init__.py` | modify | re-exports |
| `tests/persistence/test_uow.py` | create | — |
| `tests/persistence/test_repository.py` | create | — |
| `tests/persistence/test_ids.py` | create | — |
| `tests/persistence/test_idempotency.py` | create | — |

#### Interface contract
```python
class UnitOfWork:
    """Async context manager around one SQLite transaction (ADR-0002 D-9)."""

    def __init__(self, db: Database) -> None: ...
    @property
    def conn(self) -> sqlite3.Connection: ...
    async def __aenter__(
        self,
    ) -> "UnitOfWork": ...  # BEGIN IMMEDIATE; nested use raises ConfigError
    async def __aexit__(self, *exc: object) -> None: ...  # COMMIT on success, ROLLBACK on exception
    def after_commit(
        self, fn: Callable[[], Awaitable[None]]
    ) -> None: ...  # hooks fired after COMMIT, in order


T = TypeVar("T", bound=WalkModel)


class Repository(Generic[T]):
    _table: ClassVar[str]
    _model: type[T]
    _key: ClassVar[str] = "id"

    def __init__(self, db: Database) -> None: ...
    def projection(
        self, obj: T
    ) -> dict[str, object]: ...  # subclass hook: indexed columns; default {}
    async def insert(self, obj: T, uow: UnitOfWork) -> T: ...
    async def upsert(self, obj: T, uow: UnitOfWork) -> T: ...
    async def get(self, key: str) -> T | None: ...
    async def list_where(
        self,
        where: str = "1=1",
        params: Sequence[object] = (),
        *,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[T]: ...


SEQUENCE_WIDTHS: dict[
    str, int
]  # DOMAIN-MODEL §2: PHASE 2, EPIC 3, FEAT 4, STORY 4, TASK 4, BUG 4, DEC 4, DEB 4, EVD 6, APR 4, HO 4, APV 4, RC 2, OBS 4, OBS-K 4, IMP 2, PATTERN 3, ANTI 3, EXP 4


class IdSequenceStore:  # implements walk.common.ids.IdFactory
    def __init__(self, db: Database) -> None: ...
    def bind(
        self, uow: UnitOfWork
    ) -> "IdSequenceStore": ...  # returns a view that allocates on uow.conn
    def next_sequence(self, prefix: str) -> str: ...  # ConfigError when unbound or prefix unknown
    def new_ulid(self) -> str: ...


class IdempotencyRecord(FrozenModel):
    key: str
    operation: str
    result_ref: str | None
    created_at: datetime


class IdempotencyStore:
    def __init__(self, db: Database, clock: Clock) -> None: ...
    async def has(self, key: str) -> bool: ...
    async def get(self, key: str) -> IdempotencyRecord | None: ...
    async def put(
        self, key: str, operation: str, result_ref: str | None, uow: UnitOfWork
    ) -> None: ...
    async def run(
        self, key: str, operation: str, fn: Callable[[], Awaitable[str]], uow: UnitOfWork
    ) -> str: ...  # replay stored result_ref
```

#### Behavior
1. `UnitOfWork` issues `BEGIN IMMEDIATE` on enter; `COMMIT` on clean exit; `ROLLBACK` on exception, re-raising it.
2. `after_commit` callbacks run only after a successful COMMIT, sequentially, and are discarded on rollback.
3. Entering a `UnitOfWork` while another is active on the same connection raises `ConfigError("nested transaction")`.
4. `Repository.insert` stores `obj.model_dump_json()` in `json` plus `projection()` columns; `upsert` uses `ON CONFLICT(<key>) DO UPDATE`.
5. `get` deserialises via `_model.model_validate_json`; unknown key returns `None`.
6. `next_sequence("FEAT")` reads/increments `id_sequences` within the bound transaction (`INSERT … ON CONFLICT DO UPDATE SET next = next + 1 RETURNING next`), formats with `SEQUENCE_WIDTHS`; unbound → `ConfigError`.
7. Sequences never repeat across rolled-back transactions beyond the gap (gaps are allowed, repeats are not).
8. `IdempotencyStore.run` returns the stored `result_ref` without calling `fn` when the key exists; otherwise calls `fn`, stores the result in the same transaction, returns it.
9. `put` on an existing key raises `ConfigError("duplicate idempotency key")`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a UoW, When the body raises, Then no rows persisted and the exception propagates | `tests/persistence/test_uow.py::test_uow_rolls_back_on_exception` |
| 2 | When the body completes, Then rows persisted and `after_commit` callbacks ran in order | `tests/persistence/test_uow.py::test_uow_commits_and_runs_after_commit_hooks` |
| 3 | When body raises, Then `after_commit` callbacks did not run | `tests/persistence/test_uow.py::test_after_commit_hooks_skipped_on_rollback` |
| 4 | When a UoW is entered inside another, Then `ConfigError` | `tests/persistence/test_uow.py::test_nested_uow_rejected` |
| 5 | Given a test model repo, When `insert` then `get`, Then round-trips equal; projection columns populated | `tests/persistence/test_repository.py::test_insert_and_get_round_trip` |
| 6 | When `upsert` twice, Then one row with second values | `tests/persistence/test_repository.py::test_upsert_replaces_existing` |
| 7 | When `get("missing")`, Then `None` | `tests/persistence/test_repository.py::test_get_missing_returns_none` |
| 8 | When `list_where` with `order_by`/`limit`, Then ordered subset | `tests/persistence/test_repository.py::test_list_where_orders_and_limits` |
| 9 | When `next_sequence("FEAT")` thrice in one UoW, Then `FEAT-0001..0003` | `tests/persistence/test_ids.py::test_next_sequence_allocates_contiguous_ids` |
| 10 | When unbound `next_sequence`, Then `ConfigError` | `tests/persistence/test_ids.py::test_next_sequence_requires_bound_uow` |
| 11 | Given a rolled-back allocation, When allocating again, Then id is never a repeat of a committed id | `tests/persistence/test_ids.py::test_sequences_never_repeat_committed_ids` |
| 12 | When `next_sequence("EVD")`, Then width 6 | `tests/persistence/test_ids.py::test_sequence_width_follows_table` |
| 13 | When `run(key, fn)` twice, Then `fn` called once and both return the same `result_ref` | `tests/persistence/test_idempotency.py::test_run_replays_stored_result` |
| 14 | When `put` on existing key, Then `ConfigError` | `tests/persistence/test_idempotency.py::test_put_rejects_duplicate_key` |
| 15 | Given `fn` raises inside `run`, Then key not stored | `tests/persistence/test_idempotency.py::test_run_does_not_store_key_on_failure` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0002 D-7/D-9; ARCHITECTURE §5.4 key formats are used by callers, not validated here.
- Pitfall: keep `sqlite3` imports inside `walk.persistence` only (ARCHITECTURE §2.3) — other packages receive `Database`/`UnitOfWork`.
- Commit: `feat: add unit of work, repository base, id sequences and idempotency store (E01-S04)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
44 files already formatted
All checks passed!
Success: no issues found in 41 source files
Required test coverage of 85% reached. Total coverage: 99.49%
96 passed in 3.03s
```
Touched modules: `uow.py`, `repository.py`, `ids.py`, `idempotency.py` each 100%.

Level-0 decisions (no contract change):
- `id_sequences.next` stores the **next number to hand out**, as the column name says. Allocation is `INSERT … VALUES (?, 2) ON CONFLICT(prefix) DO UPDATE SET next = next + 1 RETURNING next - 1`. The first ID is still `-0001`.
- `IdSequenceStore.bind()` returns a private bound subclass (`_BoundIdSequenceStore`), so the public constructor stays `IdSequenceStore(db)`. A view whose unit of work has ended raises `ConfigError` (from `UnitOfWork.conn`).
- `UnitOfWork.conn` and `after_commit()` raise `ConfigError` outside an active unit of work. `BEGIN IMMEDIATE` that times out on the write lock raises `TransientError`. A failed `COMMIT` (for example a deferred foreign key) rolls back and re-raises the sqlite error, and no callbacks run. Statement errors from the body are not translated. Callbacks run after the unit of work is inactive, so a callback may open a new one. A failing callback propagates and skips the rest.
- Nesting is detected with `conn.in_transaction`. Two coroutines that open units of work concurrently on one `Database` connection get `ConfigError("nested transaction")` instead of being serialized.
- `__aenter__` is annotated `-> Self`, the typed form of `-> "UnitOfWork"` (ruff PYI034).
- `Repository` uses PEP 695 syntax (`class Repository[T: WalkModel]`), the 3.12 equivalent of the `TypeVar`/`Generic[T]` sketch; `Repository[Widget]` usage is unchanged. The key column value is `getattr(obj, _key)`. Projection values are converted to SQLite types: `Enum` → value, `bool` → int, `datetime` → ISO 8601. `_table`, `_key` and projection column names must be plain identifiers (`ConfigError` otherwise). `where`/`order_by` are kernel-written SQL fragments, and values go through `params`. `insert` of a duplicate key raises `sqlite3.IntegrityError` untranslated.
- `IdempotencyStore.run` on a key stored with `result_ref=None` raises `ConfigError`, because there is no result to replay.

---

### E01-S05 — Execution ledger: `LedgerManager`, `walk ledger tail/query`

**Status:** DONE (68e1158)
**Type:** feat
**Requirements:** §6.11, §81, §82, §86, §88, §137 (Inv. 9)
**Depends on:** E01-S04
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
An append-only execution ledger with a typed event model, query/tail API and CLI, so every later story has its audit write point available.

#### Scope
- In: `telemetry.models` (`LedgerEvent`, `LedgerEventKind`, `Report`), `LedgerRepository`, `DefaultLedgerManager.append/query/tail/report` (trivial `report`), `walk ledger tail|query`.
- Out: `TelemetryManager`/`EvidenceManager` (E01-S06); full reports (E09-S01/S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/__init__.py` | create | re-exports |
| `src/walk/telemetry/models.py` | create | `LedgerEventKind`, `LedgerEvent`, `Report`, `EvidenceKind`, `EVIDENCE_RANK`, `Evidence`, `EvidenceDraft`, `RetrospectiveMetrics` (models only; services in S06) |
| `src/walk/telemetry/protocols.py` | create | `LedgerManager` |
| `src/walk/telemetry/repository.py` | create | `LedgerRepository` |
| `src/walk/telemetry/service.py` | create | `DefaultLedgerManager` |
| `src/walk/cli/cmd_ledger.py` | create | `ledger_app` |
| `src/walk/cli/output.py` | create | `render_table`, `render_json`, `exit_with` |
| `src/walk/cli/app.py` | modify | registers `ledger_app` |
| `tests/telemetry/__init__.py` | create | — |
| `tests/telemetry/test_models.py` | create | — |
| `tests/telemetry/test_ledger.py` | create | — |
| `tests/cli/test_cmd_ledger.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 (`EvidenceKind`, `EVIDENCE_RANK`, `LedgerEventKind`) and §4.12 verbatim. Protocol: INTERFACES.md §1.14 `LedgerManager`. Deltas:
```python
class LedgerRepository:
    def __init__(self, db: Database) -> None: ...
    def insert(self, event: LedgerEvent, conn: sqlite3.Connection) -> LedgerEvent: ...   # returns copy with seq
    async def query(...same params as LedgerManager.query...) -> list[LedgerEvent]: ...
    async def after(self, seq: int, limit: int = 1000) -> list[LedgerEvent]: ...

class DefaultLedgerManager:
    def __init__(self, db: Database, repo: LedgerRepository, ids: IdFactory, clock: Clock) -> None: ...
    async def append(self, event: LedgerEvent, *, uow: UnitOfWork | None = None) -> LedgerEvent: ...
    async def query(...) -> list[LedgerEvent]: ...
    async def tail(self, after_seq: int) -> AsyncIterator[LedgerEvent]: ...   # polls every 0.25 s (injected sleep)
    async def report(self, kind: ..., subject_id: str) -> Report: ...        # Report(markdown="", data={"events": [e.model_dump(mode="json") …]})
```
CLI: `walk ledger tail [--since SEQ] [--follow]`, `walk ledger query [--kind K]... [--item ID] [--run ID] [--phase ID] [--since ISO] [--until ISO] [--limit N]`; both honour `--json`.

#### Behavior
1. `append` without `uow` opens its own `UnitOfWork`; with `uow` inserts on `uow.conn` (participates in caller's transaction).
2. `append` fills `id` (ULID) and `at` (clock) when the event's `id` is empty / `at` is missing; otherwise keeps caller values. `seq` is always assigned by SQLite and returned.
3. `query` filters are ANDed; `limit` default 1000, max 10000; ordered by `seq` ascending.
4. `tail(after_seq)` yields events with `seq > after_seq` in order and keeps polling; cancellation stops it cleanly.
5. Attempts to `UPDATE`/`DELETE` through any public API do not exist; the repository has no such methods (Invariant 9).
6. `report()` returns a `Report` containing the queried events for `subject_id` as `work_item_id` (task/feature), `phase_id` (phase), or all (project/cost/improvement); `markdown` is empty until E09.
7. CLI prints a table (`seq | at | kind | actor | item | run | outcome`) or JSON list; invalid `--since` ISO → exit 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `LedgerEventKind` members are enumerated, Then they equal the DOMAIN-MODEL §3 list (count and names) | `tests/telemetry/test_models.py::test_ledger_event_kinds_match_domain_model` |
| 2 | When `EVIDENCE_RANK` is checked, Then every `EvidenceKind` has a rank and `PLAYER_TELEMETRY` is highest | `tests/telemetry/test_models.py::test_evidence_rank_is_total_and_ordered` |
| 3 | When `append(event)` without id/at, Then returned event has ULID id, clock time, `seq == 1` | `tests/telemetry/test_ledger.py::test_append_assigns_id_time_and_seq` |
| 4 | Given a UoW that rolls back, When `append(event, uow=uow)`, Then no row persisted | `tests/telemetry/test_ledger.py::test_append_participates_in_caller_transaction` |
| 5 | Given 5 events of mixed kinds/items, When `query(kinds=[…], work_item_id=…)`, Then only matching rows in seq order | `tests/telemetry/test_ledger.py::test_query_filters_and_orders` |
| 6 | When `query(limit=20000)`, Then `ValueError`-free clamp to 10000 | `tests/telemetry/test_ledger.py::test_query_clamps_limit` |
| 7 | Given events appended after `tail(0)` started, When iterating, Then they arrive in order; cancelling the task stops iteration | `tests/telemetry/test_ledger.py::test_tail_streams_new_events_until_cancelled` |
| 8 | When a raw `UPDATE ledger_events` is attempted, Then `sqlite3.IntegrityError` | `tests/telemetry/test_ledger.py::test_ledger_rows_are_immutable` |
| 9 | When `report("task", "STORY-0001")`, Then `data["events"]` contains that item's events only | `tests/telemetry/test_ledger.py::test_report_returns_subject_events` |
| 10 | When `walk ledger query --kind WORK_ITEM_CREATED --json`, Then exit 0 and JSON list | `tests/cli/test_cmd_ledger.py::test_ledger_query_json_output` |
| 11 | When `walk ledger query --since not-a-date`, Then exit 1 | `tests/cli/test_cmd_ledger.py::test_ledger_query_rejects_bad_timestamp` |
| 12 | When `walk ledger tail --since 0` (no follow) on 3 events, Then 3 rows printed | `tests/cli/test_cmd_ledger.py::test_ledger_tail_prints_events_after_seq` |

#### Evidence required
- Quality gate output.
- Demo: `walk ledger query --limit 5` on a demo DB → table with ≤ 5 rows; `walk ledger query --json | head -c 200`.

#### Notes
- ARCHITECTURE §4.3 (write points), ADR-0002 D-3.
- `report()` is intentionally minimal and is extended (not replaced) by E09-S01.
- Commit: `feat: add append-only execution ledger and ledger cli (E01-S05)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
55 files already formatted
All checks passed!
Success: no issues found in 52 source files
Required test coverage of 85% reached. Total coverage: 99.68%
127 passed in 4.29s
```
Touched modules: `telemetry/*` 100%, `cli/cmd_ledger.py` 100%, `cli/output.py` 100%.

Demo (demo DB seeded with 7 events through `DefaultLedgerManager.append`):
```
$ walk ledger query --limit 5 --repo ./demo
seq  at                                kind                  actor   item        run  outcome
---  --------------------------------  --------------------  ------  ----------  ---  -------
1    2026-10-06T10:38:23.367467+00:00  WORK_ITEM_CREATED     KERNEL  STORY-0001       OK
2    2026-10-06T10:38:23.385711+00:00  WORK_ITEM_TRANSITION  KERNEL  STORY-0002       OK
3    2026-10-06T10:38:23.385711+00:00  AGENT_RUN_STARTED     KERNEL  STORY-0001       OK
4    2026-10-06T10:38:23.386216+00:00  WORK_ITEM_CREATED     KERNEL  STORY-0002       OK
5    2026-10-06T10:38:23.386216+00:00  WORK_ITEM_TRANSITION  KERNEL  STORY-0001       OK
$ walk ledger query --json --repo ./demo | head -c 200
[
  {
    "seq": 1,
    "id": "LED-01M48CP1M710F079ZZVKPRR2QQ",
    "kind": "WORK_ITEM_CREATED",
    "at": "2026-10-06T10:38:23.367467Z",
    "project_key": "DEMO",
    "actor_role": "KERNEL",
$ walk ledger query --since not-a-date --repo ./demo
error: invalid --since timestamp: 'not-a-date'      (exit 1)
```
Contract alignments (docs updated in this commit):
- `LedgerEvent.id`/`at` now have defaults (`LED-<ulid>` / `utcnow`) in DOMAIN-MODEL §4.12. Behaviour 2 needs events built without them, and §4.12 made them required. `append` treats a field missing from `model_fields_set` as unset and fills it from the injected `IdFactory`/`Clock`; values the caller set are kept. The field types stay non-optional.
- INTERFACES §1.14: `LedgerManager.append` gains `*, uow: UnitOfWork | None = None` (its docstring already said "when provided"). `tail` is declared `def tail(...) -> AsyncIterator[LedgerEvent]` in the Protocol, because an `async def` stub would type as a coroutine and reject the async-generator implementation. `DefaultLedgerManager.tail` is annotated `AsyncGenerator[LedgerEvent]`.

Level-0 decisions:
- `DefaultLedgerManager(..., *, sleep=asyncio.sleep)` is the "injected sleep" the contract asks for; the poll interval is 0.25 s, and polling only sleeps after an empty batch.
- `ledger_events.at` is stored as fixed-width UTC text (`isoformat(timespec="microseconds")`) so `since`/`until` (inclusive, normalised to UTC) compare correctly as strings. The JSON column holds the event without `seq`; reads restore `seq` from the row. `limit` is clamped to `0..10000`. `report()` reads at most 10000 events.
- Every pydantic field carries a `description=` (CONVENTIONS §4); metric descriptions only cite §115/§116.
- `output.py`: `render_table(headers, rows) -> str` (left-aligned, dashed rule, `None` empty, trailing spaces stripped), `render_json(data) -> str` (indent 2), `exit_with(error: WalkError) -> NoReturn` (stderr `error: …`; `GuardRejected`/`PermissionDenied` → 2, other kernel errors → 1). Codes 3/4 arrive with their errors in later stories. `cmd_db` keeps its own exit helper because it is outside this story's Files table; a later CLI story can switch it to `exit_with`.
- The ledger CLI opens the DB read-only and exits 1 if it is missing. Like `walk db`, it also accepts `--repo`/`--json` after the subcommand (global options are honoured too). A timestamp without an offset is read as UTC. `tail` without `--follow` prints every event after `--since` and exits. `--follow` prints one line per event (JSON lines with `--json`) until Ctrl+C, which exits 0. Command parameters are keyword-only (ruff PLR0917).
- The kinds test reads the enum list straight from `DOMAIN-MODEL.md`, so drift between doc and code fails the gate.

---

### E01-S06 — `TelemetryManager` and `EvidenceManager`

**Status:** DONE (ece9b6f)
**Type:** feat
**Requirements:** §6.6, §47, §86, §116
**Depends on:** E01-S05
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Structured JSON logging, counters/timers, ledger-derived `RetrospectiveMetrics`, and evidence recording with hashing and §47 ranking.

#### Scope
- In: `DefaultTelemetryManager`, `DefaultEvidenceManager`, `EvidenceRepository`.
- Out: log rotation and metric completeness audit (E09-S06); evidence as context candidates (E04-S10).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/telemetry/protocols.py` | modify | `TelemetryManager`, `EvidenceManager` |
| `src/walk/telemetry/service.py` | modify | `DefaultTelemetryManager`, `DefaultEvidenceManager` |
| `src/walk/telemetry/repository.py` | modify | `EvidenceRepository` |
| `src/walk/telemetry/metrics.py` | create | `METRIC_QUERIES`, `compute_metrics` |
| `src/walk/telemetry/logging.py` | create | `JsonLineHandler`, `configure_logging` |
| `tests/telemetry/test_telemetry.py` | create | — |
| `tests/telemetry/test_metrics.py` | create | — |
| `tests/telemetry/test_evidence.py` | create | — |

#### Interface contract
Protocols: INTERFACES.md §1.14 `TelemetryManager`, `EvidenceManager`. Deltas:
```python
class DefaultTelemetryManager:
    def __init__(
        self, repo_root: Path, ledger: LedgerRepository, clock: Clock
    ) -> None: ...  # log file <repo>/.walk/logs/kernel.jsonl


class DefaultEvidenceManager:
    def __init__(
        self,
        db: Database,
        ai_root: Path,
        repo: EvidenceRepository,
        ledger: LedgerManager,
        ids: IdSequenceStore,
        clock: Clock,
    ) -> None: ...
```
`METRIC_QUERIES` — one SQL per `RetrospectiveMetrics` field, scoped by optional `phase_id`/`since`:
| Field | Definition over `ledger_events` (`e`) |
|---|---|
| `stories` | count distinct `work_item_id` with `WORK_ITEM_TRANSITION` to `COMPLETE` and payload.kind in (STORY, TASK) |
| `first_pass_success_rate` | among those, share whose payload.fix_loops == 0 (0.0 when no stories) |
| `reworked_stories` | distinct items with a transition to `REWORK` |
| `qc_bugs` | count `BUG_CREATED` |
| `escaped_bugs` | count `BUG_CREATED` with payload.found_in_state == "COMPLETE" |
| `context_stale_incidents` | count `CONTEXT_FRESHNESS` with payload.status != "CURRENT" |
| `fallbacks` | count `MODEL_FALLBACK` |
| `failed_handoffs` | count `AGENT_RUN_ENDED` with payload.handover_in_id set and outcome == "FAILED" |
| `build_failures` | count `BUILD_RESULT` with outcome == "FAILED" |
| `debate_rounds` | count `DEBATE_POSITION` distinct (debate_id, round) |
| `user_escalations` | count `ESCALATION_RAISED` with payload.to_level == 3 |
| `total_cost_usd` | sum `cost_usd` of `COST_RECORDED` |
| `total_tokens` | sum payload.input_tokens + payload.output_tokens of `COST_RECORDED` |
| `mean_task_duration_s` | mean of (AGENT_RUN_ENDED.at − AGENT_RUN_STARTED.at) per run |

#### Behavior
1. `log()` writes one JSON object per line with keys `ts, level, msg, **fields`; never raises on unserialisable fields (falls back to `repr`).
2. `counter`/`timer` accumulate in-process and are flushed as a `metrics` log line every 60 s (injected clock) and on `close()`; they are diagnostics, not the ledger.
3. `metrics()` evaluates `METRIC_QUERIES` and returns a fully populated `RetrospectiveMetrics` (zeros when empty).
4. `EvidenceManager.record` copies `path_or_uri` (if a local file) under `.ai/<features|bugs|phases>/<id>/evidence/<basename>` (folder chosen by `work_item_id` prefix `FEAT`/`BUG`, else `phase_id`; STORY/TASK evidence goes under the parent feature folder passed as `work_item_id` by the caller — when it is a STORY id the folder is `.ai/features/<story-parent>`? No: STORY/TASK evidence is filed under `.ai/features/<work_item_id>/evidence/` using the item id as stem; keep it literal), computes sha256, mints `EVD-` id, inserts `evidence` row and `EVIDENCE_RECORDED` in one transaction.
5. External URIs (`http://`, `https://`, `s3://`) are stored as-is with `sha256=None`.
6. `strongest` returns max by `rank`, ties by `produced_at` desc; empty → `None`.
7. `satisfies(required, present)` returns the kinds missing from `present`, preserving `required` order.
8. Missing local file → `ConfigError`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `log("INFO", "x", a=1)`, Then last line of `kernel.jsonl` parses to `{"level":"INFO","msg":"x","a":1,…}` | `tests/telemetry/test_telemetry.py::test_log_writes_json_line` |
| 2 | When logging a non-serialisable field, Then the line still parses with its `repr` | `tests/telemetry/test_telemetry.py::test_log_falls_back_to_repr` |
| 3 | When `counter("x")` twice and clock advances 60 s, Then a `metrics` line with `x: 2` is flushed | `tests/telemetry/test_telemetry.py::test_counters_flush_periodically` |
| 4 | Given an empty ledger, When `metrics()`, Then all fields zero/0.0 | `tests/telemetry/test_metrics.py::test_metrics_zero_on_empty_ledger` |
| 5 | Given a seeded ledger fixture (2 complete stories, 1 with fix_loops=1, 1 fallback, 2 cost records), When `metrics()`, Then `stories == 2`, `first_pass_success_rate == 0.5`, `fallbacks == 1`, `total_cost_usd` is the sum | `tests/telemetry/test_metrics.py::test_metrics_computed_from_seeded_ledger` |
| 6 | Given `phase_id`, When `metrics(phase_id=…)`, Then only that phase's events count | `tests/telemetry/test_metrics.py::test_metrics_scoped_by_phase` |
| 7 | When `record(draft)` with a local file, Then file copied under the evidence folder, `sha256` set, `EVD-000001`, ledger `EVIDENCE_RECORDED` | `tests/telemetry/test_evidence.py::test_record_copies_hashes_and_logs` |
| 8 | When `record` with `https://…`, Then `uri` kept, `sha256 is None` | `tests/telemetry/test_evidence.py::test_record_external_uri` |
| 9 | When `record` with a missing file, Then `ConfigError` and no row | `tests/telemetry/test_evidence.py::test_record_missing_file_raises` |
| 10 | Given evidence of kinds LOG and AUTOMATED_TEST, When `strongest`, Then AUTOMATED_TEST | `tests/telemetry/test_evidence.py::test_strongest_uses_rank` |
| 11 | Given two AUTOMATED_TEST, Then newer wins | `tests/telemetry/test_evidence.py::test_strongest_breaks_ties_by_recency` |
| 12 | When `satisfies([TESTED kinds…], present)`, Then missing kinds returned in order | `tests/telemetry/test_evidence.py::test_satisfies_returns_missing_kinds` |
| 13 | When `for_item(id, kinds=[SCREENSHOT])`, Then filtered list | `tests/telemetry/test_evidence.py::test_for_item_filters_by_kind` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0001 (logs are diagnostics), ADR-0009 D-16 (JSON lines path; rotation in E09-S06), ADR-0003 (evidence folders).
- Evidence folder rule is literal: `.ai/features/<id>/evidence/` for FEAT/STORY/TASK ids, `.ai/bugs/<id>/evidence/` for BUG ids, `.ai/phases/<phase>/evidence/` when only `phase_id` is given.
- Commit: `feat: add telemetry logging, ledger metrics and evidence manager (E01-S06)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
60 files already formatted
All checks passed!
Success: no issues found in 57 source files
Required test coverage of 85% reached. Total coverage: 99.74%
154 passed in 5.21s
```
Touched modules: `telemetry/service.py`, `repository.py`, `metrics.py`, `logging.py`, `protocols.py` each 100%.

Additions outside the listed symbols (flagged for the owner; no listed signature changed):
- `LedgerRepository.db` (read-only property). `metrics()` must run `METRIC_QUERIES` as SQL, but the contract constructor `DefaultTelemetryManager(repo_root, ledger: LedgerRepository, clock)` passes no `Database`, and `LedgerRepository` had no read path for arbitrary SELECTs. The property exposes the handle without adding any write method (Invariant 9). `tests/telemetry/test_ledger.py` (E01-S05) now allows `db` in its "no update/delete" surface check; that is the only file touched outside the Files table. E10-S09's `DefaultTelemetryManager.improvement_metrics` → `compute_improvement_metrics(db, …)` can use the same path.
- `EvidenceRepository.project_key(uow)`. `EVIDENCE_RECORDED` needs `project_key`, and neither `DefaultEvidenceManager.__init__` nor `record()` supplies one. Because there is one DB per project (ADR-0002 D-1), the repository reads the single `projects` row inside the record transaction; zero or several rows raise `ConfigError`. Other E01 services take `*, project_key` in their constructor (e.g. `DefaultCheckpointManager`), and the owner may prefer that here.

Cross-story gap, not fixed here: the `METRIC_QUERIES` definitions read payload keys that the planned writers do not list yet. These are `WORK_ITEM_TRANSITION.payload.kind`/`fix_loops` (E01-S09 lists `from, to, event, reason, resume_state?, state_version`) and `BUG_CREATED.payload.found_in_state` (DOMAIN-MODEL §4.12 payload table). Until the writers add them, `first_pass_success_rate` and `escaped_bugs` stay 0. Story kind falls back to the id prefix (DOMAIN-MODEL §2) when `payload.kind` is absent.

Level-0 decisions:
- `compute_metrics(db, *, phase_id=None, since=None) -> RetrospectiveMetrics` (async, the shape of E10's `compute_improvement_metrics`). Every query is a static SELECT with named parameters `:phase_id`/`:since` (NULL = unscoped). Phase scoping means `e.phase_id = :phase_id`. A completed item counts as first-pass when its `MAX(payload.fix_loops) = 0`; a missing value counts as not first-pass. `!=`/`=` conditions on a missing payload key do not match. `mean_task_duration_s` joins `AGENT_RUN_STARTED` per run and is rounded to milliseconds (`julianday` float error).
- `JsonLineHandler(path)` is a `logging.FileHandler` (append, utf-8, delayed open, parent dir created) whose `format()` emits `{ts, level, msg, logger?, **fields}`. Fields come from `extra=` or from `DefaultTelemetryManager.log`, and a field never overrides `ts/level/msg/logger`. Unencodable values become `repr` (including cycles). `configure_logging(repo_root, *, level="INFO") -> None` replaces any earlier `JsonLineHandler` on the `walk` logger, matching E09-S06's planned keyword-extended signature. The module name `telemetry/logging.py` comes from the Files table; absolute imports keep stdlib `logging` unaffected.
- `DefaultTelemetryManager.log` stamps `ts` from the injected clock and writes no `logger` key, so lines are exactly `ts, level, msg, **fields`. Unknown level names are written upper-cased at INFO severity. Counters/timers use keys `name{k=v,…}` (sorted labels); timers keep `count/total_s/max_s`. The 60 s flush is checked at the start of each `counter`/`timer`/`log` call (no background task). `close()` flushes whatever is pending and closes the file; an empty window writes nothing.
- Evidence: repo-relative paths resolve against `ai_root.parent`. EPIC ids, or neither id given, raise `ConfigError` for local files (the folder rule has no entry); external URIs need no folder. Files are copied atomically (`.partial` + replace) under their basename. An existing target is reused only if it is the same file or has identical content, otherwise `ConfigError` (evidence is immutable). A failed transaction deletes a copy made by that call. The ledger payload is `{evidence_id, kind}`, and the event `at` equals `produced_at`. `for_item(kinds=[])` means no filter, as in `LedgerRepository.query`. `satisfies` de-duplicates `required` while keeping its order. Writing evidence binaries under `.ai/` is the story's own rule (ADR-0003 D-1/D-4 exempt `evidence/` folders from document writes).
- `DefaultEvidenceManager.__init__` carries `# noqa: PLR0917`, because its six positional parameters are fixed by the contract.

---

### E01-S07 — Hooks runtime core: `HookManager`

**Status:** DONE (eb4f3e8)
**Type:** feat
**Requirements:** §32, §41, §138 (Tool Failure)
**Depends on:** E01-S05
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A deterministic, synchronous, priority-ordered hook dispatcher with timeouts, fail policies and full execution records, ready for packages to register builtin hooks.

#### Scope
- In: `hooks.models`, `hooks.protocols`, `DefaultHookManager` engine, `HookExecutionRepository`, `HookFailed`.
- Out: MUST attachment table (E02-S08 — the callables live in `walk.orchestrator.builtin_hooks` and are registered by the composition root through `register(hook, fn)`, ADR-0016; `walk.hooks` has no `register_builtins`), `hooks.yaml` parsing (E02-S09) — `load_project_hooks` raises until then.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/hooks/__init__.py` | create | re-exports |
| `src/walk/hooks/models.py` | create | `HookName`, `HookFailPolicy`, `Hook`, `HookContext`, `HookResult`, `HookCallable` |
| `src/walk/hooks/protocols.py` | create | `HookManager` |
| `src/walk/hooks/errors.py` | create | `HookFailed` |
| `src/walk/hooks/repository.py` | create | `HookExecutionRepository` |
| `src/walk/hooks/service.py` | create | `DefaultHookManager` |
| `tests/hooks/__init__.py` | create | — |
| `tests/hooks/test_models.py` | create | — |
| `tests/hooks/test_service.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §4.6 (`walk.hooks.models`) verbatim. Protocol: INTERFACES.md §1.11 `HookManager`. Deltas:
```python
HookCallable = Callable[[HookContext], Awaitable[None]]


class HookFailed(PermanentError):
    """A FAIL_CLOSED hook failed; carries hook_id and results so far in detail."""


class DefaultHookManager:
    def __init__(
        self,
        repo: HookExecutionRepository,
        ledger: LedgerManager,
        clock: Clock,
        *,
        callables: dict[str, HookCallable] | None = None,
    ) -> None: ...
    def register(
        self, hook: Hook, fn: HookCallable | None = None
    ) -> None: ...  # builtin: fn required (or resolvable callable_path); project: fn None
    def load_project_hooks(self, path: str) -> list[Hook]: ...  # raises NotSupported until E02-S09
    async def fire(self, name: HookName, ctx: HookContext) -> list[HookResult]: ...
    def hooks_for(self, name: HookName) -> list[Hook]: ...
```

#### Behavior
1. `register` rejects duplicate `(name, id)` with `ConfigError`; rejects a `kind="project"` hook whose `id` equals a registered `required` builtin (`ConfigError`); rejects `enabled=False` for a `required` hook.
2. `hooks_for` returns enabled hooks ordered by `priority` ascending, then `id` ascending.
3. `fire` runs hooks strictly sequentially; each wrapped in `asyncio.wait_for(timeout_s)`; a timeout yields `status="TIMEOUT"`.
4. On failure/timeout of a `FAIL_CLOSED` hook: record the result, write `HOOK_FAILED`, raise `HookFailed` — remaining hooks are not run.
5. On failure of `LOG_AND_CONTINUE`: record, write `HOOK_FAILED`, continue.
6. Every execution inserts a `hook_executions` row and `HOOK_EXECUTED` (status OK) or `HOOK_FAILED` ledger event with `duration_ms`.
7. `fire` for a name with no hooks returns `[]` and writes nothing.
8. `HookContext.at` is taken from the caller; results carry `duration_ms` measured by the clock.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `HookName` members are enumerated, Then they equal the ARCHITECTURE §4.1 list (45 values, snake_case) | `tests/hooks/test_models.py::test_hook_names_match_architecture_table` |
| 2 | Given hooks with priorities 100, 10, 10 (ids b, a), When `hooks_for`, Then order is `10/a, 10/b, 100` | `tests/hooks/test_service.py::test_hooks_ordered_by_priority_then_id` |
| 3 | When registering the same `(name,id)` twice, Then `ConfigError` | `tests/hooks/test_service.py::test_register_rejects_duplicate_id` |
| 4 | Given a required builtin, When a project hook with the same id is registered, Then `ConfigError` | `tests/hooks/test_service.py::test_project_hook_cannot_replace_required_builtin` |
| 5 | Given two hooks, When `fire`, Then both ran sequentially (second starts after first ends) and two `HOOK_EXECUTED` events exist | `tests/hooks/test_service.py::test_fire_runs_sequentially_and_records` |
| 6 | Given a FAIL_CLOSED hook that raises before a second hook, When `fire`, Then `HookFailed`, second hook not run, `HOOK_FAILED` written | `tests/hooks/test_service.py::test_fail_closed_aborts_and_raises` |
| 7 | Given a LOG_AND_CONTINUE hook that raises, Then result FAILED, next hook runs, no exception | `tests/hooks/test_service.py::test_log_and_continue_continues` |
| 8 | Given a hook exceeding `timeout_s`, Then status TIMEOUT and policy applied | `tests/hooks/test_service.py::test_timeout_is_recorded_and_policy_applied` |
| 9 | When `fire` on a name without hooks, Then `[]` and no ledger rows | `tests/hooks/test_service.py::test_fire_without_hooks_is_noop` |
| 10 | When `load_project_hooks`, Then `NotSupported` (until E02-S09) | `tests/hooks/test_service.py::test_load_project_hooks_not_supported_yet` |
| 11 | Given a disabled non-required hook, Then it is skipped with no record | `tests/hooks/test_service.py::test_disabled_hook_is_skipped` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0009 D-7; ARCHITECTURE §4.1 failure policy; WBS §3.5 (hooks never duplicate ledger write points).
- `NEW NAME: HookFailed` (WBS §6). `NotSupported` is defined in E01-S23 — until then S07 imports a temporary local `NotSupported`? No: define `NotSupported` in `walk.common.errors`? WBS places it in `walk.integrations.errors`. Resolution for ordering: S07 raises `ConfigError("project hooks available from E02-S09")`; E02-S09 replaces it. Use `ConfigError` here (test 10 asserts `ConfigError`).
- Commit: `feat: add hook manager with ordered dispatch and fail policies (E01-S07)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
69 files already formatted
All checks passed!
Success: no issues found in 66 source files
Required test coverage of 85% reached. Total coverage: 99.78%
176 passed in 6.66s
```
Touched modules: `hooks/models.py`, `protocols.py`, `errors.py`, `repository.py`, `service.py` each 100%.

Doc corrections in this commit:
- AC 1 said "43 values". ARCHITECTURE §4.1 and DOMAIN-MODEL §4.6 both list 45 names, and the two sets are identical. The test parses the §4.1 table and expects 45. The AC text now says 45.
- AC 10 asserts `ConfigError`, as the Notes resolve, not `NotSupported`.

Level-0 decisions (no listed signature changed):
- `HookExecutionRepository(db)` has `db` (read-only property) and `async insert(ctx, result, *, at, uow)`. The `DefaultHookManager` constructor gets no `Database`, so it opens its units of work on `repo.db`, the same pattern as `LedgerRepository.db` (E01-S06).
- Each execution is recorded after the hook returns, in one unit of work: the `hook_executions` row plus the `HOOK_EXECUTED`/`HOOK_FAILED` event. The hook itself runs outside any transaction, so it can open its own units of work. Because of that, `fire` must not be called while a unit of work is open on the same database (ARCHITECTURE: hooks fire after commit). Otherwise `UnitOfWork` raises `ConfigError("nested transaction")`.
- Ledger event: `actor_role=KERNEL`, `work_item_id`/`run_id`/`phase_id` taken from the context, `at` = execution start (clock), `duration_ms`, `outcome` `OK`/`FAILED` (TIMEOUT maps to `FAILED`). The payload is `{hook_name, hook_id, kind, status, fail_policy, message}`. The row `at` is the same start time, and `message` is NULL on success.
- Timeouts use `asyncio.timeout(timeout_s)`, which is what `wait_for` does internally. `timeout.expired()` tells the kernel deadline apart from a `TimeoutError` raised by the hook itself, which counts as `FAILED`. Any `Exception` from a hook is caught and recorded as `FAILED` with message `<Type>: <text>`. Cancellation still propagates.
- `HookFailed` detail is `{hook_name, hook_id, results: [HookResult as JSON…]}`.
- `register`: the required-builtin check runs first and matches the id across all hook names. Then come the duplicate `(name, id)` check and the "required cannot be disabled" check. A builtin without `fn` resolves `callables[hook.callable_path]`, and if that fails it raises `ConfigError("… needs a callable")`. A project hook given an `fn` raises `ConfigError`, because it runs its command or action.
- A registered project hook has no executor until E02-S09. Firing it records `FAILED` ("project hooks are available from E02-S09") and applies its fail policy, so a `fail_closed` project hook never passes silently.
- `fire` raises `ConfigError` when `ctx.name` differs from `name`.
- Extra tests beyond the AC table: protocol conformance, model defaults/frozen, the register guards above, `callable_path` resolution, a hook raising `TimeoutError`, and a project hook without an executor.

---

### E01-S08 — Work-item aggregates, repository, `WorkflowManager.create/get/query`, `walk work list/show`

**Status:** DONE (dff4ff5)
**Type:** feat
**Requirements:** §52, §54, §57, §81
**Depends on:** E01-S04, E01-S05
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §52 hierarchy (Project, Epic, Feature, Story, Task, Bug) is persisted with sequence IDs and `WORK_ITEM_CREATED` events, queryable from code and CLI.

#### Scope
- In: `workflow.models` (all of DOMAIN-MODEL §4.1 and §3 workflow enums), `WorkflowRepository`, `ProjectRepository`, `DefaultWorkflowManager.create/get/query`, `walk work list|show`.
- Out: transitions (E01-S09), DoR/ready items (E01-S10), phases/RC repositories (E01-S11), provider sync (E03-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/__init__.py` | create | re-exports |
| `src/walk/workflow/models.py` | create | DOMAIN-MODEL §3 workflow enums + §4.1 models; `TransitionContext`, `GuardResult`, `Transition`, `TransitionTable` |
| `src/walk/workflow/protocols.py` | create | `WorkflowManager`, `Guard` |
| `src/walk/workflow/errors.py` | create | `WorkItemNotFound` |
| `src/walk/workflow/repository.py` | create | `WorkflowRepository`, `ProjectRepository` |
| `src/walk/workflow/service.py` | create | `DefaultWorkflowManager` (create/get/query; other methods added by S09–S11) |
| `src/walk/cli/cmd_work.py` | create | `work_app` |
| `src/walk/cli/app.py` | modify | registers `work_app` |
| `tests/workflow/__init__.py` | create | — |
| `tests/workflow/test_models.py` | create | — |
| `tests/workflow/test_repository.py` | create | — |
| `tests/workflow/test_service_create.py` | create | — |
| `tests/cli/test_cmd_work.py` | create | — |
| `tests/conftest.py` | modify | fixture `project` (persisted `Project(key="DEMO")`) |

#### Interface contract
Models: DOMAIN-MODEL §4.1 verbatim; INTERFACES.md §1.3 value objects. Protocol: INTERFACES.md §1.3 `WorkflowManager` (this story implements `create`, `get`, `query`; remaining methods raise `ConfigError("implemented in E01-S09/S10/S11")` until those stories land — the only permitted deferred-method pattern, see E01-S29 Notes). Deltas:
```python
class WorkItemNotFound(PermanentError): ...


class WorkflowRepository(
    Repository[WorkItem]
):  # table work_items; projection: kind, project_key, parent_id, phase_id, state, state_version, title, owner_role, assigned_run_id, external_ref, priority, risk, fix_loops, created_at, updated_at
    async def by_external_ref(self, external_ref: str) -> WorkItem | None: ...
    async def children(self, parent_id: WorkItemId) -> list[WorkItem]: ...


class ProjectRepository(Repository[Project]): ...  # table projects, key "key"


class DefaultWorkflowManager:
    def __init__(
        self,
        db: Database,
        items: WorkflowRepository,
        projects: ProjectRepository,
        ids: IdSequenceStore,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
        tables_dir: Path,
    ) -> None: ...
```
CLI: `walk work list [--state S]... [--kind K]... [--phase ID]`, `walk work show ID` (item + contract + transitions + runs + cost — transitions/runs/cost sections print "none" until their stories exist).

#### Behavior
1. `create(WorkItemDraft)` allocates the id from `IdSequenceStore` using the prefix for `draft.kind` (`EPIC/FEAT/STORY/TASK`), validates `parent_id` exists and is of the allowed parent kind (EPIC→none, FEATURE→EPIC|none, STORY/TASK→FEATURE, BUG→none or FEATURE via `related_feature_id`), sets `state=IDEA`, `project_key` from the single `Project`, persists and writes `WORK_ITEM_CREATED` (payload: kind, title, parent_id) in one transaction.
2. `create(BugDraft)` builds a `Bug` with `contract.goal = title`, `severity`, `reproduction/expected/observed`, `related_feature_id`, `found_against_commit`; `owner_role` unset until triage.
3. STORY/TASK drafts without `contract` raise `ConfigError`.
4. `get` raises `WorkItemNotFound`; `query` ANDs filters and orders by `created_at, id`.
5. Discriminated union round-trips: a `Bug` stored and read back is a `Bug` instance.
6. `walk work show` on unknown id exits 1.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `WorkItemState` members are enumerated, Then exactly the 15 ADR-0010 D-1 values | `tests/workflow/test_models.py::test_work_item_state_matches_adr_0010` |
| 2 | When a `Bug` JSON is validated as `WorkItem`, Then a `Bug` instance | `tests/workflow/test_models.py::test_work_item_union_discriminates_on_kind` |
| 3 | When `WorkflowRepository.insert(feature)` then `get`, Then equal; `state` column populated | `tests/workflow/test_repository.py::test_insert_and_get_feature` |
| 4 | When `by_external_ref("LOCAL-1")`, Then the item | `tests/workflow/test_repository.py::test_by_external_ref` |
| 5 | When `children(feature_id)`, Then its stories only | `tests/workflow/test_repository.py::test_children_returns_direct_children` |
| 6 | When `create(FEATURE draft)`, Then id `FEAT-0001`, state IDEA, `WORK_ITEM_CREATED` event with same item id | `tests/workflow/test_service_create.py::test_create_feature_allocates_id_and_logs` |
| 7 | When `create(STORY draft, parent=FEAT-0001)`, Then `STORY-0001` with `parent_id` set | `tests/workflow/test_service_create.py::test_create_story_under_feature` |
| 8 | When `create(STORY draft, parent=EPIC-001)`, Then `ConfigError` | `tests/workflow/test_service_create.py::test_create_rejects_invalid_parent_kind` |
| 9 | When `create(STORY draft)` without contract, Then `ConfigError` | `tests/workflow/test_service_create.py::test_create_story_requires_contract` |
| 10 | When `create(BugDraft)`, Then `BUG-0001`, severity set, `owner_role is None` | `tests/workflow/test_service_create.py::test_create_bug_from_draft` |
| 11 | Given a failing ledger (injected), When `create`, Then no work item persisted | `tests/workflow/test_service_create.py::test_create_is_atomic_with_ledger` |
| 12 | When `get("STORY-9999")`, Then `WorkItemNotFound` | `tests/workflow/test_service_create.py::test_get_unknown_raises` |
| 13 | When `query(states=[IDEA], kinds=[STORY])`, Then filtered list in creation order | `tests/workflow/test_service_create.py::test_query_filters` |
| 14 | When `walk work list --kind FEATURE`, Then table with the feature row | `tests/cli/test_cmd_work.py::test_work_list_filters_by_kind` |
| 15 | When `walk work show FEAT-0001 --json`, Then JSON with `id`, `state`, `contract` keys | `tests/cli/test_cmd_work.py::test_work_show_json` |
| 16 | When `walk work show NOPE-1`, Then exit 1 | `tests/cli/test_cmd_work.py::test_work_show_unknown_exits_1` |

#### Evidence required
- Quality gate output.
- Demo: `walk work list` → table `id | kind | state | title | owner`; `walk work show FEAT-0001`.

#### Notes
- ADR-0010; DOMAIN-MODEL §2 ID rules (allocated in the insert transaction, never from file scans).
- Pitfall: `WorkItem` is an `Annotated` union, so `Repository[WorkItem]._model` uses a `TypeAdapter`, not `model_validate_json`.
- Commit: `feat: add work item aggregates, repository and work cli (E01-S08)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
81 files already formatted
All checks passed!
Success: no issues found in 78 source files
Required test coverage of 85% reached. Total coverage: 99.84%
215 passed in 7.36s
```
Touched modules: `workflow/models.py`, `protocols.py`, `errors.py`, `repository.py`, `service.py`, `cli/cmd_work.py`, `persistence/repository.py` each 100%.

Demo (scratch repo seeded with a project, `FEAT-0001`, `STORY-0001` and `BUG-0001` through `DefaultWorkflowManager.create`):
```
$ walk work list --repo ./demo
id          kind     state  title          owner
----------  -------  -----  -------------  ----------
FEAT-0001   FEATURE  IDEA   Inventory
STORY-0001  STORY    IDEA   Pick up item   SENIOR_DEV
BUG-0001    BUG      IDEA   Bag overflows
$ walk work show FEAT-0001 --repo ./demo
FEAT-0001  FEATURE  IDEA
title: Inventory
parent: -
phase: -
owner: -
priority: P2  risk: MEDIUM
contract: none
transitions: none
runs: none
cost: none
$ walk work show STORY-0001 --repo ./demo
STORY-0001  STORY  IDEA
...
contract:
  goal: Pick up loot
  acceptance criteria:
  - item in bag
transitions: none
runs: none
cost: none
$ walk work show NOPE-1 --repo ./demo
error: work item not found: NOPE-1      (exit 1)
```

Architecture change, recorded as ADR-0018 (owner review requested):
- ARCHITECTURE §2.2 forbade `workflow → hooks` and allowed `hooks → workflow`. This story's contract (`DefaultWorkflowManager(..., hooks: HookManager, ...)`) and `Transition.hooks: tuple[HookName, ...]` (INTERFACES §1.3) need the opposite direction. The same holds for budgets, effort, permissions, memory, context, decisions and debate in later stories. `hooks` therefore moves to the front of the L2 order: it imports only common/persistence/telemetry, and every later package may import it. The E01-S07 code already obeys this. The §2.2 table, ADR index and WBS §6 register are updated.

Other contract alignments (docs updated in this commit):
- INTERFACES §1.3 `TransitionContext`: `run_id`, `payload` and `phase` gain defaults (`None`, `{}`, `None`). E03-S03 builds `TransitionContext(actor_role=…, source=…, payload=…)` without the other two. The change is additive.
- `apply_external_transition` is left out of the code `WorkflowManager` protocol and of `DefaultWorkflowManager`. Its `WorkProviderEvent` parameter is defined in `walk.integrations`, which `walk.workflow` may not import. INTERFACES §1.3 now carries an "Open (E03-S03)" note: that story must settle the event's placement.
- Outside the Files table: `persistence/repository.py` gains a private `Repository._load(raw)` hook that `get`/`list_where` use. `WorkflowRepository` overrides it with a `TypeAdapter(WorkItem)`, the story's pitfall. No public symbol changed.

Level-0 decisions:
- Deferred methods raise `ConfigError("WorkflowManager.<m> is implemented in <story>")`. `table_for`/`raise_event` name E01-S09; `ready_items`/`check_definition_of_ready`/`set_done_dimension` name E01-S10; `phase_event`/`rc_event` name E01-S11; `children_states`/`open_blocker_bug_count` name E03-S17; `gdd_coverage` names E06-S06.
- Parent rules: EPIC has no parent; FEATURE has none or an EPIC; STORY/TASK need a FEATURE parent (the story does not say "or none" for them); BUG has no `parent_id` and links through `related_feature_id`, which must exist. A missing parent or feature raises `WorkItemNotFound`. A wrong kind raises `ConfigError`. `WorkItemDraft(kind=BUG)` raises `ConfigError` (use `BugDraft`). A contract on an EPIC/FEATURE draft raises `ConfigError` instead of being silently dropped.
- STORY/TASK copy `owner_role`, `priority` and `risk` from their contract. Bugs keep `owner_role=None` and `description=""`; `BugDraft.evidence_ids` is not stored on the bug (evidence linking belongs to the output applier). `created_at = updated_at = clock.now()`, and the ledger event `at` is the same instant. `WORK_ITEM_CREATED` carries `actor_role=actor`, `outcome="OK"` and payload `{kind, title, parent_id}`. `create` fires no hooks.
- `phase_id` must name an existing `phases` row (`ConfigError`); `WorkflowRepository.phase_exists` reads it. `ProjectRepository.single()` returns the only project or raises `ConfigError("… found N")`. The `projects.updated_at` column records the write time, because `Project` has no such field.
- Timestamp projection columns are fixed-width UTC text, so `ORDER BY created_at, id` is chronological. `query` treats empty filter lists as no filter, the same as the ledger.
- CLI: `walk work list/show` open the DB read-only and exit 1 when it is missing. Like `db`/`ledger`, they accept `--repo/--json` after the subcommand. `show --json` is the item dump with a `contract` key that is always present (`null` for epics/features). Transitions/runs/cost are omitted from JSON until their stories exist; the text view prints `none`. `_TABLES_DIR` points at the packaged `walk/workflow/tables/` folder that E01-S09 creates.
- Also read: ADR-0010 (state list for AC 1), ARCHITECTURE §2.2, E01-S09/S10/S11, E03-S03, E03-S17 and E06-S06 (owners of the deferred methods).

---

### E01-S09 — `StateMachine`, YAML tables, guard registry, `raise_event`, `story_workflow`, `walk work transition`

**Status:** DONE (pending)
**Type:** feat
**Requirements:** §53, §54, §61, §81, §105 (tables as versioned data), §137 (Inv. 4, 9)
**Depends on:** E01-S07, E01-S08
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Explicit, data-driven, guarded state transitions committed atomically with the ledger event and the transition row, with hooks fired after commit; `story_workflow v1.0` is loaded from YAML and driven from the CLI.

#### Scope
- In: `StateMachine`, YAML table loader + schema, guard registry, guards needed by `story_workflow`, `raise_event`, `story_workflow.yaml`, `walk work transition`.
- Out: feature/bug tables and their guards (E01-S10), phase/RC tables (E01-S11), provider sync on transition (E03-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/state_machine.py` | create | `StateMachine`, `TableLoader`, `TABLES_DIR` |
| `src/walk/workflow/guards.py` | create | `register_guard`, `get_guard`, `registered_guards`, guard callables listed below |
| `src/walk/workflow/tables/story_workflow.yaml` | create | — |
| `src/walk/workflow/service.py` | modify | `DefaultWorkflowManager.table_for`, `raise_event` |
| `src/walk/workflow/errors.py` | modify | `UnknownTransition` |
| `src/walk/cli/cmd_work.py` | modify | `transition` command |
| `tests/workflow/test_state_machine.py` | create | — |
| `tests/workflow/test_guards.py` | create | — |
| `tests/workflow/test_tables.py` | create | — |
| `tests/workflow/test_service_transitions.py` | create | — |
| `tests/cli/test_cmd_work.py` | modify | — |

#### Interface contract
```python
class TableLoader:
    def load(
        self, path: Path
    ) -> (
        TransitionTable
    ): ...  # validates schema below; every guard name must be registered; ConfigError otherwise


class StateMachine:
    def __init__(self, tables: dict[WorkItemKind, TransitionTable]) -> None: ...
    def transition_for(
        self,
        kind: WorkItemKind,
        state: WorkItemState,
        event: str,
        item: WorkItem,
        ctx: TransitionContext,
    ) -> Transition:
        """Candidates = rows with (from_state, event) incl. wildcard rows ('*' / '* except …'); evaluates guards in row order;
        returns the first row whose guards all pass; raises UnknownTransition when no row matches (from,event),
        GuardRejected(reason) when rows exist but all guards fail, PermissionDenied when actor_role ∉ allowed_roles."""

    def resolve_target(
        self, transition: Transition, item: WorkItem, ctx: TransitionContext
    ) -> WorkItemState:
        """to_state, or ctx.payload['resume_state'] for the pseudo-state 'PREVIOUS' (BLOCKED → unblock)."""


def register_guard(name: str) -> Callable[[Guard], Guard]: ...
def get_guard(name: str) -> Guard: ...  # ConfigError on unknown
def registered_guards() -> dict[str, Guard]: ...
```
YAML schema (`story_workflow.yaml`):
```yaml
name: story_workflow
version: "1.0"
kinds: [STORY, TASK]
transitions:
  - {from: IDEA, event: ready, to: READY, guards: [definition_of_ready], roles: [ORCHESTRATOR, LEAD_DEV, SCRUM_MASTER], hooks: []}
  - {from: IDEA, event: block, to: BLOCKED, guards: [], roles: [ANY_AGENT], hooks: [on_task_blocked]}
  - {from: READY, event: start_implementation, to: IMPLEMENTING, guards: [dependencies_complete, branch_available, budget_available], roles: [KERNEL], hooks: [on_task_start]}
  - {from: IMPLEMENTING, event: submit_for_review, to: READY_FOR_REVIEW, guards: [output_status_is_completed, has_commit, required_evidence_present], roles: [SENIOR_DEV], hooks: []}
  - {from: IMPLEMENTING, event: partial, to: IMPLEMENTING, guards: [handover_present], roles: [SENIOR_DEV], hooks: [on_agent_handoff]}
  - {from: IMPLEMENTING, event: block, to: BLOCKED, guards: [escalations_non_empty], roles: [SENIOR_DEV], hooks: [on_task_blocked]}
  - {from: READY_FOR_REVIEW, event: start_review, to: LEAD_DEV_REVIEW, guards: [reviewer_role_differs, reviewer_model_differs_or_disabled], roles: [KERNEL], hooks: []}
  - {from: LEAD_DEV_REVIEW, event: review_approved, to: INTEGRATION, guards: [output_status_is_approved], roles: [LEAD_DEV], hooks: []}
  - {from: LEAD_DEV_REVIEW, event: review_rejected, to: REWORK, guards: [], roles: [LEAD_DEV], hooks: []}
  - {from: INTEGRATION, event: integration_passed, to: QC, guards: [ci_green], roles: [KERNEL], hooks: [on_ready_for_qc]}
  - {from: INTEGRATION, event: ci_failed, to: REWORK, guards: [], roles: [KERNEL], hooks: [on_build_failure]}
  - {from: QC, event: qc_passed, to: COMPLETE, guards: [output_status_is_approved, required_evidence_present], roles: [QC], hooks: [on_task_complete, on_qc_result]}
  - {from: QC, event: qc_rejected, to: REWORK, guards: [fix_loops_below_max], roles: [QC], hooks: [on_qc_result, on_bug_created], effects: [increment_fix_loops]}
  - {from: QC, event: qc_rejected, to: BLOCKED, guards: [fix_loops_at_max], roles: [QC], hooks: [on_task_failed]}
  - {from: REWORK, event: start_implementation, to: IMPLEMENTING, guards: [budget_available], roles: [KERNEL], hooks: [on_task_start]}
  - {from: BLOCKED, event: unblock, to: PREVIOUS, guards: [blocker_resolved], roles: [ORCHESTRATOR, SCRUM_MASTER, USER], hooks: []}
  - {from: "* except COMPLETE", event: cancel, to: CANCELLED, guards: [], roles: [USER], hooks: [on_task_cancelled]}
  - {from: IMPLEMENTING, event: force_review, to: READY_FOR_REVIEW, guards: [], roles: [USER], hooks: []}
```
Role aliases: `KERNEL` = `AgentRole.KERNEL`; `USER` = `AgentRole.USER`; `ANY_AGENT` = any `AgentRole` except `USER`/`KERNEL`. `effects` (`NEW NAME:` table key) names kernel-side mutations applied in the same transaction: `increment_fix_loops`, `increment_reopen_count`, `store_resume_state`.

Guards registered in this story (all read WBS §3.4 payload keys): `definition_of_ready` (delegates to `check_definition_of_ready`, E01-S10 — in S09 it checks `contract.goal` and `acceptance_criteria` non-empty), `dependencies_complete`, `branch_available`, `budget_available`, `output_status_is_completed`, `output_status_is_approved`, `has_commit`, `required_evidence_present`, `handover_present`, `escalations_non_empty`, `reviewer_role_differs`, `reviewer_model_differs_or_disabled`, `ci_green`, `fix_loops_below_max`, `fix_loops_at_max`, `blocker_resolved`.

`raise_event`: INTERFACES.md §1.3 docstring. CLI: `walk work transition ID EVENT [--reason TEXT] [--payload JSON]` raises as `actor_role=USER, source=USER`.

#### Behavior
1. Loading a table whose guard, hook or role name is unknown raises `ConfigError` naming the row.
2. `transition_for` evaluates rows in file order; wildcard `*` matches any state; `* except A,B` excludes listed states.
3. `raise_event` runs in one `UnitOfWork`: `state`, `state_version += 1`, `updated_at`, effects, `work_item_transitions` row, `WORK_ITEM_TRANSITION` ledger (payload: `from, to, event, reason, resume_state?, state_version, kind, fix_loops` — `kind` is the item's `WorkItemKind` value and `fix_loops` its counter after effects; both are read by the E01-S06 `METRIC_QUERIES`); then after commit fires `ON_STATE_TRANSITION` and each transition hook with `HookContext(payload={"from":…, "to":…, "event":…})`.
4. `block` stores `resume_state = item.state` in the transition payload and on the item (`blocked_reason` from `ctx.reason` or payload); `unblock` with pseudo-target `PREVIOUS` resolves to the stored `resume_state`, else `GuardRejected("no resume_state")`.
5. `GuardRejected.detail` lists each failing guard and its reason; `PermissionDenied.detail` carries actor and allowed roles.
6. A hook failure (`HookFailed`) after commit does not roll back the transition; it is re-raised to the caller.
7. `state_version` mismatch (optimistic concurrency: `expected_state_version` in payload differing from current) raises `GuardRejected("stale state_version")`.
8. CLI exit codes: 0 ok, 2 guard rejected / permission denied, 1 unknown item/event.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `story_workflow.yaml`, When loaded, Then 18 transitions, version `1.0`, kinds STORY/TASK | `tests/workflow/test_tables.py::test_story_workflow_loads_with_expected_rows` |
| 2 | Given a YAML row with guard `nope`, When loaded, Then `ConfigError` naming the row | `tests/workflow/test_tables.py::test_loader_rejects_unknown_guard` |
| 3 | When `transition_for(READY, start_implementation)` with all payload facts true, Then row to IMPLEMENTING | `tests/workflow/test_state_machine.py::test_transition_for_selects_matching_row` |
| 4 | When event has no row for the state, Then `UnknownTransition` | `tests/workflow/test_state_machine.py::test_unknown_transition_raises` |
| 5 | Given QC/`qc_rejected` with `fix_loops=3, max_fix_loops=3`, Then the BLOCKED row is selected | `tests/workflow/test_state_machine.py::test_guard_order_selects_second_row` |
| 6 | Given actor SENIOR_DEV raising `review_approved`, Then `PermissionDenied` | `tests/workflow/test_state_machine.py::test_role_not_allowed_raises_permission_denied` |
| 7 | Given `cancel` from COMPLETE, Then `UnknownTransition` (excluded by wildcard) | `tests/workflow/test_state_machine.py::test_wildcard_except_excludes_states` |
| 8 | For each guard in the list, Given payload true/false, Then ok/not ok with reason (parametrised) | `tests/workflow/test_guards.py::test_payload_guards_evaluate_payload_keys` |
| 9 | When `reviewer_model_differs_or_disabled` with same model and `cross_model_review=False`, Then ok | `tests/workflow/test_guards.py::test_reviewer_model_guard_respects_disabled_flag` |
| 10 | When `raise_event(STORY READY, start_implementation)`, Then state IMPLEMENTING, `state_version == 1`, one transition row, one `WORK_ITEM_TRANSITION`, `ON_STATE_TRANSITION` + `ON_TASK_START` fired in order | `tests/workflow/test_service_transitions.py::test_raise_event_commits_atomically_and_fires_hooks` |
| 11 | Given ledger insert fails, When `raise_event`, Then state unchanged and no transition row | `tests/workflow/test_service_transitions.py::test_raise_event_rolls_back_on_ledger_failure` |
| 12 | When `block` then `unblock` with `blocker_resolved=True`, Then state returns to the previous state | `tests/workflow/test_service_transitions.py::test_block_and_unblock_restore_previous_state` |
| 13 | When `qc_rejected` with `fix_loops_below_max`, Then `fix_loops` incremented in the same transaction | `tests/workflow/test_service_transitions.py::test_qc_rejected_increments_fix_loops` |
| 14 | Given `expected_state_version` stale, Then `GuardRejected` | `tests/workflow/test_service_transitions.py::test_stale_state_version_rejected` |
| 15 | Given a FAIL_CLOSED hook raising, When `raise_event`, Then transition persisted and `HookFailed` raised | `tests/workflow/test_service_transitions.py::test_hook_failure_after_commit_does_not_roll_back` |
| 16 | When `walk work transition STORY-0001 ready`, Then exit 0 and `READY` printed; with a failing guard exit 2 | `tests/cli/test_cmd_work.py::test_work_transition_exit_codes` |

#### Evidence required
- Quality gate output.
- Demo: `walk work transition STORY-0001 ready` → `STORY-0001: IDEA -> READY`; `walk work transition STORY-0001 start_implementation` → exit 2 with guard reasons (`branch_available: payload missing`).

#### Notes
- ADR-0010 D-4/D-5; ADR-0002 D-9; INTERFACES §3.2.
- `NEW NAME:` YAML keys `effects` and pseudo-state `PREVIOUS`; role alias `ANY_AGENT` (table data, not Python symbols).
- Pitfall: hooks fire after COMMIT via `UnitOfWork.after_commit`; do not fire inside the transaction.
- Commit: `feat: add state machine, guard registry and story workflow table (E01-S09)`.

#### Evidence (filled by implementer)
Quality gate (`sh scripts/check.sh`, Python 3.12.11, uv 0.7.21):
```
87 files already formatted
All checks passed!
Success: no issues found in 84 source files
Required test coverage of 85% reached. Total coverage: 99.87%
283 passed in 10.23s
```
Touched modules: `workflow/state_machine.py`, `guards.py`, `service.py`, `repository.py`, `models.py`, `errors.py`, `cli/cmd_work.py` each 100%.

Demo (scratch repo from the E01-S08 demo, `STORY-0001` in IDEA):
```
$ walk work transition STORY-0001 ready --repo ./demo
STORY-0001: IDEA -> READY
$ walk work transition STORY-0001 start_implementation --repo ./demo
error: 'start_implementation' rejected for STORY-0001: branch_available: payload missing; budget_available: payload missing      (exit 2)
$ walk work transition STORY-0001 review_approved --repo ./demo
error: no transition for event 'review_approved' from READY (STORY)      (exit 1)
$ walk work transition STORY-0001 start_implementation --payload '{"branch_available": true, "budget_ok": true}' --repo ./demo
STORY-0001: READY -> IMPLEMENTING
$ walk work show STORY-0001 --repo ./demo   (tail)
transitions:
  1  2026-10-06T11:15:32.717902+00:00  IDEA -> READY  ready  USER
  2  2026-10-06T11:15:34.622313+00:00  READY -> IMPLEMENTING  start_implementation  USER
runs: none
cost: none
$ walk ledger query --kind WORK_ITEM_TRANSITION --repo ./demo
seq  at                                kind                  actor  item        run  outcome
4    2026-10-06T11:15:32.717902+00:00  WORK_ITEM_TRANSITION  USER   STORY-0001       OK
5    2026-10-06T11:15:34.622313+00:00  WORK_ITEM_TRANSITION  USER   STORY-0001       OK
```

Contract alignments (docs updated in this commit; all additive):
- INTERFACES §1.3 `Transition` gains `excluded_states` and `effects` (both default `()`), plus `applies_to(state)`. `from_state` widens to `WorkItemState | "*"` and `to_state` to `WorkItemState | "PREVIOUS"`. Without these, the story's YAML keys (`* except …`, `PREVIOUS`, `effects`) cannot be carried from `transition_for` to `raise_event`. `TransitionTable` gains `kinds` (default `()`), which AC 1 asserts and which `table_for` uses to index tables.
- ARCHITECTURE §2.3: `walk/workflow/` joins the PyYAML allow-list. The story's `TableLoader` and ADR-0010 D-4 put YAML tables there, but the confinement table did not list the package.
- **Role semantics (owner attention):** `actor_role=USER` may raise every event and guards still apply. AC 16 and the demo require `walk work transition STORY-0001 ready` to succeed as USER, but the `ready` row lists only ORCHESTRATOR/LEAD_DEV/SCRUM_MASTER. INTERFACES §6 says "Raises event as USER (guards still apply)". Agent roles are still checked strictly (AC 6). This is recorded on `Transition.allowed_roles` in INTERFACES §1.3.

Outside the Files table: `workflow/models.py`, `workflow/repository.py`, `workflow/__init__.py`, `tests/workflow/test_service_create.py` and `docs/01-architecture/*`. The changes are the model fields above. The repository gains `add_transition`, `transitions`, `last_transition_into` and `states_of`, which keep the SQL out of the service. `__init__` re-exports `StateMachine`, `TableLoader`, `TABLES_DIR` and `UnknownTransition`. The S08 deferred-method test drops the two methods implemented here.

Level-0 decisions:
- Kernel-owned guard facts: before guards run, `raise_event` adds `dependency_states` (`{dep_id: state}` of the contract dependencies, read in the transaction) and, for a BLOCKED item, `resume_state` to the payload. `resume_state` is the `from_state` of the item's latest transition into BLOCKED, so `WorkItemBase` needs no new field and the transition row is the stored resume state. Kernel values override caller values for these two keys. `dependencies_complete` therefore needs no caller input. WBS §3.4 had no key for it, and the E01-S29 scheduler sends only `budget_ok`/`branch_available`. `NEW NAME:` payload key `dependency_states`.
- Guard semantics: a boolean fact passes only when it `is True`. A missing key gives the reason `payload missing`, and `False` gives `<key> is false`. `output_status` is compared as the string value (`AgentOutputStatus` arrives in E01-S18). `max_fix_loops` defaults to 3. `required_evidence_present` and `dependencies_complete` pass when the contract requires nothing. `definition_of_ready` checks the contract goal (non-blank) and acceptance criteria, and fails "no contract" for items without one (E01-S10 extends it).
- `transition_for` filters candidate rows by role first (`PermissionDenied`, with `detail.allowed_roles` the union of the candidates' roles), then evaluates guards row by row. `GuardRejected.detail.failed_guards` lists `{guard, reason}` for every failing guard of every permitted row, and the message joins them as `guard: reason`. `UnknownTransition(PermanentError)` is raised for an unknown kind, state or event (CLI exit 1).
- `raise_event` does everything in one `UnitOfWork`: it reads the item, checks `expected_state_version` (`GuardRejected("stale state_version …")`), selects the row, resolves the target and applies effects. It then upserts the item (`state_version + 1`, `updated_at`; `completed_at` on COMPLETE; `blocked_reason` = `payload["reason"]` on entering BLOCKED and cleared on leaving it), inserts the transition row and appends `WORK_ITEM_TRANSITION` (payload `from, to, event, reason, state_version, kind, fix_loops`, plus `resume_state` on block/unblock). Hooks run through `UnitOfWork.after_commit`: first `ON_STATE_TRANSITION`, then the row's hooks, each with `HookContext(payload={from, to, event}, role=actor)`. A `HookFailed` propagates after the commit. A non-string `payload["reason"]` is a `ConfigError`.
- Effects: `increment_fix_loops`; `increment_reopen_count` (`ConfigError` on a non-bug); `store_resume_state` is a no-op, because the transition row into BLOCKED stores the resume state. The loader rejects unknown effects, guards, hooks, roles, states and row keys with `ConfigError("<file> row N (<from> --<event>-->): …")` and `detail.row = N`. The role alias `ANY_AGENT` expands to every role except USER/KERNEL.
- `DefaultWorkflowManager` loads every `*_workflow.yaml` in `tables_dir` when constructed, so a bad table fails at startup. Other YAML files, such as E01-S10's `scheduled_states.yaml`, are ignored. Two tables governing one kind, or a missing folder, raise `ConfigError`. The guard registry is the module-level dict the contract's `register_guard` implies. It is filled only at import time, and a duplicate name raises `ConfigError`.
- CLI: `walk work transition ID EVENT [--reason] [--payload JSON] [--json]` opens the DB writable only if it already exists, and raises as USER/USER. Exit codes: 2 for guard/permission rejection; 1 for an unknown item or event, invalid `--payload` (non-object) or a missing DB. `walk work show` now lists transitions (text and JSON `transitions`), which E01-S08 deferred to this story.

---

### E01-S10 — `feature_workflow`/`bug_workflow` tables, remaining guards, DoR, `ready_items`, done dimensions

**Status:** TODO
**Type:** feat
**Requirements:** §6.5, §53, §58, §61, §64, §131, §137 (Inv. 6)
**Depends on:** E01-S09
**Effort:** HIGH   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every INTERFACES §3.1–§3.3 transition and guard exists as data plus callables; Definition of Ready, ready-item selection and feature done dimensions are implemented.

#### Scope
- In: `feature_workflow.yaml`, `bug_workflow.yaml`, `scheduled_states.yaml`, remaining guards, `check_definition_of_ready`, `ready_items`, `set_done_dimension`, `increment_reopen_count` effect.
- Out: phases/RC (E01-S11), real CI/commit facts (E03), scope guard real implementation (E06-S07 — here `in_phase_scope` passes when `item.phase_id is None or payload.phase_state == "ACTIVE" and item.phase_id == ctx.phase.id`).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/tables/feature_workflow.yaml` | create | — |
| `src/walk/workflow/tables/bug_workflow.yaml` | create | — |
| `src/walk/workflow/tables/scheduled_states.yaml` | create | — |
| `src/walk/workflow/guards.py` | modify | new guards listed below |
| `src/walk/workflow/readiness.py` | create | `definition_of_ready_checks` |
| `src/walk/workflow/service.py` | modify | `check_definition_of_ready`, `ready_items`, `set_done_dimension` |
| `tests/workflow/test_tables.py` | modify | — |
| `tests/workflow/test_guards.py` | modify | — |
| `tests/workflow/test_readiness.py` | create | — |
| `tests/workflow/test_service_ready.py` | create | — |

#### Interface contract
Tables encode INTERFACES §3.1 (feature, 20 rows incl. `force_review` whose target is the pseudo-state `CHILDREN_READY_FOR_REVIEW` handled as effect `force_children_review`) and §3.3 (bug, 17 rows). New guards: `in_phase_scope`, `has_gdd_refs_or_user_feature`, `technical_design_section_present`, `required_approved_artifacts_present`, `children_created`, `all_stories_integrated`, `ci_green_on_integration_branch`, `all_applicable_dimensions_done`, `no_open_blocker_bugs`, `rework_children_created`, `phase_in_evidence_review`, `has_children_implementing`, `severity_set`, `owner_role_set`, `decision_recorded_quality`, `root_cause_section_present`, `regression_test_evidence`, `reproduction_no_longer_reproduces_evidence`, `reopen_below_max`, `reopen_at_max`. New effects: `increment_reopen_count`, `force_children_review`.
```yaml
# scheduled_states.yaml — INTERFACES §4 rows for kinds FEATURE/STORY/TASK/BUG (phase/debate rows are E05/E07)
- {kind: FEATURE, state: IDEA, role: ORCHESTRATOR, purpose: PLAN}
- {kind: FEATURE, state: DISCOVERY, role: DESIGN_LEADER, fallback_role: ORCHESTRATOR, purpose: DESIGN}
- {kind: FEATURE, state: DESIGN, role: LEAD_DEV, purpose: DESIGN}
- {kind: FEATURE, state: QC, role: QC, purpose: QC}
- {kind: STORY, state: READY, role: contract.owner_role, purpose: IMPLEMENT}   # same for TASK, and for REWORK
- {kind: STORY, state: READY_FOR_REVIEW, role: contract.reviewer_role, purpose: REVIEW}
- {kind: STORY, state: QC, role: QC, purpose: QC}
- {kind: BUG, state: DISCOVERY, role: LEAD_DEV, purpose: TRIAGE}
- {kind: BUG, state: READY, role: contract.owner_role, purpose: IMPLEMENT}    # and REWORK
- {kind: BUG, state: READY_FOR_REVIEW, role: LEAD_DEV, purpose: REVIEW}
- {kind: BUG, state: QC, role: QC, purpose: QC}
```
```python
def definition_of_ready_checks(item: WorkItem, deps: list[WorkItem]) -> list[tuple[str, bool, str]]:
    """§58: ('requirement_complete', goal non-empty), ('acceptance_criteria', non-empty), ('dependencies_resolved', all deps COMPLETE),
    ('design_approved', not required or payload/feature flag), ('assets_available', contract has no 'asset:' constraint or payload flag),
    ('constraints_known', constraints list non-empty or complexity TRIVIAL/SMALL)."""


# DefaultWorkflowManager
def check_definition_of_ready(
    self, item: WorkItem
) -> GuardResult: ...  # reason lists failing check names
async def ready_items(
    self, phase_id: PhaseId | None
) -> list[WorkItem]: ...  # scheduled_states ∩ dependencies complete ∩ (phase scope)
async def set_done_dimension(
    self,
    feature_id: FeatureId,
    dimension: DoneDimension,
    done: bool,
    evidence_id: EvidenceId | None,
) -> Feature: ...
```

#### Behavior
1. Both tables load with every guard/hook/role resolvable; `TABLES_DIR` contains exactly `story_workflow.yaml`, `feature_workflow.yaml`, `bug_workflow.yaml` (+ `phase_workflow.yaml`, `rc_workflow.yaml` after S11) and `scheduled_states.yaml`.
2. `check_definition_of_ready` returns `ok=False` with comma-separated failing check names; `definition_of_ready` guard delegates to it.
3. `ready_items` returns items whose `(kind, state)` appears in `scheduled_states.yaml`, whose contract dependencies are all `COMPLETE`, not `BLOCKED`, with `assigned_run_id is None`, and (when `phase_id` given) `item.phase_id in (phase_id, None)`; ordered by `priority`, then `created_at`.
4. `set_done_dimension` raises `ConfigError` when `dimension not in feature.applicable_dimensions`; records `evidence_id` in payload of a `WORK_ITEM_TRANSITION`? No — writes no transition; it updates `done_dimensions` and writes ledger `TASK_COMPLETED`? No — it updates the aggregate only and relies on `qc_passed` guard `all_applicable_dimensions_done`. Literal rule: update `done_dimensions`, persist, no ledger event.
5. `all_applicable_dimensions_done` is `ok` iff every `applicable_dimensions` entry maps to `True` in `done_dimensions`.
6. `qc_rejected` on a feature does not increment `fix_loops` of children; `reopen` on a bug increments `reopen_count` (effect).
7. `wont_fix` requires `decision_id` in payload (guard `decision_recorded_quality` checks presence and `payload["decision_category"] == "QUALITY"`).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `feature_workflow.yaml` loads, Then 20 rows and every INTERFACES §3.1 `(from, event)` pair present | `tests/workflow/test_tables.py::test_feature_workflow_matches_interfaces` |
| 2 | When `bug_workflow.yaml` loads, Then 17 rows and every INTERFACES §3.3 pair present | `tests/workflow/test_tables.py::test_bug_workflow_matches_interfaces` |
| 3 | When `scheduled_states.yaml` loads, Then every INTERFACES §4 FEATURE/STORY/TASK/BUG row present | `tests/workflow/test_tables.py::test_scheduled_states_match_routing_table` |
| 4 | For each new guard, Given payload true/false, Then expected result (parametrised) | `tests/workflow/test_guards.py::test_feature_and_bug_guards_evaluate_payload_keys` |
| 5 | Given a feature with `done_dimensions` missing one applicable dimension, Then `all_applicable_dimensions_done` fails naming it | `tests/workflow/test_guards.py::test_all_dimensions_guard_names_missing_dimension` |
| 6 | Given a story with empty acceptance criteria and an incomplete dependency, When `check_definition_of_ready`, Then `ok=False` reason contains both check names | `tests/workflow/test_readiness.py::test_dor_reports_all_failing_checks` |
| 7 | Given a complete contract and COMPLETE deps, Then `ok=True` | `tests/workflow/test_readiness.py::test_dor_passes_when_ready` |
| 8 | Given items in READY/IDEA/BLOCKED and one with an incomplete dependency, When `ready_items(None)`, Then only READY items with complete deps, ordered by priority | `tests/workflow/test_service_ready.py::test_ready_items_filters_and_orders` |
| 9 | Given `phase_id`, Then items of other phases excluded, phase-less items included | `tests/workflow/test_service_ready.py::test_ready_items_respects_phase_scope` |
| 10 | When `set_done_dimension(FEAT, TESTED, True)`, Then persisted; unknown dimension → `ConfigError` | `tests/workflow/test_service_ready.py::test_set_done_dimension_updates_or_rejects` |
| 11 | When bug `reopen` with `reopen_count < max_reopen`, Then REWORK and `reopen_count` incremented | `tests/workflow/test_service_ready.py::test_bug_reopen_increments_count` |
| 12 | When bug `wont_fix` without `decision_id`, Then `GuardRejected` | `tests/workflow/test_service_ready.py::test_wont_fix_requires_quality_decision` |

#### Evidence required
- Quality gate output.
- Demo: `walk work transition BUG-0001 triaged --payload '{"severity_set": true, "owner_role_set": true}'` → `BUG-0001: DISCOVERY -> READY`.

#### Notes
- ADR-0010 D-2/D-6; INTERFACES §3.1, §3.3, §4; §58.
- `NEW NAME:` `src/walk/workflow/tables/scheduled_states.yaml` (routing data consumed by `ready_items` and E01-S29 `TaskRouter`), effects `increment_reopen_count`, `force_children_review`, pseudo-state `CHILDREN_READY_FOR_REVIEW`.
- Commit: `feat: add feature and bug workflow tables, readiness and done dimensions (E01-S10)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S11 — Phases and release candidates: models, tables, `walk phase list/start/gate`

**Status:** TODO
**Type:** feat
**Requirements:** §66, §68, §70, §76, §93 (stop phase)
**Depends on:** E01-S09
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Phase and release-candidate lifecycles exist as persisted aggregates with data-driven transitions; the CLI can list/start phases and record a gate decision (intake algorithms come in E07).

#### Scope
- In: `PhaseRepository`, `ReleaseCandidateRepository`, `phase_workflow.yaml`, `rc_workflow.yaml`, `phase_event`, `rc_event`, phase/RC guards (payload-based), `walk phase list|start|gate`.
- Out: evidence package, REWORK/CHANGE intake, next-phase start (E07-S03…S07); `walk phase plan` (E06-S04); RC service (E11-S02).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/workflow/tables/phase_workflow.yaml` | create | — |
| `src/walk/workflow/tables/rc_workflow.yaml` | create | — |
| `src/walk/workflow/repository.py` | modify | `PhaseRepository`, `ReleaseCandidateRepository` |
| `src/walk/workflow/state_machine.py` | modify | `PhaseStateMachine`, `RcStateMachine` (same engine generic over state enum) |
| `src/walk/workflow/guards.py` | modify | phase/RC guards listed below |
| `src/walk/workflow/service.py` | modify | `phase_event`, `rc_event`, `create_phase`, `list_phases` |
| `src/walk/cli/cmd_phase.py` | create | `phase_app` |
| `src/walk/cli/app.py` | modify | registers `phase_app` |
| `tests/workflow/test_tables.py` | modify | — |
| `tests/workflow/test_service_phase.py` | create | — |
| `tests/cli/test_cmd_phase.py` | create | — |

#### Interface contract
Tables encode INTERFACES §3.4 (phase, 13 rows; events `decide:GO|REWORK|CHANGE|STOP`) and §3.6 (RC, 6 rows). Guards: `previous_phase_complete_or_first`, `scope_non_empty`, `kit_validated` (payload `kit_validated`, default True until E02-S03 supplies it), `all_scope_features_terminal`, `evidence_package_written`, `retrospective_written`, `feedback_non_empty`, `rework_work_items_created`, `impact_analysis_evidence_present`, `approval_user`, `build_evidence_present`, `qc_report_evidence`, `rejection_bugs_created`, `rejection_bugs_complete`.
```python
# DefaultWorkflowManager additions
async def create_phase(
    self, name: str, ordinal: int, *, goal: str = "", scope_epic_ids: list[EpicId] = ()
) -> Phase: ...  # id PHASE-NN
async def list_phases(self) -> list[Phase]: ...
async def phase_event(
    self, phase_id: PhaseId, event: str, ctx: TransitionContext
) -> Phase: ...  # ledger PHASE_TRANSITION; decide:* also PHASE_GATE_DECISION (payload decision, feedback); gate_round += 1 on package_ready
async def rc_event(
    self, rc_id: ReleaseCandidateId, event: str, ctx: TransitionContext
) -> ReleaseCandidate: ...  # ledger RC_TRANSITION
```
CLI: `walk phase list`, `walk phase start ID`, `walk phase gate ID --decision GO|REWORK|CHANGE|STOP [--feedback TEXT|@FILE]`.

#### Behavior
1. `create_phase` enforces unique `ordinal` (`ix_phases_ordinal`) → `ConfigError` on duplicate.
2. `phase_event("start")` sets `started_at`; `decide:GO` sets `completed_at` and `last_decision`; `decide:STOP` sets `Project.paused = True`.
3. `decide:REWORK|CHANGE` require `feedback` in payload (guard `feedback_non_empty`).
4. `package_ready` increments `gate_round`.
5. `PHASE_GATE_DECISION` is written by `phase_event` for `decide:*` in the same transaction as `PHASE_TRANSITION` (ARCHITECTURE §4.3 names `orchestrator.PhaseGate` as the write point; E07-S05 moves the write there and this story's write is removed then — state this in E07-X01 refine).
6. `rc_event("next_rc")` creates a new `ReleaseCandidate` with `number + 1` in `BUILDING`.
7. CLI `gate` with `--decision` outside the enum exits 1; guard rejection exits 2.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `phase_workflow.yaml` loads, Then 13 rows covering every INTERFACES §3.4 pair | `tests/workflow/test_tables.py::test_phase_workflow_matches_interfaces` |
| 2 | When `rc_workflow.yaml` loads, Then 6 rows covering §3.6 | `tests/workflow/test_tables.py::test_rc_workflow_matches_interfaces` |
| 3 | When `create_phase("Prototype", 1)`, Then `PHASE-01`, PLANNED; duplicate ordinal → `ConfigError` | `tests/workflow/test_service_phase.py::test_create_phase_allocates_id_and_unique_ordinal` |
| 4 | When `phase_event(start)` with scope and first phase, Then ACTIVE, `started_at` set, `PHASE_TRANSITION` written, `ON_PHASE_START` fired | `tests/workflow/test_service_phase.py::test_phase_start_transitions_and_fires_hook` |
| 5 | Given ordinal 2 and phase 1 not COMPLETE, When `start`, Then `GuardRejected` | `tests/workflow/test_service_phase.py::test_phase_start_requires_previous_complete` |
| 6 | Given USER_GATE, When `decide:REWORK` without feedback, Then `GuardRejected`; with feedback → REWORK and `PHASE_GATE_DECISION` | `tests/workflow/test_service_phase.py::test_gate_rework_requires_feedback` |
| 7 | When `decide:STOP`, Then STOPPED and project paused | `tests/workflow/test_service_phase.py::test_gate_stop_pauses_project` |
| 8 | When `package_ready`, Then `gate_round == 1` | `tests/workflow/test_service_phase.py::test_package_ready_increments_gate_round` |
| 9 | When `rc_event(next_rc)` from REJECTED with bugs complete, Then new RC number 2 in BUILDING | `tests/workflow/test_service_phase.py::test_rc_next_creates_successor` |
| 10 | When `walk phase list`, Then table with id/ordinal/state; `walk phase start PHASE-01` → `ACTIVE` | `tests/cli/test_cmd_phase.py::test_phase_list_and_start` |
| 11 | When `walk phase gate PHASE-01 --decision MAYBE`, Then exit 1 | `tests/cli/test_cmd_phase.py::test_phase_gate_rejects_unknown_decision` |

#### Evidence required
- Quality gate output.
- Demo: `walk phase list` → `PHASE-01 | 1 | Prototype | PLANNED`; `walk phase start PHASE-01` → `PHASE-01: PLANNED -> ACTIVE`.

#### Notes
- ADR-0010 D-3; INTERFACES §3.4, §3.6; ARCHITECTURE §10 ("gate CLI minimal").
- Phase `USER_GATE`/`PHASE_REVIEW` projections onto features are not implemented here (dashboards, E07).
- Commit: `feat: add phase and release candidate lifecycles with phase cli (E01-S11)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S12 — Budgets and cost: `BudgetManager`, `CostManager`, `walk cost`

**Status:** TODO
**Type:** feat
**Requirements:** §20, §84, §85, §86
**Depends on:** E01-S05, E01-S07
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Budgets at Global/Project/Phase/Role/Task scope with soft/hard thresholds and hooks, cost records with roll-ups, and a `walk cost` CLI.

#### Scope
- In: `budgets.models` incl. RELOCATED `BudgetPolicy` and `BudgetVerdict`, `BudgetRepository`, `CostRepository`, `DefaultBudgetManager`, `DefaultCostManager`, `walk cost`.
- Out: token→USD conversion (`model_router.costing`, E01-S20); CI/compute/time cost completeness (E09-S03).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/budgets/__init__.py` | create | re-exports |
| `src/walk/budgets/models.py` | create | `BudgetScope`, `BudgetDimension`, `CostCategory`, `BudgetHardAction`, `Budget`, `BudgetSubject`, `CostRecord`, `BudgetPolicy`, `BudgetVerdict` |
| `src/walk/budgets/protocols.py` | create | `BudgetManager`, `CostManager` |
| `src/walk/budgets/repository.py` | create | `BudgetRepository`, `CostRepository` |
| `src/walk/budgets/service.py` | create | `DefaultBudgetManager`, `DefaultCostManager` |
| `src/walk/budgets/errors.py` | create | `BudgetExhausted` |
| `src/walk/cli/cmd_cost.py` | create | `cost_app` |
| `src/walk/cli/app.py` | modify | registers `cost_app` |
| `tests/budgets/__init__.py` | create | — |
| `tests/budgets/test_models.py` | create | — |
| `tests/budgets/test_budget_manager.py` | create | — |
| `tests/budgets/test_cost_manager.py` | create | — |
| `tests/cli/test_cmd_cost.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 budgets enums, §4.4, plus `BudgetPolicy` (DOMAIN-MODEL §4.2 definition, relocated) and `BudgetVerdict` (INTERFACES §1.6). Protocols: INTERFACES.md §1.6. Deltas:
```python
class BudgetExhausted(PermanentError):
    """hard limit reached; detail: budget id, hard_action"""


class DefaultBudgetManager:
    def __init__(
        self,
        db: Database,
        repo: BudgetRepository,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
    ) -> None: ...


class DefaultCostManager:
    def __init__(
        self,
        db: Database,
        repo: CostRepository,
        ledger: LedgerManager,
        budgets: BudgetManager,
        items: WorkflowRepository,
    ) -> None: ...
```
CLI: `walk cost --item ID | --phase ID | --project` → table `category | usd` and total; `--json`.

#### Behavior
1. `ensure` creates one `Budget` per dimension in `policy.per_task` (or `limits`) with id `<scope>:<scope_id>:<dimension>`; existing rows are untouched (idempotent).
2. `applicable(subject)` returns budgets for GLOBAL, PROJECT(subject.project_key), PHASE, ROLE, TASK where the subject field is set.
3. `meter` adds `quantity` to every applicable budget in one transaction and writes one `BUDGET_EVENT` (payload: dimension, quantity, per-budget consumed/limit). Verdict: `EXHAUSTED(hard_action)` if any budget `consumed >= limit`; else `SOFT_THRESHOLD` if any crossed `soft_threshold_ratio` for the first time (`soft_notified` set, `ON_BUDGET_THRESHOLD` fired once per budget); else `OK`. `ON_BUDGET_EXHAUSTED` fired on EXHAUSTED.
4. `headroom` = min over applicable `(limit − consumed)` per dimension; dimensions without budgets are absent from the dict (callers treat absent as unlimited).
5. `can_afford` true iff for every listed scope id the budget for `dimension` has `limit − consumed >= quantity` (missing budget → true).
6. `CostManager.record` inserts `cost_records` + `COST_RECORDED` then meters `COST_USD` (and `TOKENS` when `dimension == TOKENS`) on the subject derived from the record.
7. `cost_of(work_item_id)` sums records of the item and all descendants (recursive `parent_id`, plus bugs with `related_feature_id`), grouped by `CostCategory`; `cost_of(phase_id)`/`cost_of(project_key)` group directly.
8. `meter` with negative quantity raises `ValueError`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `BudgetPolicy()` defaults, Then `per_task` has COST_USD 15, TOOL_CALLS 400, EXECUTION_TIME_S 2700, REVIEW_LOOPS 3 | `tests/budgets/test_models.py::test_budget_policy_defaults` |
| 2 | When `ensure(TASK, "STORY-0001", policy)` twice, Then 4 rows once, ids formatted `TASK:STORY-0001:COST_USD` | `tests/budgets/test_budget_manager.py::test_ensure_is_idempotent_and_formats_ids` |
| 3 | Given GLOBAL, PROJECT, ROLE, TASK budgets, When `applicable(subject)`, Then all four returned, PHASE absent when `phase_id is None` | `tests/budgets/test_budget_manager.py::test_applicable_covers_subject_scopes` |
| 4 | Given TASK COST_USD limit 10, When `meter(…, 8.5)`, Then `SOFT_THRESHOLD`, `ON_BUDGET_THRESHOLD` fired once, `BUDGET_EVENT` written | `tests/budgets/test_budget_manager.py::test_meter_soft_threshold_fires_once` |
| 5 | When `meter` again with 0.5 (still above soft), Then `OK` and no second threshold hook | `tests/budgets/test_budget_manager.py::test_soft_threshold_not_refired` |
| 6 | When `meter` pushes `consumed >= limit`, Then `EXHAUSTED` with `hard_action` and `ON_BUDGET_EXHAUSTED` fired | `tests/budgets/test_budget_manager.py::test_meter_exhausted_fires_hook` |
| 7 | Given TASK and ROLE budgets, When `meter`, Then both consumed in one transaction (ledger failure → neither) | `tests/budgets/test_budget_manager.py::test_meter_is_atomic_across_budgets` |
| 8 | When `headroom`, Then min across scopes per dimension | `tests/budgets/test_budget_manager.py::test_headroom_is_minimum_across_scopes` |
| 9 | When `meter(…, -1)`, Then `ValueError` | `tests/budgets/test_budget_manager.py::test_meter_rejects_negative` |
| 10 | When `record(cost_record)`, Then `cost_records` row, `COST_RECORDED`, and TASK COST_USD consumed | `tests/budgets/test_cost_manager.py::test_record_persists_and_meters` |
| 11 | Given a feature with 2 stories and a bug, When `cost_of(work_item_id=FEAT)`, Then sums descendants by category | `tests/budgets/test_cost_manager.py::test_cost_of_rolls_up_descendants` |
| 12 | When `cost_of(phase_id=…)`, Then phase-scoped totals | `tests/budgets/test_cost_manager.py::test_cost_of_phase` |
| 13 | When `walk cost --item FEAT-0001 --json`, Then JSON with categories and `total_usd` | `tests/cli/test_cmd_cost.py::test_cost_item_json` |

#### Evidence required
- Quality gate output.
- Demo: `walk cost --project` → `LLM | 0.00` … `total 0.00` on a fresh DB.

#### Notes
- `RELOCATE: BudgetPolicy → walk.budgets.models` (WBS §3.2). `NEW NAME: BudgetExhausted`.
- ARCHITECTURE §4.3: `BUDGET_EVENT`, `COST_RECORDED` written here; hooks `ON_BUDGET_THRESHOLD`/`ON_BUDGET_EXHAUSTED` default attachments are E02-S08.
- Commit: `feat: add budget metering and cost accounting (E01-S12)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S13 — Effort resolution: `EffortManager`

**Status:** TODO
**Type:** feat
**Requirements:** §17, §18, §19
**Depends on:** E01-S10, E01-S12
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Effective effort is resolved deterministically from role default, task complexity, risk, workflow stage, escalation and budget headroom; dynamic changes are evaluated per §19 and take effect on the next run.

#### Scope
- In: `effort.models` incl. RELOCATED `EffortPolicy`, `DefaultEffortManager.resolve/request_change`, static cost table + rolling mean hook.
- Out: provider mapping (`map_effort`, E01-S19/S21/S22), approval persistence (E02-S11) — `request_change` receives an injected `request_approval` callback.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/effort/__init__.py` | create | re-exports |
| `src/walk/effort/models.py` | create | `EffortPolicy`, `EffortRequest`, `EffortResolution`, `EFFORT_ORDER`, `STATIC_COST_USD` |
| `src/walk/effort/protocols.py` | create | `EffortManager`, `CostEstimator` |
| `src/walk/effort/service.py` | create | `DefaultEffortManager`, `StaticCostEstimator` |
| `tests/effort/__init__.py` | create | — |
| `tests/effort/test_resolve.py` | create | — |
| `tests/effort/test_request_change.py` | create | — |

#### Interface contract
`EffortPolicy` = DOMAIN-MODEL §4.2 definition (relocated); `EffortRequest`, `EffortResolution` = DOMAIN-MODEL §4.3. Protocol: INTERFACES.md §1.5. Deltas:
```python
EFFORT_ORDER: tuple[Effort, ...] = (Effort.LOW, Effort.MEDIUM, Effort.HIGH, Effort.VERY_HIGH)
STATIC_COST_USD: dict[Effort, float] = {LOW: 1, MEDIUM: 3, HIGH: 8, VERY_HIGH: 20}  # ADR-0011 D-5


class CostEstimator(Protocol):
    def estimate(self, role: AgentRole, effort: Effort) -> float: ...


class StaticCostEstimator: ...  # STATIC_COST_USD; E09-S03 adds the rolling-mean estimator (>= 10 samples)


class DefaultEffortManager:
    def __init__(
        self,
        estimator: CostEstimator,
        ledger: LedgerManager,
        hooks: HookManager,
        clock: Clock,
        request_approval: Callable[[RunId, EffortRequest], Awaitable[bool]],
    ) -> None: ...
    def resolve(
        self,
        policy: EffortPolicy,
        item: WorkItem,
        state: WorkItemState,
        escalation_bump: int,
        budget_headroom: dict[BudgetDimension, float],
    ) -> EffortResolution: ...
    async def request_change(
        self,
        run_id: RunId,
        current: Effort,
        request: EffortRequest,
        policy: EffortPolicy,
        headroom: dict[BudgetDimension, float],
    ) -> Effort: ...
```

#### Behavior
1. `resolve` implements INTERFACES §5.2 steps 1–8 literally; items without a contract (EPIC/FEATURE) use `policy.default` as base.
2. `clamped_by_policy` is true iff step 6 changed the index; `clamped_by_budget` iff step 7 reduced it; missing `COST_USD` headroom means unlimited.
3. `resolve` is pure: no I/O, no ledger.
4. `request_change`: (a) target outside `[policy.min, policy.max]` → return `current`, no event; (b) UPGRADE with `auto_approve_upgrade_within_budget=False` → await `request_approval`; denied → return `current`; (c) UPGRADE whose `estimate(target) − estimate(current) > headroom[COST_USD]` → return `current` and fire nothing (observation is E04-S13); (d) otherwise fire `ON_EFFORT_CHANGE` and write `EFFORT_CHANGED` (payload: from, to, direction, reason) and return `target`.
5. DOWNGRADE never needs approval or budget.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given complexity NORMAL, default MEDIUM, risk MEDIUM, state READY, bump 0, Then `effective == MEDIUM` | `tests/effort/test_resolve.py::test_resolve_baseline_medium` |
| 2 | Given complexity SMALL (LOW) and default MEDIUM, Then floor keeps MEDIUM (step 2) | `tests/effort/test_resolve.py::test_role_default_is_a_floor` |
| 3 | Given risk CRITICAL (+2), Then HIGH→VERY_HIGH clamped by `policy.max=HIGH` with `clamped_by_policy` | `tests/effort/test_resolve.py::test_risk_bump_and_policy_clamp` |
| 4 | Given state REWORK, Then +1 stage bump | `tests/effort/test_resolve.py::test_stage_bump_for_rework` |
| 5 | Given escalation_bump 1, Then +1 | `tests/effort/test_resolve.py::test_escalation_bump_applied` |
| 6 | Given headroom COST_USD 2.5 and effective HIGH, Then downgraded to LOW with `clamped_by_budget` | `tests/effort/test_resolve.py::test_budget_headroom_downgrades` |
| 7 | Given no COST_USD headroom key, Then no budget clamp | `tests/effort/test_resolve.py::test_missing_headroom_is_unlimited` |
| 8 | Given a FEATURE (no contract), Then base is `policy.default` | `tests/effort/test_resolve.py::test_items_without_contract_use_default` |
| 9 | When `request_change(UPGRADE to VERY_HIGH)` with `max=HIGH`, Then returns current, no ledger | `tests/effort/test_request_change.py::test_target_outside_policy_is_denied` |
| 10 | Given auto-approve false and approval callback returns False, Then current | `tests/effort/test_request_change.py::test_upgrade_requires_approval_when_configured` |
| 11 | Given upgrade cost delta > headroom, Then current, no event | `tests/effort/test_request_change.py::test_upgrade_denied_by_budget` |
| 12 | Given valid upgrade, Then returns target, `ON_EFFORT_CHANGE` fired, `EFFORT_CHANGED` written | `tests/effort/test_request_change.py::test_upgrade_approved_fires_hook_and_ledger` |
| 13 | Given DOWNGRADE with no headroom, Then returns target | `tests/effort/test_request_change.py::test_downgrade_always_allowed` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0011 D-5/D-6; INTERFACES §5.2. `RELOCATE: EffortPolicy → walk.effort.models`. `NEW NAME: CostEstimator`, `StaticCostEstimator`, `EFFORT_ORDER`, `STATIC_COST_USD`.
- Commit: `feat: add effort resolution and dynamic effort requests (E01-S13)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S14 — Tool and skill catalogues: `ToolRegistry`, `tools.yaml`, `Skill`/`SkillProjector` models

**Status:** TODO
**Type:** feat
**Requirements:** §28, §29, §30, §91 (tool allowlist)
**Depends on:** E01-S12
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The closed set of kernel tools exists as data with availability resolution and shell-command identification, and the skill data contracts adapters implement exist.

#### Scope
- In: `tools.models/protocols/service`, `src/walk/tools/builtin/tools.yaml`, `skills.models`, `skills.protocols.SkillProjector`.
- Out: `SkillRegistry` service and builtin skills (E02-S05), projections (E02-S06), permission rules (E01-S15).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/tools/__init__.py` | create | re-exports |
| `src/walk/tools/models.py` | create | `ToolKind`, `ToolSpec` |
| `src/walk/tools/protocols.py` | create | `ToolRegistry` |
| `src/walk/tools/service.py` | create | `DefaultToolRegistry`, `load_tool_specs` |
| `src/walk/tools/builtin/__init__.py` | create | — |
| `src/walk/tools/builtin/tools.yaml` | create | — |
| `src/walk/skills/__init__.py` | create | re-exports |
| `src/walk/skills/models.py` | create | `Skill`, `SkillProjection`, `DriftReport` |
| `src/walk/skills/protocols.py` | create | `SkillProjector`, `SkillRegistry` (protocol only; service in E02-S05) |
| `tests/tools/__init__.py`, `tests/skills/__init__.py` | create | — |
| `tests/tools/test_registry.py` | create | — |
| `tests/tools/test_builtin_tools.py` | create | — |
| `tests/skills/test_models.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 `ToolKind`, §4.6 `ToolSpec`, `Skill`, `SkillProjection`, `DriftReport`. Protocols: INTERFACES.md §1.11 `ToolRegistry`, `SkillProjector`, `SkillRegistry`. Deltas:
```python
def load_tool_specs(
    paths: list[Path],
) -> list[ToolSpec]: ...  # builtin yaml + project overrides; duplicate name → ConfigError


class DefaultToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None: ...
```
`tools.yaml` rows (`name | kind | provider | protected_action | requires_env | command_patterns`):
PROVIDER_NATIVE: `bash`, `read`, `write`, `edit`, `glob`, `grep` · KERNEL/git: `git.commit`, `git.push`, `git.merge_protected` (protected `git.merge_protected`), `git.delete_branch_protected` (protected) · KERNEL/jira: `jira.create_task`, `jira.create_bug`, `jira.transition`, `jira.comment`, `jira.close_feature`, `jira.reopen`, `jira.delete` (protected) · KERNEL/kernel: `review.approve`, `review.reject`, `qc.approve`, `qc.reject`, `work.plan`, `permissions.alter` (protected), `credentials.change` (protected), `monetization.change` (protected), `repo.delete_data` (protected), `store.publish` (protected) · KERNEL/unity: `unity.compile`, `unity.run_tests`, `unity.build` (requires_env `unity`) · KERNEL/graphify: `graph.query`, `graph.neighbors` (requires_env `graphify`) · KERNEL/asset: `asset.generate` (requires_env `meshy|openart`). CLI patterns: `bash` identifies `^git\b`, `^dotnet\b`, `^graphify\b`, `^Unity(\.exe)?\b` as CLI sub-tools `git-cli`, `dotnet`, `graphify-cli`, `unity-cli` (kind CLI, `executable` set).

#### Behavior
1. `load_tool_specs` merges builtin then project files; a project row with an existing name replaces it; invalid rows → `ConfigError` with row index.
2. `available(ready_env_keys)` keeps specs whose `requires_env ⊆ ready_env_keys`; specs with `requires_env` containing `a|b` alternatives are available when any alternative is ready.
3. `for_role(allowed, ready, required)` = specs named in `allowed ∪ required` that are available; a required tool missing or unavailable → `ConfigError` listing it.
4. `identify(command)` returns the first CLI spec whose `command_patterns` regex matches the command start, else `None`.
5. `get(unknown)` → `ConfigError`.
6. `Skill.content_sha256` is the sha256 of `body_markdown`; `SkillProjection` is frozen.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `tools.yaml` loads, Then every tool name in the contract list exists with the stated kind | `tests/tools/test_builtin_tools.py::test_builtin_tools_cover_mvp_list` |
| 2 | Then every protected tool has `protected_action == name` | `tests/tools/test_builtin_tools.py::test_protected_tools_declare_protected_action` |
| 3 | Given a project yaml redefining `bash`, When loaded, Then the project row wins | `tests/tools/test_registry.py::test_project_override_replaces_builtin` |
| 4 | Given duplicate names within one file, Then `ConfigError` | `tests/tools/test_registry.py::test_duplicate_tool_name_rejected` |
| 5 | Given `ready={"git"}`, When `available`, Then unity tools excluded | `tests/tools/test_registry.py::test_available_filters_by_env` |
| 6 | Given `required=["unity.compile"]` and no unity env, When `for_role`, Then `ConfigError` names it | `tests/tools/test_registry.py::test_for_role_missing_required_raises` |
| 7 | When `identify("git status --porcelain")`, Then `git-cli`; `identify("ls")` → `None` | `tests/tools/test_registry.py::test_identify_matches_cli_patterns` |
| 8 | When `get("nope")`, Then `ConfigError` | `tests/tools/test_registry.py::test_get_unknown_raises` |
| 9 | When a `Skill` is built, Then `content_sha256` matches sha256 of body; `SkillProjection` immutable | `tests/skills/test_models.py::test_skill_hash_and_projection_frozen` |

#### Evidence required
- Quality gate output.

#### Notes
- §30 "Role → Skill → Tool → Provider"; ADR-0006 D-2 (kernel tools executed by the kernel); ADR-0007 D-6.
- `NEW NAME:` CLI sub-tool names `git-cli`, `dotnet`, `graphify-cli`, `unity-cli`; `load_tool_specs`.
- Commit: `feat: add tool registry with builtin catalogue and skill contracts (E01-S14)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S15 — Permission policy core: `PermissionManager.decide/rules_for`

**Status:** TODO
**Type:** feat
**Requirements:** §31, §63, §91, §92, §137 (Inv. 4, 7)
**Depends on:** E01-S14
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Pure, deterministic permission evaluation (ADR-0006 D-3) with default deny, plus persistence-only approval request storage so the enforcement point (E01-S26) can be built.

#### Scope
- In: `permissions.models`, `permissions.protocols`, `DefaultPermissionManager.rules_for/decide`, `ApprovalRepository`, persistence-only `request_approval/decide_approval/pending` (rows + ledger events, no run pausing/timeouts/CLI).
- Out: default rule set YAML, `permissions.yaml` loader, protected-action list config (E02-S10); run pausing, expiry, `walk approve/deny` (E02-S11).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/permissions/__init__.py` | create | re-exports |
| `src/walk/permissions/models.py` | create | `PermissionEffect`, `Approver`, `ApprovalState`, `PermissionRule`, `ProtectedAction`, `ToolCallRequest`, `PermissionDecision`, `ApprovalRequest` |
| `src/walk/permissions/protocols.py` | create | `PermissionManager` |
| `src/walk/permissions/matching.py` | create | `tool_pattern_specificity`, `match_tool`, `command_allowed`, `path_inside_worktree` |
| `src/walk/permissions/repository.py` | create | `ApprovalRepository` |
| `src/walk/permissions/service.py` | create | `DefaultPermissionManager` |
| `tests/permissions/__init__.py` | create | — |
| `tests/permissions/test_matching.py` | create | — |
| `tests/permissions/test_decide.py` | create | — |
| `tests/permissions/test_rules_for.py` | create | — |
| `tests/permissions/test_approvals.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 permissions enums, §4.5 verbatim. Protocol: INTERFACES.md §1.10. Deltas:
```python
def tool_pattern_specificity(
    pattern: str,
) -> int: ...  # exact 3 > dotted prefix glob "git.*" 2 > "*" 1 > no match 0
def match_tool(pattern: str, tool: ToolName) -> bool: ...
def command_allowed(
    command: str, allow_rules: list[PermissionRule], deny_rules: list[PermissionRule]
) -> tuple[bool, str]: ...
def path_inside_worktree(
    path: str, worktree: str
) -> bool: ...  # resolves symlinks/.., Windows-safe


class DefaultPermissionManager:
    def __init__(
        self,
        rules: list[PermissionRule],
        protected: list[ProtectedAction],
        repo: ApprovalRepository,
        ledger: LedgerManager,
        hooks: HookManager,
        ids: IdSequenceStore,
        clock: Clock,
    ) -> None: ...
```

#### Behavior
1. `rules_for(role, extra)`: kernel rules for `role` + `extra`; duplicates `(tool, effect)` collapsed; an `extra`/project rule may only narrow: an `ALLOW` on a tool the kernel set denies or requires approval for is dropped with a logged warning (ADR-0013 D-4).
2. `decide`: collect rules for `request.role` matching `request.tool`; keep the most specific group; effect precedence `DENY > REQUIRE_APPROVAL > ALLOW`; no rule → `DENY("no matching rule")`.
3. If `request.tool` names a `ProtectedAction` (or the matching `ToolSpec.protected_action`), effect is forced to `REQUIRE_APPROVAL(approver=action.approver)` regardless of rules (D-3 "cannot be downgraded").
4. For shell tools (`request.command` set): must match at least one `command_patterns` entry of an ALLOW rule and none of a DENY rule; otherwise `DENY` with the offending pattern in `reason`.
5. For file tools (`request.paths` set): every path must be inside `request.worktree_path` and, when the matched rule has `path_patterns`, match one of them; otherwise `DENY`.
6. `request_approval` persists `ApprovalRequest(PENDING)` with `APV-` id, writes `APPROVAL_REQUESTED`, fires `ON_PROTECTED_ACTION_REQUESTED`; `decide_approval` sets `APPROVED|DENIED`, `decided_at/by/note`, writes `APPROVAL_DECIDED`; `pending(approver)` lists PENDING rows. Run pausing/wakeup and expiry are E02-S11.
7. `decide` is pure (no I/O) and never raises for well-formed requests.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When specificity of `git.commit`, `git.*`, `*`, `jira.*` vs tool `git.commit`, Then 3, 2, 1, 0 | `tests/permissions/test_matching.py::test_tool_pattern_specificity` |
| 2 | When `path_inside_worktree("../x", wt)`, Then False; a path via symlink outside → False | `tests/permissions/test_matching.py::test_path_inside_worktree_rejects_escapes` |
| 3 | Given ALLOW `git.*` and DENY `git.push`, When tool `git.push`, Then DENY (more specific) | `tests/permissions/test_decide.py::test_most_specific_rule_wins` |
| 4 | Given ALLOW and REQUIRE_APPROVAL with equal specificity, Then REQUIRE_APPROVAL | `tests/permissions/test_decide.py::test_precedence_deny_over_approval_over_allow` |
| 5 | Given no rule for the tool, Then DENY with reason `no matching rule` | `tests/permissions/test_decide.py::test_default_deny` |
| 6 | Given `bash` ALLOW with pattern `^pytest`, When command `rm -rf /`, Then DENY | `tests/permissions/test_decide.py::test_shell_command_must_match_allow_pattern` |
| 7 | Given DENY pattern `git push --force` and ALLOW `^git`, When `git push --force`, Then DENY naming the deny pattern | `tests/permissions/test_decide.py::test_shell_deny_pattern_overrides_allow` |
| 8 | Given file tool with a path outside the worktree, Then DENY | `tests/permissions/test_decide.py::test_file_path_outside_worktree_denied` |
| 9 | Given ALLOW `git.merge_protected` for LEAD_DEV and protected action configured, Then REQUIRE_APPROVAL(USER) | `tests/permissions/test_decide.py::test_protected_action_forces_approval` |
| 10 | Given extra rule ALLOW `jira.close_feature` for SENIOR_DEV while kernel denies it, When `rules_for`, Then the extra rule is dropped | `tests/permissions/test_rules_for.py::test_extra_rules_may_only_narrow` |
| 11 | Given duplicate rules, Then de-duplicated | `tests/permissions/test_rules_for.py::test_rules_for_deduplicates` |
| 12 | When `request_approval`, Then row PENDING with `APV-0001`, `APPROVAL_REQUESTED`, hook fired | `tests/permissions/test_approvals.py::test_request_approval_persists_and_logs` |
| 13 | When `decide_approval(id, True, by="user")`, Then APPROVED, `APPROVAL_DECIDED`; unknown id → `ConfigError` | `tests/permissions/test_approvals.py::test_decide_approval_updates_or_rejects` |
| 14 | When `pending(Approver.USER)`, Then only PENDING rows for USER | `tests/permissions/test_approvals.py::test_pending_filters_by_approver` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0006 D-1/D-3/D-7; ADR-0013 D-4. Default rule set data lives in E02-S10; this story's tests construct rules inline.
- `NEW NAME:` module `walk.permissions.matching` and its functions.
- Commit: `feat: add permission evaluation core and approval persistence (E01-S15)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S16 — Memory core: front matter, `MemoryDocument`, atomic `write`, `apply_updates`, handovers, index

**Status:** TODO
**Type:** feat
**Requirements:** §6.2, §22, §34, §35, §41, §42 (stamping), §91 (secret isolation), §130, §137 (Inv. 2)
**Depends on:** E01-S05, E01-S07
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every `.ai/` document is parsed and written through one validated, atomic path that stamps freshness, refuses secrets, maintains `memory_index`, and supports section-level updates and handover documents.

#### Scope
- In: `memory.models` subset, front-matter parser/renderer, section-order tables, `DefaultMemoryManager.root/read/write/apply_updates/write_handover/read_handover/rebuild_index/write_report`, `MemoryIndexRepository`, `walk memory index`.
- Out: typed `FeatureContext/BugContext/ProjectContext` parsing (E04-S01), `assess_freshness` (E04-S03), `approve_artifact/verify_approved_artifacts` (E02-S12) — declared in the protocol, implemented there.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/memory/__init__.py` | create | re-exports |
| `src/walk/memory/models.py` | create | `FreshnessStatus`, `MemoryDocType`, `ApprovedArtifactKind`, `ApprovalStatus`, `Freshness`, `FreshnessAssessment`, `RelatedLinks`, `FrontMatter`, `MemoryDocument`, `ContextUpdate`, `ApprovedArtifact`, `ProjectContext`, `FeatureContext`, `BugContext` |
| `src/walk/memory/protocols.py` | create | `MemoryManager` |
| `src/walk/memory/errors.py` | create | `DocumentNotFound`, `SecretDetected`, `ApprovedWriteRefused` |
| `src/walk/memory/frontmatter.py` | create | `parse_document`, `render_document` |
| `src/walk/memory/sections.py` | create | `SECTION_ORDER`, `sections_for`, `skeleton_for` |
| `src/walk/memory/secrets.py` | create | `SECRET_PATTERNS`, `find_secrets` |
| `src/walk/memory/paths.py` | create | `doc_path_for`, `folder_for_type` |
| `src/walk/memory/repository.py` | create | `MemoryIndexRepository`, `MemoryIndexRow` |
| `src/walk/memory/service.py` | create | `DefaultMemoryManager` |
| `src/walk/cli/cmd_memory.py` | create | `memory_app` |
| `src/walk/cli/app.py` | modify | registers `memory_app` |
| `tests/memory/__init__.py` | create | — |
| `tests/memory/test_frontmatter.py` | create | — |
| `tests/memory/test_sections.py` | create | — |
| `tests/memory/test_secrets.py` | create | — |
| `tests/memory/test_service_write.py` | create | — |
| `tests/memory/test_service_updates.py` | create | — |
| `tests/memory/test_index.py` | create | — |
| `tests/cli/test_cmd_memory.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 memory enums, §4.7 verbatim. Protocol: INTERFACES.md §1.8 (`approve_artifact`, `verify_approved_artifacts`, `assess_freshness`, `read_feature_context`, `read_bug_context`, `read_project_context` raise `ConfigError("implemented in E02-S12 / E04-S01 / E04-S03")` until those stories). Deltas:
```python
def parse_document(
    path: Path, text: str
) -> (
    MemoryDocument
): ...  # YAML front matter between leading '---' lines; H2 sections in order; unknown H2 kept
def render_document(
    doc: MemoryDocument,
) -> (
    str
): ...  # deterministic: sorted-key YAML, sections in SECTION_ORDER then unknown in original order


SECTION_ORDER: dict[
    MemoryDocType, tuple[str, ...]
]  # feature §37 (14), bug §38 (12), project §36 (10), handover §22 (10), decision §44 (11: Topic, Participants, Positions, Evidence, Outcome, Owner, Rationale, Alternatives, Affected Systems, Related Work, Version), approved §33 (Status, Scope, Version, Approved By, Related Requirements, Payload)


def skeleton_for(
    doc_type: MemoryDocType, id_: str, title: str, actor: Actor, now: datetime
) -> MemoryDocument: ...  # all sections present, empty


SECRET_PATTERNS: tuple[
    re.Pattern[str], ...
]  # r"AKIA[0-9A-Z]{16}", r"\bsk-[A-Za-z0-9]{20,}", r"\bghp_[A-Za-z0-9]{36}", r"\bATATT[A-Za-z0-9_-]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"


def find_secrets(text: str) -> list[str]: ...  # pattern names found
def doc_path_for(
    ai_root: Path, doc_type: MemoryDocType, id_: str
) -> Path: ...  # ARCHITECTURE §8 layout; project → project/project.md


class DefaultMemoryManager:
    def __init__(
        self,
        ai_root: Path,
        index: MemoryIndexRepository,
        ledger: LedgerManager,
        hooks: HookManager,
        ids: IdSequenceStore,
        clock: Clock,
    ) -> None: ...
```

#### Behavior
1. `parse_document` raises `ConfigError` when front matter is missing, `id` ≠ file stem, or `type` unknown.
2. `write(doc, actor, head, branch)`: validate; `version = existing.version + 1` (1 for new); `updated_at = now`, `updated_by = actor`; `freshness = Freshness(commit=head, branch=branch, timestamp=now)` preserving `pr/build` if given; `find_secrets(rendered)` non-empty → `SecretDetected`, nothing written; path under `approved/` without `extra["change_request_decision"]` → `ApprovedWriteRefused`; write to `<path>.tmp` then `os.replace`; upsert `memory_index`; fire `ON_CONTEXT_UPDATED`; write `CONTEXT_UPDATED` (payload: doc_id, type, version, sections changed).
3. `apply_updates`: for each `ContextUpdate`, load the doc by `doc_id` (create `skeleton_for` when missing — type inferred from id prefix FEAT/BUG/`project`), REPLACE or APPEND the section (unknown section name → `ConfigError`), merge `relevant_files` into front matter, then one `write` per touched doc.
4. `write_handover(doc)` writes to `.ai/handovers/<id>.md` and writes `HANDOVER_CREATED` (payload: handover id, work item, reason) in addition to `CONTEXT_UPDATED`; `read_handover` returns the raw document or `DocumentNotFound`.
5. `rebuild_index` scans `.ai/**/*.md` (excluding `reports/`), parses, upserts rows, deletes rows whose files vanished, returns count.
6. `write_report(kind, subject_id, markdown)` writes `.ai/reports/<kind>/<subject_id>.md` without front-matter validation or index entry (ADR-0003 D-6).
7. `root()` returns the absolute `.ai/` path; `read(doc_id)` resolves via `memory_index` then falls back to `doc_path_for`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the ARCHITECTURE §8.2 sample document, When parsed then rendered, Then round-trip equality (modulo key order) and unknown H2 preserved | `tests/memory/test_frontmatter.py::test_parse_render_round_trip_preserves_unknown_sections` |
| 2 | Given a file whose `id` ≠ stem, Then `ConfigError` | `tests/memory/test_frontmatter.py::test_parse_rejects_id_mismatch` |
| 3 | When `SECTION_ORDER[FEATURE]`, Then the 14 §37 headings in order; `skeleton_for` produces all of them empty | `tests/memory/test_sections.py::test_feature_section_order_and_skeleton` |
| 4 | For each secret pattern, Given a matching string, Then `find_secrets` names it; clean text → `[]` | `tests/memory/test_secrets.py::test_secret_patterns_detect_and_pass` |
| 5 | When `write` a new feature doc, Then file exists, `version == 1`, freshness stamped with head/branch/now, index row, `ON_CONTEXT_UPDATED` fired, `CONTEXT_UPDATED` written | `tests/memory/test_service_write.py::test_write_new_document_stamps_and_indexes` |
| 6 | When `write` again, Then `version == 2` and no `.tmp` left behind | `tests/memory/test_service_write.py::test_write_bumps_version_atomically` |
| 7 | Given content with `AKIA…`, When `write`, Then `SecretDetected` and file unchanged | `tests/memory/test_service_write.py::test_write_refuses_secrets` |
| 8 | Given an `approved/` doc without change decision, Then `ApprovedWriteRefused` | `tests/memory/test_service_write.py::test_write_refuses_unauthorised_approved_change` |
| 9 | Given an injected failure after tmp write, Then original file intact | `tests/memory/test_service_write.py::test_write_is_atomic_on_failure` |
| 10 | When `apply_updates([REPLACE "Architecture"], [APPEND "Implementation Notes"])` on a missing FEAT doc, Then skeleton created, sections set/appended, `relevant_files` merged, one write | `tests/memory/test_service_updates.py::test_apply_updates_creates_skeleton_and_edits_sections` |
| 11 | When an update names an unknown section, Then `ConfigError` and no write | `tests/memory/test_service_updates.py::test_apply_updates_rejects_unknown_section` |
| 12 | When `write_handover`, Then `.ai/handovers/HO-0001.md` and `HANDOVER_CREATED`; `read_handover` returns it; unknown → `DocumentNotFound` | `tests/memory/test_service_updates.py::test_write_and_read_handover` |
| 13 | Given 3 docs on disk and a stale index row, When `rebuild_index`, Then 3 rows, stale removed, returns 3 | `tests/memory/test_index.py::test_rebuild_index_syncs_rows` |
| 14 | When `write_report("task", "STORY-0001", md)`, Then file written, no index row | `tests/memory/test_index.py::test_write_report_bypasses_index` |
| 15 | When `walk memory index`, Then prints count and exit 0 | `tests/cli/test_cmd_memory.py::test_memory_index_cli` |

#### Evidence required
- Quality gate output.
- Demo: `walk memory index` → `indexed 1 documents`.

#### Notes
- ADR-0003 D-2/D-4/D-6; ARCHITECTURE §8.2 front matter; §6 secret scan.
- `NEW NAME:` modules `walk.memory.sections`, `walk.memory.secrets`, `walk.memory.paths`, `walk.memory.frontmatter`; errors `DocumentNotFound`, `SecretDetected`, `ApprovedWriteRefused`.
- Pitfall: YAML dump must use `sort_keys=True`, `allow_unicode=True`, block style, so renders are deterministic (ADR-0012 D-7 depends on it).
- Commit: `feat: add memory document core with atomic writes and index (E01-S16)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S17 — Constitutions and runtime policies: loaders, merge rules, MVP role defaults

**Status:** TODO
**Type:** feat
**Requirements:** §8, §9, §12, §13, §14, §15, §105, §127, §137 (Inv. 1)
**Depends on:** E01-S13, E01-S15
**Effort:** HIGH   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Role constitutions and runtime policies load from kernel defaults merged with project overrides under narrowing rules, for the four MVP roles.

#### Scope
- In: `agents.models` (Constitution, ModelPolicy, RuntimePolicy, AgentInstance), `ConstitutionLoader`, `PolicyLoader`, `DefaultAgentManager.load_constitution/load_runtime_policy/list_roles`, default constitutions and `policies.yaml`.
- Out: execution contract models and `instantiate` (E01-S18), full constitution bodies (E03-S06), provider-name lint (E02-S15), narrowing on `authority` widening approvals (E05-S07).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/__init__.py` | create | re-exports |
| `src/walk/agents/models.py` | create | `Constitution`, `ModelPolicy`, `RuntimePolicy`, `AgentInstance` |
| `src/walk/agents/protocols.py` | create | `AgentManager` |
| `src/walk/agents/errors.py` | create | `ConstitutionError` |
| `src/walk/agents/constitution_loader.py` | create | `ConstitutionLoader` |
| `src/walk/agents/policy_loader.py` | create | `PolicyLoader` |
| `src/walk/agents/service.py` | create | `DefaultAgentManager` |
| `src/walk/agents/defaults/orchestrator.md` | create | — |
| `src/walk/agents/defaults/lead_dev.md` | create | — |
| `src/walk/agents/defaults/senior_dev.md` | create | — |
| `src/walk/agents/defaults/qc.md` | create | — |
| `src/walk/agents/defaults/policies.yaml` | create | — |
| `src/walk/decisions/__init__.py` | create | re-exports |
| `src/walk/decisions/models.py` | create | `DecisionCategory`, `DecisionStatus`, `AutonomyLevel`, `Authority`, `EscalationRule`, `DecisionProposal`, `EscalationRequest`, `DecisionPosition`, `Decision`, `Escalation` |
| `tests/agents/__init__.py`, `tests/decisions/__init__.py` | create | — |
| `tests/agents/test_constitution_loader.py` | create | — |
| `tests/agents/test_policy_loader.py` | create | — |
| `tests/agents/test_defaults.py` | create | — |
| `tests/decisions/test_models.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §4.2 (`Constitution`, `ModelPolicy`, `RuntimePolicy`, `AgentInstance` — `EffortPolicy`/`BudgetPolicy` imported from `walk.effort.models`/`walk.budgets.models`), §4.8 decisions models (needed by `Constitution.authority`; services in E04-S05/E05). Protocol: INTERFACES.md §1.2 (`instantiate`, `render_instructions` are E01-S18). Deltas:
```python
class ConstitutionLoader:
    def __init__(self, defaults_dir: Path, project_roles_dir: Path | None) -> None: ...
    def load(
        self, role: AgentRole
    ) -> Constitution: ...  # ADR-0013 D-1..D-4; ConstitutionError on schema/merge violations
    def available_roles(self) -> list[AgentRole]: ...


class PolicyLoader:
    def __init__(self, defaults_path: Path, project_path: Path | None) -> None: ...
    def load(
        self, role: AgentRole
    ) -> RuntimePolicy: ...  # deep-merge: project scalars/lists replace defaults per key


class DefaultAgentManager:
    def __init__(
        self,
        constitutions: ConstitutionLoader,
        policies: PolicyLoader,
        permissions: PermissionManager,
    ) -> None: ...
```
`policies.yaml` schema: `roles: {<ROLE>: {version, model_policy: {preferred: [family…], fallback, restricted, required_capabilities, cross_model_review, allow_task_override}, effort_policy: {...}, budget_policy: {...}, default_skills, allowed_tools, execution_strategy, max_parallel_runs, checkpoint_every_tool_calls}}` with ADR-0011 D-3 defaults for every `AgentRole` except USER/KERNEL. Default constitutions: front matter exactly as ADR-0013 D-2 for the role (ids `ORCHESTRATOR`, `LEAD_DEV`, `SENIOR_DEV`, `QC`; `version: "1.0"`; `authority` per ADR-0006 D-6; `tool_permissions` per ADR-0006 D-6), body sections ADR-0013 D-3 with one-paragraph placeholders derived from §10.1/§10.6/§10.7/§10.8.

#### Behavior
1. `ConstitutionLoader.load` parses `<defaults>/<role>.md` via `walk.memory.frontmatter.parse_document`, validates `type: constitution`, `role == id`, and builds `Constitution` (front matter authoritative, body sections → `body_markdown` in D-3 order).
2. Project override `.ai/agents/roles/<role>.md` (when present): scalars/lists replace; `authority.decision_scope`, `authority.may_approve/may_reject/may_create_work`, `tool_permissions`, `forbidden_actions` may only be narrowed (subset / lower `max_autonomy_level`) — widening raises `ConstitutionError` naming the field; body sections with the same name replace, new sections append.
3. Any field value containing a provider/model name (`claude`, `codex`, `gpt`, `anthropic`, `openai`, case-insensitive) raises `ConstitutionError` (ADR-0013 D-5; the `--strict` doctor lint in E02-S15 reuses this check).
4. `PolicyLoader.load` resolves model families to `ModelId`s? No — policies keep family strings (`claude/opus`) as `preferred`; `ModelId` pattern accepts them; resolution to concrete ids happens in E01-S20.
5. Unknown role in either loader → `ConstitutionError`; `list_roles` returns roles having a default constitution.
6. Loaders cache per instance; `reload()` is not provided (process restart).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | For each of the four default files, When loaded, Then valid `Constitution` with `version == "1.0"` and role matching file | `tests/agents/test_defaults.py::test_default_constitutions_load` |
| 2 | Then `LEAD_DEV.authority.decision_scope == [TECH]`, QC may create `[BUG]`, SENIOR_DEV `max_autonomy_level == 0` | `tests/agents/test_defaults.py::test_default_authorities_match_adr` |
| 3 | When `policies.yaml` loads for every MVP role, Then preferred/fallback families equal ADR-0011 D-3 | `tests/agents/test_defaults.py::test_default_policies_match_adr_0011` |
| 4 | Given an override lowering `max_autonomy_level` and removing a permission, When loaded, Then merged values applied | `tests/agents/test_constitution_loader.py::test_override_may_narrow` |
| 5 | Given an override adding `DESIGN` to LEAD_DEV `decision_scope`, Then `ConstitutionError` naming `authority.decision_scope` | `tests/agents/test_constitution_loader.py::test_override_widening_rejected` |
| 6 | Given an override with a new body section, Then appended after defaults; same-name section replaced | `tests/agents/test_constitution_loader.py::test_override_body_sections_merge` |
| 7 | Given a constitution mentioning `claude`, Then `ConstitutionError` | `tests/agents/test_constitution_loader.py::test_provider_names_rejected` |
| 8 | Given a file with `type: feature`, Then `ConstitutionError` | `tests/agents/test_constitution_loader.py::test_wrong_doc_type_rejected` |
| 9 | Given project `policies.yaml` overriding `checkpoint_every_tool_calls: 5` for SENIOR_DEV, Then merged policy has 5 and other defaults intact | `tests/agents/test_policy_loader.py::test_policy_deep_merge` |
| 10 | When `load(AgentRole.UA_RELEASE)` with no default, Then `ConstitutionError`; `list_roles()` == 4 MVP roles | `tests/agents/test_policy_loader.py::test_unknown_role_and_list_roles` |
| 11 | When `AutonomyLevel` compared, Then `USER > PO > MULTI_AGENT > LOCAL` (IntEnum) | `tests/decisions/test_models.py::test_autonomy_levels_ordered` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0013 D-1–D-5, ADR-0011 D-3, ADR-0006 D-6. Decision models are created here because `Constitution` embeds `Authority`/`EscalationRule`; the decisions service arrives in E04-S05.
- `NEW NAME:` `ConstitutionLoader` (in ARCHITECTURE key classes), `PolicyLoader`, `ConstitutionError`.
- Commit: `feat: add constitution and runtime policy loading with role defaults (E01-S17)`.

#### Evidence (filled by implementer)
_pending_

### E01-S18 — Agent execution contract: `AgentInput/AgentOutput/Handover`, templates, `instantiate`

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §9, §22, §29, §40 (section order), §126, §128, §137 (Inv. 1, 2)
**Depends on:** E01-S14, E01-S16, E01-S17, E01-S24
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The §126 execution contract exists as pydantic models, a `Handover` converts losslessly to and from a `.ai/handovers/` document, the nine purpose templates render deterministic kernel-owned prompts, and `AgentManager.instantiate` assembles a complete `AgentInstance` with validated tools and permissions.

#### Scope
- In: contract models (`AgentInput`, `AgentOutput`, `Handover`, `Finding`, `FileChange`, `NextAction`, `ExpectedOutput`, `ObservationDraft`, `ToolCallSummary`, relocated `AgentOutputStatus`), `walk.agents.handover.to_document/from_document`, `walk.agents.rendering`, nine `templates/<purpose>.md.j2` skeletons, `DefaultAgentManager.instantiate/render_instructions`.
- Out: adapter boundary and `RunSession` (E01-S19), rich template bodies (E03-S06, E04-S14), skill validation against a real `SkillRegistry` (E02-S05 wires it; here skills are resolved by name only).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/agents/models.py` | modify | `AgentOutputStatus`, `ToolCallSummary`, `Finding`, `FileChange`, `NextAction`, `Handover`, `ObservationDraft`, `ExpectedOutput`, `AgentInput`, `AgentOutput` |
| `src/walk/agents/handover.py` | create | `to_document`, `from_document`, `HANDOVER_SECTION_FIELDS` |
| `src/walk/agents/rendering.py` | create | `TEMPLATE_PURPOSES`, `TemplateRenderer`, `render_constitution`, `render_input_sections`, `INPUT_SECTION_ORDER` |
| `src/walk/agents/templates/__init__.py` | create | — |
| `src/walk/agents/templates/IMPLEMENT.md.j2` | create | — |
| `src/walk/agents/templates/DESIGN.md.j2` | create | — |
| `src/walk/agents/templates/REVIEW.md.j2` | create | — |
| `src/walk/agents/templates/QC.md.j2` | create | — |
| `src/walk/agents/templates/TRIAGE.md.j2` | create | — |
| `src/walk/agents/templates/DEBATE.md.j2` | create | — |
| `src/walk/agents/templates/PLAN.md.j2` | create | — |
| `src/walk/agents/templates/ANALYSIS.md.j2` | create | — |
| `src/walk/agents/templates/RETRO.md.j2` | create | — |
| `src/walk/agents/service.py` | modify | `DefaultAgentManager.instantiate`, `render_instructions` |
| `src/walk/agents/__init__.py` | modify | re-exports |
| `tests/agents/test_contract_models.py` | create | — |
| `tests/agents/test_handover_document.py` | create | — |
| `tests/agents/test_rendering.py` | create | — |
| `tests/agents/test_templates.py` | create | — |
| `tests/agents/test_instantiate.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §4.2 (`ToolCallSummary` … `AgentOutput`) verbatim; `AgentOutputStatus` = DOMAIN-MODEL §3 definition, **relocated** from `walk.runtime.models` to `walk.agents.models` (see Notes). Protocol: INTERFACES.md §1.2 `instantiate`, `render_instructions`. Deltas:
```python
HANDOVER_SECTION_FIELDS: tuple[
    tuple[str, str], ...
] = (  # §22 H2 heading → Handover field, in SECTION_ORDER[HANDOVER] order
    ("Task", "task_summary"),
    ("Current State", "current_state"),
    ("Completed Work", "completed_work"),
    ("Modified Files", "modified_files"),
    ("Findings", "findings"),
    ("Hypotheses", "hypotheses"),
    ("Decisions", "decisions"),
    ("Risks", "risks"),
    ("Remaining Work", "remaining_work"),
    ("Next Action", "next_action"),
)


def to_document(
    handover: Handover, *, actor: Actor, now: datetime
) -> MemoryDocument: ...  # type HANDOVER, id = handover.id; scalar fields (role, from_run_id, from_model_id, to_run_id, reason, worktree_head, branch, work_item_id) in front matter `extra`; list fields as "- " bullets; findings as "- **summary** — detail" with evidence ids; proposed_decisions as JSON block under "Decisions"
def from_document(
    doc: MemoryDocument,
) -> Handover: ...  # inverse; ConfigError when a required section/front-matter key is missing


TEMPLATE_PURPOSES: tuple[str, ...] = (
    "IMPLEMENT",
    "DESIGN",
    "REVIEW",
    "QC",
    "TRIAGE",
    "DEBATE",
    "PLAN",
    "ANALYSIS",
    "RETRO",
)
INPUT_SECTION_ORDER: tuple[str, ...] = (
    "Agent Role",
    "Constitution",
    "Authority",
    "Task",
    "Workflow State",
    "Relevant Context",
    "Approved Artifacts",
    "Relevant Decisions",
    "Available Skills",
    "Allowed Tools",
    "Permissions",
    "Budget",
    "Effort",
    "Required Evidence",
    "Expected Output",
    "Handover",
)  # §126 order; "Handover" only when present


class TemplateRenderer:
    def __init__(
        self, templates_dir: Path, project_templates_dir: Path | None = None
    ) -> None: ...  # jinja2 Environment(autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True)
    def render(
        self, purpose: str, **context: object
    ) -> str: ...  # ConfigError on unknown purpose or undefined variable
    def version_of(
        self, purpose: str
    ) -> str: ...  # first line of the template: `{# version: 1.0 #}`


def render_constitution(
    constitution: Constitution, project_constitution_markdown: str | None
) -> str: ...  # ADR-0013 D-3 section order, front matter fields rendered as bullet lists, then body_markdown, then project constitution
def render_input_sections(
    agent_input: AgentInput,
) -> str: ...  # one `## <section>` per INPUT_SECTION_ORDER entry; models serialised as fenced ```json (model_dump(mode="json"), sort_keys) except ContextBundle items which are rendered as `### <kind> <id>` + content


class DefaultAgentManager:
    def __init__(
        self,
        constitutions: ConstitutionLoader,
        policies: PolicyLoader,
        permissions: PermissionManager,
        tools: ToolRegistry,
        renderer: TemplateRenderer,
        *,
        skills: SkillRegistry | None = None,
    ) -> None: ...  # constructor extended from E01-S17
    async def instantiate(
        self,
        role: AgentRole,
        item: WorkItem,
        model_id: ModelId,
        effort: Effort,
        budget_ids: list[str],
        available_env_keys: set[str],
    ) -> AgentInstance: ...
    def render_instructions(self, agent: AgentInstance, item: WorkItem, purpose: str) -> str: ...
```
Template skeleton (every purpose, identical structure, differing only in the purpose paragraph): `{# version: 1.0 #}`, `# Task: {{ purpose }} {{ item.id }} — {{ item.title }}`, sections `## How to work` (§40 order: read context → decisions → approved artifacts → workflow state → code graph → required source → execute), `## Deliverables` (from `expected_output.deliverables`), `## Output contract` (write `.walk/output.json` matching `AgentOutput`, required `status`, `no_context_change_reason` rule, `handover` required for PARTIAL), `## Handover` (rendered only when `handover` is given: "continue from Next Action").

#### Behavior
1. `AgentOutput` validation (pydantic `model_validator`): `status == PARTIAL` requires `handover`; `status in {BLOCKED, NEEDS_INPUT}` requires non-empty `escalations`; empty `context_updates` with `status != FAILED` requires `no_context_change_reason`. Violations raise `pydantic.ValidationError` (callers convert to `OutputInvalid`).
2. `to_document` then `from_document` is lossless for every `Handover` field; the document's `related.work_items == [handover.work_item_id]`, `freshness` left for `MemoryManager.write` to stamp.
3. `from_document` rejects a document whose `type != HANDOVER` or whose `extra.reason` is not one of the §22 reasons (`ConfigError` naming the key).
4. `render_constitution` output is byte-stable for equal inputs and never contains a provider name (inherits the E01-S17 lint: a `Constitution` cannot carry one).
5. `render_input_sections` emits sections strictly in `INPUT_SECTION_ORDER`; `Relevant Context` preserves `ContextBundle.items` order and marks items with `requires_verification` as `> VERIFY AGAINST SOURCE BEFORE RELYING ON THIS`.
6. `instantiate`: loads constitution and policy; `permissions = PermissionManager.rules_for(role, extra=constitution.tool_permissions)`; `tools = ToolRegistry.for_role(policy.allowed_tools, available_env_keys, required=[])` names; `skills = policy.default_skills ∪ item.contract.required_skills` (contract present) — when a `SkillRegistry` is injected, `for_role(role, required)` validates them (`ConfigError` on missing); returns `AgentInstance(role, constitution, runtime_policy, skills, tools, permissions, model_id, effort, budget_ids)`.
7. `instantiate` raises `ConfigError` when a required tool (`policy.allowed_tools` entries marked required by the contract's `constraints` of the form `tool:<name>`) is unavailable, propagating `ToolRegistry.for_role`'s message.
8. `render_instructions(agent, item, purpose)` renders `templates/<purpose>.md.j2` with `item`, `purpose`, `agent`, `expected_output` (built from the purpose: IMPLEMENT → `[COMPLETED, PARTIAL, BLOCKED, FAILED]`, REVIEW/QC → `[APPROVED, REJECTED, NEEDS_INPUT]`, TRIAGE/PLAN/DESIGN/ANALYSIS/RETRO/DEBATE → `[COMPLETED, NEEDS_INPUT, FAILED]`; `required_evidence = item.contract.required_evidence` when present) and `handover=None`; the executor (E01-S27) re-renders with the handover when one exists. Unknown purpose → `ConfigError`.
9. A project template at `.ai/agents/templates/<purpose>.md.j2` shadows the kernel template (same loader rule as skills); its `version_of` is reported in `LedgerEvent.behavior_versions["prompt:<purpose>"]` by the executor.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `AgentOutput(status=PARTIAL)` without `handover` is validated, Then `ValidationError` naming `handover` | `tests/agents/test_contract_models.py::test_partial_requires_handover` |
| 2 | When `status=BLOCKED` with empty `escalations`, Then `ValidationError`; with one escalation → valid | `tests/agents/test_contract_models.py::test_blocked_requires_escalation` |
| 3 | When `context_updates == []`, `status=COMPLETED`, no reason, Then `ValidationError`; with `no_context_change_reason` → valid | `tests/agents/test_contract_models.py::test_empty_context_updates_requires_reason` |
| 4 | When `AgentInput` is built from fixtures, Then every §126 input field is present and `model_dump_json()` round-trips | `tests/agents/test_contract_models.py::test_agent_input_round_trip` |
| 5 | Given a full `Handover`, When `to_document` then `from_document`, Then equal; sections appear in `SECTION_ORDER[HANDOVER]` | `tests/agents/test_handover_document.py::test_handover_document_round_trip` |
| 6 | Given a document with `type: feature`, Then `ConfigError`; with `reason: WHATEVER`, Then `ConfigError` naming `reason` | `tests/agents/test_handover_document.py::test_from_document_rejects_wrong_type_or_reason` |
| 7 | Given the LEAD_DEV default constitution, When rendered twice, Then identical output with ADR-0013 D-3 headings in order | `tests/agents/test_rendering.py::test_render_constitution_is_deterministic_and_ordered` |
| 8 | Given an `AgentInput` with a `requires_verification` context item and a handover, When rendered, Then sections in `INPUT_SECTION_ORDER`, VERIFY marker present, `## Handover` last | `tests/agents/test_rendering.py::test_render_input_sections_order_and_markers` |
| 9 | For each of the nine purposes, When `TemplateRenderer.render`, Then non-empty output containing `.walk/output.json` and `version_of == "1.0"` | `tests/agents/test_templates.py::test_all_purpose_templates_render` |
| 10 | Given a project template dir shadowing `IMPLEMENT.md.j2` with version `1.1`, Then the project template wins and `version_of == "1.1"` | `tests/agents/test_templates.py::test_project_template_shadows_kernel` |
| 11 | When `render("NOPE")` or a template references an undefined variable, Then `ConfigError` | `tests/agents/test_templates.py::test_render_rejects_unknown_purpose_or_variable` |
| 12 | Given SENIOR_DEV, a story and `available_env_keys={"git"}`, When `instantiate`, Then `AgentInstance` with merged permissions, tool names ⊆ available tools, `skills` = defaults ∪ contract skills, `model_id/effort/budget_ids` as passed | `tests/agents/test_instantiate.py::test_instantiate_assembles_instance` |
| 13 | Given a constitution rule widening a kernel deny, When `instantiate`, Then the rule is absent from `AgentInstance.permissions` | `tests/agents/test_instantiate.py::test_instantiate_permissions_only_narrow` |
| 14 | Given a contract constraint `tool:unity.compile` and no unity env, Then `ConfigError` naming the tool | `tests/agents/test_instantiate.py::test_instantiate_missing_required_tool_raises` |
| 15 | When `render_instructions(agent, story, "IMPLEMENT")`, Then output contains the story id and `COMPLETED`/`PARTIAL` status options; `"REVIEW"` lists `APPROVED`/`REJECTED` | `tests/agents/test_instantiate.py::test_render_instructions_per_purpose` |

#### Evidence required
- Quality gate output.
- Demo: `python -c "from walk.agents.rendering import TemplateRenderer; ..."` is not a CLI; record the rendered `IMPLEMENT` prompt for `STORY-0001` (first 20 lines) from the test run instead.

#### Notes
- ADR-0004 D-3/D-4/D-5; ADR-0013 D-3; ADR-0003 D-5 (handover as document); WBS §3.9 (templates and purposes).
- `RELOCATE: AgentOutputStatus → walk.agents.models`. DOMAIN-MODEL §3 places it in `walk.runtime.models`, but `AgentOutput.status` (agents) needs it and `agents` may not import `runtime` (ARCHITECTURE §2.2). `walk.runtime.models` re-exports it for readers.
- `NEW NAME:` modules `walk.agents.handover`, `walk.agents.rendering`; symbols `HANDOVER_SECTION_FIELDS`, `TEMPLATE_PURPOSES`, `INPUT_SECTION_ORDER`, `TemplateRenderer`, `render_constitution`, `render_input_sections`; template version comment `{# version: x.y #}`; contract constraint convention `tool:<name>` for required tools (§29 has no field for required tools on `StoryContract`).
- Pitfall: `AgentInput` embeds `Constitution`, `ContextBundle`, `Debate`; keep `model_config` default (`WalkModel`) so `extra` fields from older JSON are rejected, which is what makes the repair turn (E01-S27) meaningful.
- Commit subject: `feat: add agent execution contract, handover documents and prompt templates (E01-S18)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S19 — `ModelAdapter` protocol, `RunSession`, `AgentEvent`, `FakeModelAdapter`

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §16 (descriptor data), §17, §21 (triggers), §22, §126, §128, §137 (Inv. 1, 2), §138 (Model Lock-In)
**Depends on:** E01-S18
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The normalised adapter boundary (protocol, event stream, session configuration, output parsing) exists, and a scripted `FakeModelAdapter` that honours every rule of the boundary is available to every later test and both epic gates.

#### Scope
- In: `model_router.models` (all DOMAIN-MODEL §4.10 models and the §3 `Capability`-independent enums), `ModelAdapter` and `ModelRouter` protocols, `RunSession`/`ProviderEffortConfig`, `NotResumable`/`BlockedProvider`, shared output parsing, `tests/fakes/fake_model_adapter.py`.
- Out: `DefaultModelRouter`, `models.yaml`, costing (E01-S20); real adapters (E01-S21/S22); `FakeSkillProjector` (E02-S06).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/__init__.py` | create | re-exports |
| `src/walk/model_router/models.py` | create | `FallbackTrigger`, `ModelDescriptor`, `CapabilityRegistry`, `TaskProfile`, `RoutingDecision`, `ProviderSessionRef`, `UsageReport`, `AdapterHealth`, `AgentEventKind`, `AgentEvent`, `RunSession`, `ProviderEffortConfig` |
| `src/walk/model_router/protocols.py` | create | `ModelAdapter`, `ModelRouter` (protocol only; service in E01-S20) |
| `src/walk/model_router/errors.py` | create | `NotResumable`, `BlockedProvider` |
| `src/walk/model_router/output.py` | create | `parse_agent_output`, `read_output_file`, `OUTPUT_RELATIVE_PATH` |
| `src/walk/model_router/adapters/__init__.py` | create | — |
| `tests/fakes/fake_model_adapter.py` | create | `FakeScript`, `FakeModelAdapter`, `fake_descriptor` |
| `tests/model_router/__init__.py` | create | — |
| `tests/model_router/test_models.py` | create | — |
| `tests/model_router/test_output.py` | create | — |
| `tests/model_router/test_fake_adapter.py` | create | — |
| `tests/conftest.py` | modify | fixtures `fake_codex_adapter`, `fake_claude_adapter`, `run_session` |

#### Interface contract
Models: DOMAIN-MODEL §3 `FallbackTrigger`, §4.10 verbatim (`Capability` is imported from `walk.common.enums`, WBS §3.2); INTERFACES.md §2.1 `RunSession`, `ProviderEffortConfig`, `ModelAdapter`; INTERFACES.md §1.4 `ModelRouter`. Deltas:
```python
class NotResumable(PermanentError):
    """Adapter cannot continue the provider-side session (unsupported or expired)."""


class BlockedProvider(TransientError):
    """No routing candidate survived; detail = list[(model_id, reason)]."""


OUTPUT_RELATIVE_PATH = ".walk/output.json"


def parse_agent_output(
    raw: str,
) -> AgentOutput: ...  # json → AgentOutput; raises OutputInvalid whose `detail` is the pydantic error list rendered as "<loc>: <msg>" lines (used verbatim in the repair turn)
def read_output_file(path: Path) -> str | None: ...  # None when absent


# tests/fakes/fake_model_adapter.py
class FakeScript(WalkModel):
    tool_calls: int = 3
    tool_name: ToolName = "edit"
    output: AgentOutput
    partial_output: AgentOutput | None = (
        None  # emitted as PARTIAL_OUTPUT before the last tool call when set
    )
    checkpoint_hint_at: list[int] = []  # tool-call indexes after which CHECKPOINT_HINT is emitted
    fail_after_tool_calls: int | None = (
        None  # emit ERROR(trigger) after this many tool calls and stop
    )
    fail_trigger: FallbackTrigger | None = None
    fail_error: str = "scripted failure"
    invalid_output_times: int = (
        0  # first N FINAL_OUTPUTs carry output=None + error (forces repair turns)
    )
    usage_per_tool_call: UsageReport = UsageReport(
        input_tokens=1000, output_tokens=200, cost_usd=0.0, turns=1, tool_calls=1, duration_s=1.0
    )
    resumable: bool = True


def fake_descriptor(
    model_id: ModelId, provider: str, **overrides: object
) -> (
    ModelDescriptor
): ...  # all capabilities 4, 200k window, 16k output, all effort levels, prices 1.0/5.0 per MTok


class FakeModelAdapter:
    provider: str

    def __init__(
        self,
        provider: str,
        descriptors: list[ModelDescriptor],
        script: FakeScript | Callable[[AgentInput], FakeScript],
        clock: Clock,
        *,
        healthy: bool = True,
    ) -> None: ...

    runs: dict[RunId, list[AgentEvent]]  # every event emitted, per run (assertion helper)
    authorizations: list[tuple[RunId, ToolCallRequest, PermissionDecision]]

    def set_healthy(self, ok: bool) -> None: ...

    # ModelAdapter methods per INTERFACES §2.1
```

#### Behavior
1. `AgentEvent` is frozen; `AgentEventKind` has exactly the ten ADR-0004 D-2 values; `ModelDescriptor.capabilities` values are validated `0..5`.
2. `parse_agent_output` accepts a JSON object (optionally wrapped in a single ```json fence) and rejects everything else with `OutputInvalid`; the error detail lists every failing field.
3. `FakeModelAdapter.run(input, session)`: emits `STARTED(session=ProviderSessionRef(provider, session_id=f"fake-{run_id}", resumable=script.resumable))`; then for `i in 1..tool_calls`: builds `ToolCallRequest(run_id, input.role, tool=script.tool_name, kind=PROVIDER_NATIVE, arguments={"path": f"src/Fake{i}.cs"}, paths=[...], worktree_path=session.worktree_path)`, emits `TOOL_CALL_REQUESTED`, awaits `session.permission_authorizer(request)`; on `ALLOW` writes `<worktree>/src/Fake{i}.cs` (one line, deterministic content) and emits `TOOL_CALL_RESULT(tool_result={"ok": true})`; on `DENY`/`REQUIRE_APPROVAL`-denied emits `TOOL_CALL_RESULT(tool_result={"ok": false, "reason": decision.reason})` and continues; emits `USAGE(script.usage_per_tool_call)` after every tool call; emits `CHECKPOINT_HINT` after indexes in `checkpoint_hint_at`.
4. When `fail_after_tool_calls == i`: emits `ERROR(error=fail_error, trigger=fail_trigger)` and returns (no `FINAL_OUTPUT`, no `ENDED`).
5. At the end: writes `script.output.model_dump_json()` to `session.output_path` (creating `.walk/`), emits `FINAL_OUTPUT(output=parsed)` — or, for the first `invalid_output_times` runs/resumes, `FINAL_OUTPUT(output=None, error="scripted invalid output")` and writes `{"status": "BOGUS"}` instead — then `USAGE` (cumulative) and `ENDED`. `partial_output` is emitted as `PARTIAL_OUTPUT` before the last tool call.
6. `resume(session_ref, instruction, session)`: `NotResumable` when `session_ref.resumable` is false or the ref is unknown; otherwise continues the same script from the recorded tool-call index (so a run interrupted at 3/12 performs the remaining 9 tool calls) and applies rule 5; `instruction` is recorded in `runs`.
7. `cancel(run_id)` sets a flag checked between events; the generator then emits `ENDED` and stops. `usage(run_id)` returns the cumulative `UsageReport`. `health()` returns `AdapterHealth(ok=healthy, provider, detail, checked_at=clock.now())`. `map_effort` returns `ProviderEffortConfig(model_id, params={"fake_effort": effort.value})` and degrades to the nearest lower level when the descriptor lacks it (`params["degraded_from"]`). `skill_projector()` raises `ConfigError("skill projection available from E02-S06")`. `parse_output` delegates to `parse_agent_output`.
8. The fake never emits `TEXT` containing the word `thinking` and never reads `AgentInput.constitution` (Invariant 1 sanity: role-agnostic).
9. Fixtures: `fake_codex_adapter` (`provider="fake-codex"`, descriptor `fake-codex/sim`) and `fake_claude_adapter` (`provider="fake-claude"`, descriptor `fake-claude/sim`) with a default 3-tool-call COMPLETED script; `run_session(tmp_repo)` builds a `RunSession` with an always-ALLOW authorizer.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `AgentEventKind` and `FallbackTrigger` members are enumerated, Then they equal ADR-0004 D-2 and DOMAIN-MODEL §3 lists | `tests/model_router/test_models.py::test_event_kinds_and_triggers_match_architecture` |
| 2 | When a `ModelDescriptor` has capability 6, Then `ValidationError`; `AgentEvent` is frozen | `tests/model_router/test_models.py::test_descriptor_validation_and_event_frozen` |
| 3 | When `parse_agent_output` receives a fenced valid JSON, Then `AgentOutput`; with `{"status":"BOGUS"}` Then `OutputInvalid` listing `status` | `tests/model_router/test_output.py::test_parse_agent_output_accepts_fence_and_lists_errors` |
| 4 | When `read_output_file` on a missing path, Then `None` | `tests/model_router/test_output.py::test_read_output_file_missing_returns_none` |
| 5 | Given a 3-call script, When `run` is consumed, Then events are `STARTED, (TOOL_CALL_REQUESTED, TOOL_CALL_RESULT, USAGE)×3, FINAL_OUTPUT, USAGE, ENDED`, three files exist in the worktree and `output.json` parses | `tests/model_router/test_fake_adapter.py::test_run_emits_normalised_stream_and_writes_output` |
| 6 | Given an authorizer returning DENY, Then no file written and `TOOL_CALL_RESULT.tool_result["ok"] is False` | `tests/model_router/test_fake_adapter.py::test_run_respects_denied_authorization` |
| 7 | Given `fail_after_tool_calls=3, fail_trigger=PROVIDER_OUTAGE` on a 12-call script, Then stream ends with `ERROR(trigger=PROVIDER_OUTAGE)` after 3 results | `tests/model_router/test_fake_adapter.py::test_run_scripted_failure_emits_error_and_stops` |
| 8 | Given that interrupted run, When `resume(ref, "continue")`, Then 9 more tool calls then `FINAL_OUTPUT` | `tests/model_router/test_fake_adapter.py::test_resume_continues_from_recorded_index` |
| 9 | Given `resumable=False`, When `resume`, Then `NotResumable` | `tests/model_router/test_fake_adapter.py::test_resume_not_resumable_raises` |
| 10 | Given `invalid_output_times=1`, Then first `FINAL_OUTPUT.output is None` with `error`, and after `resume` the output is valid | `tests/model_router/test_fake_adapter.py::test_invalid_output_then_repair` |
| 11 | When `cancel` is called mid-stream, Then the stream ends with `ENDED` without `FINAL_OUTPUT` | `tests/model_router/test_fake_adapter.py::test_cancel_stops_stream` |
| 12 | When `map_effort(VERY_HIGH)` on a descriptor supporting up to HIGH, Then `params["degraded_from"] == "VERY_HIGH"` and `fake_effort == "HIGH"` | `tests/model_router/test_fake_adapter.py::test_map_effort_degrades` |
| 13 | When `set_healthy(False)`, Then `health().ok is False` | `tests/model_router/test_fake_adapter.py::test_health_toggle` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0004 D-1/D-2/D-3/D-6; WBS §3.6 (fakes implement the real protocol; descriptor ids `fake-codex/sim`, `fake-claude/sim`).
- `NEW NAME:` `walk.model_router.output` module with `parse_agent_output`, `read_output_file`, `OUTPUT_RELATIVE_PATH`; fake helpers `FakeScript`, `fake_descriptor`; `NotResumable`/`BlockedProvider` are already registered in WBS §6.
- Boundary rule fixed here and reused by E01-S21/S22/S27: an adapter whose final output is missing or invalid emits `FINAL_OUTPUT(output=None, error=<detail>)`; the executor owns the repair turn.
- Pitfall: `run()` is an async generator; `cancel()` must not raise inside the consumer — use a flag, not `Task.cancel()`.
- Commit subject: `feat: add model adapter boundary and scripted fake adapter (E01-S19)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S20 — Model router: `CapabilityRegistry`, `models.yaml`, `select`, `classify_error`, costing

**Status:** TODO
**Type:** feat
**Requirements:** §14, §15, §16, §17, §21 (select path), §23, §84, §137 (Inv. 1), §138 (Model Lock-In)
**Depends on:** E01-S19, E01-S12
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Model families resolve to concrete descriptors from configuration, `ModelRouter.select` implements INTERFACES §5.3 steps 1–4 deterministically, adapter errors map to §21 triggers, and token usage converts to `CostRecord`s using descriptor prices.

#### Scope
- In: `models.yaml` defaults + project override loader, family resolution (ADR-0011 D-1/D-2/D-4), `DefaultModelRouter.registry/adapter_for/select/classify_error/health_all`, `costing.usage_to_cost_record`.
- Out: `fallback` steps 5–10 (E01-S28 — raises `ConfigError("implemented in E01-S28")` here), `walk doctor` validation of `models.yaml` (E02-S15), `walk policy set-model` (E02-S13).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/defaults/__init__.py` | create | — |
| `src/walk/model_router/defaults/models.yaml` | create | — |
| `src/walk/model_router/registry.py` | create | `ModelsConfig`, `FamilyLevel`, `load_models_config`, `build_registry`, `resolve_family`, `FAMILY_PATTERN` |
| `src/walk/model_router/costing.py` | create | `usage_to_cost_record`, `estimate_usage_cost_usd` |
| `src/walk/model_router/service.py` | create | `DefaultModelRouter`, `ERROR_TRIGGER_MAP` |
| `src/walk/model_router/__init__.py` | modify | re-exports |
| `tests/model_router/test_registry.py` | create | — |
| `tests/model_router/test_defaults.py` | create | — |
| `tests/model_router/test_select.py` | create | — |
| `tests/model_router/test_classify_error.py` | create | — |
| `tests/model_router/test_costing.py` | create | — |

#### Interface contract
Protocol: INTERFACES.md §1.4 `ModelRouter`. Deltas:
```python
FAMILY_PATTERN = r"^[a-z0-9-]+/[a-z0-9-]+$"  # "claude/opus", "codex/default", "fake-codex/sim"


class FamilyLevel(FrozenModel):
    model: ModelId
    params: (
        JsonDict  # provider params for this effort (effort, max_turns, model_reasoning_effort …)
    )
    execution_time_s: int  # ADR-0011 D-2 wall-clock bound
    escalate_to: str | None = (
        None  # family name when this level is served by another family (sonnet VERY_HIGH → claude/opus)
    )


class ModelsConfig(WalkModel):
    version: str
    models: dict[ModelId, ModelDescriptor]
    families: dict[str, dict[Effort, FamilyLevel]]


def load_models_config(
    default_path: Path, project_path: Path | None
) -> ModelsConfig: ...  # deep-merge: project `models` entries replace by id; project `families` replace by family name; ConfigError on schema violation or a family level naming an unknown model
def build_registry(config: ModelsConfig) -> CapabilityRegistry: ...
def resolve_family(
    config: ModelsConfig, family_or_model: str, effort: Effort
) -> tuple[
    ModelId, FamilyLevel
]: ...  # concrete ModelId passes through (level synthesised from descriptor); unknown family → ConfigError; follows `escalate_to` once
def usage_to_cost_record(
    usage: UsageReport,
    descriptor: ModelDescriptor,
    subject: BudgetSubject,
    *,
    record_id: str,
    at: datetime,
) -> CostRecord: ...  # category LLM, dimension TOKENS, quantity = input+output+cache_read, unit "tokens", cost_usd from prices, token fields copied
def estimate_usage_cost_usd(usage: UsageReport, descriptor: ModelDescriptor) -> float: ...


ERROR_TRIGGER_MAP: dict[type[BaseException], FallbackTrigger] = {
    ProviderUnavailable: PROVIDER_OUTAGE,
    RateLimited: RATE_LIMIT,
    QuotaExhausted: QUOTA_EXHAUSTED,
    Timeout: TIMEOUT,
    ToolCrashed: TOOL_INCOMPATIBILITY,
    BudgetExhausted: BUDGET_RESTRICTION,
    OutputInvalid: REPEATED_OUTPUT_INVALID,
}


class DefaultModelRouter:
    def __init__(
        self, config: ModelsConfig, adapters: dict[str, ModelAdapter], clock: Clock
    ) -> None: ...  # adapters keyed by provider; every enabled descriptor's provider must have an adapter → ConfigError otherwise
```
`defaults/models.yaml` content is ADR-0011 D-2 verbatim: models `claude-opus-5-5`, `claude-sonnet-5-5` (provider `claude`), `gpt-5-codex` (provider `codex`) with `supports_effort_levels` = all four, `supports_native_resume: true`, capability scores (opus: all 5 except VISUAL_REASONING 4; sonnet: CODING 4, ARCHITECTURE 4, others 4, VISUAL_REASONING 3; codex: CODING 5, REPOSITORY_NAVIGATION 5, TOOL_USE 5, ARCHITECTURE 3, DESIGN_REASONING 2, VISUAL_REASONING 1, REVIEW 4, PLANNING 3, LONG_CONTEXT_REASONING 4), context windows 200000/200000/272000, max output 32000/32000/32000, prices (per MTok USD) 15/75, 3/15, 1.25/10 with cache read 1.5/0.3/0.125; families `claude/opus`, `claude/sonnet` (VERY_HIGH `escalate_to: claude/opus`), `codex/default` with the D-2 params and `execution_time_s` 600/1500/2700/5400.

#### Behavior
1. `select(role, policy, profile, effort, exclude, task_override)` implements INTERFACES §5.3 steps 1–4 literally: candidates `[task_override]` (only when `policy.allow_task_override`) + `preferred` + `fallback`, de-duplicated preserving order; each candidate resolved via `resolve_family(…, effort)` to a concrete `ModelId`; removed when in `policy.restricted` (by family or id), `descriptor.enabled is False` (rejected `"MODEL_DISABLED"`), or in `exclude`.
2. Per candidate, in this order, with `rejected` accumulating `(model_id, reason)`: capability (`any(d.capabilities[c] < 3 for c in profile.required_capabilities ∪ policy.required_capabilities)` → `"capability:<c>"`), context (`profile.estimated_context_tokens > 0.6 * d.context_window_tokens` → `"context"`), effort (`effort ∉ d.supports_effort_levels` and `adapter.map_effort` cannot degrade → `"effort"`), cross-model deferral (`policy.cross_model_review and profile.implementer_model_id == m` and another candidate remains → moved to the end once), health (`not (await adapter.health()).ok` → `"health"`).
3. The first survivor yields `RoutingDecision(model_id, provider, effort, reason="preferred"|"fallback"|"override", rejected, is_fallback = m ∉ resolved(preferred))`; none → `BlockedProvider(rejected)`.
4. `select` performs no ledger writes (`MODEL_SELECTED` is written by the executor); it is deterministic given adapter health.
5. `adapter_for(model_id)` returns the adapter of the descriptor's provider; unknown id → `ConfigError`. `registry()` returns the built `CapabilityRegistry`. `health_all()` queries every adapter once and maps the result onto every model it serves.
6. `classify_error(exc, adapter)`: if the adapter exposes `classify_error(exc)` (duck-typed, optional) and it returns a trigger, use it; else walk `ERROR_TRIGGER_MAP` by `isinstance` (most-derived first); `BudgetExhausted` maps only when `exc.hard_action == FALLBACK_MODEL`; everything else → `None`.
7. `usage_to_cost_record`: `cost_usd = (input × in_price + output × out_price + cache_read × cache_price) / 1_000_000`, rounded to 6 decimals; `provider = descriptor.provider`; `run_id/work_item_id/phase_id/role/project_key` copied from `subject`.
8. `load_models_config` rejects a project override that sets a price `< 0`, a capability outside `0..5`, or a family level whose `model` is not in `models` (`ConfigError` naming family/level).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `defaults/models.yaml` loads, Then three models, three families, every family has all four effort levels and `claude/sonnet[VERY_HIGH].escalate_to == "claude/opus"` | `tests/model_router/test_defaults.py::test_default_models_yaml_matches_adr_0011` |
| 2 | Given a project override changing `gpt-5-codex` prices and adding family `fake-codex/sim`, When loaded, Then merged config keeps other defaults | `tests/model_router/test_registry.py::test_project_override_merges_by_id_and_family` |
| 3 | Given a family level naming an unknown model, Then `ConfigError` naming the family | `tests/model_router/test_registry.py::test_unknown_family_model_rejected` |
| 4 | When `resolve_family("claude/sonnet", VERY_HIGH)`, Then `claude-opus-5-5` with the opus VERY_HIGH params; `resolve_family("claude-opus-5-5", LOW)` passes through | `tests/model_router/test_registry.py::test_resolve_family_escalation_and_passthrough` |
| 5 | Given policy preferred `[fake-codex/sim]`, fallback `[fake-claude/sim]`, all healthy, Then decision is `fake-codex/sim`, `is_fallback False`, `rejected == []` | `tests/model_router/test_select.py::test_select_prefers_first_healthy_candidate` |
| 6 | Given the preferred adapter unhealthy, Then fallback chosen, `is_fallback True`, `rejected == [(fake-codex/sim, "health")]` | `tests/model_router/test_select.py::test_select_rejects_unhealthy_and_marks_fallback` |
| 7 | Given `profile.required_capabilities=[VISUAL_REASONING]` and the preferred descriptor scoring 2, Then rejected `"capability:VISUAL_REASONING"` | `tests/model_router/test_select.py::test_select_rejects_on_capability` |
| 8 | Given `estimated_context_tokens` above 60 % of the window, Then rejected `"context"` | `tests/model_router/test_select.py::test_select_rejects_on_context_window` |
| 9 | Given `cross_model_review=True` and `implementer_model_id == preferred`, Then the fallback is chosen and the preferred is `rejected` with `"cross_model_review"` | `tests/model_router/test_select.py::test_select_defers_implementer_model_for_review` |
| 10 | Given `task_override` set and `allow_task_override=False`, Then override ignored; with `True` Then override chosen with `reason="override"` | `tests/model_router/test_select.py::test_select_task_override_respects_policy` |
| 11 | Given every candidate excluded or disabled, Then `BlockedProvider` whose detail lists each rejection | `tests/model_router/test_select.py::test_select_raises_blocked_provider` |
| 12 | For each `ERROR_TRIGGER_MAP` entry, When `classify_error(exc())`, Then the mapped trigger; `ValueError` → `None`; `BudgetExhausted(hard_action=BLOCK)` → `None` | `tests/model_router/test_classify_error.py::test_classify_error_maps_taxonomy` |
| 13 | Given an adapter exposing `classify_error` returning `CONTEXT_OVERFLOW`, Then that wins | `tests/model_router/test_classify_error.py::test_adapter_classification_takes_precedence` |
| 14 | Given usage 1 000 000 in / 100 000 out on prices 3/15, Then `cost_usd == 4.5`, `quantity == 1_100_000`, `category == LLM` | `tests/model_router/test_costing.py::test_usage_to_cost_record_prices` |
| 15 | When `adapter_for("nope")`, Then `ConfigError`; `health_all()` returns one entry per model | `tests/model_router/test_select.py::test_adapter_for_and_health_all` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0011 D-1/D-2/D-4; ADR-0004 D-9 (pricing lives in configuration); INTERFACES §5.3 steps 1–4; §23.
- `NEW NAME:` `walk.model_router.registry` module (`ModelsConfig`, `FamilyLevel`, `load_models_config`, `build_registry`, `resolve_family`, `FAMILY_PATTERN`), `ERROR_TRIGGER_MAP`, `estimate_usage_cost_usd`; `ModelId` pattern must accept family strings (E01-S17 note) — verify `walk.common.ids.ModelId` allows `/`.
- Rejection reason strings (`capability:<c>`, `context`, `effort`, `health`, `cross_model_review`, `MODEL_DISABLED`) are part of the `MODEL_SELECTED` payload and asserted by the gate; keep them literal.
- Commit subject: `feat: add model registry, routing selection and usage costing (E01-S20)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S21 — `ClaudeAdapter` (claude-agent-sdk)

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §17, §21, §22, §31 (per-call authorisation), §91 (tool allowlist, repository boundary), §128, §137 (Inv. 1, 2, 11), §139 (model adapter API)
**Depends on:** E01-S19, E01-S02
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A real `ModelAdapter` for Claude runs behind the normalised boundary: SDK messages become `AgentEvent`s, every native tool call is authorised through `RunSession.permission_authorizer` before execution, thinking blocks never leave the adapter, and the adapter is unit-tested through an injected SDK client.

#### Scope
- In: `ClaudeAdapter`, `ClaudeClient` protocol + SDK-backed implementation, message translation, effort mapping, `can_use_tool` request translation, `ClaudeSkillProjector` (pure projection), fake SDK client.
- Out: wiring the authorizer to `ToolInvoker` (E01-S26), writing projections into worktrees (E02-S06), credential handling (E02-S01 — the SDK uses its own login or `ANTHROPIC_API_KEY` from the scrubbed env).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/adapters/claude/__init__.py` | create | `ClaudeAdapter` |
| `src/walk/model_router/adapters/claude/client.py` | create | `ClaudeClient`, `SdkClaudeClient`, `ClaudeQueryOptions`, `SdkMessage` |
| `src/walk/model_router/adapters/claude/adapter.py` | create | `ClaudeAdapter` |
| `src/walk/model_router/adapters/claude/events.py` | create | `translate_message`, `ClaudeTranslationState` |
| `src/walk/model_router/adapters/claude/permissions.py` | create | `to_tool_call_request`, `to_sdk_permission_result`, `NATIVE_TOOL_NAMES` |
| `src/walk/model_router/adapters/claude/effort.py` | create | `map_claude_effort` |
| `src/walk/model_router/adapters/claude/projector.py` | create | `ClaudeSkillProjector` |
| `tests/fakes/fake_claude_client.py` | create | `FakeClaudeClient`, `scripted_messages` |
| `tests/model_router/adapters/__init__.py` | create | — |
| `tests/model_router/adapters/claude/__init__.py` | create | — |
| `tests/model_router/adapters/claude/test_adapter.py` | create | — |
| `tests/model_router/adapters/claude/test_events.py` | create | — |
| `tests/model_router/adapters/claude/test_permissions.py` | create | — |
| `tests/model_router/adapters/claude/test_effort.py` | create | — |
| `tests/model_router/adapters/claude/test_projector.py` | create | — |

#### Interface contract
Protocol: INTERFACES.md §2.1 `ModelAdapter`, §1.11 `SkillProjector`. Deltas:
```python
class ClaudeQueryOptions(FrozenModel):
    """Provider-mechanical options; field names are the ones ADR-0014 verified for `claude_agent_sdk.ClaudeAgentOptions`."""
    cwd: str
    model: ModelId
    allowed_tools: list[str]
    permission_mode: str                       # restricted mode name per ADR-0014 (the one that routes every tool through can_use_tool)
    max_turns: int
    system_prompt: str
    effort: str                                # low | medium | high | xhigh | max
    env: dict[str, str]
    resume: str | None = None                  # session id
    output_schema: JsonDict | None = None      # AgentOutput JSON schema when ADR-0014 confirms structured-output support
SdkMessage = object                            # opaque SDK message; translate_message inspects type name + attributes
class ClaudeClient(Protocol):
    def query(self, prompt: str, options: ClaudeQueryOptions, can_use_tool: Callable[[str, JsonDict], Awaitable[JsonDict]]) -> AsyncIterator[SdkMessage]: ...
    async def available(self) -> tuple[bool, str]: ...     # CLI present + authenticated; detail text
    async def interrupt(self, session_id: str) -> None: ...
class SdkClaudeClient: ...                     # the only module importing claude_agent_sdk (ARCHITECTURE §2.3)
class ClaudeTranslationState(WalkModel):       # per run: session_id, pending tool calls by SDK tool_use_id, cumulative usage, turns
def translate_message(msg: SdkMessage, state: ClaudeTranslationState, run_id: RunId, now: datetime) -> list[AgentEvent]: ...
NATIVE_TOOL_NAMES: dict[str, ToolName] = {"Read": "read", "Write": "write", "Edit": "edit", "MultiEdit": "edit", "Bash": "bash", "Glob": "glob", "Grep": "grep"}
def to_tool_call_request(tool_name: str, tool_input: JsonDict, *, run_id: RunId, role: AgentRole, worktree_path: str) -> ToolCallRequest: ...   # command from input["command"] for Bash; paths from file_path/path/notebook_path/pattern dirs; unknown tool name → tool=lower(name), kind=PROVIDER_NATIVE
def to_sdk_permission_result(decision: PermissionDecision) -> JsonDict: ...   # ADR-0014 shape: allow → {"behavior": "allow", "updatedInput": ...}; deny → {"behavior": "deny", "message": reason}
def map_claude_effort(effort: Effort, descriptor: ModelDescriptor, level: FamilyLevel | None) -> ProviderEffortConfig: ...   # params {"effort": low|medium|high|xhigh, "max_turns": n}; degrade per ADR-0011 D-4
class ClaudeSkillProjector:
    provider = "claude"
    def project(self, skill: Skill, worktree_path: str) -> SkillProjection: ...   # target `<worktree>/.claude/skills/<name>/SKILL.md`; content = front matter {name, description, version} + body_markdown
class ClaudeAdapter:
    provider = "claude"
    def __init__(self, client: ClaudeClient, descriptors: list[ModelDescriptor], clock: Clock, *, system_prompt_builder: Callable[[AgentInput], str], user_message_builder: Callable[[AgentInput], str]) -> None: ...   # builders injected by the composition root from walk.agents.rendering (model_router may import agents)
```

#### Behavior
1. `run(input, session)`: builds `ClaudeQueryOptions(cwd=session.worktree_path, model=session.model_id, allowed_tools=[SDK names of session.allowed_tools with kind PROVIDER_NATIVE], permission_mode=<restricted>, max_turns=session.max_turns, system_prompt=system_prompt_builder(input), effort=map_claude_effort(...).params["effort"], env=session.env_allowlist)` and streams `client.query(user_message_builder(input), options, can_use_tool)`; each SDK message passes through `translate_message`.
2. `can_use_tool(tool_name, tool_input)`: `request = to_tool_call_request(...)`; `decision = await session.permission_authorizer(request)`; records `TOOL_CALL_REQUESTED` (always) and returns `to_sdk_permission_result(decision)`; `REQUIRE_APPROVAL` is resolved by the authorizer (it awaits the approval) so the adapter only ever sees `ALLOW`/`DENY`.
3. `translate_message`: system `init` → `STARTED(session=ProviderSessionRef("claude", session_id, resumable=True))`; assistant text blocks → `TEXT`; thinking/redacted-thinking blocks → dropped (no event, not logged); `tool_use` blocks → remembered by id (the event was already emitted in rule 2); user `tool_result` blocks → `TOOL_CALL_RESULT(tool_result={"ok": not is_error, "content": truncated to 4 kB})`; result message → `USAGE(UsageReport from usage fields, cost from `total_cost_usd` when present else 0.0)` then `FINAL_OUTPUT` (rule 4) then `ENDED`; result with `is_error` → `ERROR(error=text, trigger=None)`.
4. Final output: structured output from the result message when `output_schema` was accepted (ADR-0014), else `read_output_file(session.output_path)`; `parse_agent_output` success → `FINAL_OUTPUT(output=…)`, failure/missing → `FINAL_OUTPUT(output=None, error=detail)` (E01-S19 boundary rule).
5. `resume(session_ref, instruction, session)`: same as `run` with `options.resume = session_ref.session_id` and `instruction` as the prompt; `session_ref.provider != "claude"` or `not resumable` → `NotResumable`.
6. Exceptions from the client are mapped before leaving the adapter: SDK connection/process errors → `ProviderUnavailable`; HTTP 429 / "rate limit" in the message → `RateLimited`; "overloaded"/5xx → `ProviderUnavailable`; `asyncio.TimeoutError` after `session.timeout_s` → `Timeout` (the client is interrupted first); CLI-not-found → `ConfigError`.
7. `health()` calls `client.available()` at most once per 60 s (clock-based cache) and returns `AdapterHealth`. `cancel(run_id)` interrupts the session id recorded for the run. `usage(run_id)` returns the cumulative report. `parse_output` = `parse_agent_output`. `skill_projector()` returns `ClaudeSkillProjector()`.
8. `descriptors()` returns the descriptors given at construction (the registry, not the adapter, is authoritative — ADR-0004 D-9).
9. Nothing outside `adapters/claude/client.py` imports `claude_agent_sdk`; the import is lazy inside `SdkClaudeClient` so the kernel runs without the optional extra.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a scripted client (init, text, tool_use Edit, tool_result, result), When `run` is consumed, Then events `STARTED, TEXT, TOOL_CALL_REQUESTED, TOOL_CALL_RESULT, USAGE, FINAL_OUTPUT, ENDED` and the output file parsed | `tests/model_router/adapters/claude/test_adapter.py::test_run_translates_sdk_stream` |
| 2 | Given a thinking block in the script, Then no event carries its text | `tests/model_router/adapters/claude/test_events.py::test_thinking_blocks_are_dropped` |
| 3 | Given the authorizer returns DENY, When the client invokes `can_use_tool("Bash", {"command": "rm -rf /"})`, Then the SDK result is a deny with the reason and `TOOL_CALL_REQUESTED` was emitted | `tests/model_router/adapters/claude/test_adapter.py::test_can_use_tool_denies_through_authorizer` |
| 4 | When `to_tool_call_request("Edit", {"file_path": "/wt/src/A.cs", ...})`, Then `tool == "edit"`, `paths == [...]`, `kind == PROVIDER_NATIVE`; `"Bash"` sets `command` | `tests/model_router/adapters/claude/test_permissions.py::test_to_tool_call_request_maps_tools` |
| 5 | When `to_sdk_permission_result(ALLOW)` / `(DENY)`, Then the ADR-0014 shapes | `tests/model_router/adapters/claude/test_permissions.py::test_sdk_permission_result_shapes` |
| 6 | Given no output file and no structured result, Then `FINAL_OUTPUT.output is None` with error detail | `tests/model_router/adapters/claude/test_adapter.py::test_missing_output_yields_repairable_final_output` |
| 7 | Given a client raising a connection error, Then `ProviderUnavailable`; raising a 429 error → `RateLimited` | `tests/model_router/adapters/claude/test_adapter.py::test_client_errors_are_mapped` |
| 8 | Given a client that never yields, When `timeout_s=1` (fake clock + injected sleep), Then `Timeout` and `interrupt` called | `tests/model_router/adapters/claude/test_adapter.py::test_timeout_interrupts_and_raises` |
| 9 | When `resume(ref)`, Then `options.resume == ref.session_id`; non-claude ref → `NotResumable` | `tests/model_router/adapters/claude/test_adapter.py::test_resume_passes_session_id_or_raises` |
| 10 | When `health()` twice within 60 s, Then `available()` called once | `tests/model_router/adapters/claude/test_adapter.py::test_health_is_cached` |
| 11 | For each `Effort`, When `map_claude_effort` on the opus descriptor, Then params equal ADR-0011 D-2 (`effort`, `max_turns`); on a descriptor without VERY_HIGH → degraded to HIGH with `degraded_from` | `tests/model_router/adapters/claude/test_effort.py::test_map_claude_effort_matches_adr_and_degrades` |
| 12 | When `ClaudeSkillProjector.project(skill, wt)`, Then target `<wt>/.claude/skills/<name>/SKILL.md`, `generated_from_sha256 == skill.content_sha256`, nothing written to disk | `tests/model_router/adapters/claude/test_projector.py::test_projection_is_pure_and_targets_claude_dir` |
| 13 | When `walk.model_router.adapters.claude.adapter` is imported without `claude_agent_sdk` installed (monkeypatched import), Then import succeeds | `tests/model_router/adapters/claude/test_adapter.py::test_module_imports_without_sdk` |

#### Evidence required
- Quality gate output.
- Optional (not gating): transcript of `uv run pytest -m integration tests/model_router/adapters/claude` against a logged-in SDK, if the implementer has credentials.

#### Notes
- ADR-0004 D-1/D-2/D-7; ADR-0006 D-1 (enforcement point 2); ADR-0011 D-2/D-4; ADR-0014 (E01-S02) is authoritative for SDK option/field names, permission-result shape and structured-output support — the implementer reads it before coding `client.py` and `permissions.py`.
- `NEW NAME:` `ClaudeClient`, `SdkClaudeClient`, `ClaudeQueryOptions`, `SdkMessage`, `ClaudeTranslationState`, `translate_message`, `to_tool_call_request`, `to_sdk_permission_result`, `NATIVE_TOOL_NAMES`, `map_claude_effort`, `ClaudeSkillProjector`, `FakeClaudeClient`; constructor builder callables (`system_prompt_builder`, `user_message_builder`) keep `rendering` out of the adapter.
- Pitfall: `TEXT` events are diagnostics only; the executor must not persist them (E01-S27 rule).
- Commit subject: `feat: add claude agent sdk model adapter (E01-S21)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S22 — `CodexAdapter` (`codex exec --json`)

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §17, §21, §22, §91 (sandbox, secret isolation), §128, §137 (Inv. 1, 2, 11), §139 (model adapter API, sandbox technology)
**Depends on:** E01-S19, E01-S02
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A real `ModelAdapter` for Codex drives `codex exec --json` as a sandboxed subprocess with a scrubbed environment, parses its JSON event lines into `AgentEvent`s (tool calls reported post-hoc), supports thread resume, and is unit-tested from recorded fixtures without spawning the CLI.

#### Scope
- In: `CodexAdapter`, process launcher protocol + asyncio implementation, command builder, `CodexSandboxConfig` model, event parsing/translation, effort mapping, `CodexSkillProjector` (pure), JSONL fixtures.
- Out: `configure_sandbox()` policy (which paths/network a run may use — E01-S26), `BoundaryAuditor` post-run audit (E01-S25/S27), projection writing (E02-S06), env allowlist contents (E02-S01 — the adapter passes `session.env_allowlist` and nothing else).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/adapters/codex/__init__.py` | create | `CodexAdapter` |
| `src/walk/model_router/adapters/codex/adapter.py` | create | `CodexAdapter` |
| `src/walk/model_router/adapters/codex/process.py` | create | `CodexProcessLauncher`, `AsyncioCodexProcessLauncher`, `CodexProcess` |
| `src/walk/model_router/adapters/codex/command.py` | create | `build_exec_command`, `build_resume_command`, `CODEX_BINARY` |
| `src/walk/model_router/adapters/codex/sandbox.py` | create | `CodexSandboxConfig`, `DEFAULT_SANDBOX_MODE` |
| `src/walk/model_router/adapters/codex/events.py` | create | `CodexEvent`, `parse_codex_line`, `translate_codex_event`, `CodexTranslationState` |
| `src/walk/model_router/adapters/codex/effort.py` | create | `map_codex_effort` |
| `src/walk/model_router/adapters/codex/projector.py` | create | `CodexSkillProjector`, `AGENTS_MD_START`, `AGENTS_MD_END` |
| `tests/fakes/fake_codex_launcher.py` | create | `FakeCodexProcessLauncher` |
| `tests/fixtures/codex/__init__.py` | create | — |
| `tests/fixtures/codex/exec_success.jsonl` | create | — |
| `tests/fixtures/codex/exec_error_rate_limit.jsonl` | create | — |
| `tests/fixtures/codex/exec_resume.jsonl` | create | — |
| `tests/model_router/adapters/codex/__init__.py` | create | — |
| `tests/model_router/adapters/codex/test_adapter.py` | create | — |
| `tests/model_router/adapters/codex/test_command.py` | create | — |
| `tests/model_router/adapters/codex/test_events.py` | create | — |
| `tests/model_router/adapters/codex/test_effort.py` | create | — |
| `tests/model_router/adapters/codex/test_projector.py` | create | — |

#### Interface contract
Protocol: INTERFACES.md §2.1 `ModelAdapter`, §1.11 `SkillProjector`. Deltas:
```python
CODEX_BINARY = "codex"
DEFAULT_SANDBOX_MODE = "workspace-write"
class CodexSandboxConfig(FrozenModel):
    mode: str = DEFAULT_SANDBOX_MODE          # read-only | workspace-write | danger-full-access (never set by the kernel)
    cwd: str
    network_enabled: bool = False
    writable_roots: list[str] = []            # extra `-c sandbox_workspace_write.writable_roots=[...]`; default none beyond cwd
class CodexProcess(Protocol):
    pid: int | None
    def lines(self) -> AsyncIterator[str]: ...                 # stdout lines (JSONL)
    async def wait(self) -> int: ...                           # exit code
    async def kill(self) -> None: ...
    async def stderr_text(self) -> str: ...
class CodexProcessLauncher(Protocol):
    async def launch(self, argv: list[str], *, cwd: str, env: dict[str, str]) -> CodexProcess: ...
    async def version(self) -> tuple[bool, str]: ...           # `codex --version` ok + text
    async def login_status(self) -> tuple[bool, str]: ...      # `codex login status`
class AsyncioCodexProcessLauncher: ...                         # asyncio.create_subprocess_exec; the only module spawning the codex CLI (ARCHITECTURE §2.3)
def build_exec_command(cfg: ProviderEffortConfig, sandbox: CodexSandboxConfig, *, prompt_file: str, output_schema_path: str | None) -> list[str]: ...
    # ["codex", "exec", "--json", "--sandbox", sandbox.mode, "--cd", sandbox.cwd, "-c", f"model={cfg.model_id}", "-c", f"model_reasoning_effort={cfg.params['model_reasoning_effort']}", *(["--output-schema", path] if path), *network/writable flags per ADR-0014, "-"]   # prompt on stdin
def build_resume_command(thread_id: str, cfg: ProviderEffortConfig, sandbox: CodexSandboxConfig) -> list[str]: ...   # ["codex", "exec", "resume", thread_id, "--json", ...same flags, "-"]
class CodexEvent(FrozenModel):                 # one parsed JSONL line: type, item_type, item_id, payload (raw dict)
def parse_codex_line(line: str) -> CodexEvent | None: ...     # None for blank/non-JSON lines (logged)
class CodexTranslationState(WalkModel): ...    # thread_id, usage so far, turns, last agent_message text, seen item ids
def translate_codex_event(ev: CodexEvent, state: CodexTranslationState, run_id: RunId, now: datetime) -> list[AgentEvent]: ...
def map_codex_effort(effort: Effort, descriptor: ModelDescriptor, level: FamilyLevel | None) -> ProviderEffortConfig: ...   # params {"model_reasoning_effort": low|medium|high|xhigh}
AGENTS_MD_START = "<!-- walk:skills:start -->"; AGENTS_MD_END = "<!-- walk:skills:end -->"
class CodexSkillProjector:
    provider = "codex"
    def project(self, skill: Skill, worktree_path: str) -> SkillProjection: ...   # target `<worktree>/AGENTS.md`; content = `## Skill: <name> (v<version>)` + body; E02-S06 merges all skill contents inside the managed markers
class CodexAdapter:
    provider = "codex"
    def __init__(self, launcher: CodexProcessLauncher, descriptors: list[ModelDescriptor], clock: Clock, *, system_prompt_builder: Callable[[AgentInput], str], user_message_builder: Callable[[AgentInput], str], sandbox_factory: Callable[[RunSession], CodexSandboxConfig] | None = None) -> None: ...   # sandbox_factory default: workspace-write, cwd = worktree, network off (E01-S26 injects the policy-aware factory)
```
Fixture event vocabulary (`tests/fixtures/codex/*.jsonl`, recorded by the E01-S02 spike and authoritative for the parser): `thread.started{thread_id}`, `turn.started`, `item.started|item.completed{item:{id,type,…}}` with item types `agent_message{text}`, `reasoning{…}`, `command_execution{command, exit_code, aggregated_output}`, `file_change{changes:[{path,kind}]}`, `turn.completed{usage:{input_tokens,cached_input_tokens,output_tokens}}`, `error{message}`. Exact field names follow ADR-0014; the fixture files are updated with it.

#### Behavior
1. `run(input, session)`: writes the prompt (`system_prompt_builder(input)` + `\n\n` + `user_message_builder(input)`) to `<worktree>/.walk/prompt.md` and the `AgentOutput` JSON schema to `<worktree>/.walk/output.schema.json`; `sandbox = sandbox_factory(session)`; launches `build_exec_command(map_codex_effort(...), sandbox, ...)` with `cwd=session.worktree_path`, `env=session.env_allowlist` (nothing inherited); emits `STARTED(session=ProviderSessionRef("codex", thread_id, resumable=True))` on `thread.started`.
2. Translation: `reasoning` items → dropped; `agent_message` → `TEXT` (last text remembered); `command_execution` completed → `TOOL_CALL_REQUESTED` immediately followed by `TOOL_CALL_RESULT` (post-hoc: `ToolCallRequest(tool="bash", kind=PROVIDER_NATIVE, command=…, worktree_path)`, `tool_result={"ok": exit_code == 0, "exit_code", "output": truncated 4 kB}`); `file_change` completed → the same pair with `tool="edit"` and `paths`; `turn.completed` → `USAGE` (cache tokens → `cache_read_tokens`, `cost_usd=0.0` — costing is the router's job); `error` → `ERROR(error=message, trigger=None)`; every event increments nothing else.
3. Codex tool calls are **not** pre-authorised (ADR-0004 D-8, ADR-0006 D-5); the adapter calls `session.permission_authorizer` only in *advisory* mode after the fact: `DENY` decisions are recorded as `TOOL_CALL_RESULT.tool_result["kernel_decision"] = "DENY"` so the executor/`BoundaryAuditor` can fail the run; the adapter never blocks the stream on them.
4. Process end: exit code 0 → final output from the last `agent_message` text when it parses as `AgentOutput`, else `read_output_file(session.output_path)`; success → `FINAL_OUTPUT(output=…)`, failure/missing → `FINAL_OUTPUT(output=None, error=detail)`; then cumulative `USAGE`, `ENDED`. Non-zero exit without an `error` event → mapped exception (rule 6).
5. `resume(session_ref, instruction, session)`: `build_resume_command(session_ref.session_id, …)` with `instruction` as the prompt; non-codex ref or `resumable=False` → `NotResumable`.
6. Error mapping: launcher cannot find the binary → `ConfigError`; exit code ≠ 0 with stderr matching `(?i)rate.?limit|429` → `RateLimited`; matching `(?i)quota|usage limit|insufficient` → `QuotaExhausted`; no output within `session.timeout_s` → process killed, `Timeout`; any other non-zero exit → `ProviderUnavailable(detail=stderr tail)`.
7. `cancel(run_id)` kills the recorded process; `health()` = `version()` ok and `login_status()` ok, cached 60 s; `usage(run_id)` cumulative; `parse_output` = `parse_agent_output`; `skill_projector()` = `CodexSkillProjector()`; `descriptors()` as constructed.
8. The adapter never adds environment variables (no `OPENAI_API_KEY`, no inherited `os.environ`); the launched env equals `session.env_allowlist` exactly.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `exec_success.jsonl` through the fake launcher, When `run` is consumed, Then events `STARTED, TEXT, (TOOL_CALL_REQUESTED, TOOL_CALL_RESULT)×2, USAGE, FINAL_OUTPUT, USAGE, ENDED` with `session_id` from `thread.started` | `tests/model_router/adapters/codex/test_adapter.py::test_run_translates_jsonl_stream` |
| 2 | Given a `reasoning` item in the fixture, Then no event contains its text | `tests/model_router/adapters/codex/test_events.py::test_reasoning_items_dropped` |
| 3 | When `parse_codex_line("not json")`, Then `None`; a `command_execution` line → `CodexEvent(item_type="command_execution")` | `tests/model_router/adapters/codex/test_events.py::test_parse_codex_line` |
| 4 | When `build_exec_command` for `gpt-5-codex`/HIGH with default sandbox, Then argv contains `exec`, `--json`, `--sandbox workspace-write`, `--cd <wt>`, `-c model=gpt-5-codex`, `-c model_reasoning_effort=high`, `--output-schema <path>` and ends with `-` | `tests/model_router/adapters/codex/test_command.py::test_build_exec_command_flags` |
| 5 | When `build_resume_command("thr_1", …)`, Then argv starts `codex exec resume thr_1 --json` | `tests/model_router/adapters/codex/test_command.py::test_build_resume_command` |
| 6 | When `run`, Then the launcher received `env == session.env_allowlist` and `cwd == worktree` | `tests/model_router/adapters/codex/test_adapter.py::test_launch_env_is_exactly_allowlist` |
| 7 | Given `exec_error_rate_limit.jsonl` + exit 1 + stderr "429 rate limit", Then `RateLimited` | `tests/model_router/adapters/codex/test_adapter.py::test_rate_limit_exit_maps_to_rate_limited` |
| 8 | Given exit 1 with unrelated stderr, Then `ProviderUnavailable` carrying the stderr tail | `tests/model_router/adapters/codex/test_adapter.py::test_unknown_failure_maps_to_provider_unavailable` |
| 9 | Given a launcher that emits nothing, When `timeout_s=1`, Then process killed and `Timeout` | `tests/model_router/adapters/codex/test_adapter.py::test_timeout_kills_process` |
| 10 | Given the authorizer returns DENY for a `command_execution`, Then `TOOL_CALL_RESULT.tool_result["kernel_decision"] == "DENY"` and the stream continues | `tests/model_router/adapters/codex/test_adapter.py::test_advisory_deny_is_recorded_not_blocking` |
| 11 | Given no parsable agent message and no output file, Then `FINAL_OUTPUT.output is None` with error | `tests/model_router/adapters/codex/test_adapter.py::test_missing_output_yields_repairable_final_output` |
| 12 | Given `exec_resume.jsonl`, When `resume(ref)`, Then the resume command was launched and events translated; non-codex ref → `NotResumable` | `tests/model_router/adapters/codex/test_adapter.py::test_resume_uses_thread_id_or_raises` |
| 13 | When `health()` with `login_status` false, Then `ok False` with detail; cached on second call | `tests/model_router/adapters/codex/test_adapter.py::test_health_requires_login_and_caches` |
| 14 | For each `Effort`, When `map_codex_effort`, Then `model_reasoning_effort` per ADR-0011 D-2; degraded when unsupported | `tests/model_router/adapters/codex/test_effort.py::test_map_codex_effort_matches_adr` |
| 15 | When `CodexSkillProjector.project`, Then target `<wt>/AGENTS.md`, content starts with `## Skill: <name>`, nothing written | `tests/model_router/adapters/codex/test_projector.py::test_projection_targets_agents_md` |

#### Evidence required
- Quality gate output.
- Optional (not gating): `uv run pytest -m integration tests/model_router/adapters/codex` against a logged-in `codex` CLI.

#### Notes
- ADR-0004 D-2/D-8; ADR-0006 D-5 (compensating controls — this story records decisions, E01-S25/S26/S27 enforce them); ADR-0009 D-5/D-8; ADR-0011 D-2; ADR-0014 authoritative for flags and event names.
- `NEW NAME:` `CodexProcessLauncher`, `AsyncioCodexProcessLauncher`, `CodexProcess`, `CodexSandboxConfig`, `DEFAULT_SANDBOX_MODE`, `CODEX_BINARY`, `build_exec_command`, `build_resume_command`, `CodexEvent`, `parse_codex_line`, `translate_codex_event`, `CodexTranslationState`, `map_codex_effort`, `CodexSkillProjector`, `AGENTS_MD_START/END`, `FakeCodexProcessLauncher`, fixture folder `tests/fixtures/codex/`.
- Architecture inconsistency to report: WBS §6 routes all subprocess calls through `walk.integrations.subprocess.SubprocessRunner`, but ARCHITECTURE §2.2 forbids `model_router → integrations`. This story therefore defines its own structurally equivalent `CodexProcessLauncher` inside the adapter package; the composition root may adapt one to the other. The architect should either allow `model_router → integrations (subprocess only)` or move `SubprocessRunner` to `walk.common`.
- Commit subject: `feat: add codex cli model adapter (E01-S22)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S23 — Integration protocols and `GitCliProvider` local operations

**Status:** TODO
**Type:** feat
**Requirements:** §26 (manifest model), §43 (protocol), §55 (protocol), §59, §60 (worktrees), §62 (protocols), §78 (protocol), §81 (`COMMIT`), §90, §91 (protected branches, repository boundary), §137 (Inv. 3)
**Depends on:** E01-S04, E01-S05
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every provider-boundary protocol and its value objects exist in `walk.integrations`, subprocess execution is injectable, and the local git operations needed by sandboxes, checkpoints and freshness (branches, worktrees, status/diff, WIP commits with trailers, guard hooks, ancestry) work against a real repository.

#### Scope
- In: `integrations.models`, `integrations.protocols` (all INTERFACES §1.12, §2.2–§2.6 protocols), `NotSupported`/`GitError`, `SubprocessRunner`, `GitCliProvider` local operations, guard-hook scripts, `tests/fakes/fake_subprocess.py`, `tmp_game_repo` fixture.
- Out: `push`, `open_pr`, `merge`, `squash_wip` (E03-S01 — raise `ConfigError("implemented in E03-S01")`), `IntegrationManager` service (E03-S03), work/unity/graphify/asset providers (E03/E04/E08), `CredentialStore` (E02-S01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/integrations/__init__.py` | create | re-exports |
| `src/walk/integrations/models.py` | create | `ReadinessState`, `ComponentStatus`, `EnvironmentManifest`, `ProductionKit`, `WorkProviderEvent`, `WorkItemRef`, `CommitInfo`, `PullRequestRef`, `BuildTarget`, `JobResult`, `AssetRequest`, `AssetJob`, `AssetProvenance`, `GraphNode`, `GraphEdge`, `GraphNeighborhood` |
| `src/walk/integrations/protocols.py` | create | `IntegrationManager`, `WorkProvider`, `GitProvider`, `UnityProvider`, `CiProvider`, `AssetProvider`, `CodeGraphProvider` |
| `src/walk/integrations/errors.py` | create | `NotSupported`, `GitError` |
| `src/walk/integrations/subprocess.py` | create | `SubprocessResult`, `SubprocessRunner`, `AsyncioSubprocessRunner` |
| `src/walk/integrations/git/__init__.py` | create | `GitCliProvider` |
| `src/walk/integrations/git/provider.py` | create | `GitCliProvider`, `FORBIDDEN_COMMIT_PATHSPECS`, `WORK_ITEM_TRAILER` |
| `src/walk/integrations/git/guard_hooks.py` | create | `render_guard_hook`, `GUARD_HOOK_MARKER` |
| `tests/fakes/fake_subprocess.py` | create | `FakeSubprocessRunner` |
| `tests/integrations/__init__.py` | create | — |
| `tests/integrations/test_models.py` | create | — |
| `tests/integrations/test_subprocess.py` | create | — |
| `tests/integrations/git/__init__.py` | create | — |
| `tests/integrations/git/test_provider.py` | create | — |
| `tests/integrations/git/test_guard_hooks.py` | create | — |
| `tests/conftest.py` | modify | fixture `tmp_game_repo` (real git repo: `git init -b main`, user config, one commit with `README.md`, `.gitignore` containing `.walk/` and `.ai/kernel.db`) |

#### Interface contract
Models: DOMAIN-MODEL §4.13 verbatim; INTERFACES §2.2–§2.6 value objects (`WorkItemRef`, `CommitInfo`, `PullRequestRef`, `BuildTarget`, `JobResult`, `AssetRequest`, `AssetJob`, `AssetProvenance`, `GraphNode`, `GraphEdge`, `GraphNeighborhood`) placed in `integrations.models` (WBS §3.2). Protocols: INTERFACES.md §1.12, §2.2, §2.3, §2.4, §2.5, §2.6 verbatim. Deltas:
```python
class NotSupported(PermanentError):
    """Provider does not implement the operation (e.g. LocalWorkProvider.parse_webhook)."""


class GitError(TransientError):
    """git exited non-zero; detail = argv + stderr tail."""


class SubprocessResult(FrozenModel):
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class SubprocessRunner(Protocol):
    async def run(
        self,
        argv: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_s: int = 120,
        input_text: str | None = None,
    ) -> SubprocessResult: ...


class AsyncioSubprocessRunner: ...  # asyncio.create_subprocess_exec; env=None → inherit; timeout → kill + Timeout


WORK_ITEM_TRAILER = "Walk-Work-Item"
FORBIDDEN_COMMIT_PATHSPECS: tuple[str, ...] = (
    ":(exclude).ai/kernel.db",
    ":(exclude).ai/kernel.db-wal",
    ":(exclude).ai/kernel.db-shm",
    ":(exclude).walk/**",
    ":(exclude)**/*.env",
    ":(exclude)ProjectSettings/*Secrets*",
)
GUARD_HOOK_MARKER = "# walk-guard-hook v1"


def render_guard_hook(
    kind: Literal["pre-commit", "pre-push"], protected_branches: list[str]
) -> str: ...  # POSIX sh script; exits 1 with a message when the current/target branch matches a protected glob


class GitCliProvider:
    provider = "git-cli"

    def __init__(
        self,
        repo_root: Path,
        runner: SubprocessRunner,
        ledger: LedgerManager,
        idempotency: IdempotencyStore,
        clock: Clock,
        *,
        project_key: ProjectKey,
    ) -> None: ...
    async def discard_changes(
        self, path: str
    ) -> None: ...  # `git checkout -- .` + `git clean -fd` restricted to the worktree (used by BoundaryAuditor path, E01-S27)

    # GitProvider methods per INTERFACES §2.3; remote ops deferred to E03-S01
```

#### Behavior
1. `AsyncioSubprocessRunner.run` never raises on non-zero exit (returns the result); raises `Timeout` after killing the process; `input_text` is written to stdin; `env=None` inherits the parent environment, a dict replaces it entirely.
2. `GitCliProvider` runs every command through the runner with `cwd` = the given path (or `repo_root`) and raises `GitError` on non-zero exit, except where a method documents otherwise.
3. `head(path)` → `git rev-parse HEAD`; `current_branch(path)` → `git rev-parse --abbrev-ref HEAD`; `status(path)` → `git status --porcelain=v1` paths; `diff_names(path, base)` → `git diff --name-only <base>` (base `None` → `HEAD`) ∪ untracked files; `is_ancestor` → `git merge-base --is-ancestor` (exit 1 → `False`, other → `GitError`); `changed_between(a, b, paths)` → `git diff --name-only a b -- paths`.
4. `ensure_branch(name, base, idempotency_key)`: wrapped in `IdempotencyStore.run(key)`; creates `name` from `base` if absent (`git branch name base`), returns the branch name; existing branch → no-op.
5. `add_worktree(path, branch)` → `git worktree add <path> <branch>` (creates parent dirs; existing worktree at path → no-op) and returns the absolute path; `remove_worktree(path, force)` → `git worktree remove [--force] <path>` then `git worktree prune`.
6. `commit_all(path, message, trailer_work_item, idempotency_key)`: `git add -A -- . <FORBIDDEN_COMMIT_PATHSPECS>`; if nothing staged → `None`; else `git commit -m <message> --trailer "Walk-Work-Item: <id>"` (fallback: trailer appended to the message when the git version lacks `--trailer`); returns `CommitInfo(sha, message, files)`; writes `COMMIT` (payload: sha, branch, files count, work item) in the same `IdempotencyStore` transaction; replay with an existing key returns the stored `CommitInfo` without committing.
7. `install_guard_hooks(path, protected_branches)` writes `pre-commit` and `pre-push` into the worktree's hooks dir (`git rev-parse --git-path hooks`), executable, overwriting only files carrying `GUARD_HOOK_MARKER` (foreign hooks → `ConfigError`); the scripts block commits/pushes to any branch matching a protected glob.
8. `push`, `open_pr`, `merge`, `squash_wip` raise `ConfigError("implemented in E03-S01")`.
9. `discard_changes(path)` resets tracked and untracked changes inside the worktree only; never touches `repo_root` when `path` differs.
10. The provider never reads credentials and never calls a remote in this story.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `EnvironmentManifest`, `JobResult`, `GraphNeighborhood` are built from fixtures, Then JSON round-trips and `BuildTarget` has the five INTERFACES §2.4 values | `tests/integrations/test_models.py::test_integration_models_round_trip` |
| 2 | When `AsyncioSubprocessRunner.run(["python", "-c", "print(1)"])`, Then exit 0 and stdout `1`; a failing command returns non-zero without raising | `tests/integrations/test_subprocess.py::test_runner_returns_result_without_raising` |
| 3 | Given a sleeping command and `timeout_s=1`, Then `Timeout` | `tests/integrations/test_subprocess.py::test_runner_timeout_kills_and_raises` |
| 4 | When `FakeSubprocessRunner` is scripted for an argv prefix, Then `run` returns the scripted result and records the call | `tests/integrations/test_subprocess.py::test_fake_runner_scripts_and_records` |
| 5 | Given `tmp_game_repo`, When `head`, `current_branch`, Then a 40-hex sha and `main` | `tests/integrations/git/test_provider.py::test_head_and_current_branch` |
| 6 | When `ensure_branch("feat/STORY-0001-x", "main", key)` twice, Then branch exists once and the second call replays the key | `tests/integrations/git/test_provider.py::test_ensure_branch_is_idempotent` |
| 7 | When `add_worktree(<repo>/.walk/worktrees/RUN1, branch)`, Then the path exists on that branch; `remove_worktree` removes it and prunes | `tests/integrations/git/test_provider.py::test_worktree_add_and_remove` |
| 8 | Given a dirty worktree with `src/A.cs` and `.walk/x.json` and `secrets.env`, When `commit_all`, Then only `src/A.cs` committed, message carries `Walk-Work-Item: STORY-0001`, `COMMIT` ledger written | `tests/integrations/git/test_provider.py::test_commit_all_excludes_forbidden_and_adds_trailer` |
| 9 | Given a clean worktree, When `commit_all`, Then `None` and no ledger event | `tests/integrations/git/test_provider.py::test_commit_all_clean_returns_none` |
| 10 | When `commit_all` with an already-used idempotency key, Then the stored `CommitInfo` is returned and HEAD unchanged | `tests/integrations/git/test_provider.py::test_commit_all_replays_idempotency_key` |
| 11 | When `status`/`diff_names` on a worktree with one modified and one untracked file, Then both listed | `tests/integrations/git/test_provider.py::test_status_and_diff_names_include_untracked` |
| 12 | Given commits A→B, When `is_ancestor(A, B)` Then `True`; `(B, A)` Then `False`; `changed_between(A, B, paths=["src/"])` lists only files under `src/` | `tests/integrations/git/test_provider.py::test_ancestry_and_changed_between` |
| 13 | When `install_guard_hooks(wt, ["main", "release/*"])` then a commit is attempted on `main` in that worktree, Then git rejects it; on `feat/x` it succeeds | `tests/integrations/git/test_provider.py::test_guard_hooks_block_protected_branches` |
| 14 | Given a foreign `pre-commit` hook without the marker, Then `ConfigError` and the file untouched | `tests/integrations/git/test_guard_hooks.py::test_foreign_hook_is_not_overwritten` |
| 15 | When `render_guard_hook("pre-push", ["release/*"])`, Then script contains the marker and the glob | `tests/integrations/git/test_guard_hooks.py::test_render_guard_hook_contents` |
| 16 | When `push`/`open_pr`/`merge`/`squash_wip`, Then `ConfigError` mentioning E03-S01 | `tests/integrations/git/test_provider.py::test_remote_operations_deferred` |
| 17 | When `discard_changes(wt)` on a dirty worktree, Then clean; repo root untouched | `tests/integrations/git/test_provider.py::test_discard_changes_scoped_to_worktree` |

#### Evidence required
- Quality gate output (requires `git` ≥ 2.32 on PATH; record `git --version`).

#### Notes
- ADR-0002 D-4/D-7 (WIP commits, idempotency in the same transaction); ADR-0005 (protocol only); ADR-0006 D-1 (guard hooks = enforcement point 4); ADR-0009 D-5/D-10; ARCHITECTURE §4.3 (`COMMIT` write point), §6 (forbidden paths).
- `NEW NAME:` `GitError`, `SubprocessResult`, `GitCliProvider.discard_changes` (INTERFACES §1.13 `BoundaryAuditor` prescribes `git checkout -- .` without naming a `GitProvider` method), `FORBIDDEN_COMMIT_PATHSPECS`, `WORK_ITEM_TRAILER`, `render_guard_hook`, `GUARD_HOOK_MARKER`, `FakeSubprocessRunner`, fixture `tmp_game_repo`; `SubprocessRunner`/`AsyncioSubprocessRunner`/`NotSupported` are already registered in WBS §6.
- Pitfall (Windows): hook scripts need LF line endings and a `#!/bin/sh` shebang (Git for Windows ships `sh`); write bytes, not text with platform newlines. Worktree paths from `git worktree list --porcelain` are forward-slash; normalise with `Path.resolve()` before comparing.
- Commit subject: `feat: add integration protocols, subprocess runner and local git provider (E01-S23)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S24 — Context manager skeleton: mandatory items, token budget, `ContextBundle`

**Status:** TODO
**Type:** feat
**Requirements:** §6.8, §40, §42 (flagging only), §43 (optional graph), §137 (Inv. 2), §138 (Hallucinated Project State, Excessive Context Cost)
**Depends on:** E01-S08, E01-S16
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`ContextManager.build` produces a deterministic `ContextBundle` containing the §40 mandatory tier in order (work item, workflow state, open handover, feature/bug context + selected project sections, accepted decisions, approved-artifact metadata) within an effort-derived token budget, with a manifest suitable for checkpoints.

#### Scope
- In: `context.models`, `context.protocols`, token budget (ADR-0012 D-3), `DefaultContextManager` mandatory tier a–f, freshness flag plumbing, determinism contract, `WorkflowRepository.transitions`.
- Out: ranked candidates g–j, scoring, source slicing, code graph (E04-S08…S12); real freshness assessment (E04-S03); decisions and approved artifacts providers (E04-S05, E02-S12 — injected callables default to empty).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/context/__init__.py` | create | re-exports |
| `src/walk/context/models.py` | create | `ContextItemKind`, `ContextItem`, `ContextRequest`, `ContextBundle`, `ContextBundleRef` |
| `src/walk/context/protocols.py` | create | `ContextManager` |
| `src/walk/context/budget.py` | create | `EFFORT_BUDGET_RATIO`, `CHARS_PER_TOKEN`, `estimate_tokens`, `token_budget_for` |
| `src/walk/context/service.py` | create | `DefaultContextManager`, `PROJECT_CONTEXT_SECTIONS`, `MANDATORY_ORDER` |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.transitions` |
| `tests/context/__init__.py` | create | — |
| `tests/context/test_models.py` | create | — |
| `tests/context/test_budget.py` | create | — |
| `tests/context/test_service_mandatory.py` | create | — |
| `tests/context/test_determinism.py` | create | — |
| `tests/workflow/test_repository.py` | modify | — |

#### Interface contract
Models: DOMAIN-MODEL §4.9 verbatim. Protocol: INTERFACES.md §1.7. Deltas:
```python
EFFORT_BUDGET_RATIO: dict[Effort, float] = {
    LOW: 0.20,
    MEDIUM: 0.35,
    HIGH: 0.50,
    VERY_HIGH: 0.60,
}  # ADR-0012 D-3
CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int: ...  # ceil(len(text) / 3.5)
def token_budget_for(
    effort: Effort, context_window_tokens: int, max_output_tokens: int
) -> int: ...  # int(ratio × window) − max_output; minimum 1000


PROJECT_CONTEXT_SECTIONS: tuple[str, ...] = (
    "Goals",
    "Technical Constraints",
    "Coding Conventions",
    "Architecture Overview",
)  # matched case-insensitively against SECTION_ORDER[PROJECT] headings
MANDATORY_ORDER: tuple[ContextItemKind, ...] = (
    WORK_ITEM,
    WORKFLOW_STATE,
    HANDOVER,
    FEATURE_CONTEXT,
    BUG_CONTEXT,
    PROJECT_CONTEXT,
    DECISION,
    APPROVED_ARTIFACT,
)
FreshnessProbe = Callable[[MemoryDocument, Sha], Awaitable[FreshnessAssessment | None]]
HandoverLookup = Callable[[WorkItemId], Awaitable[MemoryDocument | None]]
DecisionLookup = Callable[[WorkItem, list[str]], Awaitable[list[Decision]]]
ArtifactLookup = Callable[[WorkItem], Awaitable[list[ApprovedArtifact]]]


class DefaultContextManager:
    def __init__(
        self,
        workflow: WorkflowManager,
        items: WorkflowRepository,
        memory: MemoryManager,
        hooks: HookManager,
        ledger: LedgerManager,
        clock: Clock,
        *,
        head_resolver: Callable[[], Awaitable[Sha]],
        freshness: FreshnessProbe | None = None,
        handovers: HandoverLookup | None = None,
        decisions: DecisionLookup | None = None,
        artifacts: ArtifactLookup | None = None,
    ) -> None: ...


# WorkflowRepository
async def transitions(
    self, work_item_id: WorkItemId, *, limit: int = 5
) -> list[WorkItemTransition]: ...  # newest first
```

#### Behavior
1. `build(request)` implements INTERFACES §5.4 steps 1–3, 7, 8 for the mandatory tier; steps 4–6 (candidates) are a no-op returning `excluded_count = 0` until E04-S08.
2. Item ids are stable: `WORK_ITEM:<id>`, `WORKFLOW_STATE:<id>`, `HANDOVER:<HO id>`, `FEATURE_CONTEXT:<FEAT id>`, `BUG_CONTEXT:<BUG id>`, `PROJECT_CONTEXT:project`, `DECISION:<DEC id>`, `APPROVED_ARTIFACT:<id>`; every mandatory item has `mandatory=True`, `score=1.0`.
3. `WORK_ITEM` content = the item serialised as sorted-key JSON (contract included); `WORKFLOW_STATE` content = state, `state_version`, `fix_loops`, `blocked_reason`, the last five transitions (`WorkflowRepository.transitions`) as a table.
4. `HANDOVER` is included only when `handovers(work_item_id)` returns a document (its rendered Markdown is the content); `FEATURE_CONTEXT`/`BUG_CONTEXT` reads `MemoryManager.read(<feature or bug id>)` where the feature is the item itself or its nearest FEATURE ancestor (via `parent_id`; bugs use `related_feature_id`); a missing document yields an item with content `(no context document yet for <id>)` so the agent is told explicitly (Hallucinated Project State); `PROJECT_CONTEXT` includes only the `PROJECT_CONTEXT_SECTIONS` of `project.md` (missing document → item omitted).
5. For every memory-backed item, when a `freshness` probe is injected and returns an assessment with `status != CURRENT`: `requires_verification = True`, `freshness` set, `ON_CONTEXT_STALE` fired with payload `{doc_id, status, reason}`; the `CONTEXT_FRESHNESS` ledger event belongs to `MemoryManager` (E04-S03) and is **not** written here (WBS §3.5).
6. `DECISION` items come from `decisions(item, affected_systems=[])` (ACCEPTED only, content = the decision as Markdown); `APPROVED_ARTIFACT` items carry metadata only (id, kind, version, scope, sha) — never the payload.
7. Mandatory items are never trimmed; when their total exceeds `request.token_budget` the bundle is still returned and `TelemetryManager`-free: a `logging` warning is emitted and `ContextBundle.excluded_count` stays 0.
8. `ContextBundle.items` order = `MANDATORY_ORDER` (bugs have no `FEATURE_CONTEXT` item unless `related_feature_id` is set, in which case both appear, bug first); `head_commit = await head_resolver()`; `built_at = clock.now()`.
9. Determinism (ADR-0012 D-7): two `build()` calls with the same DB, `.ai/` tree, HEAD and request produce byte-identical `model_dump_json(exclude={"built_at"})`.
10. `token_budget_for` never returns less than 1000 and raises `ValueError` when `max_output_tokens >= context_window_tokens`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `ContextItemKind` members are enumerated, Then the 12 DOMAIN-MODEL §4.9 values; `ContextBundle.ref()` lists ids and stale ids | `tests/context/test_models.py::test_context_models_and_ref` |
| 2 | For each `Effort`, When `token_budget_for(e, 200_000, 16_000)`, Then `int(ratio × 200000) − 16000`; `estimate_tokens("a" * 35) == 10` | `tests/context/test_budget.py::test_token_budget_and_estimate` |
| 3 | When `token_budget_for(LOW, 10_000, 16_000)`, Then `ValueError`; tiny window → minimum 1000 | `tests/context/test_budget.py::test_token_budget_bounds` |
| 4 | Given a story under a feature with a context document and a project document, When `build`, Then items `WORK_ITEM, WORKFLOW_STATE, FEATURE_CONTEXT, PROJECT_CONTEXT` in that order, all `mandatory`, project item contains only the four sections | `tests/context/test_service_mandatory.py::test_build_includes_mandatory_items_in_order` |
| 5 | Given an open handover document returned by the lookup, Then `HANDOVER` item placed after `WORKFLOW_STATE` | `tests/context/test_service_mandatory.py::test_build_includes_open_handover` |
| 6 | Given a feature without a context document, Then `FEATURE_CONTEXT` content says no document yet | `tests/context/test_service_mandatory.py::test_missing_feature_context_is_explicit` |
| 7 | Given a bug with `related_feature_id`, Then `BUG_CONTEXT` then `FEATURE_CONTEXT` | `tests/context/test_service_mandatory.py::test_bug_includes_bug_then_feature_context` |
| 8 | Given a freshness probe returning `POSSIBLY_STALE`, Then item `requires_verification`, `ref().stale_item_ids` contains it, `ON_CONTEXT_STALE` fired once, no `CONTEXT_FRESHNESS` ledger row | `tests/context/test_service_mandatory.py::test_stale_item_flagged_and_hook_fired` |
| 9 | Given decision and artifact lookups returning one each, Then `DECISION` and `APPROVED_ARTIFACT` items present, artifact content has no payload key | `tests/context/test_service_mandatory.py::test_decisions_and_artifact_metadata_included` |
| 10 | Given five transitions on the item, Then `WORKFLOW_STATE` content lists the newest five, newest first | `tests/context/test_service_mandatory.py::test_workflow_state_lists_recent_transitions` |
| 11 | Given a tiny `token_budget`, Then mandatory items still included and `excluded_count == 0` | `tests/context/test_service_mandatory.py::test_mandatory_items_never_trimmed` |
| 12 | When `build` twice on unchanged inputs, Then `model_dump_json(exclude={"built_at"})` identical | `tests/context/test_determinism.py::test_bundle_is_byte_identical` |
| 13 | When `WorkflowRepository.transitions(id, limit=2)`, Then the two newest rows | `tests/workflow/test_repository.py::test_transitions_returns_newest_first` |

#### Evidence required
- Quality gate output.

#### Notes
- ADR-0012 D-1/D-3/D-4/D-7; INTERFACES §5.4 steps 1–3, 7–8; §40 order.
- `NEW NAME:` `walk.context.budget` module (`EFFORT_BUDGET_RATIO`, `CHARS_PER_TOKEN`, `estimate_tokens`), `PROJECT_CONTEXT_SECTIONS`, `MANDATORY_ORDER`, injected lookup callables (`FreshnessProbe`, `HandoverLookup`, `DecisionLookup`, `ArtifactLookup`), `WorkflowRepository.transitions`. The lookups exist because `context` may not import `runtime` (handovers table) and the decisions/artifact services arrive in later epics; E01-S30 wires `CheckpointManager.latest_open_handover_doc`.
- Pitfall: serialise with `sort_keys=True` and fixed `datetime` formatting; never include `clock.now()` inside item content.
- Commit subject: `feat: add context manager skeleton with mandatory tier and token budget (E01-S24)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S25 — Runtime persistence: `AgentRun` repository, `SandboxManager`, `CheckpointManager`, `BoundaryAuditor`

**Status:** TODO
**Type:** feat
**Requirements:** §22, §41, §54, §60, §89, §90, §91 (repository boundary), §137 (Inv. 10, 12, 13)
**Depends on:** E01-S18, E01-S20, E01-S23
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Agent runs, checkpoints and handovers persist in SQLite; every run gets an isolated git worktree with guard hooks; a checkpoint makes a WIP commit, records the run's durable state and (when asked) writes a handover document; and a post-run boundary audit detects writes outside the allowed paths.

#### Scope
- In: `runtime.models` (`AgentRunState`, `CheckpointKind`, `AgentRun`, `Checkpoint`, `AppliedEffects`), `runtime.protocols` (all INTERFACES §1.13 protocols), repositories, `DefaultSandboxManager`, `DefaultCheckpointManager`, `DefaultBoundaryAuditor`, `tests/fakes/fake_git_provider.py`.
- Out: `ToolInvoker` (E01-S26), `AgentExecutor`/`OutputApplier` (E01-S27), recovery (E01-S28), skill projections into the worktree (E02-S06 modifies `sandbox.py`), scrubbed env (E02-S01), forbidden-path configuration from `permissions.yaml` (E02-S14).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/__init__.py` | create | re-exports |
| `src/walk/runtime/models.py` | create | `AgentRunState`, `CheckpointKind`, `AgentRun`, `Checkpoint`, `AppliedEffects` (re-exports `AgentOutputStatus` from `walk.agents.models`) |
| `src/walk/runtime/protocols.py` | create | `CheckpointManager`, `AgentExecutor`, `ToolInvoker`, `OutputApplier`, `SandboxManager`, `BoundaryAuditor` |
| `src/walk/runtime/errors.py` | create | `RunNotFound`, `CheckpointNotFound` |
| `src/walk/runtime/repository.py` | create | `AgentRunRepository`, `CheckpointRepository`, `HandoverRepository` |
| `src/walk/runtime/sandbox.py` | create | `DefaultSandboxManager`, `WORKTREES_DIR`, `branch_name_for` |
| `src/walk/runtime/checkpoints.py` | create | `DefaultCheckpointManager` |
| `src/walk/runtime/boundary.py` | create | `DefaultBoundaryAuditor`, `DEFAULT_FORBIDDEN_PATHS`, `DEFAULT_ALLOWED_PATHS` |
| `tests/fakes/fake_git_provider.py` | create | `FakeGitProvider` |
| `tests/runtime/__init__.py` | create | — |
| `tests/runtime/test_models.py` | create | — |
| `tests/runtime/test_repository.py` | create | — |
| `tests/runtime/test_sandbox.py` | create | — |
| `tests/runtime/test_checkpoints.py` | create | — |
| `tests/runtime/test_boundary.py` | create | — |

#### Interface contract
Models: DOMAIN-MODEL §3 runtime enums (except the relocated `AgentOutputStatus`), §4.11 verbatim; `AppliedEffects` from INTERFACES §1.13 (WBS §3.2). Protocols: INTERFACES.md §1.13 verbatim. Deltas:
```python
class RunNotFound(PermanentError): ...
class CheckpointNotFound(PermanentError): ...
class AgentRunRepository(Repository[AgentRun]):      # table agent_runs; projection columns per DOMAIN-MODEL §6.2
    async def by_state(self, states: list[AgentRunState], *, kernel_instance_not: str | None = None) -> list[AgentRun]: ...
    async def for_item(self, work_item_id: WorkItemId) -> list[AgentRun]: ...
    async def set_state(self, run_id: RunId, state: AgentRunState, *, failure_reason: str | None = None, conn: sqlite3.Connection | None = None) -> AgentRun: ...
class CheckpointRepository:                           # append-only; insert(conn) + latest(run_id) + latest_for_item(work_item_id) + next_seq(run_id)
class HandoverRepository(Repository[Handover]):       # table handovers; projection: work_item_id, from_run_id, to_run_id, reason, ai_path, created_at
    async def latest_open(self, work_item_id: WorkItemId) -> Handover | None: ...   # to_run_id IS NULL, newest
    async def close(self, handover_id: HandoverId, to_run_id: RunId) -> Handover: ...
WORKTREES_DIR = ".walk/worktrees"
def branch_name_for(item: WorkItem) -> str: ...     # item.branch or f"feat/{item.id.lower()}-{slug(title)[:30]}"
class DefaultSandboxManager:
    def __init__(self, repo_root: Path, git: GitProvider, protected_branches: list[str]) -> None: ...
    async def create(self, run: AgentRun, item: WorkItem) -> str: ...   # ensure_branch(idempotency `git.branch:{item.id}`) → add_worktree(<repo>/.walk/worktrees/<run_id>) → install_guard_hooks → returns absolute path
    async def remove(self, run: AgentRun, *, keep_branch: bool = True) -> None: ...
class DefaultCheckpointManager:
    def __init__(self, db: Database, runs: AgentRunRepository, checkpoints: CheckpointRepository, handovers: HandoverRepository, git: GitProvider,
                 memory: MemoryManager, hooks: HookManager, ledger: LedgerManager, ids: IdSequenceStore, idempotency: IdempotencyStore, clock: Clock, *, project_key: ProjectKey) -> None: ...
    async def latest_open_handover(self, work_item_id: WorkItemId) -> Handover | None: ...
    async def latest_open_handover_doc(self, work_item_id: WorkItemId) -> MemoryDocument | None: ...   # for ContextManager (E01-S24 HandoverLookup)
    async def close_handover(self, handover_id: HandoverId, to_run_id: RunId) -> Handover: ...
DEFAULT_FORBIDDEN_PATHS: tuple[str, ...] = (".ai/**", ".walk/**", "**/*.env", "ProjectSettings/*Secrets*", ".git/**", ".claude/**", "AGENTS.md", ".codex/**")
DEFAULT_ALLOWED_PATHS: tuple[str, ...] = ("**",)
class DefaultBoundaryAuditor:
    def audit(self, worktree_path: str, changed_files: list[str], allowed_paths: list[str], forbidden_paths: list[str]) -> list[str]: ...
```

#### Behavior
1. `AgentRunRepository.set_state` updates `state`, `failure_reason`, `ended_at` (for terminal states) and the JSON column atomically; unknown id → `RunNotFound`. `by_state(states, kernel_instance_not=X)` is the recovery query (ARCHITECTURE §5.3 step 1).
2. `CheckpointRepository` has no update/delete methods; `next_seq(run_id)` = max(seq)+1 (1 for the first); the unique index `(run_id, seq)` makes concurrent duplicates fail loudly.
3. `SandboxManager.create`: branch from `item.branch` or `branch_name_for(item)` based on `Project.default_branch`; the worktree path is `<repo>/.walk/worktrees/<run_id>`; guard hooks installed with `protected_branches`; returns the absolute path and the caller stores `run.worktree_path/branch`. Projections are written by E02-S06 (extension point: a `post_create` coroutine list, empty here).
4. `SandboxManager.remove(run, keep_branch=True)` removes the worktree (force) and never deletes the branch unless `keep_branch=False` and the branch is not protected.
5. `checkpoint(run, kind, handover=None)`: (1) `git.commit_all(run.worktree_path, f"wip({run.work_item_id}): checkpoint {seq}", trailer_work_item=run.work_item_id, idempotency_key=f"git.commit:{run.id}:{seq}")` — `None` when clean; (2) `head_sha = git.head(worktree)`, `dirty_files = git.status(worktree)` (after the commit, normally empty); (3) if `handover` given: allocate `HO-` id when `handover.id` is empty, insert `handovers` row, `memory.write_handover(to_document(handover), actor=Actor(role=run.role, run_id), head=head_sha, branch=run.branch)` (idempotency key `handover:{run.id}:{seq}` — replay skips the write and reuses the stored path), set `run.handover_out_id`; (4) insert the `checkpoints` row with `Checkpoint(id=ULID, seq, kind, role, model_id, effort, workflow_state=<item state passed via run context>, head_sha, wip_commit_sha, dirty_files, tool_calls_so_far=run.tool_calls, budget_consumed, provider_session=run.provider_session, handover_id, context_manifest)` — `budget_consumed` and `context_manifest` are supplied by the caller through optional keyword args `budget_consumed: dict[BudgetDimension, float] | None`, `context_manifest: ContextBundleRef | None` (empty defaults); (5) write `CHECKPOINT_CREATED` (payload: seq, kind, head_sha, wip_commit_sha, handover_id) in the same transaction as the row; (6) after commit fire `ON_AGENT_CHECKPOINT`.
6. `latest(run_id)`/`latest_for_item(work_item_id)` return the newest row or `None`; `interrupted_runs(current_instance)` = `runs.by_state([RUNNING, PAUSED_FOR_APPROVAL], kernel_instance_not=current_instance)`.
7. `build_handover(run, reason, partial_output)`: never reads transcripts; `task_summary` = item contract goal (or title); `current_state` = `f"{item.state}; {run.tool_calls} tool calls; branch {run.branch} @ {head}"`; `completed_work` = `partial_output.result` split into bullet lines + each finding summary; `modified_files` = `git.diff_names(worktree, base=<branch base sha>)`; `findings` = `partial_output.findings`; `hypotheses/risks/remaining_work/next_action` from `partial_output.handover` when present, else `remaining_work = [n.description for n in partial_output.next_actions]`, `next_action = remaining_work[0]` or `"Continue the task from the current worktree state"`; `decisions = []`, `proposed_decisions = partial_output.decisions`; `worktree_head = git.head(worktree)`, `branch = run.branch`, `from_run_id = run.id`, `from_model_id = run.model_id`, `reason` as given. With `partial_output=None` all lists are empty and `next_action` is the default sentence.
8. `BoundaryAuditor.audit` returns, in input order, every changed file that is outside `worktree_path` (after `Path.resolve`), or matches any `forbidden_paths` glob, or matches no `allowed_paths` glob; matching uses `PurePosixPath.match` on worktree-relative forward-slash paths plus `**` semantics (`fnmatch` on the full relative path). Exception: files under `.ai/features/**/evidence/`, `.ai/bugs/**/evidence/`, `.ai/phases/**/evidence/` are allowed even though `.ai/**` is forbidden (ADR-0006 D-5 "except evidence folders").
9. `audit` is pure (no git, no I/O beyond path resolution).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `AgentRunState`/`CheckpointKind` members are enumerated, Then the DOMAIN-MODEL §3 lists; `Checkpoint` is frozen; `runtime.models.AgentOutputStatus is agents.models.AgentOutputStatus` | `tests/runtime/test_models.py::test_runtime_enums_and_relocated_status` |
| 2 | When a run is inserted and `set_state(COMPLETED)`, Then `ended_at` set and `by_state([COMPLETED])` returns it; unknown id → `RunNotFound` | `tests/runtime/test_repository.py::test_run_repository_state_updates` |
| 3 | Given runs owned by instance A and B in RUNNING, When `by_state([RUNNING], kernel_instance_not="B")`, Then only A's | `tests/runtime/test_repository.py::test_by_state_excludes_current_instance` |
| 4 | When a checkpoint row is UPDATEd directly, Then `sqlite3.IntegrityError`; `next_seq` increments | `tests/runtime/test_repository.py::test_checkpoints_immutable_and_sequenced` |
| 5 | Given two handovers for an item (one closed), When `latest_open`, Then the open one; `close` sets `to_run_id` | `tests/runtime/test_repository.py::test_handover_latest_open_and_close` |
| 6 | Given `tmp_game_repo` and a story, When `SandboxManager.create`, Then worktree at `.walk/worktrees/<run>` on branch `feat/story-0001-…`, guard hooks installed, path absolute | `tests/runtime/test_sandbox.py::test_create_worktree_with_branch_and_hooks` |
| 7 | When `create` twice for the same item (two runs), Then one branch, two worktrees | `tests/runtime/test_sandbox.py::test_create_reuses_branch_across_runs` |
| 8 | When `remove(run)`, Then worktree gone and branch kept; `remove(keep_branch=False)` deletes a non-protected branch | `tests/runtime/test_sandbox.py::test_remove_keeps_or_deletes_branch` |
| 9 | Given a dirty worktree, When `checkpoint(run, PERIODIC)`, Then WIP commit `wip(STORY-0001): checkpoint 1` with trailer, `head_sha` = new HEAD, `checkpoints` row seq 1, `CHECKPOINT_CREATED`, `ON_AGENT_CHECKPOINT` fired after commit | `tests/runtime/test_checkpoints.py::test_checkpoint_makes_wip_commit_and_records` |
| 10 | Given a clean worktree, Then no commit, `wip_commit_sha is None`, row still written | `tests/runtime/test_checkpoints.py::test_checkpoint_on_clean_worktree` |
| 11 | When `checkpoint(run, HANDOFF, handover=h)`, Then `handovers` row, `.ai/handovers/HO-0001.md` exists with §22 sections, `HANDOVER_CREATED` written once, `run.handover_out_id` set | `tests/runtime/test_checkpoints.py::test_checkpoint_with_handover_writes_document` |
| 12 | Given the ledger fails on `CHECKPOINT_CREATED`, Then no checkpoint row (commit on git may exist; replay-safe via idempotency key) | `tests/runtime/test_checkpoints.py::test_checkpoint_row_and_ledger_are_atomic` |
| 13 | Given a `PARTIAL` output with findings and next actions, When `build_handover(run, "FALLBACK", output)`, Then fields populated from output + `git diff --name-only`, `next_action` = first next action, no transcript text | `tests/runtime/test_checkpoints.py::test_build_handover_from_output_and_git` |
| 14 | When `build_handover(run, "RECOVERY", None)`, Then empty lists and the default `next_action` | `tests/runtime/test_checkpoints.py::test_build_handover_without_output` |
| 15 | Given changed files `src/A.cs`, `.ai/agents/roles/qc.md`, `../outside.txt`, `.ai/features/FEAT-0001/evidence/log.txt`, `secrets.env`, When `audit` with defaults, Then violations `[".ai/agents/roles/qc.md", "../outside.txt", "secrets.env"]` | `tests/runtime/test_boundary.py::test_audit_flags_forbidden_and_outside_paths` |
| 16 | Given `allowed_paths=["Assets/**"]` and a change in `Packages/x.json`, Then flagged | `tests/runtime/test_boundary.py::test_audit_enforces_allowed_paths` |
| 17 | When `FakeGitProvider` is used for `checkpoint`, Then calls recorded and injected `GitError` propagates | `tests/runtime/test_checkpoints.py::test_checkpoint_propagates_git_errors` |

#### Evidence required
- Quality gate output.
- Demo: after the checkpoint test, `git -C <tmp repo> log --oneline feat/story-0001-… | head -3` showing a `wip(STORY-0001): checkpoint 1` commit (paste from test output).

#### Notes
- ADR-0002 D-4/D-5/D-7; ADR-0006 D-5/D-6 (`BoundaryAuditor` forbids `.ai/agents/**`, `.ai/approved/**`); ADR-0009 D-5; ADR-0013 D-6; ARCHITECTURE §5.2, §6 (forbidden paths).
- Write-point note: ARCHITECTURE §4.3 lists `CHECKPOINT_CREATED` under `runtime.AgentExecutor`; it is written by `runtime.CheckpointManager` (same package) because the checkpoint row and the event must share a transaction. `HANDOVER_CREATED` is written by `MemoryManager.write_handover` (E01-S16) — not duplicated here.
- `NEW NAME:` `RunNotFound`, `CheckpointNotFound`, `AgentRunRepository.by_state/for_item/set_state`, `CheckpointRepository`, `HandoverRepository.latest_open/close`, `WORKTREES_DIR`, `branch_name_for`, `DefaultCheckpointManager.latest_open_handover/latest_open_handover_doc/close_handover`, `DEFAULT_FORBIDDEN_PATHS`, `DEFAULT_ALLOWED_PATHS`, `FakeGitProvider`; `checkpoint()` optional kwargs `budget_consumed`, `context_manifest`.
- Pitfall: `Checkpoint.workflow_state` is not on `AgentRun`; the executor passes it via the `workflow_state` kwarg — add it to the optional kwargs of `checkpoint()` and default to `IMPLEMENTING`? No: default is `ConfigError` when absent and `kind != START`; keep callers explicit.
- Commit subject: `feat: add agent run persistence, worktree sandbox, checkpoints and boundary audit (E01-S25)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S26 — `ToolInvoker`: permission enforcement point, Claude `can_use_tool` bridge, Codex sandbox config

**Status:** TODO
**Type:** feat
**Requirements:** §30, §31, §32 (`on_tool_*`), §81 (tool invocation), §91, §92, §137 (Inv. 7, 9)
**Depends on:** E01-S15, E01-S25, E01-S07, E01-S12
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
Every tool call an agent makes is decided by the kernel at one enforcement point: provider-native calls are authorised through the `RunSession.permission_authorizer` (Claude `can_use_tool` → `ToolInvoker.authorize`), kernel tools are dispatched only after authorisation and metering, `REQUIRE_APPROVAL` pauses the run until a decision or timeout, and Codex runs receive a policy-derived sandbox configuration.

#### Scope
- In: `DefaultToolInvoker.authorize/invoke/record_result/authorizer_for`, kernel-tool handler registry, `ApprovalWaiter` protocol + polling default, run pausing on approval, `CodexAdapter.configure_sandbox`, `ON_TOOL_BEFORE/AFTER/DENIED` firing, `TOOL_INVOKED`/`TOOL_DENIED` ledger writes, `TOOL_CALLS` metering.
- Out: event-driven `ApprovalWaiter` registry, expiry sweeps and `walk approve/deny` CLI (E02-S11), kernel tool handlers for jira/git/unity (E03-S03/S08/S11 — none registered here), default rule set data (E02-S10), scrubbed env (E02-S01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/tool_invoker.py` | create | `DefaultToolInvoker`, `KernelToolHandler`, `ApprovalWaiter`, `PollingApprovalWaiter`, `APPROVAL_TIMEOUT_S` |
| `src/walk/runtime/__init__.py` | modify | re-exports |
| `src/walk/model_router/adapters/codex/adapter.py` | modify | `CodexAdapter.configure_sandbox` |
| `src/walk/model_router/adapters/codex/sandbox.py` | modify | `sandbox_for_session` |
| `tests/runtime/test_tool_invoker.py` | create | — |
| `tests/runtime/test_approval_wait.py` | create | — |
| `tests/model_router/adapters/codex/test_sandbox.py` | create | — |

#### Interface contract
Protocol: INTERFACES.md §1.13 `ToolInvoker`. Deltas:
```python
KernelToolHandler = Callable[[ToolCallRequest], Awaitable[JsonDict]]
APPROVAL_TIMEOUT_S = 24 * 3600  # ADR-0006 D-4 default


class ApprovalWaiter(Protocol):
    async def wait(
        self, approval_id: ApprovalRequestId, *, timeout_s: int
    ) -> bool: ...  # True = approved; False = denied or expired


class PollingApprovalWaiter:
    def __init__(
        self,
        approvals: ApprovalRepository,
        clock: Clock,
        *,
        sleep: Callable[[float], Awaitable[None]],
        interval_s: float = 1.0,
    ) -> (
        None
    ): ...  # E02-S11 replaces with an event-based waiter; on timeout marks the request EXPIRED


class DefaultToolInvoker:
    def __init__(
        self,
        permissions: PermissionManager,
        tools: ToolRegistry,
        budgets: BudgetManager,
        hooks: HookManager,
        ledger: LedgerManager,
        runs: AgentRunRepository,
        checkpoints: CheckpointManager,
        waiter: ApprovalWaiter,
        clock: Clock,
        *,
        handlers: dict[ToolName, KernelToolHandler] | None = None,
        approval_timeout_s: int = APPROVAL_TIMEOUT_S,
        project_key: ProjectKey,
    ) -> None: ...
    def register_handler(
        self, tool: ToolName, handler: KernelToolHandler
    ) -> None: ...  # duplicate → ConfigError
    def authorizer_for(
        self, run: AgentRun
    ) -> Callable[
        [ToolCallRequest], Awaitable[PermissionDecision]
    ]: ...  # binds run for RunSession.permission_authorizer
    async def authorize(self, request: ToolCallRequest) -> PermissionDecision: ...
    async def invoke(self, request: ToolCallRequest) -> JsonDict: ...
    async def record_result(
        self, request: ToolCallRequest, result: JsonDict, *, duration_ms: int
    ) -> (
        None
    ): ...  # post event for PROVIDER_NATIVE tools (called by the executor on TOOL_CALL_RESULT)


# adapters/codex
def sandbox_for_session(
    session: RunSession, *, network_enabled: bool = False, extra_writable: list[str] = ()
) -> CodexSandboxConfig: ...


class CodexAdapter:
    def configure_sandbox(
        self, session: RunSession
    ) -> (
        CodexSandboxConfig
    ): ...  # workspace-write, cwd = session.worktree_path, network off, no extra roots in MVP
```

#### Behavior
1. `authorize(request)`: `decision = permissions.decide(request)`; the request's `tool` is first normalised via `ToolRegistry.identify(request.command)` when `tool == "bash"` and a CLI sub-tool matches (so `git push --force` is evaluated as `git-cli`); then:
   - `ALLOW` → fire `ON_TOOL_BEFORE` (payload: tool, command, paths), write `TOOL_INVOKED` with `outcome="OK"`, `payload={"phase": "pre", "matched_rule": …}`; return.
   - `DENY` → write `TOOL_DENIED` (`outcome="DENIED"`, reason, matched rule), fire `ON_TOOL_DENIED`; return.
   - `REQUIRE_APPROVAL` → `approval = permissions.request_approval(request, kind="TOOL_CALL" | "PROTECTED_ACTION" (when the tool has a `protected_action`), approver=decision.matched_rule.approver or USER, requested_by=request.role, run_id, work_item_id)`; set run `PAUSED_FOR_APPROVAL`; `checkpoints.checkpoint(run, PAUSE)`; `approved = await waiter.wait(approval.id, timeout_s)`; set run `RUNNING`; approved → treated as `ALLOW` (rule above, payload includes `approval_request_id`), else `DENY("approval denied or expired")`.
2. `invoke(request)` is for `kind == KERNEL` only (others → `ConfigError`): `decision = await authorize(request)`; `DENY` → raise `PermissionDenied(decision.reason)`; else `budgets.meter(BudgetSubject(project_key, phase_id=None, role=request.role, work_item_id, run_id), TOOL_CALLS, 1)` — `EXHAUSTED` → raise `BudgetExhausted` (the executor turns it into `BLOCKED_BUDGET`); dispatch to the registered handler (`ConfigError("no kernel handler for <tool>")` when absent); on return write `TOOL_INVOKED` (`phase="post"`, `duration_ms`, `outcome="OK"`), fire `ON_TOOL_AFTER`; on handler exception write `TOOL_INVOKED` with `outcome="FAILED"` and re-raise (converted to `ToolCrashed` when not already a `WalkError`).
3. `record_result(request, result, duration_ms)` writes the `phase="post"` `TOOL_INVOKED` event (`outcome` from `result.get("ok", True)`), meters `TOOL_CALLS` by 1 on the run's subject, and fires `ON_TOOL_AFTER` with payload `{tool, paths, ok}` — the hook table's default `ON_CODE_CHANGED` attachment is E04-S04.
4. `authorizer_for(run)` returns a coroutine function that fills `request.run_id`/`role`/`worktree_path` from the run when the adapter left them empty and delegates to `authorize`; the returned callable is what `RunSession.permission_authorizer` carries.
5. `PollingApprovalWaiter.wait` polls `ApprovalRepository.get(id)` every `interval_s` using the injected `sleep`; returns on `APPROVED`/`DENIED`; after `timeout_s` sets the row to `EXPIRED` (via `PermissionManager.decide_approval(..., approve=False, by="kernel", note="timeout")`) and returns `False`.
6. `configure_sandbox(session)` = `sandbox_for_session(session)` with `network_enabled=False` always in E01 (ADR-0006 D-5 keys network on `ToolSpec.requires_network`, which DOMAIN-MODEL does not define — see Notes); `CodexAdapter.run` uses `configure_sandbox` as its default `sandbox_factory`.
7. Ledger write discipline: `APPROVAL_REQUESTED`/`APPROVAL_DECIDED` are written by `PermissionManager` (E01-S15); the invoker never duplicates them (WBS §3.5).
8. All ledger events written here carry `run_id`, `work_item_id`, `tool`, `actor_role=request.role`.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given rules allowing `edit` for SENIOR_DEV, When `authorize(edit request inside worktree)`, Then `ALLOW`, `ON_TOOL_BEFORE` fired, `TOOL_INVOKED(phase=pre)` written | `tests/runtime/test_tool_invoker.py::test_authorize_allow_fires_hook_and_logs` |
| 2 | Given no rule for `write` for QC, Then `DENY`, `TOOL_DENIED` written, `ON_TOOL_DENIED` fired | `tests/runtime/test_tool_invoker.py::test_authorize_deny_logs_and_fires` |
| 3 | Given `bash` with command `git push --force` and a DENY pattern on `git-cli`, Then the request is evaluated as `git-cli` and denied | `tests/runtime/test_tool_invoker.py::test_authorize_identifies_cli_subtool` |
| 4 | Given `git.merge_protected` (protected action) and a waiter approving, When `authorize`, Then run went `PAUSED_FOR_APPROVAL` → `RUNNING`, a `PAUSE` checkpoint exists, `APPROVAL_REQUESTED` once, final decision `ALLOW` with `approval_request_id` | `tests/runtime/test_tool_invoker.py::test_require_approval_pauses_then_allows` |
| 5 | Given the waiter returns False, Then `DENY` with reason containing `denied or expired` and `TOOL_DENIED` written | `tests/runtime/test_tool_invoker.py::test_require_approval_denied` |
| 6 | Given a KERNEL tool with a registered handler, When `invoke`, Then handler called once, `TOOL_CALLS` metered by 1, `TOOL_INVOKED(phase=post)` with `duration_ms`, `ON_TOOL_AFTER` fired | `tests/runtime/test_tool_invoker.py::test_invoke_dispatches_meters_and_logs` |
| 7 | Given a KERNEL tool denied, When `invoke`, Then `PermissionDenied` and handler not called | `tests/runtime/test_tool_invoker.py::test_invoke_denied_raises_without_dispatch` |
| 8 | Given TOOL_CALLS budget exhausted, When `invoke`, Then `BudgetExhausted` and handler not called | `tests/runtime/test_tool_invoker.py::test_invoke_budget_exhausted_raises` |
| 9 | Given a handler raising `RuntimeError`, Then `TOOL_INVOKED(outcome=FAILED)` and `ToolCrashed` | `tests/runtime/test_tool_invoker.py::test_invoke_handler_failure_logged_and_wrapped` |
| 10 | When `invoke` with a PROVIDER_NATIVE request or an unregistered KERNEL tool, Then `ConfigError` | `tests/runtime/test_tool_invoker.py::test_invoke_rejects_non_kernel_or_unhandled` |
| 11 | When `record_result(edit request, {"ok": true}, 42)`, Then `TOOL_INVOKED(phase=post, duration_ms=42)`, `TOOL_CALLS` metered, `ON_TOOL_AFTER` fired | `tests/runtime/test_tool_invoker.py::test_record_result_posts_event_and_meters` |
| 12 | When `authorizer_for(run)` is called with a request lacking `run_id`, Then the decision was evaluated for `run.id`/`run.role` | `tests/runtime/test_tool_invoker.py::test_authorizer_for_binds_run` |
| 13 | Given a PENDING approval that becomes APPROVED after two polls, When `PollingApprovalWaiter.wait`, Then `True` after two sleeps | `tests/runtime/test_approval_wait.py::test_polling_waiter_returns_on_decision` |
| 14 | Given no decision within `timeout_s`, Then `False`, request `EXPIRED`, `APPROVAL_DECIDED` written with note `timeout` | `tests/runtime/test_approval_wait.py::test_polling_waiter_times_out_and_expires` |
| 15 | When `configure_sandbox(session)`, Then `mode == "workspace-write"`, `cwd == worktree`, `network_enabled is False`, `writable_roots == []`; `build_exec_command` reflects it | `tests/model_router/adapters/codex/test_sandbox.py::test_configure_sandbox_defaults` |

#### Evidence required
- Quality gate output.
- Demo: transcript from `tests/runtime/test_tool_invoker.py::test_require_approval_pauses_then_allows` showing the `walk ledger query --run <id>` style event sequence (`APPROVAL_REQUESTED`, `CHECKPOINT_CREATED(PAUSE)`, `APPROVAL_DECIDED`, `TOOL_INVOKED`).

#### Notes
- ADR-0006 D-1 (enforcement points 1–3), D-3, D-4, D-5, D-7; ARCHITECTURE §4.1 (`ON_TOOL_*`, `ON_PROTECTED_ACTION_REQUESTED` fired by `PermissionManager.request_approval`), §4.2, §4.3 (`TOOL_INVOKED`, `TOOL_DENIED` write point).
- `NEW NAME:` `KernelToolHandler`, `ApprovalWaiter`, `PollingApprovalWaiter`, `APPROVAL_TIMEOUT_S`, `DefaultToolInvoker.register_handler/authorizer_for/record_result`, `sandbox_for_session`, `CodexAdapter.configure_sandbox` (named in ADR-0006/ARCHITECTURE §4.2 but absent from INTERFACES §2.1).
- Doc inconsistency to report: ADR-0006 D-5 conditions Codex network access on `ToolSpec.requires_network`, a field DOMAIN-MODEL §4.6 does not define. E01 keeps network off unconditionally; the architect should add the field or drop the clause.
- Pitfall: `authorize` is awaited from inside the adapter's event stream (Claude callback). It must not call back into the adapter and must tolerate being awaited concurrently for different runs; keep per-run state on `AgentRun`, not on the invoker.
- Commit subject: `feat: add tool invoker enforcement point with approval pausing and codex sandbox config (E01-S26)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S27 — `AgentExecutor` event loop, output validation/repair, `OutputApplier` core

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §9, §22, §40, §41, §54, §81, §84, §86, §89, §91 (repository boundary), §126, §137 (Inv. 1, 2, 9, 12), §138 (Hallucinated Project State)
**Depends on:** E01-S26, E01-S20, E01-S24, E01-S06
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`DefaultAgentExecutor.start` runs one `AgentRun` end-to-end as an asyncio task: worktree, `ContextBundle`, `AgentInput` and `RunSession` assembly, start ledger events, consumption of the adapter event stream (tool results recorded, usage metered into cost records, periodic and hinted checkpoints with a boundary audit before every WIP commit), validation of the final `AgentOutput` with one repair turn, and the `OutputApplier` core that writes context updates and evidence and raises the IMPLEMENT workflow event.

#### Scope
- In: `DefaultAgentExecutor.start/cancel/pause/running/wait`, `AgentInputBuilder`, `build_run_session`, `expected_output_for`, `UsageMeter`, `DefaultOutputApplier.apply` (context updates, evidence, IMPLEMENT event for STORY/TASK), boundary audit before WIP commits and at run end, `AGENT_ASSIGNED`/`AGENT_RUN_STARTED`/`MODEL_SELECTED`/`EFFORT_SET`/`AGENT_RUN_ENDED`/`RETRY`/`ERROR` write points, `ON_AGENT_START`/`ON_AGENT_END`/`ON_TASK_FAILED` firing, `WorkflowRepository.set_assigned_run`.
- Out: retries with backoff, fallback, handover-on-fallback, `resume_native` and startup recovery (E01-S28 — `resume_native` raises `ConfigError("implemented in E01-S28")` here and every `ERROR` ends the run `FAILED`); scheduling (E01-S29); `new_tasks`/`new_bugs`, change reconciliation, final kernel commit and the YAML output-event table (E03-S08); PARTIAL-specific handover and `ON_AGENT_END` context repair (E04-S07); scrubbed env contents (E02-S01 — an injected provider returning `{}` here); MUST builtin hooks (E02-S08).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/runtime/executor.py` | create | `DefaultAgentExecutor`, `MAX_REPAIR_TURNS`, `REPAIR_INSTRUCTION`, `RUN_TIMEOUT_S` |
| `src/walk/runtime/inputs.py` | create | `AgentInputBuilder`, `build_run_session`, `expected_output_for` |
| `src/walk/runtime/metering.py` | create | `UsageMeter` |
| `src/walk/runtime/output_applier.py` | create | `DefaultOutputApplier`, `IMPLEMENT_OUTPUT_EVENTS` |
| `src/walk/runtime/__init__.py` | modify | re-exports |
| `src/walk/workflow/repository.py` | modify | `WorkflowRepository.set_assigned_run` |
| `tests/runtime/test_executor.py` | create | — |
| `tests/runtime/test_executor_repair.py` | create | — |
| `tests/runtime/test_executor_boundary.py` | create | — |
| `tests/runtime/test_inputs.py` | create | — |
| `tests/runtime/test_metering.py` | create | — |
| `tests/runtime/test_output_applier.py` | create | — |
| `tests/workflow/test_repository.py` | modify | — |

#### Interface contract
Protocols: INTERFACES.md §1.13 `AgentExecutor`, `OutputApplier`, `AppliedEffects`; §2.1 `RunSession`. Deltas:
```python
MAX_REPAIR_TURNS = 1  # ARCHITECTURE §5.5
RUN_TIMEOUT_S = 2700  # used when the resolved FamilyLevel has no execution_time_s
REPAIR_INSTRUCTION = (
    "Your final output was rejected by the kernel:\n{errors}\n"
    "Write a corrected AgentOutput JSON object to .walk/output.json and finish."
)
IMPLEMENT_OUTPUT_EVENTS: dict[AgentOutputStatus, str] = {
    COMPLETED: "submit_for_review",
    PARTIAL: "partial",
    BLOCKED: "block",
    NEEDS_INPUT: "block",
}
# STORY/TASK + purpose IMPLEMENT only; FAILED → no event; E03-S08 replaces this constant with output_events.yaml


def expected_output_for(
    purpose: str, item: WorkItem
) -> ExpectedOutput: ...  # E01-S18 rule 8 status options; required_evidence from item.contract; deliverables [] in E01


class AgentInputBuilder:
    def __init__(
        self,
        agents: AgentManager,
        context: ContextManager,
        tools: ToolRegistry,
        budgets: BudgetManager,
        phases: PhaseRepository,
        clock: Clock,
        *,
        project_key: ProjectKey,
    ) -> None: ...
    async def build(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        run_id: RunId,
        worktree_path: str,
        branch: str,
        descriptor: ModelDescriptor,
        handover: Handover | None = None,
        debate: Debate | None = None,
    ) -> AgentInput: ...


def build_run_session(
    run: AgentRun,
    agent_input: AgentInput,
    authorizer: Callable[[ToolCallRequest], Awaitable[PermissionDecision]],
    *,
    max_turns: int,
    timeout_s: int,
    env_allowlist: dict[str, str],
) -> RunSession: ...  # output_path = <worktree>/OUTPUT_RELATIVE_PATH


class UsageMeter:
    def __init__(
        self,
        costs: CostManager,
        descriptor: ModelDescriptor,
        subject: BudgetSubject,
        clock: Clock,
        *,
        new_id: Callable[[], str],
    ) -> None: ...
    async def observe(
        self, cumulative: UsageReport
    ) -> (
        CostRecord | None
    ): ...  # meters only the delta since the last observe; None when no new tokens
    @property
    def total(self) -> UsageReport: ...


class DefaultOutputApplier:
    def __init__(
        self,
        memory: MemoryManager,
        evidence: EvidenceManager,
        workflow: WorkflowManager,
        git: GitProvider,
        clock: Clock,
    ) -> None: ...
    async def apply(
        self, run: AgentRun, output: AgentOutput, *, start_head: Sha
    ) -> AppliedEffects: ...  # `start_head` keyword is a delta to INTERFACES §1.13


class DefaultAgentExecutor:
    def __init__(
        self,
        db: Database,
        runs: AgentRunRepository,
        items: WorkflowRepository,
        workflow: WorkflowManager,
        router: ModelRouter,
        inputs: AgentInputBuilder,
        sandbox: SandboxManager,
        checkpoints: DefaultCheckpointManager,
        tool_invoker: DefaultToolInvoker,
        auditor: BoundaryAuditor,
        applier: DefaultOutputApplier,
        git: GitProvider,
        budgets: BudgetManager,
        costs: CostManager,
        hooks: HookManager,
        ledger: LedgerManager,
        ids: IdFactory,
        clock: Clock,
        *,
        project_key: ProjectKey,
        kernel_instance: str,
        env_allowlist: Callable[[], dict[str, str]] = dict,
        on_run_finished: Callable[[AgentRun], Awaitable[None]] | None = None,
        allowed_paths: tuple[str, ...] = DEFAULT_ALLOWED_PATHS,
        forbidden_paths: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
    ) -> None: ...
    async def start(
        self,
        agent: AgentInstance,
        item: WorkItem,
        purpose: str,
        *,
        handover: Handover | None = None,
        parent_run_id: RunId | None = None,
        debate: Debate | None = None,
        routing: RoutingDecision | None = None,
        effort_resolution: EffortResolution | None = None,
    ) -> AgentRun: ...
    async def resume_native(
        self, checkpoint: Checkpoint
    ) -> AgentRun: ...  # ConfigError("implemented in E01-S28")
    async def cancel(self, run_id: RunId, reason: str) -> AgentRun: ...
    async def pause(self, run_id: RunId) -> AgentRun: ...
    def running(self) -> list[AgentRun]: ...
    async def wait(
        self, run_id: RunId
    ) -> AgentRun: ...  # awaits the run task; returns the persisted terminal run


# WorkflowRepository
async def set_assigned_run(
    self, work_item_id: WorkItemId, run_id: RunId | None, *, conn: sqlite3.Connection | None = None
) -> WorkItem: ...
```

#### Behavior
1. `start` precondition: the item has no non-terminal run (`assigned_run_id` set and that run in `PENDING|RUNNING|PAUSED_*`) → `ConfigError("work item <id> already has active run <run>")` (§60 one run per item). Unknown purpose (not in `TEMPLATE_PURPOSES`) → `ConfigError`.
2. Allocation, in one `UnitOfWork`: `RunId` from `ids` (`RUN-` prefix); insert `AgentRun(state=PENDING, model_id=agent.model_id, provider=router.adapter_for(agent.model_id).provider, effort=agent.effort, purpose, parent_run_id, handover_in_id=handover.id if handover else None, kernel_instance)`; `set_assigned_run(item.id, run.id)`; ledger `AGENT_ASSIGNED` (payload role, purpose).
3. Preparation: `worktree = sandbox.create(run, item)` (run row updated with `worktree_path`, `branch`); `descriptor = router.registry().models[run.model_id]`; `agent_input = inputs.build(...)` where the builder requests `ContextRequest(work_item_id, role, effort, token_budget=context.token_budget_for(effort, descriptor.context_window_tokens, descriptor.max_output_tokens))`, sets `allowed_tools = [tools.get(n) for n in agent.tools]`, `permissions = agent.permissions`, `budget = budgets.applicable(BudgetSubject(project_key, item.phase_id, role, item.id, run_id))`, `approved_artifacts = []`, `decisions = []` (filled by E04), `skills = []` (E02-S05 resolves `Skill` objects), `required_evidence = item.contract.required_evidence` (empty without contract), `expected_output = expected_output_for(purpose, item)`, `instructions_markdown = agents.render_instructions(agent, item, purpose)`, `handover` as given (rendered last by `render_input_sections`, E01-S18 rule 5). Any exception here → run `FAILED` with `failure_reason="prepare: <detail>"`, `ERROR` ledger, item unassigned, worktree kept for diagnosis.
4. `session = build_run_session(run, agent_input, tool_invoker.authorizer_for(run), max_turns=50, timeout_s=<FamilyLevel.execution_time_s or RUN_TIMEOUT_S>, env_allowlist=env_allowlist())`.
5. Start events, in one `UnitOfWork`: run → `RUNNING`, `started_at = clock.now()`; ledger `AGENT_RUN_STARTED` (payload purpose, branch, worktree, parent_run_id, handover_in_id, `context_item_ids`), `MODEL_SELECTED` (payload `reason`, `rejected`, `is_fallback`, `trigger` from `routing`; `{"reason": "direct"}` when `routing is None`), `EFFORT_SET` (payload effort, `degraded_from` from `adapter.map_effort(effort, model_id).params`, and the `effort_resolution` components when given). Every event carries `run_id`, `work_item_id`, `actor_role`, `model_id`, `effort`, and `behavior_versions["prompt:<purpose>"]`.
6. After commit: fire `ON_AGENT_START` (payload `context_doc_ids` = memory-backed item ids of the bundle); `HookFailed` → run `FAILED_HOOK`, item unassigned, no adapter call. Then `checkpoints.checkpoint(run, START, workflow_state=item.state, context_manifest=bundle.ref())`; its `head_sha` is the run's `start_head`. Then an `asyncio.Task` drives the stream and `start` returns the `RUNNING` run.
7. Event handling: `STARTED` → persist `run.provider_session`; `TEXT` → `logging.debug` only, never persisted; `TOOL_CALL_REQUESTED` → no action (authorisation happened through the session authorizer); `TOOL_CALL_RESULT` → `tool_invoker.record_result(request, result, duration_ms)` (KERNEL-kind results are already recorded by `invoke`), `run.tool_calls += 1`, and `tool_result["kernel_decision"] == "DENY"` (Codex advisory, E01-S22 rule 3) is remembered as a boundary violation; `CHECKPOINT_HINT` → checkpoint `AGENT_REQUESTED`; `USAGE` → `meter.observe(adapter.usage(run.id))` (event payload ignored; delta semantics make per-call and cumulative USAGE events equivalent); `PARTIAL_OUTPUT` → kept in memory as the run's latest partial output; `FINAL_OUTPUT` → rule 9; `ERROR` → rule 12; `ENDED` → loop ends.
8. Periodic checkpoints: after the tool call that makes `run.tool_calls % agent.runtime_policy.checkpoint_every_tool_calls == 0`, the executor audits `git.status(worktree)` with `auditor.audit(...)` **before** calling `checkpoints.checkpoint(run, PERIODIC, workflow_state, budget_consumed=<meter totals by dimension>, context_manifest)`; a violation ends the run per rule 11 without committing.
9. `FINAL_OUTPUT` validation: `output is None` (adapter could not parse, E01-S19 boundary rule) or `output.status ∉ expected_output.status_options` → invalid with `errors` = the event's `error` or `"status <s> not allowed for <purpose>"`. Invalid and `run.repair_turns < MAX_REPAIR_TURNS` and `run.provider_session.resumable` → `repair_turns += 1`, ledger `RETRY` (payload `reason="output_invalid"`, `errors`), the stream continues with `adapter.resume(run.provider_session, REPAIR_INSTRUCTION.format(errors=errors), session)`. Otherwise run `FAILED`, `failure_reason="output_invalid: <errors>"`.
10. Valid output: (a) final audit of `git.status(worktree) ∪ git.diff_names(worktree, base=start_head)` — violation or remembered advisory DENY → rule 11; (b) `checkpoints.checkpoint(run, END, ...)` (final WIP commit); (c) `run.output = output`; `effects = applier.apply(run, output, start_head=start_head)`; (d) run `COMPLETED`; (e) meter `EXECUTION_TIME_S` with the run's wall-clock seconds; (f) ledger `AGENT_RUN_ENDED` (`outcome="OK"`, payload status, tool_calls, repair_turns, `effects` as JSON, `deferred_intents = {"new_tasks": n, "new_bugs": m}`, `cost_usd` = meter total); (g) item unassigned; (h) fire `ON_AGENT_END` (payload `status`, `context_updates` count, `no_context_change_reason`, `checkpoint_id` of the END checkpoint); (i) `on_run_finished(run)`.
11. Boundary violation: `git.discard_changes(worktree)`, run `FAILED_BOUNDARY` with `failure_reason="boundary: <paths>"`, ledger `ERROR` (`outcome="FAILED"`, payload `kind="BOUNDARY"`, `violations`), item unassigned, `ON_TASK_FAILED` fired, output not applied, no workflow event.
12. `ERROR` events and exceptions raised by the adapter iterator: run `FAILED` with `failure_reason="error: <trigger or 'none'>: <message>"`, `adapter.cancel(run.id)`, ledger `ERROR` (payload `trigger` = event trigger or `router.classify_error(exc, adapter)`), item unassigned, `ON_TASK_FAILED` fired, `AGENT_RUN_ENDED` with `outcome="FAILED"`. E01-S28 replaces this rule with retry/fallback.
13. `BudgetExhausted` raised through the authorizer or after metering (any applicable budget with `hard_action=BLOCK` and zero headroom) → `adapter.cancel`, checkpoint `PAUSE`, run `BLOCKED_BUDGET`, ledger `ERROR` (payload `kind="BUDGET"`), item unassigned; no workflow event.
14. `cancel(run_id, reason)`: `adapter.cancel`, awaits the task, checkpoint `PAUSE`, run `CANCELLED`, `failure_reason=reason`, `sandbox.remove(run, keep_branch=True)`, item unassigned, `AGENT_RUN_ENDED` (`outcome="SKIPPED"`). `pause(run_id)`: `adapter.cancel`, checkpoint `PAUSE`, run `PAUSED_BY_USER`, worktree kept, item stays assigned. Unknown run → `RunNotFound`. `running()` returns runs whose task is not done.
15. `DefaultOutputApplier.apply`: (1) `context_updates` → `memory.apply_updates(updates, actor=Actor(role=run.role, model_id=run.model_id, run_id=run.id), head=git.head(worktree), branch=run.branch)` → `memory_docs`; (2) each `evidence` draft → relative `path_or_uri` resolved against the worktree; missing file → skipped with a `logging` warning; else `evidence.record(draft, actor, work_item_id=item.id, phase_id=item.phase_id, commit=head)` → `evidence_ids`; (3) `decisions`, `escalations`, `new_tasks`, `new_bugs` are left on `run.output` (`decision_ids = []`, `escalation_ids = []`, `created_work_items = []`); (4) `commit_sha = head if head != start_head else None`; (5) `event = IMPLEMENT_OUTPUT_EVENTS.get(status)` when `item.kind in (STORY, TASK)` and `run.purpose == "IMPLEMENT"`, else `None`; when set, `workflow.raise_event(item.id, event, TransitionContext(actor_role=run.role, source=AGENT, run_id=run.id, payload={output_status, has_commit: commit_sha is not None, evidence_kinds_present: kinds of evidence.for_item(item.id), handover_present: output.handover is not None, escalations_non_empty}, phase=None))`; (6) `GuardRejected` → re-raised as `GuardRejected`; the executor ends the run `FAILED` with `failure_reason="guard_rejected: <reason>"`, ledger `ERROR`, `ON_TASK_FAILED` (E03-S08 replaces with the `block` path).
16. `UsageMeter.observe` computes the delta of `input_tokens`, `output_tokens`, `cache_read_tokens` against the previous cumulative report, builds `usage_to_cost_record(delta, descriptor, subject, record_id=new_id(), at=clock.now())` and calls `costs.record(...)` (which writes `COST_RECORDED` and meters `COST_USD`/`TOKENS`); a cumulative report lower than the previous one → `ConfigError` (adapter defect).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given a STORY in IMPLEMENTING and a 3-call COMPLETED fake script, When `start` then `wait`, Then run `COMPLETED`, ledger kinds in order `AGENT_ASSIGNED, AGENT_RUN_STARTED, MODEL_SELECTED, EFFORT_SET, CHECKPOINT_CREATED(START)… AGENT_RUN_ENDED`, `ON_AGENT_START` and `ON_AGENT_END` fired once | `tests/runtime/test_executor.py::test_start_runs_to_completion_with_ledger_sequence` |
| 2 | Given an item whose `assigned_run_id` is a RUNNING run, When `start`, Then `ConfigError` and no new run row | `tests/runtime/test_executor.py::test_start_rejects_second_active_run` |
| 3 | Given a 12-call script and `checkpoint_every_tool_calls=5`, Then checkpoints `START, PERIODIC, PERIODIC, END` with seq 1–4 and two WIP commits before the END one | `tests/runtime/test_executor.py::test_periodic_checkpoints_every_n_tool_calls` |
| 4 | Given `checkpoint_hint_at=[2]`, Then an `AGENT_REQUESTED` checkpoint after the second tool call | `tests/runtime/test_executor.py::test_checkpoint_hint_creates_agent_requested_checkpoint` |
| 5 | Given three provider-native tool results, Then `TOOL_INVOKED(phase=post)` three times and `run.tool_calls == 3` | `tests/runtime/test_executor.py::test_tool_results_recorded_and_counted` |
| 6 | Given a script with `TEXT` events, Then no ledger event, checkpoint or run field contains their text | `tests/runtime/test_executor.py::test_text_events_never_persisted` |
| 7 | When `start`, Then `RunSession.worktree_path` is the sandbox path, `output_path` ends with `.walk/output.json`, `allowed_tools` equals the instance tools and `permission_authorizer` evaluates for the run | `tests/runtime/test_inputs.py::test_build_run_session_fields` |
| 8 | Given a story with contract and a handover, When `AgentInputBuilder.build`, Then every §126 field present, `expected_output.status_options` for IMPLEMENT, `required_evidence` from contract, `handover` set, context token budget from the descriptor | `tests/runtime/test_inputs.py::test_agent_input_builder_populates_contract` |
| 9 | Given `invalid_output_times=1`, Then one `RETRY` ledger with `reason=output_invalid`, `repair_turns == 1`, run `COMPLETED` | `tests/runtime/test_executor_repair.py::test_invalid_output_repaired_once` |
| 10 | Given `invalid_output_times=2`, Then run `FAILED` with `failure_reason` starting `output_invalid` | `tests/runtime/test_executor_repair.py::test_invalid_output_twice_fails` |
| 11 | Given a REVIEW run whose output status is `COMPLETED`, Then treated as invalid (`status COMPLETED not allowed for REVIEW`) and repaired | `tests/runtime/test_executor_repair.py::test_status_outside_expected_options_is_invalid` |
| 12 | Given a non-resumable session and an invalid output, Then no repair turn and run `FAILED` | `tests/runtime/test_executor_repair.py::test_no_repair_when_session_not_resumable` |
| 13 | Given a scripted write to `.ai/agents/roles/qc.md` before the first periodic checkpoint, Then run `FAILED_BOUNDARY`, no WIP commit contains the file, worktree clean, `ERROR(kind=BOUNDARY)` | `tests/runtime/test_executor_boundary.py::test_violation_detected_before_wip_commit` |
| 14 | Given a Codex-style `TOOL_CALL_RESULT` with `kernel_decision == "DENY"`, Then the run ends `FAILED_BOUNDARY` and the output is not applied | `tests/runtime/test_executor_boundary.py::test_advisory_deny_fails_run` |
| 15 | Given a scripted `ERROR(trigger=PROVIDER_OUTAGE)` after 3 calls, Then run `FAILED`, `ERROR` ledger with trigger, `ON_TASK_FAILED` fired, item unassigned | `tests/runtime/test_executor.py::test_error_event_fails_run_until_fallback_lands` |
| 16 | Given a TOOL_CALLS budget exhausted mid-run, Then run `BLOCKED_BUDGET`, a `PAUSE` checkpoint, no workflow event | `tests/runtime/test_executor.py::test_budget_exhausted_blocks_run` |
| 17 | When `cancel(run, "user")` mid-stream, Then run `CANCELLED`, `PAUSE` checkpoint, worktree removed, branch kept; `pause` → `PAUSED_BY_USER` with worktree kept | `tests/runtime/test_executor.py::test_cancel_and_pause` |
| 18 | When `resume_native(ckpt)`, Then `ConfigError` mentioning E01-S28 | `tests/runtime/test_executor.py::test_resume_native_deferred` |
| 19 | Given per-call USAGE events followed by a cumulative USAGE, Then the sum of `COST_RECORDED` tokens equals `adapter.usage(run).input+output` exactly | `tests/runtime/test_metering.py::test_usage_meter_records_deltas_only` |
| 20 | Given a cumulative report lower than the previous, Then `ConfigError` | `tests/runtime/test_metering.py::test_usage_meter_rejects_decreasing_totals` |
| 21 | Given a COMPLETED IMPLEMENT output with one context update and one AUTOMATED_TEST evidence on a story requiring it, When `apply`, Then memory doc written, `EVD-` id returned, story `READY_FOR_REVIEW`, `workflow_event == "submit_for_review"`, `commit_sha` set | `tests/runtime/test_output_applier.py::test_apply_completed_implement_submits_for_review` |
| 22 | Given an evidence draft pointing at a missing file, Then it is skipped and the other effects still apply | `tests/runtime/test_output_applier.py::test_missing_evidence_file_skipped` |
| 23 | Given a COMPLETED output with no commits since `start_head`, When `apply`, Then `GuardRejected` (has_commit) and the executor ends the run `FAILED` with `guard_rejected` | `tests/runtime/test_output_applier.py::test_guard_rejection_fails_run` |
| 24 | Given a REVIEW run or a FEATURE item, When `apply`, Then `workflow_event is None` and `new_tasks` are left untouched | `tests/runtime/test_output_applier.py::test_non_implement_runs_raise_no_event` |
| 25 | When `set_assigned_run(id, run)` then `set_assigned_run(id, None)`, Then `assigned_run_id` set then cleared and `ready_items` excludes then includes the item | `tests/workflow/test_repository.py::test_set_assigned_run_round_trip` |

#### Evidence required
- Quality gate output.
- Demo: from `tests/runtime/test_executor.py::test_periodic_checkpoints_every_n_tool_calls` paste `walk ledger query --run <RUN id>` output (or the equivalent `LedgerManager.query` dump) and `git -C <tmp repo> log --oneline <branch>` showing three `wip(STORY-0001): checkpoint n` commits.

#### Notes
- ARCHITECTURE §3.2 steps 3–7, §4.1 (`ON_AGENT_START`, `ON_AGENT_END`, `ON_TASK_FAILED`), §4.3 (`runtime.AgentExecutor` write point), §5.2, §5.5; ADR-0002 D-4/D-9; ADR-0004 D-2/D-3/D-6; ADR-0006 D-2/D-5; ADR-0011 D-4/D-6; INTERFACES §1.13, §2.1.
- `NEW NAME:` `walk.runtime.executor` (`MAX_REPAIR_TURNS`, `REPAIR_INSTRUCTION`, `RUN_TIMEOUT_S`, `DefaultAgentExecutor.wait`, constructor callbacks `env_allowlist`, `on_run_finished`), `walk.runtime.inputs` (`AgentInputBuilder`, `build_run_session`, `expected_output_for`), `walk.runtime.metering.UsageMeter`, `walk.runtime.output_applier` (`DefaultOutputApplier`, `IMPLEMENT_OUTPUT_EVENTS`), `WorkflowRepository.set_assigned_run`; protocol deltas: `AgentExecutor.start` keywords `routing`, `effort_resolution` (needed because ARCHITECTURE §4.3 makes the executor the `MODEL_SELECTED`/`EFFORT_SET` write point while the scheduler holds the decision) and `OutputApplier.apply` keyword `start_head` — update INTERFACES §1.13 in this commit.
- `expected_output_for` duplicates the purpose → status table of E01-S18 rule 8 (private there). `runtime` may not import `agents.service`, so the duplication is accepted in E01; E01-R01 checks that both tables agree.
- Cross-epic coordination (non-blocking): E02-S08 registers `builtin.final_checkpoint` (`ON_AGENT_END` → `checkpoint(END)`), which would duplicate the END checkpoint made here in Behavior 10(b). The `ON_AGENT_END` payload carries `checkpoint_id`; E02-S08's hook must be a no-op when it is present. E04-S07 refers to `src/walk/runtime/applier.py`; the file is `output_applier.py` (E03-S08 uses this name).
- Pitfall: the drive task must catch every exception and leave the run in a terminal state; an unhandled exception in an `asyncio.Task` is otherwise lost. Use one `UnitOfWork` per state change; never hold a transaction across an `await` on the adapter stream.
- Pitfall: `run.tool_calls` is persisted after every result so that a crash between checkpoints loses at most the counter delta, not the checkpoint sequence.
- Commit subject: `feat: add agent executor event loop, output repair and applier core (E01-S27)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S28 — Fallback, handover and recovery

**Status:** TODO
**Type:** feat
**Requirements:** §21, §22, §41, §89, §90, §128, §132 (path exercised with fakes), §137 (Inv. 1, 12), §138 (Model Lock-In, Tool Failure)
**Depends on:** E01-S27
**Effort:** HIGH   **Risk:** HIGH
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
A run that hits a transient provider error is retried with backoff; a run whose error maps to a §21 trigger checkpoints, writes a structured handover and continues on another model in the same worktree (bounded by `max_fallbacks_per_run`); a crashed kernel's orphaned runs are resumed at startup, natively when the provider session is resumable and healthy, otherwise from the handover on a routed model.

#### Scope
- In: `DefaultModelRouter.fallback` (INTERFACES §5.3 steps 7–9) via `FallbackRequest`; executor retry with backoff, fallback steps 5, 6, 10, `BLOCKED_PROVIDER` + user escalation; `DefaultAgentExecutor.resume_native`; worktree adoption for child runs (`SandboxManager.adopt`); `RecoveryManager.recover` (ARCHITECTURE §5.3 steps 1–6); `MODEL_FALLBACK`, `RETRY`, `RECOVERY_RESUMED`, `ERROR(kind=INTERRUPTED)` write points; `ON_MODEL_FALLBACK`, `ON_RECOVERY_RESUME` firing.
- Out: `ON_AGENT_HANDOFF` chaining and other MUST builtins (E02-S08); approval-waiter re-registration for `PAUSED_FOR_APPROVAL` runs (E02-S11 extends `RecoveryManager`); `IntegrationManager.reconcile` after recovery (ARCHITECTURE §5.3 step 7 — E03-S03); handover enrichment from context documents and decisions (E04-S06); PARTIAL/PAUSE/BUDGET handovers (E04-S07); calling `recover()` at startup (E01-S30).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/model_router/models.py` | modify | `FallbackRequest`, `MAX_FALLBACKS_PER_RUN` |
| `src/walk/model_router/protocols.py` | modify | `ModelRouter.fallback` (signature takes `FallbackRequest`) |
| `src/walk/model_router/service.py` | modify | `DefaultModelRouter.fallback`, `PROVIDER_WIDE_TRIGGERS` |
| `src/walk/model_router/__init__.py` | modify | re-exports |
| `src/walk/runtime/executor.py` | modify | `DefaultAgentExecutor.resume_native`, `RETRY_DELAYS_S`, `RESUME_INSTRUCTION` (constructor gains `agents`, `permissions`, `ready_env_keys`, `sleep`) |
| `src/walk/runtime/protocols.py` | modify | `SandboxManager.adopt` |
| `src/walk/runtime/sandbox.py` | modify | `DefaultSandboxManager.adopt` |
| `src/walk/runtime/recovery.py` | create | `RecoveryManager`, `RecoveryReport` |
| `src/walk/runtime/__init__.py` | modify | re-exports |
| `docs/01-architecture/INTERFACES.md` | modify | — (§1.4 `fallback` signature, §1.13 `SandboxManager.adopt`, §5.3 step ownership — already applied by the architect 2026-10-06; edit only if the implementation deviates) |
| `tests/model_router/test_fallback.py` | create | — |
| `tests/runtime/test_executor_retry.py` | create | — |
| `tests/runtime/test_executor_fallback.py` | create | — |
| `tests/runtime/test_resume_native.py` | create | — |
| `tests/runtime/test_recovery.py` | create | — |
| `tests/runtime/test_sandbox.py` | modify | — |

#### Interface contract
INTERFACES.md §1.4 `ModelRouter`, §1.13 `AgentExecutor.resume_native`, §5.3; ARCHITECTURE.md §5.1, §5.3, §5.5. Deltas:
```python
# walk.model_router.models
MAX_FALLBACKS_PER_RUN = 2                                   # ARCHITECTURE §5.5
class FallbackRequest(FrozenModel):
    role: AgentRole
    policy: ModelPolicy
    current_model_id: ModelId
    trigger: FallbackTrigger
    profile: TaskProfile
    effort: Effort
    fallbacks_so_far: int = Field(description="AgentRun.fallbacks of the failing run (chain count)")
    max_fallbacks: int = MAX_FALLBACKS_PER_RUN
    measured_context_tokens: int | None = None              # CONTEXT_OVERFLOW only
# walk.model_router.protocols / service
PROVIDER_WIDE_TRIGGERS: frozenset[FallbackTrigger] = frozenset({PROVIDER_OUTAGE, QUOTA_EXHAUSTED, RATE_LIMIT})
async def fallback(self, request: FallbackRequest) -> RoutingDecision: ...   # raises BlockedProvider
# walk.runtime
RETRY_DELAYS_S: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)       # ARCHITECTURE §5.1, max 5 attempts; the default `sleep` adds 0–10 % jitter, tests inject a recording fake
RESUME_INSTRUCTION = "Continue the task from the current worktree state. Write .walk/output.json when finished."
class SandboxManager(Protocol):
    async def adopt(self, run: AgentRun, previous: AgentRun, item: WorkItem) -> str: ...   # reuse previous.worktree_path; re-add it on the same branch when missing
class DefaultAgentExecutor:
    def __init__(self, ..., agents: AgentManager, permissions: PermissionManager, *, ready_env_keys: Callable[[], set[str]] = set,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, ...) -> None: ...   # E01-S27 constructor plus these
    async def resume_native(self, checkpoint: Checkpoint) -> AgentRun: ...
class RecoveryReport(FrozenModel):
    interrupted: list[RunId]
    resumed_native: list[RunId]                  # new run ids
    restarted_with_handover: list[RunId]         # new run ids
    requeued: list[WorkItemId]                   # no checkpoint → item unassigned for the scheduler
    failed: list[tuple[RunId, str]]
class RecoveryManager:
    def __init__(self, runs: AgentRunRepository, checkpoints: DefaultCheckpointManager, executor: DefaultAgentExecutor, router: ModelRouter,
                 agents: AgentManager, items: WorkflowRepository, hooks: HookManager, ledger: LedgerManager, clock: Clock, *,
                 kernel_instance: str, project_key: ProjectKey, ready_env_keys: Callable[[], set[str]] = set) -> None: ...
    async def recover(self) -> RecoveryReport: ...
```

#### Behavior
1. `DefaultModelRouter.fallback(request)`: (step 7) `fallbacks_so_far >= max_fallbacks` → `BlockedProvider([(current_model_id, "max_fallbacks")])`; (step 8) `exclude = [current_model_id]` plus every model with the same provider when `trigger ∈ PROVIDER_WIDE_TRIGGERS`; `CONTEXT_OVERFLOW` → profile copied with `estimated_context_tokens = measured_context_tokens` and surviving candidates ordered by `context_window_tokens` descending; `BUDGET_RESTRICTION` → surviving candidates ordered by `output_cost_per_mtok_usd` ascending; (step 9) otherwise `select(role, policy, profile, effort, exclude=exclude)`; the result has `is_fallback=True`, `trigger=trigger`. No ledger writes.
2. Retry (ARCHITECTURE §5.1): a `TransientError` **raised** by the adapter iterator (not an `ERROR` event) is retried: for attempt `n` in `1..5`, ledger `RETRY` (payload attempt, delay, error class), `await sleep(RETRY_DELAYS_S[n-1])`, then continue with `adapter.resume(run.provider_session, RESUME_INSTRUCTION, session)` when the session is resumable, else `adapter.run(input, session)`. After the fifth failure the exception is classified (`router.classify_error`); a trigger → rule 3, `None` → E01-S27 failure path. `PermanentError` is never retried.
3. Fallback: an `ERROR` event with `trigger` (adapter-classified, not retried) or a classified exhausted retry runs, in order: (step 5) `handover = checkpoints.build_handover(run, "FALLBACK", <latest PARTIAL_OUTPUT or None>)`, `ckpt = checkpoints.checkpoint(run, HANDOFF, handover=handover, workflow_state=item.state, budget_consumed=…, context_manifest=…)` (audit before the WIP commit as in E01-S27 rule 8); (steps 7–9) `decision = router.fallback(FallbackRequest(role, policy=agent.runtime_policy.model_policy, current_model_id=run.model_id, trigger, profile, effort=run.effort, fallbacks_so_far=run.fallbacks))`; (step 6) ledger `MODEL_FALLBACK` (payload `trigger`, `from`=run.model_id, `to`=decision.model_id, `handover_id`, `checkpoint_id`, `rejected`) and fire `ON_MODEL_FALLBACK` with the same payload; (step 10) in one `UnitOfWork` the old run → `HANDED_OVER` and the item is unassigned, ledger `AGENT_RUN_ENDED` (`outcome="FAILED"`, payload `state="HANDED_OVER"`, `trigger`); then `new_run = start(agent.model_copy(update={"model_id": decision.model_id, "effort": decision.effort}), item, run.purpose, handover=handover, parent_run_id=run.id, routing=decision)` with `new_run.fallbacks = run.fallbacks + 1`; `checkpoints.close_handover(handover.id, new_run.id)`.
4. `BlockedProvider` from rule 3: old run → `BLOCKED_PROVIDER`, `failure_reason="blocked_provider: <rejections>"`, ledger `ERROR` (payload `kind="BLOCKED_PROVIDER"`, `rejected`), `permissions.request_approval(kind="ESCALATION", approver=USER, payload={"reason": "blocked_provider", "work_item_id", "run_id", "rejected"})` (§21 escalation to level 3), item unassigned, `ON_TASK_FAILED` fired. The HANDOFF checkpoint and handover document remain for a later manual resume.
5. Worktree adoption: `start(..., parent_run_id=P)` where run `P` has a `worktree_path` calls `sandbox.adopt(new_run, P, item)` instead of `create`: the existing directory is reused unchanged (uncommitted residue kept); a missing directory is re-added with `git.add_worktree(path, P.branch)` and guard hooks re-installed. The new run's `worktree_path`/`branch` equal the parent's. `remove(P)` is never called while a child run uses the path.
6. `resume_native(ckpt)`: loads the checkpoint's run `P` and item; `adapter = router.adapter_for(ckpt.model_id)`; requires `ckpt.provider_session.resumable` and `(await adapter.health()).ok` else raises `NotResumable`; instantiates `agents.instantiate(P.role, item, ckpt.model_id, ckpt.effort, budget_ids, ready_env_keys())`; creates a run with `parent_run_id=P.id`, `provider_session=ckpt.provider_session`, `tool_calls=ckpt.tool_calls_so_far`, same purpose; adopts the worktree (rule 5); writes the E01-S27 start events with `MODEL_SELECTED.payload.reason = "native_resume"`; drives `adapter.resume(ckpt.provider_session, RESUME_INSTRUCTION, session)`. A `NotResumable` raised by the adapter's first iteration → the run ends `FAILED` (`failure_reason="not_resumable"`) and the caller (`RecoveryManager`) takes the handover path.
7. `RecoveryManager.recover()` (ARCHITECTURE §5.3): (1) `runs = checkpoints.interrupted_runs(kernel_instance)`; (2) each → `INTERRUPTED`, ledger `ERROR` (payload `kind="INTERRUPTED"`, previous state, previous `kernel_instance`); (3) `ckpt = checkpoints.latest(run.id)`; none → item unassigned, reported in `requeued`; (5) same model healthy and `ckpt.provider_session.resumable` → `executor.resume_native(ckpt)`, reported in `resumed_native`; otherwise or after `NotResumable` → `handover = checkpoints.latest_open_handover(item.id)` or, when none, `build_handover(run, "RECOVERY", None)` checkpointed as `HANDOFF` on the interrupted run; `decision = router.select(role, policy, profile, ckpt.effort, exclude=[ckpt.model_id] if the adapter is unhealthy else [])`; when `decision.model_id != ckpt.model_id` write ledger `MODEL_FALLBACK` (payload `trigger=PROVIDER_OUTAGE`, `from=ckpt.model_id`, `to=decision.model_id`) and fire `ON_MODEL_FALLBACK`; `executor.start(agent, item, run.purpose, handover=handover, parent_run_id=run.id, routing=decision)`; the interrupted run ends `HANDED_OVER`; `close_handover`; reported in `restarted_with_handover`; (6) ledger `RECOVERY_RESUMED` (payload `from_run_id`, `mode` = `native`|`handover`, `checkpoint_seq`, `handover_id`) and fire `ON_RECOVERY_RESUME` (payload `handover_id`, `mode`).
8. Recovery isolates failures per run: any exception for one run → that run `FAILED` (`failure_reason="recovery: <detail>"`), entry in `failed`, the loop continues. `recover()` is idempotent: a second call finds no orphaned runs (resumed runs carry the current `kernel_instance`).
9. `TaskProfile` for fallback and recovery: `TaskProfile(required_capabilities=[], required_tools=agent.tools, required_skills=agent.skills, estimated_context_tokens=<last bundle total_tokens_estimate or 0>, risk=item.risk)`; E03-S07 replaces with the router-built profile.
10. Invariant 1: the role, constitution and permissions of the continuing run are identical to the failing run's; only `model_id`/`provider`/`effort` change (asserted in tests by comparing `AgentInstance` dumps minus those fields).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given preferred `fake-codex/sim`, fallback `fake-claude/sim` and trigger `PROVIDER_OUTAGE`, When `fallback`, Then `fake-claude/sim`, `is_fallback`, `trigger == PROVIDER_OUTAGE` | `tests/model_router/test_fallback.py::test_fallback_excludes_failed_provider` |
| 2 | Given two models of the failing provider and trigger `RATE_LIMIT`, Then both excluded; trigger `TIMEOUT` excludes only the current model | `tests/model_router/test_fallback.py::test_provider_wide_triggers_exclude_whole_provider` |
| 3 | Given `fallbacks_so_far == 2`, Then `BlockedProvider` with `max_fallbacks` | `tests/model_router/test_fallback.py::test_fallback_respects_max_fallbacks` |
| 4 | Given `CONTEXT_OVERFLOW` with measured tokens and two candidates, Then the larger window wins; `BUDGET_RESTRICTION` → the cheaper output price wins | `tests/model_router/test_fallback.py::test_context_and_budget_triggers_reorder_candidates` |
| 5 | Given an adapter raising `RateLimited` twice then succeeding, Then two `RETRY` events with delays 1 and 2 from the fake sleep and run `COMPLETED` | `tests/runtime/test_executor_retry.py::test_transient_error_retried_with_backoff` |
| 6 | Given an adapter raising `ProviderUnavailable` six times, Then five `RETRY` events and then the fallback path with trigger `PROVIDER_OUTAGE` | `tests/runtime/test_executor_retry.py::test_retries_exhausted_then_fallback` |
| 7 | Given an adapter raising `PermissionDenied`, Then no `RETRY` and run `FAILED` | `tests/runtime/test_executor_retry.py::test_permanent_error_not_retried` |
| 8 | Given a 12-call codex script failing with `ERROR(PROVIDER_OUTAGE)` after 3 calls, Then a `HANDOFF` checkpoint, `.ai/handovers/HO-0001.md`, `MODEL_FALLBACK(from=fake-codex/sim, to=fake-claude/sim)`, old run `HANDED_OVER`, new run `COMPLETED` with `parent_run_id`, `handover_in_id == HO-0001`, `fallbacks == 1`, handover row closed with the new run id | `tests/runtime/test_executor_fallback.py::test_provider_outage_falls_back_with_handover` |
| 9 | Given that fallback, Then the new run's `worktree_path` and `branch` equal the old run's and the files written by the first run are present | `tests/runtime/test_executor_fallback.py::test_fallback_run_adopts_worktree` |
| 10 | Given that fallback, Then the new run's `AgentInput.handover.next_action` is non-empty and its `AgentInstance` equals the old one except `model_id`, `effort` | `tests/runtime/test_executor_fallback.py::test_fallback_preserves_role_and_passes_handover` |
| 11 | Given both fakes failing with `PROVIDER_OUTAGE`, Then after two fallbacks the third failure yields `BLOCKED_PROVIDER`, one `ESCALATION` approval request for USER, `ON_TASK_FAILED` fired | `tests/runtime/test_executor_fallback.py::test_exhausted_fallbacks_block_provider_and_escalate` |
| 12 | Given an `ERROR` event without trigger, Then no fallback and run `FAILED` | `tests/runtime/test_executor_fallback.py::test_untriggered_error_does_not_fall_back` |
| 13 | Given a checkpoint with a resumable session and a healthy adapter, When `resume_native`, Then a new run with the same model continues the script from the recorded tool-call index and completes | `tests/runtime/test_resume_native.py::test_resume_native_continues_session` |
| 14 | Given `resumable=False` or an unhealthy adapter, When `resume_native`, Then `NotResumable` | `tests/runtime/test_resume_native.py::test_resume_native_requires_resumable_and_healthy` |
| 15 | Given a RUNNING run owned by instance `old` with a checkpoint, When `recover()` under instance `new` with healthy adapters, Then the run is `INTERRUPTED`, `ERROR(kind=INTERRUPTED)`, a native resume run exists, `RECOVERY_RESUMED(mode=native)`, `ON_RECOVERY_RESUME` fired | `tests/runtime/test_recovery.py::test_recover_resumes_natively_when_possible` |
| 16 | Given the codex fake unhealthy, When `recover()`, Then a handover is written (`reason=RECOVERY`) and the new run uses `fake-claude/sim` with `mode=handover` | `tests/runtime/test_recovery.py::test_recover_uses_handover_when_provider_unhealthy` |
| 17 | Given an orphaned run without any checkpoint, Then the item is unassigned and listed in `requeued` | `tests/runtime/test_recovery.py::test_recover_requeues_runs_without_checkpoint` |
| 18 | Given two orphaned runs where the first raises during recovery, Then the second is still resumed and the first is `FAILED` in `failed` | `tests/runtime/test_recovery.py::test_recover_isolates_failures` |
| 19 | When `recover()` is called twice, Then the second report is empty | `tests/runtime/test_recovery.py::test_recover_is_idempotent` |
| 20 | Given a parent run whose worktree directory was deleted, When `adopt`, Then the worktree is re-added on the parent's branch with guard hooks | `tests/runtime/test_sandbox.py::test_adopt_reuses_or_re_adds_worktree` |

#### Evidence required
- Quality gate output.
- Demo: from `tests/runtime/test_executor_fallback.py::test_provider_outage_falls_back_with_handover` paste the ledger sequence for the story (`AGENT_RUN_STARTED`, `CHECKPOINT_CREATED(HANDOFF)`, `HANDOVER_CREATED`, `MODEL_FALLBACK`, `AGENT_RUN_ENDED(HANDED_OVER)`, `AGENT_RUN_STARTED`, …) and the first 15 lines of `HO-0001.md`; equivalent CLI form `walk ledger query --item STORY-0002`.

#### Notes
- INTERFACES §5.3 steps 5–10; ARCHITECTURE §4.3 (`MODEL_FALLBACK`, `RETRY`, `RECOVERY_RESUMED` are `runtime.AgentExecutor` write points; `RecoveryManager` is in the same package and writes them on its behalf), §5.1, §5.3, §5.5; ADR-0002 D-5/D-6; ADR-0004 D-5/D-6; ADR-0011 D-6.
- Architecture inconsistency resolved (architect, 2026-10-06): ARCHITECTURE §2.2 forbids `model_router → runtime`, so the router owns the decision (steps 7–9, `FallbackRequest`) and the executor owns the side effects (steps 5, 6, 10). INTERFACES §1.4/§1.13/§5.3, DOMAIN-MODEL §4.10 (`FallbackRequest`, `MAX_FALLBACKS_PER_RUN`) and §4.12 (`MODEL_FALLBACK`/`RECOVERY_RESUMED` payload contracts) and ARCHITECTURE §5.3 (recovery `MODEL_FALLBACK`, interrupted run `HANDED_OVER`) already carry this design.
- `NEW NAME:` `FallbackRequest`, `MAX_FALLBACKS_PER_RUN`, `PROVIDER_WIDE_TRIGGERS`, `RETRY_DELAYS_S`, `RESUME_INSTRUCTION`, `SandboxManager.adopt`, `RecoveryManager`, `RecoveryReport` (`RecoveryManager` is already referenced by E02-S11), ledger payload keys `kind="INTERRUPTED"|"BLOCKED_PROVIDER"`, `mode`.
- Cross-epic coordination (non-blocking): E02-S08 `builtin.fallback_chain` fires `ON_AGENT_HANDOFF`, whose MUST attachment checkpoints and writes a handover; the HANDOFF checkpoint and handover already exist when `ON_MODEL_FALLBACK` fires here. The payload carries `checkpoint_id` and `handover_id`; E02-S08's handoff hook is a no-op when both are present (E02-S08 Behavior 8, ARCHITECTURE §4.1).
- Pitfall: git refuses to check out one branch in two worktrees; never call `sandbox.create` for a child run (rule 5). The old run's task must be fully finished (adapter cancelled, stream closed) before the child run starts in the same directory.
- Pitfall: `sleep` is injected so tests never wait and stay deterministic; jitter lives only in the default `sleep` wrapper built by the composition root.
- Commit subject: `feat: add model fallback with handover, retries and startup recovery (E01-S28)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S29 — `TaskRouter`, `Scheduler`, `Orchestrator` service

**Status:** TODO
**Type:** feat
**Requirements:** §6.2, §10.1 (assign role), §56, §60, §87 (status snapshot), §89, §90, §125, §137 (Inv. 4 — role check only, 12)
**Depends on:** E01-S28, E01-S13, E01-S10, E01-S11
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
The orchestrator package exists: `DefaultTaskRouter` resolves the role and purpose of a ready work item from `scheduled_states.yaml`, `Scheduler.tick` admits ready STORY/TASK work per INTERFACES §5.1 (pause flag, parallelism, idempotency key, budgets, effort, model selection, admission transition, open handover, executor start), and `DefaultOrchestrator` runs startup recovery, the tick loop with wake-ups, and a `KernelStatus` snapshot.

#### Scope
- In: `orchestrator.models` (`RouteDecision`, `KernelStatus`, `PhaseEvidencePackage`), `orchestrator.protocols` (`Orchestrator`, `TaskRouter`), `NoScheduledRole`, `DefaultTaskRouter.route` (literal and contract roles, `fallback_role`) and `can_run_parallel` (same item, dependency edge, same branch), `Scheduler.tick` with `ADMISSION_EVENTS` for STORY/TASK `READY|REWORK → start_implementation`, `DefaultOrchestrator.start/stop/wake/tick/run_once/status`, `StatusBuilder`.
- Out: full routing profile, Invariant 4 implementer check and cross-model enforcement, contract-path parallelism (E03-S07); admission of REVIEW/QC/TRIAGE/PLAN/DESIGN work (E03-S09/S13/S14/S15 extend `ADMISSION_EVENTS`); bug-severity and BLOCKED-first ordering (E03-S18); per-role limits beyond `max_parallel_runs` and `max_parallel_agents > 2` (E07-S01); handover open/close refinements (E04-S06); `escalation_bump` from effort requests (E04-S07); daemon, lock and CLI (E01-S30); the deferred methods listed in Behavior 11.

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/orchestrator/__init__.py` | create | re-exports |
| `src/walk/orchestrator/models.py` | create | `RouteDecision`, `KernelStatus`, `PhaseEvidencePackage` |
| `src/walk/orchestrator/protocols.py` | create | `Orchestrator`, `TaskRouter` |
| `src/walk/orchestrator/errors.py` | create | `NoScheduledRole` |
| `src/walk/orchestrator/router.py` | create | `DefaultTaskRouter` |
| `src/walk/orchestrator/scheduler.py` | create | `Scheduler`, `ADMISSION_EVENTS`, `DEFAULT_MAX_PARALLEL_AGENTS` |
| `src/walk/orchestrator/status.py` | create | `StatusBuilder` |
| `src/walk/orchestrator/service.py` | create | `DefaultOrchestrator`, `DEFAULT_POLL_INTERVAL_S` |
| `tests/orchestrator/__init__.py` | create | — |
| `tests/orchestrator/test_models.py` | create | — |
| `tests/orchestrator/test_router_basic.py` | create | — |
| `tests/orchestrator/test_scheduler.py` | create | — |
| `tests/orchestrator/test_status.py` | create | — |
| `tests/orchestrator/test_service.py` | create | — |

#### Interface contract
Models: INTERFACES.md §1.1 `RouteDecision`, `KernelStatus`; DOMAIN-MODEL §4.15 `PhaseEvidencePackage` verbatim. Protocols: INTERFACES.md §1.1 `Orchestrator`, `TaskRouter` verbatim. Algorithm: INTERFACES.md §5.1. Deltas:
```python
class NoScheduledRole(ConfigError):
    """(kind, state) has no row in scheduled_states.yaml."""


class DefaultTaskRouter:
    def __init__(
        self,
        scheduled_states: Path,
        agents: AgentManager,
        runs: AgentRunRepository,
        workflow: WorkflowManager,
    ) -> None: ...  # signature fixed for E03-S07
    def route(self, item: WorkItem, state: WorkItemState) -> RouteDecision: ...
    def can_run_parallel(self, a: WorkItem, b: WorkItem) -> bool: ...


DEFAULT_MAX_PARALLEL_AGENTS = 2  # ARCHITECTURE §3.2 [MVP]
ADMISSION_EVENTS: dict[tuple[WorkItemKind, WorkItemState], str] = {
    (STORY, READY): "start_implementation",
    (STORY, REWORK): "start_implementation",
    (TASK, READY): "start_implementation",
    (TASK, REWORK): "start_implementation",
}


class Scheduler:
    def __init__(
        self,
        db: Database,
        projects: ProjectRepository,
        workflow: WorkflowManager,
        router: TaskRouter,
        agents: AgentManager,
        effort: EffortManager,
        budgets: BudgetManager,
        models: ModelRouter,
        executor: DefaultAgentExecutor,
        checkpoints: DefaultCheckpointManager,
        idempotency: IdempotencyStore,
        telemetry: TelemetryManager,
        clock: Clock,
        *,
        project_key: ProjectKey,
        max_parallel_agents: int = DEFAULT_MAX_PARALLEL_AGENTS,
        ready_env_keys: Callable[[], set[str]] = set,
    ) -> None: ...
    async def tick(self) -> int: ...


class StatusBuilder:
    def __init__(
        self,
        projects: ProjectRepository,
        workflow: WorkflowManager,
        phases: PhaseRepository,
        runs: AgentRunRepository,
        budgets: BudgetManager,
        ledger: LedgerManager,
        *,
        project_key: ProjectKey,
        pending_approvals: Callable[[], Awaitable[list[ApprovalRequest]]] | None = None,
    ) -> None: ...
    async def build(self) -> KernelStatus: ...


DEFAULT_POLL_INTERVAL_S = 5.0  # ADR-0009 D-4 timer wake-up


class DefaultOrchestrator:
    def __init__(
        self,
        scheduler: Scheduler,
        executor: DefaultAgentExecutor,
        recovery: RecoveryManager,
        status_builder: StatusBuilder,
        hooks: HookManager,
        ledger: LedgerManager,
        clock: Clock,
        *,
        project_key: ProjectKey,
        kernel_instance: str,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> None: ...
    async def run_once(
        self, *, wait_runs: bool = True
    ) -> int: ...  # startup steps 4–6, one tick, optionally await the started runs, stop

    # Orchestrator protocol methods per INTERFACES §1.1
```

#### Behavior
1. `route(item, state)`: finds the `scheduled_states.yaml` row for `(item.kind, state)` (missing → `NoScheduledRole`); role = literal, or `item.contract.owner_role` / `item.contract.reviewer_role` for `contract.*` values (defaults `SENIOR_DEV` / `LEAD_DEV` when no contract); `fallback_role` used when the role is not in `agents.list_roles()`; `profile = TaskProfile(required_capabilities=[], required_tools=agents.load_runtime_policy(role).allowed_tools, required_skills=contract.required_skills or [], estimated_context_tokens=0, risk=item.risk, implementer_model_id=None)`; `cross_model_review = load_runtime_policy(role).model_policy.cross_model_review`. Pure apart from the YAML (loaded once in `__init__`).
2. `can_run_parallel(a, b)` is `False` when `a.id == b.id`, when either is in the other's `contract.dependencies`, or when both `branch` values are set and equal; otherwise `True`. Symmetric, no I/O.
3. `Scheduler.tick` (INTERFACES §5.1): (1) `ProjectRepository.get(project_key).paused` → return 0; (2) `items = workflow.ready_items(project.current_phase_id)` (order preserved: priority, created_at); (4) loop while `len(executor.running()) < max_parallel_agents`; items whose `(kind, state)` is not in `ADMISSION_EVENTS` are skipped (telemetry counter `scheduler.not_admitted`); (5) `route = router.route(item, item.state)`; (6) skip when running runs of `route.role` ≥ `RuntimePolicy.max_parallel_runs` or `can_run_parallel(item, r_item)` is `False` for any running run's item; (7) `key = f"schedule:{item.id}:{item.state}:{item.state_version}"` — `idempotency.has(key)` → skip.
4. Tick continued: (8) `budgets.ensure(TASK, item.id, policy.budget_policy, None)` and `budgets.ensure(ROLE, role, policy.budget_policy, None)`; `headroom = budgets.headroom(BudgetSubject(project_key, item.phase_id, role, item.id))`; `budget_ok = all(v > 0 for v in headroom.values())`; (9) `resolution = effort.resolve(policy.effort_policy, item, item.state, escalation_bump=0, budget_headroom=headroom)`; (10) `routing = models.select(role, policy.model_policy, route.profile, resolution.effective)` — `BlockedProvider` → skip (counter `scheduler.blocked_provider`, `logging` warning with the rejections); (11) `agent = agents.instantiate(role, item, routing.model_id, routing.effort, [b.id for b in budgets], ready_env_keys())` — `ConfigError` → skip (counter `scheduler.instantiate_failed`).
5. Admission transition: `workflow.raise_event(item.id, ADMISSION_EVENTS[(kind, state)], TransitionContext(actor_role=KERNEL, source=KERNEL, run_id=None, payload={"budget_ok": budget_ok, "branch_available": <no non-terminal run of another item uses item.branch>}, phase=None))`; `GuardRejected` → skip (counter `scheduler.admission_rejected`); the item is re-read after the transition.
6. Start: (12) `handover = checkpoints.latest_open_handover(item.id)`; (13) `run = executor.start(agent, item, route.purpose, handover=handover, routing=routing, effort_resolution=resolution)`; in one `UnitOfWork` `idempotency.put(key, "schedule", run.id)`; when a handover was passed, `checkpoints.close_handover(handover.id, run.id)`; `started += 1`. An exception from `start` is logged, counted (`scheduler.start_failed`) and does not abort the tick.
7. `tick` never raises for a single item's failure; it raises only when the project row is missing (`ConfigError`).
8. `StatusBuilder.build()`: `project_key`, `paused`, `current_phase` (`PhaseRepository.get(project.current_phase_id)` or `None`), `phase_progress` = item count per `WorkItemState` for the current phase (all items when no phase), `gdd_coverage = {}` (E09-S04), `active_runs` = runs in `RUNNING|PAUSED_FOR_APPROVAL|PAUSED_BY_USER`, `blocked_items` = ids of `BLOCKED` items, `pending_approvals` from the injected callable (`[]` when `None`; E02-S11 wires it), `open_debates = []`, `model_usage` = `UsageReport` per `model_id` summed from `COST_RECORDED` ledger payloads (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_usd`; `turns`/`tool_calls`/`duration_s` 0), `qc_status = {}`, `build_status = None`, `budgets = budgets.applicable(BudgetSubject(project_key))`, `open_improvement_candidates = 0`.
9. `DefaultOrchestrator.start()` (ARCHITECTURE §3.4 steps 5–6; steps 1–3 belong to the daemon, E01-S30, and E02; step 4 — builtin hook registration — is done by the composition root before `start`, ADR-0016): `report = recovery.recover()`; ledger `PROJECT_STARTED` (payload `kernel_instance`, recovery counts); fire `ON_PROJECT_START`; snapshot `status`; then loop until `stop()`: `started = await tick()`, refresh the status snapshot, `await asyncio.wait_for(wake_event.wait(), poll_interval_s)` (timeout is normal), clear the event. `wake()` sets the event. `tick()` delegates to `Scheduler.tick`.
10. `stop(drain=True)`: ends the loop; `drain=True` → `executor.pause(run_id)` for every running run (PAUSE checkpoint, `PAUSED_BY_USER`); `drain=False` → adapters cancelled without checkpoint and runs left `RUNNING`, so the next start's recovery resumes them from their latest checkpoint. `run_once(wait_runs=True)` = startup steps of rule 9, one `tick`, then waits until `executor.running()` is empty (so fallback and repair continuations started by the executor are included), then `stop(drain=False)`; returns the number started by the tick. `status()` returns the latest snapshot (built at least once in `start`/`run_once`).
11. Deferred methods raise `ConfigError("implemented in <ID>")`: `submit_feature` → E03-S09, `plan_phase` → E06-S04, `start_phase` → E07-S02, `request_phase_review` → E07-S04, `decide_phase` → E07-S05, `handle_escalation` → E05-S02, `pause`/`resume`/`cancel_work_item` → E02-S13, `force_review` → E03-S16.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | When `RouteDecision`, `KernelStatus`, `PhaseEvidencePackage` are built from fixtures, Then JSON round-trips; `RouteDecision` and `KernelStatus` are frozen | `tests/orchestrator/test_models.py::test_orchestrator_models_round_trip` |
| 2 | Given a READY story with contract `owner_role=SENIOR_DEV`, When `route`, Then `SENIOR_DEV`/`IMPLEMENT`; READY_FOR_REVIEW → contract reviewer role/`REVIEW`; FEATURE IDEA → `ORCHESTRATOR`/`PLAN` | `tests/orchestrator/test_router_basic.py::test_route_literal_and_contract_roles` |
| 3 | Given DESIGN_LEADER not in `list_roles()`, When `route(FEATURE, DISCOVERY)`, Then `ORCHESTRATOR` | `tests/orchestrator/test_router_basic.py::test_route_uses_fallback_role` |
| 4 | When `route(STORY, COMPLETE)`, Then `NoScheduledRole` | `tests/orchestrator/test_router_basic.py::test_route_unknown_state_raises` |
| 5 | Given two stories with a dependency edge or the same branch, Then `can_run_parallel` is `False` both ways; unrelated stories → `True` | `tests/orchestrator/test_router_basic.py::test_can_run_parallel_basic_rules` |
| 6 | Given a READY story and healthy fakes, When `tick`, Then 1 returned, the story is `IMPLEMENTING` via `start_implementation` (actor KERNEL), a run exists with `routing` in its `MODEL_SELECTED` payload, and the `schedule:` key is stored with the run id | `tests/orchestrator/test_scheduler.py::test_tick_admits_ready_story` |
| 7 | Given the same item and `state_version`, When `tick` runs twice with the first run still RUNNING, Then only one run exists | `tests/orchestrator/test_scheduler.py::test_tick_is_idempotent_per_state_version` |
| 8 | Given three READY stories and `max_parallel_agents=2`, Then two runs start and the third waits for the next tick | `tests/orchestrator/test_scheduler.py::test_tick_respects_max_parallel_agents` |
| 9 | Given SENIOR_DEV `max_parallel_runs=1` and one running SENIOR_DEV run, Then a second READY story is not admitted | `tests/orchestrator/test_scheduler.py::test_tick_respects_role_parallelism` |
| 10 | Given `projects.paused = 1`, When `tick`, Then 0 and no transition | `tests/orchestrator/test_scheduler.py::test_tick_returns_zero_when_paused` |
| 11 | Given a READY_FOR_REVIEW story and a FEATURE in IDEA, When `tick`, Then neither is started and `scheduler.not_admitted` is counted | `tests/orchestrator/test_scheduler.py::test_tick_skips_states_without_admission_event` |
| 12 | Given every candidate model unhealthy, Then the item is skipped, stays READY, and the tick continues with the next item | `tests/orchestrator/test_scheduler.py::test_blocked_provider_skips_item` |
| 13 | Given an exhausted TASK budget, Then `start_implementation` is rejected by `budget_available` and no run starts | `tests/orchestrator/test_scheduler.py::test_budget_guard_blocks_admission` |
| 14 | Given an open handover for the item, When `tick`, Then `AgentInput.handover.id` equals it and the handover is closed with the new run id | `tests/orchestrator/test_scheduler.py::test_tick_passes_open_handover` |
| 15 | Given the effort policy of SENIOR_DEV and a HIGH-risk story, Then `EFFORT_SET` payload shows the resolved components and the run effort equals `resolution.effective` | `tests/orchestrator/test_scheduler.py::test_tick_uses_effort_resolution` |
| 16 | Given items in several states, one BLOCKED, one RUNNING run and two COST_RECORDED events, When `StatusBuilder.build`, Then counts, `blocked_items`, `active_runs` and `model_usage` totals match | `tests/orchestrator/test_status.py::test_status_snapshot_from_db_and_ledger` |
| 17 | When `run_once()` with one READY story, Then `PROJECT_STARTED` written, `ON_PROJECT_START` fired, recovery ran, one run started and awaited to `COMPLETED`, returns 1 | `tests/orchestrator/test_service.py::test_run_once_starts_and_waits` |
| 18 | Given `start()` running in a task, When `wake()` is called, Then a tick runs before `poll_interval_s` elapses; `stop()` ends the loop | `tests/orchestrator/test_service.py::test_wake_triggers_tick_and_stop_ends_loop` |
| 19 | Given a running run, When `stop(drain=True)`, Then `PAUSED_BY_USER` with a PAUSE checkpoint; with `drain=False` the run stays `RUNNING` and a new instance's `recover()` resumes it | `tests/orchestrator/test_service.py::test_stop_drain_modes` |
| 20 | For each deferred method, When called, Then `ConfigError` naming its story id | `tests/orchestrator/test_service.py::test_deferred_methods_name_their_story` |

#### Evidence required
- Quality gate output.
- Demo: transcript of `tests/orchestrator/test_service.py::test_run_once_starts_and_waits` printing `orchestrator.status().model_dump_json(indent=2)` after the run (the CLI form `walk status --json` arrives in E01-S30).

#### Notes
- INTERFACES §1.1, §4, §5.1; ARCHITECTURE §3.1, §3.2 "Concurrency", §3.4; ADR-0009 D-3/D-4; ADR-0002 D-7 (`schedule:` key).
- **Deferred-method pattern** (referenced by E01-S08): a protocol method whose behaviour belongs to a later story is implemented as `raise ConfigError("implemented in <story ID>")`, the story id is listed in Scope "Out", and one test asserts the message. No other placeholder (`NotImplementedError`, `pass`, `...`) is allowed in `src/`.
- Write-point note: ARCHITECTURE §4.3 does not list `PROJECT_STARTED`; it is written by `DefaultOrchestrator.start` (the §4.1 `ON_PROJECT_START` MUST row names it). Record for the architect.
- Known E01 limitation: a run that ends `FAILED` leaves its item in `IMPLEMENTING`, which `ready_items` does not schedule; the `ON_TASK_FAILED` escalation that re-queues or blocks it is E03-S16. The epic gate does not exercise this path.
- `NEW NAME:` `NoScheduledRole`, `ADMISSION_EVENTS`, `DEFAULT_MAX_PARALLEL_AGENTS`, `DEFAULT_POLL_INTERVAL_S`, `StatusBuilder`, `DefaultOrchestrator.run_once`, telemetry counters `scheduler.*`. File names `router.py`, `scheduler.py`, `errors.py`, `service.py` match the assumptions of E03-S07/E03-S18/E04-S06.
- Pitfall: `Scheduler.tick` must re-read `executor.running()` after every start; a run that fails during preparation leaves the running set immediately.
- Pitfall: the orchestrator imports `walk.runtime` repositories and `Default*` runtime classes only as constructor parameter types; it never constructs them (composition root only).
- Commit subject: `feat: add task router, scheduler tick and orchestrator service (E01-S29)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S30 — Daemon and composition root: `build_kernel`, `KernelLock`, `CommandConsumer`, `walk run`, `walk status`

**Status:** TODO
**Type:** feat
**Requirements:** §6.2, §56, §87, §89, §93 (transport only), §122, §125, §128, §137 (Inv. 1, 9, 12), §139 (local daemon)
**Depends on:** E01-S29
**Effort:** HIGH   **Risk:** MEDIUM
**Owner role:** SeniorDev   **Reviewer role:** LeadDev

#### Goal
`build_kernel` wires every E01 service from configuration (or test overrides) into a `KernelHandle`; `walk run` acquires the per-repository lock, migrates, recovers and either runs one tick (`--once`) or the daemon loop with the SQLite command channel; `walk status` prints the `KernelStatus` snapshot from a read-only connection; `walk work transition` goes through the daemon when one holds the lock.

#### Scope
- In: `KernelSettings`, `KernelOverrides`, `KernelHandle`, `build_kernel`, `build_status_reader`; `KernelLock` + `KernelLockHeld`; `KernelInstanceRegistry`; `Command`/`CommandResult` models; `CommandConsumer` (daemon side) with handlers `wake`, `stop`, `work.transition`; `CommandClient`, `daemon_running`, `run_mutation` (CLI side); `run_daemon`; `walk run [--once] [--max-parallel N] [--poll-interval S] [--skip-preflight]`; `walk status [--watch]`; `walk work transition` routed through `run_mutation`.
- Out: preflight (`--skip-preflight` is accepted and recorded; preflight itself is E02-S02); Production Kit loading, version pins and drift checks at startup (E02-S03/S04/S07); `--webhook-port` and the `/status` HTTP endpoint (E03-S05, E09-S04); pause/resume/cancel/priority/policy commands (E02-S13); approve/deny commands (E02-S11); `walk phase gate` via the daemon (E07-S05); credential store and scrubbed env (E02-S01).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `src/walk/cli/composition.py` | modify | `KernelSettings`, `KernelOverrides`, `KernelHandle`, `build_kernel`, `build_status_reader`, `DEFAULT_READY_ENV_KEYS` (keeps `open_database`) |
| `src/walk/cli/daemon.py` | create | `run_daemon` |
| `src/walk/cli/ipc.py` | create | `CommandClient`, `daemon_running`, `run_mutation`, `COMMAND_POLL_INTERVAL_S` |
| `src/walk/cli/cmd_run.py` | create | `run` |
| `src/walk/cli/cmd_status.py` | create | `status` |
| `src/walk/cli/cmd_work.py` | modify | `transition` (routes through `run_mutation`) |
| `src/walk/cli/app.py` | modify | registers `run`, `status` |
| `src/walk/persistence/lock.py` | create | `KernelLock`, `LOCK_FILE_NAME` |
| `src/walk/persistence/instances.py` | create | `KernelInstanceRegistry` |
| `src/walk/persistence/errors.py` | modify | `KernelLockHeld` |
| `src/walk/persistence/__init__.py` | modify | re-exports |
| `src/walk/orchestrator/models.py` | modify | `Command`, `CommandResult` |
| `src/walk/orchestrator/commands.py` | create | `CommandConsumer`, `CommandHandler` |
| `src/walk/orchestrator/__init__.py` | modify | re-exports |
| `tests/cli/test_composition.py` | create | — |
| `tests/cli/test_daemon.py` | create | — |
| `tests/cli/test_ipc.py` | create | — |
| `tests/cli/test_cmd_run.py` | create | — |
| `tests/cli/test_cmd_status.py` | create | — |
| `tests/cli/test_cmd_work.py` | modify | — |
| `tests/persistence/test_lock.py` | create | — |
| `tests/persistence/test_instances.py` | create | — |
| `tests/orchestrator/test_commands.py` | create | — |

#### Interface contract
CLI: INTERFACES.md §6 rows `walk run`, `walk status`, `walk work transition`; exit codes 0/1/2/3/4. IPC tables: DOMAIN-MODEL §6.2 `commands`, `command_results`, `kernel_instances`. Deltas:
```python
# walk.cli.composition
DEFAULT_READY_ENV_KEYS: frozenset[str] = frozenset({"git"})          # used when git is on PATH; E02-S02 replaces with the EnvironmentManifest
class KernelSettings(WalkModel):
    repo_path: Path
    max_parallel: int = DEFAULT_MAX_PARALLEL_AGENTS
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S
    webhook_port: int | None = None                                   # accepted, unused until E03-S05
    skip_preflight: bool = False
    json_output: bool = False
class KernelOverrides(WalkModel):                                     # arbitrary_types_allowed; tests and e2e gates only
    adapters: dict[str, ModelAdapter] | None = None                   # keyed by provider; replaces ClaudeAdapter/CodexAdapter
    git: GitProvider | None = None
    clock: Clock | None = None
    id_factory: IdFactory | None = None                               # ULIDs only; sequences always come from IdSequenceStore
    subprocess_runner: SubprocessRunner | None = None
    sleep: Callable[[float], Awaitable[None]] | None = None
    kernel_instance: str | None = None
    ready_env_keys: set[str] | None = None
class KernelHandle:
    settings: KernelSettings; project_key: ProjectKey; kernel_instance: str; db: Database; ledger: LedgerManager; telemetry: TelemetryManager; evidence: EvidenceManager
    hooks: HookManager; workflow: WorkflowManager; budgets: BudgetManager; costs: CostManager; effort: EffortManager; tools: ToolRegistry
    permissions: PermissionManager; memory: MemoryManager; agents: AgentManager; router: ModelRouter; git: GitProvider; context: ContextManager
    checkpoints: DefaultCheckpointManager; tool_invoker: DefaultToolInvoker; executor: DefaultAgentExecutor; recovery: RecoveryManager
    scheduler: Scheduler; orchestrator: DefaultOrchestrator; status_builder: StatusBuilder
    async def aclose(self) -> None: ...                               # cancels run tasks without checkpoint, closes the DB
def build_kernel(settings: KernelSettings, *, overrides: KernelOverrides | None = None) -> KernelHandle: ...
def build_status_reader(repo: Path) -> StatusBuilder: ...             # read-only connection; no adapters constructed
# walk.persistence
LOCK_FILE_NAME = "kernel.lock"                                        # <repo>/.ai/kernel.lock
class KernelLockHeld(ConfigError): """Another live process holds the kernel lock; detail = holder pid, instance, started_at."""
class KernelLock:
    def __init__(self, ai_root: Path, *, kernel_instance: str, clock: Clock) -> None: ...
    def acquire(self) -> None: ...                                    # non-blocking OS lock (msvcrt / fcntl); writes JSON {pid, kernel_instance, started_at}
    def release(self) -> None: ...
    def __enter__(self) -> "KernelLock": ...; def __exit__(self, *exc: object) -> None: ...
    @staticmethod
    def is_held(ai_root: Path) -> bool: ...
class KernelInstanceRegistry:
    def __init__(self, db: Database, clock: Clock) -> None: ...
    async def register(self, kernel_instance: str, *, hostname: str, pid: int) -> None: ...
    async def heartbeat(self, kernel_instance: str) -> None: ...
# walk.orchestrator
class Command(FrozenModel): id: int; name: str; args: JsonDict; requested_at: datetime; requested_by: str; state: Literal["PENDING", "RUNNING", "DONE", "FAILED"]
class CommandResult(FrozenModel): command_id: int; finished_at: datetime; ok: bool; result: JsonDict; exit_code: int
CommandHandler = Callable[[JsonDict], Awaitable[JsonDict]]
class CommandConsumer:
    def __init__(self, db: Database, clock: Clock, *, poll_interval_s: float = 0.25, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...
    def register(self, name: str, handler: CommandHandler) -> None: ...   # duplicate → ConfigError
    async def poll_once(self) -> int: ...                                 # processes PENDING rows in id order; returns count
    async def run(self, stop: asyncio.Event) -> None: ...
# walk.cli.ipc
COMMAND_POLL_INTERVAL_S = 0.25                                        # ADR-0009 D-3
class CommandClient:
    def __init__(self, db: Database, clock: Clock, *, timeout_s: float = 30.0, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...
    async def submit(self, name: str, args: JsonDict, *, requested_by: str = "USER") -> int: ...
    async def wait(self, command_id: int) -> CommandResult: ...       # polls command_results every COMMAND_POLL_INTERVAL_S; timeout → Timeout
def daemon_running(repo: Path) -> bool: ...
async def run_mutation(repo: Path, name: str, args: JsonDict, in_process: Callable[[KernelHandle], Awaitable[JsonDict]]) -> CommandResult: ...
# walk.cli.daemon
async def run_daemon(settings: KernelSettings, *, once: bool, overrides: KernelOverrides | None = None) -> int: ...   # exit code
```

#### Behavior
1. `build_kernel` performs no network or provider calls and starts no task: opens `<repo>/.ai/kernel.db` (creating `.ai/` when absent), applies pending migrations, constructs every E01 service with constructor injection in dependency order (persistence → telemetry → hooks → workflow → budgets/effort → tools/permissions → memory → context → agents → model_router → integrations.git → runtime → orchestrator), and returns the handle. The project key is the key of the single `projects` row (none → `ConfigError("no project in .ai/kernel.db; run 'walk bootstrap'")`, several → `ConfigError`). It is the only module importing `service.py` files of several packages (ARCHITECTURE §1.3).
2. Configuration sources: kernel defaults for constitutions, policies and `models.yaml`, merged with `<repo>/.ai/agents/roles/`, `policies.yaml`, `models.yaml` when present (E01-S17/S20 loaders). Permission rules for `DefaultPermissionManager` = the union of every role's constitution `tool_permissions` (ADR-0006 D-6 defaults) until E02-S10 adds `permissions.yaml`.
3. Adapters: `overrides.adapters` when given — their `descriptors()` are added to the models config for ids not already present, so fakes route without a project `models.yaml`; otherwise `CodexAdapter` (with `AsyncioCodexProcessLauncher`) and `ClaudeAdapter` when `claude_agent_sdk` is importable — when it is not, every `claude` descriptor is set `enabled=False` and a warning is logged. Prompt builders: system = `render_constitution(input.constitution, <project constitution markdown or None>)`; user = `input.instructions_markdown + "\n\n" + render_input_sections(input)` (E01-S18).
4. Wiring details: `ContextManager.handovers = checkpoints.latest_open_handover_doc` (E01-S24 Notes), `head_resolver = git.head(repo_root)`; `executor.on_run_finished = orchestrator.wake` (late-bound); `executor.env_allowlist` returns `{}` until E02-S01; `ready_env_keys` = override or `DEFAULT_READY_ENV_KEYS` when `git` is on `PATH`, else `set()`; `kernel_instance` = override or a new UUID4; `scheduler.max_parallel_agents = settings.max_parallel`; `orchestrator.poll_interval_s = settings.poll_interval_s`.
5. `KernelLock.acquire` takes a non-blocking exclusive OS lock on `<repo>/.ai/kernel.lock` and writes the holder JSON; a second acquirer in another process (or another `KernelLock` instance in the same process) gets `KernelLockHeld` with the holder details. A lock file left by a dead process does not block (the OS lock died with it). `is_held` probes without keeping the lock.
6. `run_daemon(settings, once)`: (1) acquire lock — held → message `kernel already running (pid …)`, exit 1; (1b) no `projects` row → message `no project — run 'walk bootstrap'`; with `once=True` print `started 0 run(s)` (`{"started": 0}` with `--json`) and exit 0, in daemon mode exit 1; (2) `build_kernel`; (3) `KernelInstanceRegistry.register`; (4) preflight skipped with an info log (E02-S02); (5) `once=True` → `orchestrator.run_once()`, print `started <n> run(s)` (or JSON `{"started": n}` with `--json`), exit 0; `once=False` → register consumer handlers, run `consumer.run(stop)` and `orchestrator.start()` concurrently, heartbeat every tick; `KeyboardInterrupt`/`stop` command → `orchestrator.stop(drain=True)`; (6) `handle.aclose()` and lock release in `finally`. Unexpected exceptions → logged, exit 1.
7. `CommandConsumer.poll_once`: selects `PENDING` rows ordered by `id`, sets `RUNNING`, awaits the handler, inserts `command_results(ok, result_json, finished_at)` and sets `DONE`/`FAILED` in one `UnitOfWork`; unknown name → `FAILED` with `{"error": "unknown command <name>", "exit_code": 1}`; `GuardRejected`/`PermissionDenied` → exit code 2; other `WalkError` → 1; non-`WalkError` exceptions → 1 and logged with traceback. The consumer writes no ledger events.
8. Daemon handlers in E01: `wake` → `orchestrator.wake()`, result `{}`; `stop` → sets the stop event; `work.transition{work_item_id, event, reason}` → `workflow.raise_event(id, event, TransitionContext(actor_role=USER, source=USER, run_id=None, payload={"reason": reason}, phase=None))` then `wake()`, result `{"to_state": …}`.
9. `run_mutation(repo, name, args, in_process)`: when `daemon_running(repo)` → `CommandClient.submit` + `wait`; else acquire the lock, `build_kernel`, run `in_process(handle)`, release (ARCHITECTURE §3.1 offline-safe commands). `walk work transition` uses it; exit codes from the result (0 ok, 2 guard/permission, 1 other, 3 on client `Timeout` with message `daemon not responding`).
10. `walk run` options map onto `KernelSettings` (`--max-parallel`, `--poll-interval`, `--skip-preflight`) plus `--once`; `walk status` builds `build_status_reader(repo).build()` and prints a table (phase, progress per state, active runs with role/model/state, blocked items, pending approvals, budgets) or `KernelStatus.model_dump_json()` with `--json`; `--watch` re-renders every 2 s until interrupted. `walk status` never requires the daemon and never writes to the DB.
11. `KernelHandle.aclose()` cancels running run tasks without checkpoint (their rows stay `RUNNING`, recovered by the next instance) and closes the DB; it is idempotent.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given `tmp_game_repo` and overrides with two fake adapters, When `build_kernel`, Then every `KernelHandle` attribute is set, the DB is migrated, no task is running and the fakes' descriptors are routable | `tests/cli/test_composition.py::test_build_kernel_wires_all_services_with_fakes` |
| 2 | Given no overrides and `claude_agent_sdk` not importable, When `build_kernel`, Then claude descriptors are disabled and `router.adapter_for("gpt-5-codex").provider == "codex"` | `tests/cli/test_composition.py::test_build_kernel_disables_missing_claude_sdk` |
| 3 | Given a project `.ai/agents/policies.yaml` overriding SENIOR_DEV `checkpoint_every_tool_calls`, When built, Then `agents.load_runtime_policy(SENIOR_DEV)` reflects it | `tests/cli/test_composition.py::test_build_kernel_reads_project_overrides` |
| 4 | When the composition module is inspected, Then it is the only module under `src/walk/` importing more than one package's `service.py` | `tests/cli/test_composition.py::test_composition_is_only_multi_service_importer` |
| 5 | Given a held lock, When a second `KernelLock.acquire` runs in a subprocess, Then `KernelLockHeld` with the holder pid; after `release` it succeeds | `tests/persistence/test_lock.py::test_lock_is_exclusive_across_processes` |
| 6 | Given a lock file written by a process that exited, When `acquire`, Then success | `tests/persistence/test_lock.py::test_stale_lock_file_does_not_block` |
| 7 | When `register` then `heartbeat`, Then one `kernel_instances` row with updated `heartbeat_at` | `tests/persistence/test_instances.py::test_register_and_heartbeat` |
| 8 | Given PENDING commands `wake` and `nope`, When `poll_once`, Then `wake` → `DONE` with ok result, `nope` → `FAILED` exit 1, both in `command_results` | `tests/orchestrator/test_commands.py::test_poll_once_dispatches_and_records` |
| 9 | Given a handler raising `GuardRejected`, Then the result has `ok=false`, `exit_code=2` | `tests/orchestrator/test_commands.py::test_guard_rejection_maps_to_exit_code_2` |
| 10 | When `register("wake", …)` twice, Then `ConfigError` | `tests/orchestrator/test_commands.py::test_duplicate_handler_rejected` |
| 11 | Given a consumer running against the same DB, When `CommandClient.submit("wake")` and `wait`, Then the result arrives with ok; with no consumer and `timeout_s=0.5` → `Timeout` | `tests/cli/test_ipc.py::test_client_round_trip_and_timeout` |
| 12 | Given no daemon, When `run_mutation`, Then `in_process` ran under the lock and the lock is released afterwards | `tests/cli/test_ipc.py::test_run_mutation_in_process_without_daemon` |
| 13 | Given a READY story and fake adapters, When `run_daemon(settings, once=True)`, Then exit 0, one run `COMPLETED`, `PROJECT_STARTED` and `AGENT_RUN_ENDED` in the ledger, lock released | `tests/cli/test_daemon.py::test_run_once_executes_one_tick` |
| 14 | Given the lock held by another process, When `walk run --once`, Then exit 1 and message contains `already running` | `tests/cli/test_cmd_run.py::test_run_exits_1_when_lock_held` |
| 15 | Given a migrated repo without a project row (and, separately, with a project but no ready work), When `walk run --once --json`, Then exit 0 and stdout `{"started": 0}` | `tests/cli/test_cmd_run.py::test_run_once_with_no_ready_work` |
| 16 | Given the daemon loop running in a task, When a `stop` command is submitted, Then `orchestrator.stop(drain=True)` ran, the loop ended and exit 0 | `tests/cli/test_daemon.py::test_stop_command_ends_daemon` |
| 17 | Given items, one active run and a budget, When `walk status --json`, Then valid `KernelStatus` JSON matching the DB; table mode lists the run's role and model | `tests/cli/test_cmd_status.py::test_status_json_and_table` |
| 18 | When `walk status` runs while another process holds the lock, Then exit 0 (read-only, no lock needed) | `tests/cli/test_cmd_status.py::test_status_does_not_need_lock` |
| 19 | Given a running daemon, When `walk work transition STORY-0001 block --reason x`, Then the transition is executed by the consumer (command row `DONE`) with actor USER; a guard failure exits 2 | `tests/cli/test_cmd_work.py::test_transition_routes_through_daemon` |
| 20 | Given no daemon, When `walk work transition`, Then it runs in-process and exits 0 | `tests/cli/test_cmd_work.py::test_transition_in_process_without_daemon` |
| 21 | When `KernelHandle.aclose()` is called with a RUNNING run, Then the task is cancelled, the row stays `RUNNING`, and calling it again is a no-op | `tests/cli/test_composition.py::test_aclose_leaves_runs_recoverable` |
| 22 | Given a migrated repo with no `projects` row, When `build_kernel`, Then `ConfigError` mentioning `walk bootstrap`; with two rows → `ConfigError` | `tests/cli/test_composition.py::test_build_kernel_requires_single_project` |

#### Evidence required
- Quality gate output.
- Demo on a fresh temp repo (after `walk db migrate`): `walk run --once` → `started 0 run(s)`; `walk status --json` → `KernelStatus` JSON with empty `active_runs`; a second terminal running `walk run` while the first holds the lock → exit 1 `kernel already running`.
- Checkpoint (WBS §7.2): `walk run --once` with no ready work exits 0.

#### Notes
- ARCHITECTURE §1.2 (`cli` hosts the composition root), §1.3, §3.1, §3.4; ADR-0009 D-3/D-4/D-16/D-17; WBS §3.6, §3.7; INTERFACES §6.
- `NEW NAME:` `KernelSettings`, `KernelOverrides`, `KernelLock`, `CommandConsumer` (placement), `CommandClient` (already in WBS §6); new here: `KernelHandle` attributes and `aclose`, `build_status_reader`, `DEFAULT_READY_ENV_KEYS`, `KernelLockHeld`, `LOCK_FILE_NAME`, `KernelInstanceRegistry`, `Command`, `CommandResult`, `CommandHandler`, `COMMAND_POLL_INTERVAL_S`, `daemon_running`, `run_mutation`, `run_daemon`, command names `wake`, `stop`, `work.transition`, `KernelOverrides` fields beyond WBS §3.6 (`sleep`, `kernel_instance`, `ready_env_keys`).
- `KernelOverrides` is a test seam (WBS §3.6); production code paths must not branch on it beyond choosing the injected object.
- Pitfall (Windows): `msvcrt.locking` locks byte ranges; lock byte 0 of a file opened `a+b` and keep the handle open for the daemon's lifetime. The lock test spawns `sys.executable -c` so it exercises a real second process.
- Pitfall: the CLI process and the daemon both open the DB; the CLI must never hold a write transaction while waiting for a command result.
- Commit subject: `feat: add composition root, kernel lock, command channel and run/status cli (E01-S30)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-S31 — Epic gate: kernel loop with fake adapters incl. fallback (e2e), import-linter contracts

**Status:** TODO
**Type:** feat
**Requirements:** §6.1, §21, §22, §41, §54, §81, §86, §87, §89, §122, §135 (Stage 1 exit), §137 (Inv. 1, 2, 9, 12), §138 (Model Lock-In)
**Depends on:** E01-S30, E01-S21, E01-S22
**Effort:** MEDIUM   **Risk:** MEDIUM
**Owner role:** QC   **Reviewer role:** LeadDev

#### Goal
One end-to-end test module proves the E01 gate exactly as WBS §4 E01 states it — a READY story runs to `READY_FOR_REVIEW` through 12 tool calls with two periodic WIP-commit checkpoints, a second story survives a scripted provider outage by falling back to the other fake with a handover, and the CLI views reflect all of it — and the package dependency rules and SDK confinement become mechanical parts of the quality gate.

#### Scope
- In: `tests/e2e/` fixtures and gate tests; import-linter contracts generated by hand from ARCHITECTURE §2.2 and a test that keeps them in sync with the table; ruff `banned-api` rules for SDK/subprocess confinement (ARCHITECTURE §2.3); `lint-imports` added to `scripts/check.sh`/`check.ps1`; gate transcript in this story's Evidence.
- Out: any new kernel behaviour (defects found here become `E01-B*` stories via E01-R01); real-provider runs (optional integration markers of E01-S21/S22); recovery after a crash end-to-end (E04-S15); `sqlite3` confinement (see Notes).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `tests/e2e/__init__.py` | create | — |
| `tests/e2e/conftest.py` | create | fixtures `e01_repo`, `e01_kernel`, `e01_scenario`; helpers `E01Scenario`, `run_cli`, `gate_script_for` |
| `tests/e2e/test_e01_gate.py` | create | — |
| `tests/test_import_contracts.py` | create | — |
| `tests/test_scaffold.py` | modify | — (check scripts now run five gate commands) |
| `pyproject.toml` | modify | — (`[tool.importlinter]` contracts; `[tool.ruff.lint.flake8-tidy-imports.banned-api]` + per-file ignores) |
| `scripts/check.sh` | modify | — (adds `uv run lint-imports` after mypy) |
| `scripts/check.ps1` | modify | — (same) |
| `docs/02-work-breakdown/EPIC-01-kernel-core.md` | modify | — (Evidence section of this story) |

#### Interface contract
```python
# tests/e2e/conftest.py
class E01Scenario(WalkModel):                     # arbitrary_types_allowed
    repo: Path
    handle: KernelHandle
    story_ok: WorkItemId                          # STORY-0001: 12 tool calls, COMPLETED
    story_fallback: WorkItemId                    # STORY-0002: PROVIDER_OUTAGE after 3 calls on fake-codex, completes on fake-claude
    started: int                                  # value returned by orchestrator.run_once()

def gate_script_for(agent_input: AgentInput) -> FakeScript: ...
    """STORY-0001 → 12 calls, COMPLETED output with one AUTOMATED_TEST evidence draft (path src/Fake1.cs) and no_context_change_reason;
    STORY-0002 without `agent_input.handover` (first run, routed to fake-codex) → 12 calls with fail_after_tool_calls=3, fail_trigger=PROVIDER_OUTAGE;
    STORY-0002 with a handover (fallback run on fake-claude) → 6 calls, COMPLETED as above. Pure function of the input."""

@pytest.fixture
def e01_repo(tmp_game_repo: Path) -> Path:
    """tmp_game_repo + migrated DB + Project(key="DEMO") row + .ai/agents/policies.yaml overriding SENIOR_DEV:
    model_policy {preferred: [fake-codex/sim], fallback: [fake-claude/sim], cross_model_review: true}, checkpoint_every_tool_calls: 5,
    max_parallel_runs: 2 — plus STORY-0001/STORY-0002 created and moved to READY by ORCHESTRATOR (contract with goal,
    acceptance_criteria, constraints, required_evidence [AUTOMATED_TEST])."""

@pytest.fixture
async def e01_kernel(e01_repo: Path, fake_clock: FakeClock) -> AsyncIterator[KernelHandle]:
    """build_kernel(KernelSettings(repo_path=e01_repo), overrides=KernelOverrides(adapters={"fake-codex": FakeModelAdapter("fake-codex", [fake_descriptor("fake-codex/sim", "fake-codex")], gate_script_for, clock), "fake-claude": FakeModelAdapter("fake-claude", [fake_descriptor("fake-claude/sim", "fake-claude")], gate_script_for, clock)}, clock=fake_clock, sleep=<no-op>, kernel_instance="gate-1")); aclose() on teardown."""

@pytest.fixture
async def e01_scenario(e01_repo: Path, e01_kernel: KernelHandle) -> E01Scenario:
    """Runs `await e01_kernel.orchestrator.run_once()` once and returns the scenario."""

def run_cli(repo: Path, *args: str) -> tuple[int, str]: ...   # typer CliRunner on walk.cli.app with --repo <repo>; returns (exit_code, stdout)
```
Import-linter (`pyproject.toml`): `root_package = "walk"`; one `forbidden` contract per package row of ARCHITECTURE §2.2 whose `source_modules` is the package and whose `forbidden_modules` are exactly the `·` cells among existing packages; one `forbidden` contract forbidding `walk.*.service` from every package except `walk.cli.composition` (wildcards, import-linter ≥ 2.0). Ruff `banned-api`: `claude_agent_sdk` (allowed only in `src/walk/model_router/adapters/claude/**`), `typer` (`src/walk/cli/**`), `keyring` (`src/walk/integrations/credentials.py`), `subprocess` and `asyncio.create_subprocess_exec` (`src/walk/integrations/subprocess.py`, `src/walk/model_router/adapters/codex/process.py`), all allowed in `tests/**` and `scripts/**`.

#### Behavior
Each gate assertion is one test; every test builds its own scenario (no shared state between tests, no ordering dependency).
1. `run_once()` admits both READY stories in one tick (`max_parallel_agents=2`, SENIOR_DEV `max_parallel_runs=2`, different branches) and returns 2; it returns only after every run, including the fallback continuation, has ended.
2. STORY-0001: one run on `fake-codex/sim`, 12 `TOOL_INVOKED(phase=post)` events, checkpoints `START, PERIODIC, PERIODIC, END` (seq 1–4), the work branch has `wip(STORY-0001): checkpoint 2` and `wip(STORY-0001): checkpoint 3` commits each carrying the `Walk-Work-Item: STORY-0001` trailer, one `EVD-` evidence of kind `AUTOMATED_TEST`, run `COMPLETED`, story `READY_FOR_REVIEW` via `submit_for_review` with `actor_role=SENIOR_DEV`.
3. STORY-0002: run A on `fake-codex/sim` ends `HANDED_OVER` after 3 tool calls with a `HANDOFF` checkpoint and `.ai/handovers/HO-0001.md` (10 §22 sections, `reason: FALLBACK`); `MODEL_FALLBACK` payload `trigger=PROVIDER_OUTAGE`, `from=fake-codex/sim`, `to=fake-claude/sim`; run B on `fake-claude/sim` has `parent_run_id = A`, `handover_in_id = HO-0001`, `fallbacks = 1`, the same worktree path and branch as A, ends `COMPLETED`; the story reaches `READY_FOR_REVIEW`; the handover row is closed with `to_run_id = B`.
4. CLI views (read-only, no daemon): `walk status --json` → valid `KernelStatus` with no active runs, `phase_progress[READY_FOR_REVIEW] == 2`, `model_usage` keys `fake-codex/sim` and `fake-claude/sim`; `walk ledger query --item STORY-0002 --json` contains, in order, `AGENT_RUN_STARTED`, `CHECKPOINT_CREATED`, `HANDOVER_CREATED`, `MODEL_FALLBACK`, `AGENT_RUN_ENDED`, `AGENT_RUN_STARTED`, …, `AGENT_RUN_ENDED`; `walk work show STORY-0001` prints `READY_FOR_REVIEW`, both transitions and the run.
5. Ledger completeness (Invariant 9): every run has exactly one `AGENT_RUN_STARTED` and one `AGENT_RUN_ENDED`; every event has `project_key == "DEMO"`; event kinds are a subset of the ARCHITECTURE §4.3 table plus `PROJECT_STARTED`; an `UPDATE ledger_events` statement raises `sqlite3.IntegrityError`.
6. Role ≠ model (Invariant 1): runs A and B of STORY-0002 have the same `role`, `purpose` and `behavior_versions["prompt:IMPLEMENT"]` on `AGENT_RUN_STARTED`, and different `model_id`/`provider`.
7. Continuity (Invariant 12): run B's first tool call happens with the files written by run A present in the worktree (checked via the fake's recorded events and the WIP commit of the HANDOFF checkpoint), and no `TEXT` content appears in `HO-0001.md`.
8. Dependency rules: `lint-imports` (console script of the active environment) exits 0; the contract test proves every `·` cell of ARCHITECTURE §2.2 for packages present under `src/walk/` is covered by a contract and no contract forbids a `✔` cell.
9. The quality gate scripts run, in order, `ruff format --check`, `ruff check`, `mypy src tests`, `lint-imports`, `pytest` (CONVENTIONS §5).

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given the gate repo with two READY stories, When `run_once()`, Then 2 returned and no run is left non-terminal | `tests/e2e/test_e01_gate.py::test_run_once_admits_both_stories_and_drains` |
| 2 | Given STORY-0001, Then 12 tool calls, checkpoints START/PERIODIC/PERIODIC/END, two periodic WIP commits with trailer, AUTOMATED_TEST evidence, story `READY_FOR_REVIEW` | `tests/e2e/test_e01_gate.py::test_story_completes_with_periodic_checkpoints` |
| 3 | Given STORY-0002 with a scripted `PROVIDER_OUTAGE` after 3 calls, Then HANDOFF checkpoint, `HO-0001.md`, `MODEL_FALLBACK` codex→claude, child run completes in the same worktree, story `READY_FOR_REVIEW`, handover closed | `tests/e2e/test_e01_gate.py::test_provider_outage_falls_back_with_handover` |
| 4 | When `walk status --json`, `walk ledger query --item STORY-0002 --json` and `walk work show STORY-0001` run against the repo, Then their outputs reflect Behavior 4 | `tests/e2e/test_e01_gate.py::test_cli_views_reflect_kernel_state` |
| 5 | Given the scenario ledger, Then start/end pairs per run, `project_key` everywhere, kinds within the write-point table, and UPDATE rejected | `tests/e2e/test_e01_gate.py::test_ledger_complete_and_immutable` |
| 6 | Given runs A and B of STORY-0002, Then same role/purpose/prompt version, different model and provider | `tests/e2e/test_e01_gate.py::test_role_is_independent_of_model` |
| 7 | Given run B, Then run A's files exist at B's first tool call and `HO-0001.md` contains no `TEXT` event content | `tests/e2e/test_e01_gate.py::test_continuation_does_not_depend_on_session` |
| 8 | When `lint-imports` runs in the active environment, Then exit 0 | `tests/e2e/test_e01_gate.py::test_import_linter_contracts_pass` |
| 9 | Given ARCHITECTURE.md §2.2 parsed from the repository and `pyproject.toml` contracts, Then every forbidden cell for existing packages is covered and no allowed cell is forbidden | `tests/test_import_contracts.py::test_contracts_match_dependency_table` |
| 10 | Given `pyproject.toml`, Then banned-api entries exist for `claude_agent_sdk`, `typer`, `keyring`, `subprocess`, `asyncio.create_subprocess_exec` with exactly the per-file allowances above | `tests/test_import_contracts.py::test_sdk_confinement_rules_configured` |
| 11 | When `scripts/check.sh` and `check.ps1` are read, Then each contains the five gate commands in order | `tests/test_scaffold.py::test_check_scripts_invoke_all_gate_commands` |

#### Evidence required
- Quality gate output (`scripts/check.sh`) including the `lint-imports` summary (`Contracts: N kept, 0 broken`) and `tests/e2e/test_e01_gate.py` 8 passed.
- Demo transcript (pasted into Evidence) against the repo left by a scenario run (`pytest --basetemp=<dir> tests/e2e/test_e01_gate.py::test_provider_outage_falls_back_with_handover`): `walk status --json`, `walk ledger query --item STORY-0002`, `walk ledger query --kind MODEL_FALLBACK --json`, `walk work show STORY-0001`, `git -C <repo> log --oneline --all | grep wip`, `head -20 .ai/handovers/HO-0001.md`.

#### Notes
- Gate text: WBS.md §4 E01 (verbatim scenario). Uses only fakes and a real temporary git repository (WBS §3.6); `FakeClock` keeps timestamps deterministic, the injected no-op `sleep` removes retry waits.
- The `.ai/agents/policies.yaml` override is the only way the fixture changes kernel behaviour; it must not be needed by production defaults (default SENIOR_DEV policy keeps ADR-0011 D-3 families and `checkpoint_every_tool_calls: 10`).
- `sqlite3` confinement (ARCHITECTURE §2.3) is **not** encoded: repositories outside `walk.persistence` (e.g. E01-S25 `AgentRunRepository.set_state(conn: sqlite3.Connection)`) type-annotate `sqlite3.Connection`. Report to the architect: either allow `sqlite3` type imports outside persistence or introduce a `walk.persistence.Connection` alias; E01-R01 records it.
- `NEW NAME:` `tests/e2e/` already registered (WBS §6); new here: `E01Scenario`, `gate_script_for`, `run_cli`, fixtures `e01_repo`, `e01_kernel`, `e01_scenario`. E02-S16 later adds `bootstrapped_repo`, `cli`, `kernel_with_fakes` to the same conftest; its refine step may reuse `run_cli`.
- Pitfall: two runs write into two worktrees of one repository concurrently; `git` operations on the shared object store are safe, but the gate must not assert on global commit order — assert per branch.
- Commit subject: `feat: add epic 01 kernel gate test and import contracts (E01-S31)`.

#### Evidence (filled by implementer)
_pending_

---

### E01-R01 — Review E01

**Status:** TODO
**Type:** docs
**Requirements:** §6.1, §21–§23, §31, §41, §54, §81, §86, §89, §90, §125, §126, §135 (Stage 1 exit), §137 (Inv. 1, 2, 9, 12)
**Depends on:** E01-S31
**Effort:** MEDIUM   **Risk:** LOW
**Owner role:** LeadDev   **Reviewer role:** QC

#### Goal
An independent agent instance (a different model than the implementer of the majority of E01 stories) verifies every E01 story against the Definition of Done and invariants 1, 2, 9 and 12, consolidates the epic's `NEW NAME:` items and architecture inconsistencies for the architect, and records defects as `E01-B*` bugfix stories.

#### Scope
- In: review of the E01-S01…S31 commits; DoD checklist per story; invariant checks 1, 2, 9, 12; ledger write-point audit; deferred-method pattern audit; `NEW NAME:` consolidation into WBS §6; bugfix story creation.
- Out: fixing defects (bugfix stories `E01-B*`); architecture document changes (architect, from the consolidated list); re-planning later epics (planner, via `E02`+ refine tasks).

#### Files
| Path | Action | Public symbols |
|---|---|---|
| `docs/02-work-breakdown/EPIC-01-kernel-core.md` | modify | — (this task's Evidence; appended `E01-B*` stories) |
| `docs/02-work-breakdown/WBS.md` | modify | — (§5 status rows for E01-R01 and any `E01-B*`; §6 rows for unregistered `NEW NAME:` items) |

#### Interface contract
Reviewer protocol: `docs/00-governance/IMPLEMENTATION-PROTOCOL.md` "Reviewer protocol" steps 1–5. Checklist per story: DoD "Code", "Tests", "Documentation", "Evidence", "Delivery" boxes; per acceptance-criteria row the named test exists by exact node id and passes (`uv run pytest <nodeid>`). Bugfix stories use `docs/00-governance/STORY-TEMPLATE.md` with `**Type:** bugfix`, `**Depends on:** E01-R01` and a severity line in Notes (`Severity: BLOCKER | MAJOR | MINOR`).

#### Behavior
1. For every story S01–S31: `git show --stat <sha>` touches only Files-table paths (or the commit body justifies extras); public symbols match the Interface contract (no extra public names); every acceptance test exists by exact node id and passes; coverage ≥ 90 % for touched modules and ≥ 85 % overall (`uv run pytest --cov=walk --cov-report=term-missing`); Evidence section filled; Status and WBS row updated in the same commit; commit subject matches the story's `Commit subject:` line and COMMIT-POLICY.
2. Invariant 1 (Role ≠ Model): `lint-imports` and `ruff check` clean (SDK confinement); no module under `src/walk/model_router/adapters/` branches on `AgentInput.role` or reads `AgentInput.constitution` except to render the system prompt through the injected builder; the gate test `test_role_is_independent_of_model` passes.
3. Invariant 2 (Project Knowledge ≠ Model Context): no code outside `src/walk/memory/` writes under `.ai/` except the kernel lock file and `kernel.db` (grep for `.ai` path joins combined with `write_text`, `open(`, `replace(`); adapters never emit reasoning content (E01-S19/S21/S22 tests); `TEXT` events are never persisted (E01-S27 AC 6).
4. Invariant 9 (auditable): every `LedgerManager.append` call site maps to a row of ARCHITECTURE §4.3 or to a documented exception (E01-S25 `CHECKPOINT_CREATED` in `CheckpointManager`, E01-S28 `RecoveryManager`, E01-S29 `PROJECT_STARTED`); `telemetry/repository.py` contains no UPDATE/DELETE; the immutability triggers exist; `test_ledger_complete_and_immutable` passes.
5. Invariant 12 (continuity): all six `CheckpointKind` values are produced by some test; every WIP commit carries the `Walk-Work-Item` trailer; the fallback gate test and the E01-S28 recovery tests pass; handover documents contain the ten §22 sections.
6. Deferred-method pattern (E01-S29 Notes): every `ConfigError("implemented in <ID>")` in `src/` names an ID present in WBS §5; no `NotImplementedError`, bare `pass` or `...` bodies in `src/walk/` outside `Protocol` classes.
7. Consistency checks that the stories delegated to this review: E01-S27 `expected_output_for` and E01-S18's purpose → status table agree; the composition root is the only multi-`service.py` importer (E01-S30 AC 4).
8. `NEW NAME:` consolidation: every `NEW NAME:`/`RELOCATE:` item in this epic's Notes appears in WBS §6 (add missing rows with "Where introduced"); the architecture inconsistencies reported in E01 Notes (E01-S22 `SubprocessRunner` vs `model_router` imports, E01-S26 `ToolSpec.requires_network`, E01-S27/S28 protocol deltas and E02-S08 checkpoint duplication, E01-S28 `ModelRouter.fallback` signature, E01-S29 `PROJECT_STARTED` write point, E01-S31 `sqlite3` confinement) are listed in this task's Evidence as one table for the architect.
9. Each defect → one `E01-Bnn` story, linked from this task's Evidence; `BLOCKER` when it breaks the gate, an invariant or the quality gate on `main`. E02 may start only when no `BLOCKER` is open (WBS §2 rule 2).
10. Commit `docs: review epic 01 stories s01-s31 (E01-R01)` and push.

#### Acceptance criteria
| # | Given / When / Then | Test |
|---|---|---|
| 1 | Given each story commit, When diffed against its Files table, Then no unlisted file without justification | manual checklist recorded in Evidence |
| 2 | Given each acceptance row of S01–S31, When `uv run pytest <nodeid>`, Then the test exists and passes | manual checklist recorded in Evidence |
| 3 | Given `main` after E01-S31, When `scripts/check.sh` runs, Then green with coverage ≥ 85 % overall | manual checklist recorded in Evidence |
| 4 | Given the gate scenario, When run, Then role and model are independent across the fallback (Invariant 1) | `tests/e2e/test_e01_gate.py::test_role_is_independent_of_model` |
| 5 | Given the gate ledger, When inspected, Then complete and immutable (Invariant 9) | `tests/e2e/test_e01_gate.py::test_ledger_complete_and_immutable` |
| 6 | Given the fallback run, When inspected, Then continuation does not depend on the provider session (Invariant 12) | `tests/e2e/test_e01_gate.py::test_continuation_does_not_depend_on_session` |
| 7 | Given ARCHITECTURE §2.2, When compared with the import contracts, Then every forbidden edge is enforced | `tests/test_import_contracts.py::test_contracts_match_dependency_table` |
| 8 | Given the `.ai/` write audit, the write-point audit and the deferred-method audit, Then findings are recorded (or "none") per Behavior 3, 4, 6 | manual checklist recorded in Evidence |
| 9 | Given every `NEW NAME:` item in EPIC-01, Then each has a WBS §6 row and the architect table is in Evidence | manual checklist recorded in Evidence |

#### Evidence required
- Gate output of the full suite on `main` after E01-S31 (`scripts/check.sh` summary lines incl. `lint-imports`).
- Table in Evidence: story → sha → DoD result → defects (ids).
- Audit results for Behavior 2–7 (command used + result).
- Architect table (Behavior 8) and the list of `E01-B*` stories with severities.
- Demo transcript on a scenario repo: `walk status --json`, `walk ledger query --kind MODEL_FALLBACK`, `walk run --once` on a repo with no ready work (`started 0 run(s)`).

#### Notes
- Reviewer must be a different agent instance/model than the implementer of ≥ 50 % of E01 stories (IMPLEMENTATION-PROTOCOL "Reviewer protocol", §23).
- Do not fix in place; create `E01-B*` stories. Planning-level inconsistencies (wrong story ID references, missing Files rows in later epics) are reported to the planner in Evidence, not turned into bugfix stories.
- Commit subject: `docs: review epic 01 stories s01-s31 (E01-R01)`.

#### Evidence (filled by implementer)
_pending_

