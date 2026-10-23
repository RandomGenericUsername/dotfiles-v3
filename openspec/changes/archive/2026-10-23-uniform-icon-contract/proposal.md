# uniform-icon-contract

## Why

Doc 101 §13 step 3 / spine **AD-7** fixes one icon contract for every app: **code
emits a state key only**, and data maps `key → variant → art` through the
provider's `bar_mappings.states`. Two call sites still bypass it and resolve a
**direct variant**, so their glyph vocabulary lives in the widget instead of the
manifest:

- **Audio** (`bar/widgets/audio.tsx:36-38,101,134`) resolves the `volume` and
  `microphone` variants itself, via `projectBarIndicators` /
  `levelVariant` (`audio/presentation/levels.ts:16`) and `registry.resolve`.
- **Battery power-mode** (`components/battery/BatteryContent.tsx:71-74`) resolves
  `registry.resolve("power-mode", mode.glyph)` from `mode.glyph` — a variant
  name, not a state key. `presentation.ts:88,128` (`glyphForTier`) supplies it.
- **Battery bar glyph** (`bar/widgets/battery.tsx:42-48`) hand-navigates
  `bar_mappings.states` itself instead of going through the kit's chain.

`volume`, `microphone`, and `power-mode` therefore have **no `bar_mappings`** in
the manifest, so a state key cannot resolve to them at all.

Separately, spine **AD-21** fixes a second defect: the manifest has more than one
shape and no version. `lib/icon-registry.ts:24` casts the committed
`dotfiles/config/ags/icons.json` with no `schemaVersion`, provisioning generates
the same file from `icons.yaml`
(`roles/compositor_configs/tasks/main.yml:88`), and the drift gate compares the two
as `to_nice_json(icons.yaml)` with no version
(`scripts/icons-json-drift.py:101-102`). AD-16 requires each artifact to carry its
own `schemaVersion`; AD-21 requires exactly one manifest, one owner, one shape,
where the bar's build-time import is a bundling detail of the same artifact.

Evidence: `grep -n "glyph(\"volume\"\|glyph(\"microphone\"\|registry.resolve"
dotfiles/config/ags/bar/widgets/audio.tsx dotfiles/config/ags/components/battery/BatteryContent.tsx
dotfiles/config/ags/bar/widgets/battery.tsx`;
`python3 -c "import json; d=json.load(open('dotfiles/config/ags/icons.json')); print('schemaVersion' in d, [g for g in ('volume','microphone','power-mode') if not d[g].get('bar_mappings')])"`.

Verify: `grep -n "iconByStateKey\|registry.resolve\|getBarMappings"
dotfiles/config/ags/bar/widgets/audio.tsx dotfiles/config/ags/components/battery/BatteryContent.tsx
dotfiles/config/ags/bar/widgets/battery.tsx`.

## What Changes

### Migrate the leaks to `iconByStateKey` (AD-7)

- `audio/presentation/bar-indicators.ts` gains pure `volumeStateKey(muted,
  level)` and `microphoneStateKey(variant)`; `bar/widgets/audio.tsx` uses
  `iconByStateKey("volume"|"microphone", …)` + `resolveIcon`, dropping the
  hand-rolled `glyph()`.
- `components/battery/presentation.ts` gains pure `powerModeStateKey(mode)`;
  `components/battery/BatteryContent.tsx` resolves the mode glyph through
  `iconByStateKey("power-mode", …)` + `resolveIcon`.
- `bar/widgets/battery.tsx` resolves its glyph through
  `iconByStateKey("battery", …)` + `resolveIcon` instead of hand-navigating
  `bar_mappings.states`.
- `volume`, `microphone`, and `power-mode` gain `bar_mappings.states` in the
  manifest source (`icons.yaml`): `volume-medium → medium`,
  `microphone-mic-off → mic-off`, `power-mode-powersave → powersave`, … A key
  with no entry resolves to **blank**, never a crash.

### One manifest, one owner, one shape (AD-21)

- The generated artifact `dotfiles/config/ags/icons.json` carries a top-level
  `schemaVersion` (AD-16). The authored source `icons.yaml` stays a **pure group
  map** (so the ITR renderer, which iterates every top-level key as a group, is
  untouched); the version is stamped at generation.
- Provisioning (`compositor_configs`) and the `icons-json-drift` gate stamp the
  **same** version from one owner: the gate reads the role's own
  `compositor_configs_icon_manifest_schema_version`, exactly as it already calls
  the role's own `to_nice_json` filter, so the two cannot drift.
- `lib/icon-registry.ts` separates the reserved `schemaVersion` key from the
  group map, so the group lookup (`barMappings`/`resolve`) reads only groups.
  The bar's build-time `import icons.json` remains the same artifact.

### Tests (pure, no GTK)

- `tests/ts/icon-state-keys.test.ts` pins the state-key functions, resolves each
  key through the **real** manifest table, and proves an unknown key blanks
  (`resolveIconSource(...) === null`, no throw).

## Out of scope

- **No app-local `icon-registry.ts` migration.** The four copies under
  `src/gui-tools/**` (capture-tool, hypr-pano, notifications,
  wallpaper-selector) are the `ags-apps` epic's job and are not touched. They
  look up named groups, so the reserved `schemaVersion` key does not affect them.
- **No `validateIcons` / capability declaration validator.** AD-15's
  declared-`icons` validation is the provisioning/validator step, not this one.
- **No widget-shape migration.** The hand-rolled widgets are not rewritten onto
  `RichWidgetSpec`/`Shell` (REQ-008); only their icon resolution changes.
- **No network/bluetooth widget migration.** `network` already has its state-key
  function (`lib/network-icon.ts`) and descriptor; `bluetooth` is not one of the
  two leaks AD-7 names.
- **No platform extraction.** The registry stays a module value behind the
  `kit/icon.ts` facade (AD-2 lands with the platform extraction).
- **No new `bar.json` / runtime producer relocation.** AD-16's producer move is
  the provisioning step; this change keeps provisioning as producer and adds the
  version.

## Impact

- Edited: `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`,
  `dotfiles/config/ags/icons.json` (regenerated),
  `dotfiles/config/ags/lib/icon-registry.ts`,
  `dotfiles/config/ags/kit/widget.tsx` (shared `applyIconSource`),
  `dotfiles/config/ags/audio/presentation/bar-indicators.ts`,
  `dotfiles/config/ags/components/battery/presentation.ts`,
  `dotfiles/config/ags/bar/widgets/audio.tsx`,
  `dotfiles/config/ags/components/battery/BatteryContent.tsx`,
  `dotfiles/config/ags/bar/widgets/battery.tsx`,
  `scripts/icons-json-drift.py`,
  `src/provisioning/ansible/roles/compositor_configs/{tasks/main.yml,vars/main.yml}`,
  `dotfiles/config/ags/tests/tsconfig.tests.json`.
- New: `dotfiles/config/ags/tests/ts/icon-state-keys.test.ts`.
- No behavior change on a provisioned host: every migrated call site resolves the
  same rendered SVG path it does today.
