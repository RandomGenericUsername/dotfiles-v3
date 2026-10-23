# bluetooth-bar-popup

Acceptance criteria restated from the owner-approved mock
(`mockups/panel.html`). Mock state → requirement mapping is one-to-one; where a
scenario names a mock caption, that caption is the visual contract.

## ADDED Requirements

### Requirement: Bluetooth is reachable from the status bar and from the settings panel

The Bluetooth capability SHALL be reachable from **two** independent entry
points, matching Wi-Fi: a status-bar indicator whose primary click opens the
popup, and a settings-panel tile whose row opens the subview. Both SHALL render
the same `BluetoothContent` body; neither SHALL be the only route to the
capability.

The bar indicator SHALL resolve its glyph through
`registry.getBarMappings("bluetooth").states[stateKey]` →
`registry.resolve("bluetooth", variant)` — the exact resolution path
`bar/widgets/network.tsx` uses for `network`. It SHALL NOT read the icon
manifest directly or hard-code a path.

#### Scenario: the bar indicator opens the popup under its own icon

- **GIVEN** the Bluetooth bar indicator is visible
- **WHEN** the user primary-clicks it
- **THEN** the popup becomes visible
- **AND** the popup's left margin places it centred beneath the icon's x
- **AND** a second primary-click on the same spot closes it

#### Scenario: the settings tile still opens the subview

- **GIVEN** the settings panel main view is open
- **WHEN** the user clicks the Bluetooth tile row (not its power glyph)
- **THEN** the Bluetooth subview opens
- **AND** the same device list the popup shows is visible

### Requirement: The bar glyph is drawn from a guard-managed group with art-distinguished states

The `bluetooth` icon group SHALL declare `COLOR_FOREGROUND` at **group level
only**, with no variant-level `color_mappings`, and SHALL be listed in
`BAR_GROUPS` in `src/runtime/src/runtime/domain/icon_contrast.py`. The `on` and
`off` states SHALL be distinguished by the glyph's **shape** — `off` carries a
slash — never by opacity or by a tint alone.

A variant-level pin on a bar glyph would structurally exempt it from the
contrast guard, which is the opposite of what a glyph floating over the
wallpaper requires.

#### Scenario: the two bar states are visually distinct without colour

- **GIVEN** the Bluetooth bar indicator
- **WHEN** the adapter is powered on, then powered off
- **THEN** the indicator switches between the `bluetooth-on` and
  `bluetooth-off` variants
- **AND** the off glyph is recognisable by its slash alone, in greyscale, at
  24px

#### Scenario: bar state keys survive YAML parsing

- **GIVEN** `bar_mappings.states` in `icons.yaml`
- **WHEN** the manifest is parsed
- **THEN** every state key is a string
- **AND** no key is a YAML boolean (`on`, `off`, `yes`, `no` resolve to
  booleans under YAML 1.1 and would make every bar lookup miss)

### Requirement: Device rows lead with the circle-badged signal glyph at the Wi-Fi size

Every device row that can report a signal SHALL lead with
`settings-panel/bluetooth-signal-{full,good,medium,low}` at **30px**,
matching `.settings-net-signal` (`style.css` `min-width/min-height: 30px`) and
`WifiContent`'s `pixel_size={30}`. Variant selection SHALL use the existing
thresholds: `rssi >= -60` → `full`, `>= -70` → `good`, `>= -80` → `medium`,
else `low`. The panel SHALL NOT resolve the bare `signal-*` variants for this
slot, and SHALL NOT resolve any bar-only `battery-*` variant.

