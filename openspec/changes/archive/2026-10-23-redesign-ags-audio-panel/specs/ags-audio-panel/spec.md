# AGS audio panel

## ADDED Requirements

### Requirement: Audio panel inherits the active desktop palette

The audio popup and its bar indicators SHALL use the wallpaper-generated AGS runtime palette loaded from `colors.css`, consistent with existing GTK/AGS surfaces. New audio styles SHALL use the shared `@color_*` tokens and established surface, selected-row, focus, and slider treatments. The UI SHALL NOT introduce a fixed light/dark palette or hard-coded decorative colors; semantic microphone-live green and application brand artwork remain the established exceptions. The approved browser concept's literal colors are illustrative and SHALL NOT be copied as runtime theme values.

#### Scenario: wallpaper palette changes restyle audio controls

- **GIVEN** the desktop regenerates its AGS palette after a wallpaper change
- **WHEN** the audio panel is displayed with the new `colors.css`
- **THEN** its surfaces, text, selected routes, focus indicators, and sliders use the active runtime tokens
- **AND** no audio-specific fixed palette overrides the shared theme

#### Scenario: selected route and slider follow shared AGS styles

- **GIVEN** an app route or output device is selected
- **WHEN** the selected state and level controls are rendered
- **THEN** selected state uses the shared `@color_10` treatment
- **AND** selected text follows the GUI-unification on-selection contrast rule and meets 4.5:1
- **AND** small muted/supporting text uses at least the validated 64% foreground-opacity token unless it is decorative and carries no required information
- **AND** slider track, fill, and thumb use the shared AGS slider tokens

### Requirement: Preferred output and follow-preferred routing

The audio panel SHALL expose the system preferred/default output device. Each active stream route SHALL be `Follow preferred`, `Explicit(endpoint)`, or `Unknown`. A newly appearing app stream SHALL follow the preferred output by default unless the user or an observed external route action explicitly overrides it. Changing the preferred output SHALL move following streams and SHALL preserve explicit routes. A per-app explicit choice SHALL remain explicit even when it selects the same endpoint as the preferred output. The UI SHALL show the actual endpoint when known even if route intent is unknown, and SHALL NOT infer intent for a pre-existing stream solely from endpoint equality. A stream already active when the adapter starts, or whose intent history is lost, SHALL be `Unknown` unless authoritative evidence restores its intent. Selecting “Follow preferred” SHALL route the active stream to the current preferred device and resume following future preferred-output changes.

#### Scenario: choosing a preferred output moves following apps

- **GIVEN** outputs A, B, and C are available
- **AND** Chrome and Firefox follow the preferred output C
- **AND** Spotify has an explicit route to A
- **WHEN** the user selects B as the preferred output
- **THEN** the system default becomes B
- **AND** Chrome and Firefox route to B
- **AND** Spotify remains routed to A

#### Scenario: app route menu distinguishes intent from coincidence

- **GIVEN** C is the preferred output
- **WHEN** an app's route menu is shown
- **THEN** the menu has a distinct “Follow preferred · C” choice
- **AND** it lists explicit device targets separately, including “C · Override”
- **AND** the app's current choice is identified

#### Scenario: returning an app to preferred restores following behavior

- **GIVEN** Spotify is explicitly routed to A while the preferred output is C
- **WHEN** the user selects “Follow preferred · C” for Spotify
- **THEN** Spotify routes to C
- **AND** a later preferred-output change moves Spotify with the preference

#### Scenario: an explicit route to the preferred device stays explicit

- **GIVEN** C is the preferred output
- **WHEN** the user explicitly selects “C · Override” for Chrome
- **THEN** the row continues to identify the route as an explicit override
- **WHEN** the preferred output later changes to B
- **THEN** Chrome remains routed to C

#### Scenario: a first-launched app follows later preferred-output changes

