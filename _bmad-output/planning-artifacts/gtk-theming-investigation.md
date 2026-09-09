# GTK Theming Consumer — Investigation & Architecture Plan

> Cross-domain remediation (Phase 2.x): the system GTK toolkit (GTK3 + GTK4/libadwaita)
> and new-shell terminal colors are not runtime consumers. This document records the
> investigation; `epics-gtk-theming.md` carries the executable breakdown.
> Built in worktree `feat/gtk-theming-consumer` so master work is untouched.

## 1. Problem analysis

Three defects, one shared root cause — **the consumer set was defined too narrowly**
(`consumer-wiring.md` pins AGS, Hyprpaper, ITR, terminal-OSC only).

| # | Symptom | Root cause | Owning actor |
|---|---|---|---|
| P1 | GTK4/libadwaita surfaces (bar buttons, menus/popovers, screenshot tool, **icme**) render default **light Adwaita** | libadwaita ignores `gtk-theme-name`; palette emits only custom `@define-color color_*` names; nothing links the palette into `~/.config/gtk-4.0/` | csg (format) + runtime seeder (pointer) |
| P2 | GTK3 apps frozen on static Arc-Dark | `settings.ini` is a user-owned file outside the spine; no GTK3 palette surface (`gtk.css @import`) exists | provisioning (config-in-spine) + seeder |
| P3 | New shells themed from **orphaned** `generated/palettes/colors.sequences` (pre-Epic-4, never updated); live OSC recolors only the launching terminal | `dotfiles/config/zsh/.zshrc.j2:30` cats a tree Epic 4 deleted; runtime cache never emits the sequences artifact | provisioning (zsh_config) + runtime (artifact set) |

Verified on-machine evidence (2026-09-07):

- `~/.config/gtk-3.0/settings.ini` — `gtk-theme-name=Arc-Dark`, user-owned (Nov 2025), not in spine.
- `~/.config/gtk-3.0/gtk.css` — xfce-era padding only; `~/.config/gtk-4.0/gtk.css` — **absent**.
- AGS `app.tsx` applies `colors.css` at runtime; `style.css` references `@color_*` custom names,
  so the bar is themed but its button chrome falls through to the GTK4 default theme.
- **icme** (`src/gui-tools/icon-color-mapping-editor`) is an AGS/GTK4 app
  (`import { Astal, Gdk, Gtk } from "ags/gtk4"`) → same libadwaita root cause as P1.
- `~/.local/share/dotfiles/generated/` still exists (orphaned, Epic-4-ignored);
  `.zshrc` cats `generated/palettes/colors.sequences` from it.
- csg already ships the `sequences` format (`ColorFormat.SEQUENCES`,
  `colors.sequences.j2`) — the runtime artifact set simply never included it.
- `~/.local/state/dotfiles/current/` holds `colors.{conf,yaml,gtk.css}` + wallpaper/effects/icons.

