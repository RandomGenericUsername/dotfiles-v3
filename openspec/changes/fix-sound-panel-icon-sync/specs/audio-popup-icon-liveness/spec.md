## ADDED Requirements

### Requirement: DeviceCard glyphs track live endpoint state

`DeviceCard` SHALL derive `level` and `muted` from the endpoint node's live
GObject `volume`/`mute` properties, subscribed through
`useEndpointEpoch(endpoint)`. It SHALL NOT read those values solely through
`defaultSpeakerVolume` / `defaultSpeakerMute` / `defaultMicrophoneVolume` /
`defaultMicrophoneMute` inside the glyph/badge/level computeds.

#### Scenario: default source mute flips Input glyph and badge

- **GIVEN** the popup is open on the main view with default mic unmuted
- **WHEN** the default microphone is muted (panel click or `wpctl set-mute
  @DEFAULT_AUDIO_SOURCE@ 1`)
- **THEN** the Input card leading glyph resolves `microphone/system-mic-off`
- **AND** the `Muted` badge beside the title is visible
- **AND** the bar `MicIndicator` shows `mic-off` in the same step

#### Scenario: default speaker volume flips Output glyph

- **GIVEN** popup open, default speaker unmuted at a known level
- **WHEN** default speaker volume moves through 15%, 40%, 60%, 90%
- **THEN** the Output card glyph resolves
  `system-lowest`, `system-low`, `system-medium`, `system-max` respectively
- **AND** the bar `OutputIndicator` variant and the card percentage match the
  same thresholds

#### Scenario: default speaker mute flips Output glyph and dims level

- **GIVEN** default speaker unmuted
- **WHEN** default speaker is muted
- **THEN** Output glyph resolves `volume/system-muted`
- **AND** `LevelLine` carries class `audio-level-line muted`
- **AND** badge is visible

### Requirement: Per-surface mute authority is not mixed

Bar mic and Input card SHALL follow the default microphone only. Output card
and bar output SHALL follow the default speaker only. Each Recording row SHALL
follow only its own stream's `mute`; muting the default microphone SHALL NOT
change Recording-row glyphs or badges. Each panel glyph click SHALL toggle
exactly the node its row controls.

#### Scenario: source mute leaves Recording rows on mic-on

- **GIVEN** default mic muted, two Chrome recording streams unmuted
- **WHEN** popup shows Recording section
- **THEN** both rows show `system-mic-on` and no `Muted` badge
- **AND** Input card shows `system-mic-off` + badge
- **AND** clicking one Recording glyph toggles only that stream's `mute` in
  `pw-dump` / `wpctl status`

### Requirement: Change is reactive, not polled, and scoped

The fix SHALL use existing reactive bindings only (no `pw-dump`/`wpctl`
poll loops, no new dependencies). Files outside `AudioPopup.tsx::DeviceCard`
(and audit-only `RecorderRow`) SHALL be unchanged: `state.ts` accessors,
`bar/widgets/audio.tsx`, `VolumeSlider.tsx`, icon registry, CSS, icons.json,
provisioning.

#### Scenario: forbidden surface untouched

- **GIVEN** the implementation is complete
- **WHEN** `git diff` is inspected
- **THEN** only `dotfiles/config/ags/audio/AudioPopup.tsx` is modified
  (plus this openspec change directory if tasks were checked off)
- **AND** `state.ts` still exports the original four default accessors
