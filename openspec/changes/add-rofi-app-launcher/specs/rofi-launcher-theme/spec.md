## ADDED Requirements

### Requirement: launcher config is a static authored skeleton
`dotfiles/config/rofi/launcher/config.rasi` SHALL exist in the repo as a plain rasi file (no `.j2`/`.tpl` suffix) and SHALL be placed into the spine by the compositor_configs role.

#### Scenario: the skeleton file exists and is static
- **WHEN** the repo is inspected
- **THEN** `dotfiles/config/rofi/launcher/config.rasi` exists
- **AND** its suffix is `.rasi` (not `.j2`/`.tpl`)
- **AND** it contains no Jinja `{{ }}` sequences (it is not templated)

#### Scenario: the file is placed in the spine
- **WHEN** the compositor_configs role runs
- **THEN** `<install>/config/rofi/launcher/config.rasi` exists with the authored content
- **AND** the placement is repo-authoritative (`force: true`)

### Requirement: launcher uses drun mode with the runtime palette
The launcher SHALL run rofi in `drun` mode and SHALL source all visible colors from the imported palette (`@import "../colors.rasi"`), not from hardcoded hex values. The structure/geometry matches the measured reference; the colors follow the runtime theme.

#### Scenario: drun mode configured
- **WHEN** `launcher/config.rasi` is loaded
- **THEN** `configuration.modes` is `"drun"`
- **AND** the file contains `@import "../colors.rasi"`

#### Scenario: palette drives the visible theme
- **WHEN** the launcher is open
- **THEN** the panel background, border, dark ring, search bar, element rows, selected row, and text resolve from palette variables (`@background`, `@foreground`, `@color01`, `@color04`, `@color10`, `@color07`) as defined in the imported rasi
- **AND** no visible color is a literal hex constant in the theme block
- **AND** the window background outside the border is not painted (`transparency: "real"`); no `rgba(@var, N%)` is used anywhere (unsupported by rofi 2.0)

### Requirement: panel-sized transparent window, centered, no compositor rules
The launcher window SHALL be a layer-shell overlay sized to the panel only (548px wide incl. border), perfectly centered on screen, floating over the live wallpaper with no dim backdrop. It SHALL NOT rely on Hyprland window rules (layer-shell surfaces are outside `windowrule`; rofi self-positions and self-sizes).

#### Scenario: panel-sized transparent window
- **WHEN** the launcher opens
- **THEN** the rofi window is 548px wide (incl. the 4px border), centered on the monitor
- **AND** the area outside the rounded panel is not painted (`transparency: "real"`), so the live wallpaper shows through with no full-screen dim

#### Scenario: no Hyprland window rules required
- **WHEN** the launcher is open
- **THEN** it is a layer-shell overlay surface (rofi default; `-normal-window` not used)
- **AND** `dotfiles/config/hypr/window-rules.lua` contains no rofi entry
- **AND** no `layerrule` for blur is applied to the launcher (crisp fidelity per the reference)

### Requirement: measured geometry (from the reference screenshot)
The launcher geometry SHALL match the reference at 1x: outer radius ~12px; 4px border; 2px dark ring; 18px body padding (top/sides, ~14px bottom); search bar 500×38 with ~5px radius; 21px gap to the list; 8 visible rows of 36px with zero spacing and ~5px radius; 24px icons; normal text bright, selection full-row with dark text.

#### Scenario: panel chrome
- **WHEN** the launcher opens
- **THEN** the panel body is `@background` with a 12px outer radius
- **AND** it carries a 4px border in `@color04` and a 2px ring in `@color01` between border and body (realized via the `window` padding zone: `window { border: 4px @color04; background-color: @color01; padding: 2px; }` with `mainbox` `@background`)

#### Scenario: search bar and list spacing
- **WHEN** the launcher opens
- **THEN** the search bar is 38px tall with a ~5px radius and `@color01` background, inset 18px from the body edges
- **AND** there is a 21px gap between the search bar and the first row
- **AND** exactly 8 rows are visible with a 36px row height and zero inter-row spacing

#### Scenario: rows, selection, and icons
- **WHEN** a list row is rendered
- **THEN** icons render at 24px from the host icon theme
- **AND** the selected row is a full-row pill in `@color10` with `@background` text
- **AND** normal rows use `@foreground` text

### Requirement: icons and font
The launcher SHALL show application icons and use the provisioned Nerd Font.

#### Scenario: icon display
- **WHEN** the launcher opens
- **THEN** `show-icons` is enabled, so icons render from the host icon theme

#### Scenario: font
- **WHEN** the launcher opens
- **THEN** the font is the provisioned JetBrains Mono Nerd family at ~12pt

### Requirement: keybinding SUPER+D launches the launcher
`SUPER+D` SHALL be bound to `rofi -config ~/.config/rofi/launcher/config.rasi -show drun` in `keybindings.lua`, replacing the wofi invocation.

#### Scenario: the binding is present and correct
- **WHEN** `keybindings.lua` is inspected
- **THEN** the launcher binding uses `mod .. " + D"`
- **AND** its command is `rofi -config ~/.config/rofi/launcher/config.rasi -show drun`
- **AND** no `wofi` invocation remains in the file

### Requirement: relaunch follows palette changes
A launcher opened after a `wallpaper set` SHALL reflect the new palette on its next launch, with no reloader daemon and no running-process re-theme.

#### Scenario: relaunch after re-theme
- **WHEN** a new wallpaper palette is applied and the launcher is launched again
- **THEN** the launcher colors reflect the new `current/colors.rasi`
- **AND** no additional runtime process is required for the pickup