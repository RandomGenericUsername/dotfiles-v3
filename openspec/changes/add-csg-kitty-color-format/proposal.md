## Why

kitty is the terminal the dotfiles desktop runs in, but it colors itself from its
own config — nothing today lets the runtime palette reach it. CSG
(`color-scheme-generator`) is the single palette producer and already emits one
artifact per consumer (`colors.conf` for Hyprland, `colors.gtk.css`,
`colors.adw.css`, `colors.rasi`, `colors.sequences`, …), but it has **no kitty
format**. It cannot be added by dropping a template in a custom dir either:
`TemplateCatalogService.derive` rejects any `colors.*.j2` whose key is not in the
`ColorFormat` enum. So the kitty format must be added to CSG itself.

This is the first of three changes that make all open kitty windows follow the
wallpaper palette (CSG format → runtime artifact + reload → provisioning
`kitty.conf`).

## What Changes

- Add `ColorFormat.KITTY = "kitty"` to the format enum.
- Add `defaults/templates/colors.kitty.j2` — a kitty config colors fragment in
  **plain kitty syntax** (`key #rrggbb`), emitting:
  `background`, `foreground`, `cursor`, `color0`…`color15`, and
  `selection_background` / `selection_foreground`.
- The format renders to `colors.kitty` like every sibling (no new machinery).
- Tests: enum value locked; template discovered by the catalog; rendered fragment
  matches the pinned kitty syntax.

## Non-goals

- No runtime change here (requesting, hashing, and exposing `colors.kitty` is
  `add-runtime-kitty-terminal-reload`).
- No kitty reload mechanism and no `kitty.conf` (that is the provisioning and
  runtime changes).
- No change to any existing format's bytes.
