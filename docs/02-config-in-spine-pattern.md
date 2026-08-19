# Config-in-Spine Pattern — Design

> Design decision record for relocating all managed configs into the install
> spine and exposing them via symlinks at the tools' native XDG locations.
> Supersedes the copy-into-`~/.config` mechanism for the managed set.

## Status

Adopted 2026-08-16. Replaces the "copy everything into `~/.config`" mechanism
for the managed config set (config-copies, compositor configs, per-tool
settings). Assets, generated output, and the CSG templates/effects catalogs
already live in the spine and are unchanged except for relocation into
`config/`.

## Motivation

Single source of truth for ALL machine configs inside the install target
(`$XDG_DATA_HOME/dotfiles/`). The user's stated goal: **the target directory
has all the configs, the settings, all** — one coherent tree that can be
versioned, backed up, and understood as a unit.

The CSG subdir-split flaw (settings under `color-scheme-generator/`, templates
under `color-scheme/`) was fixed first (commit `90d2a07`), so every tool now
uses one config subdir named after itself:

| Tool | Config subdir |
|---|---|
| CSG | `color-scheme-generator/` (settings.toml + templates/) |
| WEG | `weg/` (settings.toml + effects.yaml) |
| ITR | `itr/` (settings.toml) |
| compositors | `hypr/`, `ags/`, `hyprpaper/` |
| dotfiles | `nvim/`, `starship/`, `wlogout/`, `zsh/` |

## Core invariant (unchanged, reworded)

**Machine, not repo** — nothing references the repo checkout at runtime; the
machine keeps working after the repo is deleted.

**NFR-8 REWORDED** (the XDG-invariant reversal is a deliberate, documented
consequence):

> Spine Containment — the install dir is the single home for ALL managed
> config + data; `~/.config` is an alias layer whose entries are symlinks into
> the spine. Removing the spine leaves the `~/.config` symlinks broken (a
> machine is considered unprovisioned). Nothing references the repo checkout.

