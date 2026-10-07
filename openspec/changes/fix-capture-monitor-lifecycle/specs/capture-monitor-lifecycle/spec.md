## ADDED Requirements

### Requirement: The capture GUI SHALL react to monitors being connected and disconnected

After the capture GUI has started, a monitor being connected SHALL result in a
capture window for it, and a monitor being disconnected SHALL result in that
monitor's window being removed from the application and destroyed.

The signal subscribed SHALL be `Gio.ListModel::items-changed` on the model
returned by `Gdk.Display.get_monitors()`. `Gdk.Display` SHALL NOT be treated as
the source of monitor hotplug: on GTK 4.22 it has no `monitor-added` or
`monitor-removed` signal, and connecting to either raises
`No signal 'monitor-added' on object 'GdkWaylandDisplay'`.

Rationale: `app.tsx` read `app.get_monitors()` once inside `main()` and looped,
so a monitor attached after login got no window at all and an unplugged monitor
left its window alive and still resolvable by name.

#### Scenario: A monitor is connected after the GUI has started
- **WHEN** a monitor that was not present at startup appears
- **THEN** a capture window is built for it and added to the application
- **AND** the number of windows named `capture-window` grows by exactly one

#### Scenario: A monitor is disconnected
- **WHEN** a monitor that had a window is removed
- **THEN** its window is removed from the application's window list AND destroyed
- **AND** the number of windows named `capture-window` falls by exactly one
- **AND** the surviving windows are unaffected

#### Scenario: Removal order is unregister-then-destroy
- **WHEN** a monitor's window is removed
- **THEN** it is removed from the application's window list BEFORE it is destroyed
- **RATIONALE** a destroyed window left in that list is one the launcher can
  still resolve by name, so a later `ags toggle` would act on a dead object

#### Scenario: Hiding is not removal
- **WHEN** a monitor's window is removed
- **THEN** the window is `destroy()`ed, not merely made invisible
- **RATIONALE** `visible = false` only unmaps; the `Gtk.Widget`, its subtree, its
  `Gtk.EventController` and its layer-shell surface all stay alive

#### Scenario: A repeated or duplicate change notification is a no-op
- **WHEN** the same monitor set is reconciled more than once, with no change
- **THEN** no window is created and no window is destroyed

#### Scenario: A resolution change does not rebuild the window
- **WHEN** a monitor's geometry changes while it remains connected
- **THEN** its window is neither rebuilt nor destroyed

#### Scenario: Monitor changes arriving before the first reconcile are not lost
- **WHEN** the change subscription is established before the initial window build
- **THEN** a monitor change occurring between the two is still reconciled

### Requirement: Monitor change handling SHALL be a diff, not an application of the notification payload

The `items-changed` payload describes a **range**, not a set of additions
(`removed != added` shifts the position of every later item), and
`Gdk.Monitor::invalidate` is a second signal describing the same disconnect. The
handler SHALL therefore re-read the monitor list and reconcile against the full
set, and SHALL NOT apply `(position, removed, added)` incrementally.

#### Scenario: One unplug delivers two notifications
- **WHEN** `items-changed` and `Monitor::invalidate` both fire for one disconnect
- **THEN** exactly one window is destroyed

#### Scenario: One notification describes several changes
- **WHEN** a single notification adds or removes several monitors at once
- **THEN** the resulting window set matches the resulting monitor set

### Requirement: The launcher SHALL open the focused monitor's window

The provisioned launcher runs `ags toggle capture-window -i capture`. Because
every monitor's window deliberately shares the name `capture-window`, which one
that reaches SHALL be the window of the monitor the user is on. When the focused
monitor cannot be determined, the window chosen SHALL be the first in this
application's own registration order, and SHALL be the same one on every
invocation.

#### Scenario: Focus is on the second monitor
- **WHEN** the focused monitor is the second of two, and the launcher toggles
- **THEN** the second monitor's window is the one shown
- **AND** the first monitor's window is left exactly as it was found

#### Scenario: The resolved window is not decided by GTK's window list order
- **WHEN** the focused monitor changes
- **THEN** the resolved window changes with it, for every focused monitor
- **RATIONALE** `App.get_window` is `windows.find(...)`, so which duplicate is
  reached is decided purely by list position. Measured on GTK 4.22.5, GTK's list
  is the reverse of registration and does not move on map, unmap or present, so
  it is stably the last monitor added and never the focused one

