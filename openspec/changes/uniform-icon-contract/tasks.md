# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-icon-contract/spec.md` with ADDED Requirements + Scenarios citing
  AD-7/AD-21 and doc 101 §7, §13.3.
  Verify: `openspec validate uniform-icon-contract --type change` → valid.
  - `openspec validate uniform-icon-contract --type change` →
    `Change 'uniform-icon-contract' is valid`.

## 2. Migrate the audio leak to `iconByStateKey` (AD-7)

- [ ] 2.1 Add pure state-key functions `volumeStateKey(muted, level)` and
  `microphoneStateKey(variant)` to `audio/presentation/bar-indicators.ts`, built
  on the existing `levelVariant` vocabulary.
  Verify: `grep -n "export function volumeStateKey\|export function microphoneStateKey" dotfiles/config/ags/audio/presentation/bar-indicators.ts`.
- [ ] 2.2 Migrate `bar/widgets/audio.tsx`: replace the hand-rolled `glyph()` +
  `registry.resolve` with `iconByStateKey("volume"|"microphone", …)` +
  `resolveIcon`, rendering the tagged `IconSource`.
  Verify: `grep -n "iconByStateKey\|registry.resolve" dotfiles/config/ags/bar/widgets/audio.tsx`
  → only `iconByStateKey` (no `registry.resolve`).

## 3. Migrate the battery leaks to `iconByStateKey` (AD-7)

- [ ] 3.1 Add pure `powerModeStateKey(mode)` to
  `components/battery/presentation.ts`.
  Verify: `grep -n "export function powerModeStateKey" dotfiles/config/ags/components/battery/presentation.ts`.
- [ ] 3.2 Migrate `components/battery/BatteryContent.tsx`: the power-mode mode
  glyph and the nav-header battery glyph resolve through `iconByStateKey` +
  `resolveIcon`, not `registry.resolve` / `getBarMappings`.
  Verify: `grep -n "iconByStateKey\|registry.resolve\|getBarMappings" dotfiles/config/ags/components/battery/BatteryContent.tsx`
  → only `iconByStateKey`.
- [ ] 3.3 Migrate `bar/widgets/battery.tsx`: the glyph resolves through
  `iconByStateKey("battery", …)` + `resolveIcon`, not a hand-navigated
  `bar_mappings.states` lookup.
  Verify: `grep -n "iconByStateKey\|getBarMappings" dotfiles/config/ags/bar/widgets/battery.tsx`
  → only `iconByStateKey`.

## 4. Manifest source carries the state→variant tables (AD-7)

- [ ] 4.1 Add `bar_mappings.states` for `volume`, `microphone`, and
  `power-mode` to `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`,
  mapping each state key to its existing variant.
  Verify: `python3 -c "import json;d=json.load(open('dotfiles/config/ags/icons.json'));print({g:d[g]['bar_mappings']['states'] for g in ('volume','microphone','power-mode')})"`.
- [ ] 4.2 A missing key blanks, never crashes: `resolveIconSource` returns
  `null` for a key with no table entry and no fallback.
  Verify: the `icon-state-keys` suite asserts `resolveIconSource(...) === null`
  for an unknown key.

## 5. One manifest, one owner, one shape (AD-21, AD-16)

- [ ] 5.1 Add `compositor_configs_icon_manifest_schema_version` to the role vars
  and stamp it into the generated `icons.json` (bar and capture) in
  `roles/compositor_configs/tasks/main.yml`.
  Verify: `grep -n "schema_version\|schemaVersion\|combine" src/provisioning/ansible/roles/compositor_configs/tasks/main.yml src/provisioning/ansible/roles/compositor_configs/vars/main.yml`.
- [ ] 5.2 Reconcile `scripts/icons-json-drift.py`: read the version from the
  role's own var and inject it, so the gate compares against the role's output.
  Verify: `make icons-json-drift` → exit 0.
- [ ] 5.3 Regenerate `dotfiles/config/ags/icons.json` (now carrying
  `schemaVersion`).
  Verify: `python3 -c "import json;print(json.load(open('dotfiles/config/ags/icons.json'))['schemaVersion'])"`
  → `1`.
- [ ] 5.4 Separate the reserved `schemaVersion` key from the group map in
  `lib/icon-registry.ts`, so `barMappings`/`resolve` read only groups.
  Verify: `grep -n "schemaVersion" dotfiles/config/ags/lib/icon-registry.ts`.

## 6. Tests (pure, no GTK)

- [ ] 6.1 Add `tests/ts/icon-state-keys.test.ts`: pin the state-key functions,
  resolve each key through the real manifest table, and prove an unknown key
  blanks.
  Verify: `make ags-test` → the `icon-state-keys` suite passes.
- [ ] 6.2 Register the pure modules in `tests/tsconfig.tests.json`'s explicit
  purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.

## 7. Verify

- [ ] 7.1 All gates green.
  Verify: `make ags-test` → `fail 0`; `make ags-typecheck` → PASS;
  `make bar-typecheck` → OK; `make gates-ci` → exit 0; `make icons-json-drift`
  → exit 0.
- [ ] 7.2 The change validates and the tree is clean.
  Verify: `openspec validate uniform-icon-contract --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
