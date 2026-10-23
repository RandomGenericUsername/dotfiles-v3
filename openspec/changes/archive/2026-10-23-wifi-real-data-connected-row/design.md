# Design: Wi-Fi real data + connected row

## Diagnosis script (do first, then fix what it proves)

1. `AGS_WIFI_DEBUG=1`, open popup, read the bar log:
   - `connected ssid -> none` forever + non-empty AP reads → connected
     resolution is broken (prime suspect: `lastDeviceState` starts `0` and
     nothing seeds it until a `StateChanged` fires).
   - Empty AP reads (`ap=null`, `device=null`) → scan/device problem:
     check `devicePath` resolution, `RequestScan` throttling, killswitch.
2. Whichever it is, fix only that path; re-run the log check.

## Implementation

- `services/wifi-service.ts`:
  - After `resolveDevice()` in `bootstrap()`, the device props (including
    `State`) are already read by `refreshDeviceProps()` — ensure
    `setLastDeviceState` is fed from that initial read (it is, via
    `applyDeviceProps` path — verify, don't assume), so `currentConnectedSsid()`
    is correct from the first `applyNetworks()`.
  - If the log shows state stuck pre-ACTIVATED while NM is connected, add a
    one-shot re-resolve of the active connection on the first completed AP
    refresh.
- `components/wifi/WifiContent.tsx` (`OtherNetworksExpand`): no structural
  change expected — `connected()`/`knownSaved`/`otherNetworks` already encode
  the right partition; they just need truthful input. Only adjust if the
  diagnosis shows the partition itself drops the active network.
- Keep `WifiRow` busy/badge branches untouched (`state-5-connecting`).

## Contract table

| Mock element (`state-1-connected`) | Code owner |
|---|---|
| Connected row + `Connected` badge | `WifiRow` + `connected()` partition |
| Saved row(s) below | `knownSaved` partition |
| `No networks found` only when truly empty | `showList` + scan-completed signal |

## Verification

- Parity gate: `python3 scripts/wifi-mock-parity.py` → 0.
- Live: connect to a network, open popup → connected row first with badge;
  bar log shows `connected ssid -> <ssid>`; screenshot next to
  `state-1-connected`, row-by-row.
