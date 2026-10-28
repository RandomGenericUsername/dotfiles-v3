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

**Where the roles live now (S6b/S7).** This is a design record for the install
spine, not a source map. The Ansible implementation it names — `config_links`,
`assets`, `compositor_configs`, `config_copies`, `settings`, `verify` — is the
pinned external `dotfiles-provision` engine repo (tag in
`dotfiles/provisioning/installer.pin`); the corpus these roles read is the
pinned `dotfiles-assets` repo (`dotfiles/provisioning/assets.yaml`). This repo
authors neither: it owns the manifests, the runtime and the gates. The full pin
set is `ARCHITECTURE.md` §4.1.

**AGS app surfaces are list-driven (AD-31/AD-32).** The seven AGS apps are
declared once in `dotfiles/provisioning/apps.yaml`; the install dir, repo/tag,
config/spine/XDG links, optional bin link, launcher, autostart and launch policy
all come from that entry. `ags_apps_units` is the only owner; `config_links`
must NOT expose an AGS basename, and `make deploy-coverage` fails if the engine
and list disagree. All seven entries are `owner: standalone`; each app installs
as an immutable tag and the cutover never hot-swaps a link under a running app.
The field semantics and one-owner rule are in
[`102-ags-app-consumption.md`](./102-ags-app-consumption.md).

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
│   ├── hypr/                    13 Lua modules (12 static + hyprland.lua's one rendered path)
│   ├── ags/                     LIVE LINK → <install>/apps/bar/<tag>/ (the standalone ags-bar unit; no source here)
│   ├── ags-notifications/ …     LIVE LINKS → each app's <install>/apps/<installDir>/<tag>/
│   ├── theme-producer/          settings.toml + templates/ (the pinned tpr producer)
│   ├── hyprpaper/               hyprpaper.conf
│   ├── nvim/                    (pinned dotfiles-assets configs/nvim copy)
│   ├── starship/                starship.toml
│   ├── wlogout/                 layout (copied from the corpus) + style.css (RENDERED from the corpus template)
│   ├── zsh/                     .zshrc (RENDERED from the corpus's templates/zsh/.zshrc.j2; no .j2 is deployed)
│   ├── color-scheme-generator/  settings.toml + templates/
│   ├── weg/                     settings.toml + effects.yaml
│   └── itr/                     settings.toml
├── wallpapers/  icon-templates/  icon-mappings/   (assets, unchanged)
├── assets/<tag>/               the pinned dotfiles-assets checkout: icons/, templates/, configs/,
│                               content/, desktop/ — the SOURCE for every copy and render above
├── (removed — Epic 4) `generated/` — runtime owns all derived artifacts under `$XDG_STATE_HOME/dotfiles/`
└── (removed) csg-templates/  →  config/color-scheme-generator/templates/
└── (removed) weg-effects.yaml →  config/weg/effects.yaml
```

**Where the static config files come from (S2).** `hypr/`, `hyprpaper/`, `rofi/`, `nvim/`,
`starship/` and wlogout's `layout` are copied or rendered FROM the pinned `dotfiles-assets`
checkout (`<install>/assets/<tag>/configs/`, class `configs`), never from this repo. They are
byte-identical to the files this repo used to carry; the pin is `assets.tag` and each role
mirrors it (`compositor_configs_assets_pinned_tag`, `config_copies_assets_pinned_tag`).

**Where the template sources come from (S3).** Every Jinja source — `.zshrc.j2`, `style.css.tpl`,
`kitty.conf.j2`, `btop.conf.j2` and the five display-manager templates — now lives in the same
pinned checkout under `templates/` (`<install>/assets/<tag>/templates/`), one `*.vars.schema.json`
beside each. The five rendering roles (`zsh_config`, `kitty_config`, `btop_config`,
`wlogout_config`, `display_manager`) supply the VALUES and keep every `dest`, `mode`, `become` and
task-supplied var unchanged; they no longer carry a `templates/` dir. Nothing in this repository is
a template source any more, and since R-07 it authors no config tree either: the btop
`active-theme` preference is host state in the install spine
(`<install>/config/btop/active-theme`, written by the studio). The required-var parity test
(`tests/unit/test_template_vars_parity.py`) asserts that
every schema `required[]` name is supplied by its render task, and `deploy-coverage` asserts each
render reads the pinned checkout. `wlogout_config` also prunes the pre-S3
`<spine>/config/wlogout/style.css.tpl`, and `verify` asserts it is absent.

**Where the desktop entries come from (S4).** The six per-user `.desktop` entries and
`toggle-touchpad` live in the same pinned checkout's `desktop/` class
(`<install>/assets/<tag>/desktop/{applications,scripts,desktop.yaml}`).
`compositor_configs` copies the entries into `$XDG_DATA_HOME/applications/` (0755 for the helper
into the user bin dir) and **resolves `desktop.yaml` before the copy** (spine AD-10 layer 2): a
missing `requires` binary fails the run naming entry and binary, a missing `optional` one is
reported and that entry is skipped. `verify` re-asserts the deployed set, resolves each deployed
`Exec` binary on PATH, and checks every keybind-invoked launcher is executable (layer 3). This repo
authors no desktop entry and no helper script any more; `deploy-coverage` asserts both retired
trees stay absent.

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

### Migrate-then-symlink (GTK consumer dirs, gt-3-1)

The GTK dirs (`~/.config/gtk-3.0`, `~/.config/gtk-4.0`) are managed spine
entries that carry a per-entry **seed flag**: for these entries the guard
COPIES the pre-existing dir's contents into the freshly-created spine dir
BEFORE the move-aside (`ansible.builtin.copy`, `remote_src: true`,
trailing-`/` contents-into-dest), so the user's files (e.g.
`gtk-3.0/settings.ini`, their `gtk.css`) live in the spine and the timestamped
backup preserves the ORIGINAL verbatim. Ordering is pinned
**seed → backup → symlink**: a seed failure aborts the run while the user's
live dir is still intact (no backup taken, no link created) — re-run
re-classifies the real dir and retries cleanly.

After the backup, an idempotent palette-import line
(`@import "colors.css";`) is ensured in the SPINE `gtk.css`
(append-if-absent — re-runs never duplicate it; a migrated user `gtk.css`
keeps its existing content verbatim with the import appended at EOF; a fresh
machine gets a new `gtk.css` containing exactly the import line). The import
points at `colors.css`, which the RUNTIME seeder creates inside the spine
dirs on the first seed (a missing import file is harmless to GTK).

**nwg-look write-through:** post-link, nwg-look (and any GTK tool) writes
`settings.ini` IN the spine through the symlink — the write survives re-runs
and repo changes; the backup guard migrates the pre-spine original into the
spine at first link.

Dry-run note: under `--check` the backup move-aside is skipped, so a
conflicting pre-existing dir is still on disk when the link task evaluates;
the link task therefore skips its prediction ONLY in that case (a fresh
machine's absent target is still predicted as a would-change). A real run
resolves the conflict via the move-aside and creates the link.

## Role changes

| Role | Change |
|---|---|
| **filesystem** | creates `<install>/config/` and the tool subdirs (was: XDG dirs only) |
| **assets** | WEG effects → `config/weg/effects.yaml`; CSG templates → `config/color-scheme-generator/templates/` (was `<install>/weg-effects.yaml`, `<install>/csg-templates/`) |
| **compositor_configs** | renders the pinned corpus's 15 non-bar skeletons into `spine/config/{hypr,hyprpaper,rofi}/` and, since S4, deploys the pinned `desktop/` class: six entries into `$XDG_DATA_HOME/applications/` (after resolving the contract's `requires`/`optional`) and `toggle-touchpad` 0755 into the user bin dir (was: repo skeleton copies + repo `dotfiles/applications/` + `dotfiles/scripts/`; the corpus is `dotfiles-assets` since S2/S4) |
| **config_copies** | copies the pinned corpus's `configs/` class → `spine/config/{nvim,starship,wlogout}/` (was: repo dirs into `~/.config/...`; `zsh` left the set in S2 — zsh_config renders `.zshrc` from the template source) |
| **zsh_config / kitty_config / btop_config / wlogout_config / display_manager** | render their files from the pinned corpus's `templates/` class (S3; `<install>/assets/<tag>/templates/…`) instead of a repo/role `templates/` dir. Values, `dest`, `mode`, `become` and supplied vars unchanged; wlogout_config also prunes the pre-S3 `<spine>/config/wlogout/style.css.tpl` |
| **settings** | renders → `spine/config/{color-scheme-generator,weg,itr}/settings.toml` (was `~/.config/...`); CSG `default_formats = []` (interactive = all catalog formats) |
| **default_palette** | `--templates-dir <install>/config/color-scheme-generator/templates` |
| **config_links (NEW)** | backup guard + symlink step for all managed dirs |
| **icons (REMOVED — Epic 4)** | role deleted; runtime derives icons per wallpaper into `cache/icons/<ih>/` |
| **verify** | criterion 9 flips to symlink assertion (below); icons criterion is `current/icons/` populated (Epic 4) |

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
