# ADR 0004 — UI editor for overriding icons

- **Status:** Proposed
- **Date:** 2026-08-19
- **Deciders:** TBD
- **Depends on:**
  [0001 — Override layers](0001-icon-override-layers.md),
  [0003 — Storage model](0003-icon-storage-model.md)

## Context

Once we've decided *what* layers exist (0001) and *where* overrides
live (0003), we still need a UI that:

- Lets the right role see the right control (pack authors don't get an
  org-override button; org admins don't hand-edit YAML).
- Makes the resolution order visible ("this icon comes from your org's
  override; the pack default is X").
- Is a small enough surface to review, since icons are cosmetic and
  should not eclipse threat-model work.

The current codebase has three obvious host surfaces:

1. `PackCard` on `/libraries` — good for a per-pack override.
2. `NodeEditPanel` on the DFD editor — the only place a diagram author
   already spends time; good for runtime prop overrides.
3. Org Settings page — good for a bulk / audit view.

## Decision drivers

- Reuse an existing surface if we can (don't build a new route).
- Keep the runtime prop path (POC) as the fallback so hurried users can
  always eyeball a change without saving.
- Make it obvious when the resolved icon differs from the pack default.
- Icons are low-stakes; the editor should not have a confirmation modal.

## Options

### Option A — Inline override on `PackCard` (org admin only)

- Add a small pencil icon on the `PackCard` visible only to org
  admins.
- Opens a popover with:
  - Icon slug (autocomplete from `PACK_ICON_REGISTRY` keys).
  - Variant dropdown (populated from the chosen icon component's
    typed union).
  - `className` free-text (guarded by a "raw CSS" toggle that only
    admins with a specific permission can enable — see OWASP A05).
  - "Reset to pack default" button.
- Saves a `PackIconOverride` row per ADR 0003.

### Option B — Dedicated `/settings/branding` page

- Collects all icon overrides in a table (pack, current icon, resolved
  icon, "override active?" toggle).
- Same fields as Option A but batched.
- Not tied to the browsing flow — you have to go find it.

### Option C — Right-panel override on `NodeEditPanel`

- Adds an "Icon" section to the node editor.
- Any override here is **per-node**, saved on the diagram node's data,
  and only visible in the current threat model.
- This is the "Option C" (per-node) layer from ADR 0001 — only build
  it if that ADR chooses Option C or later.

### Option D — Command palette entry

- `Cmd-K → "Change pack icon…"` opens a modal, no per-surface UI.
- Cheap to build; power-user only. Discoverability is poor.

### Option E — No UI editor; YAML-only

- Overrides live only in YAML. Orgs fork the pack (or maintain a
  per-org overlay pack) if they need custom icons.
- Zero UI to build, zero validation to write.
- Consistent with how compliance overlays already work today.

## Guiding questions

1. What roles exist in the product today, and which of them should be
   allowed to change an icon? (Superuser? Org admin? Any org member?)
   The answer determines whether we even need Option B/C.
2. Where do users currently discover *which* pack an icon came from?
   If nowhere, the editor also has to solve discoverability — should
   the popover show `pack.name` and `pack.slug`?
3. Do we want icon changes to appear in the diagram's changelog / DFD
   audit trail? Per-node (Option C) would be picked up by existing
   diagram autosave; per-org (Option A) would need its own history.
4. Are there any diagram export flows (PDF/PNG/DOCX) that already
   fetch icons? If yes, they must respect the resolved (post-override)
   icon; a naive implementation could keep exporting the pack default.
5. Do we ever want to **preview** an override before saving? If yes,
   the editor is significantly larger — we need a live-rendering
   preview panel.
6. Is there a legitimate case for a user pasting arbitrary SVG in the
   editor (e.g. "our company logo is not in `@thesvg/react`")? If yes,
   we've crossed from "override" into "asset management" and that
   probably deserves its own ADR.

## Proposal (recommended for discussion)

**Option A** as the day-one editor, gated behind an `is_org_admin`
check, with the following minimum surface:

- Small pencil (`Edit`) icon on `PackCard`, visible only when
  `useCurrentUser().permissions.includes('pack.override_icon')`.
- Popover fields: `slug` (autocomplete), `variant` (dropdown when the
  chosen slug has variants), `width`, `height`.
- No `className` / `style` in the day-one editor. Those stay
  YAML-only until we have a review flow (OWASP A05).
- Header of the popover shows: "Pack default: `slug=aws, className=…`"
  so the base is always visible.
- Foot of the popover: "Reset to pack default" (deletes the override
  row).
- Editor writes to the `PackIconOverride` model from ADR 0003.

Option C (per-node) is deferred until we hear a real user story for
per-node overrides.

## Consequences

- **Positive:** Reuses the existing `/libraries` surface — no new
  route, no new nav item.
- **Positive:** Locks down the injection-prone fields (`className`,
  `style`) to YAML review until we have a story for safer inline
  editing.
- **Positive:** Small enough that the initial PR is one popover + one
  API call + one serializer field.
- **Negative:** Org admins who love bulk editing get a
  card-by-card UX. If that becomes friction, promote to Option B.
- **Negative:** Discovery: users won't know the feature exists until
  they hover the card. Consider an empty-state hint on the pack detail
  page.
