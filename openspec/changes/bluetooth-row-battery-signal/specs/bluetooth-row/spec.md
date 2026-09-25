## ADDED Requirements

### Requirement: Two-line row layout pinned to the approved mock

The Bluetooth device row SHALL render exactly two lines: line 1 = device name
plus (when connected) the `Connected` badge; line 2 =
`justify-content: space-between` with the stacked meta block on the left and
the action buttons (`valign=CENTER`) on the right. The rendered row SHALL
match `mockups/bluetooth-row-final.html` (the owner-approved contract) — no
drift in line order, badge placement, meta stacking, or action placement.

#### Scenario: connected device renders the approved structure

- **GIVEN** a connected device `TOZO NC9` reporting battery `100` and
  `rssi = -65`
- **WHEN** the Bluetooth view renders the row
- **THEN** line 1 shows the ellipsized name followed by the `Connected` badge
- **AND** line 2 left block stacks `[battery glyph] 100%` above
  `[signal glyph] −65 dBm`
- **AND** line 2 right block holds the `Disconnect` and `Unpair` buttons,
  vertically centered against the meta block

#### Scenario: disconnected device keeps the same geometry

- **GIVEN** a paired, in-range, disconnected device
- **WHEN** the row renders
- **THEN** the `Connected` badge is hidden and the action button reads
  `Connect`, with line 2 still split left-meta / right-actions

### Requirement: Device name truncates instead of overflowing

The name label SHALL set `maxWidthChars` with `Pango.EllipsizeMode.END`
(shipping precedent: `.audio-routing`), and SHALL expose the full name as its
tooltip. For any device name the row SHALL remain within the 312px panel
width with no right-edge clipping of the badge or action buttons.

#### Scenario: a long device name is ellipsized

- **GIVEN** a device whose alias is longer than the available name cell
- **WHEN** the row renders
- **THEN** the name ends in an ellipsis
- **AND** the badge and both action buttons remain fully visible inside the
  panel's right edge
- **AND** the label tooltip shows the untruncated alias

### Requirement: Battery and signal lines follow their visibility gates

The battery line SHALL render ONLY when the device is connected AND reports
a battery level greater than 0 (BlueZ battery can be stale after disconnect).
The signal line SHALL render ONLY when `rssi` is a negative value (BlueZ
reports `0`/non-negative when the device has never been seen, and drops RSSI
for connected classic headsets). When `absent()` holds, the meta block SHALL
render exactly one line: `Not in range`. Neither line may render an empty or
placeholder value.

#### Scenario: battery unknown hides the battery line

- **GIVEN** a connected device with `battery = 0`
- **WHEN** the row renders
- **THEN** only the signal line shows, left-aligned as before

#### Scenario: RSSI never reported hides the signal line

- **GIVEN** a connected device with `battery = 100` and `rssi = 0`
- **WHEN** the row renders
- **THEN** the meta block contains only the battery line

#### Scenario: Absent device renders only Not in range

- **GIVEN** a paired, disconnected device with `rssi = 0` and a stale battery
  of `80`
- **WHEN** the row renders
- **THEN** the meta block contains exactly the `Not in range` line (no
  battery, no signal)
- **AND** the row is dimmed

#### Scenario: Connected device without RSSI shows battery only

- **GIVEN** a connected device with battery `100` and no RSSI reported
  (`rssi = 0`)
- **WHEN** the row renders
- **THEN** the meta block shows the battery line only

### Requirement: All displayed values come from the service model

The component SHALL derive battery percent and dBm text from the
`bluetooth-service` device fields (`battery`, `rssi`) and SHALL NOT contain
hardcoded percentage or dBm literals. RSSI SHALL map to a signal variant by
the fixed thresholds `≥ −60 → high`, `≥ −70 → good`, `≥ −80 → medium`,
otherwise `low`; the battery level SHALL bucket as the bar does
(`<25 → 0`, `<50 → 25`, `<75 → 50`, `<100 → 75`, else `100`).

#### Scenario: live values change when the service updates

- **GIVEN** a row rendering a device at battery `100` / `rssi = -65`
- **WHEN** the service updates the same device to battery `42` /
  `rssi = -85`
- **THEN** the row shows `42%` and the `low` signal glyph with `−85 dBm`
  without a rebuild

#### Scenario: thresholds select the expected glyph

- **GIVEN** devices reporting `rssi` of `-55`, `-65`, `-75`, and `-95`
- **WHEN** each row renders
- **THEN** the signal glyphs resolve to `settings-panel-signal-high`,
  `-good`, `-medium`, and `-low` respectively

### Requirement: Panel icons resolve guard-exempt outputs

The row SHALL resolve battery glyphs from the `battery` group's
`system-battery-{0,25,50,75,100}` variants (variant-level
`COLOR_FOREGROUND: foreground` pin) and signal glyphs from the
`settings-panel` group's `signal-{low,medium,good,high}` variants. It SHALL
NOT resolve bare `battery-*` variants, which remain reserved for the status
bar.

#### Scenario: light wallpaper leaves panel glyphs untouched

- **GIVEN** a light wallpaper that flips the `battery` group's
  `COLOR_FOREGROUND` for the bar
- **WHEN** icons are regenerated
- **THEN** `battery-100.svg` contains the guard-picked dark hex
- **AND** `system-battery-100.svg` and `settings-panel-signal-good.svg`
  contain the palette `foreground` hex unchanged

#### Scenario: status bar battery behavior is unchanged

- **GIVEN** the status bar battery widget
- **WHEN** icons are regenerated on any wallpaper
- **THEN** it still resolves bare `battery-*` outputs through
  `bar_mappings.states`, byte-identical to before this change