- **GIVEN** A is the current preferred output
- **AND** no per-app override or external explicit target has been observed for the new stream
- **WHEN** Chrome is launched for the first time and its playback stream appears
- **THEN** Chrome is represented as following the preference and is routed to A
- **WHEN** the user changes the preferred output to C
- **THEN** Chrome follows the preference and routes to C

#### Scenario: an existing stream with unprovable intent is shown as unknown

- **GIVEN** an app stream already exists when the audio adapter starts
- **AND** its effective endpoint is C, the preferred output
- **AND** no authoritative route-intent record or target metadata is available
- **WHEN** the app row is rendered
- **THEN** it shows C as the observed endpoint
- **AND** it labels route intent as unknown rather than claiming Follow preferred
- **AND** the user can explicitly choose Follow preferred or an endpoint override

### Requirement: Device output level is separate from app stream level

The preferred-output section SHALL provide an output-level and mute control for the selected sink. The sink-level control SHALL affect every stream actually routed to that sink, whether its route follows the preference or is explicit. Its level-aware speaker icon SHALL reflect the sink's actual volume and mute state, and activating it SHALL toggle only the sink's mute state. The popup, bar volume nudge, and Settings slider SHALL use the same selected-output level/mute application actions and observe the same source state. Each app SHALL have an independent stream-level control that changes only that app's stream. The panel SHALL NOT present an aggregate play/pause/seek control in the output-device section.

#### Scenario: sink level affects every stream sent to that sink

- **GIVEN** C is selected and Chrome follows C
- **AND** Spotify has an explicit route to C
- **AND** Firefox is routed to A
- **WHEN** the user changes C's output level
- **THEN** the device-level gain for C changes
- **AND** both Chrome and Spotify are affected by that sink level
- **AND** Firefox is not affected by C's sink level
- **AND** no app's stream-level setting is overwritten

#### Scenario: app level is isolated

- **GIVEN** Chrome and Spotify are both audible
- **WHEN** the user changes Chrome's per-app level
- **THEN** only Chrome's stream level changes
- **AND** the preferred sink level and Spotify's stream level remain unchanged

#### Scenario: output section has no ambiguous player target

- **GIVEN** one or more apps expose MPRIS players
- **WHEN** the preferred-output section is rendered
- **THEN** it contains no aggregate play/pause or seek action
- **AND** each player action is located in its app row

#### Scenario: selected output mute is independent of app mute

- **GIVEN** output C is selected and Chrome is routed to it
- **WHEN** the user activates the selected-output speaker icon
- **THEN** only output C's mute state changes
- **AND** the icon reflects C's actual mute/volume state
- **AND** Chrome's stream-level mute and level remain unchanged

#### Scenario: Settings output level is shared with the popup

- **GIVEN** output C is selected and Chrome has its own stream level
- **WHEN** the user changes the Settings-panel output slider
- **THEN** the selected sink's level changes through the shared output-level action
- **AND** the popup reflects the updated sink level from PipeWire state
- **AND** Chrome's stream-level setting remains unchanged

### Requirement: Per-app mute icon reflects live stream state

Each app row SHALL show a speaker icon derived from that app stream's actual volume and mute state. Activating that icon SHALL toggle only that app stream's mute state. Muting SHALL preserve the stream's volume value so unmuting restores its prior level. Updates from outside the panel SHALL be reflected in the icon and control state.

#### Scenario: icon level follows the actual app stream level

- **GIVEN** an unmuted app stream's volume changes externally from medium to low
- **WHEN** the panel receives the stream update
- **THEN** that app's speaker icon changes to the low-volume variant
- **AND** other app icons remain unchanged

#### Scenario: app mute preserves level

- **GIVEN** Chrome has a stream level of 63 percent and is unmuted
- **WHEN** the user clicks Chrome's speaker icon
- **THEN** only Chrome becomes muted
- **AND** its stream level remains 63 percent
- **AND** its icon indicates mute
- **WHEN** the user clicks the icon again
- **THEN** Chrome unmutes at 63 percent

### Requirement: App rows present media identity and artwork

