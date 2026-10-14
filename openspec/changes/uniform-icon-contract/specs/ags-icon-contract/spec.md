# ags-icon-contract (delta)

## ADDED Requirements

### Requirement: Every icon-bearing call site emits a state key, never a direct variant

An icon-bearing widget SHALL express its icon through `iconByStateKey` (the
ref emits a state key) or `iconByVariant` (a group with no `bar_mappings`
table). It SHALL NOT navigate `bar_mappings.states` or call
`registry.resolve` by hand, and it SHALL NOT resolve a variant name it derived
itself.

Source: spine **AD-7**; doc 101 §7, §13 step 3.

#### Scenario: the audio bar resolves through the state key

- **WHEN** `bar/widgets/audio.tsx` renders the output and mic indicators
- **THEN** it resolves `iconByStateKey("volume"|"microphone", …)` through
  `resolveIcon`, and no `registry.resolve` / `getBarMappings` call remains

#### Scenario: the battery panel and bar resolve through the state key

- **WHEN** `components/battery/BatteryContent.tsx` renders a power-mode cell and
  `bar/widgets/battery.tsx` renders the battery glyph
- **THEN** each resolves `iconByStateKey("power-mode"|"battery", …)` through
  `resolveIcon`, and no `registry.resolve` / `getBarMappings` call remains

### Requirement: The manifest maps state key → variant → art for every declared group

For every group a widget addresses by state key, the manifest's
`bar_mappings.states` SHALL map each emitted state key to an existing variant in
that group, so the resolution chain can reach the art. `volume`, `microphone`,
and `power-mode` SHALL declare such a table.

Source: spine **AD-7**; doc 101 §7.

#### Scenario: a declared state key resolves to art

- **WHEN** the state-key function emits a key the group's `bar_mappings.states`
  declares
- **THEN** resolution returns the variant's `IconSource`

#### Scenario: every declared state key names a real variant

- **WHEN** the manifest's `volume`, `microphone`, and `power-mode`
  `bar_mappings.states` are enumerated
- **THEN** each mapped variant exists in the group's `variants`

### Requirement: A missing state key resolves to blank, never a crash

When a state key has no entry in the group's table (and no `ref.fallback` covers
it), resolution SHALL return `null` (blank) and SHALL NOT throw. A missing key is
a normal, degradable state (AD-15: the runtime blanks a missing glyph).

Source: spine **AD-7**, **AD-15**.

#### Scenario: an unknown key blanks

- **WHEN** a ref emits a key absent from the group's table
- **THEN** `resolveIconSource` returns `null`, and the renderer clears the image
  rather than throwing

#### Scenario: the unlisted power-mode tier blanks

- **WHEN** an undeclared power tier resolves to the neutral `unknown` glyph
- **THEN** its `power-mode-unknown` state key has no table entry and blanks

### Requirement: There is one icon manifest artifact, one owner, one shape

Exactly one icon manifest artifact SHALL exist per install, generated from the
single authored source (`icons.yaml`), and it SHALL carry a top-level
`schemaVersion`. The bar's build-time `import icons.json` SHALL be that same
artifact — a bundling detail, not a second source. The authored `icons.yaml`
SHALL remain a pure group map (no reserved top-level key), so the icon-template
renderer, which treats every top-level key as a group, is unaffected.

Source: spine **AD-21**, **AD-16**.

#### Scenario: the generated artifact carries a version

- **WHEN** `dotfiles/config/ags/icons.json` is read
- **THEN** it has a numeric top-level `schemaVersion` alongside its group map

#### Scenario: the authored source stays a group map

- **WHEN** the icon-template renderer parses `icons.yaml`
- **THEN** every top-level key is still a group, because the version is stamped
  at generation rather than authored

### Requirement: Provisioning and the drift gate stamp the same version from one owner

The `icons-json-drift` gate SHALL derive the expected `schemaVersion` from the
provisioning role's own variable (the same owner that writes the file), so the
committed artifact, the generated artifact, and the gate cannot disagree on the
shape. The gate SHALL fail rather than guess when that variable is absent.

Source: spine **AD-21**, **AD-16**.

#### Scenario: the gate compares against the role's output

- **WHEN** `make icons-json-drift` runs
- **THEN** it reads `compositor_configs_icon_manifest_schema_version` and compares
  the committed `icons.json` to that version plus `to_nice_json(icons.yaml)`

#### Scenario: a missing version fails the gate

- **WHEN** the role's version variable is absent
- **THEN** the gate exits non-zero with a stated reason, rather than comparing
  against a guessed value

### Requirement: The registry reads groups, not the reserved version key

`lib/icon-registry.ts` SHALL separate the reserved top-level `schemaVersion` from
the group map, so `getBarMappings` and `resolve` read only named groups. The
group lookup SHALL be unaffected by the presence of the version key.

Source: spine **AD-21**, **AD-16**.

#### Scenario: the version key is not a group

- **WHEN** the manifest carries `schemaVersion`
- **THEN** `barMappings`/`resolve` never treat it as a group, and a named group
  lookup is unchanged

### Requirement: The contract is testable without the desktop stack

The state-key functions and the resolution/blanking behavior SHALL be
exercisable by `make ags-test` with no GTK and no `ags` import on the path,
resolving against the real manifest's tables.

Source: spine **AD-7**; doc 101 §13 step 3.

#### Scenario: the pure suite pins resolution and blanking

- **WHEN** the `icon-state-keys` suite runs under `node --test`
- **THEN** each declared state key resolves through the real manifest and an
  unknown key returns `null`
