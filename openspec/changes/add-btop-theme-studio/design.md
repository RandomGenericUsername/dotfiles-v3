# Design

## Context

See `proposal.md` — Why. Relevant current state:

- btop's theme is a fixed **48-key** `.theme` file; csg renders one theme (`colors.btop.theme.j2`) from the wallpaper palette into a **derived, content-addressed** cache entry, exposed via `current/` and a spine pointer (`<install>/config/btop/themes/colors.btop.theme`). It is re-derived on every wallpaper set, so it cannot be hand-edited.
- btop's **layout** is not a file: `shown_boxes` plus a `presets` string (`box:P:G`) in `btop.conf`; geometry is computed at runtime by `Draw::calcSizes()`. There is no layout template to consume.
- btop has no reload except **`SIGUSR2`** (full config + theme reload + forced redraw); the runtime already ships `BtopReloader` using it.
- The repo already has the **icon color-mapping editor** (`SUPER+I`) as the precedent for a launch-on-demand AGS authoring tool with a repo-authoritative model and a spine fallback (`isSpinePath`).
- The working PoC for this change is `mock.html` + `prototype/` in this change folder.

## Goals / Non-Goals

**Goals:**
- An authoring tool that makes btop theme defects visible and fixable, and lets users create and tune themes beyond the generated one.
- A preview that cannot drift from btop.
- A truthful "where does this key show?" answer derived from source.
- Save to repo (reproducible) or to the installed theme (immediate), without path juggling.

**Non-Goals:**
- Re-implementing btop's layout engine or drawing.
- Editing the derived generated `.theme` in place as a source of truth.
- Adding new btop theme keys (btop's key set is fixed).
- Changing the runtime's palette derivation or the existing reload behavior.

## Decisions

### D1. Standalone AGS app, launch-on-demand
Mirror the icon editor: `src/gui-tools/btop-theme-studio/`, its own AGS instance, launcher bin, `SUPER` keybind; not in the bar, not autostarted. *Alternatives:* a window inside the runtime AGS (couples authoring to the bar); a separate GTK4/Python app (AGS is already a dependency and the precedent is AGS).

### D2. Component schematic driven by btop's real config, not a re-implemented layout
Parse `shown_boxes` and `presets` from `btop.conf`; the preset selector re-lays out the schematic's box set; warn when a key paints a module the preset hides. *Alternatives:* port `Draw::calcSizes()` (rejected — version-drifting re-implementation); fixed invented layout (rejected — the reason the first mock "looked like a different app").

### D3. Preview is the real btop binary (pty + terminal emulator)
Run `btop --no-tty --force-utf` on a 200×50 pty pointed at the candidate theme; reconstruct the frame with a terminal emulator (`pyte`). *Alternatives:* re-implement btop's drawing (rejected — the "phased rows" drift); capture a PNG (heavier, no better).

### D4. Warm process + `SIGUSR2` delta capture
Keep one warm btop process; per edit write the theme, send `SIGUSR2` (full redraw), and parse only the post-signal bytes. Measured ≈0.8 s/edit vs ≈2.8 s for a fresh spawn. A preset change or an oversized transcript respawns. *Alternatives:* fresh spawn per edit (slow); N-process pool (idle `/proc` burn, lifecycle cost, not needed). Fallback: fresh capture if a future btop makes the redraw partial.

### D5. Column-accurate rendering via font, not per-cell spans
Render the frame in a `<pre>` with a monospace font stack that includes braille and box-drawing at one advance (`JetBrainsMono Nerd Font`, `Adwaita Mono`, `DejaVu Sans Mono`). The raw grid is already column-correct; the earlier misalignment was a missing-braille font fallback. *Alternative:* per-cell fixed-width spans (bulletproof but heavy) — keep as fallback.

### D6. Save target = Repo | Installed, no path selection
Two-way toggle. **Repo** = repo-authoritative source deployed by `bootstrap` (default). **Installed** = write straight into `<install>/config/btop/themes/` and reload live (`SIGUSR2`). The resolved destination is shown read-only; the diff and action follow the target. *Alternatives:* ICME-style path pickers (rejected — the user wants only a repo/installed choice); seed-once machine-owned manifest (rejected historically — repo edits silently stop propagating).

### D7. Generated theme is a palette-linked, read-only base; authored themes are static
The generated `colors.btop` follows the wallpaper and is forked to edit; authored themes are static `.theme` files independent of the wallpaper. *Rationale:* editing the generated output is futile (re-derived); forking bakes the current palette into an owned theme.

### D8. Key→widget map generated from source, with a drift guard
Generate from `btop_theme.cpp` (key set) + `btop_draw.cpp` (attribution, including gradient names passed into `Draw::Graph`/`Meter`). Verify by re-deriving and comparing. *Alternatives:* hand trace (rejected — it produced wrong modules, e.g. `used`).

### D9. Palette editing: palette + arbitrary colour + transparent + gradient stops
Offer ramp, `color0–15`, named tokens, a native arbitrary colour picker, a hex field, a `transparent` (empty-value) option, and a start/mid/end gradient editor with "add middle colour". *Rationale:* btop supports empty-value transparency and exactly three gradient stops; the tool must not imply more.

### D10. Active theme is a repo-owned setting
The active `color_theme` is chosen from a repo setting rendered into `btop.conf`, so it survives re-provisioning; `save_config_on_exit = false` keeps btop from rewriting the spine config. Provisioning ships authored themes into the spine themes dir **alongside** the generated pointer, which stays a runtime-owned pointer into `current/`. *Alternative:* runtime state only (would be reset by re-provisioning the rendered config).

### D11. Preview controls live in the schematic, not the live preview
The load control, fixed-fill levels, and backdrop toggle affect only the component schematic; the live preview always shows btop's real data. *Rationale:* the live pane's value is that it is btop's actual output — injecting synthetic load there would break that contract. *Alternative:* drive the live pane with synthetic data (rejected — no longer btop).

## Risks / Trade-offs

- **`SIGUSR2` full-redraw assumption** → keep the fresh-capture path as a fallback and re-verify on btop version change.
- **Vendored btop source** (for the generator) → pin to a version (`v1.4.7`), keep the drift guard, and honour the upstream licence; refresh deliberately.
- **Attribution heuristic** (`Mem::draw` paints both mem and disks) → document it in the artifact and include call sites so it is auditable.
- **Warm-process resources** → a single process, bounded transcript; no pool.
- **`pyte` dependency** → confined to the live engine; the schematic needs none.
- **Installed target for the generated theme** → it is a derived pointer; recommend repo-only for generated and warn on Installed.
- **PoC is browser+HTTP** → the AGS tool should embed a terminal (VTE) for the live view and drive the same reload; the pty+emulator approach in `prototype/` is the reference behavior, not the final integration.

## Migration Plan

Additive: new GUI tool + provisioning additions + a repo setting. No migration of existing data. Rollback = stop launching the tool and revert the provisioning/settings additions; the existing generated theme and reload path are untouched.

## Open Questions

- The exact settings key/name for the active theme.
- Whether the shipped AGS app embeds a VTE terminal for the live view or reuses the pty+emulator engine (behaviorally identical per the `btop-live-preview` spec).