An app row SHALL display the app's name as visible text independently of the media title. With an associated MPRIS player it SHALL display the current media title and artist when provided. It SHALL display supplied media artwork when available while retaining the app identity in the row. When artwork is unavailable, the app icon SHALL be used. When track metadata is absent, the row SHALL use an honest app/media fallback and SHALL NOT present a generic PipeWire backend label as a song title.

The media projection SHALL update when MPRIS metadata changes, including while playback remains Playing; metadata presentation SHALL NOT depend on pausing the player or reopening the popup. PipeWire stream labels such as `AudioStream` or `Playback` SHALL NOT replace available MPRIS metadata. If a player does not expose metadata, the row SHALL use the honest fallback above and SHALL NOT invent a track title.

#### Scenario: metadata and artwork are shown for an active stream

- **GIVEN** a Chrome stream is linked to an MPRIS player reporting a title, artist, and artwork URI
- **WHEN** the app row is rendered
- **THEN** it shows the title and artist
- **AND** it shows the supplied artwork
- **AND** it keeps Chrome's app identity visible

#### Scenario: Chrome metadata appears while playback remains active

- **GIVEN** Chrome is Playing and its MPRIS player reports a media title and artist
- **WHEN** that metadata is available at startup or changes during playback
- **THEN** the row shows the current title and artist without requiring pause or popup reopen
- **AND** the displayed values update from MPRIS events while Chrome remains Playing

#### Scenario: Tidal metadata is shown while its stream is live

- **GIVEN** Tidal is Playing and its MPRIS player reports the title `Opus Pocus` and artist `Jason Becker`
- **AND** its PipeWire stream reports the generic media name `Playback`
- **WHEN** the app row is rendered
- **THEN** it shows `Opus Pocus` and `Jason Becker`
- **AND** the generic stream label does not replace the MPRIS metadata

#### Scenario: Firefox stream label is not presented as media metadata

- **GIVEN** Firefox exposes the PipeWire label `AudioStream`
- **AND** its MPRIS player reports a media title and artist
- **WHEN** the Firefox row is rendered
- **THEN** it shows the MPRIS title and artist
- **AND** `AudioStream` is not shown as the media subtitle

#### Scenario: missing Firefox metadata uses an honest fallback

- **GIVEN** Firefox exposes `AudioStream` but its MPRIS player has no title or artist
- **WHEN** the Firefox row is rendered
- **THEN** it identifies Firefox as the app
- **AND** it does not present `AudioStream` as a track title

#### Scenario: missing artwork falls back to app identity

- **GIVEN** an app player reports title and artist but no usable artwork
- **WHEN** its row is rendered
- **THEN** the title and artist remain visible
- **AND** the app icon is used in place of artwork

#### Scenario: a stream without MPRIS remains controllable

- **GIVEN** Discord has a PipeWire stream but no associated MPRIS player
- **WHEN** its row is rendered
- **THEN** it still provides app volume, mute, and route controls
- **AND** it does not display player transport or seek controls

### Requirement: App row lifetime follows stream and player independently

An app row SHALL remain available while either its PipeWire playback stream or its associated MPRIS player exists. Loss or relink of a PipeWire stream SHALL NOT clear valid MPRIS metadata or destroy the player's app row. Stream-specific volume, mute, and route controls SHALL be unavailable when no current stream can safely receive the action; player controls SHALL remain available when the MPRIS player is still present. When both sources disappear, the row SHALL be removed without transferring state or commands to another app.

#### Scenario: paused player keeps its media identity through a stream gap

- **GIVEN** Firefox has a live MPRIS player with title and artwork
- **AND** its PipeWire stream is temporarily removed while paused or relinking
- **WHEN** the audio panel receives the stream removal
- **THEN** the Firefox row and its last authoritative MPRIS title/artwork remain stable
- **AND** stream-only controls are disabled or marked unavailable until a current stream returns
- **AND** the row does not blink, resize, or substitute a backend label for the track title

#### Scenario: ended player and stream are removed

