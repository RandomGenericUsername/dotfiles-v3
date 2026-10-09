# ags-audio-panel (delta)

## MODIFIED Requirements

### Requirement: App stream level is the only level the panel sets

The preferred-output section SHALL present the output **selector** and SHALL NOT
present a device-level output level or mute control. Owner decision 2026-10-07:
the selector stays because it governs real behaviour — WirePlumber's
`follow-default-target` moves streams following the default whenever the default
changes, and hiding the control only hid the behaviour — while the device-level
level line is removed because it read as a second, competing control beside each
app's own.

Each app SHALL have an independent stream-level control that changes only that
app's stream. Sink gain remains reachable from the Settings panel through the
shared output-level application action, so there is one implementation of that
use case rather than two that can drift. The panel SHALL NOT present an
aggregate play/pause/seek control in the output-device section.

*Changed from:* the previous requirement mandated an output-level and mute
control for the selected sink inside the preferred-output section, with its own
level-aware icon and shared popup/bar/Settings actions. That control is removed
from the panel; the Settings surface is unchanged.

#### Scenario: the preferred-output section exposes no device-level level control

- **GIVEN** the popup is open with a preferred output selected
- **WHEN** the preferred-output section is rendered
- **THEN** it contains the output selector
- **AND** it contains no device-level level slider and no device-level mute control
- **AND** it contains no aggregate play/pause or seek action

#### Scenario: changing the preferred output moves only followers

- **GIVEN** Chrome follows the preferred output and Firefox is pinned to A
- **WHEN** the user selects C as the preferred output
- **THEN** Chrome's audio follows the new default
- **AND** Firefox remains on A
- **AND** no app's stream-level setting is overwritten

#### Scenario: app level is isolated

- **GIVEN** Chrome and Spotify are both audible
- **WHEN** the user changes Chrome's per-app level
- **THEN** only Chrome's stream level changes
- **AND** Spotify's stream level remains unchanged

#### Scenario: Settings still reaches sink gain

- **GIVEN** output C is selected and Chrome has its own stream level
- **WHEN** the user changes the Settings-panel output slider
- **THEN** the selected sink's level changes through the shared output-level action
- **AND** the popup reflects the updated sink level from PipeWire state
- **AND** Chrome's stream-level setting remains unchanged

## ADDED Requirements

### Requirement: The panel's transport button uses the panel's own icon group

The play/pause button in an app row SHALL use the `media-transport-panel` icon
group, so the panel can adopt its own art without altering any other surface.
The `media-transport` group SHALL remain the source for `previous` and `next`
here and for every other consumer, including the bar.

#### Scenario: only the panel's play/pause changes

- **GIVEN** the panel renders an app row with transport controls
- **WHEN** the play/pause button is rendered
- **THEN** it uses an icon from `media-transport-panel`
- **AND** previous and next use `media-transport`
- **AND** the bar's audio indicator is unchanged
