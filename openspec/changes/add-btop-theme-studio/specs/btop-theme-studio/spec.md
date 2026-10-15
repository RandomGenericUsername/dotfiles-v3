# Spec Delta

## Purpose

`btop-theme-studio` is the authoring surface for btop themes: a launch-on-demand GUI that lets a user inspect and edit every btop theme key, preview the result against the real btop interface, and save it either to the repo (deployed by provisioning) or directly to the installed theme.

## ADDED Requirements

### Requirement: Launch-on-demand standalone tool

The studio SHALL be a standalone GUI application provisioned as its own AGS instance, launched on demand (launcher bin and a `SUPER` keybind), and SHALL NOT be registered in the bar's `app.tsx` or autostarted.

#### Scenario: launched from the keybind
- **WHEN** the user invokes the studio keybind
- **THEN** the studio window opens as its own instance without affecting the bar or other AGS instances

### Requirement: Theme library

The studio SHALL present a library of themes supporting create, duplicate, fork, and delete. The generated `colors.btop` theme SHALL be a read-only, palette-linked base that can be forked but not deleted.

#### Scenario: forking the generated theme
- **WHEN** the user forks `colors.btop`
- **THEN** a new authored theme is created containing the current resolved colours and becomes the edited theme

#### Scenario: generated theme cannot be deleted
- **WHEN** the user attempts to delete `colors.btop`
- **THEN** the studio refuses and offers to fork it instead

### Requirement: Component schematic as the primary view

The studio SHALL render btop's interface as a labelled schematic of boxes (cpu, cpu-detail, gpu, mem, net, disks, proc), where each drawn element is associated with the theme key(s) that paint it. Selecting a theme key SHALL highlight every component that key paints.

#### Scenario: selecting a key highlights its components
- **WHEN** the user selects the `cpu` key family
- **THEN** the cpu meter, per-core graphs, GPU utilisation, and battery components are highlighted

### Requirement: Consume btop's real layout config

The studio SHALL parse `shown_boxes` and the `presets` string from the active `btop.conf` and SHALL lay out the schematic according to the selected preset's box set, without inventing box geometry. The studio SHALL warn when the selected key paints a module that the current preset does not show.

#### Scenario: preset drives the box set
- **WHEN** the user selects a preset whose box set excludes `disks`
- **THEN** the schematic shows only that preset's boxes and the caption names them

#### Scenario: warning for a hidden module
- **WHEN** the user selects `available_*` while the current preset does not show the `disks` box
- **THEN** the studio states that this key paints `disks`, which is not shown, so the change will not be visible

### Requirement: Edit every theme key

The studio SHALL expose all 48 btop theme keys, grouped (surface, box chrome, consumption, load/heat, network/process, process state), and SHALL allow editing any of them.

#### Scenario: all keys present
- **WHEN** a theme is loaded
- **THEN** the key tree lists all 48 keys btop defines, including two-stop keys such as `download_mid` and `upload_mid`

### Requirement: Palette, arbitrary colour, and transparent sources

The picker SHALL offer the deduped ramp stops, the full `color0`–`color15` palette, the named tokens (`background`, `foreground`, `cursor`), an arbitrary colour picker for colours beyond the palette, a hex field, and a `transparent` (empty value) option. The arbitrary colour picker SHALL be usable regardless of theme kind.

#### Scenario: arbitrary colour beyond the palette
- **WHEN** the user opens the colour picker and chooses a colour not in the palette
- **THEN** the selected key is set to that literal colour and the preview updates

#### Scenario: transparent value
- **WHEN** the user picks `transparent` for a colour key
- **THEN** the key is written as an empty value and the preview renders it as transparent

### Requirement: Gradient editor

For a gradient key family the studio SHALL show its `start`, `mid`, and `end` stops as editable, and for a two-stop gradient (empty `mid`) SHALL offer adding a middle colour. The studio SHALL state that btop allows at most three stops and that new theme keys cannot be added.

#### Scenario: add a middle colour
- **WHEN** the user adds a middle colour to the two-stop `download` gradient
- **THEN** `download_mid` is set and the gradient becomes three-stop

