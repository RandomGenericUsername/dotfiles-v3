## Purpose

The icon assets the settings panel and its bar trigger require, delivered through
the existing ITR pipeline: palette-aware SVG templates, `icons.yaml` registration,
and the runtime contrast guard for the bar icon.

## ADDED Requirements

### Requirement: Palette-aware templates

Every new icon SVG SHALL live under the existing icon-template tree and SHALL use
ITR palette placeholders for its fills, with no literal colors, so it follows the
runtime wallpaper palette like every other icon.

#### Scenario: Placeholder, not literal
- **WHEN** a new settings/volume/brightness template is inspected
- **THEN** its fills use `{{COLOR_FOREGROUND}}` (or another vocabulary
  placeholder) and contain no literal `black`/`white`/hex fill

#### Scenario: Valid geometry
- **WHEN** the template is validated
- **THEN** it is valid SVG with a `viewBox` that frames the visible paths

### Requirement: Settings and panel icon groups

`icons.yaml` SHALL register a `settings` group (bar trigger), a `settings-panel`
group (`wifi`, `wifi-off`, `bluetooth`, `bluetooth-off`, `hyprmod`), a
`brightness` group (`default`), and a `volume` group (`muted`, `lowest`, `low`,
`medium`, `max`), each variant mapping to a unique template and output filename.
The `settings-panel` on-variants SHALL map `COLOR_FOREGROUND` to the accent
(`color13`) and the off-variants to the neutral `foreground` token, so the state
tint is baked by ITR rather than applied by CSS. The off state SHALL be carried
by brightness (the panel dims the neutral off glyph via opacity), not by a
second palette hue — palette tokens such as `color11` and `color13` can be
near-identical on some wallpapers.

#### Scenario: Distinct outputs
- **WHEN** the manifest is read
- **THEN** every new variant has a unique logical name, an existing template
  path, and a unique output filename

#### Scenario: Bar mapping present
- **WHEN** the `settings` group is read by AGS
- **THEN** it exposes `bar_mappings` with `widget: settings` and
  `states: { default: <settings variant> }`

### Requirement: Level-aware volume set

The `volume` group SHALL provide five distinct variants whose rendered glyphs
increase in wave/level detail from `muted` through `max`, preserving the
supplied level distinction (the outer wave layers at reduced opacity for the
lower non-muted levels).

#### Scenario: Five distinct levels
- **WHEN** the five variants are rendered
- **THEN** each is visually distinct and ordered muted → lowest → low → medium → max

### Requirement: Bar contrast guard coverage

The `settings` bar group SHALL be included in the runtime contrast-guard
allowlist so its foreground mapping retargets on low-contrast wallpapers; the
`settings-panel`, `volume`, and `brightness` groups SHALL NOT be in the
allowlist because they render over the opaque panel surface (brightness is its
own group specifically so a bar contrast flip cannot darken it).

#### Scenario: Bar icon retargets
- **WHEN** the wallpaper makes the default foreground mapping low-contrast
- **THEN** the rendered `settings` bar icon uses the retargeted palette token

#### Scenario: Panel icons excluded
- **WHEN** the allowlist is inspected
- **THEN** it contains `settings` and does not contain the panel-only groups
