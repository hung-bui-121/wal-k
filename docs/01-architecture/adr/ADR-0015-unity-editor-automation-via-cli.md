# ADR-0015 — Unity Editor Automation via Batchmode CLI (Unity MCP Rejected)

**Status:** Accepted (owner decision 2026-10-06)
**Date:** 2026-10-06
**Deciders:** Project owner, system architect
**Related requirements:** §30, §31, §62, §79, §129, §137 (Inv. 7, 9, 11); ADR-0006 D-1/D-2, ADR-0009 D-6, ADR-0017

## Context

ADR-0009 D-6 put Unity automation on the batchmode CLI (`com.walk.ci`) and deferred Unity MCP to Stage 8 "as an additional `ToolKind.MCP` provider". E08-S08 needs three read-only inspection capabilities for reviewing agents (ART_DIRECTOR, DESIGN_LEADER, LEAD_DEV, QC): a rendered screenshot of a scene or prefab, the Unity console (import/compile log entries), and a structured description of an asset. An earlier `Proposed` draft of this ADR (same number, never accepted) delivered them through the open-source MCP for Unity server and an in-house stdio JSON-RPC client.

On 2026-10-06 the owner decided that Unity Editor automation uses the Unity CLI, not MCP. This ADR records that decision and the shape of the CLI-based inspection capabilities.

## Decision

**D-1 One Unity automation path: batchmode CLI.** Every kernel interaction with the Unity Editor — compile, EditMode/PlayMode tests, build (E03-S10), asset validation (E08-S06) and the three inspection capabilities (E08-S08) — runs the editor in batchmode through `UnityBatchProvider` with `-executeMethod WalK.CI.<Method>` from the kernel's `com.walk.ci` editor package, and reads the JSON `UnityResultFile` written to `-walkResult`. No MCP server, no editor-side bridge and no running interactive editor is required.

**D-2 Inspection capabilities.** Each capability is one `UnityProvider` method, one `WalK.CI` static method and one KERNEL tool:

| Capability | `UnityProvider` method | C# method | Kernel tool | `JobResult.job_kind` | Evidence |
|---|---|---|---|---|---|
| Screenshot of a scene or prefab | `capture_screenshot` | `WalK.CI.CaptureScreenshot` | `unity.screenshot` | `screenshot` | `SCREENSHOT` |
| Console capture (import + compile log entries) | `capture_console` | `WalK.CI.CaptureConsole` | `unity.console` | `console` | `LOG` |
| Asset inspection | `inspect_asset` | `WalK.CI.InspectAsset` | `unity.inspect_asset` | `asset_inspection` | `PROJECT_DATA` |

Command-line arguments follow the `-walk*` convention of E03-S10/E08-S06: `-walkResult` (all), `-walkTarget <repo-relative .unity or .prefab path>`, `-walkCamera <GameObject name>`, `-walkResolution <W>x<H>`, `-walkPreviewDir <dir>` (reused from E08-S06), `-walkLogTypes <Error,Warning,Log>`, `-walkMaxEntries <n>`, `-walkAssets <comma-separated paths>` (reused from E08-S06). Exact signatures: E08-S08.

**D-3 Read-only by construction.** The three C# methods never call a save API (`EditorSceneManager.SaveScene`, `AssetDatabase.SaveAssets`, `PrefabUtility.SaveAsPrefabAsset`); temporary objects (preview camera, prefab instance) live in a new unsaved scene that is discarded. The only side effect is the import cache under `Library/`. None of the three tools is a protected action (ADR-0006 D-3).

**D-4 Kernel-executed, single enforcement point.** The tools are `ToolKind.KERNEL` rows in `tools.yaml` (provider `unity`, `requires_env: [unity]`, like `unity.compile`) authorised and metered by `ToolInvoker.invoke` (ADR-0006 D-1); the handler runs Unity against the calling run's worktree and records evidence (ADR-0006 D-2). Agents never start Unity themselves for inspection. Permission defaults: ALLOW for ART_DIRECTOR, DESIGN_LEADER, LEAD_DEV and QC; every other role falls to default deny.

**D-5 Graphics device.** `CaptureScreenshot` runs without `-nographics` (as E08-S06 previews do). Without a graphics device the C# method writes `ok=false, summary="no graphics device"`; the tool returns `ok=false` — never an exception.

**D-6 One Unity process per project path.** Unity locks a project (`Temp/UnityLockfile`). Inspection runs on the agent run's worktree, never on the main checkout. A lock collision (an editor already open on that path) yields a missing result file → `UnityJobFailed` (E03-S10 Behavior 3), which the handler returns as `ok=false` with the log tail.

**D-7 `ToolKind.MCP` stays reserved.** The enum member remains in DOMAIN-MODEL §3 with no Stage 8 provider. Any MCP-based Unity integration later needs a new ADR that supersedes this one. Remote MCP for a non-Unity provider is a separate decision (ADR-0017).

## Alternatives considered

- **MCP for Unity (`CoplayDev/unity-mcp`) through an in-house stdio JSON-RPC client** (the earlier `Proposed` draft) — rejected by owner decision. It adds a second runtime process (the Python MCP server) and an editor-side bridge package on every machine, needs a running interactive editor (not deterministic, not usable in headless CI), introduces a second Unity integration path to maintain next to `com.walk.ci`, and binds kernel tools to a third-party server's tool names and `action` selectors that change between releases.
- **MCP for Unity through the `mcp` Python SDK** — rejected for the same reasons; the SDK being adopted for OpenArt (ADR-0017) does not change them, because OpenArt has no CLI alternative and Unity does.
- **Agents connect to a Unity MCP server directly** (Claude SDK `mcp_servers`) — rejected: bypasses the kernel enforcement point (ADR-0006 D-1), cannot be offered to Codex (Invariant 1 parity), and images would not become evidence.
- **Console capability as a Python tail of the last Unity job log** — rejected: the last log belongs to an unrelated job, is unstructured, and may not exist in a fresh worktree; a dedicated import/compile pass gives structured entries for the current worktree state.

## Consequences

- No `walk/integrations/unity_mcp/` package, no MCP server process, no Unity MCP row in `ARCHITECTURE.md` §2.3; ADR-0009 D-6's Stage 8 MCP deferral is closed by this ADR.
- Latency: every inspection call starts a batchmode editor (seconds to minutes; the first open of a fresh worktree imports the whole project into `Library/`). Calls are bounded by a tool timeout (E08-S08) and agents are told to batch paths into one `unity.inspect_asset` call. Live editor state (play mode, unsaved edits) is not observable — accepted: reviewers judge the committed worktree state, which is what gets approved.
- E08-S08 is rewritten as "Unity inspection tools via batchmode CLI"; it extends INTERFACES §2.4 (`UnityProvider` methods, `JobResult.job_kind` values), `UnityResultFile.job`, `com.walk.ci` and `FakeUnityProvider`.
- One fewer runtime dependency and process to install, configure and keep running on each machine; Unity work stays reproducible in CI.
