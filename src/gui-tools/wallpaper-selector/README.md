# wallpaper-selector

AGS wallpaper picker (P5 drill-down): level 1 is the install-spine
wallpaper grid with search and hover quick-apply; level 2 is the
per-wallpaper variant gallery (breadcrumb + Back) fed by the runtime's
effects cache. Applying shells the engine (`dotfiles-runtime wallpaper
set`); progress and LIVE refresh arrive via the `wallpaper.state` domain
event. Variants promoted to wallpaper skip WEG regeneration in the
runtime (mechanism A) while palette/icons still derive.

## Layout

```
src/gui-tools/wallpaper-selector/
  app.tsx                 instance `wallpaper-selector`, single centered window
  style.css               ws-* classes (house dark theme)
  ui/WallpaperSelectorWindow.tsx   P5 window (imperative GTK + createEffect)
  lib/model.ts            pure grouping/filtering (node-tested, no GJS imports)
  lib/scan.ts             spine + effects-cache + current.json scan (GJS)
  lib/thumbnails.ts       disk-cached GdkPixbuf thumbnails (GJS)
  lib/apply.ts            execAsync engine entry point (GJS)
  lib/contrast.ts         icons preference/regenerate CLI shell (GJS)
  lib/event-bus-core.ts   contract constants + hydration state machine (copy)
  lib/event-bus.ts        Gio transport singleton (copy)
  tests/model.mjs         pure-model tests
  tests/event-contract-drift.mjs   baked-constants drift gate
```

## Run / lint / test

```
make -C src/gui-tools/wallpaper-selector run    # ags run app.tsx
make -C src/gui-tools/wallpaper-selector lint   # ags bundle check
make -C src/gui-tools/wallpaper-selector test   # node tests
```

Provisioned as `<install>/config/ags-wallpaper-selector/` with launcher
`wallpaper-selector-ui` (SUPER+W).

## Lifecycle

- Only the Apply buttons set the wallpaper; thumbnail presses are inert.
- An "Auto high-contrast icons" checkbox (L2 crumb header, primary) edits
  the per-wallpaper pref via `dotfiles-runtime icons preference <hash>
  --set on|off`; the L1 hover swatch is a CSS-drawn shortcut that drills to
  L2. A live-target flip additionally runs `icons regenerate --contrast
  on|off` (icons only, no pixel change); a non-live flip persists only.
- Applies persist the focused wallpaper's checkbox state before
  `wallpaper set` (`auto` resolution). While `wallpaper.state` is
  `applying`/`visible`, Apply controls are insensitive; the checkbox stays
  live and a flip defers its regenerate until `done`/`error`.
- The window self-hides on successful apply (stays open on failure).
- The runtime's AGS reloader skips this instance (`DEFAULT_SKIP_CONFIG_DIRS`,
  same as the editor): a restart would pop the visible-on-start window back
  open uninvited. Palette restyling arrives event-driven instead — the
  `wallpaper.state → done` handler re-applies `ags/colors.css` plus the
  re-rendered search icon.
