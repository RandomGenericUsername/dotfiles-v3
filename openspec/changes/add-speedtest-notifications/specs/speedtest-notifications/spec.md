## Purpose

A speed-test measurement currently completes silently: the panel rows update and, if you are not looking, the result is lost until the next interval. This capability makes each run observable in the notification surface the desktop already uses, as a single card that reports progress in place and settles on the measured result — reusing the existing notification stack and the existing domain-event seam rather than introducing a new surface.

The approved mock is `mock.html`, states `state-stc-running`, `state-stc-result`, `state-stc-error`, `state-stc-setting`.

## ADDED Requirements

### Requirement: Reuse the existing notification architecture (no new surface)

The speed-test notification SHALL be delivered by the existing notification app (`src/gui-tools/notifications/`) through the existing domain-event hub (`org.dotfiles.Events`). It SHALL NOT introduce a new AGS instance, a new bus name, a new notification protocol, or a second event-bus client implementation. Specifically:

- the card SHALL be built by `NotificationsWindow` and SHALL NOT be emitted via `org.freedesktop.Notifications.Notify` with a `replaces_id` (the wallpaper progress model is a bespoke in-place card, not a notification with grouping)
- the consumer SHALL subscribe through a `lib/speedtest-events.ts` module shaped like the existing `lib/wallpaper-events.ts` — single topic, single handler, subscribe-before-read, no polling timer
- the card SHALL reuse the shipped `.notif-card` base class and `CARD_WIDTH`, and SHALL be styled only with `@color_*` tokens from `colors.css`

#### Scenario: No new bus name or instance
- **WHEN** the change is implemented
- **THEN** `ags list` shows no instance beyond the existing `ags`, `notifications`, `capture`, and `hypr-pano`, and no new well-known bus name is claimed

#### Scenario: Card is a bespoke in-place card, not a grouped Notify
- **WHEN** a speed-test run reaches a terminal state
- **THEN** the card is the one built and mutated by `NotificationsWindow`; no `Notify` call is made for the speed-test path and no `replaces_id` is used

### Requirement: Speed-test lifecycle event

`contracts/event-contract.json` SHALL define a `speedtest.state` topic, superseding `speedtest.finished`, with payload `{ state, trigger, ssid, server_name }` where `state ∈ { starting, done, error }` and `trigger ∈ { scheduled, manual, connect }`. Every key and enum value SHALL be pinned by the event-contract drift gate, and the gate SHALL be green before the producer or consumer is implemented.

The producer SHALL emit `starting` when a run begins and exactly one terminal `done` or `error` when it settles — including when the run is abandoned by the watchdog. The `done` payload SHALL carry `down_mbps`, `up_mbps`, and `latency_ms`, plus `ssid` and `server_name` so the card can name the network and test server it measured (the card requirement below depends on these; the payload and the card MUST NOT disagree). `ssid` and `server_name` MAY be empty strings when the information is unavailable. The card SHALL render whichever half it has, and SHALL fall back to the trigger phrase only when BOTH are absent — discarding a measured SSID because the backend reported no server name would throw away a fact we did measure. A missing half SHALL be omitted entirely, never left as a dangling separator. The `error` payload SHALL carry a short human-readable reason with no traceback.

The producer SHALL remain non-fatal to the speed-test UI when the hub is absent, matching the existing `publishSpeedTestFinished` behaviour.

#### Scenario: Run start is announced
- **WHEN** a scheduled or manual run begins
- **THEN** `speedtest.state` is emitted with `state: starting` and the matching `trigger`

#### Scenario: Result carries all three measurements and its context
- **WHEN** a run completes successfully
- **THEN** `speedtest.state` is emitted with `state: done`, numeric `down_mbps`, `up_mbps`, `latency_ms`, and the measured `ssid` and `server_name`

#### Scenario: Card names the network and server
- **WHEN** a run completes and the card renders
- **THEN** the body shows the measured network and server, matching the approved mock, rather than a generic pointer to the panel

#### Scenario: Failure is a terminal event with a short reason
- **WHEN** a run fails, is rejected by the parser, or is abandoned by the watchdog
- **THEN** `speedtest.state` is emitted with `state: error` and a single-line reason, never a traceback

#### Scenario: Exactly one terminal event per run
- **WHEN** a run settles
- **THEN** exactly one of `done` or `error` is emitted for that run, never both

#### Scenario: Contract drift gate gates implementation
- **WHEN** the topic's keys or enums are not present in the pinned contract
- **THEN** the drift gate fails, naming the missing key, and implementation does not proceed

### Requirement: Single in-place progress card

The notification app SHALL render exactly one card per run and mutate it in place across the run's lifetime, matching the shipped wallpaper progress card. It SHALL NOT emit a notification per phase.

The card SHALL contain a four-step checklist — Test scheduled, Latency measured, Download measured, Upload measured — with the shipped marker treatment (pending `○`, active `·`, done `✓`, failed `!`). While the run is in flight the progress bar SHALL pulse (indeterminate); it SHALL NOT display a numeric percentage, because the underlying `speedtest-cli` invocation reports no intermediate progress and any percentage would be fabricated.

On success the card SHALL show the three measured values as separate Download / Upload / Ping cells, mirroring the panel's own row split, and the body SHALL name the connected network and test server for context.

