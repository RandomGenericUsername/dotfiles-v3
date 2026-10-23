## Context

The desktop palette contract (gt-2-2 consumer-wiring): the runtime owns `<state>/dotfiles/current/` artifacts; a `ConsumerPointer` table (`StaticConsumerPathSpec`) maps each consumer's spine path to a `current/` artifact; the seeder repoints the symlink on every seed/reconcile. "Adding a consumer = ONE spec line + its `@import` — never adapter code." AGS, GTK-3.0, and GTK-4.0 already consume this way.

csg already ships `defaults/templates/colors.rasi.j2` producing a `* { background/foreground/cursor/color00..15 + metadata }` block — rofi parses unknown global properties as user variables (validated on the host: `rofi -theme <csg-generated rasi>` exit 0), and rofi's `@import` resolves relative to the importing file (`man rofi-theme`; validated on the host with the nested layout). `ColorFormat.RASI` exists in csg's enum and catalog. The only missing pieces are: the runtime requesting the format, carrying it through the cache/current chain, and the consumer wiring + launcher config.

The rofi root palette is shared by every future rofi tool: `<install>/config/rofi/colors.rasi` (runtime symlink) + each tool subdir doing `@import "../colors.rasi"`. Nested layout chosen because the user is building multiple rofi-based tools and wants one dedicated directory per tool under the rofi config root.

## Goals / Non-Goals

**Goals**
- Pressing `SUPER+D` opens a themed rofi drun launcher that consumes the current wallpaper palette and follows re-themes on relaunch.
- A nested `config/rofi/` layout that makes adding the next rofi tool a copy of the pattern, not a redesign.
- Full provisioning: package installed from the manifest, config placed in the spine, `~/.config/rofi` linked, verify asserts it, keybinding wired.
- The runtime palette chain grows to exactly six artifacts without a reloader daemon.

