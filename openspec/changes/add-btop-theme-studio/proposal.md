# Proposal

## Why

btop is themed by a **generated** `colors.btop.theme` (csg renders it from the wallpaper palette) that has two systemic colour defects: `meter_bg` is taken from a mid-luminance palette stop, and `used_start` is the *same* stop — so a disk/mem meter at 20% reads as **full**, and the unfilled part of every meter competes with the data. There is no authoring surface for btop themes: the generated file is a derived, content-addressed artifact re-created on every wallpaper set, so it cannot be hand-edited, and btop offers no layout/theme templating beyond the fixed `.theme` key set. The result is a monitor that looks wrong at low load and cannot be tuned or extended without editing csg's Jinja by hand.

## What Changes

- **New standalone GUI tool** `btop-theme-studio` (AGS/GTK4, its own instance, launcher bin, keybind), launched on demand like the icon color-mapping editor (`SUPER+I`). It is the authoring surface for btop themes.
- **Component schematic** as the primary view: the btop interface drawn as labelled boxes (cpu · cpu-detail · gpu · mem · net · disks · proc), each element tagged by the theme key it uses; selecting a key highlights every component it paints.
- **Consumes btop's real config** — `shown_boxes` and the parsed `presets` string from `btop.conf` — so the schematic's box set/positions follow the preset, and the tool warns when a key's module is not shown in the current preset. It does not invent a layout.
- **Live preview tab**: renders the **real btop binary** on a pty with the candidate theme, so the preview can never drift from btop (layout, braille graphs, and colours included). A warm btop process is reloaded per edit (`SIGUSR2`) and only the redraw delta is captured, so edits render in well under a second.
- **Theme library**: create / duplicate / fork / delete authored themes; the generated `colors.btop` is a read-only, palette-linked base that can be forked. Authored themes are static `.theme` files.
- **Full key editing**: every one of btop's 48 theme keys (tree grouped by surface / chrome / gradients / process state), with palette swatches (`ramp`, `color0–15`), named tokens (`background`/`foreground`/`cursor`), an **arbitrary colour picker** for colours beyond the palette, a **transparent** (empty-value) option, and a **gradient editor** (start/mid/end, with "add middle colour" for btop's two-stop gradients).
- **Save target = Repo | Installed** (no path selection): *Repo* writes the repo-authoritative source (deployed by `bootstrap`); *Installed* writes straight into the install spine and reloads btop live. Mirrors the icon editor's repo-authoritative model with an explicit spine target.
- **Generated, tested key→widget map**: derived from btop's own `btop_draw.cpp` + `btop_theme.cpp` (all 48 keys), with a drift-guard verifier — replacing hand-traced guesses.
- **Provisioning** ships authored themes into the spine themes dir and selects the active `color_theme` (surviving re-provisioning).

## Capabilities

### New Capabilities

- `btop-theme-studio`: the authoring GUI — theme library, component schematic driven by btop's real config, full 48-key editing (palette + arbitrary colour + transparent + gradient stops), and the Repo/Installed save targets.
- `btop-live-preview`: rendering the real btop binary on a pty as the preview (warm process + `SIGUSR2` delta capture), so the preview is always btop's actual output.
- `btop-key-widget-map`: the generated, drift-checked mapping from every btop theme key to the boxes/modules that draw it, derived from btop source.

### Modified Capabilities

<!-- none: no existing spec's requirements change; provisioning/runtime btop work is introduced by this change's capabilities -->

## Impact

- **New**: `src/gui-tools/btop-theme-studio/` (AGS app), a launcher bin + `SUPER` keybind, and a `btop-theme-studio` capability's data artifact (the key→widget map).
- **Provisioning**: extend the `btop_config` role / assets to ship authored themes and to set the active `color_theme` from a setting; keep `save_config_on_exit = false`.
- **Settings**: a new active-theme selection (repo-owned) rendered into `btop.conf`.
- **Consumes (unchanged)**: the csg btop template, the runtime `current/` pointer, and the existing `BtopReloader` (`SIGUSR2`) — no runtime behavior change required.
- **Dependencies**: the live-preview engine runs btop on a pty and reconstructs the screen with a terminal emulator (`pyte`); the key→widget generator parses vendored btop sources.
- **Mock / prototype**: `openspec/changes/add-btop-theme-studio/mock.html` + `prototype/` (the working PoC this proposal codifies).
