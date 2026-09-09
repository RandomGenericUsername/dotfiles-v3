## ADDED Requirements

### Requirement: csg generate requests the rasi format
`csg generate` (as invoked by the runtime adapter) SHALL include `--format rasi`, so a `colors.rasi` file is produced in the output directory alongside the existing five palette artifacts.

#### Scenario: runtime render produces colors.rasi
- **WHEN** the runtime seeds a wallpaper through the csg adapter
- **THEN** the csg subprocess args include `--format rasi`
- **AND** a file `colors.rasi` exists in the adapter output directory

#### Scenario: artifact verification includes colors.rasi
- **WHEN** the adapter verifies the generated artifacts exist
- **THEN** `colors.rasi` is checked as a file (not a directory) alongside `colors.yaml`, `colors.conf`, `colors.gtk.css`, `colors.adw.css`, `colors.sequences`

### Requirement: PaletteArtifacts carries colors_rasi
The `PaletteArtifacts` model and every persisted `artifact_hashes` shape SHALL include a `colors_rasi` entry keyed `"colors.rasi"`, mirroring the existing five named fields.

#### Scenario: cache meta.json records the sixth hash
- **WHEN** a palette entry is written to the cache
- **THEN** `meta.json` `artifact_hashes` contains `"colors.rasi": "<sha256-hex>"` alongside the five existing names

#### Scenario: sentinel state carries the field
- **WHEN** a state-repository fallback sentinel is built
- **THEN** it includes `colors_rasi` with the sentinel hash value

### Requirement: PALETTE_ARTIFACT_NAMES includes colors.rasi
The completeness oracle tuple SHALL include `"colors.rasi"`, so a cache entry is a valid hit only when all six artifacts are present.

#### Scenario: a six-artifact entry is a complete hit
- **WHEN** a palette cache entry contains all six artifact files and a meta.json carrying all six hashes
- **THEN** `ensure_palette_entry_complete` returns true (no eviction)

#### Scenario: a legacy five-artifact entry is migrated
- **WHEN** a cache entry exists with only the five legacy artifacts
- **THEN** it is treated as incomplete and evicted
- **AND** the same wallpaper regenerates a six-artifact entry through the normal staging path

### Requirement: current/ and consumer repoint include colors.rasi
The seeder's `repoint_current_symlinks` SHALL create `current/colors.rasi → cache/palettes/<entry>/colors.rasi`, and the reconcile skip/cleanup/expected-target tuples SHALL treat `colors.rasi` as a known palette artifact name.

#### Scenario: current/colors.rasi is repointed
- **WHEN** the seeder repoints current symlinks after a seed
- **THEN** `current/colors.rasi` is a symlink to the active cache entry's `colors.rasi`

#### Scenario: reconcile tracks colors.rasi
- **WHEN** reconcile computes skip lists, stale-symlink cleanup, and expected targets
- **THEN** `colors.rasi` appears in all three palette-artifact sets
- **AND** a stale `current/colors.rasi` (pointing at a superseded entry) is cleaned up

#### Scenario: inspect reports colors.rasi
- **WHEN** the inspect use case projects the current palette layer's expected targets
- **THEN** `colors.rasi` appears in the palette target set alongside the five existing names

### Requirement: the rasi artifact is present in test fixtures
Every runtime test fixture that constructs a `PaletteEntry` or `PaletteArtifacts` SHALL carry `colors_rasi`, so the six-artifact set is exercised end to end.

#### Scenario: unit fixtures construct six artifacts
- **WHEN** a unit test builds a palette entry directly
- **THEN** it supplies `colors_rasi` alongside the five existing hashes
- **AND** no fixture relies on a five-field shape (mypy/pytest enforce the field)