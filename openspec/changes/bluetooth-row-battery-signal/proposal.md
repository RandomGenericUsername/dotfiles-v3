## Why

The settings-panel Bluetooth row overflows its 312px container: device labels
carry no `ellipsize` / `maxWidthChars`, and the trailing `Connected` badge plus
`Disconnect` / `Unpair` buttons exceed the available width. `SettingsPanel`
sets `hscrollbarPolicy=NEVER`, so the excess is clipped rather than scrolled —
the row's right edge is unreachable on long device names.

Separately, the row shows no peripheral state at all: battery level and signal
strength exist on the service model (`battery`, `rssi` from BlueZ) but are
never rendered, so the user cannot see whether a headset is dying or dropping.

## What Changes

- Restructure `BluetoothRow` to the owner-approved layout (V1): line 1 =
  ellipsized device name (full name via tooltip) + `Connected` badge; line 2 =
  `justify-content: space-between`, left = stacked meta (`[battery glyph 14px
  + "N%"]` over `[signal glyph 14px + "−N dBm"]`), right = action buttons
  `valign=CENTER`. Name truncation follows the shipped `.audio-routing`
  precedent (`maxWidthChars` + `ellipsize`; GTK ignores CSS `max-width`).
- Add 4 signal icon templates (`low`, `medium`, `good`, `high`) converted from
  the owner's Downloads artwork, plus a `settings-panel` group exposing them as
  `settings-panel-signal-{low,medium,good,high}` outputs.
- Add 5 `system-battery-{0,25,50,75,100}` variants reusing the existing
  `status-bar/battery` templates, each pinned variant-level
  `COLOR_FOREGROUND: foreground` so the contrast guard never retargets them
  (bare `battery-*` IS guard-subject — one render serves bar + panel).
- Regenerate `icons.json` (never hand-edit); byte-verify the diff is
  additions-only; extend `verify_icons_samples`.
- Render **live** values only: battery % from `battery` (hidden when unknown/
  level 0), dBm from `rssi` with the fixed mapping
  `≥−60→high, ≥−70→good, ≥−80→medium, else low` (hidden when `rssi` absent).
  No hardcoded percentages or signal strings anywhere.
- Copy the approved mock into the change as the no-drift contract; tasks carry
  anti-drift harnesses (FORBIDDEN list, `icons.json` addition-only diff,
  overlay-exemption unit test, light-wallpaper proof, owner visual sign-off).
- Partial deploy path: `assets.yaml` → `compositor-configs.yaml` playbooks +
  `dotfiles-runtime icons regenerate` (icons-only re-derive from live palette,
  restarts AGS so the new row code re-bundles), gated by
  `dotfiles-provision verify`. Full `make bootstrap` remains the final accept
  gate.

## Capabilities

### New Capabilities

- `bluetooth-row`: the normative Bluetooth device-row contract — layout,
  truncation, badge, stacked battery/signal meta, actions, visibility gates,
  and live-data (no-hardcode) rules, pinned to the approved mockup.

### Modified Capabilities

<!-- none: no existing spec-level requirement changes. The icon-pipeline
     additions follow the already-specified `system-*` overlay-exemption
     pattern from add-system-icon-variants. -->

## Impact

- `dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx` —
  `BluetoothRow` restructure (~lines 107-151) + `batteryVariant` /
  `signalVariant` helpers.
- `dotfiles/config/ags/services/bluetooth-service.ts` — read-only source of
  `battery` / `rssi` / `connected` (no schema change expected).
- `dotfiles/config/ags/settings-panel/style.css` — `.settings-meta-icon` and
  truncation rules (precedent: `.audio-routing` ~lines 853-860).
- `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` — new
  `settings-panel` variants + `battery.system-battery-*` variants.
- `dotfiles/assets/icon-templates/settings-panel/signal/{low,medium,good,high}/default/icon.svg`
  — new templates from `~/Downloads/signal {low,medium,good,high}.svg`.
- `dotfiles/config/ags/icons.json` — regenerated only.
- Contrast guard untouched (`src/runtime` `BAR_GROUPS` / derive logic
  unchanged); the fix is variant-level pins, same mechanism as shipped
  `system-*`.
- Runtime: `dotfiles-runtime icons regenerate` becomes the day-to-day
  re-render path; no runtime / cache / registry API change.
