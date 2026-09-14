## ADDED Requirements

### Requirement: `colors.kitty` is a first-class palette artifact
The runtime SHALL request the `kitty` format from CSG, hash its output, store it
in the palette cache entry's `artifact_hashes`, and expose it at
`current/colors.kitty`, exactly like `colors.conf`/`colors.rasi`/etc. A palette
cache entry lacking `colors.kitty` SHALL be treated as incomplete and self-healed
(evicted and re-derived), with no manual migration.

#### Scenario: a fresh derivation produces colors.kitty
- **GIVEN** a wallpaper whose palette is derived
- **WHEN** the palette cache entry is created
- **THEN** `colors.kitty` exists in the entry and its hash is recorded in `artifact_hashes`
- **AND** `current/colors.kitty` is a symlink to the entry's `colors.kitty`

#### Scenario: a pre-growth cache entry self-heals
- **GIVEN** an existing palette entry with only the six legacy artifacts
- **WHEN** it is evaluated as a cache hit
- **THEN** it is treated as incomplete
- **AND** it is evicted and re-derived on the next need (now including `colors.kitty`)

### Requirement: The kitty artifact is requested like every other format
`csg_adapter` SHALL pass `--format kitty` alongside the existing formats and
SHALL include `colors.kitty` in the hashed outputs used to validate the
derivation, so the kitty artifact participates in the same cache-key and
completeness checks as its siblings.

#### Scenario: adapter requests and hashes the kitty format
- **WHEN** the CSG adapter builds its invocation
- **THEN** the argument list contains `--format kitty`
- **AND** the generated `colors.kitty` is hashed into the palette artifact set
