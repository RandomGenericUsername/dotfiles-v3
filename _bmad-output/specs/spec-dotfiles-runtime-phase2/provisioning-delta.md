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

## The consumer-path symlinks are runtime-owned (AD-17, R2 DONE in Epic 4)

The R2 symlink (`<install>/config/ags/colors.css` →
`$XDG_STATE_HOME/dotfiles/current/colors.gtk.css`) is created by the
**runtime seeder** (`repoint_consumer_symlinks`, rt-4-2) — NOT by
provisioning apply. Provisioning's `compositor_configs` places skeletons
only; the Story 1.12 dont-clobber guard is retired with the fragment-copy
tasks it guarded (nothing left to guard — provisioning never writes
palette fragments anywhere).

| # | Provisioning role / file | Bootstrap state (pre-seed) | Post-seed (runtime-owned) |
| --- | --- | --- | --- |
| 1 | `compositor_configs` — AGS `colors.css` | absent (no copy) | seeder symlink → `current/colors.gtk.css` |
| 2 | ITR `settings.toml` | `color_scheme.path` → `current/colors.yaml` (static string; file absent until seed) | resolves per render |
| 3 | `hyprpaper` conf template | points at `<install>/wallpapers/default.png` (fresh boot shows default) | per-monitor IPC overrides with resolved `current/` paths |
| 4 | `settings` (WEG/CSG) | scratch/output defaults under XDG cache | env overrides per render |

## Provisioning's actual deltas (Epic 4 — replaces the list below)

1. **Delete** `default_palette` + `icons` roles and their playbooks; add the
   `runtime-seed.yaml` step (`wallpaper set default.png`) after
   `config-links`, before `display-manager`/`verify` (rt-4-1).
2. **`verify` criterion 6:** `current/colors.{conf,yaml,gtk.css}` ONLY
   (no `generated/` OR-branch); icons criterion: `current/icons/` ONLY.
3. **Retire the dont-clobber guard (R3)** with the fragment copies.
4. Provisioning deploys `<install>/` inputs only; `<install>/generated/`
   is gone (orphaned trees on upgraded machines are left in place and
   ignored by every gate).

## What does NOT change

- The install spine structure (`wallpapers/`, `generated/`, `config/`, `icon-templates/`, `icon-mappings/`) stays as provisioning owns it.
- csg/weg/itr rendered `settings.toml` stays provisioning-owned; runtime overrides output via env vars per call (AD-7).
- Provisioning gains no runtime knowledge: it does not manage `cache/`, `current/`, or the state store.

## Boundary rule

Runtime never writes under the install spine after seeding (AD-11). Provisioning never writes under `$XDG_STATE_HOME/dotfiles/` (AD-5). The only cross-boundary reads are runtime reading spine inputs (templates, catalog, icon templates/mappings) for cache keys.

## Verify gate interplay

`dotfiles-provision verify` continues to assert provisioning done-criteria against provisioned locations only. Criterion 6 is the one that must tolerate a post-runtime machine. The other thirteen are unaffected.

## Display manager: SDDM + Pixie (2026-08-19)

Provisioning's **display_manager** role provisions **SDDM + the Pixie theme** with a **Wayland greeter** (`DisplayServer=wayland`, no X11/GPU grab — avoids the hard-freeze Hyprland suffered with X11 greeters). Cross-domain relevance to the runtime: the login manager is the entry point that boots into Hyprland + the AGS bar.

- `packages.yaml` group_vars: `display_manager: [sddm, qt6-declarative, qt6-svg]` (also installed by the packages role in the aggregate).
- `display_manager` role: install sddm+Qt6, git-fetch the Pixie theme → `/usr/share/sddm/themes/pixie`, render `/etc/sddm.conf.d/10-dotfiles.conf` (theme=pixie, `DisplayServer=wayland`), enable `sddm`, disable `greetd`/`lightdm`, remove the legacy `display-manager.service` alias.
- Retained fallback: `display_manager_type: greetd-regreet` keeps the prior greetd+tugreet/regreet path switchable.
- This is a provisioning-side capability (domain 1); the runtime treats it as an external entry point, not a managed consumer of `current/`.

## cli_tools PATH resolution fix (2026-08-19)

The `cli_tools` role's `cli_tools_bin_dir` now resolves exactly as `uv` does (`$UV_TOOL_BIN_DIR → $XDG_BIN_HOME → $HOME/.local/bin`) and the install task pins `UV_TOOL_BIN_DIR` to it. Previously it hardcoded `$HOME/.local/bin`, which under this project's custom XDG layout pointed at a dir uv never wrote — so `csg`/`weg`/`itr` failed to resolve on PATH after a successful `uv tool install`, blocking the `default_palette` → `compositor_configs colors.css` chain and any manual tool use. `~/.local/bin` is also added (guarded) to the rendered `.zshrc`.

## Fresh-machine verification status (2026-08-19)

Both the **AGS bar** bundle (install via AUR → `~/.config/ags` symlink → `app.tsx`/`style.css` → runtime `apply_css`) and the **SDDM + Pixie** login manager are **task/file-verified in a fresh container** (proven: `ags` binary installs, bar project lands, sddm binary installs, Pixie theme fetch + sddm.conf render). **Pending end-to-end hardware confirmation via a QEMU VM:** the container host cannot (a) build the `csg` container image (needs a non-nested engine) so the palette `colors.css` step is unproven end-to-end, and (b) run `systemctl enable sddm` (needs a real PID1/systemd) so the SDDM boot-to-login is unproven. See epic stories 1.4 (CSG determinism), 1.9/2.x (palette), and the display-manager role for the concrete steps.