- **GIVEN** an app's MPRIS player and PipeWire stream both disappear
- **WHEN** both source updates have been reconciled
- **THEN** the app row is removed
- **AND** no held stream node can receive a command

### Requirement: Playback and seek controls are app-scoped and capability-aware

Each supported MPRIS player SHALL expose its own playback controls in the matching app row. Seek SHALL be offered only when the player advertises seeking and a usable duration is known. A missing seek capability SHALL NOT remove unrelated app stream controls. Seek completion and metadata updates SHALL NOT visibly blink, resize, or rebind the app row.

#### Scenario: seek belongs to the matching app

- **GIVEN** Chrome and Spotify both have active players
- **WHEN** the user seeks in Chrome's row
- **THEN** only Chrome's player position changes
- **AND** Spotify's player position is unchanged

#### Scenario: unavailable seek leaves other app controls present

- **GIVEN** an app player cannot seek or has no usable duration
- **WHEN** its row is displayed
- **THEN** no seek affordance is shown
- **AND** supported play/pause, app volume, mute, and routing remain available

### Requirement: Audio controls expose accessible identity, state, and keyboard operation

Each app row SHALL expose a semantic group labelled with the visible app name and current media when available. Icon-only controls and sliders SHALL have accessible names that identify scope (device, app, or input), action, and state. Level sliders SHALL expose percent values; seek SHALL expose elapsed and total playback time. Route selectors SHALL expose the current route intent and endpoint, selected option, and expanded/collapsed state. They SHALL support keyboard opening, option navigation, commit, Escape cancellation, and focus return. Focus order SHALL follow visible order and SHALL stay on the same logical control when its row remains. At constrained work-area sizes or increased text scale, controls SHALL remain reachable without horizontal clipping. Text and controls SHALL meet the repository GUI contrast standard: at least 4.5:1 for small text and 3:1 for non-text control/focus boundaries.

#### Scenario: route selector communicates selection and keyboard behavior

- **GIVEN** Chrome follows preferred output C
- **WHEN** keyboard focus reaches Chrome's route selector
- **THEN** its accessible name/value identifies Chrome, Follow preferred, and C
- **WHEN** the user opens it and moves to A · Desk speakers
- **THEN** the option is announced as selected after commit
- **AND** Escape before commit closes the selector and returns focus to its trigger

#### Scenario: route selector announces unknown intent

- **GIVEN** Chrome's observed endpoint is C but route intent is unknown
- **WHEN** keyboard focus reaches Chrome's route selector
- **THEN** its accessible name/value identifies Chrome, the observed endpoint C, and unknown intent
- **AND** its options allow the user to choose Follow preferred or an explicit endpoint

#### Scenario: app identity is available without artwork inspection

- **GIVEN** Chrome is playing media with artwork
- **WHEN** a screen reader traverses the row
- **THEN** Chrome is announced as the app identity
- **AND** the media title and artist are announced separately
- **AND** artwork does not replace the app name

#### Scenario: level and seek sliders expose meaningful values

- **GIVEN** the selected output is C at 72 percent
- **AND** Chrome's player position is 1:25 of 4:03
- **WHEN** assistive technology reads the controls
- **THEN** the sink slider is identified as C output level at 72 percent
- **AND** Chrome's seek control is identified as its playback position at 1:25 of 4:03

#### Scenario: controls remain reachable in a constrained work area

- **GIVEN** the popup is opened on a short monitor or with increased text scaling
- **WHEN** the content exceeds available height or width
- **THEN** content scrolls or wraps without horizontal clipping
- **AND** the current keyboard focus remains visible and reachable

#### Scenario: seek and stream relink do not flicker the row

- **GIVEN** a user seeks while the PipeWire stream is briefly removed and relinked
- **WHEN** graph and player events arrive
- **THEN** the row's media text and control geometry remain stable
- **AND** writes are not sent to a stale PipeWire node

### Requirement: Input, microphone activity, and screen capture stay distinct

