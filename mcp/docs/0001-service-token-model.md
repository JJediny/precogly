# 0001: Service token model

Status: partially superseded by [0003](0003-oauth-authorization-server.md)
Date: 2026-07-28
Relates to: precogly/precogly discussion #221 ("MCP for Precogly")

Token issuance, the write bit, and the unattended-daemon premise are superseded. The
introspection contract, explicit organization scoping, advisory role, and the process-level
read-only flag stand as written.

The MCP server authenticates to the Precogly API with an opaque bearer token that it
introspects on every request and then forwards unchanged. It holds no credential of its
own. It can only narrow what the API would allow, never widen it: the read-only flag
refuses writes the API would have accepted, and nothing else it decides grants access the
API would have refused.

## Context

The API authenticates with `rest_framework_simplejwt` only
(`config/settings/base.py:169`): a 60-minute access token with a 7-day rotating refresh.
That is designed for a browser session and cannot drive a daemon — an agent running
unattended has no way to complete the refresh dance, and a leaked token cannot be
revoked ahead of its window.

Two further facts shape the design. The import endpoints select the organization
implicitly, via `request.user.organization_memberships.first()`
(`apps/threat_models/views.py:896`, `:975`), so a token belonging to a multi-org user
writes to whichever membership the database returns first. And SSO is planned but not
built, so whatever identity source exists today is not the identity source this will
have to work with.

## Decision

A service token is an **opaque handle**, not a self-contained JWT. It carries no claims
in its body; the MCP server exchanges it for identity by calling an introspection
endpoint on every request.

The token record binds three things:

- the **user** who created it — the token can never do more than that user can
- the **organization** it acts in, chosen explicitly at creation
- a single **write bit**, chosen at creation

The user's role travels in the introspection response, but it is **advisory for listing,
not authoritative for access**. It decides which tools the server shows; it never decides
what a call is allowed to do. It is read from the user's current membership at
introspection time rather than stored on the token, so a role change takes effect on the
next introspection and needs no reissue. The API's existing permission classes
(`apps/core/permissions.py`, and the per-view `organization_memberships` filters) run on
every request exactly as they do for a browser session, and remain the authorization
boundary.

Carrying role matters because the tool list is a menu. Several endpoints are
security-team-only — `ThreatLibraryViewSet` declares
`permission_classes = [IsAuthenticated, IsSecurityTeam]` (`apps/threats/views.py:87`) —
and an agent offered a tool it cannot reach does not reliably conclude "not for me". It
retries, rephrases, or reports the task as blocked. A menu whose items 403 is worse than
a shorter menu.

The introspection response is shaped like RFC 7662:

```json
{
  "active": true,
  "sub": "user-id",
  "client_id": "token-id",
  "scope": "write",
  "exp": 1790000000,
  "organization_id": "org-id",
  "role": "security_team"
}
```

Tools accept an explicit `organization_id` argument. The server validates it against the
introspected value rather than trusting it, and rejects a mismatch. Where the argument is
omitted, the token's organization is used. This closes the `.first()` hole without
changing the adapters, which already accept `organization` as a parameter
(`apps/threat_models/adapters/base.py:10`).

## Where filtering is enforced

The server filters the tool list on two independent inputs, and they need different
treatment at call time.

**The read-only flag is a process-level setting with no counterpart in the API.** Precogly
does not know that this MCP process was started read-only, so nothing downstream will
catch a write that slips through. Filtering it out of `tools/list` is not enough — a
client holding a cached listing, or an agent guessing a tool name, reaches a real write
path. Write-tagged tools must therefore be rejected in the call handler as well, not only
hidden from the listing.

**Role is enforced downstream on every request.** Rejecting a role-filtered tool at call
time adds no security, because `IsSecurityTeam` already refuses it. It buys a better
error: "this token's role cannot reach the threat library" instead of a bare 403 the
agent has to interpret. Worth doing for that reason alone, and for no other.

Tool listings are cached by clients. A role change mid-session leaves a stale menu until
the client reconnects, and the introspection cache widens that window.
`ToolListChangedNotification` exists in the protocol, but sending it requires noticing the
change. The call path must behave correctly against a stale menu rather than assume the
client's view is current.

## Trade-offs

- **Round-trip per request**: introspection sits in the hot path of every tool call.
  Mitigated by caching the response for the token's remaining lifetime under a short TTL,
  with revocation invalidating the cache. A self-contained JWT would avoid this entirely.
  We pay it to keep revocation immediate and to keep the identity source swappable.

- **Coarse capability**: one write bit cannot express "may import a threat model but may
  not update countermeasure status". A token that can do either can do both. Accepted
  because scopes must always be a subset of the creating user's role, which makes adding
  a real scope vocabulary later purely additive — existing tokens keep working, and
  `scope` in the introspection response is already the field it would populate.

- **No delegation**: the MCP server cannot act on behalf of a user who has not issued a
  token. There is deliberately no service account with ambient authority over an
  organization. That pattern makes the server a confused deputy, and prompt injection
  against tool inputs is an explicit concern for this feature.

## Deferred

Recorded here because each one constrains something above, not because any is scheduled.

- **Fine-grained scopes.** The `scope` field exists and carries `write` or nothing. A
  richer vocabulary (`threat-models:read`, `library:read`, `threat-models:import`) drops
  in without a schema change.

- **SSO.** When an external IdP lands it becomes the token issuer, and service tokens
  become a client-credentials grant against it. The RFC 7662 response shape is what makes
  that a configuration change rather than a second auth path — the SDK's `TokenVerifier`
  keeps the same contract either way.

- **The capability map from role to tool tags.** `role` is in the introspection response
  from the start, but the initial mapping is the single case that exists today:
  security-team-only tools are tagged, and a non-security-team token does not see them.
  A general role-to-capability table waits until there is more than one distinction to
  express.

## Not done here

Organization management tools are excluded by not being written. There is no runtime
filter for them and there should not be one — a tool that can change a member's role is
a prompt-injection target whose blast radius is not worth any workflow it enables.
