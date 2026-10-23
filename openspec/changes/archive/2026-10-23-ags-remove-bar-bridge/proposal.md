# ags-remove-bar-bridge

## Why

Slice 2 of `ags-apps-bar-first` has landed (merge `16a9266e`): the live bar is now
the **pinned external unit** — `<install>/config/ags` is a symlink into
`<install>/ags-apps/bar-v0.1.0/bar`, installed by the `ags_apps` role. The
in-repo `dotfiles/config/ags/` tree is now only a **dev/typecheck/test bridge**,
and it is a byte-identical duplicate of `ags-apps/bar/`.

Evidence:

- `git ls-files dotfiles/config/ags | wc -l` → **115**; `git -C /home/inumaki/Development/dotfiles/ags-apps ls-files bar | wc -l` → **115** (same tree, slice 1 copied it verbatim).
- `compositor_configs_skeleton_files` carries **no** `dotfiles/config/ags/` entry
  (`src/provisioning/ansible/roles/compositor_configs/vars/main.yml:106-121`); the
  91 bar entries were retired by slice 2.
- `scripts/deploy-coverage.py:48-54` already calls `dotfiles/config/ags/` "the
  dev/typecheck/test source (the bridge)" — but lines `452` and `459` still
  **hard-require** `dotfiles/config/ags/app.tsx`, so this one gate cannot simply
  be deleted with the tree.

The bridge is dead weight: it duplicates `ags-apps/bar/`, and it pins a whole
family of **bar-only** gates in this repo (`bar-typecheck`, `ags-typecheck`,
`ags-test`, five mock-parity gates, seven audio validation tests,
`icons-json-drift`, the `ags-symbol-check` bar scan, the `contract.ts` pin half).
None of them can run once the tree is gone, and all of them belong to the bar's
own repo.

**This change removes the bridge. It does not implement anything.**

## What Changes

- **Delete `dotfiles/config/ags/`** (115 tracked files).
- **Retire the bar-dev gates** in this repo (`bar-typecheck`, `ags-typecheck`,
  `ags-test`/`ags-test-deps`, the five `*-mock-parity` targets, the seven
  `audio-*-test` targets, `speedtest-no-new-architecture`, `icons-json-drift`) and
  their CI jobs. `bar-typecheck` and `ags-test` already exist in `ags-apps`
  (`Makefile:88`, `Makefile:143`); the rest move to `ags-apps` as companions.
- **Rewrite `deploy-coverage`** so it asserts the provisioning shape (unit +
  live-bar link + shortcuts + no stale per-file bar entry + no retired
  `platform/` dir) **without** requiring the in-repo entry point.
- **Repoint** `ags-platform-dev` (drop the `dotfiles/config/ags/node_modules`
  link), `per-app-drift-symbol-suites` (drop `ags-symbol-check.mjs`), and the
  `ci-gates-parity` declared tables.
- **Update** the provisioning tests that read the in-repo tree
  (`test_compositor_skeleton_configs.py`, `test_gui_tools_role.py`,
  `TestDeployCoverageGate`), `AGENTS.md` §2, `.gitignore`, and the docs.

## Non-goals

- **Not deleting the other apps.** `src/gui-tools/**` and every deployed
  `config/ags-*` instance stay.
- **Not the redundant seam copies** (5 `icon-registry.ts`, 4 `event-bus*.ts`,
  popup chrome, 3 `theme.ts`) — those stay in `ags-delete-redundant-code`.
- **Not the platform** — `ags-consume-platform` / `ags_platform` are done.
- **Not the `ags-apps` repo.** Re-homing each retired gate into `ags-apps` is a
  **required companion** (recorded in tasks §7), not performed here.
- **No behaviour change** to the bar or any app; the deployed path
  `<install>/config/ags` is unchanged (still the live-bar symlink).
- **No live-host action.**

## Impact

- **Deleted:** `dotfiles/config/ags/**` (115 files), `scripts/ags-typecheck.py`,
  `scripts/icons-json-drift.py`, `scripts/{wifi,bluetooth,battery,speedtest,audio}-mock-parity.py`,
  `scripts/speedtest-no-new-architecture.py`, `scripts/deploy-audio-panel.sh`,
  `tsconfig.ags.json`, `src/gui-tools/icon-color-mapping-editor/tests/ags-symbol-check.mjs`
  + `mpris-core.test.mjs`, `openspec/changes/redesign-ags-audio-panel/validation/*.mjs`.
- **Edited:** `Makefile`, `.github/workflows/gates.yml`, `scripts/deploy-coverage.py`,
  `scripts/ci-gates-parity.py`, `scripts/contract-pin-check.py`,
  `src/provisioning/tests/unit/{test_compositor_skeleton_configs,test_gui_tools_role,test_compositor_configs_role}.py`,
  `AGENTS.md`, `.gitignore`, the bar docs.
- **Unchanged (deliberately):** `src/provisioning/ansible/roles/{ags_apps,ags_platform,compositor_configs,verify,filesystem,config_links,wlogout_config}/**`,
  `src/runtime/**` (consumer pointer `<install>/config/ags/colors.css`),
  `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`,
  `scripts/sync-icons-manifest.py`.

