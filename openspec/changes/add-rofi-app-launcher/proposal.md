## Why

Pressing `SUPER+D` today spawns a launcher that is invisible to the theme system. The keybinding in `dotfiles/config/hypr/keybindings.lua` runs `wofi --show drun`, but wofi is a ghost: it is listed in `packages.yaml` yet never mapped in either `group_vars` package map, so it was never actually installed (manifest/group_vars drift), and it has no config directory at all. The result is an unthemed, default-look launcher that ignores the wallpaper-derived palette the rest of the desktop consumes.

Meanwhile the host already runs `rofi 2.0.0` (the Wayland-native Arch package) and `csg` already ships a `colors.rasi.j2` template — the palette artifact rofi themes import — but the runtime never generates it: `csg_adapter.py` hardcodes the five `--format` flags and every downstream pinned tuple (cache model, seeder, reconcile) carries the same five names. The rasi format is a latent feature of the toolchain with no consumer.

## What Changes

A themed rofi app launcher, provisioned end-to-end and consuming the runtime palette through the existing "one ConsumerPointer line + `@import`" contract (gt-2-2). Rofi is chosen as the launcher engine (vs wofi/tofi) because it is the most flexible and customizable of the three (rasi theme language, drun/dmenu/window/script modes) and is already present on the host.

- **Nested config layout** under `dotfiles/config/rofi/`: the rofi root carries the shared palette import, and one subdirectory per rofi-based tool. This change adds `launcher/` (the app launcher); future rofi tools (powermenu, clipboard picker, window switcher…) each get their own subdirectory reusing the same shared palette — a future tool is a new subdirectory + one skeleton entry, never runtime or provisioning restructuring.
- **Runtime palette artifact**: `colors.rasi` becomes the sixth palette artifact. `csg generate` requests `--format rasi`, the cache model/seeder/reconcile tuples grow to six, `current/colors.rasi` is repointed, and a new ConsumerPointer wires `<install>/config/rofi/colors.rasi → current/colors.rasi`. One shared pointer at the rofi root serves every nested tool via `@import "../colors.rasi"`.
- **Launcher theme** (`launcher/config.rasi`): a measured-fidelity reproduction of the reference screenshot — a panel-sized window (548px) perfectly centered on screen, floating over the live wallpaper with a fully transparent backdrop and no dim; 4px palette border + 2px surface ring; rounded (12px outer / 5px elements); 500×38 search bar; 8 rows of 36px; 24px icons; full-row selection in `@color10` with dark text; JetBrains Mono Nerd 12. All colors resolve from the runtime palette (`@background`, `@foreground`, `@color01/04/07/10`).
- **Keybinding**: `SUPER+D` repointed from `wofi --show drun` to `rofi -config ~/.config/rofi/launcher/config.rasi -show drun`. Rofi re-reads its theme on every launch, so a `wallpaper set` re-theme is picked up on the next invocation with no reloader adapter.
- **Provisioning**: manifest drift fixed (`packages.yaml` swaps wofi → rofi; both `group_vars` maps gain a `rofi` entry), the compositor_configs role places the launcher skeleton, config-links exposes `~/.config/rofi`, verify asserts it, and the structural parity tests are updated.
- **No compositor window rules**: rofi-wayland runs as a layer-shell overlay (like the AGS bar), so Hyprland `windowrule` does not apply; position/size/centering come from the rofi theme itself. This absence is deliberate (design D7), documented so it is never "fixed" into a dead rule.

## Non-goals

- Not adding any other rofi tool (powermenu, clipboard, window switcher, emoji) — this change only builds the app launcher and the shared layout/artifact contract those future tools will reuse.
- No rofi reloader daemon / live re-theme while a rofi window is open; relaunch-pickup is the model (same as every other consumer in this architecture).
- No changes to csg templates: `colors.rasi.j2` already exists and is correct; this change only makes the runtime request the format it already supports.
- No wofi removal from the host (it was never installed); the manifest is simply corrected to state the real desired set.
- No AGS bar widget for the launcher; `SUPER+D` is the only entry point.
- No Hyprland window rules and no `layerrule` (blur) for the launcher (D7): it is a layer-shell overlay that self-positions and self-sizes; crisp, unblurred fidelity per the reference.