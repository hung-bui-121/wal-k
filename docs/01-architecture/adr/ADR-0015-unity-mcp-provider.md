# ADR-0015 — Unity MCP Provider and Kernel-Side MCP Client

**Status:** Proposed (owner acceptance required before E08-S08 starts; see "Acceptance checklist")
**Date:** 2026-10-06
**Deciders:** Project owner, system architect
**Related requirements:** §30, §31, §62, §79, §91, §129, §137 (Inv. 7, 11); ADR-0001, ADR-0006 D-1/D-2, ADR-0009 D-6/D-8

## Context

ADR-0009 D-6 keeps Unity automation on the batchmode CLI (`com.walk.ci`) and defers Unity MCP to Stage 8 "as an additional `ToolKind.MCP` provider". E08-S08 plans that provider: three read-only kernel tools (`unity_mcp.screenshot`, `unity_mcp.console`, `unity_mcp.inspect_asset`) executed by a kernel-side MCP client and authorised at the single `ToolInvoker` enforcement point (ADR-0006 D-1). Agents never connect to the MCP server; the kernel performs the call and turns images into `SCREENSHOT` evidence (ADR-0006 D-2).

E08-S08 cannot start until four questions are decided: (a) in-house stdio client versus the `mcp` Python SDK, (b) the default Unity MCP server and its tool names, (c) the accepted MCP protocol versions, (d) the environment passed to the server process.

## Decision

**D-1 In-house minimal client, no new dependency (recommended).** `walk/integrations/unity_mcp/client.py` implements JSON-RPC 2.0 over stdio for exactly `initialize`, `notifications/initialized`, `tools/list` and `tools/call` (E08-S08 contract). The client declares `capabilities: {}`. Server-to-client traffic: notifications are logged and skipped; a server **request** `ping` is answered with an empty result; any other server request (`roots/list`, `sampling/createMessage`, `elicitation/create`, …) is answered with JSON-RPC error `-32601` (method not found) so the server never blocks waiting for the kernel. Re-evaluate in favour of the `mcp` SDK when any of these becomes a requirement: a second MCP server, the Streamable HTTP transport, or server-initiated capabilities the kernel must honour.

**D-2 Transport and confinement.** stdio only. One server process per kernel, started lazily by `UnityMcpProvider` and re-created after `ProviderUnavailable` (E08-S08 Behavior 4); `cwd` = game repository root; stderr goes to the kernel log and is never parsed. The process and the client are confined to `walk/integrations/unity_mcp/` (`ARCHITECTURE.md` §2.3).

**D-3 Protocol version.** The client requests `MCP_PROTOCOL_VERSION = "2025-06-18"` and accepts a server answer in `MCP_ACCEPTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")`; any other answer → `McpProtocolError` and the provider reports `MISCONFIGURED`. Rationale: the four messages above and the `text`/`image` content types the client reads are unchanged across these revisions; content types the client does not know (`audio`, `resource_link`, `structuredContent`) are ignored (E08-S08 Behavior 2). A newer revision is added only after checking it against these four messages.

**D-4 Server choice: none compiled in; one reference server.** `KernelSettings.unity_mcp_command` defaults to `None` (provider disabled, E08-S08 Behavior 10); the owner configures the command per machine. The reference server for docs, the live test and the default tool bindings is the open-source **MCP for Unity** server (`CoplayDev/unity-mcp`, MIT; Unity editor package + Python stdio server), pinned to one released version recorded in this ADR at acceptance. Commercial or Unity-official servers can be used by overriding the bindings (D-5) without code change.

**D-5 Tool bindings carry fixed arguments.** A kernel tool maps to a server tool **plus fixed arguments**, because multipurpose server tools select their operation by an argument (e.g. an `action` field) and some operations are destructive:

```python
class McpToolBinding(FrozenModel):
    tool: str                                  # server tool name from tools/list
    fixed_arguments: JsonDict = Field(default_factory=dict)   # merged over caller arguments; a caller key that collides → OutputInvalid
```

