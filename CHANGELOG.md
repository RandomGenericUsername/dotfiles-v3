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

_No unreleased changes._

## [0.6.15] - 2026-10-30 — engine v0.1.28; the PIN-0119 pins actually take effect

### Changed

- Installer engine pin `v0.1.27` → `v0.1.28`: the `cli_tools` role now reads
  `dotfiles/provisioning/cli-tools.yaml` as the single pin source (it previously
  hardcoded v0.4.0/v0.4.1 in `roles/cli_tools/vars/main.yml`, making PIN-0119 a
  silent no-op). The role validates the manifest, publishes `cli_tools_tags`,
  and the `assets`, `settings` and `verify` roles derive every pin, image tag,
  contract and tag-qualified path from that fact — no duplicated pin literals.
- `assets.yaml` `csg-templates` / `tpr-templates` sources now derive from
  `{{ cli_tools_tags.csg }}` / `{{ cli_tools_tags.tpr }}` instead of hardcoded
  `v0.2.2` / `v0.4.0` paths.
- This is the pin that makes tpr `v0.5.0` + runtime `v0.5.0` (PIN-0119) live:
  the CLI checkouts, installed tools, image tags, rendered settings and template
  catalogs all resolve from the composition manifest.

## [0.6.14] - 2026-10-30 — tpr v0.5.0 + runtime v0.5.0 (palette.v1 + on_backdrop)

### Changed

- `tpr` pin `v0.4.0` → `v0.5.0`: the producer gains the additive produced role
  `on_backdrop` (theme.json schema `1.1`), computed from the wallpaper's top
  `min(48, height)` band and emitted in `theme.json`, `colors.yaml`,
  `colors.gtk.css`, `colors.adw.css`, `colors.rasi` and `colors.conf`. It may
  intentionally sit on the opposite luminance pole from `on_surface` when the
  wallpaper band disagrees with the light/dark scheme — it is the ink that reads
  over the photo, and it replaces the runtime icon-contrast guard (removed in
  the follow-up seam-cleanup pin, not here).
- `dotfiles-runtime` pin `v0.4.1` → `v0.5.0`: adds the `palette.v1` vocabulary
  contract — the 50 tpr Material roles plus `on_backdrop` — validated
  fail-closed before the visible swap for every tpr palette, with
  `inspect palette` / `doctor` reporting and probe fixtures against role drift.
- Both pins move together on purpose: runtime `v0.5.0` rejects a tpr `v0.4.0`
  palette (missing `on_backdrop`), and stale cache entries are regenerated
  through the validated pipeline. The `cli_tools` role rebuilds the tpr base +
  engine images at `v0.5.0` and re-renders the projection templates from that
  checkout.
- csg remains installed and the documented rollback in this pin; its retirement
  is the follow-up seam-cleanup pin (runtime REQ-007).

## [0.6.13] - 2026-10-29 — engine v0.1.27 + runtime v0.4.1 + csg v0.2.2; tpr default

### Changed

- Installer engine pin `v0.1.26` → `v0.1.27`: the engine renders
  `<install>/config/dotfiles-runtime/producer.json` from its
  `runtime_palette_producer` input, removes the ambient environment.d/unit
  producer switch, runs tpr in container mode, and moves the rofi/gtk/btop
  palette-consumer links after `runtime-seed`. Engine `v0.1.27` consumes and
  verifies csg `v0.2.2`, tpr `v0.4.0` and runtime `v0.4.1`.
- `dotfiles-runtime` pin `v0.4.0` → `v0.4.1`: the runtime resolves the producer
  from `producer.json` (explicit `--producer` > config > `csg` default) in every
  CLI/daemon composition root, ignores stale `RUNTIME__PALETTE__*` env, and runs
  `TprAdapter` through tpr's container runtime.
- `csg` pin `v0.2.1` → `v0.2.2`: `generate` fails closed on a decoy CWD
  `templates/` directory, a missing renderer, a failed format, or a wrapper
  rc 0 whose inner run failed or produced no artifacts. The `csg-templates`
  asset source moves to the `v0.2.2` checkout to match the manifest pin.
- `bootstrap.sh` exports
  `RUNTIME_PALETTE_PRODUCER="${RUNTIME_PALETTE_PRODUCER:-tpr}"` before the
  bootstrap/verify stages, so a normal v3 bootstrap renders `producer: tpr`.
  An explicit `RUNTIME_PALETTE_PRODUCER=csg ./bootstrap.sh` is the documented
  rollback; csg stays installed and verified either way. No ambient
  double-underscore `RUNTIME__PALETTE__PRODUCER` is set — the runtime ignores it.
- `deploy-coverage` asserts the tpr bootstrap default and rejects a
  double-underscore producer variable.
- Docs/pin tables (`ARCHITECTURE.md`, `README.md`, `docs/WORKSPACE.md`,
  `docs/102-ags-app-consumption.md`) align the new engine/runtime/csg pins and
  the tpr default. `tpr` stays `v0.4.0`; weg/itr, the assets corpus `v0.6.2`,
  the program tuple and the seven app tags are unchanged.

