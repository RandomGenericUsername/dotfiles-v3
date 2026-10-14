# ags-surfaces (delta)

## ADDED Requirements

### Requirement: A surface body is a factory, mounted lazily

A `SurfaceSpec.body` SHALL be a **factory** (`body(host) => JSX.Element`), never a
pre-built element. A host SHALL call the factory only while the surface is
visible and SHALL tear the body down when the surface is hidden, so a hidden
surface holds no live body and runs none of its effects. Durable state SHALL live
in an app-level state module, not in the body.

Source: spine **AD-10**; doc 101 §4.4 (mount policy: Option B).

#### Scenario: the body is not built while hidden

- **WHEN** a surface is hidden and the host renders
- **THEN** the body factory is not called and no body instance exists

#### Scenario: the body is built on show and dropped on hide

- **WHEN** the surface becomes visible
- **THEN** the factory is called once and the body is live
- **WHEN** the surface becomes hidden again
- **THEN** the body is dropped and the next show builds a fresh body

### Requirement: At most one overlay is live

The overlay coordinator SHALL allow one overlay open at a time, and each host
SHALL mount its body only while its own overlay is open, so at most one surface
body is live at any instant.

Source: spine **AD-10**; doc 101 §4.4.

#### Scenario: opening a second overlay closes the first

- **WHEN** overlay A is open and overlay B is opened through the coordinator
- **THEN** overlay A is closed

#### Scenario: at most one body is live

- **WHEN** every host's visible flag is wired to the coordinator and overlays are
  opened in turn
- **THEN** the number of live surface bodies never exceeds one

### Requirement: `PopupHost` is the shipped popup primitive

The kit SHALL ship `PopupHost` (the anchored panel window: `marginTop`, the
clamped `marginLeft` anchor math, the keymode flip and the Escape controller) and
its click-catcher. All five bar popups (`AudioPopup`, `WifiPopup`,
`BatteryPopup`, `BluetoothPopup`, `SettingsPanel`) SHALL render through it and
SHALL NOT re-implement the catcher, the anchor clamp or the keymode setup.

Source: spine **AD-10**; doc 101 §4.4.

#### Scenario: no popup repeats the chrome

- **WHEN** the five popup sources are searched for `settings-catcher`,
  `marginLeft = createComputed` and `Astal.Keymode`
- **THEN** none of the five contains them (the chrome lives only in `kit/`)

#### Scenario: the click-catcher still closes the surface

- **WHEN** the primary button is released on the catcher fill
- **THEN** the surface's own close action runs

#### Scenario: keymode flips only for typed input

- **WHEN** a surface's `keyboard` accessor reads true (a password prompt or a
  text entry is on screen)
- **THEN** the window keymode is `ON_DEMAND`
- **WHEN** it reads false
- **THEN** the window keymode is `NONE`

### Requirement: Content stays mountable in two hosts

`WifiContent` and `BluetoothContent` SHALL remain mountable in both their popup
(`WifiPopup`/`BluetoothPopup`) and the settings panel (`WifiView`/`BluetoothView`).

Source: doc 101 §4.4 ("`WifiContent`/`BluetoothContent` are already mounted in two
hosts"); spine AD-10.

#### Scenario: the Wi-Fi body has two hosts

- **WHEN** the Wi-Fi content mount sites are searched
- **THEN** both `components/wifi/WifiPopup.tsx` and
  `settings-panel/views/WifiView.tsx` mount `WifiContent`

#### Scenario: the Bluetooth body has two hosts

- **WHEN** the Bluetooth content mount sites are searched
- **THEN** both `components/bluetooth/BluetoothPopup.tsx` and
  `settings-panel/views/BluetoothView.tsx` mount `BluetoothContent`

### Requirement: A new kit source is registered for deployment

`kit/surface.ts` and `kit/popup-host.tsx` SHALL be registered in
`compositor_configs_skeleton_files` and mirrored in the verify role, so a fresh
provision deploys them.

Source: spine **AD-17** (per-file placement); `deploy-coverage` gate.

#### Scenario: deploy coverage is green

- **WHEN** `make deploy-coverage` runs
- **THEN** every AGS module reachable from `app.tsx` is registered, including
  both new kit sources
