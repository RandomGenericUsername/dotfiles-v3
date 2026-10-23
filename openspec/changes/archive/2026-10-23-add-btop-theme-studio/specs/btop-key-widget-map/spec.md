# Spec Delta

## Purpose

`btop-key-widget-map` is a generated, drift-checked artifact mapping every btop theme key to the boxes/modules that draw it, so the studio can truthfully answer "where does this key show?" instead of relying on hand-traced guesses.

## ADDED Requirements

### Requirement: Map derived from btop source

The key→widget map SHALL be generated from btop's own source: the key set from `btop_theme.cpp` (`Default_theme`) and the per-key attribution from `btop_draw.cpp`, including the gradient names passed as variables into `Draw::Graph` / `Draw::Meter` builders.

#### Scenario: variable gradient names are attributed
- **WHEN** a gradient is drawn via a variable (`Theme::g(color_gradient)`) supplied by a `Draw::Graph{…,"download",…}` call site
- **THEN** the key `download` is attributed to the module of that call site (`net`)

### Requirement: Complete key coverage

The map SHALL cover every key btop defines (all 48), with attribution for each.

#### Scenario: all keys present
- **WHEN** the map is generated
- **THEN** it contains an entry for every key in `Default_theme`, including gradient stops and box-outline keys

### Requirement: Documented attribution rules

The map SHALL attribute a key by the namespace of its draw code, SHALL attribute a `*_box` key to its own box, SHALL attribute gradient-stop keys to their family's modules, and SHALL attribute keys not referenced in the draw source to all boxes, flagged as such.

#### Scenario: gradient stop inherits family
- **WHEN** `used_start` is not itself referenced but `used` is
- **THEN** `used_start` inherits the modules of `used`

#### Scenario: unreferenced key flagged
- **WHEN** a key (such as `main_bg`) is not referenced in the draw source
- **THEN** it is attributed to all boxes and its site is flagged as not-referenced

### Requirement: Drift guard

The map SHALL have a verifier that re-derives it from the source and fails when the committed map differs, so the artifact stays pinned to the btop version it was derived from.

#### Scenario: drift fails
- **WHEN** the source changes such that a key's modules differ from the committed map
- **THEN** the verifier exits non-zero and reports the differing keys

### Requirement: Consumed by the studio

The studio SHALL use the generated map for its component coverage and "where it shows" reporting.

#### Scenario: coverage is source-derived
- **WHEN** the studio shows which modules a key paints
- **THEN** those modules come from the generated map
