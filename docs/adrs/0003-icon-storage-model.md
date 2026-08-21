# ADR 0003 — Backend storage & inheritance for icon overrides

- **Status:** Proposed
- **Date:** 2026-08-19
- **Deciders:** TBD
- **Depends on:**
  [0001 — Override layers](0001-icon-override-layers.md),
  [0002 — YAML shape](0002-icon-yaml-shape-and-migration.md)

## Context

`LibraryPack.icon` is a `JSONField(default=dict)` and is the only
persisted layer today. ADR 0001 proposes a **pack → org → runtime**
layering; that requires deciding *where* an org override lives and how
it composes with the pack default when the API serializes it.

Two secondary concerns:

- The `ComponentLibrary` serializer already exposes `source_pack_icon`
  so diagram nodes can resolve the icon without a separate round-trip.
  If we add an override layer, we must decide whether the *resolved*
  icon or the *layered* icon flows over the API.
- Multi-tenant safety: an org's override must never leak to a different
  org's rendering of the same pack.

## Decision drivers

- Django/DRF idioms: prefer one model per concern (avoid overloading
  `LibraryPack` with per-org state).
- Frontend simplicity: nodes should get a *final, ready-to-render*
  config in one query, not compose it client-side.
- Cache-friendliness: `LibraryPack.icon` is org-agnostic and can be
  cached hard; per-org overrides must not poison that cache.
- OWASP A01 (broken access control): every write to an override table
  must be scoped to the requesting user's `organization_id`.

## Options

### Option A — Column on `OrganizationPackInstallation` (or equivalent)

Precogly already has an org-side representation of "this org installed
this pack" (`compliance`/`packs` linkage). Add `icon_override: JSONField`
to that row.

- One row per (org, pack). Natural place for org-level overrides.
- Nothing new to model.
- **Downside:** couples "install state" and "presentation" — future
  overrides (colors, labels) will accumulate here.

### Option B — New `PackIconOverride` model

```python
class PackIconOverride(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=CASCADE)
    library_pack = models.ForeignKey(LibraryPack, on_delete=CASCADE)
    icon = models.JSONField(default=dict)  # same shape as LibraryPack.icon
    class Meta:
        unique_together = [("organization", "library_pack")]
```

- One row per (org, pack) *only when overridden*, so most packs cost
  nothing.
- Purpose-built and easy to extend (add `component_library` FK later
  for per-tech overrides — Option C of ADR 0001).
- Requires a new admin, serializer, permission class.

### Option C — Generic `PresentationOverride` (polymorphic)

```python
class PresentationOverride(TimestampedModel):
    organization = models.ForeignKey(Organization, on_delete=CASCADE)
    target_type = models.CharField(choices=[
        "pack", "component_library", "diagram_node",
    ])
    target_id = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)  # {icon: {...}, color: ..., ...}
```

- One table for all presentation overrides at every layer.
- Flexible but harder to index and query.
- Payload becomes a magnet for unrelated concerns.

### Option D — Resolve at read time only (no persisted override)

- No new table. The frontend composes overrides from a client-only
  store (org-scoped `localStorage` + optional export/import JSON).
- **Pros:** zero backend work; zero migration.
- **Cons:** overrides don't survive device changes; can't share within
  a team; can't be audited; can't be applied to server-rendered
  exports.

## Guiding questions

1. Where do org-level overrides for other concerns (label, color,
   description) currently live? If there is already an
   `OrganizationPackInstallation`-like table, Option A is close to
   free.
2. Do overrides need to be **audited** (who changed it, when)? A
   dedicated model (Option B) makes `HistoricalRecords` trivial;
   Option C blurs the audit trail across concerns.
3. Do we need to export/re-import overrides between orgs (e.g. GSA
   templates a set of overrides for downstream tenants)? If yes,
   Option B or C, and the payload must be portable.
4. Do we anticipate wanting an org "reset all my icon overrides"
   button? All options support it, but Option B is a single DELETE.
5. Should the API return **the resolved icon** (backend composes
   layers) or **the layered icon** (backend returns pack + override
   separately)? Resolved = simpler frontend, but requires refetching
   when overrides change; layered = more chatty but cache-friendly.

## Proposal (recommended for discussion)

**Option B** with a resolved-at-read API:

- New `PackIconOverride(org, pack, icon)` model, unique per pair,
  history via `django-simple-history` if we adopt that pattern (else
  `created_at/updated_at`).
- `LibraryPackListSerializer` and `LibraryPackDetailSerializer` add a
  `resolved_icon` field: `PackIconOverride(icon) || LibraryPack.icon`.
- `ComponentLibrarySerializer.source_pack_icon` also returns the
  resolved value for the requesting org.
- Frontend continues to read one field (`resolved_icon` on packs,
  `sourcePackIcon` on components). No client-side composition.

**Precedence merge rule** (matches ADR 0001):

```python
def resolve_icon(pack_icon: dict, org_override: dict | None) -> dict:
    if not org_override:
        return pack_icon
    merged = {**pack_icon, **org_override}
    # className concatenates (org appended → wins in Tailwind cascade)
    cls = " ".join(filter(None, [pack_icon.get("className"), org_override.get("className")]))
    if cls:
        merged["className"] = cls
    # style is deep-merged per-key (org wins)
    merged["style"] = {**pack_icon.get("style", {}), **org_override.get("style", {})}
    return merged
```

## Consequences

- **Positive:** Frontend rendering code (both `PackIcon` and
  `TechnologyIcon`) does not need to know about override layers — it
  always renders a resolved dict.
- **Positive:** Pack `icon` remains org-agnostic and remains
  cache-friendly (Redis/CDN).
- **Positive:** Removing all overrides is a single scoped DELETE.
- **Negative:** Serializer now depends on request context to know
  which org is asking. This is standard for tenant-scoped queries in
  the codebase but adds one indirection.
- **Negative:** Requires a migration + admin + permission class.
