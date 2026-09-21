# Tasks: extract-ags-shared-components

Workstreams map to orchestrated agents (W1–W6). Respect the dependency order;
`W1` and `W4` can run first, `W2`/`W3` after `W1`, `W5` after `W2`, `W6` in
parallel once the final file list is known.

## 1. Services move + refcounted scan (W1)

- [x] 1.1 Move `dotfiles/config/ags/settings-panel/services/{nm-client,wifi-service,bluetooth-service}.ts`
  to `dotfiles/config/ags/services/` (git-tracked move; no content change beyond
  imports).
- [x] 1.2 Update every import of the moved files: `settings-panel/controls/*`,
  `settings-panel/views/*`, `settings-panel/bluetooth-agent.ts`.
- [x] 1.3 Make scan ownership refcounted in `services/wifi-service.ts`
  (`scanUsers`; start/stop balanced per host).
- [x] 1.4 No other service behavior change.

## 2. Shared primitives (W1, same agent — trivial move)

- [x] 2.1 Extract `IconToggle` and `LevelSlider` into
  `components/primitives/{IconToggle,LevelSlider}.tsx`.
- [x] 2.2 `settings-panel/primitives.tsx` keeps `PanelCard`/`CapabilityTile`/
  `NavHeader` and imports `IconToggle` from `components/primitives`.
- [x] 2.3 Grep: `components/**` contains no import from `settings-panel/**`.

## 3. Slider components (W4 — parallel after W1)

- [x] 3.1 `components/sliders/VolumeSlider.tsx` (AstalWp + level glyph + mute).
- [x] 3.2 `components/sliders/BrightnessSlider.tsx` with a `visible` prop
  driving its poll interval.
- [x] 3.3 Rewrite `settings-panel/controls/volume.tsx` → `PanelCard` +
  `VolumeSlider`; `brightness.tsx` → `PanelCard` + `BrightnessSlider visible={panelVisible}`.

## 4. Wi-Fi component (W2 — depends on W1)

- [x] 4.1 `components/wifi/state.ts` (`wifiPopupVisible`, `wifiIconX`,
  `open/close/toggle`, `setWifiIconX`) — no settings-panel imports.
- [x] 4.2 `components/wifi/WifiContent.tsx`: move the list/rows/prompt +
  failure/off/empty states out of `controls/wifi.tsx`; own the refcounted scan
  lifecycle keyed on a `visible` prop; export `wifiPromptVisible` and
  `WifiToggle`.
- [x] 4.3 `components/wifi/WifiPopup.tsx`: `WifiPopupCatcher` + `WifiPopup`
  window (anchor under `wifiIconX`, `ON_DEMAND` while the prompt is shown, Esc
  close; header `Wi-Fi` + `WifiToggle` + `WifiContent`).
- [x] 4.4 `settings-panel/controls/wifi.tsx` → `WifiTile` only;
  `views/WifiView.tsx` → `NavHeader` + `WifiContent`.

## 5. Bluetooth component (W3 — depends on W1)

- [x] 5.1 `components/bluetooth/BluetoothContent.tsx`: device list + failure +
  discovery lifecycle keyed on `visible`.
- [x] 5.2 `settings-panel/controls/bluetooth.tsx` → `BluetoothTile` only;
  `views/BluetoothView.tsx` → `NavHeader` + `BluetoothContent`.
- [x] 5.3 No icon wiring for Bluetooth (out of scope).

## 6. Bar wiring + mutual exclusion (W5 — depends on W2)

- [x] 6.1 `bar/widgets/network.tsx`: left-click records icon x, closes the
  settings panel, `setWifiIconX`, `toggleWifiPopup`; right-click stays
  `wifitui`; drop the nm-applet `StatusNotifier` menu usage.
- [x] 6.2 `settings-panel/state.ts` `open()` closes the Wi-Fi popup.
- [x] 6.3 `app.tsx`: add `WifiPopupCatcher` + `WifiPopup` on the primary
  monitor (catcher first).

## 7. Provisioning layout (W6 — parallel, after the file list is frozen)

- [x] 7.1 `compositor_configs_config_dirs`: add `ags/services`,
  `ags/components{,/primitives,/wifi,/bluetooth,/sliders}`; remove
  `ags/settings-panel/services`.
- [x] 7.2 `compositor_configs_skeleton_files`: add the 11 new files; remove the
  3 `settings-panel/services` entries.
- [x] 7.3 Add a legacy cleanup task removing the deployed
  `ags/settings-panel/services` directory.
- [x] 7.4 `verify_compositor_skeleton_files`: new paths in, old paths out.
- [x] 7.5 Tests updated (`test_compositor_configs_role.py`,
  `test_verify_role.py`, any count/list assertions) and green.

## 8. Verification (gates)

- [x] 8.1 `ags bundle app.tsx --gtk 4` exit 0.
- [x] 8.2 `src/provisioning` unit suite green.
- [x] 8.3 `dotfiles-provision apply` + `verify` exit 0 (internet permitting for
  the unrelated `display_manager` role; `verify` alone must pass).
- [ ] 8.4 Runtime smoke (owner): popup opens under the Wi-Fi icon on
  left-click and its list scrolls when long; connect + password prompt in the popup; Esc/click-outside
  dismiss; mutual exclusion with the panel; panel sections + sliders unchanged;
  `wifitui` still on left-click.
