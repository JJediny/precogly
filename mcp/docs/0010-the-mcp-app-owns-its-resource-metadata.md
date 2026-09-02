# 0010: The MCP app owns its resource metadata

Status: accepted
Date: 2026-08-13
Relates to: [0008](0008-the-mcp-server-runs-inside-precogly.md), [0003](0003-oauth-authorization-server.md)

Precogly's URLconf serves the RFC 8414 authorization-server metadata. The MCP app serves
the RFC 9728 protected-resource document for `/mcp`. django-oauth-toolkit's
protected-resource patterns are not routed at all.

## Context

`config/urls.py` mounted `oauth2_provider.urls.metadata_urlpatterns` at the origin root,
because RFC 8414 puts the authorization-server document there and strict clients look
nowhere else. That name covers four patterns, not one:

```text
  .well-known/oauth-authorization-server                RFC 8414
  .well-known/oauth-authorization-server/<issuer_path>  RFC 8414
  .well-known/oauth-protected-resource                  RFC 9728
  .well-known/oauth-protected-resource/<resource_path>  RFC 9728
```

The MCP app registers the last of those for itself. `AuthSettings.resource_server_url` is
what fixes where RFC 9728 puts the document, so mounting the endpoint at `/mcp` puts its
document at `/.well-known/oauth-protected-resource/mcp` — a path Django's URLconf already
claimed.

Both were served, and which one a client saw was decided by the path check in
`config/mcp_mount.py`, which dispatches to the MCP app before Django sees the request.
Measured against the seeded stack at `precogly@c53f4d3`, same path, same Host:

```text
  Django                                      the MCP app
  ------                                      -----------
  resource:              .../mcp              resource:              .../mcp
  authorization_servers: [".../o"]            authorization_servers: ["..."]
  scopes_supported:      ["read", "write"]    scopes_supported:      ["read"]
```

Django's document is not wrong. Its issuer is discoverable —
`/.well-known/oauth-authorization-server/o` resolves, as does the root form — so a client
following it reaches the same authorization server by a different name.

The scopes are the substantive disagreement. In a protected-resource document
`scopes_supported` is a claim about what *this resource* requires, and what the endpoint
requires is `AuthSettings.required_scopes`, which is `["read"]` and which its token
verifier enforces on every call. Django builds the list from `OAUTH2_PROVIDER["SCOPES"]`,
which describes what the authorization server can issue. So the endpoint advertised
`write`, and there is no write tool.

Note when re-measuring: Django's version builds absolute URLs from the request, and
Django's test client sends `Host: testserver`. Without `SERVER_PORT`/`HTTP_HOST` set to
match, the two documents also appear to disagree about the port, which is an artifact of
the probe rather than a difference between them.

## Decision

`config/urls.py` includes only the two `oauth-server-metadata` patterns, selected by name
from `metadata_urlpatterns`. The MCP app keeps its own document.

The reason to put it that way round rather than the other is that `AuthSettings` supplies
both halves: the `scopes_supported` in the published document and the `required_scopes`
the verifier applies. One object, so they cannot drift. Django's copy was assembled from
different settings by different code, which is how it came to advertise a scope the
endpoint has no tool for.

`test_django_does_not_answer_for_a_protected_resource` pins the absence, so restoring
`metadata_urlpatterns` wholesale fails rather than quietly reinstating the second
document.

## Rejected

- **Letting Django own the document and suppressing the SDK's route.** It would mean
  either not using `streamable_http_app`, which builds the route, or intercepting that
  path in the WSGI dispatch and passing it to Django. The published claims would then come
  from `OAUTH2_PROVIDER` while enforcement stayed in `AuthSettings` — the same two sources
  of truth as before, without the collision that made them visible.

- **Leaving both mounted and relying on the dispatch order.** It works today. It fails
  silently the moment anyone reorders the path check in `config/mcp_mount.py`, mounts the
  MCP app under a prefix, or serves `/mcp` from somewhere else: a client would start
  reading a document with different scopes, and every test would still pass.

- **Deriving Django's document from the same settings** so the two agree by construction.
  More machinery than deleting two URL patterns, and it leaves two code paths producing
  one document.

## Trade-offs

- **Precogly cannot advertise another protected resource without restoring those
  patterns**, and would then have to exclude `/mcp` specifically. There is no other
  protected resource today. If `/api/` becomes one, this decision is what to revisit.

- **The document's shape now lives in a dependency.** The MCP SDK builds it from
  `AuthSettings`, so a field the specification adds arrives with an SDK upgrade rather
  than with a change here, and anything Precogly wants to say in that document has to be
  expressible through `AuthSettings`.

- **The test pins an absence.** It passes whenever those paths 404, including for reasons
  that have nothing to do with this decision — the URLconf being broken, say. The
  positive half of the claim, that the MCP app answers with the right scopes, is measured
  over HTTP against a running stack and is not in the Django test suite, because the app
  is dispatched to before Django and a Django test client cannot reach it.
