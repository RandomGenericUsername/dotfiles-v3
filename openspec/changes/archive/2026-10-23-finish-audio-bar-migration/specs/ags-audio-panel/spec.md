# ags-audio-panel (delta)

## MODIFIED Requirements

### Requirement: Audio application boundaries are hexagonal

The audio domain and application rules SHALL be independent of GJS/GTK, AstalWp,
Gio, and shell command transports. PipeWire and MPRIS SHALL be separate outbound
adapters behind explicit ports. GTK widgets — **including the status-bar
indicators** — SHALL render presentation state and dispatch application actions
without owning graph parsing, cross-source identity policy, or audio routing
rules. Every audio surface SHALL observe the session through the single
composition root (`audio/composition.ts`); no widget, view, or bar indicator
SHALL import `AstalWp` or bind `wp.nodes` directly. Existing dotfiles event-hub
behavior SHALL remain outside the audio domain.

*Changed from:* the requirement named "GTK widgets" generally without saying the
status-bar indicators were in scope. That was already implied, but it was not
enforced — the bar bound `AstalWp` through the legacy `audio/state.ts`. The
requirement now names the bar explicitly and states the single-composition-root
rule that makes the implication mechanical.

#### Scenario: core rules run without desktop runtime objects

- **GIVEN** pure audio identity, route, level, and presentation rules
- **WHEN** they are imported by a non-GJS runtime
- **THEN** they do not require GTK, Gio, AstalWp, a live PipeWire graph, or a session bus

#### Scenario: a UI action crosses an application port

- **GIVEN** the user changes an app's route, level, mute, or player state
- **WHEN** a GTK control activates
- **THEN** the control dispatches a named application action
- **AND** the relevant PipeWire or MPRIS adapter performs the effect
- **AND** the resulting source event updates presentation state

#### Scenario: the bar indicator observes the composition binding

- **GIVEN** the bar's output and microphone indicators are mounted
- **WHEN** their state is inspected
- **THEN** it is derived from `audioPanelBinding().model`
- **AND** neither indicator imports `AstalWp` or binds `wp.nodes`

## ADDED Requirements

### Requirement: Bar audio indicators consume the composition binding

The status bar's output and microphone indicators SHALL derive their state from
the audio composition binding's projected session model
(`projectAudioPanel` / `AudioPanelViewModel`), not from `AstalWp` directly. The
output glyph SHALL reflect the preferred output's volume and mute state; the
microphone glyph SHALL reflect the preferred input's mute state; the microphone
live dot SHALL be visible exactly when input-direction consumers are present.
The bar's volume nudge SHALL dispatch the same selected-output level application
action the popup and the Settings panel use.

#### Scenario: output glyph follows the preferred output

- **GIVEN** the preferred output's level is 30 percent and unmuted
- **WHEN** the output indicator renders
- **THEN** it shows the `volume` group's `low` variant
- **WHEN** the preferred output becomes muted
- **THEN** it shows the `muted` variant without a poll or a widget-owned epoch

#### Scenario: microphone glyph and live dot follow the input

- **GIVEN** the preferred input is unmuted and no application records
- **WHEN** the microphone indicator renders
- **THEN** it shows `mic-on` and no live dot
- **WHEN** an application opens a recording stream
- **THEN** the live dot appears while the glyph tracks the preferred input's mute state

#### Scenario: scroll nudge uses the shared application action

- **GIVEN** the preferred output is at 50 percent
- **WHEN** the user scrolls up over the output indicator
- **THEN** the bar dispatches the selected-output level application action to 55 percent
- **AND** the panel and Settings panel observe the same resulting level from the source

#### Scenario: click opens the shared popup surface

- **GIVEN** the audio popup is closed
- **WHEN** the user left-clicks either audio indicator
- **THEN** the popup opens through the shared UI-state module
- **AND** the indicator's x-centre is recorded so the popup anchors beneath it

### Requirement: Audio UI state is separate from audio graph state

Popup visibility, the active section, the view epoch, the follower anchor x, and
the level vocabulary SHALL live in a UI-state module (`audio/ui-state.ts`) that
depends only on `ags`, plus a pure level module (`audio/presentation/levels.ts`)
independent of `AstalWp`, `Gio`, and MPRIS. The level vocabulary (`levelVariant`,
`clampVolume`) SHALL be pure and node-testable,
so the same variant decision is shared by the bar, the popup, and the Settings
panel without importing a runtime.

#### Scenario: UI state carries no desktop-runtime dependency

- **GIVEN** the audio UI-state module
- **WHEN** it is imported by a non-GJS runtime
- **THEN** it requires only `ags` state primitives and the pure level functions
- **AND** it does not require AstalWp, Gio, MPRIS, or a live session bus

### Requirement: The legacy audio graph-state module is retired

The direct `AstalWp`/MPRIS binding in `audio/state.ts` SHALL be removed once
every consumer is migrated. No module SHALL expose a second audio source;
`AstalWp` and MPRIS access SHALL exist only behind the audio adapters. The
`useEndpointEpoch` invalidation workaround SHALL NOT be reintroduced on the bar
path: if the event-fed runtime misses a default-device change, the gap SHALL be
fixed in the observation adapter, not by a widget-owned epoch.

#### Scenario: no surface imports the legacy module

- **GIVEN** the migration is complete
- **WHEN** the AGS tree is searched for imports of the legacy `audio/state.ts`
- **THEN** none remain
- **AND** `AstalWp` is imported only by `audio/adapters/**`

#### Scenario: a missed default-device event is fixed at the adapter

- **GIVEN** a default output is changed outside the bar (pavucontrol, `wpctl`, hotplug)
- **WHEN** the projection does not update
- **THEN** the fix is made in the PipeWire observation adapter
- **AND** no `useEndpointEpoch`-style invalidation is added to the bar