### Requirement: Diagnosis

The studio SHALL diagnose meter-contrast defects, including when `used_start` and `meter_bg` resolve to the same colour and when `meter_bg` is too close to (or too far from) the background.

#### Scenario: collision reported
- **WHEN** `used_start` and `meter_bg` are the same colour
- **THEN** the studio reports that low-load meter blocks vanish into the empty meter

### Requirement: Save target is Repo or Installed

The studio SHALL let the user choose a save target of **Repo** or **Installed** without selecting a path, SHALL display the resolved destination for the chosen target, and SHALL reflect the target in the pending diff and the save action.

#### Scenario: repo target
- **WHEN** the target is Repo and the user saves an authored theme
- **THEN** the diff names the repo path and the action reads "Save to repo", with the change deployed by provisioning

#### Scenario: installed target
- **WHEN** the target is Installed and the user saves
- **THEN** the diff names the install-spine path and the change is written there and reloaded live

### Requirement: Repo-authoritative with an explicit installed target

The studio SHALL default to the repo-authoritative model (repo source deployed by `bootstrap`) and SHALL offer the installed target as an explicit override that writes to the install spine and reloads btop, while stating that repo edits will not propagate to a machine-owned installed theme.

#### Scenario: installed override warns of divergence
- **WHEN** the user selects the Installed target
- **THEN** the studio states that the change goes straight to the spine and drifts from the repo

### Requirement: Edit scope

A pick SHALL be applicable at three scopes — *This key*, *Same role* (every key sharing the role suffix), and *All keys* — and the studio SHALL state the blast radius before applying.

#### Scenario: same-role scope
- **WHEN** the user picks a colour with the "Same role" scope on `used_start`
- **THEN** every `*_start` key in that theme is updated together

#### Scenario: this-key scope
- **WHEN** the user picks a colour with the "This key" scope
- **THEN** only the selected key changes

### Requirement: Active theme selection

The studio SHALL let the user mark exactly one theme as the **active** theme (the one btop uses via `color_theme`), and SHALL persist that choice through the repo-owned active-theme setting.

#### Scenario: marking a theme active
- **WHEN** the user marks a theme active
- **THEN** the studio records it as the active theme and the saved setting selects it in `btop.conf`

### Requirement: One-click meter fixes

The studio SHALL provide one-click fixes for the motivating defect: **Reserve surface for meters** (the unfilled meter is drawn from the surface) and **Transparent meters** (the unfilled meter is transparent).

#### Scenario: transparent meters
- **WHEN** the user applies "Transparent meters"
- **THEN** `meter_bg` is set to the empty (transparent) value and the preview reflects it

#### Scenario: reserve surface
- **WHEN** the user applies "Reserve surface for meters"
- **THEN** the unfilled meter colour is set to the theme's surface and the used floor is raised

### Requirement: Pending edits, diff, and revert

Picks SHALL accumulate as pending edits shown as a diff; nothing SHALL be written until save; a revert SHALL discard all pending edits.

#### Scenario: nothing written on pick
- **WHEN** the user picks a colour
- **THEN** the diff shows the pending change and no file is written until save

#### Scenario: revert discards
- **WHEN** the user reverts
- **THEN** the pending edits are discarded and the diff returns to its empty state

### Requirement: Preview load and backdrop controls

The component schematic SHALL provide preview controls: a **load** control that sets the meter/utilisation level shown, a **fixed fill** mode that renders every meter at a chosen level (0 / 25 / 50 / 100%), and a **backdrop** toggle between the theme's own background and a neutral backdrop.

#### Scenario: load control
- **WHEN** the user sets the preview load to 20%
- **THEN** the schematic's meters render at that level so the theme can be judged at low load

#### Scenario: fixed fill levels
- **WHEN** the user enables fixed fill
- **THEN** every meter is rendered at the chosen fixed level, so a nearly-empty meter can be checked

#### Scenario: backdrop toggle
- **WHEN** the user toggles the backdrop
- **THEN** the schematic renders on the theme's background or on a neutral backdrop, without changing any theme colour