The popup SHALL retain input-device selection, input level/mute, and a list of active app streams consuming microphone input. The audio panel SHALL distinguish microphone-consuming streams from the dotfiles screen-capture tool's recording state. The bar microphone indicator SHALL be visible only while an app actually consumes microphone input; its glyph SHALL reflect the default-microphone mute state and its live ornament SHALL reflect active use. Screen-capture state SHALL NOT activate the microphone indicator.

#### Scenario: input device and level controls are independent

- **GIVEN** the USB microphone is the preferred input at 74 percent
- **WHEN** the user selects the built-in microphone and changes its input level
- **THEN** the preferred input and its level update
- **AND** output device, output level, and app stream levels remain unchanged

#### Scenario: mic consumer is visible without screen capture

- **GIVEN** Discord consumes microphone input while the screen-capture tool is idle
- **WHEN** the audio popup and bar are rendered
- **THEN** Discord appears under microphone activity
- **AND** the bar mic-use indicator is visible
- **AND** screen-capture recording is not implied

#### Scenario: screen capture does not impersonate an audio input stream

- **GIVEN** the screen-capture tool records the screen without an app consuming microphone input
- **WHEN** capture state changes
- **THEN** the capture indicator reflects the screen-capture state
- **AND** the microphone activity list and mic-use indicator remain based on actual input streams

### Requirement: Audio adapters preserve event-driven authority

PipeWire/WirePlumber SHALL remain the authority for output/input devices, stream level/mute, and routing. MPRIS SHALL remain the authority for media metadata, player capabilities, and playback state. State updates SHALL be signal/event-driven with hydration where required; implementations SHALL NOT poll external audio or player state to refresh the UI. The dotfiles domain-event hub SHALL NOT carry PipeWire or MPRIS state.

#### Scenario: external changes update the view from source events

- **GIVEN** the preferred output, stream mute, player status, or metadata changes outside the panel
- **WHEN** the corresponding PipeWire or MPRIS event is received
- **THEN** the affected view projection updates from that source
- **AND** no periodic command polling is required

#### Scenario: audio state does not enter the jobs event hub

- **GIVEN** PipeWire and MPRIS adapters are active
- **WHEN** audio state changes
- **THEN** it is consumed through the audio adapters
- **AND** no `audio.*` job topic is published through the dotfiles event hub

### Requirement: Audio rows remain stable under graph churn

Re-reading unchanged state SHALL NOT rebuild application rows. A transient stream unlink/relink or title change SHALL NOT reset the row, clear valid metadata, shift adjacent controls, or cause visible text blinking. State reconciliation SHALL be bounded and owned by the audio application/presentation boundary, not scattered through GTK widgets.

#### Scenario: unchanged graph state keeps existing rows

- **GIVEN** a graph notification whose normalized app, route, and player projection is unchanged
- **WHEN** the notification is processed
- **THEN** the existing row instances remain in place
- **AND** unchanged labels and images are not needlessly rewritten

#### Scenario: a stream relink retains app identity

- **GIVEN** a PipeWire stream is temporarily absent during a seek/relink
- **WHEN** the same app's stream returns
- **THEN** its row remains associated with the same app/player identity
- **AND** its route and player information do not jump to another app

#### Scenario: seeking does not blink a Firefox row with an unchanged subtitle

- **GIVEN** Firefox is playing and its displayed row text is unchanged
- **WHEN** the user moves the seek slider and PipeWire or MPRIS emits related updates
- **THEN** the existing row remains visually stable without a blink or geometry reset
- **AND** its title, route, app level, and player identity remain attached to Firefox

### Requirement: Audio application boundaries are hexagonal

The audio domain and application rules SHALL be independent of GJS/GTK, AstalWp, Gio, and shell command transports. PipeWire and MPRIS SHALL be separate outbound adapters behind explicit ports. GTK widgets SHALL render presentation state and dispatch application actions without owning graph parsing, cross-source identity policy, or audio routing rules. Existing dotfiles event-hub behavior SHALL remain outside the audio domain.

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
