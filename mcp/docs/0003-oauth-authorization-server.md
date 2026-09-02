# 0003: Precogly is the authorization server

Status: partially superseded by [0008](0008-the-mcp-server-runs-inside-precogly.md)
Date: 2026-07-29
Relates to: precogly/precogly discussion #221 ("MCP for Precogly"),
[0001](0001-service-token-model.md)
Supersedes: token issuance and capability representation in [0001](0001-service-token-model.md)

The authorization server is as decided here, and so is everything about who issues tokens
and how a user gets one. The resource server is not: the separate process, introspection
over HTTP, the claim that the MCP server holds no credential of its own, and the move to a
standalone `streamable-http` service are all superseded by
[0008](0008-the-mcp-server-runs-inside-precogly.md).

Precogly becomes an OAuth 2.1 authorization server. The MCP server is a resource server: it
validates bearer tokens, serves protected-resource metadata, and holds no credential of its
own. A user authorizes it by logging into Precogly in a browser, the same way the Atlassian
MCP server works.

## Context

[0001](0001-service-token-model.md) assumed an unattended daemon. Its opening context —
"an agent running unattended has no way to complete the refresh dance" — is what ruled out
an interactive flow and led to a bespoke service token pasted into a config file.

That premise was wrong about the product. The user connects a client, is sent to a login
page, and approves access. That is an attended, delegated authorization, which is what the
authorization code grant is for. A service token issued from a settings page solves a
problem this product does not have.

Three roles have to be filled, and only one of them is new work:

```text
  MCP client                 authorization server            resource server
  (Claude Code)              (Precogly, django-oauth-        (precogly-mcp)
                              toolkit)
       |                              |                              |
       |------ tools/call ------------|----------------------------->|
       |<----- 401 + WWW-Authenticate: resource_metadata ------------|
       |                              |                              |
       |-- GET /.well-known/oauth-protected-resource --------------->|
       |-- POST /register (RFC 7591) ->|                             |
       |-- browser: /authorize + PKCE ->|  user logs in, consents    |
       |<- redirect localhost/callback?code=...                      |
       |-- POST /token, resource=<mcp uri> (RFC 8707) -->|           |
       |------ tools/call + Bearer ----------------------------------|--> introspect
```

The client half is free — Claude Code already does all of it, which is how the Atlassian
integration works in practice. The resource-server half is small: the SDK takes a
`token_verifier` and runs `BearerAuthBackend` for you
(`mcp/server/mcpserver/server.py:1129`). The authorization server is the whole cost, and it
lands upstream in Precogly.

## Why django-oauth-toolkit

Precogly has no OAuth infrastructure today — `rest_framework_simplejwt` with `dj-rest-auth`
and allauth's account middleware, and no OIDC or OAuth package anywhere in the backend.

django-oauth-toolkit 3.4.0 (2026-07-23) added the three specs MCP authorization depends on,
in one release:

- **RFC 7591 / 7592** — `DynamicClientRegistrationView`, so a client registers itself
  rather than every user hand-registering a client ID.
- **RFC 8707** — the `resource` parameter, binding an issued token to this MCP server so a
  token minted for it cannot be replayed against another Precogly client.
- **RFC 9728** — the `/.well-known/oauth-protected-resource` endpoint the client fetches
  after a 401.

It also ships `/introspect/` and a separate-resource-server mode
(`RESOURCE_SERVER_INTROSPECTION_URL`, `RESOURCE_SERVER_AUTH_TOKEN`), which is the
introspection contract 0001 already designed against.

## What survives from 0001

The parts of 0001 that were about the resource server, not about issuance, are unchanged:

- **Introspection on every request.** The token stays opaque to the MCP server and is
  exchanged for identity per request, with the same caching and the same immediate
  revocation.
- **Explicit organization.** Tools take an `organization_id` argument validated against the
  introspected value rather than trusted. This still closes the `.first()` hole at
  `apps/threat_models/views.py:896`, and still needs no adapter change.
- **Role is advisory for listing, never authoritative for access.** It decides which tools
  appear in the menu. The API's permission classes remain the authorization boundary.
- **The process-level read-only flag** is still a property of this process with no
  counterpart in the API, so write-tagged tools are still rejected in the call handler and
  not merely hidden from `tools/list`.
- **No ambient service account.** The authorization code grant strengthens this: every
  token is user-delegated by construction, so the confused-deputy shape 0001 avoided by
  policy is now avoided by the protocol.

## What 0003 changes

- **Issuance.** A token is obtained through an authorization code grant with PKCE, not
  created in a settings page and pasted into a config file.
- **Capability representation.** The single write bit becomes an OAuth scope. 0001 accepted
  the coarse bit on the grounds that a real scope vocabulary would be purely additive; the
  authorization server makes scopes native, so the write bit has no reason to exist as a
  bespoke field.
- **Transport.** The server moves from stdio to HTTP. Browser-redirect authorization has no
  meaning for a subprocess speaking over a pipe, and the MCP specification directs stdio
  servers to take credentials from the environment instead.

[0002](0002-tool-implementation-order.md) is unaffected. Tool bodies do not depend on the
transport; only the auth layer does.

## Trade-offs

- **Precogly must run an authorization server.** This is a backend project, not a task, and
  it blocks `list_threat_models` — the tool 0002 chose precisely because nothing else about
  it was unresolved. Accepted because the alternative that avoids it is worse: making the
  MCP server the authorization server would give it a credential store, a datastore, and a
  security-critical role, contradicting the property that it holds no credential of its own.

- **django-oauth-toolkit 3.4.0 is six days old.** The three RFCs this design leans on all
  landed in that release, so adopting it means being an early user of new code in an auth
  path. Mitigated by the fallback being unattractive rather than by the risk being small:
  hand-rolling DCR and resource indicators is strictly worse than using a new implementation
  of them.

- **The demo agent in #221 becomes attended.** An unattended run now needs a client
  credentials grant, which the authorization server can issue but which is a second flow
  rather than a free consequence of the first.

## Deferred

- **Client credentials for unattended runs.** The SDK has
  `mcp/client/auth/extensions/client_credentials.py` and django-oauth-toolkit supports the
  grant. Needed only when something runs without a person present.

- **SSO.** 0001 recorded SSO as the event that would make service tokens a client
  credentials grant against an external issuer. With Precogly as the authorization server
  the question becomes whether it federates to an IdP or is replaced by one. The RFC 7662
  response shape still absorbs either.

- **Consent-time organization selection.** Organization is an explicit tool argument today.
  Choosing it during consent, and binding it into the token, would remove the argument
  entirely — worth doing once there is a real multi-org user to test against.