## Ownership rulings (the two the contract asks about)

### `icons.json`

- **Source of truth:** `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`
  (this repo owns it — it stays).
- **Generation:** the `compositor_configs` role writes
  `<install>/config/ags/icons.json` and `<install>/config/ags-capture/icons.json`
  fresh on every provision (`roles/compositor_configs/vars/main.yml:158-179`).
  That path lands **through the live-bar symlink into the unit tree** — it stays.
- **The committed copy** `dotfiles/config/ags/icons.json` (28951 bytes) is only a
  **build input for the in-repo bar tree** (`lib/icon-registry.ts` imports
  `../icons.json`) and the subject of `icons-json-drift`. It already exists,
  byte-identical, at `ags-apps/bar/icons.json`. When the tree leaves, this copy
  leaves with it, and **`icons-json-drift` must move to `ags-apps`** — otherwise
  the `icons.yaml ↔ manifest` projection loses its guard. The deployed-artifact
  guard stays here via `test_compositor_configs_role.py` (the strict install gate).

### AGENTS.md §2 skeleton-registration rule

The clause *"New bar source files MUST be registered in
`compositor_configs_skeleton_files` and the verify role mirror"* is **obsolete for
the bar**: the bar deploys **whole** via the `ags_apps` unit, so there are no
per-file bar sources to register (`roles/ags_apps/vars/main.yml:19-22` already
says the rule is "satisfied BY CONSTRUCTION for the bar"). §2 must be rewritten
to keep the rule for the **non-bar** skeletons (hypr/hyprpaper/rofi) and the
`gui_tools_*_app_files` lists, and to state that `deploy-coverage` asserts the
**absence** of a stale per-file bar entry.

## Reference inventory (file:line)

Grouped; only references that touch the **in-repo bar source** are listed as
actionable. `openspec/changes/*/` (historical records) and `_bmad-output/**`
(planning artifacts) are read-only and excluded.

### A. Makefile (all bar-source)
- `Makefile:388` `BAR_DIR := dotfiles/config/ags`
- `Makefile:263-334` `ags-test` / `ags-test-deps` (`AGS_TESTS` L275)
- `Makefile:448-501` `bar-typecheck`
- `Makefile:663-675` `ags-typecheck`
- `Makefile:531-550` `icons-json-drift`
- `Makefile:503-504,515-516,525-526,528-529,660-661` five `*-mock-parity`
- `Makefile:683-711` `AUDIO_VALIDATION` + seven `audio-*-test` + `audio-panel-gates`
- `Makefile:603-604` `speedtest-no-new-architecture`
- `Makefile:577-601` `deploy-coverage`
- `Makefile:419-439` `ags-platform-dev` (`BAR_DIR` link L431-432)
- `Makefile:46-55` `GATES`; `Makefile:78` `gates-ci` filter
- `Makefile:358-362` `PER_APP_SUITES` (`ags-symbol-check.mjs` L361)

### B. scripts/
- `scripts/ags-typecheck.py:104,113,180-181,215-217`
- `scripts/deploy-coverage.py:92-94,183-199,452,459`
- `scripts/icons-json-drift.py:62`
- `scripts/wifi-mock-parity.py:172-173`
- `scripts/bluetooth-mock-parity.py:316-317`
- `scripts/battery-mock-parity.py:107-108`
- `scripts/audio-mock-parity.py:194-195`
- `scripts/speedtest-mock-parity.py:83,86`
- `scripts/speedtest-no-new-architecture.py:47-48,68-69`
- `scripts/contract-pin-check.py:62` (`TS_VENDORED`)
- `scripts/sync-icons-manifest.py:46` — **stays** (deployed spine path)
- `scripts/deploy-audio-panel.sh:49,131-134`

### C. CI
- `.github/workflows/gates.yml` jobs: `wifi-mock-parity:75`, `battery:83`,
  `bluetooth:93`, `icons-json-drift:111`, `speedtest-mock-parity:173`,
  `speedtest-no-new-architecture:181`, `ags-test:221`, `audio-mock-parity:275`,
  `audio-core:292`, `audio-presentation:303`, `pipewire:314`,
  `audio-session:325`, `audio-panel-render:336`, `audio-icons:347`,
  `audio-seek:358`, `ags-typecheck:381`, `bar-typecheck:403`
- `scripts/ci-gates-parity.py:121-141` `CI_SELF_HOSTED_GATES`

### D. provisioning — mostly **stays**
- `compositor_configs/vars/main.yml:106-121` (no bar entries — stays), `:158-179` (icons generation — stays)
- `verify/vars/main.yml:436-459,480-529` (stays)
- `ags_apps/**`, `ags_platform/**`, `filesystem/vars/main.yml:60-61`,
  `wlogout_config/tasks/main.yml:40`, `bootstrap.yaml:68-69` (stays)

