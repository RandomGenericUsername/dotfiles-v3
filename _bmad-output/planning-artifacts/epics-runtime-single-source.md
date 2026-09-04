# Epic 4: Single Source of Truth (Runtime Owns All Generated Artifacts)

## Overview

Eliminate the provisioning-side `generated/` vs runtime-side `current/`
duality. After this epic, the runtime is the single source of truth for
every derived artifact (palette, effects, icons); provisioning deploys
inputs only; AGS resolves through `current/` exclusively.

## Problem

Provisioning generates palette/effects/icons once at bootstrap into
`<install>/generated/` (via the `default_palette` and `icons` roles) and
copies palette fragments into config dirs (via `compositor_configs`).
The runtime regenerates the same artifacts per wallpaper into
`cache/<layer>/<hash>/` and symlinks them from `current/`. Consumers
read through two different paths:

- AGS colors: `<install>/config/ags/colors.css` — a COPY from
  `generated/` (stale after every `wallpaper set`; nothing ever updates it)
- AGS icons: `IconRegistry` checks `current/icons/` first, then falls
  back to `generated/icons/` (stale provisioned render)
- Hyprland `colors.conf` copy in `<install>/config/hypr/` is not even
  sourced by the Lua configs (dead weight)

The `provisioning-delta.md` R2 step ("seeder replaces provisioning
copies with symlinks → `current/` as its last step") was specified but
NEVER IMPLEMENTED — `CacheSeeder` only creates `current/` symlinks, it
never touches the spine copies. The `compositor_configs` dont-clobber
guard (Story 1.12) protects a symlink state that nothing ever creates.

## Decision (user-approved)

- Provisioning deploys INPUTS ONLY (wallpapers, templates, catalog,
  mappings, settings.toml). No generation.
- Runtime owns ALL generation (`wallpaper set` / first-run seed).
- AGS resolves through `current/` exclusively (no `generated/` fallback).
- Bootstrap calls the runtime once: after `settings` + `config_links`,
  run `wallpaper set <install>/wallpapers/default.png` (the seed path,
  already fixed in rt-3-8 to read from `wallpapers/`), then
  `compositor_configs` places skeletons only, then `verify` asserts
  `current/` + spine symlinks.
- `<install>/generated/` is REMOVED ENTIRELY (dirs, roles, references).
- `compositor_configs` fragment-copy tasks are DELETED (skeletons only).
  The R2 consumer-path symlinks (`<install>/config/hypr/colors.conf` →
  `current/colors.conf`, `<install>/config/ags/colors.css` →
  `current/colors.gtk.css`) are created by the runtime seeder (the
  missing R2 implementation), NOT by provisioning.
- `hyprpaper.conf` rewrite and ITR `color_scheme.path` rewrite (old R2
  items 3-4) DISSOLVE: hyprpaper uses IPC with the resolved `current/`
  path (rt-2-5 verified channel), and the ITR settings template points
  at `current/colors.yaml` as a static string (path need not exist at
  render time).

## Stories

| # | Key | Title | Owner |
|---|-----|-------|-------|
| 4.1 | rt-4-1 | Remove generation roles from provisioning bootstrap | provisioning |
| 4.2 | rt-4-2 | Runtime seeder implements missing R2 consumer-path symlinks | runtime |
| 4.3 | rt-4-3 | AGS IconRegistry runtime-only + ITR settings repoint | AGS / provisioning-settings |
| 4.4 | rt-4-4 | Verify current-only criteria + remove generated/ + docs | provisioning-verify / docs |

## Ordering

rt-4-2 (runtime R2) FIRST — it is independently shippable (creates
symlinks that are no-ops when fragments are plain files? NO — it
REPLACES files with symlinks; must land together with rt-4-1's
deletion of the copy tasks, otherwise seed fights provisioning).
Therefore rt-4-1 + rt-4-2 land as one atomic change (two stories, one
commit window), then rt-4-3, then rt-4-4.

Fresh-machine bootstrap order after the epic:
`packages → cli_tools → filesystem → assets → compositor_configs
(skeletons only) → config_copies → settings (ITR points at
current/colors.yaml) → zsh_tools → zsh_config → wlogout_config →
config_links → runtime-seed (wallpaper set default.png) →
display_manager → verify (current-only criteria)`

## Out of scope

- Changing the cache layout or hash formulas
- Changing CSG/WEG/ITR derivation semantics
- The WEG `<stem>/` subdir nesting (tracked separately)
- SDDM/display-manager behavior
