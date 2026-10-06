# ADR-0017 — OpenArt via Remote MCP (Streamable HTTP + OAuth 2.1 PKCE)

**Status:** Accepted (owner decision 2026-10-06)
**Date:** 2026-10-06
**Deciders:** Project owner, system architect
**Related requirements:** §26, §78, §80, §84, §91, §129, §137 (Inv. 1, 11); ADR-0001, ADR-0006 D-1/D-2, ADR-0009 D-8/D-11, ADR-0015

## Context

E08-S03 (`OpenArtAssetProvider`) was `BLOCKED`: no public OpenArt REST contract could be confirmed, and endpoint guesses are not allowed. On 2026-10-06 the owner decided that OpenArt is accessed through its remote MCP server `https://mcp.openart.ai/mcp`.

Facts verified by an unauthenticated probe on 2026-10-06:

| Probe | Result |
|---|---|
| `POST https://mcp.openart.ai/mcp` without a token | `401`, `WWW-Authenticate: Bearer ... resource_metadata="https://mcp.openart.ai/.well-known/oauth-protected-resource/mcp"` |
| Protected-resource metadata (RFC 9728) | `{"resource": "https://mcp.openart.ai/mcp", "authorization_servers": ["https://openart.ai"], "bearer_methods_supported": ["header"], "scopes_supported": ["full_access"]}` |
| Authorization-server metadata `https://openart.ai/.well-known/oauth-authorization-server` | authorize `https://openart.ai/suite/api/auth/oauth/authorize`, token `.../oauth/token`, dynamic client registration `.../oauth/register`, revoke `.../oauth/revoke`; PKCE `S256`; `token_endpoint_auth_methods_supported: ["none"]` (public client); grants `authorization_code`, `refresh_token`; scope `full_access` |

Not known: the server's tool list (`tools/list` requires authentication). Tool names, arguments and result shapes must therefore be configuration discovered from `tools/list`, never written into code or docs from guesses.

## Decision

**D-1 Official `mcp` Python SDK.** The kernel uses the official `mcp` SDK — its streamable HTTP client transport, `ClientSession`, and OAuth client provider (an `httpx.Auth`). `mcp` becomes an approved runtime dependency (amends ADR-0001 / WBS §3.8), range `mcp>=1.12,<2`. The lower bound must be a release whose OAuth client discovers the authorization server through protected-resource metadata (RFC 9728), because OpenArt's authorization server (`openart.ai`) is not the resource host (`mcp.openart.ai`). E08-S10 verifies the bound and records the exact resolved version in its Evidence. The SDK negotiates the MCP protocol revision; the kernel pins none itself.

**D-2 Confinement.** `mcp` is imported only under `walk/integrations/mcp/` (generic client, OAuth glue, server registry) and `walk/integrations/assets/openart/` (adapter). The ruff `banned-api` configuration enforces this (`ARCHITECTURE.md` §2.3). Nothing outside `walk.integrations` sees an SDK type.

**D-3 Server registry as data.** A server is an `McpServerSpec` (name, URL, scope, credential names) in `walk.integrations.mcp.servers.MCP_SERVERS`; Stage 8 registers only `openart` (`https://mcp.openart.ai/mcp`, scope `full_access`). Authorization endpoints are discovered at runtime from the metadata above, not configured.

**D-4 Interactive login once: `walk auth login openart`.** OAuth 2.1 authorization code with PKCE `S256`, public client, dynamic client registration, resource indicator = the protected-resource `resource` value. The command binds a loopback listener on `127.0.0.1` with an ephemeral port, registers a fresh client whose only redirect URI is `http://127.0.0.1:<port>/callback` (re-registration on every login avoids depending on loopback-port wildcard support), opens the system browser at the authorize URL, verifies `state`, exchanges the code and stores the result (D-5). `walk auth logout openart` revokes the refresh token (best effort) and deletes the stored entries; `walk auth status openart [--tools]` reports login state and, with `--tools`, the server's `tools/list`.

**D-5 Token storage only through `CredentialStore` (OS keyring).** Two keyring-only entries (service `walk`, ADR-0009 D-8): `OPENART_OAUTH_CLIENT` (JSON of the client registration: `client_id`, `redirect_uris`, issue time — a public client has no secret) and `OPENART_OAUTH_REFRESH_TOKEN`. Access tokens are held in process memory only and never persisted, which keeps keyring entries well below the Windows Credential Manager blob limit (2560 bytes) and limits exposure. Environment variables of the same names are ignored: refresh tokens rotate, so an environment copy would go stale. No token or client registration is ever written to `.ai/`, the ledger, logs, evidence, tool results or an agent environment.

