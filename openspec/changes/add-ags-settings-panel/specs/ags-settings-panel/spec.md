## Purpose

The macOS-style settings panel invoked from the status bar: a shared-state AGS
window that toggles Wi-Fi and Bluetooth (icon = power), opens their in-place
lists, connects Wi-Fi (including password entry), connects/disconnects Bluetooth
devices, drives display brightness and volume (with a level-aware speaker glyph),
and launches `hyprmod` — styled with the GUI-family palette tokens and built so
future sections append without redesign.

## ADDED Requirements

### Requirement: Provisioned dependency gate

The panel's runtime implementation SHALL NOT begin until provisioning has
installed the Astal Bluetooth and WirePlumber bindings, installed and enabled
`bluez`, and ensured backlight control works for the user. The runtime SHALL NOT
install, detect, or bootstrap any dependency; it only consumes provisioned
capabilities.

#### Scenario: Bindings present before implementation
- **WHEN** the `packages` playbook converges and `verify` runs
- **THEN** the `AstalBluetooth` and `AstalWp` GIR namespaces resolve and
  `bluetooth.service` is enabled, so the panel can be built against them

#### Scenario: No runtime installation
- **WHEN** the AGS sources are inspected
- **THEN** they contain no package installation, download, or dependency
  provisioning — only GObject reads and control calls against provisioned services

### Requirement: Status-bar trigger and panel placement

The bar SHALL render a settings button using the `settings` icon group; clicking
it SHALL toggle the settings panel. The panel SHALL be a window in the existing
always-on bar AGS instance, anchored top-right under the bar on the primary
monitor only, and SHALL NOT reserve exclusive screen space.

#### Scenario: Bar icon toggles the panel
- **WHEN** the user clicks the bar settings icon
- **THEN** the panel opens; clicking it again closes the panel

#### Scenario: Primary monitor only
- **WHEN** the session has more than one monitor
- **THEN** exactly one panel exists, on the primary monitor, and the secondary
  monitor shows no panel

#### Scenario: Anchored under the bar
- **WHEN** the panel is visible
- **THEN** it floats over the wallpaper just below the bar, at the top-right,
  without pushing or resizing any other window

### Requirement: Icon is the power toggle; the row opens the list

For Wi-Fi and Bluetooth rows, the capability icon SHALL be the power toggle and
the row (label + chevron) SHALL open the corresponding subview. No separate
explicit switch control SHALL be rendered, and the icon SHALL NOT be wrapped in a
rounded container/box. The icon SHALL be a palette-tinted SVG from the icon
pipeline (not a CSS filter behind a shape): the enabled state renders the accent
variant and the disabled state renders a muted variant, and the rendered glyph
SHALL swap when the control is enabled/disabled.

#### Scenario: Icon toggles power
- **WHEN** the user clicks the Wi-Fi icon
- **THEN** the Wi-Fi radio toggles and the icon swaps to the matching state variant

#### Scenario: No container, pipeline-tinted
- **WHEN** the Wi-Fi or Bluetooth tile is inspected
- **THEN** no rounded background/border surrounds the glyph, and the glyph's
  color comes from its ITR-rendered variant (accent when on, muted when off)

#### Scenario: Row opens the list
- **WHEN** the user clicks the Wi-Fi or Bluetooth row label/chevron
- **THEN** the panel swaps in-place to that list with a back-arrow header

### Requirement: In-place subviews with back navigation

Wi-Fi and Bluetooth lists SHALL render inside the same panel as an in-place
swap, with a back-arrow header that returns to the main view; the panel
dimensions SHALL remain stable across views.

#### Scenario: Back returns to main
- **WHEN** the user activates the back arrow from a subview
- **THEN** the main view is shown and the panel has not changed size

### Requirement: Wi-Fi connect with password entry

The Wi-Fi subview SHALL list available networks (deduped, connected-first, with
secured/open and signal strength), and clicking a network SHALL connect to it
without leaving the panel. A secured network with no saved secret SHALL present
an inline password field with Cancel and Join; connecting SHALL go through the
provisioned NetworkManager CLI. Read state SHALL remain reactive via AstalNetwork.

#### Scenario: Open network connects directly
- **WHEN** the user clicks an open network
- **THEN** the panel connects to it and the row shows the connected state

#### Scenario: Secured network prompts for a password
- **WHEN** the user clicks a secured network without a saved secret
- **THEN** an inline password field appears with Cancel/Join, and Join connects

#### Scenario: Failed connect does not dump a traceback
- **WHEN** joining fails (wrong password or unreachable)
- **THEN** the password field remains and a short inline message is shown, not a
  raw error output

#### Scenario: Radio-off state is legible
- **WHEN** the Wi-Fi radio is off and the user opens the Wi-Fi subview
- **THEN** the list communicates that Wi-Fi is off rather than showing stale
  networks

### Requirement: Bluetooth connect and disconnect

The Bluetooth subview SHALL list devices (connected, paired, available) and
SHALL connect, disconnect, or pair on user action via the provisioned BlueZ
stack, with reactive state via AstalBluetooth.

#### Scenario: Connect a paired device
- **WHEN** the user activates Connect on a paired device
- **THEN** the device connects and its row shows the connected state

#### Scenario: Disconnect a connected device
- **WHEN** the user activates Disconnect on the connected device
- **THEN** the device disconnects and its row reflects that

### Requirement: Brightness slider

The Display card SHALL provide a slider that reads and writes display brightness
through the provisioned backlight tool, reflects external (Fn-key) changes while
the panel is open, and applies the user's change immediately.

#### Scenario: Slider writes brightness
- **WHEN** the user drags the Display slider
- **THEN** the screen brightness changes to the selected level

#### Scenario: External change reflected
- **WHEN** a Fn-key brightness change happens while the panel is open
- **THEN** the slider position updates to match within the refresh interval

### Requirement: Volume slider with level-aware glyph

The Sound card SHALL provide a slider bound to the default audio sink; the
leading speaker glyph SHALL change with the level — muted (0%), lowest (1–25%),
low (26–50%), medium (51–75%), max (76–100%) — resolved through the icon
registry, and clicking the glyph SHALL toggle mute.

#### Scenario: Glyph tracks level
- **WHEN** the volume is set to 40%
- **THEN** the speaker renders the `low` variant; at 0% it renders `muted`; at
  90% it renders `max`

#### Scenario: Glyph toggles mute
- **WHEN** the user clicks the speaker glyph
- **THEN** the sink mute state toggles and the glyph shows the muted level

### Requirement: Hyprmod launch

The Hyprmod tile SHALL be an action tile with no toggle state; activating it
SHALL run the provisioned `hyprmod` program.

#### Scenario: Tile launches hyprmod
- **WHEN** the user activates the Hyprmod tile
- **THEN** the `hyprmod` program is launched

### Requirement: Dismissal

The panel SHALL close on `Esc` and on a click outside the panel.

#### Scenario: Escape closes
- **WHEN** the panel is open and the user presses Escape
- **THEN** the panel closes and returns to the main view for the next open

#### Scenario: Click outside closes
- **WHEN** the panel is open and the user clicks anywhere outside it
- **THEN** the panel closes

### Requirement: Extensible section composition

The main view SHALL be composed from a stable section list and reusable
primitives (`PanelCard`, `CapabilityTile`, `IconToggle`, `LevelSlider`,
`NavHeader`) so a future section is an addition to the list and a new card,
without restructuring the panel.

#### Scenario: A new section appends
- **WHEN** a new capability card is added to the section list
- **THEN** it renders in the panel with the existing primitives and tokens, and
  no existing section requires modification