The row SHALL render **no** signal glyph when `rssi >= 0` (BlueZ's "not seen").

#### Scenario: a connected in-range device leads with the circle glyph

- **GIVEN** a connected device with `rssi = -52`
- **WHEN** the row renders
- **THEN** the leading glyph is `bluetooth-signal-full`
- **AND** the glyph occupies a 30px box, identical to a Wi-Fi network row

#### Scenario: an unseen device has no signal glyph at all

- **GIVEN** a paired device with `rssi = 0`
- **WHEN** the row renders
- **THEN** no signal glyph is drawn
- **AND** no signal tooltip exists on the row

### Requirement: Row subtitles carry words, never strength numbers

The row's subtitle SHALL be a word — `Not in range`, `Paired`, or
`Ready to pair` — and SHALL NOT contain a dBm figure, matching `WifiRow`'s
`Saved` / `Secured` / `Open network`. The exact `rssi` value SHALL remain
available on the leading signal glyph's tooltip, so nothing is lost. Because a
`rssi >= 0` row has neither glyph nor tooltip, the word layer SHALL NOT be
removed under any circumstance.

#### Scenario: the number is reachable but not printed

- **GIVEN** a connected device with `rssi = -52`
- **WHEN** the row renders and the user hovers the signal glyph
- **THEN** the row's own text contains no `dBm`
- **AND** the glyph tooltip reports the exact reading

#### Scenario: the out-of-range state survives losing the number

- **GIVEN** a paired device with `rssi = 0`, not connected
- **WHEN** the row renders
- **THEN** the subtitle reads `Not in range`
- **AND** this word is the only channel carrying the state besides the row's
  reduced opacity and the insensitive `Connect` button

### Requirement: The popup matches the Wi-Fi popup's window geometry

`BluetoothPopup` SHALL mirror `WifiPopup` property for property: 312px
`settings-surface`; `anchor={TOP|LEFT}`; `exclusivity=IGNORE`;
`layer=OVERLAY`; `marginTop={52}`; follower `marginLeft` clamped to
`[8, monitorWidth - 320]`; `Keymode.NONE`. Its scrolledwindow SHALL set
`propagateNaturalWidth={false}` and `maxContentHeight={420}`.

`exclusivity` MUST be `IGNORE`: `NORMAL` makes Hyprland offset the overlay below
the bar's reserved zone and then apply `marginTop`, pushing the popup far too
low.

#### Scenario: a long device name cannot grow the surface

- **GIVEN** a device alias longer than the name cell
- **WHEN** the popup renders
- **THEN** the surface stays 312px wide
- **AND** the name ends in an ellipsis with the full alias in its tooltip
- **AND** the badge and both action buttons remain inside the right edge

### Requirement: The header is a pinned sibling of the scrolled area on both surfaces

The Bluetooth popup and the settings subview SHALL each render the power
control in the trailing slot of a `settings-nav-header` placed as a **sibling**
of the scrolledwindow, never as a child. The control SHALL be a `Gtk.Switch`
matching the Wi-Fi header, on **both** surfaces.

`BluetoothToggle` SHALL be retained on the main-view tile only. It is a
`Gtk.Button`, so its `clicked` signal fires only on genuine user activation and
it carries none of the `notify::active` self-oscillation hazard `WifiSwitch`
exists to defeat — which is also why it is not interchangeable with the
header switch.

#### Scenario: the subview header now carries a switch

- **GIVEN** the Bluetooth settings subview
- **WHEN** it renders
- **THEN** the header shows a `Gtk.Switch` in the trailing slot, not a bare
  22px glyph
- **AND** the header does not scroll away with the content

#### Scenario: the switch forwards an explicit value

- **GIVEN** the header switch is toggled
- **WHEN** the backend subsequently echoes the new state
- **THEN** no second write is issued (the switch suppresses backend echoes)
- **AND** an independent toggle from the other surface cannot oscillate

### Requirement: Every power control forwards an explicit value, never a blind toggle

Both the header switch and the tile glyph SHALL call
`setBluetoothPowered(enabled: boolean)` with an explicit value. Neither SHALL
use a read-modify-write toggle, because two surfaces now mount a power control
and a stale read is a real way to write the wrong value.

#### Scenario: a rapid double interaction cannot invert the radio

- **GIVEN** the popup header switch and the settings tile both mounted
- **WHEN** both are toggled within the same frame
- **THEN** the adapter ends in the state each interaction requested
- **AND** no self-oscillation occurs

### Requirement: Bluetooth power control keeps the keyboard it does not need

The popup SHALL set `Keymode.NONE`. It SHALL NOT widen the keymode
unconditionally. Bluetooth has no typed-input surface — the shipped pairing
agent is `NoInputNoOutput` (Just Works) — so there is no `Gtk.Entry` to widen
for, and unlike Wi-Fi there is no password prompt.

If a PIN/passkey field is ever added, the keymode SHALL become `ON_DEMAND`
only while that field is on screen.

#### Scenario: the popup does not steal bar clicks

- **GIVEN** the popup is open with no text field on screen
- **WHEN** the user clicks the bar icon again
- **THEN** the popup collapses
- **AND** the bar did not swallow the click

### Requirement: The popup dismisses via the catcher and the global close request

A full-screen `BluetoothPopupCatcher` SHALL be registered in `app.tsx`
**immediately before** the popup so the popup stacks above it, and
click-outside SHALL close the popup. `app.tsx`'s `popup-close` request handler
SHALL call `closeBluetoothPopup()` alongside `closeSettings()` and
`closeAudio()`, so the global Escape keybind dismisses whichever popup is open.

Mutual exclusion SHALL be coordinated by callers, not by the state module, and
`components/bluetooth/state.ts` SHALL import nothing from `settings-panel/**`.

#### Scenario: opening the settings panel closes the Bluetooth popup

- **GIVEN** the Bluetooth popup is open
- **WHEN** the user opens the settings panel
- **THEN** the Bluetooth popup is closed

### Requirement: Device actions are driven by the whole row

The entire row SHALL be the primary action target via a row-level
`Gtk.GestureClick`, with the action button claiming its own click first.
`act()` SHALL no-op while busy or out of range; disconnect when connected,
connect when paired, pair otherwise. Action labels SHALL be `Pair`,
`Connect` and `Disconnect`, and while an action is in flight the button SHALL be
replaced by a spinner plus `<Action>ing…`.

BlueZ is single-flight (`runAction` returns early when
`bluetoothBusy().address !== null`), so every other row's primary action SHALL
go insensitive while one is busy, and `Unpair` SHALL be hidden entirely.

#### Scenario: a paired idle device reports no battery

- **GIVEN** a paired, in-range, disconnected device reporting a battery
  percentage
- **WHEN** the row renders
- **THEN** no battery stat is shown
- **AND** only `Connect` and `Unpair` are offered

A paired-but-idle device's `Battery1` reading is stale; showing it would be a
lie.

#### Scenario: one busy row disables the others

- **GIVEN** two paired devices and one pairing in progress
- **WHEN** the list renders
- **THEN** the busy row shows a spinner and `Pairing…`
- **AND** the other row's primary action is insensitive
- **AND** `Unpair` is absent from both rows

### Requirement: Unpair is confirmed inline without reflowing the row

Clicking `Unpair` SHALL replace the row's meta stack with the single line
`Remove from paired devices` and swap the action pair to `Keep` /
`Unpair device`. The row SHALL NOT resize or reflow: same two-line geometry, so
a confirm never moves anything. `Unpair device` SHALL use the one new class
this change introduces, `.settings-rowact.danger`. Opening a confirm on one row
SHALL close any other open confirm, and click-outside or Escape SHALL dismiss
an open confirm **before** the surface closes.

#### Scenario: the confirm keeps the row's height

- **GIVEN** a paired device row
- **WHEN** the user clicks `Unpair`
- **THEN** the action pair becomes `Keep` / `Unpair device`
- **AND** the row's height is unchanged
- **AND** the row above it has not moved

#### Scenario: the safe path costs the same to change your mind

- **GIVEN** an open unpair confirm
- **WHEN** the user clicks `Keep`
- **THEN** the row returns to its normal actions and nothing else changed

### Requirement: Exactly two new CSS classes are introduced

The change SHALL add exactly two classes to `style.css` —
`.settings-rowact.danger` (the destructive confirm action) and
`.settings-net.confirming` (the inline-confirm row wash) — and SHALL NOT add any
other. Every other element SHALL resolve to an existing `settings-*` class already
shipped by the settings panel or the Wi-Fi popup. Any further new class proposed
during implementation SHALL be a spec change, not an implementation detail.

**Amended from one class to two.** The mock shows a faint wash on the confirming
row, and the mock is the contract. That wash is not decoration: the confirm
requirement forbids the row from reflowing, so a mode change that could only be
signalled by layout is not available, and the background is what carries it
visually. Declaring the class but shipping no selector would have made the code
render something the approved mock does not show — which is exactly the
mock/code divergence `bluetooth-mock-parity` exists to catch. `.confirming` is
declared after `.settings-net.sel` so it wins over the connected fill: a
confirming row is a different *mode*, not a different *connection state*.

#### Scenario: the harness proves no class was invented

- **GIVEN** the implemented Bluetooth surfaces
- **WHEN** `make bluetooth-mock-parity` runs
- **THEN** every class token in every anchored mock state resolves to
  `style.css`, to the state's mapped TSX file, or to an explicit allowlist
  entry
- **AND** zero tokens are uncovered
- **AND** zero known gaps remain

### Requirement: The adapter detail row shows the machine's own adapter address

While powered on, the popup SHALL render an `Adapter` detail row from
`bluetoothAdapterAddress`. This is the local controller's hardware address
(BlueZ `Adapter1.Address`), not any device's. The row SHALL render `—` when the
address is unavailable and SHALL be hidden entirely while powered off.

The popup SHALL NOT render an audio-output row: PipeWire routing state inside a
Bluetooth surface mixes concerns.

#### Scenario: powering off hides the adapter row

- **GIVEN** the popup is open and the adapter is powered on
- **WHEN** the user powers Bluetooth off
- **THEN** the `Adapter` row is hidden
- **AND** the body collapses to the single line `Bluetooth is off`

### Requirement: Audio routing failures are recorded rather than silent

`routeAudioToDevice` SHALL record the endpoint it actually defaulted into
`bluetoothAudioTarget`, and `null` when its bounded retry window expires. The
service SHALL expose it; the popup SHALL NOT display it. It exists so the
failure is observable in state rather than vanishing — today a device can read
`Connected` while the sound stays on the speakers with nothing to indicate which
half of the chain failed.

#### Scenario: routing exhaustion is recorded

- **GIVEN** `routeAudioToDevice` finds no matching endpoint within its window
- **WHEN** it returns
- **THEN** `bluetoothAudioTarget()` is `null`
- **AND** no exception or user-facing toast is raised

### Requirement: Discovery is tied to surface visibility and reference-counted

Discovery SHALL start and stop from a `visible`-scoped effect in
`BluetoothContent`, gated on the radio being powered, exactly as shipped.
`startBluetoothDiscovery` and `stopBluetoothDiscovery` SHALL be
reference-counted in the service: `start` increments, `stop` decrements, and
`StopDiscovery` SHALL be issued only when the count reaches zero.

The settings panel keeps all three views mounted and toggles `visible`, so
without counting, a popup close racing a panel open can stop a scan the subview
just started.

#### Scenario: a hidden surface issues no scan

- **GIVEN** the popup is closed and the subview is not visible
- **WHEN** the service is idle
- **THEN** no discovery is running

#### Scenario: two visible surfaces share one scan

- **GIVEN** the popup and the settings subview are both visible
- **WHEN** one of them hides
- **THEN** discovery continues for the other
- **AND** `StopDiscovery` is issued only after both have hidden

### Requirement: No new class token appears in the popup besides the allowlisted one

The popup body SHALL use only `settings-*` classes already present in
`style.css` or the mapped TSX files. Mock-only scaffolding (page chrome, zoom
control, captions) is confined to the mock and never shipped.

#### Scenario: the shipped popup carries no mock-only class

- **GIVEN** the Bluetooth popup is rendered from the shipped TSX and `style.css`
- **WHEN** its class tokens are compared with the allowlisted `settings-*` set
- **THEN** no mock-only class (page chrome, zoom control, caption) appears

### Requirement: The pairing watchdog is surfaced without a timer in the view

While an action is in flight the row SHALL show a spinner and a **static**
`Can take up to 30 s` line. It SHALL NOT render a countdown: a countdown
requires a timer in the view, which the architecture forbids. The watchdog
itself stays in the service, bounded and self-cancelling.

#### Scenario: a hung BlueZ call surfaces as text

- **GIVEN** the 30s watchdog fires during pairing
- **WHEN** the failure line renders
- **THEN** it reads the service's string verbatim, `Pairing timed out`
- **AND** the row's action returns to `Pair`

#### Scenario: no timer exists in the view

- **GIVEN** the implemented `BluetoothContent`
- **WHEN** inspected
- **THEN** it contains no interval or timeout registration

### Requirement: Failure copy is the service's string, verbatim

The failure line SHALL render `bluetoothFailure()` unmodified — including
`Pairing timed out`, `Could not turn Bluetooth on (adapter may be soft-blocked)`
and `No Bluetooth adapter available`. It SHALL NOT be reworded or prefixed with
`Error:`. An absent adapter SHALL additionally show the
`settings-panel/info-caution` glyph and make the header switch insensitive.

#### Scenario: a service failure is shown verbatim

- **GIVEN** `bluetoothFailure()` returns `Pairing timed out`
- **WHEN** the popup renders the failure line
- **THEN** the text is exactly `Pairing timed out`, with no `Error:` prefix or rewording

### Requirement: Blueman is provisioned, mapped per distro, and not autostarted

`blueman` SHALL be declared in `dotfiles/provisioning/packages.yaml` and mapped
in **both** `group_vars/arch.yml` and `group_vars/debian-family.yml`; an
unmapped logical entry would be silently skipped by the packages role. It SHALL
NOT be autostarted: its tray applet would occupy a bar slot and own a second
agent role for a GUI the user only opens deliberately.

The `Bluetooth Settings` row SHALL launch `blueman-manager`. It SHALL NOT
launch `bluetoothctl`, which is a terminal TUI.

Blueman is what makes a PIN/passkey pairing completable at all: the panel's own
agent registers `NoInputNoOutput` and cannot answer `RequestPinCode` or
`RequestPasskey`.

#### Scenario: a missing adapter degrades honestly

- **GIVEN** no `Adapter1` object on the bus
- **WHEN** the panel opens
- **THEN** the header switch is insensitive
- **AND** the body shows `No Bluetooth adapter available` with the caution glyph
- **AND** nothing crashes

#### Scenario: the settings row opens a GUI, not a terminal

- **GIVEN** the `Bluetooth Settings` row
- **WHEN** the user clicks it
- **THEN** `blueman-manager` is launched
- **AND** a spawn failure surfaces in the existing failure line, never a dialog

### Requirement: The Blueman tray applet is kept out of the bar

The Blueman StatusNotifier item SHALL NOT be rendered by the AGS tray. Two
layers, in order of effect:

1. A user-level autostart override SHALL disable `blueman-applet`, so the tray
   item is never created. This survives package upgrades, unlike editing
   `/etc/xdg/autostart`.
2. AGS SHALL filter any Bluetooth StatusNotifier item from the tray, alongside
   the existing `isNetworkItem` exclusion, as a guard in case another process
   registers one.

#### Scenario: the bar shows the AGS indicator, not an applet icon

- **GIVEN** a login session with `blueman` installed
- **WHEN** the bar renders
- **THEN** exactly one Bluetooth affordance is present, the AGS bar indicator
- **AND** no `blueman-applet` tray item appears in the tray

### Requirement: No hub topic is introduced

This change SHALL NOT add a `bluetooth.state` topic, and SHALL leave
`contracts/event-contract.json`, `contracts/event-contract.xml`,
`hub.KNOWN_TOPICS`, `emit_validation.SCHEMAS`, `lib/event-bus-core.ts` and
`lib/event-bus.ts` unchanged. BlueZ is already bound losslessly in-process; a
topic would create a second source of truth for the same fact and, to stay
truthful on RSSI, would publish on every received advertisement frame.

#### Scenario: the contract is untouched

- **GIVEN** this change merged
- **WHEN** the contract conformance gates run
- **THEN** no new topic, payload schema or enum is present in either contract
  file
- **AND** `make contracts-check` passes unchanged
