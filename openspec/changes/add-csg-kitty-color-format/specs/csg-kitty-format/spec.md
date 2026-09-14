## ADDED Requirements

### Requirement: A `kitty` color format exists in CSG
The `ColorFormat` enum SHALL contain `KITTY` with value `kitty`, and a
`colors.kitty.j2` template SHALL be part of the default template catalog. The
format SHALL render to `colors.kitty` through the same path as every other
format (no special-casing). An unknown `colors.<key>.j2` SHALL still be rejected
by the catalog.

#### Scenario: catalog discovers the kitty template
- **GIVEN** a templates directory containing `colors.kitty.j2`
- **WHEN** the catalog is derived
- **THEN** it contains one entry with `format == ColorFormat.KITTY`
- **AND** an unknown `colors.bogus.j2` still raises `TemplatesValidationError`

#### Scenario: rendering produces colors.kitty
- **GIVEN** a generation request whose formats include `kitty`
- **WHEN** the scheme is rendered
- **THEN** `output_dir/colors.kitty` exists
- **AND** its bytes are the rendered `colors.kitty.j2`

### Requirement: The kitty fragment uses valid kitty color syntax
The rendered `colors.kitty` SHALL contain exactly the kitty-supported colour keys
in plain `key #rrggbb` form — `background`, `foreground`, `cursor`, `color0`
through `color15`, `selection_background`, `selection_foreground` — and SHALL
NOT contain variable syntax, `rgb()` values, or non-kitty metadata lines. Every
colour SHALL come from the shared `ColorScheme` model (never invented), so the
artifact cannot drift from the other consumers.

#### Scenario: kitty parses the fragment cleanly
- **GIVEN** a rendered `colors.kitty`
- **WHEN** kitty loads it (`load_config`)
- **THEN** no "Ignoring invalid config line" is emitted
- **AND** `background` and `color0` equal the scheme's `background` and `colors[0]`

#### Scenario: selection colours are palette-derived
- **GIVEN** a rendered `colors.kitty`
- **WHEN** `selection_background` / `selection_foreground` are read
- **THEN** they equal the scheme `background` / `foreground` hexes