`KernelSettings.unity_mcp_tool_map: dict[str, McpToolBinding]`. The fixed arguments are what makes a kernel tool read-only; the permission rule (E08-S08 Behavior 9) is written against the kernel tool name, so an agent can never reach a mutating server operation through a read-only kernel tool. Default bindings for the reference server (to be confirmed against `tools/list` of the pinned version — acceptance checklist item 2):

| Kernel tool | Server tool | Fixed arguments | Status |
|---|---|---|---|
| `unity_mcp.console` | `read_console` | `{"action": "get"}` | verify |
| `unity_mcp.inspect_asset` | `manage_asset` | `{"action": "get_info"}` | verify |
| `unity_mcp.screenshot` | — (unmapped) | — | map only if the pinned server returns MCP `image` content; a server that only writes a file into the project does not qualify (the kernel would have to read and later delete a file the agent cannot see) |

An unmapped kernel tool raises `NotSupported` and is excluded from the health check (E08-S08 Behaviors 4–5), so the provider is `READY` with two of three tools.

**D-6 Server environment.** The server process receives the E02-S01 scrubbed agent environment allowlist and nothing else: no `CredentialStore` value, no provider key. Server-specific settings (bridge port, project path) are passed as arguments in `unity_mcp_command`, not as environment variables. If a server cannot start on a platform because the allowlist lacks a system variable (e.g. `SystemRoot` on Windows), the allowlist in E02-S01 is fixed for all subprocesses instead of adding a per-server exception.

**D-7 Scope stays read-only in Stage 8.** Scene- or asset-mutating MCP operations need a new ADR that classifies them as protected actions (ADR-0006 D-3); until then no binding may target them.

## Alternatives considered

- **`mcp` Python SDK** — rejected for Stage 8: a large dependency tree (async framework, HTTP server stack, settings library) for four messages; it would require an ADR-0001 amendment and widen the §2.3 confinement surface. Kept as the upgrade path (D-1 triggers); `client.py` keeps the same public names so the swap is local.
- **Give agents the MCP server directly** (Claude SDK `mcp_servers`) — rejected: bypasses the kernel enforcement point (ADR-0006 D-1), cannot be offered to Codex (Invariant 1 parity), and images would not become evidence.
- **Plain name map `dict[str, str]`** (E08-S08 draft contract) — rejected: cannot express the operation selector of multipurpose tools, so read-only cannot be guaranteed.
- **Compile a default server command** — rejected: install location and launcher (`uv`, `uvx`, a venv) differ per machine; a wrong default yields confusing `UNKNOWN` health instead of a clear `MISSING`.
- **Replace batchmode with MCP for CI** — rejected (ADR-0009 D-6): batchmode is headless and deterministic; MCP needs a running editor.

## Consequences

- No new runtime dependency; ADR-0001 unchanged. `ARCHITECTURE.md` §2.3 gains the row "Unity MCP server process / MCP client → `walk/integrations/unity_mcp/`".
- E08-S08 contract deltas that apply when this ADR is accepted: `MCP_ACCEPTED_PROTOCOL_VERSIONS`; `McpToolBinding` and `unity_mcp_tool_map: dict[str, McpToolBinding]` (replaces `dict[str, str]`); server `ping` answered and other server requests answered with `-32601` (adds to Behavior 1); caller/fixed argument collision → `OutputInvalid` (adds to Behavior 4).
- The live test (`test_unity_mcp_live.py`) runs against the pinned reference server version.

## Acceptance checklist (E08-X01 with the owner)

1. Pin the reference server version (release tag) and record it here.
2. Run `tools/list` against it; record the tool names and the operation-selector argument values; confirm or correct the D-5 table (including whether a screenshot tool returns `image` content).
3. Confirm the MCP specification revisions in D-3 are still current; add a newer revision only after the check in D-3.
4. Confirm the server starts with the D-6 environment on the owner's OS.
5. Set **Status: Accepted** and apply the E08-S08 contract deltas listed under Consequences.
