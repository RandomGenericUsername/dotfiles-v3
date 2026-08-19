# Provisioning Delta — dotfiles-runtime-phase2

Companion to SPEC-dotfiles-runtime-phase2. The cross-domain changes the runtime core requires from the completed provisioning phase. These are Phase-2 stories against `src/provisioning/`, not a redesign of it.

## AGS-for-Waybar: the bar-shell swap (correct-course 2026-08-18)

The bar shell is **AGS (Aylur's GTK Shell v2)**, fully replacing Waybar across provisioning AND runtime. This is a provisioning-phase change layered on Phase 1's completed work:

| Provisioning artifact | Waybar (current) | AGS (target) |
| --- | --- | --- |
| `packages.yaml` | `waybar` (pacman/apt) | `ags` (AUR, GTK4) |
| `dotfiles/config/waybar/` | `config` (JSONC) + `style.css` | `dotfiles/config/ags/` — TS/JS project (`config.ts`, `style.css`, `package.json`; `ags init` scaffold) |
| `compositor_configs` | waybar config/style.css copy tasks | AGS project copy tasks |
| `compositor_configs` palette copy | `waybar-colors-css` → `config/waybar/colors.css` | → `config/ags/colors.css` (GTK `@define-color`, same CSG gtk.css source) |
| `filesystem` / `config_links` | `config/waybar` dir, `~/.config/waybar` symlink | `config/ags` dir, `~/.config/ags` symlink |
| `verify` | waybar done-criteria | AGS done-criteria |
| tests | 13 tests reference waybar | AGS equivalents |

The runtime plan's references to "Waybar" in AD-17, CAP-6, the consumer-wiring chain, and Epic 2's reload adapter all become AGS.

## The consumer-path flips are runtime-owned (AD-17, amended by R2)

The repoint of `colors.conf`/`colors.css` from the provisioning copy to `$XDG_STATE_HOME/dotfiles/current/...` is performed by the **runtime seeder as its last step** — NOT by provisioning apply. This avoids a dangling-symlink first boot (provisioning apply → first boot → before runtime ever runs).

| # | Provisioning role / file | Pre-runtime (provisioning owns) | Post-runtime (seeder repoints) |
| --- | --- | --- | --- |
| 1 | `compositor_configs` — `colors.conf` | copy of `<install>/generated/palettes/colors.conf` | seeder replaces with symlink → `current/colors.conf` |
| 2 | `compositor_configs` — AGS `colors.css` | copy of `<install>/generated/palettes/colors.gtk.css` | seeder replaces with symlink → `current/colors.gtk.css` |
| 3 | `hyprpaper` conf template | points at `<install>/wallpapers/default.png` | seeder rewrites to `current/wallpaper.png` (or hyprpaper reads a runtime-managed conf) |
| 4 | `settings` (ITR) | `[color_scheme] path` → `<install>/generated/palettes/colors.yaml` | seeder rewrites to `current/colors.yaml` |

## Provisioning's actual deltas

1. **AGS swap** (the bar-shell replacement above).
2. **`verify` criterion 6:** relax to "either `<install>/generated/palettes/colors.yaml` exists (pre-runtime) OR `$XDG_STATE_HOME/dotfiles/current/colors.yaml` exists (post-runtime)."
3. **Don't-clobber guard (R3):** `compositor_configs`/`config_copies` leave `colors.conf`/`colors.css` untouched when they are already runtime symlinks (a re-apply must not destroy the runtime's repoint).
4. Provisioning keeps writing `<install>/generated/` (the seed source) and its pre-runtime copies — Phase-1 behavior unchanged.

## What does NOT change

- The install spine structure (`wallpapers/`, `generated/`, `config/`, `icon-templates/`, `icon-mappings/`) stays as provisioning owns it.
- csg/weg/itr rendered `settings.toml` stays provisioning-owned; runtime overrides output via env vars per call (AD-7).
- Provisioning gains no runtime knowledge: it does not manage `cache/`, `current/`, or the state store.

## Boundary rule

Runtime never writes under the install spine after seeding (AD-11). Provisioning never writes under `$XDG_STATE_HOME/dotfiles/` (AD-5). The only cross-boundary reads are runtime reading spine inputs (templates, catalog, icon templates/mappings) for cache keys.

## Verify gate interplay

`dotfiles-provision verify` continues to assert provisioning done-criteria against provisioned locations only. Criterion 6 is the one that must tolerate a post-runtime machine. The other thirteen are unaffected.
