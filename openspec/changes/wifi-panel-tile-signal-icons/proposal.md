# Proposal: settings-panel Wi-Fi tile uses signal-reactive icon

## Why

The main-view Wi-Fi tile still renders the static `wifi`/`wifi-off`
capability glyphs and never reflects signal level, while the mock
(`state-4-panel-tile`) specifies the circle-badged `wifi-signal-*` glyph
matching the active network's strength. Owner: "not using the most updated
network icon and not reacting to levels of signal."

## What Changes

- `settings-panel/controls/wifi.tsx` (`WifiTile`): resolve
  `wifi-signal-full/good/medium/low` from the active network's strength
  (same thresholds as popup `getSignalIconKey`), falling back to
  `wifi`/`wifi-off` when the radio is off or nothing is connected.
  Subtitle stays `SSID · NN%`.
- No ITR work: templates + `icons.yaml` + `icons.json` entries already exist
  (verified: 12 `wifi-signal` references in the deployed manifest).

## Non-goals

- No tile layout changes; no toggle-behavior changes (guarded `WifiSwitch`
  work already landed — do not touch).
- No bar-widget changes (change 8 owns the bar surface).

## Mock anchors

- `state-4-panel-tile`