The previous wording ("wiping the data dir leaves nothing orphaned in the XDG
config tree") described the copy mechanism; it is superseded by the symlink
mechanism.

## Target layout

```
$XDG_DATA_HOME/dotfiles/                          ← install target
├── config/                                       ← ALL managed configs
│   ├── hypr/                    hyprland.conf + colors.conf (fragment)
│   ├── ags/                     app.tsx, style.css + colors.css (fragment)
│   ├── hyprpaper/               hyprpaper.conf
│   ├── nvim/                    (repo dotfiles/config/nvim copy)
│   ├── starship/                starship.toml
│   ├── wlogout/                 layout, style.css.tpl
│   ├── zsh/                     .zshrc.j2 (the legacy .zshrc was user-placed, not managed)
│   ├── color-scheme-generator/  settings.toml + templates/
│   ├── weg/                     settings.toml + effects.yaml
│   └── itr/                     settings.toml
├── wallpapers/  icon-templates/  icon-mappings/   (assets, unchanged)
├── generated/                                    (runtime output, unchanged)
└── (removed) csg-templates/  →  config/color-scheme-generator/templates/
└── (removed) weg-effects.yaml →  config/weg/effects.yaml
```

## Symlink mapping (machine side)

Every managed dir is symlinked at its native XDG location:

```
~/.config/hypr                → <install>/config/hypr
~/.config/ags                 → <install>/config/ags
~/.config/hyprpaper           → <install>/config/hyprpaper
~/.config/nvim                → <install>/config/nvim
~/.config/starship            → <install>/config/starship
~/.config/wlogout             → <install>/config/wlogout
~/.config/zsh                 → <install>/config/zsh
~/.config/color-scheme-generator → <install>/config/color-scheme-generator
~/.config/weg                 → <install>/config/weg
~/.config/itr                 → <install>/config/itr
```

Because the links point at the tools' **declared** XDG stops, native tool
discovery works with no env-var or `--flag` scaffolding:

- `weg info` resolves effects via `~/.config/weg/effects.yaml` → spine
- `csg` resolves templates via `~/.config/color-scheme-generator/templates` → spine
- `csg/weg/itr info --config ~/.config/<tool>/settings.toml` → spine

## New role: `config_links` (or a shared task include)

Owns the symlink step for ALL managed dirs. Runs AFTER the writing roles
(config_copies, compositor_configs, settings, assets). Single place that:
1. Ensures each `<install>/config/<name>` exists (created by the writing role).
2. Applies the **backup/migration guard** (below) to any existing
   `~/.config/<name>`.
3. Creates the symlink `~/.config/<name>` → `<install>/config/<name>`.
4. Is idempotent: a link already pointing at the correct target is a no-op.

## Backup/migration guard (safety layer)

Purpose: never destroy user-owned content when replacing an existing target.

### Exists-state classification (per target)

| State at `~/.config/<name>` | Action |
|---|---|
| already symlink → `<install>/config/<name>` | **no-op** (idempotent re-run) |
| real dir / real file / foreign symlink (ours-from-prior-copy, user's, or mixed) | **backup then symlink** |
| absent | create symlink, no prompt |

### Backup mechanics

- Whole-directory backup, always (the managed dirs can hold write-back files —
  e.g. `nvim/lazy-lock.json` — and user additions; a file-set backup risks
  dropping them).
- Destination: `~/.config/.dotfiles-backups/<name>-<timestamp>/` (timestamp =
  `%Y%m%dT%H%M%S`). Never a fixed path — a second run must not clobber the
  first backup.
- Backup is a **copy** (`ansible.builtin.copy` or `command: cp -a`), never a
  move: the user's live dir stays intact until the symlink takes over.
- The guard REPORTS what it found (e.g. "wlogout: directory with 3 entries
  incl. style.css symlink not managed by us") so the user knows what was backed
  up.

### Prompting policy (TTY-aware)

- **Interactive (`--ask-backup` / TTY present):** prompt per conflicting
  target — "existing nvim is not ours; back it up to
  ~/.config/.dotfiles-backups/nvim-<ts>/ and symlink? [Y/n]" — with an
  explicit "abort" option.
- **Non-interactive (no TTY, e.g. `bootstrap.sh`, CI, `--check`):** do NOT
  hang. Default to **auto-backup and proceed** (copy aside, then symlink) —
  lossless and safe. Fresh machines have no dirs, so this path rarely
  triggers.
- **`plan --check`:** the link task is check-gated (`when: not
  ansible_check_mode`); a dry run never prompts or writes.

### Safety guarantees

- Never `rm -rf` anything. The pre-existing target is always preserved as a
  backup copy before the symlink replaces it.
- Never prompts without a TTY.
- Never clobbers a prior backup (timestamped destination).
- A link already pointing at the correct spine target is never touched.

## Role changes

| Role | Change |
|---|---|
| **filesystem** | creates `<install>/config/` and the tool subdirs (was: XDG dirs only) |
| **assets** | WEG effects → `config/weg/effects.yaml`; CSG templates → `config/color-scheme-generator/templates/` (was `<install>/weg-effects.yaml`, `<install>/csg-templates/`) |
| **compositor_configs** | writes skeletons/fragments into `spine/config/{hypr,ags,hyprpaper}/` (was `~/.config/...`) |
| **config_copies** | copies repo dirs → `spine/config/{nvim,starship,wlogout,zsh}/` (was `~/.config/...`) |
| **settings** | renders → `spine/config/{color-scheme-generator,weg,itr}/settings.toml` (was `~/.config/...`); CSG `default_formats = []` (interactive = all catalog formats) |
| **default_palette** | `--templates-dir <install>/config/color-scheme-generator/templates` |
| **config_links (NEW)** | backup guard + symlink step for all managed dirs |
| **icons (NEW)** | invokes `itr render <install>/icon-mappings/icons.yaml --config <install>/config/itr/settings.toml` → `generated/icons/` (the chain previously never rendered icons) |
| **verify** | criterion 9 flips to symlink assertion (below); new done-criterion: `generated/icons/` populated |

## Verify gate changes (criterion 9 — bulletproof symlink check)

Replace the "real dirs, not symlinks" assertion with the 5-layer check per
managed dir:

```
1. islnk    stat follow:false          → stat.islnk == true      (it IS a link)
2. target   stat.lnk_target            → == <install>/config/<name>
3. resolves stat follow:true           → stat.exists and stat.isdir  (not broken)
4. content  stat through the link      → e.g. ~/.config/nvim/init.lua isreg
5. function existing parse gates       → csg/weg/itr info --config resolve through the link
```

Layer 2 uses an **exact** target match (not "under install_dir") so a link to
the repo, a moved location, or a wrong spine path fails. Layers 3-4 catch
broken/empty links. Layer 5 proves the tools work through the link.

Also add: verify asserts `<install>/config/weg/effects.yaml` and
`<install>/config/color-scheme-generator/templates/` exist (relocated
catalogs).

## NFR-8 wording update

Update in `epics-dotfiles-provisioning-phase1.md` (NFR-8) and
`chaining-spine.md` to the reworded invariant above. The previous wording
described the copy mechanism and is obsolete.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| nvim lazy-lock.json write-back through link | lands in spine (expected); regenerates; backup captures it on migration |
| broken links after spine wipe | verify layer 3 fails loudly; NFR-8 reworded to treat this as unprovisioned |
| migration destroys user dirs | backup guard copies before replacing; never rm -rf |
| wlogout style.css is a user symlink inside the managed dir | whole-dir backup captures it; survives as content in the spine copy |
| XDG semantic violation | documented + NFR-8 reworded (deliberate tradeoff) |

## Rollout

1. Apply the CSG subdir fix (done, `90d2a07`).
2. Implement the new role/step (config_links) + backup guard.
3. Relocate assets outputs (effects, templates) into `config/`.
4. Rewrite compositor_configs / config_copies / settings to write into
   `spine/config/`.
5. Flip verify criterion 9 + add the relocated-catalog asserts.
6. Update NFR-8 + chaining-spine wording.
7. Full suite + a live migration re-apply on this host.
8. (Follow-up) CSG `default_formats = []` + the icons render role — see
   commit `a91bfae`.
