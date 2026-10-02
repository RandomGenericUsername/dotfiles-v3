# audio-panel-default-and-app-identity

## ADDED Requirements

### Requirement: The default endpoint re-resolves when the default changes

The audio panel SHALL re-resolve the default output and default input node when
the default device changes, without polling. It SHALL treat a change of the
default as an event distinct from a change of the node list, and SHALL trigger
re-resolution on its own `set-default` write, on any node-list change, and on
opening the popup.

#### Scenario: selecting another output updates the Output card

- **GIVEN** the popup is open on the main view with the analog sink as default
  and a Bluetooth sink also enumerated
- **WHEN** the user picks the Bluetooth sink in `Change ›`
- **THEN** the Output card title, its level line and the bar output glyph all
  describe the Bluetooth sink
- **AND** the Bluetooth row carries the `✓` in the device list

#### Scenario: one selection is enough

- **GIVEN** the audio server applies a default change asynchronously
- **WHEN** the user picks a device once
- **THEN** the panel shows the new default without a second selection and
  without waiting for playback to start
- **AND** the re-resolution it performs is bounded and stops once the new
  default is in force

#### Scenario: the per-app routing labels follow the new default

- **GIVEN** applications are routed to the previous default sink
- **WHEN** the user picks a different default sink
- **THEN** each application's routing label reports the new sink
- **AND** no application row is left advertising the previous device until the
  popup is reopened

#### Scenario: the node list does not change when the default does

- **GIVEN** two sinks are enumerated
- **WHEN** the default is switched from one to the other
- **THEN** the panel still re-resolves, because it does not treat node-list
  membership as the signal that the default moved

#### Scenario: a default changed outside the panel is shown on open

- **GIVEN** the default sink was changed by another tool while the popup was
  closed
- **WHEN** the user opens the popup
- **THEN** the Output card shows the new default sink

#### Scenario: no polling

- **GIVEN** the popup stays open indefinitely and nothing is clicked
- **WHEN** time passes
- **THEN** the panel issues no periodic re-read of the default endpoint; the
  re-resolutions come only from the three declared triggers

### Requirement: A seek control requires a known duration

The transport SHALL offer a seek control only when the player reports both seek
support and a known duration. It SHALL NOT commit a seek when the duration is
unknown, and a duration the app announced earlier SHALL survive a later
announcement of the same track that omits it.

#### Scenario: a live stream with no duration offers no seek control

- **GIVEN** a player that reports it can seek but publishes no duration
- **WHEN** the transport is rendered
- **THEN** no seek control is offered
- **AND** releasing a seek gesture commits nothing

#### Scenario: a dropped duration does not remove the control

- **GIVEN** a track whose duration the app announced, which the app then
  re-announces without that key while still naming the same media
- **WHEN** the transport is rendered
- **THEN** the seek control remains, positioned against the known duration

#### Scenario: a different track never inherits a duration

- **GIVEN** a track whose duration is known
- **WHEN** a different track is announced with no duration
- **THEN** no seek control is offered for it
- **AND** the previous track's duration is not applied to it

### Requirement: A committed position outranks a stale app report

The panel SHALL show the position the user committed until the application
reports a consistent one. A report that contradicts a playing media's position by
more than a tolerance SHALL NOT be shown, for a bounded window. A report at or
past the trusted position SHALL be shown immediately, and the panel SHALL accept
the application's report as soon as it does.

#### Scenario: an application reporting zero does not reset the display

- **GIVEN** an application whose position reports alternate between zero and the
  true position while playing
- **WHEN** the panel displays that application
- **THEN** the displayed position does not jump to the start
- **AND** a report at or past the displayed position is shown immediately

#### Scenario: a genuine restart is not suppressed

- **GIVEN** the panel is holding a position for an application
- **WHEN** the application announces different media starting at the beginning
- **THEN** the application starts from the beginning and the hold is discarded

#### Scenario: the hold expires

- **GIVEN** the panel is holding a position and the application never reports a
  consistent one
- **WHEN** the hold's window elapses
- **THEN** the panel shows the application's own report

### Requirement: The audio surface does not flicker on a churning graph

The panel SHALL NOT visibly reset a row or card because the audio graph is busy.
Re-reading unchanged state SHALL NOT re-render the surface, and a graph
notification SHALL NOT be mistaken for the default output having moved.

#### Scenario: an unchanged snapshot is not republished

- **GIVEN** a refresh that parses to exactly the state already held
- **WHEN** it completes
- **THEN** nothing on screen re-renders

#### Scenario: repeated notifications do not spawn overlapping work

- **GIVEN** many graph notifications arrive in quick succession
- **WHEN** a refresh is already running
- **THEN** at most one further refresh runs, after the current one finishes