**D-6 Non-interactive kernel runs use refresh.** Inside `walk run`, `walk doctor` and tests, the OAuth provider is built with a redirect handler that raises `ProviderAuthRequired`; the kernel never opens a browser. The first request after start obtains an access token with the stored refresh token; a rotated refresh token is written back before the request continues. One MCP session per operation (initialize → one request → close); the access token is reused across sessions for the provider's lifetime.

**D-7 Expired or revoked authorization.** No stored refresh token → `health()` `MISSING` (`not logged in; run walk auth login openart`). Refresh rejected (`invalid_grant`, or `401` after a refresh) → `ProviderAuthRequired`; `health()` → `MISCONFIGURED` (`authorization expired; run walk auth login openart`); in the asset pipeline the task is `BLOCKED` with that reason and the kernel escalates to USER with `permissions.request_approval(kind="ESCALATION", approver=USER, payload={"reason": "provider_auth_required", "provider": "openart", ...})` — the same escalation path as `BLOCKED_PROVIDER` (INTERFACES §5.3). Before declaring expiry the client re-reads the stored refresh token once: when another kernel process on the same machine rotated it, the request is retried with the new token.

**D-8 Tool mapping is configuration validated against `tools/list`.** Kernel default `walk/integrations/assets/openart/openart_tools.yaml` (package data) maps the adapter's semantic operations (`generate`, optional `status`) and semantic arguments (`prompt`, `width`, `height`, …) to server tool and argument names, plus result paths and a status map. Its content is produced from a real `tools/list` by the first Behavior step of E08-S03 and recorded in that story's Evidence. A project may replace it with key `openart` in `.ai/project/asset-providers.yaml` (read-only for the kernel, same precedent as `.ai/project/asset-rules.yaml`). At preflight (`walk doctor`, `walk run` start) the provider's `health()` calls `tools/list` and checks that every mapped tool and argument exists; any mismatch → `MISCONFIGURED` naming the missing items, so `asset.generate` is not offered for OpenArt.

**D-9 Tests.** Unit tests run against an in-process fake MCP server (SDK server API over the SDK's in-memory transport) exposing the tool names recorded in `openart_tools.yaml`, and a fake OAuth authorization server served through `httpx.MockTransport`. `@pytest.mark.integration` tests run against the real server with the owner's stored login; automated live tests never call a generation tool (credits) — a live generation is an owner-run step.

## Alternatives considered

- **OpenArt REST API with an API key** — rejected: no public contract could be confirmed (E08-S03 was `BLOCKED` on it); the MCP server is the surface the owner endorses.
- **In-house streamable HTTP and OAuth client** — rejected: protected-resource and authorization-server discovery, dynamic registration, PKCE, refresh rotation and streamable HTTP sessions are a large, security-sensitive surface; the SDK is maintained with the protocol. (ADR-0015's earlier draft rejected the SDK for a four-message stdio client — a different scale.)
- **Pre-registered static client id** — rejected: the authorization server offers dynamic registration and there is no client-provisioning process.
- **Fixed loopback port** — rejected: port conflicts on developer machines; re-registering per login is cheap.
- **Agents connect to the OpenArt MCP server directly** (Claude SDK `mcp_servers`) — rejected: bypasses `ToolInvoker`, budgets, idempotency and cost records (credits would be spent uncontrolled) and is not available to Codex (Invariant 1 parity).
- **Tokens in a file under `.walk/` or `.ai/`** — rejected (ADR-0009 D-8: credentials only via environment/keyring; `.ai/` never stores secrets).

## Consequences

- New runtime dependency `mcp` with its transitive tree (`anyio`, `httpx-sse`, `starlette`, `uvicorn`, `pydantic-settings`, …); `claude-agent-sdk` (optional extra) already depends on `mcp`, so the tree is not new for Claude-enabled installs (E08-S10 verifies this at the pinned versions).
- ADR-0009 D-8 replaces the former OpenArt API-key credential with `OPENART_OAUTH_CLIENT` and `OPENART_OAUTH_REFRESH_TOKEN`; `CredentialStore` gains a keyring write path (`set`/`delete`) restricted to keyring-only names (E08-S10).
- New CLI group `walk auth` (`login`, `logout`, `status`).
- Work breakdown: E08-S10 (MCP client and OAuth login) precedes E08-S03 (OpenArt adapter over MCP); E08-S03 is unblocked.
- If OpenArt changes its tool surface, `walk doctor` reports `MISCONFIGURED`; a project override restores service without a kernel release.
- Keyring entries are machine-wide (service `walk`), so all projects on a machine share one OpenArt login; D-7's re-read handles refresh rotation between two kernel processes.
