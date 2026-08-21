# ADR 0001 — Icon override layers & precedence

- **Status:** Proposed
- **Date:** 2026-08-19
- **Deciders:** TBD
- **Depends on:** —

## Context

The POC on `feature/icon-library` renders pack icons in two places:

1. **Library screens** (`PackCard`) — reads `LibraryPack.icon` directly.
2. **Diagram nodes** (`ProcessNode`, `DataStoreNode`, `SystemActorNode`)
   — reads `technology.packIcon` (inherited from the tech's source
   pack) via `TechnologyIcon`.

Today an icon can be declared in exactly one place: `pack.yaml -> icon:`.
The UI can only pass render-time props (`className`, `width`, …) as
overrides, and those are ephemeral (not persisted).

We need to decide **how many override layers exist**, **who owns each
one**, and **how they compose** — before we design storage (ADR 0003)
or the editor (ADR 0004).

## Decision drivers

- Pack authors already own presentation defaults (YAML). We should not
  take that away.
- Multi-tenant orgs will want brand overrides ("show the GSA logo, not
  the AWS one, on our components") without forking the pack.
- Diagram authors need per-node freedom for one-off visuals (a
  deprecated service painted red, an anonymized icon in a demo).
- Every layer we add is another place to search when an icon looks
  wrong. Keep the count minimal.
- OWASP LLM01/03 & OWASP Top 10 A05 concern: user-supplied `style` /
  `className` fields can be an injection vector; each layer that lets a
  non-admin user write raw CSS multiplies review load.

## Options

### Option A — Two layers: **pack default** + **UI runtime prop**

- Pack YAML is the only persisted config.
- The UI can pass props (`className`, `style`, `variant`, …) that win
  for the current render but are not saved.
- This is what the POC ships.

### Option B — Three layers: **pack** → **org override** → **runtime**

- Org admins can override a pack's icon for their organization only
  (stored on a new `OrgPackIconOverride` row).
- Diagram authors still pass runtime props but cannot persist a change
  per-node.
- Runtime props win at render.

### Option C — Four layers: **pack** → **org** → **tech** → **node**

- Adds two persisted layers:
  - **Tech-level override** — org can override the icon for one
    `ComponentLibrary` row (e.g. their DynamoDB icon, but not their
    Lambda icon).
  - **Node-level override** — a diagram author can pin an icon on one
    node in one diagram.
- Runtime props still win at render (but the "runtime prop" here is
  usually just node overrides sourced from the DB).

### Option D — Two layers with **explicit "presentation profile"** rows

- Instead of overrides at each level, an org selects a named
  "presentation profile" (e.g. `gsa-brand`, `dark-only`) that maps
  every pack slug to a chosen icon config. Profiles are versioned
  library artifacts, like packs.
- Diagram nodes reference a profile, not a raw icon.

## Guiding questions

1. Who is the primary editor of an icon override in this product —
   pack authors (YAML), org admins (settings screen), or diagram
   authors (right-panel)? If you had to pick one, which is it?
2. How often will an override be **per-node** vs **per-tech** vs
   **per-pack**? Do we have real user stories for the per-node case, or
   is it a hypothetical?
3. Is "an icon looks wrong on my diagram" a support burden today? If
   so, would a single "reset to pack default" button in Option A be
   enough, or does that scenario really need Option B/C persistence?
4. Do we need to keep pack YAML as the **only** source of truth so that
   packs remain shareable/exportable across orgs? Or is per-org drift
   acceptable?
5. Would a "presentation profile" (Option D) actually reduce cognitive
   load, or would it become another thing users forget to attach?
6. Is there any concern with letting non-admin users write arbitrary
   `className` / `style` values through an override layer? (See OWASP
   A03 injection / A05 security-misconfiguration.)

## Proposal (recommended for discussion)

**Option B** ("pack → org → runtime") is the smallest step that unlocks
the real request ("our org wants to swap the icon on shared packs
without forking"), does not require a diagram-schema change, and keeps
per-node customization as a follow-on rather than a day-one feature.

**Precedence rule** (higher wins):

```
runtime prop  >  org override (persisted)  >  pack YAML default  >  vendor mapping  >  lucide fallback
```

`className` is *concatenated* across layers (higher-precedence appended
last so Tailwind's cascade wins). `style` is deep-merged (higher wins
per-key). All other props are last-write.

## Consequences

- **Positive:** Predictable resolution order documented once, applied
  identically in library screens and diagram nodes.
- **Positive:** Runtime prop still wins, so the current React Flow
  rendering keeps working unchanged.
- **Negative:** Adds one new persisted table (see ADR 0003) and one new
  admin/settings screen (ADR 0004).
- **Follow-on:** Node-level overrides (Option C's fourth layer) can be
  added later without breaking the precedence rule — they simply slot
  in between "org override" and "runtime prop".