#### Scenario: a busy graph is not treated as a moved default output

- **GIVEN** applications whose streams come and go while the default output
  stays the same device
- **WHEN** those notifications arrive
- **THEN** the Output card is not re-rendered for them

#### Scenario: a row keeps its binding across a re-link

- **GIVEN** an application's stream is briefly present without a parsed identity
- **WHEN** the snapshot is refreshed
- **THEN** the row keeps its stream-bound rendering rather than falling back to
  its transport-only rendering

#### Scenario: a row does not resize when its subtitle changes

- **GIVEN** an application row whose subtitle appears or disappears
- **WHEN** the row is rendered
- **THEN** the row's height, and every control below it, stay in place

### Requirement: The Output card's transport acts on the selected output device

The Output card's play/pause control SHALL act on the output device the card is
displaying, and on EVERY application routed through that device — whether those
applications are on other devices or share this one. It SHALL NOT act on a
single application chosen by a hidden recency rule. Its glyph SHALL reflect the
aggregate state, and its tooltip SHALL name the device and the number of
applications it will affect.

#### Scenario: pausing the selected output pauses everything routed to it

- **GIVEN** the headphones are the selected output and two applications are
  routed through them
- **WHEN** the user presses the Output card's transport
- **THEN** both applications pause

#### Scenario: applications on other devices are untouched

- **GIVEN** the headphones are selected, one application plays through them and
  another plays through the speakers
- **WHEN** the user pauses the Output card's transport
- **THEN** only the application routed through the headphones pauses

#### Scenario: the control never exceeds what the rows show

- **GIVEN** any set of application rows
- **WHEN** the Output card's transport is evaluated
- **THEN** the applications it acts on are exactly those whose routing label
  names the selected output
- **AND** the tooltip states that count and the device name

#### Scenario: a mixed aggregate silences rather than half-restarts

- **GIVEN** two applications routed to the selected output, one playing and one
  paused
- **WHEN** the user presses the transport
- **THEN** both end up paused
- **AND** the previously paused application is not started

#### Scenario: nothing routed to the device

- **GIVEN** no application is routed to the selected output
- **WHEN** the Output card is rendered
- **THEN** the transport is not shown

#### Scenario: a re-registered player does not fabricate recency

- **GIVEN** an application has been playing for a long time and its bus name
  leaves and reappears on the session bus
- **WHEN** the panel rediscovers it, still playing
- **THEN** the panel SHALL NOT treat the rediscovery as the app beginning to play

### Requirement: One Applications row per real app

The Applications list SHALL contain exactly one row per application, even when
the application's PipeWire stream and its MPRIS player spell its name
differently. The row SHALL be keyed by an identity both sources resolve to, and
every per-app control on it (stream volume, mute, routing, transport) SHALL
address that one playback.

#### Scenario: a differently-spelled identity does not duplicate the app

- **GIVEN** a live playback stream reporting `application.name = "Firefox"` and
  an MPRIS player whose root `Identity` is `Mozilla firefox`
- **WHEN** the Applications list is built
- **THEN** it contains a single Firefox row
- **AND** that row has both a live stream (volume, mute, routing) and the
  player's transport line

#### Scenario: a player with no stream still gets a row

- **GIVEN** an application with a live MPRIS player and no playback stream
- **WHEN** the Applications list is built
- **THEN** it contains a volume-only row for that application, with its
  transport line
- **AND** the row is not merged into an unrelated application

#### Scenario: a claimed key is never re-resolved

- **GIVEN** a live stream already claims an application's canonical key
- **WHEN** a player reports that same key
- **THEN** the player is listed under that key unchanged

#### Scenario: the transport stays bound to the unified row

- **GIVEN** one row exists for an application that has both a stream and a
  player
- **WHEN** its transport controls are used
- **THEN** they act on that application's player
- **AND** no second row appears for the same application

### Requirement: Long names are clamped, not renamed

Device and media names SHALL be rendered inside the popup surface. Where a name
exceeds the space available, the label SHALL ellipsize and SHALL expose the
full text as a tooltip. The device name itself SHALL remain the value the audio
server reports; the panel SHALL NOT substitute a name of its own.

#### Scenario: a long media title stays inside the surface

- **GIVEN** a media title long enough to exceed the row width
- **WHEN** the Applications card is rendered
- **THEN** the title and subtitle are ellipsized within the surface
- **AND** no text is drawn outside the popup surface

#### Scenario: a long device name stays inside the routing popover

- **GIVEN** a device whose reported name is long
- **WHEN** the routing popover lists it
- **THEN** the item is clamped to the popover width

#### Scenario: the full text remains available

- **GIVEN** any clamped label
- **WHEN** the pointer rests on it
- **THEN** the complete untruncated text is shown
