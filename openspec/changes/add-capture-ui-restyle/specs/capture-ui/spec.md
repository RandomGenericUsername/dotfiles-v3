## Purpose

The capture window rebuilt to the approved mockup information architecture (`spikes/capture-tool-ui/`): mode-first, icon targets, receding settings, one loud primary action, GIF as its own mode — styled exclusively with runtime palette tokens and remembering the user's last choices.

## ADDED Requirements

### Requirement: Mode-first layout

The window SHALL open on a two-tab mode switch (Screenshot with the `camera` icon, Recording with the `video` icon); the active tab is tinted in the palette accent and determines which settings view renders. The two modes SHALL share one accent colour and be distinguished by their icon and the record dot, not by a second accent hue. No backend names (`grim`, `wf-recorder`, …) SHALL appear in the UI.

#### Scenario: Mode determines the view
- **WHEN** the user switches tabs
- **THEN** exactly one of the screenshot/recording settings views is visible and the active tab carries the `.active` selected style

### Requirement: Icon target tiles

Both views SHALL present Region/Screen/Window as three equal icon tiles with single-select behavior; the selected tile shows an accent tint and accent border plus an accent icon.

#### Scenario: Target selection is exclusive and visible
- **WHEN** the user clicks a target tile
- **THEN** it becomes the only `.selected` tile and the choice feeds the capture/record invocation

### Requirement: Setting rows with segmented pills

Each setting SHALL render as a micro-cap label on the left and an equal-width segmented control on the right. Screenshot exposes Delay (None/3s/5s/10s), Format (PNG/JPEG), Output (Clipboard/Save with icons). Recording exposes Frame rate (24/30/60), Format (MP4/WebM/GIF), Audio (System/Mic/None with icons), Quality (Low/Medium/High), Duration (∞/10s/30s/60s/Custom).

#### Scenario: Rows match the mockup inventory
- **WHEN** comparing each view against `spikes/capture-tool-ui/screenshot.html` and `recording.html`
- **THEN** every row, option, and default selection is present; audio and duration choices are live state, not decoration

### Requirement: GIF special mode

Selecting GIF SHALL remove the Audio row, narrow Frame rate to (10/15/20/30), and add a Size row (Original/75%/50%) in the slot Audio vacated. Rows SHALL keep their positions across the switch — Frame rate stays above Format. Deselecting GIF SHALL restore the standard rows. No explanatory notice is rendered (review feedback: the row changes are self-evident).

#### Scenario: GIF reshapes the view
- **WHEN** the user selects the GIF format pill
- **THEN** the audio row is gone, the fps row is narrowed, Size occupies the audio slot, and Format has not moved

### Requirement: Surface follows the view size

The window SHALL resize its layer surface when the visible view's height changes
(mode switch, settings, GIF row swap), and SHALL shrink as well as grow.
GTK does not shrink a layer-shell surface on its own — measured live, the
surface stayed 718px tall after returning to the 590px screenshot view, leaving
the panel pinned near the top of a too-tall transparent window — so the panel is
measured and an explicit size pushed after each switch, which also re-centres it
on the compositor side.

#### Scenario: Returning to a shorter view re-centres the panel
- **WHEN** the user goes Recording (taller) and back to Screenshot (shorter)
- **THEN** the surface shrinks to the screenshot view's height and the panel is centred again

#### Scenario: Settings grows the surface
- **WHEN** the settings view (the tallest) opens
- **THEN** the surface grows to fit it and stays centred

### Requirement: Primary action and keyboard contract

Each view SHALL end in one full-width primary button (accent-tinted camera + "Take Screenshot"; record-tinted dot + "Start Recording"). `Escape` SHALL hide the window (cancel); `Enter` SHALL trigger the primary action.

#### Scenario: Keyboard parity with mouse
- **WHEN** the user presses `Escape` / `Enter` with the window focused
- **THEN** the window hides / the primary action fires, identically to clicking Close / the CTA

### Requirement: Remembered configuration

The window SHALL restore the user's last-used screenshot and recording choices on open and persist them on every capture/record start. First run falls back to the mockup defaults (Region, PNG, Clipboard / Region, 60fps, MP4, System, High, ∞).

#### Scenario: Choices survive relaunch
- **WHEN** the user sets 5s delay + JPEG + Save, captures, closes, and reopens
- **THEN** those three selections are pre-selected

### Requirement: Token-driven stylesheet

`style.css` SHALL style the window using only `@color_*` palette tokens, with NO literal colors. Both mode accents and the primary CTAs SHALL use the palette accent (`@color_06`); caution/severity states (settings errors) SHALL use the palette's caution slot (`@color_03`). Selected states use accent tint + accent border.

#### Scenario: Both modes share the accent
- **WHEN** the user switches between the Screenshot and Recording tabs
- **THEN** the active tab and the primary CTA use the same palette accent colour in both modes

#### Scenario: Palette swap restyles the window
- **WHEN** the runtime derives a new palette and the reloader restarts the `capture` instance
- **THEN** the window renders in the new palette with zero code or file changes

#### Scenario: No literal colors
- **WHEN** scanning `style.css`
- **THEN** no hex literal appears — accents are palette slots, not fixed colours
