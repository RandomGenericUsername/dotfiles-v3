# Design: settings-panel Wi-Fi tile signal icons

## Implementation (`settings-panel/controls/wifi.tsx`)

- Add a `wifiSignalIcon()` resolver mirroring popup `getSignalIconKey`
  (≥75 full, ≥50 good, ≥25 medium, else low) over the active network's
  `strength`; share the thresholds via a tiny helper (single home — either
  export from `WifiContent` or a `lib/` helper; no duplicated threshold
  tables).
- `CapabilityTile` takes `iconOn`/`iconOff` as resolved file paths today —
  confirm it accepts a *reactive* icon (computed accessor) or extend it
  minimally so the glyph swaps live with signal changes without a
  view re-mount. Off state keeps the muted `wifi-off` variant.
- Subtitle logic untouched.

## Contract table

| Mock element (`state-4-panel-tile`) | Code owner |
|---|---|
| Circle-badged signal glyph | `wifiSignalIcon()` + `registry.resolve("settings-panel", …)` |
| `SSID · NN%` subtitle | existing subtitle computed |
| Tile layout/selection | `CapabilityTile` (unchanged) |

## Verification

- Parity gate → 0. Live: vary signal (move rooms / hotspot) → tile glyph
  steps full→good→medium→low matching popup rows; radio off → muted glyph;
  screenshot vs `state-4-panel-tile`.
