# Design: extract-ags-shared-components

## 0. Invariants

1. **One-way dependency**: `settings-panel → components → services → (nm-client)`.
   `components/**` MUST NOT import from `settings-panel/**`. Only the bar
   widgets and the settings panel may coordinate overlays (mutual exclusion).
2. **Services are the single source of truth.** Components render service
   accessors and forward intent; they never talk D-Bus or spawn processes.
3. **UI never blocks.** No `call_sync`/subprocess in components (inherited from
   the services change).
4. **No behavior change to the settings panel UX** — same content, same states,
   only relocated and composed differently.

## 1. Services move + refcounted scan

Move `settings-panel/services/{nm-client,wifi-service,bluetooth-service}.ts` →
`ags/services/`. Update every import (controls, views, `bluetooth-agent.ts`).

Scan ownership becomes refcounted because two hosts may show the Wi-Fi list at
once (panel view + popup):

```ts
let scanUsers = 0
export function startScanning(): void {
  scanUsers++
  if (scanUsers > 1) return
  void requestScan()
  scheduleScan()
}
export function stopScanning(): void {
  scanUsers = Math.max(0, scanUsers - 1)
  if (scanUsers > 0) return
  // cancel the timer
}
```

Each host pairs one `startScanning()` with one `stopScanning()` in its
`visible` effect cleanup.

## 2. Shared primitives

Move the two genuinely generic primitives out of `settings-panel/primitives.tsx`
into `components/primitives/`:

- `IconToggle.tsx` (icon button with on/off glyphs) — used by `CapabilityTile`
  (panel) and `WifiToggle` (component).
- `LevelSlider.tsx` (glyph + track) — used by both slider components.

`settings-panel/primitives.tsx` keeps the panel chrome (`PanelCard`,
`CapabilityTile`, `NavHeader`) and imports `IconToggle` from
`components/primitives`.

## 3. `components/wifi/`

### 3.1 `state.ts`
```ts
wifiPopupVisible: Accessor<boolean>
openWifiPopup(): void
closeWifiPopup(): void
toggleWifiPopup(): void
wifiIconX: Accessor<number | null>
setWifiIconX(x: number): void
```
No knowledge of the settings panel (one-way rule). Mutual exclusion is done by
the callers (§6).

### 3.2 `WifiContent.tsx`
```tsx
export function WifiContent({ visible }: { visible: Accessor<boolean> })
```
The embeddable body: "Wi-Fi is off", the state-derived failure message,
"No networks found", the `<For>` network list, and the password prompt
(visibility-toggled). Owns the scan lifecycle keyed on `visible`:
```ts
createEffect(() => { if (!visible()) return; startScanning(); return () => stopScanning() })
```
Also exports `wifiPromptVisible`, `WifiRow`, `WifiPasswordPrompt`, and
`WifiToggle` (header power toggle using `IconToggle`).

### 3.3 `WifiPopup.tsx`
- `WifiPopupCatcher(gdkmonitor)` — full-screen overlay catcher (same shape as
  `SettingsCatcher`), visible only while `wifiPopupVisible`, dismisses on
  release.
- `WifiPopup(gdkmonitor)` — window `name="wifi-popup"`, `class="settings-panel"`
  (reuses the panel surface styling), `anchor={TOP|LEFT}`,
  `exclusivity=IGNORE`, `layer=OVERLAY`, `marginTop=52`,
  `marginLeft = wifiIconX − width/2` clamped to the monitor, `visible` from
  `wifiPopupVisible`. `keymode` switches `ON_DEMAND` while
  `wifiPromptVisible()` else `NONE`; an `EventControllerKey` closes on Escape.
  Body: a compact header (`Wi-Fi` + `WifiToggle`) + `WifiContent`.

## 4. `components/bluetooth/BluetoothContent.tsx`
```tsx
export function BluetoothContent({ visible }: { visible: Accessor<boolean> })
```
Device list + failure message + discovery lifecycle keyed on `visible`
(start/stop discovery). Exports the device-row component. No icon wiring.

## 5. `components/sliders/`
- `VolumeSlider.tsx` — AstalWp default-speaker binding, level-aware glyph,
  `LevelSlider`, mute toggle. Self-contained (no panel imports).
- `BrightnessSlider.tsx` — `brightnessctl` read/write; polling keyed on its own
  `visible` prop:
  ```tsx
  export function BrightnessSlider({ visible }: { visible: Accessor<boolean> })
  ```

## 6. Panel composition

- `settings-panel/controls/wifi.tsx` → `WifiTile` only.
- `settings-panel/controls/bluetooth.tsx` → `BluetoothTile` only.
- `settings-panel/controls/volume.tsx` → `<PanelCard title="Sound"><VolumeSlider/></PanelCard>`.
- `settings-panel/controls/brightness.tsx` → `<PanelCard title="Display"><BrightnessSlider visible={panelVisible}/></PanelCard>`.
- `settings-panel/views/WifiView.tsx` → `NavHeader(title, back, trailing <WifiToggle/>)` + `<WifiContent visible={panelVisible() && activeView()==="wifi"}/>`.
- `settings-panel/views/BluetoothView.tsx` → `NavHeader` + `<BluetoothContent visible=.../>`.

## 7. Bar wiring + mutual exclusion

`bar/widgets/network.tsx`:
- left-click (`onClicked`): record the pointer x via a motion controller
  (mirror `bar/widgets/settings.tsx`), `close()` the settings panel,
  `setWifiIconX(x)`, `toggleWifiPopup()`;
- right-click (`BUTTON_SECONDARY`): launch `wifitui`;
- drop the `findNetworkItem`/`popupItemMenu` usage (nm-applet menu replaced).

`settings-panel/state.ts` `open()` also calls `closeWifiPopup()` so the two
overlays stay mutually exclusive.

`app.tsx`: create `WifiPopupCatcher(primary)` **before** `WifiPopup(primary)`
so the popup stacks above the catcher (same ordering rule as the settings
panel). Both are added alongside the existing settings windows.

## 8. Provisioning layout

`compositor_configs`:
- `compositor_configs_config_dirs`: add `ags/services`,
  `ags/components`, `ags/components/primitives`, `ags/components/wifi`,
  `ags/components/bluetooth`, `ags/components/sliders`; remove
  `ags/settings-panel/services`.
- `compositor_configs_skeleton_files`: add the 11 new files under the new paths;
  remove the 3 `settings-panel/services/*` entries (47 → 55).
- New task: remove the legacy deployed `.../ags/settings-panel/services`
  directory (`state: absent`) — `copy` never deletes.

`verify`: `verify_compositor_skeleton_files` gains the 11 new paths and drops
the 3 old ones.

Tests: `test_compositor_configs_role.py` (count 47→55, source list, deploy
fixture), `test_verify_role.py` (fixture dirs + files), plus any var-name
assertions.

## 9. Verification

- `ags bundle app.tsx` exit 0.
- provisioning unit suite green.
- `dotfiles-provision verify` exit 0 (the spine carries the new layout).
- Runtime smoke: right-click the Wi-Fi bar icon opens the popup under the icon;
  connect/prompt from the popup; Esc/click-outside dismiss; opening the popup
  closes the panel and vice versa; the settings panel Wi-Fi/Bluetooth/sliders
  are unchanged; `wifitui` still opens on left-click.
