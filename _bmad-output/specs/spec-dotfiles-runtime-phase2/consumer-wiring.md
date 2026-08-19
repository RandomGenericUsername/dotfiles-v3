# Consumer Wiring — dotfiles-runtime-phase2

Companion to SPEC-dotfiles-runtime-phase2. Describes how desktop components read the runtime's `current/` symlinks (CAP-3) and how that wiring changes the provisioning phase (AD-17). **The bar shell is AGS (Aylur's GTK Shell v2), fully replacing Waybar (correct-course 2026-08-18).**

## Consumers read through current/

```
Hyprland colors.conf
    ~/.config/hypr/colors.conf
      → (config-in-spine symlink) <install>/config/hypr/colors.conf
      → (NEW symlink, was a copy) $XDG_STATE_HOME/dotfiles/current/colors.conf
      → cache/palettes/<ph>/colors.conf

AGS (bar shell) CSS palette fragment
    ~/.config/ags/style.css (GTK4 CSS + SASS) imports the palette fragment
    ~/.config/ags/colors.css
      → (config-in-spine symlink) <install>/config/ags/colors.css
      → (NEW symlink, was a copy) $XDG_STATE_HOME/dotfiles/current/colors.gtk.css
      → cache/palettes/<ph>/colors.gtk.css

Hyprpaper wallpaper
    hyprpaper.conf wallpaper path
      → (NEW path) $XDG_STATE_HOME/dotfiles/current/wallpaper.png
      → cache/wallpapers/<wh>/wallpaper.png

ITR icon rendering
    itr settings.toml [color_scheme] path
      → (NEW path) $XDG_STATE_HOME/dotfiles/current/colors.yaml
      → cache/palettes/<ph>/colors.yaml
```

The AGS palette fragment uses GTK `@define-color` / CSS variables — the same CSG `gtk.css` output Waybar consumed; AGS's GTK4 CSS engine reads it natively.

Terminal colors: applied from `current/colors.yaml` by the terminal adapter (CAP-6), not by a symlink (terminals read a config file, not a shared path).

## What the swap changes

Repointing the `current/` symlinks (AD-6) atomically changes what every consumer above resolves to — no per-consumer config rewrite on swap. The reload step (CAP-6) tells each running process to re-read its config.

## Provisioning deltas (AD-17, amended by R2/R3 — cross-domain Phase-2 stories)

The consumer-path flips are performed by the **runtime seeder as its last step**, NOT by provisioning apply. Provisioning's actual deltas:

1. `verify` criterion 6: relax to "either `<install>/generated/palettes/colors.yaml` exists (pre-runtime) OR `$XDG_STATE_HOME/dotfiles/current/colors.yaml` exists (post-runtime)."
2. **Don't-clobber guard (R3):** `compositor_configs`/`config_copies` leave `colors.conf`/`colors.css` untouched when they are already runtime symlinks — a provisioning re-apply must not destroy the runtime's repoint.
3. Provisioning keeps writing `<install>/generated/` (the seed source) and its pre-runtime copies — Phase-1 behavior unchanged.

The seeder (Epic 1, CAP-5) then replaces the copies with symlinks → `current/...` and rewrites hyprpaper conf + ITR color_scheme path to `current/...`. This ordering means a fresh machine (apply → boot → before first runtime run) keeps provisioning's pre-runtime copies — no dangling symlinks.

## AGS provisioning swap (correct-course 2026-08-18, full replacement)

Provisioning swaps Waybar → AGS across Phase 1's completed work:

- `dotfiles/provisioning/packages.yaml`: `waybar` → `ags` (AUR, GTK4).
- `dotfiles/config/waybar/` → `dotfiles/config/ags/` (TS/JS project: `config.ts`/`config.js`, `style.css`, package.json as needed; `ags init` scaffold).
- `compositor_configs`: waybar config/style.css copy tasks → AGS project; `waybar-colors-css` palette-copy → `config/ags/colors.css`.
- `config_links` / `filesystem`: `~/.config/waybar` → `~/.config/ags` symlink; `config/waybar` → `config/ags` dir.
- `verify`: waybar presence done-criteria → AGS.
- 13 provisioning tests referencing waybar → AGS equivalents.
- docs/99, docs/01, docs/02 reconciled.

## Unverified (Epic 2 story-level decision)

1. Hyprpaper's wallpaper-swap channel: reload-after-symlink-repoint vs `hyprctl hyprpaper wallpaper <monitor> <path>` IPC. Must be verified against the installed Hyprpaper version before the reload adapter is built.
2. AGS reload channel: `ags run` hot-reload on file change vs process restart vs dbus signal. Must be verified against the installed AGS version before the AGS reload adapter is built.