Key architectural insight: **GTK theming is a consumer-pointer problem, not a reload
problem.** GTK reads CSS at process start; the "apply" is the symlink flip (same as
AGS's R2 pointer). No daemon, no hot-reload; relaunch picks up new colors.

## 2. Actor duties (hexagonal, each actor keeps its job)

| Actor | Duty | NOT |
|---|---|---|
| **csg** (compute provider) | derive palette → formats; owns the adw mapping semantics (palette slot → libadwaita named color); new `ColorFormat.ADW_CSS` + template | never imports runtime/provisioning |
| **runtime domain** | `PaletteArtifacts` grows: `colors_adw_css`, `colors_sequences` (same `sha256(ph‖templates)` key — no formula change) | no I/O |
| **runtime ports** | NEW `IConsumerPathSpec` (declarative consumer-pointer table) + `IColorSchemeGenerator` artifact list extension | no concrete logic |
| **runtime adapters** | `CsgAdapter` requests `-f adw.css -f sequences`; `CacheSeeder.repoint_consumer_symlinks` becomes a generic spec loop (null-palette removal, file-replace, never-dangling rules unchanged); `TerminalColorApplier` reads `current/colors.sequences` bytes instead of re-deriving OSC | no per-consumer hardcoded repoints |
| **runtime application/cli** | zero new use cases — reconcile/seed/doctor/inspect consume the spec | — |
| **provisioning** | config-in-spine for GTK: spine `config/gtk-3.0/` + `config/gtk-4.0/` (`gtk.css` `@import "colors.css";` skeleton + migrated user files via backup guard); `config_links` symlinks; `zsh_config` repoints the cat → `current/colors.sequences`; verify criteria | never writes under `state_root` |
| **consumers** | read through `current/` at startup: AGS, GTK3 apps, GTK4/libadwaita apps, new zsh shells | — |

§11 boundary intact: runtime never edits provisioning-rendered files (pointers only,
AD-11 exception extended); provisioning never writes under `state_root`.

## 3. The scalability move: declarative consumer wiring

Today `repoint_consumer_symlinks()` is hardcoded AGS-only. Every future consumer
(rofi, dunst, wlogout…) would mean bespoke code. Instead, pin a **ConsumerPointer
table** in `shared-data-contract.md`:

```yaml
consumer_pointers:
  - { path: "{install}/config/ags/colors.css",     target: "current/colors.gtk.css" }
  - { path: "{install}/config/gtk-3.0/colors.css", target: "current/colors.gtk.css" }
  - { path: "{install}/config/gtk-4.0/colors.css", target: "current/colors.adw.css" }
rules:
  - palette null → remove existing pointer (missing_ok)
  - regular file at destination → replace with symlink (one-run migration)
  - target artifact missing → skip + warn (never a dangling consumer link)
```

One adapter loop implements the rules once; adding a consumer = one spec line +
its `@import`. Doctor, `inspect status`, and (Phase 3) prune inherit coverage for free.

## 4. Contract changes (shared-data-contract.md)

1. **Palette artifact set**: `colors.yaml, colors.conf, colors.gtk.css` →
   `+ colors.adw.css, colors.sequences` (`PaletteArtifacts` TypedDict, per-entry
   `meta.json` artifact_hashes, `CsgAdapter` expected set, inspect/reconcile
   expected-name lists, `derive.py` hash map).
2. **Consumer-pointer table** (§3) replaces the AD-11 single-symlink prose;
   ARCHITECTURE-SPINE AD-11 exception extended (same class: consumer *pointers*).
3. **Swap sequence**: unchanged — new pointers ride the existing repoint step.
4. **`.zshrc` contract**: `cat "$XDG_STATE_HOME/dotfiles/current/colors.sequences" &`
   (absent until seed → harmless backgrounded cat).

## 5. adw.css mapping (csg-owned semantics, pinned in csg docs)

| libadwaita named color | palette source |
|---|---|
| `window_bg_color`, `view_bg_color`, `headerbar_bg_color`, `card_bg_color`, `dialog_bg_color`, `popover_bg_color`, `sidebar_bg_color` | `background` |
| `window_fg_color`, `view_fg_color`, `headerbar_fg_color`, `card_fg_color`, `sidebar_fg_color` | `foreground` |
| `accent_color`, `accent_bg_color`, `accent_fg_color` | `color_04` (+ `color_05` alt) |
| `destructive_*` | `color_08`/`color_09` pair |
| `success_*` / `warning_*` / `error_*` | `color_06`/`color_10` + `color_12`/`color_14` mapping, pinned once in the template |
| `@define-color color_00..15` | passthrough (GTK3-compatible custom names stay available) |

## 6. Risks / tradeoffs

| Risk | Mitigation |
|---|---|
| Running GTK apps don't re-theme | documented relaunch-pickup (same class as AGS restart); no daemon (P5) |
| `nwg-look` writes `settings.ini` | after config-in-spine it writes *through* the symlink into the spine — survives; backup guard migrates the original |
| adw named-color coverage varies per app | mapping pinned in csg docs; gaps = future csg template edits — cache keys auto-invalidate (Phase 3 invalidation guards this) |
| `generated/` orphan keeps confusing | `.zshrc` becomes state-root-only; orphan stays ignored by every gate |
| GTK4 `@define-color` override mechanism | documented libadwaita override channel (`~/.config/gtk-4.0/gtk.css`); verify against installed libadwaita version in G1.1 verification step |

## 7. Execution choice

**BMad epic/stories** (not OpenSpec): matches the repo's runtime precedent (Phase 2
executed via BMad stories with GWT ACs + sprint-status integration + cross-domain
story pattern from Epic 4), and this task is story-sized with per-story testable
acceptance criteria (layering tests, adapter unit tests, contract pins) — OpenSpec's
spec-delta format adds ceremony without adding testability here.
