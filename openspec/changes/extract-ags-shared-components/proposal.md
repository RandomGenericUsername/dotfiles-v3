## Why

The settings panel shipped with its network UI and slider logic living inside
`settings-panel/` and importing panel-local primitives. That made the Wi-Fi
list, the Bluetooth device list, and the volume/brightness sliders impossible to
reuse outside the panel — but the owner needs exactly that: the Wi-Fi network
picker must be reachable from the **bar's Wi-Fi icon**, not only
from the settings panel.

The current dependency direction is also wrong: domain logic
(`settings-panel/services/*` = NetworkManager/BlueZ D-Bus) is owned by the
panel, and reusable content mixes with panel chrome (tiles, `NavHeader`).
Nothing about Wi-Fi state is panel-specific.

## What Changes

### Panel-agnostic services
Move `dotfiles/config/ags/settings-panel/services/` →
`dotfiles/config/ags/services/` (nm-client, wifi-service, bluetooth-service).
Scan ownership becomes refcounted (`startScanning`/`stopScanning` may be called
by more than one host at once — the panel view and the popup).

### Reusable components
New `dotfiles/config/ags/components/`, with a strict one-way dependency rule:

```
settings-panel  →  components  →  services
```

- `components/wifi/` — `WifiContent.tsx` (embeddable message + network list +
  rows + password prompt, driven by a `visible` accessor), `WifiPopup.tsx` (a
  standalone overlay window anchored under the Wi-Fi bar icon), and `state.ts`
  (popup visibility + icon anchor x + open/close/toggle). The settings panel's
  `WifiView` becomes `NavHeader` + `WifiContent`; the tile stays panel-owned.
- `components/bluetooth/` — `BluetoothContent.tsx` (device list + discovery
  lifecycle), used by the panel now and wireable to an icon later.
- `components/sliders/` — `LevelSlider` (moved out of panel primitives),
  `VolumeSlider` (AstalWp + level-aware glyph), `BrightnessSlider`
  (brightnessctl; polls while its own `visible` is true).

Components must not import from `settings-panel/`.

### Wi-Fi popup from the bar icon
The bar's network widget opens the Wi-Fi popup on **left-click** (replacing
the nm-applet right-click menu) and keeps **right-click** = `wifitui`. The popup is
a compact header (title + power toggle) plus the shared `WifiContent`, anchored
beneath the Wi-Fi icon, dismissed by `Esc`/click-outside, and switches to
`keymode ON_DEMAND` while the password prompt is shown. Opening the popup
closes the settings panel and vice versa (mutual exclusion).

## Capabilities

### New Capabilities
- `ags-shared-components` — the reusable Wi-Fi content + popup, Bluetooth
  content, and volume/brightness slider components, including the one-way
  dependency rule, the refcounted scan contract, and the popup behavior
  (anchor, dismissal, keyboard for password entry, mutual exclusion with the
  settings panel).

### Modified Capabilities
- `ags-settings-panel` — the Wi-Fi/Bluetooth/slider sections are now
  compositions over `components/` + `services/`; the panel keeps only chrome
  (tiles, cards, `NavHeader`, window/state). No behavior change to the panel's
  own UX.
- `settings-panel-provisioning` — the deploy manifest and verify gate follow the
  new file layout (`services/`, `components/{wifi,bluetooth,sliders}`), remove
  the old `ags/settings-panel/services` entries, and clean up the previously
  deployed directory.

## Impact

- **Moved**: 3 service files (`settings-panel/services/` → `services/`).
- **New**: `components/wifi/{state,WifiContent,WifiPopup}.tsx`, `components/bluetooth/BluetoothContent.tsx`, `components/sliders/{LevelSlider,VolumeSlider,BrightnessSlider}.tsx`.
- **Slimmed**: `settings-panel/{controls,views,primitives}.tsx` (composition only).
- **Wired**: `bar/widgets/network.tsx` (left-click → popup, icon anchor x),
  `app.tsx` (popup window + shared dismissal).
- **Provisioning**: config dirs, per-file skeleton entries, verify gate, and
  tests updated for the new layout; legacy `settings-panel/services` cleanup.
- **Non-goals**: wiring the Bluetooth component to an icon (owner will do
  later); changing the panel's visual design; changing any service behavior
  except the refcounted scan lifecycle.