#### Scenario: Focus cannot be determined
- **WHEN** no focus source is available, or focus is on a monitor with no window
- **THEN** the first window in registration order is chosen
- **AND** the same window is chosen on every subsequent invocation

#### Scenario: A name this application does not own is still resolved
- **WHEN** `get_window` is called with a name no owned window carries
- **THEN** the original lookup is used, so `ags toggle` on any other window is
  unaffected

#### Scenario: No override is stacked
- **WHEN** the lookup is installed more than once
- **THEN** the behaviour is unchanged

### Requirement: The window name and its consumers SHALL be unchanged

Every monitor's window SHALL keep the name `capture-window`. `style.css` SHALL
continue to select it with `window#capture-window`, and
`capture-ui.j2` SHALL continue to toggle `capture-window` on instance `capture`.

Rationale: `window#capture-window` is a GTK **id** selector, which matches the
widget NAME rather than a class, so a per-monitor rename drops the surface
styling onto nothing and revives a documented first-frame rectangle. The
launcher line is pinned verbatim by an existing test, so changing it would
weaken that test and would additionally require a provisioning run on every host.

#### Scenario: A monitor is added without any rename
- **WHEN** a window is built for a newly connected monitor
- **THEN** its name is `capture-window`, identical to every other monitor's

#### Scenario: The stylesheet still selects the window
- **WHEN** `style.css` is read
- **THEN** it contains `window#capture-window`

#### Scenario: The provisioned launcher is unchanged
- **WHEN** `capture-ui.j2` is read
- **THEN** it contains `ags toggle "$WINDOW" -i "$INSTANCE"` with
  `WINDOW="capture-window"` and `INSTANCE="capture"`

#### Scenario: The keybind works with no provisioning run
- **WHEN** the change is applied to an existing host
- **THEN** SUPER+PRINT opens the panel on the focused monitor with no
  provisioning step required

### Requirement: The focused monitor SHALL come from a source that can answer, and its absence SHALL be survivable

The GTK toolkit on this stack SHALL NOT be used to determine the focused monitor:
`Gdk.Seat.get_focus`, `Gdk.Device.get_position`,
`Gdk.Display.get_monitor_at_window` and `Gdk.Display.get_monitor_at_point` do not
exist, and `Gdk.Device.get_surface_at_position()` reports `(NULL, 0, 0)` whenever
the pointer is over another client's surface. Focus SHALL come from a port, so
that a host with no such source degrades instead of failing.

#### Scenario: A compositor focus source is present
- **WHEN** the platform can name the focused monitor
- **THEN** it is matched against the monitors the GUI knows about, by connector
- **AND** the monitor's window is the one the launcher reaches

#### Scenario: No focus source is present
- **WHEN** the focus source cannot be loaded
- **THEN** the application still starts and the panel still opens
- **AND** the window chosen is the first in registration order

#### Scenario: Focus names a monitor the GUI has no window for
- **WHEN** focus is reported for a monitor outside the known set
- **THEN** no window is preferred, and the deterministic fallback applies

### Requirement: The monitor decisions SHALL be pure and independently testable

The decisions — which windows a monitor change means, which window a name lookup
should reach first, how a monitor is identified — SHALL live in the domain layer
with no GTK, GLib, `ags/*` or subprocess dependency, so they can be executed by
`node --test`. Reading monitors, subscribing to changes, creating and destroying
windows, and replacing the launcher lookup SHALL live in adapters.

#### Scenario: The domain module is pure
- **WHEN** `domain/` and `ports/` are scanned
- **THEN** neither imports `ags/*` nor `gi://*`

#### Scenario: The decisions are executed, not asserted about
- **WHEN** the capture unit tests run
- **THEN** `planSync`, `orderedForFocus`, `focusKey` and `monitorKey` are
  imported from the real domain module and executed

#### Scenario: The app has no decision logic
- **WHEN** `app.tsx` is read
- **THEN** it constructs the adapters and hands them over, and contains no
  per-monitor window loop