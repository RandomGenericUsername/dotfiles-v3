## ADDED Requirements

### Requirement: Shared UI components

The AGS config SHALL provide reusable UI components for the Wi-Fi network
picker, the Bluetooth device list, and the volume/brightness sliders, located
outside the settings panel and usable by any host (the settings panel now, bar
widgets later).

#### Scenario: Components are host-agnostic
- **WHEN** the component sources are inspected
- **THEN** no file under `components/` imports from `settings-panel/`, and
  components read state only from `services/`

#### Scenario: Wi-Fi content embeds in more than one host
- **WHEN** `WifiContent` is rendered with a `visible` accessor
- **THEN** it shows the network list, failure/off/empty states, and the password
  prompt, and starts/stops scanning with that `visible` value

#### Scenario: Sliders are self-contained
- **WHEN** the volume or brightness slider component is rendered by any host
- **THEN** it reads and writes its own domain (AstalWp / brightnessctl) without
  importing settings-panel code, and the brightness slider polls only while its
  `visible` prop is true

### Requirement: Wi-Fi popup from the bar icon

The bar's network widget SHALL open the shared Wi-Fi content in a popup window
on left-click, anchored beneath the Wi-Fi icon. Right-click SHALL remain the
`wifitui` launcher.

#### Scenario: Left-click opens the popup
- **WHEN** the user left-clicks the network widget
- **THEN** the Wi-Fi popup opens beneath the icon with the network list, and the
  nm-applet StatusNotifier menu is not shown

#### Scenario: Right-click launches the TUI
- **WHEN** the user right-clicks the network widget
- **THEN** the `wifitui` terminal interface is launched

#### Scenario: Popup list is bounded and scrollable
- **WHEN** many networks are in range
- **THEN** the popup's network list is capped to a fraction of the screen and
  scrolls, instead of growing to the full window height

#### Scenario: Popup does not open two overlays
- **WHEN** the Wi-Fi popup opens while the settings panel is visible
- **THEN** the settings panel closes, and opening the settings panel closes the
  Wi-Fi popup

#### Scenario: Popup dismisses
- **WHEN** the user presses Escape or clicks outside the popup
- **THEN** the popup closes

#### Scenario: Password entry works in the popup
- **WHEN** a secured network triggers the password prompt while the popup is
  shown
- **THEN** the popup takes keyboard input so the password can be typed

### Requirement: Refcounted Wi-Fi scanning

The Wi-Fi scan lifecycle SHALL be reference-counted so that multiple hosts
showing the Wi-Fi list do not stop each other's scans.

#### Scenario: Two hosts scanning
- **WHEN** the settings Wi-Fi view and the popup are both shown and then one is
  hidden
- **THEN** scanning continues until the last host hides
