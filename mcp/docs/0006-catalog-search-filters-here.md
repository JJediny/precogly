# 0006: Catalog searches filter here, not at the viewset

Status: accepted
Date: 2026-08-01
Relates to: [0002](0002-tool-implementation-order.md),
[0005](0005-code-execution-over-tools.md), precogly/precogly #208, #261, #265, #266

`search_threat_library`, `search_countermeasure_library` and `search_component_library`
fetch a whole catalog and filter it in the tool body. No argument is forwarded as a query
parameter; the request is a bare `GET` every time.

Measured against a stack at `precogly@09900cc`.

## Why

The viewsets offer two filtering surfaces and neither answers the question the tools exist
to answer.

`?search=` is a DRF `SearchFilter` over `search_fields`, which on the threat library is
`name` and `description` (`apps/threats/views.py:91`). Every row already serializes its
`taxonomy_entries`, and no server-side search reaches them — `?search=CWE-20` and
`?search=Improper Input Validation` both return 0 against a catalog where nine threats are
mapped to CWE-20. That is #265, and it is the single most useful question the threat
catalog can be asked.

The rest is hand-rolled: nine parameters read straight out of `query_params` in
`get_queryset` across eight list routes, absent from the published schema because
`filterset_fields` is empty where they live and drf-spectacular has nothing to introspect
(#261). `?threat_model=abc` returns 500 on six of them, uncaught from Django's field
coercion (#266). `?component_id=99999` silently returns the whole catalog.

What makes filtering here affordable is #208. The catalogs set `pagination_class = None`,
so one request is the whole thing:

```text
threat-library          33 rows   38 KB   ->  22 KB projected
countermeasure-library  46 rows  7.8 KB
component-library       10 rows  3.1 KB
```

## Identifiers match in full

`SearchFilter` is `icontains` and cannot be told otherwise. `CWE-20` under it returns 17
threats where 9 are mapped to CWE-20; the extras are mapped to CWE-200 and CWE-201. Those
are not near-misses a caller can spot — CWE-200 is Exposure of Sensitive Information, an
unrelated weakness — so an agent asked "what are we exposed to under CWE-20" gets eight
wrong answers with nothing marking them wrong.

So a taxonomy `external_id` is compared in full, case-insensitively, and every other field
is a case-insensitive substring. Measured across the catalog, the two rules differ on
exactly the identifier queries: `injection`, `tampering`, `T1190` and `AML.T0051` return
the same rows either way, and `injection` returns the same 8 rows as `?search=injection`.

This is the one place where filtering here is not merely equivalent to the server but
better, and it would still be better after #265 lands, because #265 adds those fields to
`search_fields` and `search_fields` is `icontains`.

## Trade-offs

- **This is the linear scaling [0005](0005-code-execution-over-tools.md) warned about,
  relocated.** A tool that fetches a catalog and filters it in its body is a hardcoded
  instance of what generated code would do: every question shape has to be chosen in
  advance, written here, and given a tool slot. Three of the nine-tool budget are now
  spent. The counter is that these three cover the catalog questions that exist, and 0005
  names the trigger for reconsidering rather than a date.
- **38 KB crosses the wire for a query that returns 5 KB.** Free over loopback and not
  free once the MCP server and Precogly are not co-located, which
  [0003](0003-oauth-authorization-server.md) leaves open. #99 — full CWE, CAPEC, ATT&CK
  and ATLAS packs — is what makes this stop being cheap, and the fallback is the
  server-side filters this document declines to depend on.
- **`search_countermeasure_library` is strictly weaker than `?search=` and cannot be
  fixed here.** `CountermeasureLibraryListSerializer` omits `description`
  (`apps/threats/serializers.py:145`) while `search_fields` includes it, so the server can
  match a field it never sends. A query matches the name and nothing else, and an agent
  searching for a mechanism cannot tell a real absence from this one. The description says
  so. Adding `description` to the list serializer is the fix and it belongs upstream.
- **Narrowing to a threat model's connected packs is given up.** `?threat_model=` does
  that on all three catalogs and is the most useful of the nine undeclared parameters. It
  cannot be reproduced here without a second call to learn which packs a model connects,
  and it is one of the six routes that 500 on a non-numeric value. Worth revisiting when
  #266 lands, at which point it is a filter arriving on a tool that already exists.
- **Nothing bounds the result.** A query matching every row returns every row. That is the
  same bet as the fetch — it holds while the catalogs are small, and #99 is what ends it.
