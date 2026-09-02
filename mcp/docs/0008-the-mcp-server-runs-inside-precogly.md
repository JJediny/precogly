# 0008: The MCP server runs inside Precogly

Status: accepted
Date: 2026-08-11
Relates to: [0003](0003-oauth-authorization-server.md), [0004](0004-where-the-user-authorizes.md)
Supersedes: the resource-server topology in [0003](0003-oauth-authorization-server.md) —
the separate process, introspection over HTTP, and the transport move

The MCP endpoint is served from Precogly's own WSGI process, at `/mcp`. A token is
verified by reading django-oauth-toolkit's tables directly, and a tool acts on the user
that token resolves to rather than by forwarding the token onward.

## Context

[0003](0003-oauth-authorization-server.md) settled that Precogly issues the tokens. It
also assumed, without weighing it, that the MCP server is a separate process — a resource
server that introspects over HTTP and holds no credential of its own. Those two claims do
not both survive: introspection requires the resource server to authenticate itself, and
django-oauth-toolkit's `/o/introspect/` takes HTTP Basic client credentials
(`ClientProtectedResourceMixin`, "HTTP Basic Auth, Client Credentials and Access token in
that order"). A separate process needs a client id and secret provisioned into every
deployment.

That cost lands on self-hosters, and the topology had never been costed against them.
The comparison that decides it is GitLab, which is open-core, self-managed, and ships an
MCP server: it is mounted inside GitLab at `/api/v4/mcp`, same origin as its own
authorization server, and a self-managed operator enables it with settings rather than by
provisioning credentials.

Two facts made co-location cheap enough to take:

- **Streamable HTTP no longer requires streaming.** Revision 2026-07-28 removed the GET
  stream endpoint and protocol-level sessions. A server must expose one POST endpoint and
  may answer a request with `application/json` instead of an SSE stream. Plain
  request/response is what WSGI already carries, so Precogly does not move to ASGI.
- **Nothing in Precogly streams today.** No `StreamingHttpResponse` and no
  `text/event-stream` anywhere in `apps/` or `config/`, so no existing behaviour depended
  on the alternative.

## Decision

**Serve `/mcp` from `config/wsgi.py`.** `config/mcp_mount.py` dispatches `/mcp` and
`/.well-known/oauth-protected-resource/mcp` to the MCP app and everything else to Django.
The MCP app is Starlette; a2wsgi bridges it, and its ASGI lifespan is started once on
a2wsgi's persistent loop. That last part is not optional — the transport's session
manager runs a task group started by lifespan, and a bridge that only dispatches requests
leaves every call failing with "Task group is not initialized".

**Verify tokens against the database, not over HTTP.** `apps/core/mcp.py` looks a token up
by checksum, checks validity, and checks the audience. Sharing a process is what removes
the credential: there is nothing to provision, rotate, or leak.

**Check the audience explicitly rather than through `allows_audience()`.** That helper
returns True for a token carrying no resource indicator at all, and matches by URL prefix.
Both are wrong for this endpoint, which wants exact membership. The MCP specification
makes audience validation a MUST.

**Tools act on the resolved user, not on the caller's token.** This is the part that is
easy to get backwards. Audience binding means a token issued for `/mcp` is *by
construction* invalid at `/api/threat-models/` — django-oauth-toolkit enforces it with
`validate_resource_as_url_prefix`, its default validator. Forwarding the caller's token to
Precogly's own API cannot work and should not: it is what a *remote* MCP server does
because it has no alternative. GitLab spends the token once at the boundary, resolves
`current_user`, and hands that to the tool (`lib/api/mcp/handlers/call_tool.rb`).

Tools therefore read Precogly through a data-access protocol defined in `precogly_mcp` and
supplied by the caller, the same seam the token verifier uses. Precogly implements it over
the ORM; the existing HTTP client implements it for stdio. The tools' filtering and
validation are unchanged, and no translation layer is needed — the models set
`populate_by_name`, so DRF's serializer output validates as-is.

## Rejected

- **Widening the audience to the origin**, so one token is valid at both `/mcp` and the
  API. One line, and it would have made the current tools work untouched. Rejected because
  it spends the property that makes the binding worth having, and because
  `/.well-known/oauth-protected-resource` at the origin root is already served by
  django-oauth-toolkit with different contents — two documents claiming one path.

- **Moving Precogly to ASGI** and mounting the MCP app there. The diff is about forty
  lines across `config/asgi.py`, the Dockerfile, and requirements. Rejected on blast
  radius rather than size: 48 view classes over 30,000 lines, none of them written for
  async, would move onto a different concurrency substrate, and proving that free means
  re-verifying every request path in the product for one beta feature.

- **Rewriting the MCP server in another language.** It forecloses co-location entirely —
  another runtime is another process — so it reinstates the credential this decision
  removes. It would matter only if the separate topology came back, where a single static
  binary is genuinely easier for a self-hoster than a Python service.

## Trade-offs

- **`precogly_mcp` fixes ship on Precogly's release train**, and the server can no longer
  be run standalone against a Precogly it is not deployed inside. Thin in practice: anyone
  self-hosting deploys both halves anyway.

- **Two implementations behind four tools**, one over the ORM and one over HTTP, for as
  long as stdio is supported. Stdio is the pre-OAuth shape and the intended end state
  drops it; until then it is a second code path and a second set of tests.

- **The bridge is machinery in the request path.** a2wsgi plus a hand-started lifespan is
  infrastructure that has to be understood before it can be changed, and it is load-bearing
  for every MCP request. The alternative was the ASGI migration above.

- **No streaming, ever, without revisiting this.** Not a preference: an SSE response
  carries `Connection: keep-alive`, which PEP 3333 forbids as hop-by-hop, so a streaming
  response raises inside the WSGI server and returns 500. The mount answers GET and DELETE
  on `/mcp` with 405 for that reason as much as for the specification's. A tool therefore
  cannot report progress while it works; none of the four does, and the catalogs are small
  enough that none is likely to.

## Deferred

- **A dedicated `mcp` scope.** Tokens are issued `read` today, the same scope any other
  OAuth client of Precogly would get. GitLab mints an `mcp` scope whose tokens are usable
  only with MCP tools. Worth copying: it makes "who has MCP access" legible, and it stops
  a replay at the REST API even if audience checking were relaxed.

- **Per-user MCP access control.** Belongs in the verifier, where the token is already
  resolved to a user, and is where GitLab puts its own feature and permission checks.

- **Submoduling this repository into precogly/precogly.** The intended end state. Nothing
  here blocks it, and the seams are drawn so that Django stays on Precogly's side of them.
