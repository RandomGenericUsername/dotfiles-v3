# Changelog

Notable changes to `dotfiles-v3`, the **composition repo**: the provisioning
manifests, the pinned installer-engine entry point (`bootstrap.sh`), the pins and
the gates. The runtime is its own pinned repo. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This repo is not
released (it has no tags); the 0.x sections group the assets-split slices by the
commits that landed them, and the authoritative record is the planning set — not
this summary:

- spine: `_bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21/ARCHITECTURE-SPINE.md`
- slices: `…/SLICES.md`
- residual ledger: `…/RESIDUALS.md` (open items R-01…R-17)
- closure record: `openspec/changes/archive/2026-10-22-assets-repo-split/POST-MIGRATION.md`

## [Unreleased]

## [0.6.7] - 2026-10-26 — logout `uwsm stop` + assets v0.6.1 / runtime v0.2.2

### Changed

- Installer engine pin `v0.1.15` → `v0.1.16`: the engine consumes assets
  `v0.6.1` and runtime `v0.2.2` in every `*_assets_pinned_tag` mirror and in
  `verify` (`verify_runtime_version` / `verify_runtime_tool_version`), so a
  provision installs and verifies the fixed logout action and runtime.
- Assets corpus pin `v0.6.0` → `v0.6.1`: the wlogout Logout tile runs
  `uwsm stop` instead of `loginctl terminate-user $USER`, so logout stops the
  compositor unit and lets `sddm-helper` exit normally; SDDM returns to the
  Pixie greeter instead of leaving a black VT with a cursor (provision
  BUG-005). The corpus's `validate-configs` gate now pins the action. No other
  tile, key, icon or pixie change ships in this pin.
- `dotfiles-runtime` pin `v0.2.0` → `v0.2.2`: the icon-contrast prefs reader
  accepts its own canonical document at any entry count, including four or
  more prefs (runtime BUG-003), and BUG-004's `btop-theme-studio` skip is kept
  so a wallpaper change does not discard unsaved studio edits. Includes
  v0.2.1's BUG-002 csg timeout cleanup (330 s timeout, SIGINT before SIGKILL,
  complete-artifact verification, 512 MiB container limit kept).

### Notes

- No AGS app code and no wlogout/pixie source in this repo changes; the
  logout fix arrives only through the pinned assets tag. Host deploy and the
  logout → 5-login acceptance are user-run.

## [0.6.6] - 2026-10-26 — runtime palette order + engine v0.1.15

### Changed

- Installer engine pin `v0.1.12` → `v0.1.15`: the engine mirrors
  `dotfiles-runtime v0.2.0` in `cli_tools` and in `verify`
  (`verify_runtime_version` / `verify_runtime_tool_version`), so provisioning
  installs and verifies the mandatory-palette runtime. The engine also carries
  the earlier releases of this train: the weston SDDM greeter (v0.1.13) and the
  `ags-apps v0.4.3` selector click-collapse (v0.1.14).
- Assets corpus pin `v0.5.0` → `v0.6.0` to match the engine's mirrored
  `*_assets_pinned_tag` defaults, including the SDDM `[Wayland]` template.
- `dotfiles-runtime` pin `v0.1.0` → `v0.2.0`: `wallpaper set` prepares the
  palette (hard) before the visible swap, and a palette failure exits non-zero
  without swapping the wallpaper, writing `current.json`, or changing consumer
  links. The published stage order is
  `applying/generating_palette` → `applying/palette_generated` →
  `applying/setting_wallpaper` → `visible/preparing_appearance_assets` →
  `visible/appearance_assets_ready` → `visible/reconciling_consumers` →
  `done/finished`; a palette failure publishes only `generating_palette` then
  `error/generating_palette`, never `visible`. Reconcile refuses a legacy
  null-palette state instead of unlinking consumer pointers.

### Docs

- `docs/ags-restart-vs-live-theme-refresh.md` records the runtime v0.2.0 stage
  order; its restart-vs-live-refresh rules are unchanged.

## [0.6.5] - 2026-10-25 — color thumbnails consume

### Fixed

