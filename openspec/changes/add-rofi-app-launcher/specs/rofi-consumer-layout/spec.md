## ADDED Requirements

### Requirement: one shared consumer pointer at the rofi root
The consumer pointer table SHALL include `ConsumerPointer(path="config/rofi/colors.rasi", target="colors.rasi")` and target the `colors.rasi` artifact (not `colors.gtk.css`). The pointer SHALL be the single runtime wiring for rofi; no per-tool pointers are added.

#### Scenario: the rofi pointer is present
- **WHEN** `StaticConsumerPathSpec.consumer_pointers()` is invoked
- **THEN** it returns the rofi pointer after the gtk-4.0 entry
- **AND** the pointer maps `config/rofi/colors.rasi` to `colors.rasi`

#### Scenario: the seeder creates the symlink once the dir exists
- **WHEN** `<install>/config/rofi/` exists (provisioned) and the seeder runs
- **THEN** `<install>/config/rofi/colors.rasi` is a symlink to `current/colors.rasi`

#### Scenario: missing parent dir skips without creating
- **WHEN** `<install>/config/rofi/` does not exist yet
- **THEN** the seeder skips the pointer with a warning
- **AND** no directory is created under the spine

### Requirement: nested tool subdirectories import the shared palette
Every rofi tool config under `<install>/config/rofi/<tool>/` SHALL reference the shared palette via a relative `@import "../colors.rasi"`. The palette import SHALL NOT be duplicated per tool.

#### Scenario: launcher config imports the root palette
- **WHEN** rofi loads `launcher/config.rasi`
- **THEN** the file contains `@import "../colors.rasi"`
- **AND** rofi resolves the import relative to the importing file (the launcher subdirectory), resolving to `<install>/config/rofi/colors.rasi`

#### Scenario: future tool dirs reuse the same import
- **WHEN** a new rofi tool directory is added under the rofi config root
- **THEN** it needs no runtime change to consume the palette
- **AND** the new tool's config uses `@import "../colors.rasi"` to the shared pointer

### Requirement: the palette variables are usable as rofi theme values
The generated `colors.rasi` (as produced by csg's `colors.rasi.j2`) SHALL parse cleanly as a rofi theme, exposing `background`, `foreground`, `cursor`, and `color00`–`color15` as global properties referenceable from theme blocks.

#### Scenario: generated artifact parses under rofi
- **WHEN** `rofi -theme <generated colors.rasi> -dump-theme` is run against a live-generated artifact
- **THEN** it exits 0 with no parse errors
- **AND** the dump includes the `color00`–`color15` and `background`/`foreground` global properties

#### Scenario: theme references resolve
- **WHEN** a config.rasi theme block uses `@background`, `@foreground`, and `@colorNN`
- **THEN** rofi resolves them to the values from the imported palette