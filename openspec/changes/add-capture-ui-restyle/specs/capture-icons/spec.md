## Purpose

One palette-aware icon namespace for the capture tool: 14 user-provided glyphs registered through the ITR pipeline, consumed by the capture GUI and the bar recording indicator alike, with the two legacy groups (`screen-recorder`, `screenshot-tool`) retired.

## ADDED Requirements

### Requirement: Single capture-tool icon group

The icon manifest SHALL define exactly one `capture-tool` group containing 14 variants — `camera`, `video`, `region`, `monitor`, `window`, `clipboard`, `save`, `speaker`, `mic`, `info`, `warning`, `pause`, `play`, `stop` — each with a `template` under `capture-tool/default/` and an `output` named `capture-tool-<variant>.svg`. The group SHALL declare `color_mappings` for `COLOR_FOREGROUND` (→ `foreground`) and `COLOR_ACCENT` (→ a bright palette slot, battery-precedent `color13`, user-retunable via the icon color mapping editor).

#### Scenario: Manifest enumerates the full set
- **WHEN** inspecting `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`
- **THEN** the `capture-tool` group exists with all 14 variants and no other capture-related group remains

#### Scenario: Every placeholder resolves
- **WHEN** `itr render` runs against the active palette
- **THEN** all 14 outputs land in `current/icons/` with no unmapped-placeholder errors

### Requirement: Palette-safe templates

Committed SVG templates SHALL contain no literal color values: strokes and fills use `{{COLOR_FOREGROUND}}`, and the region glyph's filled body uses `{{COLOR_ACCENT}}`. Templates SHALL keep a valid `viewBox` with all visible paths inside it.

#### Scenario: No fixed colors in templates
- **WHEN** scanning `dotfiles/assets/icon-templates/capture-tool/default/*.svg`
- **THEN** no `black`, `white`, or hex literal appears in any `fill` or `stroke` attribute

#### Scenario: Small-size legibility
- **WHEN** the transport glyphs render at `pixel_size=16` in the bar cluster
- **THEN** pause/play/stop remain distinguishable (verified visually or via VM screenshot)

### Requirement: Legacy group retirement

The `screen-recorder` group (manifest block + `dotfiles/assets/icon-templates/screen-recorder/`) and the `screenshot-tool` group (`screenshot-tool.yaml` + manifest block + `dotfiles/assets/icon-templates/screenshot-tool/`) SHALL NOT exist. Their rendered outputs SHALL be unreferenced.

#### Scenario: No legacy references
- **WHEN** grepping the repo for `screen-recorder` outside historical docs and for the five legacy variant names (`all-screen-selection`, `region-selection`, `take-screenshot`, legacy `cursor`/`delay` template paths)
- **THEN** only the transport backends (`gpu-screen-recorder`, `wf-recorder` binary names) and history remain

### Requirement: Registry consumption

The bar recording indicator SHALL resolve `pause`/`play`/`stop` from the `capture-tool` group. The capture window SHALL resolve its mode, target, output, audio, and notice icons from the `capture-tool` group via `IconRegistry`. Neither SHALL hardcode icon paths.

#### Scenario: Bar resolves the new namespace
- **WHEN** `recording.tsx` renders pause/play/stop states
- **THEN** `registry.resolve("capture-tool", variant)` returns the runtime path for each, and the old group name appears nowhere in the widget

#### Scenario: Capture window has no icon-less buttons
- **WHEN** the capture window renders any mode tab, target tile, output/audio segment, or the GIF notice
- **THEN** each carries its resolved icon; a missing icon file degrades to the existing text label, never to a broken image widget

### Requirement: Provisioning delivers icons to both AGS instances

Provisioning SHALL generate `icons.json` into both `config/ags/` and `config/ags-capture/`, and SHALL deploy `lib/icon-registry.ts` into the capture app's source tree with the same repo-authoritative (`force: true`) discipline as the other capture files. The `verify` role SHALL expect the new paths and SHALL NOT expect the retired ones.

#### Scenario: Capture spine is icon-capable
- **WHEN** provisioning converges and the `capture` instance starts
- **THEN** `<install>/config/ags-capture/icons.json` exists, `lib/icon-registry.ts` is deployed beside the app sources, and `registry.resolve("capture-tool", "camera")` returns an existing file

#### Scenario: Verify covers the move
- **WHEN** the `verify` role runs
- **THEN** it expects the capture `lib/` + dual `icons.json` paths and fails if `icon-mappings/screenshot-tool.yaml` is still deployed