**Non-Goals**
- No additional rofi tools beyond the launcher.
- No live re-theme of an open rofi window; relaunch-pickup only.
- No csg template changes (rasi template already correct).
- No AGS bar widget for the launcher.
- No Hyprland window rules or `layerrule`/blur for the launcher (D7 — layer-shell overlay, rules don't apply, crisp fidelity).

## Decisions

### D1. rofi (Wayland-native) is the launcher engine; wofi is removed from the manifest

rofi 2.0.0 is installed on the host and is the most flexible/customizable of the three candidates (rasi theme language, multiple modes, script modes). wofi is currently a manifest ghost (listed in `packages.yaml`, mapped nowhere, never installed). The manifest is corrected to `rofi` and both `group_vars` package maps gain a `rofi` entry (Arch `rofi` is the Wayland fork; Debian-family carries the same logical name for symmetry).

### D2. Nested config: one subdirectory per rofi tool, shared palette at the rofi root

```
<install>/config/rofi/            (linked → ~/.config/rofi)
├── colors.rasi                   RUNTIME symlink → current/colors.rasi (ConsumerPointer)
├── launcher/
│   └── config.rasi               @import "../colors.rasi" + drun theme
└── <future-tool>/                same pattern
```

The palette import stays at the rofi root so every tool shares one runtime pointer. `@import "../colors.rasi"` resolves relative to the importing file (validated). A future tool = new subdirectory + one compositor_configs skeleton entry + one keybind if needed — zero runtime changes.

### D3. Runtime: `colors.rasi` becomes the sixth palette artifact via the existing pinned-tuple pattern

Every place the five-name artifact tuple appears grows by one (`colors.rasi`), mirroring how `colors.adw.css`/`colors.sequences` were added in gt-2-1 (coordinate, never re-decide):

- `csg_adapter.py` — add `--format rasi` to the args list; add `colors.rasi` to the post-run artifact verify set; hash it into `PaletteArtifacts`.
- `domain/models.py` — `PaletteArtifacts` TypedDict gains `colors_rasi: str`.
- `application/derive.py` — `PALETTE_ARTIFACT_NAMES` tuple gains `"colors.rasi"`; the `artifact_hashes` dict written to meta.json gains the entry.
- `adapters/seeder.py` — `write_palette_meta_in` parse gains `colors_rasi`; `repoint_current_symlinks` palette tuple gains `"colors.rasi"`.
- `application/reconcile.py` — the three pinned tuples (`_derive_skipped`, `_cleanup_stale_symlinks`, `_build_expected_targets`) each gain `"colors.rasi"`.
- `adapters/json_state_repository.py` — the sentinel-shape dict gains `colors_rasi`.

Consequence (intended, one-time): `ensure_palette_entry_complete` treats existing five-artifact cache entries as incomplete and evicts+regenerates them on first reconcile — same migration mechanism as gt-2-1 AC 8.

### D4. Consumer pointer at the rofi root, target `colors.rasi`

`StaticConsumerPathSpec.consumer_pointers()` gains:
`ConsumerPointer(path="config/rofi/colors.rasi", target="colors.rasi")`.

This is the only runtime consumer change. The seeder's missing-parent rule skips+warns until the compositor_configs role creates the spine dir (never mkdir into the spine).

### D5. Keybinding repoints `SUPER+D`, no wrapper script

`keybindings.lua:29` becomes `hl.dsp.exec_cmd("rofi -config ~/.config/rofi/launcher/config.rasi -show drun")`. The path relies on config-links exposing `~/.config/rofi`; shell tilde expansion applies in Hyprland's `sh -c` execution. If a future need for a fixed launcher entry point (non-tilde, or env-independent) arises, a `compositor_configs_bin_scripts` wrapper (the `toggle-touchpad` pattern) can be added — deferred, not built now.

### D6. Launcher theme: measured-fidelity spec (from the reference screenshot)

The user provided a full-desktop reference screenshot of the target launcher. The model cannot view images, so the reference was analyzed **programmatically** (ImageMagick pixel sampling of the pasted PNG recovered from the session store) and every value below is measured, not guessed. Native-resolution measurements (1922×1080, ~1x):

| Element | Measurement | Runtime mapping (confirmed by user: palette roles) |
|---|---|---|
| Window | **panel-sized, dead-centered** on screen (center ≈ 959.5, 539 ≈ screen center); floats on the live wallpaper with **no dim backdrop** | `location: center; width: 548px; transparency: "real"` |
| Border | **4px** `#B4A1DB` (muted lavender) | `@color04` (dim blue accent) |
| Dark ring (border→body) | **2px** `#262636` — color equals the search-bar surface | `@color01` via the `window` padding zone (`padding: 2px`) between border and `mainbox` |
| Panel body | `#1E1E2E`, outer radius **≈12px** | `@background`, radius 12px |
| Padding (body→elements) | **18px** all around (bottom ~14px) | `mainbox` padding |
| Search bar | **500×38**, radius **≈5px**, bg = the ring color; magnifier icon + placeholder `Search...` in gray `#A6A6A7` | bg `@color01`, placeholder `@color07` (G5-tunable, see below) |
| Gap searchbar→list | **21px** | `mainbox` spacing |
| List rows | **36px tall, spacing 0** (pitch exactly 36px), **8 visible**, no scrollbar, radius ≈5px | `lines: 8`, `spacing: 0`, `element` height 36 |
| Selection | full-row pill `#89B4FA` + **dark text** `#202030` | bg `@color10` (bright blue), text `@background` |
| Icons | **24px**, ~25px from element left edge; text ~12px after icon | `element-icon size: 24px` |
| Normal text | `#C5CBDA`–`#D6DDEC` (bright) | `@foreground` |
| Font | ~15–16px mono (text cap ~13px, 26px line incl. asc/desc) | `JetBrainsMono Nerd Font 12` |

Geometry self-checks against the measurements: `18 (top) + 38 (searchbar) + 21 (gap) + 8×36 (rows) + 14 (bottom) = 379px` ≈ measured body height 378px; element side inset 18px matches searchbar/rows x-offset from the body edge.

Two host-validated constraints shape the implementation:
1. **`rgba(@var, N%)` is unsupported in rofi 2.0** (verified: theme-load warning + fallback to the default theme). Alpha may only be a literal. The design is all-solid-color so this costs nothing. The transparent backdrop is achieved with `transparency: "real"` (the area outside the border is not painted) and the 2px ring is realized by the `window` padding zone: `window { transparency: "real"; border: 4px; border-color: @color04; background-color: @color01; padding: 2px; }` + `mainbox { background-color: @background; }` — the 2px padding shows `@color01` between border and body, the same token as the search bar, exactly like the image.
2. **The full theme structure parses under rofi 2.0** (validated with a probe theme mirroring the spec: `window` transparency real + border + `@surface` bg + 2px padding + radius 12; `mainbox` `@background` + radius 8 + spacing 21; `inputbar` `@surface` radius 5; `listview` lines 8/spacing 0/no scrollbar; `element selected.normal` accent bg + `@background` text; `element-icon` 24px) — `rofi -theme <probe> -dump-theme` exits 0 with every property applied.

The palette mapping is confirmed by the user (structure/geometry exactly like the image; colors from the runtime theme). Placeholder contrast (`@color07` on `@color01`) is the one value flagged G5-tunable: first fallback `@foreground`, second — if the surface contrast is genuinely wrong — adding derived alpha-carrying properties to `colors.rasi.j2` (a template change currently excluded by non-goals; noted, not done by default).

### D7. No compositor window rules for the launcher

rofi-wayland's default mode is a **layer-shell OVERLAY surface** (confirmed on the host: `-normal-window` is an explicit opt-in experimental flag we do not use). Hyprland `windowrule`/`hl.window_rule` applies to regular windows and has no effect on layer surfaces — the launcher never tiles, auto-floats, grabs its own keyboard, and positions itself. Everything the reference shows is achieved by the rofi theme alone (`location: center`, `width: 548px`, panel-sized window, no dim). The AGS bar and the icme editor's overlay are the same class of surface (see `window-rules.lua:16-22`), and no `layerrule` is added — the reference has no blur on the launcher, and crisp fidelity is the goal.

Rejected alternative, documented for the future: adopting `-normal-window` would make rofi a regular window and would THEN require a float + center + size rule in `window-rules.lua`. Not built now; noted in tasks 6.x so nobody later adds a dead rule or "fixes" a missing one.

## Gates / Harnesses (acceptance — nothing is "done" until these pass)

The change is considered complete only when every gate below is green. Each maps to a tasks.md item and, where applicable, to an automated harness.

- **G1 — Runtime artifact chain (automated).** `pytest src/runtime/tests` green with the six-artifact set: csg adapter requests rasi; `PaletteArtifacts`/meta.json carry `colors_rasi`; seeder parses, repoints `current/colors.rasi`, and creates the consumer symlink; reconcile's three tuples include rasi; sentinel shape parity. Unit + integration suites cover it.
- **G2 — Provisioning parity (automated).** `pytest src/provisioning/tests` green: packages manifest ↔ `test_yaml_manifest_reader` package set; compositor_configs skeleton-file count/list and config-dir list (test_compositor_configs_role); config_links ↔ verify `managed_link_dirs` parity (test_config_links_role); verify role assertions.
- **G3 — Real-machine provisioning (manual, scripted).** From the workspace: `assets` + `compositor-configs` + `config-copies`(if touched) playbooks against `install_dir=$HOME/.local/share/dotfiles`; then re-run → idempotent (no changes). Assert `~/.config/rofi/launcher/config.rasi` resolves through the spine and `~/.config/rofi` is a symlink to `<install>/config/rofi`.
- **G4 — Runtime on host (manual, scripted).** Reconcile / `wallpaper set` (session env): assert `~/.local/state/dotfiles/current/colors.rasi` exists (symlink to a six-artifact cache entry) and `<install>/config/rofi/colors.rasi` → `current/colors.rasi`. `dotfiles-runtime inspect` reports the pointer healthy.
- **G5 — Live launch + palette pickup (manual).** `SUPER+D` opens the launcher; rofi parse is clean (`rofi -config … -dump-theme` exit 0 with the live palette). Set a different wallpaper (`wallpaper set <other>`), relaunch launcher → colors follow. **Fidelity pass**: the launcher matches the reference geometry at 1x (panel-sized centered window over the live wallpaper, no dim; 4px border + 2px ring; search bar 38px; rows 36px; 24px icons; radius 12/5px) — any deviation corrected in `launcher/config.rasi` (G5 is the acceptance gate for the visual reference).
- **G6 — Future-tool extensibility (manual, structural).** A reviewer confirms the nested layout makes the next tool additive: new subdir + one skeleton entry, no runtime edits. Locked by the skeleton list growing by one and the shared `colors.rasi` import path being stable.

## Risks / Trade-offs

- **Rofi 2.0 rasi strictness on the generated `colors.rasi`** — the csg template's metadata properties (`source-image`, `backend`, `generated-at`) are non-standard global properties. Validated on host: rofi 2.0.0 parses them fine (exit 0). If a future rofi release rejects them, the fix is isolated to `colors.rasi.j2` (excluded from scope by non-goals, but the contract test in G1 catches breakage).
- **One-time cache regeneration** — every existing palette entry is evicted once (G4 observes it); expected, non-destructive, logged by the existing migration path.
- **Tilde expansion in the keybind** — relies on Hyprland's `sh -c`; the wrapper-script fallback (D5) is the mitigation if it ever breaks.
- **Manifest/group_vars drift root cause** — the wofi entry proves the manifest is not an install authority; tasks add the rofi mapping in both `group_vars` so the installed set matches the desired set. A broader "manifest ↔ group_vars parity" harness is out of scope (noted in non-goals).

## Resolved Questions

- *Which launcher?* rofi (D1). User-selected from the proposed set after tradeoff review.
- *Keybinding?* Keep `SUPER+D` (D5); it already exists and is repointed.
- *Where does colors.rasi live?* One runtime symlink at the rofi root (D2/D4); tool subdirs import it via `../colors.rasi` — not duplicated per tool.
- *Does the runtime need a reloader?* No (proposal non-goals); relaunch-pickup matches every other consumer.
- *Are Hyprland window rules needed?* No (D7) — layer-shell overlay; `windowrule` does not apply. Documented so the absence is intentional, not a gap.