### Notes

- No host provision, publish or tag was performed. Historical changelog
  entries above are unchanged.

## [0.6.12] - 2026-10-29 — engine v0.1.26 + runtime v0.4.0 + tpr v0.4.0

### Changed

- btop Theme Studio pin `v0.1.0` → `v0.1.2`: the mock-v8 visual shell
  (header, three-column hierarchy, section/panel chrome), followed by the
  v0.1.2 runtime fix — the real btop live preview is the default stage again,
  auto-refreshes after theme edits, and keeps its own scroller. v0.1.1 is
  superseded (its primary preview was hidden behind the Live tab).
- Bar app pin `v0.1.2` → `v0.1.3`: the conformance test and docs accept the
  committed `colors.css` runtime-pointer symlink the engine's
  `barPalettePointer` contract requires.
- Installer engine pin `v0.1.23` → `v0.1.26` (through `v0.1.24`): bootstrap runs
  `compositor-configs` before `ags-apps-units` so the app role sees the current
  assets-owned `hypr/autostart.lua`; `cli_tools`/`verify`/`assets` agree on the
  tpr and runtime checkouts. Engine `v0.1.26` consumes and verifies
  `dotfiles-runtime v0.4.0` and `theme-producer v0.4.0` in `cli_tools`, `assets`
  and `verify`.
- `dotfiles-runtime` pin `v0.3.0` → `v0.4.0`.
- New CLI pin `tpr` (`theme-producer v0.4.0`) in
  `dotfiles/provisioning/cli-tools.yaml`, before `dotfiles-runtime`, matching the
  engine's `cli_tools` order: the semantic-role palette producer and its
  template catalog.
- New `tpr-templates` asset (`kind: tpr-template`) copying the tpr projection
  catalog from
  `<install>/cli-tools/tpr/v0.4.0/src/theme_producer/defaults/templates` into
  `config/theme-producer/templates`; `filesystem.yaml` gains
  `config/theme-producer` and `config/theme-producer/templates`. The assets
  corpus pin stays `v0.6.2`.
- Docs/pin tables (`ARCHITECTURE.md`, `README.md`, `docs/WORKSPACE.md`) align the
  new engine/runtime/tpr pins. The stale "every consumer pins one contract tag"
  rule is replaced by per-consumer released contract tags: runtime and tpr pin
  `v0.4.0`, while csg/weg/itr remain on `v0.2.0` until their next release. The
  program tuple's `contracts v0.3.0` is the AGS platform schema contract, not
  this consumer pin.

### Notes

- **No activation.** `runtime_palette_producer` remains the shipped default
  `csg`; no palette-producer override was added anywhere. The tpr pin is inert.
- No host provision, publish or tag was performed.

## [0.6.11] - 2026-10-28 — engine v0.1.23 + runtime v0.3.0 final align

### Changed

- Installer engine pin `v0.1.22` → `v0.1.23`: the engine consumes
  `dotfiles-runtime v0.3.0` in `cli_tools` and `verify` (with its fixture),
  so the composition's final runtime pin and the engine mirrors now agree.
- `dotfiles-runtime` pin `v0.2.3` → `v0.3.0`: manifest discovery/identity,
  applied-appearance ledger, parallel live/serialized restart lanes and the
  clipboard namespace migration.
- Docs/pin tables (`ARCHITECTURE.md`, `README.md`, `docs/WORKSPACE.md`,
  `docs/102-ags-app-consumption.md`) align engine `v0.1.23` and runtime
  `v0.3.0`. All seven app entries stay standalone; assets `v0.6.2`,
  platform/contracts `v0.3.0` and the app tags are unchanged.
- OpenSpec 3.3 is closed for the composition (the GitHub archive/push remains
  external); 4.2 host no-op/refresh remains pending.

### Notes

- No host provision, publish or archive was performed; the engine/runtime tags
  are local-only in this change.

## [0.6.10] - 2026-10-28 — final all-standalone AGS cutover (engine v0.1.22)

### Changed

- Installer engine pin `v0.1.19` → `v0.1.22`: the engine removes the legacy
  `ags_apps` role/playbook, installs all seven AGS apps from
  `dotfiles/provisioning/apps.yaml` as immutable `<install>/apps/<installDir>/<tag>/`
  units, owns the ONE `<install>/apps/node_modules/ags-platform` shortcut, and
  adds the tpr palette-producer support.
- All seven app-list entries are now `owner: standalone` with released repos:
  `ags-bar v0.1.1` (state migration) and `ags-notifications` /
  `ags-capture-tool` / `ags-clipboard` / `ags-wallpaper-selector` / `ags-icme` /
  `ags-btop-theme-studio` at `v0.1.0`. The old `hypr-pano` entry is replaced by
  `clipboard`/`ags-clipboard`; launcher and autostart names follow the rename.