### E. provisioning tests — **must update**
- `test_compositor_skeleton_configs.py:37-38,132-149,206-224` (reads the repo tree)
- `test_gui_tools_role.py:810-812` (reads the repo tree)
- `test_compositor_configs_role.py:1001-1091` `TestDeployCoverageGate` (`_AGS` L1015)
- `test_verify_role.py:1740-1785` (skeleton-list assertions — already tolerant)

### F. runtime — **stays** (consumer pointer, not source)
- `consumer_path_spec.py:49`, `seeder.py:708-714`, `watch_roots.py:11`,
  `reconcile.py:83`, `models.py:81`, `ags_reloader.py:4`

### G. other apps — **stays** (non-goal)
- `src/gui-tools/*/lib/icon-registry.ts` (comments about `~/.config/ags/icons.json`)
- `hypr-pano/lib/event-bus-core.ts:3`, `capture-tool/bin/capture-tool:760-762`

### H. dotfiles — **stays**
- `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (source of truth)
- `dotfiles/config/hypr/autostart.lua:19` (`ags run`)
- `dotfiles/provisioning/filesystem.yaml:28`
- `.gitignore:22-23,59-60` — **delete** (bar-tree artifacts)

### I. docs — **update prose**
- `docs/100-ags-bar-rearchitecture.md`, `docs/101-ags-platform-architecture.md`,
  `docs/99-dotfiles-hexagonal-architecture.md`, `docs/02-config-in-spine-pattern.md`,
  `docs/HANDOFF-bar-rearchitecture.md`, `docs/ags-restart-vs-live-theme-refresh.md`,
  `docs/ags_tray_statusnotifier.md`, `docs/Animated_Icon_Loader_Findings.md`,
  `docs/Adding an Icon — ITR and Provisioning Pipeline.md`

## Classification

| Class | Items |
|---|---|
| **(a) delete/retire** | `dotfiles/config/ags/**`; the bar-dev Makefile targets + CI jobs above; `ags-typecheck.py`, `icons-json-drift.py`, 5 `*-mock-parity.py`, `speedtest-no-new-architecture.py`, `deploy-audio-panel.sh`; `tsconfig.ags.json`; `.gitignore` bar entries; the `ags-symbol-check.mjs` + `mpris-core.test.mjs` + audio `validation/*.mjs` (moved to ags-apps) |
| **(b) repoint** | `deploy-coverage.py` (assert shape, not closure); `ags-platform-dev` (drop `BAR_DIR` link); `PER_APP_SUITES` (drop `ags-symbol-check`); `ci-gates-parity.py` tables; `GATES`/`gates-ci`; provisioning tests; `AGENTS.md` §2; docs |
| **(c) stay** | `icons.yaml` + icon mappings; `compositor_configs`/`verify`/`ags_apps`/`ags_platform`/`filesystem`/`config_links`/`wlogout_config` roles; runtime consumer pointer; `sync-icons-manifest.py`; `dotfiles/config/{hypr,hyprpaper,rofi,nvim,starship,wlogout,zsh}`; `src/gui-tools/**`; historical `openspec/changes/**` |

## Gate fate (exact Makefile lines)

| Gate | Makefile | Fate in this repo | After |
|---|---|---|---|
| `bar-typecheck` | 448-501 (+`BAR_DIR` 388) | **retire** | `ags-apps` `bar-typecheck` (`Makefile:88`) |
| `ags-typecheck` | 663-675 | **retire** | `ags-apps` `bar-typecheck` covers the same tree (port `ags-typecheck.py` only if a distinct gate is wanted) |
| `ags-test` / `ags-test-deps` | 263-334 | **retire** | `ags-apps` `ags-test` (`Makefile:143`) |
| `deploy-coverage` | 577-601 | **keep, rewrite** | stays here (owns the provisioning shape) |
| `icons-json-drift` | 531-550 | **retire** | re-home in `ags-apps` (companion) |
| `wifi-mock-parity` | 503-504 | **retire** | re-home in `ags-apps` |
| `bluetooth-mock-parity` | 515-516 | **retire** | re-home in `ags-apps` |
| `battery-mock-parity` | 525-526 | **retire** | re-home in `ags-apps` |
| `speedtest-mock-parity` | 528-529 | **retire** | re-home in `ags-apps` |
| `audio-mock-parity` | 660-661 | **retire** | re-home in `ags-apps` |
| `audio-core-test` … `audio-seek-stability-test` | 685-707 | **retire** | re-home in `ags-apps` |
| `audio-panel-gates` | 709-711 | **retire** | (aggregate) |
| `speedtest-no-new-architecture` | 603-604 | **retire** | re-home, or rewrite to assert only the notifications consumer |
| `capture-hexagonal-gate` | 385-386 | **stay** | capture source stays here |
| `per-app-drift-symbol-suites` | 364-370 | **stay** (drop `ags-symbol-check`) | event-contract-drift suites stay |
| `ags-platform-dev` | 419-439 | **keep** (drop `BAR_DIR` link) | root shortcut still needed |
| `ci-gates-parity` | 105-106 | **stay** (update tables) | |
| `contract-pin-check` | 31-32 | **stay** (drop `TS_VENDORED`) | dev-only, not in `GATES` |
| `gates` / `gates-ci` | 46-78 | **update lists** | |
