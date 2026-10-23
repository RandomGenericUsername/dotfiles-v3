## Why

Two glyphs in the audio popup freeze while their bar/slider counterparts stay
live: the `Input` card stays `mic-on` when the default source is muted (no
`Muted` badge), and the `Output` card glyph ignores speaker volume/mute even
though the slider and bar indicator track. Applications rows already track.

Root cause (confirmed, T11): `DeviceCard` reads volume/mute through memoized
inner computeds (`defaultSpeakerVolume/Mute`, `defaultMicrophoneVolume/Mute`)
that only depend on `wp.nodes` membership, never on per-node
`notify::volume/mute`.

## What Changes

- `DeviceCard` subscribes via `useEndpointEpoch(endpoint)` and reads live
  GObject props (`nodeOf(endpoint())?.volume/mute`) directly — same pattern as
  `OutputIndicator` / `StreamRow`.
- Behavior contract locked (user-confirmed): bar mic + Input card follow the
  default microphone; Recording rows follow each stream's own mute only (no OR
  with default mic); Output card follows default speaker; every leading/trailing
  glyph keeps click-to-toggle its own node; bar mic click still opens the popup.
- No other files, no polling, no shared-accessor rewrite.

## Non-goals

- No `state.ts` accessor changes, no bar widget changes, no `VolumeSlider.tsx`,
  no CSS/icon-registry/icons.json, no effective-mute OR on Recording rows, no
  new deps, no redesign.
