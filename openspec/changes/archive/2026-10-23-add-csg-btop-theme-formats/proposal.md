## Why

btop is launched from the ags bar (`dotfiles/config/ags/bar/widgets/btop.tsx`
shells `kitty -- btop`) and is already a provisioned package
(`group_vars/arch.yml:100`), but it colors itself from its own config and
**nothing today lets the runtime palette reach it**. CSG is the single palette
producer and already emits one artifact per consumer, but it has **no btop
format** — and one cannot be added by dropping a template into a custom dir,
because `TemplateCatalogService.derive` raises `TemplatesValidationError` for any
`colors.*.j2` whose key is not in the closed `ColorFormat` enum. The format must
be added to CSG itself.

btop's theme format is well suited to the existing pipeline. Verified against
btop 1.4.7 (`src/btop_theme.cpp`):

- 48 keys, **none required** — a missing key falls back to `Default_theme`, with
  dedicated fallbacks for `meter_bg`, `graph_text`, and `process_*`.
- Values are `"#RRGGBB"`, `"#GG"`, or `"12 34 56"`. No 8-digit/alpha.
- `theme[<x>_mid]=""` yields a clean **two-stop gradient** — a documented idiom
  the built-in TTY theme uses.
- A theme file is discovered from `--themes-dir`, then
  `$XDG_CONFIG_HOME/btop/themes`, then the system dir; selection is by
  `color_theme` in `btop.conf`.

The user asked for a **difficulty dial** rather than a feature list, so this adds
three variants that differ only in which gradients are forced cool→warm.

## What Changes

- Add three members to `ColorFormat`:
  `BTOP_MINIMAL = "btop-minimal.theme"`, `BTOP_BALANCED = "btop-balanced.theme"`,
  `BTOP_FULL = "btop-full.theme"`.
- Add three templates under `defaults/templates/`, each self-contained and
  emitting all 48 keys from the shared `ColorScheme`:
  - `csg-minimal` — every gradient is a slice of the wallpaper luminance ramp.
  - `csg-balanced` — `temp` and `cached` forced cool→warm.
  - `csg-full` — `temp`, `cached`, and `cpu` forced cool→warm.
- Meters are grouped by **true meaning**, not by key name: `free`+`available`
  ("room left"), `used`+`cached` ("consumption").
- Box outlines (`cpu_box`/`mem_box`/`net_box`/`proc_box`) and `div_line` share one
  dim ramp stop.
- Tests: enum values locked; catalog discovery; rendered bytes validated against
  btop's real parser rules (key set, value grammar, column-0 rule).

Multi-dot enum values are safe: the catalog strips the `colors.` prefix and passes
the remainder to `ColorFormat()`, and `GTK_CSS = "gtk.css"` is the existing
precedent.

## Non-goals

- **No runtime change here.** Requesting the artifacts, hashing them, and
  exposing them through `current/` is `add-runtime-btop-theme-artifacts`.
- **No `btop.conf` and no `config_links` wiring.** That is
  `provision-btop-config`.
- **No reloader.** btop loads its theme at startup and exposes no reload signal;
  the theme applies on next launch. Deliberate deferral (see design D5).
- **No btop-as-source backend.** Deriving a palette from an existing `.theme`
  file is a separate change that builds on the templates proven here.
- **No change to any existing format's bytes.**
