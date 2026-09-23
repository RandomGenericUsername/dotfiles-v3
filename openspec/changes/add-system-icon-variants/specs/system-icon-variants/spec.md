## ADDED Requirements

### Requirement: Dual outputs for dual-use groups (bar + system)

The manifest SHALL expose both bare variants (bar, guard-eligible) and
`system-*` variants (system surfaces, never retargeted) for the `volume`
(5: `system-muted`, `system-lowest`, `system-low`, `system-medium`,
`system-max`) and `microphone` (2: `system-mic-on`, `system-mic-off`) groups.
Each `system-*` variant SHALL reuse the bar variant's template, emit a
`volume-system-*.svg` / `microphone-system-*.svg` output, and pin
variant-level `COLOR_FOREGROUND: foreground`. Group-level mappings and
`bar_mappings` SHALL be unchanged.

#### Scenario: system variants render bright on a light wallpaper

- **GIVEN** a light wallpaper whose top-strip luminance flips bare
  `volume.COLOR_FOREGROUND` below threshold
- **WHEN** `wallpaper set <light.png>` derives icons
- **THEN** `volume-system-low.svg` contains the palette `foreground` hex and
  `volume-low.svg` contains the picked dark hex
- **AND** `meta.json contrast.decisions` mentions only bare variants, never
  `system-*`

#### Scenario: dark wallpaper keeps both stable

- **GIVEN** a dark wallpaper where bare tokens already meet the threshold
- **WHEN** icons derive
- **THEN** bare and `system-*` outputs contain their authored hexes with no
  retarget entries

### Requirement: Consumers resolve the correct surface

The bar SHALL resolve bare variants; the settings-panel Sound card
(`VolumeSlider.tsx`) and the audio popup (`AudioPopup.tsx`) SHALL resolve
`system-*` variants only. `media-transport`, `app-icons`, `capture-tool`,
`settings-panel`, and `brightness` resolution SHALL be unchanged.

#### Scenario: popup and slider never show guard-retargeted files

- **GIVEN** a light wallpaper with an active contrast flip on bare `volume`
- **WHEN** the audio popup and settings panel render
- **THEN** every speaker/mic glyph resolves to a `volume-system-*.svg` /
  `microphone-system-*.svg` path (no bare `volume-*.svg` / `microphone-*.svg`)

### Requirement: Cache stays single-entry, content-addressed

`icons_entry_hash` SHALL continue over the effective overlay bytes; the 7 new
outputs SHALL belong to the same cache entry as the bare variants. Same
inputs SHALL hit cache; a palette flip SHALL produce a new entry (no stale
icons served).

#### Scenario: one entry holds both surfaces

- **GIVEN** two `wallpaper set` runs with identical wallpaper + templates +
  manifest
- **WHEN** the second runs
- **THEN** it reports `cache_hit_icons == True` with zero `itr` invocations
- **AND** the entry dir contains both `volume-low.svg` and
  `volume-system-low.svg`

### Requirement: Provisioning carries the change; bootstrap is the gate

No new SVG assets or asset-category entries SHALL be introduced (templates
reused). `assets` SHALL sync the updated manifest, `compositor_configs` SHALL
regenerate `icons.json` + deploy edited AGS sources, `runtime-seed` SHALL
render the new outputs, `verify` SHALL expect the new samples. The change is
done ONLY when `make bootstrap` completes green on the host plus the
light/dark wallpaper proofs above.

#### Scenario: fresh bootstrap serves system icons

- **GIVEN** a host after `make bootstrap` with this change
- **WHEN** `wallpaper set` runs and the popup opens
- **THEN** `current/icons/volume-system-low.svg` and
  `microphone-system-mic-on.svg` exist and resolve from the live manifest
