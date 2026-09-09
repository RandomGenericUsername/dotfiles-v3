# Consumer Wiring — dotfiles-runtime-phase2

Companion to SPEC-dotfiles-runtime-phase2. Describes how desktop components read the runtime's `current/` symlinks (CAP-3) and how that wiring changes the provisioning phase (AD-17). **The bar shell is AGS (Aylur's GTK Shell v2), fully replacing Waybar (correct-course 2026-08-18).**

## Consumers read through current/ (Epic 4 single-source)

```
Hyprland colors.conf
    NOT CONSUMED — no Hyprland Lua config sources colors.conf
    (verified: no reference under dotfiles/config/hypr/*.lua).
    The runtime creates no Hyprland consumer path.

 AGS (bar shell) CSS palette fragment
    ~/.config/ags/style.css (GTK4 CSS + SASS) imports the palette fragment
    ~/.config/ags/colors.css
      → (config-in-spine symlink) <install>/config/ags/colors.css
      → (R2 symlink, runtime seeder — rt-4-2, never a copy)
        $XDG_STATE_HOME/dotfiles/current/colors.gtk.css
      → cache/palettes/<ph>/colors.gtk.css

System GTK — GTK4/libadwaita apps (gt-4-1, two-channel mechanism)
    ~/.config/gtk-4.0/gtk.css (spine skeleton, gt-3-1)
      @import "colors.css";
      → <install>/config/gtk-4.0/colors.css
      → (R2 symlink, runtime seeder) current/colors.adw.css
      → cache/palettes/<ph>/colors.adw.css
    colors.adw.css emits BOTH channels: `@define-color` named colors
    (window/view/headerbar/card/dialog/popover/sidebar + accent/state trios +
    `color_00..15` passthrough) AND the `:root { --window-bg-color: … }`
    custom-properties block (libadwaita ≥ 1.4 / plain-GTK4 Default theme
    ≥ 4.16 resolve variables; chrome surfaces are color-mix blends of the
    wallpaper's k-means mid clusters — visibly wallpaper-tinted).
    Pickup = process relaunch (no hot reload). REQUIRES the session NOT to
    export `GTK_THEME` (see hazard below).

GTK3 apps (gt-4-1 channel, consumer-cooperative)
    ~/.config/gtk-3.0/gtk.css (spine skeleton, gt-3-1)
      @import "colors.css";
      → <install>/config/gtk-3.0/colors.css
      → (R2 symlink) current/colors.gtk.css
      → cache/palettes/<ph>/colors.gtk.css
    Provides the GTK3-compatible `@color_*` custom names + `color_00..15`.
    Only reaches GTK3 surfaces whose stylesheets consume those names; apps
    with their own theme engine (e.g. thunderbird via `gtk-theme-name`) are
    out of the runtime's reach — separate follow-up scope.

New zsh shells (gt-3-2)
    .zshrc: `(cat "$XDG_STATE_HOME/dotfiles/current/colors.sequences" &)`
      → cache/palettes/<ph>/colors.sequences
    STALE `generated/palettes` path retired (pre-Epic-4 orphan). The
    CURRENT palette reaches every NEW shell; a running terminal only
    receives the OSC payload written by TerminalColorApplier to its own
    `/dev/tty` (launching terminal only — documented Phase-2 limitation;
    broadcast to all open terminals = Phase-5 daemon territory).

Hyprpaper wallpaper
    hyprpaper.conf wallpaper path
      → (static default) <install>/wallpapers/default.png
        (fresh boot shows the default wallpaper until first IPC)
      → (IPC override) $XDG_STATE_HOME/dotfiles/current/wallpaper-<monitor>.png
      → cache/wallpapers/<wh>/wallpaper.png

ITR icon rendering
    itr settings.toml [color_scheme] path
      → $XDG_STATE_HOME/dotfiles/current/colors.yaml
      → cache/palettes/<ph>/colors.yaml

AGS icons
    IconRegistry resolves through
      $XDG_STATE_HOME/dotfiles/current/icons/<output> ONLY
      (no generated/ fallback — Epic 4; missing icons return null)
```

The AGS palette fragment uses GTK `@define-color` / CSS variables — the same CSG `gtk.css` output Waybar consumed; AGS's GTK4 CSS engine reads it natively.

Terminal colors: applied from `current/colors.yaml` by the terminal adapter (CAP-6), not by a symlink (terminals read a config file, not a shared path).

## What the swap changes

Repointing the `current/` symlinks (AD-6) atomically changes what every consumer above resolves to — no per-consumer config rewrite on swap. The reload step (CAP-6) tells each running process to re-read its config.

## Provisioning deltas (AD-17, amended by R2/R3 — cross-domain Phase-2 stories;
Epic 4 completes R2)

The consumer-path symlink is created by the **runtime seeder**
(`repoint_consumer_symlinks`, rt-4-2), NOT by provisioning apply.
Provisioning's `compositor_configs` places skeletons only (no palette
fragments since Epic 4); the dont-clobber guard is retired with the copy
tasks it guarded. Provisioning keeps deploying `<install>/` inputs only.

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

1. Hyprpaper's wallpaper-swap channel: reload-after-symlink-repoint vs `hyprctl hyprpaper wallpaper <monitor> <path>` IPC. Must be verified against the installed Hyprpaper version before the reload adapter is built. (RESOLVED 2026-09-02: channel = per-monitor IPC `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]`, verified against hyprpaper 0.8.4 / hyprland 0.56.2 source; reload-after-symlink-repoint unavailable in the rewrite)
2. AGS reload channel: `ags run` hot-reload on file change vs process restart vs dbus signal. Must be verified against the installed AGS version before the AGS reload adapter is built.

## The `GTK_THEME` hazard (gt-4-1, 2026-09-08 — machine-verified)

A session that exports `GTK_THEME` — even an EMPTY string — makes GTK load
the plain GTK theme in place of libadwaita's stylesheet at a priority that
beats ALL `~/.config/gtk-4.0` user-CSS declarations: the wallpaper palette
never reaches libadwaita apps while it is set. This project shipped that
hazard itself (`env-variables.lua:6` `GTK_THEME=Adwaita:dark`, Phase-1 era);
the line was removed with an in-file rationale and the durable lesson is:
before concluding a CSS channel is dead upstream, probe for env-var
overrides. Light/dark preference comes from
`gsettings org.gnome.desktop.interface color-scheme` (the runtime does not
manage it in Phase 2.x; luminance-based auto-switch is a future
`ISystemColorSchemeSetter` story).
