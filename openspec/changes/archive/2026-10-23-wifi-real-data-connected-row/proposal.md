# Proposal: Wi-Fi real data + connected row

## Why

The popup currently shows an empty network list: no connected row under
Known Networks, sometimes no rows at all. All visual work (changes 2–8) is
decoration until the list shows real data with the active network marked.
Owner report: bar icon shows connected while the popup list is empty.

## What Changes

- Diagnose with `AGS_WIFI_DEBUG=1`: whether `wifiNetworks()` is empty
  (scan/device problem) vs. populated-but-unmarked (`currentConnectedSsid()`
  returns null because `lastDeviceState !== ACTIVATED`, i.e. the state
  subscription missed the initial state).
- Fix the root cause in `services/wifi-service.ts` (candidates, in rank
  order): seed `lastDeviceState` from an initial `refreshDeviceProps()` read
  during bootstrap instead of waiting for the first `StateChanged` event;
  and/or re-resolve the active connection after the first AP refresh.
- `components/wifi/WifiContent.tsx`: render the connected network as the
  first row under Known Networks with the `Connected` badge
  (`state-1-connected`); keep saved-then-others ordering; keep the
  `No networks found` empty state honest (only when the list is truly empty
  *and* a scan completed).

## Non-goals

- No styling changes beyond what the mock already specifies (change 4).
- No details-block values beyond MAC/IP already present (change 2 owns the
  table + real values).
- No scheduler/config changes.

## Mock anchors

- `state-1-connected` (connected row + badge + saved row)
- `state-5-connecting` (row busy branch must keep working after the fix)
