# ADR 0002 — YAML icon shape, shorthand, and migration path

- **Status:** Proposed
- **Date:** 2026-08-19
- **Deciders:** TBD
- **Depends on:** [0001 — Icon override layers](0001-icon-override-layers.md)

## Context

`pack.yaml` currently accepts two icon forms because we shipped both
during the POC:

```yaml
# Shorthand (bare string)
icon: aws

# Full config
icon:
  slug: aws
  variant: default
  fill: currentColor
  className: text-orange-500
  ariaLabel: AWS logo
```

The importer's `_normalize_icon` promotes the shorthand to
`{"slug": "<value>"}` and drops any keys outside the allowlist
(`slug, variant, width, height, fill, viewBox, className, style,
ariaLabel`). About 14 packs on disk today use the string form; 2 use
the mapping form.

Before we build editors/overrides on top, we need to decide **whether
both forms stay**, and **what happens when the schema evolves** (new
prop, renamed prop, deprecated prop).

## Decision drivers

- Pack authoring must stay trivial for the common case (a single
  brand slug).
- The schema must be forward-compatible: adding a prop next quarter
  can't invalidate today's YAML.
- Pack files are user-editable and reviewed as text diffs, so the
  format must be easy to read/grep.
- Every allowed key is a surface that we validate + render + carry
  through the API. Extra keys = extra tests.

## Options

### Option A — Keep both forms (shorthand + full config)

- Shorthand `icon: aws` is sugar for `{ slug: aws }`, normalized at
  import time.
- Full config allows the documented props.
- Unknown keys are stripped silently.

### Option B — Only the full mapping form

- Every pack must write `icon: { slug: <value> }`.
- Older packs break on re-import until updated (or a one-time
  compatibility path runs).

### Option C — Keep both, but formalize the schema

- Introduce a JSON Schema (or Pydantic model) that validates
  `pack.icon` at import time.
- Unknown keys are a validation *warning* (not a silent drop) and
  surface in the "available_overlays" API preview.
- Schema is versioned with `pack.schema_version` — new props require
  bumping schema version.

### Option D — Two-tier config: `preset` + `overrides`

```yaml
icon:
  preset: aws-brand-orange   # references a named preset in icons/pack.yaml
  overrides:
    className: text-orange-700
```

- Presets are declared in the `libraries/packs/icons` catalog pack.
- Packs pick a preset name, then optionally override individual props.
- Reduces duplication when many packs share the same visual treatment.

## Guiding questions

1. Do we expect **enough packs to share visual treatments** to justify
   presets (Option D)? Or is per-pack config always different enough
   that presets are ceremony?
2. Is a validation *warning* on unknown keys (Option C) enough, or do
   we want a hard error? Hard error = safer schema, but every prop
   rename becomes a breaking release for every pack that used it.
3. Do we want the ability to say "this pack has no icon and should not
   fall back to a lucide default"? Today `icon: {}` and `icon: null`
   both silently fall back — should there be an explicit
   `icon: { hidden: true }`?
4. Should `className` and `style` be *allowed at all* in YAML, given
   OWASP A05 concerns about presentation coming from user-editable
   files? Or should YAML only carry `slug`, `variant`, `width`, and
   `height`, with all styling in Tailwind classes owned by the
   frontend?
5. Where should the schema live so pack contributors can find it —
   inline in `pack.yaml` comments, in `docs/concepts/library-packs.md`,
   or as a JSON Schema next to the icons catalog?

## Proposal (recommended for discussion)

**Option A + a subset of C**:

- Keep both YAML forms (POC compatibility).
- Add explicit validation in `apps.packs.services.validate_pack` that
  emits a `ValidationWarning` (existing type) when:
  - `icon` is neither string nor mapping;
  - the mapping contains keys not in the allowlist;
  - `slug` is missing when the mapping form is used;
  - `className` or `style` are set but the org has disabled raw CSS in
    packs (see question 4).
- Document the allowlist in
  [docs/concepts/library-packs.md](../concepts/library-packs.md) and in
  a comment at the top of `libraries/packs/icons/pack.yaml`.
- Defer Option D (presets) until we see ≥ 3 packs duplicating the same
  `className`/`fill` combo.

## Consequences

- **Positive:** No breaking change to existing pack.yaml files; simple
  packs keep the one-liner form.
- **Positive:** Validation warnings surface schema drift *before*
  import, so bad configs never reach the DB.
- **Negative:** Two allowed forms means two code paths (normalizer +
  serializer) — small but real maintenance cost.
- **Follow-on:** If Option D becomes desirable, presets can be layered
  on Option A without touching existing packs (a `preset:` key is just
  another allowed key that resolves before merge).
