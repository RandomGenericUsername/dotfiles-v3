## ADDED Requirements

### Requirement: The runtime requests and caches the btop palette artifacts
The runtime SHALL request `btop-minimal.theme`, `btop-balanced.theme`, and
`btop-full.theme` from CSG on every palette generation, SHALL include all three in
the hashed outputs of the produced palette entry, and SHALL record their hashes in
the entry's `meta.json` `artifact_hashes`.

The three artifact names SHALL be members of `PALETTE_ARTIFACT_NAMES`, which is
the completeness oracle used by `ensure_palette_entry_complete`.

#### Scenario: generation requests the btop formats
- **GIVEN** a wallpaper change
- **WHEN** the runtime invokes CSG
- **THEN** the invocation includes `--format btop-minimal.theme`,
  `--format btop-balanced.theme`, and `--format btop-full.theme`

#### Scenario: the artifacts are part of the completeness oracle
- **GIVEN** `PALETTE_ARTIFACT_NAMES`
- **WHEN** its members are listed
- **THEN** it contains `colors.btop-minimal.theme`, `colors.btop-balanced.theme`,
  and `colors.btop-full.theme`

#### Scenario: an entry missing a btop artifact self-heals
- **GIVEN** a cached palette entry lacking any of the three btop artifacts
- **WHEN** `ensure_palette_entry_complete` evaluates it
- **THEN** the entry is reported incomplete, evicted, and re-derived
- **AND** no manual migration step is required

### Requirement: The btop artifacts are reachable through `current/`
After a successful palette swap, `current/colors.btop-minimal.theme`,
`current/colors.btop-balanced.theme`, and `current/colors.btop-full.theme` SHALL
be atomic symlinks into the palette cache entry, following the same
repoint-and-skip rules as every other artifact.

#### Scenario: current exposes all three after a swap
- **GIVEN** a completed palette swap
- **WHEN** the `current/` directory is listed
- **THEN** all three `colors.btop-*.theme` symlinks exist
- **AND** each resolves to a file inside the new palette entry

#### Scenario: a missing artifact is skipped, never left dangling
- **GIVEN** a palette entry missing one of the three btop artifacts
- **WHEN** `repoint_current_symlinks` runs
- **THEN** that artifact's symlink is skipped with a warning
- **AND** no dangling symlink is created

### Requirement: The palette contract schema declares the btop artifacts
The palette `meta.json` schema SHALL list `colors.btop-minimal.theme`,
`colors.btop-balanced.theme`, and `colors.btop-full.theme` in **both** the
`artifact_hashes` `required` array and its `properties` map. The schema change
SHALL land in the same commit as the runtime change, because the object is closed
(`additionalProperties: false`) with a closed `required` list.

#### Scenario: a conforming meta.json with the btop artifacts validates
- **GIVEN** a `meta.json` whose `artifact_hashes` includes all ten artifacts
- **WHEN** it is validated against the palette schema
- **THEN** validation succeeds

#### Scenario: an entry written before this change is no longer conforming
- **GIVEN** a `meta.json` whose `artifact_hashes` lacks the three btop artifacts
- **WHEN** it is validated against the palette schema
- **THEN** validation fails, which is the intended forcing function for
  re-derivation

#### Scenario: contracts-check stays green
- **GIVEN** the runtime writes the three new artifact keys
- **WHEN** `make contracts-check` runs
- **THEN** it passes