#### Scenario: One card, mutated in place
- **WHEN** a run passes through starting and then done
- **THEN** a single card is created at the start and updated in place; no second card is pushed for the result

#### Scenario: Progress is indeterminate
- **WHEN** a run is in flight
- **THEN** the bar pulses and shows no percentage text

#### Scenario: Result mirrors the panel's split rows
- **WHEN** a run completes
- **THEN** the card shows Download, Upload, and Ping as three separate labelled cells with the measured values

#### Scenario: Steps reflect real progress
- **WHEN** a run is in flight
- **THEN** steps already passed are marked done, the current step is active, and later steps are pending

### Requirement: Failure is persistent, success is transient

A successful run's card SHALL auto-dismiss after the shipped wallpaper completion delay (5 s). A failed run's card SHALL persist until dismissed and SHALL render in the palette caution treatment already used by critical notification cards, matching the shipped `.notif-card.critical` styling.

A failure SHALL mark the step it stopped at as failed and SHALL state that the next interval will retry.

#### Scenario: Success clears itself
- **WHEN** a run completes successfully
- **THEN** the card auto-dismisses after the completion delay without user action

#### Scenario: Failure waits for the user
- **WHEN** a run fails
- **THEN** the card persists until dismissed, uses the caution treatment, and names the step it stopped at

### Requirement: Notification preference

`services/speedtest-service.ts` SHALL add a `notify_on_test: boolean` field to `SpeedTestConfig`, defaulting to `true`, persisted through the existing `wifi-speedtest.json` load/merge/save path so it survives restarts alongside the interval. An existing config file without the key SHALL load with the default.

The Wi-Fi panel SHALL render the preference as a row matching the shipped `run_on_connect` row: a `settings-stc-row` containing a `settings-stc-label` and a `WifiSwitch`, with the sub-label stating that a card appears per run in the notification stack.

When the preference is `false`, the run SHALL still execute and the panel SHALL still update; only the card is suppressed. The gate SHALL be evaluated in the producer before any event is emitted.

#### Scenario: Preference persists with the interval
- **WHEN** the preference is toggled and AGS restarts
- **THEN** `wifi-speedtest.json` contains `notify_on_test` and the toggle renders in the saved position

#### Scenario: Missing key loads the default
- **WHEN** an existing `wifi-speedtest.json` has no `notify_on_test` key
- **THEN** the preference loads as `true` and no write occurs until it is changed

#### Scenario: Off suppresses only the card
- **WHEN** the preference is `false` and a run completes
- **THEN** no `speedtest.state` event is emitted, the measurement is still stored, and the panel rows still update

#### Scenario: Row matches the shipped toggle pattern
- **WHEN** the Wi-Fi panel's Speed Test section is expanded
- **THEN** the preference appears as a labelled row with a `WifiSwitch`, consistent with the Auto-run on connect row

### Requirement: Mock/code parity is gated

`scripts/speedtest-mock-parity.py` SHALL gate the change. It SHALL behave as `scripts/wifi-mock-parity.py` does: every `class` token inside each anchored mock state SHALL either be mock-only scaffolding listed in an `ALLOWLIST` with a reason, or resolve to a class shipped in the notifications `style.css` or in that state's mapped TSX file — directly, or via a `CLASS_MAP` entry naming the shipped equivalent. Anything else SHALL fail loudly, naming the state and the token, and exit non-zero.

Every mapped TSX file and the stylesheet SHALL exist, or the gate SHALL fail naming the missing path. Mock-only scaffolding SHALL never be permitted to represent a shippable feature.

#### Scenario: Uncovered token fails the gate
- **WHEN** a mock state uses a class token with no shipped counterpart and no `CLASS_MAP` or `ALLOWLIST` entry
- **THEN** the gate exits non-zero, naming the state and the token

#### Scenario: Broken mapping fails the gate
- **WHEN** a `CLASS_MAP` entry names a shipped class that is absent from both the stylesheet and the mapped TSX
- **THEN** the gate exits non-zero rather than trusting the mapping

#### Scenario: Missing mapped file fails the gate
- **WHEN** a state's mapped TSX file does not exist
- **THEN** the gate exits non-zero naming the missing path

### Requirement: No new architecture beyond the existing seams

`scripts/speedtest-no-new-architecture.py` SHALL gate the change against architectural drift. It SHALL assert that:

- no `Notify` call and no non-zero `replaces_id` appears in the speed-test producer or consumer path
- no new AGS instance name is introduced (the instance list is compared against the pre-existing set)
- no second event-bus client is added to the notifications app beyond the `speedtest-events.ts` sibling of `wallpaper-events.ts`
- `speedtest-events.ts` contains no `GLib.timeout_add` polling loop — the subscribe-before-read shape only
- the speed-test path adds no new D-Bus interface or well-known name outside `org.dotfiles.Events`

#### Scenario: A Notify call is introduced
- **WHEN** the producer or consumer begins calling `org.freedesktop.Notifications.Notify` for speed tests
- **THEN** the gate exits non-zero, naming the offending file and line

#### Scenario: A polling loop is introduced
- **WHEN** `speedtest-events.ts` gains a `GLib.timeout_add` poll
- **THEN** the gate exits non-zero, naming the file

#### Scenario: Clean implementation passes
- **WHEN** the implementation reuses only the existing seams
- **THEN** the gate exits zero and reports the checks it performed
