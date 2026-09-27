# Tasks: settings-panel Wi-Fi tile signal icons

- [x] 1. Implement reactive `wifiSignalIcon()` in `controls/wifi.tsx` (shared thresholds, no duplication).
- [x] 2. Confirm/extend `CapabilityTile` for reactive icon swap; keep off-state muted variant.
- [ ] 3. Provision + restart AGS; live signal-step check full→low.
- [ ] 4. Parity gate green; screenshot-vs-`state-4-panel-tile` sign-off.

Verification: with radio off the tile shows `wifi-off` (no crash on
null active network); with no saved networks it shows `Not connected`.
