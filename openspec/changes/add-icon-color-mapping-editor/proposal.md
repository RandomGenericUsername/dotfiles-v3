## Why

Recoloring an icon today is a blind, three-file edit. The colors an icon actually shows come from a two-hop lookup that is invisible in any single file:

```
{{COLOR_ACCENT}}          (SVG template — dotfiles/assets/icon-templates/**/icon.svg)
      ↓  color_mappings   (dotfiles/config/icon-template-color-scheme-mappings/{icons,defaults}.yaml)
   color12
      ↓  palette          (~/.local/share/dotfiles/generated/palettes/colors.yaml)
   #6ea8fe
```

To change one battery color you must open the SVG to learn which placeholder a shape uses, open `icons.yaml`/`defaults.yaml` to learn what that placeholder maps to, open `colors.yaml` to learn what that token looks like, edit, re-run `itr render`, and look at the result. There is no way to see which shape a placeholder paints, no way to see a palette token before choosing it, and no way to see that a group-level mapping change recolors every variant of the group.

## What Changes

A new authoring-time GUI, `icon-color-mapping-editor` (AGS/GTK4), that turns that loop into: click a shape → pick a palette swatch → save.

- **Inputs (3):** SVG template root (read-only), `icons.yaml` + `defaults.yaml` (the only files written), generated `colors.yaml` (read-only).
- **Renders** the icon exactly as `itr render` would — same placeholder substitution semantics, same mapping precedence (vocabulary defaults → group → variant).
- **Click-to-select a shape** in the preview; the panel names the shape, the placeholder it uses (`{{COLOR_ACCENT}}`), the token that placeholder currently maps to (`color12 · #6ea8fe`), and how widely that placeholder is used ("2 shapes across 4 variants").
- **Pick any palette token** (`color0..15`, `foreground`, `background`, `cursor`) for the selected placeholder. Tokens absent from `colors.yaml` are shown disabled, not hidden.
- **Edit scope switch:** *Whole group* (default) writes `battery.color_mappings.COLOR_ACCENT`; *This variant only* writes a `variants[].color_mappings` override.
- **Group-wide live preview:** all variants of the group re-render on every pick, so the blast radius of a group mapping is visible before saving.
- **Deferred writes:** edits accumulate in a pending buffer with a YAML diff pane; nothing touches disk until *Save*, and *Revert* discards.

Locked semantics: the tool edits **mappings**, never SVG templates. It never touches `generated/`; its output is a repo diff that you re-render and re-provision as usual.

The UI is already validated against real battery templates and mappings — see `mock.html` in this change folder, which this proposal codifies.

## Non-goals

- Not a runtime widget: not added to `app.tsx`, not provisioned into the spine, no bar integration.
- No SVG template editing, no shape/path creation, no new placeholder vocabulary names.
- No palette editing and no `colors.yaml` writes; adding the missing `surface`/`accent`/`accent-muted` tokens is a separate change.
- No `itr render` invocation from the GUI (preview is in-process); rendering stays the CLI's job.