- Program tuple `dotfiles-assets` `v0.6.1` → `v0.6.2`; assets corpus pin and
  source paths move to `v0.6.2` (launch-lock autostart + clipboard rename).
- `deploy-coverage` now asserts the final all-standalone topology: every app is
  standalone, the released repo/tag inventory is exact, the composition list
  matches the engine's seven-app fixture, launcher/autostart/bin surfaces have
  one owner, the tuple/platform/assets mirrors agree, the legacy role is absent,
  and the fake cutover/rollback fixture is present.

### Blocked / not claimed

- `dotfiles-runtime` remains `v0.2.3`: engine `v0.1.22` still mirrors `v0.2.3`
  in `cli_tools` and `verify`; the separate local runtime `v0.3.0` release
  requires an engine re-pin before the composition can consume it. No host
  provision was run.
- No app tag, engine tag, assets tag or repo was published; no `ags-apps`
  archive was performed. Those are external follow-ups.

## [0.6.9] - 2026-10-27 — AGS adoption tuple active (engine v0.1.19)

### Changed

- Installer engine pin `v0.1.17` → `v0.1.19`: the engine activates the AGS
  adoption tuple (`ags-apps v0.5.0` + `ags-platform v0.3.0`), keeps the
  `dotfiles-assets v0.6.1` and `dotfiles-runtime v0.2.3` pins unchanged, and
  ships the generic `ags_apps_units` install/cutover role plus the `verify`
  mirror and fake-app one-owner fixtures. No app cuts over; all seven
  `apps.yaml` entries remain `owner: legacy`.
- `deploy-coverage` now asserts the adoption tuple is real: the pinned engine's
  `ags_apps` legacy shortcut, `ags_platform` role and both verify mirrors must
  resolve the program tuple's `ags-platform` tag; `ags-apps`/verify versions
  must agree; the verify mirror must read the same `apps.yaml` /
  `program-tuple.yaml` and assert the same standalone surfaces; and the engine
  must carry the legacy/mixed/all-standalone and quiesce → install/start →
  verify → rollback fixtures. OpenSpec tasks 2.2 and 2.3 are covered by this
  gate against the pinned engine. Final closeout (3.3) and runtime reconcile
  behavior (4.2) remain open.
- Docs `ARCHITECTURE.md`, `README.md`, `docs/WORKSPACE.md` and
  `docs/102-ags-app-consumption.md` now name engine `v0.1.19`, the active
  adoption tuple and the engine-owned verify/cutover fixtures.

### Notes

- `installer.pin` and the engine tag are local-only in this change; no remote
  tag or push. The program tuple stays `contracts v0.3.0`,
  `ags-platform v0.3.0`, `dotfiles-assets v0.6.1`.
- No AGS app, `hypr-pano` rename, assets corpus, runtime or CLI source changes.

## [0.6.8] - 2026-10-26 — csg v0.2.1 + runtime v0.2.3 (engine v0.1.17)

### Changed

- Installer engine pin `v0.1.16` → `v0.1.17`: the engine consumes csg
  `v0.2.1` and runtime `v0.2.3` in its `cli_tools`, `assets_csg_pinned_tag`,
  `settings_csg_image_tag` and `verify` mirrors (plus both test fixtures), so
  a provision installs and verifies the stale-container sweep and the
  optional-root watch health. The assets corpus stays `v0.6.1`.
- `csg` pin `v0.2.0` → `v0.2.1`: container-mode wrappers are labelled
  csg-owned and a best-effort startup sweep removes stale csg wrappers —
  previous-boot wrappers immediately, same-boot wrappers only after their own
  timeout plus a 60 s grace; young/concurrent, unlabelled/foreign and
  age-less wrappers are untouched, and sweep failures never fail the
  requested palette run (csg BUG-001).
- `dotfiles-runtime` pin `v0.2.2` → `v0.2.3`: an absent optional intent root
  (`$XDG_CONFIG_HOME/dotfiles/desired.json`) is informational
  (`optional_absent`) and only required roots degrade watch health
  (runtime BUG-005). The health record gains the additive `optional_absent`
  field under its unchanged `version: 1`, `inspect daemon`/`doctor` report it
  without failing, and `WatchCoordinator` retries once per burst so a parent
  created later is watched without a daemon restart.

### Fixed

- `dotfiles/provisioning/assets.yaml`'s `csg-templates` source now names
  `v0.2.1`, matching the csg pin; `make deploy-coverage` now rejects a source
  tag that differs from `cli-tools.yaml`. The stale `v0.2.0` path was inert at
  deploy time (the engine role uses `assets_csg_pinned_tag`) but was a latent
  second pin.

### Notes

- No assets corpus, AGS, wlogout or pixie changes; the pins arrive only
  through the engine and the CLI manifest. Host deploy and live checks are
  user-run after this pin.

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
