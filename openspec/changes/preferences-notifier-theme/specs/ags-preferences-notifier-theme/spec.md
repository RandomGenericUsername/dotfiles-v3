# ags-preferences-notifier-theme (delta)

## ADDED Requirements

### Requirement: Preferences is a port with an injected source

Settings SHALL be read through `Preferences.get<T>(namespace, key, fallback):
ReadAccessor<T>`. The port SHALL take its file access through an **injected**
`PreferencesSource` seam (`read(namespace)` + `watch(namespace, onChange)`), so
the port module carries no `gi://` and no `ags`, and an absent file SHALL
degrade to the fallback rather than throw.

Source: spine **AD-12**; doc 101 §4.6.

#### Scenario: an absent file degrades to the fallback

- **WHEN** a key is read and the fake source returns no record for the namespace
- **THEN** the accessor reads the fallback

#### Scenario: a present value wins over the fallback

- **WHEN** the fake source returns `{ key: true }` and the fallback is `false`
- **THEN** the accessor reads `true`

#### Scenario: the module is pure

- **WHEN** `platform/preferences.ts` is imported by the pure test project
- **THEN** no module reachable from it imports `gi://*` or `ags`

### Requirement: The adapter owns the file and the monitor lifecycle

The Gio adapter SHALL own both the config file read and its `Gio.FileMonitor`,
holding each monitor in an adapter-owned map so it is **never** a module-scope
global and cannot be collected while the widget is live. A namespace SHALL be
watched at most once, and a monitor change SHALL re-read the namespace and update
every accessor derived from it.

Source: spine **AD-12** (the module-scope-monitor GC trap); doc 101 §4.6.

#### Scenario: a monitor change updates the accessor

- **WHEN** an accessor is read and the fake monitor then fires after the source
  record changes
- **THEN** the accessor reads the new value

#### Scenario: one watch per namespace

- **WHEN** two keys of the same namespace are read
- **THEN** the fake source records exactly one `watch` call for that namespace

### Requirement: The bar reads `bar_compact_controls` through the port

`bar/widgets/recording.tsx` SHALL read the capture-tool `bar_compact_controls`
setting through the `Preferences` port and SHALL NOT read the config file or
hold a `Gio.FileMonitor` itself. The rendered indicator SHALL be unchanged:
compact mode still swaps the bar buttons for the popup, and turning compact mode
off still closes the popup.

Source: spine **AD-12**; doc 101 §4.6, §13 step 7.

#### Scenario: the widget no longer owns the file or the monitor

- **WHEN** `bar/widgets/recording.tsx` is searched for the config path, the
  direct read, or `monitor_file`
- **THEN** none is present (they live in the adapter)

#### Scenario: leaving compact mode closes the popup

- **WHEN** the port reports compact mode has turned off while the popup is open
- **THEN** the popup is popped down

### Requirement: Notifier takes intents and the provider routes them

Senders SHALL post `NotificationIntent`s through `Notifier.post`; they SHALL NOT
construct a freedesktop call. The provider SHALL route a **transient** intent
(no `key`, no `progress`) to the freedesktop `notify` sink and a **keyed or
progress** intent to the `card` sink (the event-card path). `dismiss(key)` SHALL
reach the dismiss seam.

Source: spine **AD-11**; doc 101 §4.5.

#### Scenario: a transient intent goes to freedesktop

- **WHEN** an intent with no `key` and no `progress` is posted
- **THEN** the fake `notify` sink receives it and the fake `card` sink does not

#### Scenario: a keyed intent goes to the event-card path

- **WHEN** an intent carrying a `key` is posted
- **THEN** the fake `card` sink receives it and the fake `notify` sink does not

#### Scenario: a progress intent goes to the event-card path

- **WHEN** an intent carrying `progress` is posted
- **THEN** the fake `card` sink receives it and the fake `notify` sink does not

#### Scenario: dismiss reaches the dismiss seam

- **WHEN** `dismiss(key)` is called
- **THEN** the fake dismiss seam receives that key

### Requirement: The bar's freedesktop send is routed through the Notifier

`services/bluetooth-service.ts` SHALL post a transient `NotificationIntent`
through the `Notifier` and SHALL NOT construct the freedesktop `Notify` call.
The wire SHALL be unchanged: the same app name, icon, summary, body, and timeout
reach `org.freedesktop.Notifications`.

Source: spine **AD-11**; doc 101 §4.5, §13 step 7.

#### Scenario: the sender no longer knows the wire

- **WHEN** `services/bluetooth-service.ts` is searched for a freedesktop bus call
  (`Gio.bus_get_sync`) constructing `Notify`
- **THEN** none is present (the call lives in the adapter)

### Requirement: Theme is a port and the bar routes its palette through it

A `Theme` port SHALL apply the palette through an injected `CssSink`; the port
module SHALL carry no `gi://` and no `ags`. The bar SHALL apply its palette via
`theme.apply()` and SHALL NOT call `app.apply_css` for the palette directly. The
adapter SHALL apply the **stable** `colors.css` pointer, never a generation path
(F9), so a palette swap is not cached.

Source: spine **AD-13**; doc 101 §4 (no port was defined there); review F9.

#### Scenario: the bar no longer applies the palette directly

- **WHEN** `app.tsx` is searched for a direct `apply_css` of `colors.css`
- **THEN** it is absent (the palette application lives in the adapter)

#### Scenario: the palette is applied through the sink

- **WHEN** `theme.apply()` runs with a fake `CssSink`
- **THEN** the sink receives the stable palette path

### Requirement: New sources are registered for deployment

The six new sources SHALL be registered in `compositor_configs_skeleton_files`
and mirrored in the verify role, so a fresh provision deploys them.

Source: spine **AD-17** (per-file placement); `deploy-coverage` gate.

#### Scenario: deploy coverage is green

- **WHEN** `make deploy-coverage` runs
- **THEN** every AGS module reachable from `app.tsx` is registered, including the
  three platform ports and their three adapters
