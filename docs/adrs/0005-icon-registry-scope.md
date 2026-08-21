# ADR 0005 — Icon registry scope (curated brands vs. lazy full catalog)

- **Status:** Proposed
- **Date:** 2026-08-19
- **Deciders:** TBD
- **Depends on:** [0001 — Override layers](0001-icon-override-layers.md)

## Context

The POC ships a **curated registry**
(`frontend/src/lib/pack-icons.ts` → `PACK_ICON_REGISTRY`) that maps a
finite set of slugs (`aws`, `azure`, `gcp`, `github`, `microsoft`, …)
to explicit `@thesvg/react` components. `PackIcon` looks up the slug
and renders that component; unknown slugs fall back to a lucide
`Package` icon.

Two competing pressures now apply:

- **Coverage:** `@thesvg/react` publishes 3000+ brand SVGs. Every
  request to add "just my company's logo" hits the wall of the
  curated list.
- **Bundle size / auditability:** the curated list is grep-able,
  reviewed, and ships only what's used. A lazy dynamic import against
  the full catalog trades review for surface area.

## Decision drivers

- Bundle budget: the frontend already pulls React Flow, DFD tooling,
  and the compliance UI. Icons should not blow the JS budget.
- Supply chain: `@thesvg/react` is a single upstream. Every new
  registry entry is one more thing to audit if that package is ever
  compromised (OWASP A08 — software integrity).
- Discoverability for pack authors: they need to know "does slug `foo`
  work?" without reading source.
- Ability to swap the underlying library. `@thesvg/react` is one
  option; we may want `simple-icons` or an in-house SVG catalog later.

## Options

### Option A — Curated registry only (status quo)

- Explicit `PACK_ICON_REGISTRY` map.
- Adding an icon = a PR that touches one file.
- Unknown slug → lucide fallback.

### Option B — Lazy dynamic import against full `@thesvg/react`

```ts
const Icon = React.lazy(async () => {
  try {
    const mod = await import(`@thesvg/react/${slug}`);
    return { default: mod.default };
  } catch {
    return { default: FallbackIcon };
  }
});
```

- Any slug that exists in the package resolves.
- Import path is dynamic — most bundlers ship one chunk per icon.
- Unknown slug → fallback at runtime.

### Option C — Curated registry + optional lazy escape hatch

- Curated map remains the default (fast, audited).
- Behind an org-level feature flag (`pack.icon.lazyCatalog = true`),
  unknown slugs attempt the dynamic import from Option B before
  falling back.
- Off by default; explicitly opt-in per environment.

### Option D — Move icon catalog to the backend

- Backend serves `/api/v1/icons/<slug>.svg` (or a manifest).
- Frontend renders `<img src>` / inline SVG fetched from the backend.
- Icons become a first-class asset, easier to audit and cache at the
  CDN.
- Adds a network round-trip per unique icon (mitigated by cache).

### Option E — Hand-authored SVG assets shipped with packs

- Pack authors drop an `icon.svg` next to `pack.yaml`.
- Importer stores it in blob/asset storage; the frontend reads it via
  the pack detail API.
- Removes the `@thesvg/react` dependency entirely for those packs.
- Adds asset upload plumbing and mimetype validation.

## Guiding questions

1. What's the current JS bundle budget for the `/libraries` and
   `/threat-models/*/edit` routes? If we're already near it, Option B
   is risky even lazy-loaded.
2. Does security have an appetite for pulling arbitrary icon modules
   at runtime from an npm package the user's browser hasn't yet
   downloaded? If not, Option A or D is safer.
3. How often does a new pack need an icon that isn't in the curated
   list? If it's a monthly PR, Option A is fine. If it's every pack,
   Option A becomes a bottleneck.
4. Do we anticipate offline / air-gapped deploys (federal/on-prem)?
   Option D + Option E work in those environments; Option B (dynamic
   npm imports) may not, depending on how the frontend is served.
5. Should the *fallback* be lucide `Package` (as today) or something
   more informative (e.g. an "unknown pack" avatar with the pack's
   initials)?
6. If we adopt Option D or E, does the export/import format
   ([docs/guides/importing-exporting.md](../guides/importing-exporting.md))
   need to carry the icon bytes with the pack? Otherwise, imported
   packs lose their icons.

## Proposal (recommended for discussion)

**Option A** for day one, with a **planned Option C** if demand grows:

- Keep `PACK_ICON_REGISTRY` as the source of truth. It's short,
  auditable, and covers the ~20 brands actually referenced by shipped
  packs.
- Document the process for adding a slug in
  [docs/concepts/library-packs.md](../concepts/library-packs.md): open
  a PR, add one entry, done. Include a screenshot of where the slug
  is used.
- Add a `known_slugs` field to the pack list API so pack authors can
  fetch the current registry programmatically instead of reading
  source.
- When we see a real bottleneck (10+ pending "please add this icon"
  requests), promote to Option C behind a feature flag.

Explicitly reject Option B for now: even lazy-loaded, it makes
supply-chain review a moving target.

## Consequences

- **Positive:** Bundle size stays predictable; unused icons never
  reach the browser.
- **Positive:** Any new icon goes through review — good for both
  supply chain and design consistency.
- **Positive:** Swapping `@thesvg/react` for another library is a
  one-file change (rewrite `PACK_ICON_REGISTRY`).
- **Negative:** Adding an icon still requires a frontend PR. For a
  federal deployment that iterates on packs but not the app itself,
  that's a real friction point — flag Option D as the escape hatch.
- **Negative:** Users cannot self-serve an icon their pack needs.
  Ships as a deliberate constraint until Option C or D lands.
