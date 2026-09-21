## MODIFIED Requirements

### Requirement: Panel composition over shared components

The settings panel SHALL compose its Wi-Fi, Bluetooth, and slider sections from
the shared `components/` layer and the `services/` domain layer, keeping only
panel-specific chrome (tiles, cards, navigation header, window, state). The
panel's own behavior and appearance SHALL be unchanged.

#### Scenario: Panel uses shared Wi-Fi content
- **WHEN** the Wi-Fi view is shown in the settings panel
- **THEN** it renders the navigation header plus the shared Wi-Fi content, with
  the same list, states, and password prompt as before

#### Scenario: Panel uses shared sliders
- **WHEN** the main view is shown
- **THEN** the Display and Sound cards render the shared brightness and volume
  slider components inside the panel's card chrome

#### Scenario: Panel state stays panel-owned
- **WHEN** the settings panel sources are inspected
- **THEN** the panel owns `panelVisible`/`activeView` and chrome, while Wi-Fi and
  Bluetooth domain state lives in `services/` and is only read by the panel