- Installer engine pin `v0.1.11` → `v0.1.12`: the engine consumes `ags-apps v0.4.2`
  (ags-apps BUG-001). The wallpaper-selector rendered every PNG card in black &
  white — gdk-pixbuf's JPEG writer desaturates 4-channel (RGBA) pixbufs, and the
  selector's disk-cache keys (path+mtime+size) never invalidate for files that do
  not move. The fix flattens RGBA onto an opaque 3-channel pixbuf over black
  before the JPEG save and bumps the thumb-cache entry format to v2, so every
  poisoned entry regenerates on the first open of the fixed build; the engine's
  `verify` mirror moves with the pin.

## [0.6.4] - 2026-10-24 — power-options daemon reload

### Fixed

- Installer engine pin `v0.1.10` → `v0.1.11`: the `power_options` role now restarts
  `power-options.service` after rewriting the profile TOMLs, then refreshes. Without the restart the
  daemon kept its old in-memory Powersave profile and still soft-blocked Bluetooth; the
  `policy_version = 2` marker makes an upgrade restart an already-false set once.

## [0.6.3] - 2026-10-24 — power-options Bluetooth policy

### Added

- Installer engine pin `v0.1.9` → `v0.1.10`: the new `power_options` role rewrites
  `block_bt = false` in the Powersave/Powersave++/Balanced profiles, refreshes the active profile,
  and writes `/etc/power-options/.dotfiles-bt-ok`. `verify` reads the three profiles and fails if
  any still blocks Bluetooth. Switching power profiles no longer disables the radio.

## [0.6.2] - 2026-10-24 — engine v0.1.9 / host verify

### Fixed

- Installer engine pin `v0.1.8` → `v0.1.9`: the wheel now ships
  `inventory/group_vars` (BUG-002), so the installed engine's `verify` resolves
  `container_runtime_engine` and `shell` instead of failing on undefined vars.
- Host proof: `make provision ARGS="verify --expected-engine-tag v0.1.9"` →
  exit 0 on 2026-10-24; engine 0.1.9, runtime pinned v0.1.0, daemon and clipboard
  units active, runtime state seeded. A true fresh-VM proof is still pending
  because `incus` is absent on this host.

## [0.6.1] - 2026-10-23 — runtime-seed fix

### Fixed

- Installer engine pin `v0.1.7` → `v0.1.8`: the `runtime-seed` playbook no longer invokes the
  deleted `composition_root/src/runtime`; it runs the installed pinned `dotfiles-runtime` from
  the uv tool bin dir (BUG-001 in `dotfiles-provision`). Bootstrap/apply now reaches the seed
  step after the runtime extraction.

## [0.6.0] - 2026-10-23 — runtime repo consumption (REQ-002)

### Changed

- `dotfiles-runtime` is consumed as `{name, repo, tag}` at `v0.1.0`; the
  installer engine pin is `v0.1.7` (its role/verify mirrors carry the runtime
  entry). The CLI manifest now has **zero** local `source:` entries.
- `deploy-coverage` asserts the runtime's pinned shape, requires `src/` to be
  absent, and no longer validates a composition-owned `[tool.uv.sources]` or a
  vendored `contracts/` copy.
- The runtime-only gates (`contracts-check`, `runtime-architecture`,
  `contract-pin-check`) and their CI jobs moved to the runtime repo with the
  code. The composition keeps `ansible-embedded-template-lint`,
  `deploy-coverage`, `ci-gates-parity` and `per-app-drift-symbol-suites`.
- `AGENTS.md`, `README.md`, `ARCHITECTURE.md` and `docs/WORKSPACE.md` state the
  new boundary: the composition authors manifests and gates only.

### Removed

- `src/runtime/`, `contracts/` and `scripts/contract-pin-check.py` — the
  runtime and its conformance material live in `dotfiles-runtime`.

## [0.5.0] - 2026-10-22 — composition closeout (S7)

### Added

