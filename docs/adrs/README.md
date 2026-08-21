# Pack Icon Override & Configuration ADRs

This directory holds a small set of Architectural Decision Records (ADRs)
covering how library-pack icons are declared in YAML, stored on the
backend, and overridden in the UI. They exist because the current POC
(`feature/icon-library`) already ships a working nested-YAML `icon:`
config and a `PackIcon` / `TechnologyIcon` renderer, but the *override
story* — who can change an icon, at which layer, and how the layers
compose — has not been designed.

The ADRs are numbered in the order in which they should be decided, since
each later decision depends on the earlier one:

| # | Title | Status | Depends on |
|---|-------|--------|------------|
| [0001](0001-icon-override-layers.md) | Icon override layers & precedence | Proposed | — |
| [0002](0002-icon-yaml-shape-and-migration.md) | YAML icon shape, shorthand, and migration path | Proposed | 0001 |
| [0003](0003-icon-storage-model.md) | Backend storage & inheritance for icon overrides | Proposed | 0001, 0002 |
| [0004](0004-icon-ui-editor.md) | UI editor for overriding icons (pack, tech, node) | Proposed | 0001, 0003 |
| [0005](0005-icon-registry-scope.md) | Icon registry scope (curated brands vs. lazy full catalog) | Proposed | 0001 |

Each ADR uses MADR-lite structure (`Context / Options / Decision drivers
/ Guiding questions / Proposal`) so we can answer the guiding questions
in review and promote a decision without rewriting the file.

**Working assumption for all five ADRs** — the shipped POC is the
baseline:

- Pack YAML: `pack.icon` is a mapping (`slug`, `variant`, `width`,
  `height`, `fill`, `viewBox`, `className`, `style`, `ariaLabel`),
  serialized to `LibraryPack.icon` (JSONField).
- Frontend `PackIcon` merges YAML defaults + runtime props (props win,
  `className`s concatenate, `style` deep-merges).
- `TechnologyIcon` resolves diagram-node icons in the order
  `technology.packIcon` → `technology.vendor` → lucide fallback.
- No per-node, per-tech, or per-org override path exists yet — that is
  what these ADRs decide.