- The **composition pin set** as one documented table (`ARCHITECTURE.md` §4.1)
  and one executable assertion: `deploy-coverage`'s `assert_pin_set` requires
  every pin to be a semver tag and every mirror to agree — `installer.pin` ↔
  `bootstrap.sh`, the assets tag ↔ its role/verify mirrors, every CLI tag ↔
  manifest/role/verify, and every runtime `[tool.uv.sources]` a `git` + `tag`
  source (never `path`, `editable`, `rev` or `branch`).
- `assert_composition_only` — the terminal composition catch-all: `src/` holds
  `runtime/` only, `dotfiles/` holds `config/` + `provisioning/` (`config/` is
  exactly the mutable `btop/active-theme`), and `src/provisioning/`,
  `dotfiles/assets/`, `dotfiles/applications/` and `dotfiles/scripts/` are
  asserted absent.
- MIT `LICENSE` and this `CHANGELOG.md` (the metadata the closeout exposed).

### Changed

- `ARCHITECTURE.md`, `AGENTS.md` and `docs/02-config-in-spine-pattern.md` now
  describe the installer engine as the pinned external `dotfiles-provision`
  repo everywhere; no section claims an in-repo provisioning tree.
- `bootstrap.sh`'s semver error example is `vX.Y.Z`, not the current tag, so the
  shell really reads `dotfiles/provisioning/installer.pin` instead of repeating
  it.

## [0.4.0] - 2026-10-22 — installer engine extracted (S6)

### Changed

- The provisioning engine (the Python orchestrator **and** the Ansible tree) is
  the pinned external `dotfiles-provision` repo at `v0.1.0`
  (`dotfiles/provisioning/installer.pin`). `bootstrap.sh` clones the tag into
  `.dev/dotfiles-provision-<tag>/` and installs it editable, because the wheel
  packages `src/provisioning` only; `deploy-coverage` and
  `ansible-embedded-template-lint` read the same cached checkout.
- This repo keeps only the composition seam: declarative manifests, the runtime,
  the gates and `bootstrap.sh` (`dotfiles-provision --manifests-dir …`).

### Removed

- `src/provisioning/` — engine Python package, roles, playbooks, inventory and
  its tests. `deploy-coverage` asserts the root stays absent.

## [0.3.0] - 2026-10-22 — desktop class + schema window (S4–S5)

### Added

- `desktop/` class at assets `v0.5.0`: six `.desktop` entries,
  `toggle-touchpad`, and `desktop.yaml` (`requires`/`optional`). The
  `compositor_configs` role resolves the contract **before** the copy; `verify`
  re-asserts the deployed set and resolves every `Exec` binary.
- `assets_schema_support` on fetch and verify (AD-12): every schema-bearing
  class must be inside the consumer's supported `schema_major` window before the
  first copy, and `verify` rejects a corpus outside it.

### Removed

- `dotfiles/applications/` and `dotfiles/scripts/` (retired with an absence
  guard).

## [0.2.0] - 2026-10-22 — configs + templates (S2–S3)

### Added

- The pinned corpus's `configs/` (assets `v0.3.0`) and `templates/`
  (assets `v0.4.0`) classes. The 15 non-bar skeletons, the copied
  `nvim`/`starship`/wlogout `layout` files, and every Jinja source (zsh, kitty,
  btop, wlogout, display-manager) render from `<install>/assets/<tag>/…`.
- `<role>_assets_pinned_tag` + `<role>_assets_templates_dir` mirrors and the
  required-var parity test (AD-8.4).

### Removed

- `dotfiles/config/{hypr,hyprpaper,nvim,rofi,starship,zsh,wlogout}/` as authored
  sources (the last mutable file, `btop/active-theme`, stays by design).

## [0.1.0] - 2026-10-21 — corpus split begins (S0–S1)

### Added

- `dotfiles-assets`, a data-only pinned repo (no package, no console script),
  born at `v0.1.0` and populated to `v0.2.0`.
- The `icons/` and `content/` classes: icon templates, one group map, the icon
  vocabulary, and the wallpaper archive. `dotfiles/provisioning/assets.yaml`
  declares repo + tag + class map; the assets role and verify mirror it.

### Removed

- `dotfiles/assets/` and the in-repo icon mapping corpus, replaced by
  `<install>/assets/<tag>/` from the pin (`deploy-coverage` asserts absence).
