# Design: wire auto-run + Run button, parse real ookla JSON

## Ookla mapping (`speedtest-service.ts`)

Real `speedtest --format=json` (Ookla) result shape:
`{type:"result", timestamp, ping:{jitter,latency}, download:{bandwidth,bytes,elapsed}, upload:{bandwidth,…}, server:{…}}`
where `bandwidth` is **bytes/sec**. Map:
`down_mbps = download.bandwidth / 125000`,
`up_mbps = upload.bandwidth / 125000`,
`latency_ms = ping.latency`. Validate with `Number.isFinite` per field;
on any invalid shape or CLI error, set a typed failure
(`lastError` state) instead of swallowing — UI shows `Test failed` until
next run. Record `ranAt` (epoch ms) alongside the result for the
details-table `Ran` row (change 2 consumes it).

If `speedtest` is absent, run the distro-provided `speedtest-cli --json`
fallback. Its top-level throughput values are bit/s; divide by 1,000,000 to
display Mbps. Provision `speedtest-cli` for Arch and Debian-family systems.

## Auto-run snap-back diagnosis (do first)

1. Flip the switch, then `cat ~/.config/ags/wifi-speedtest.json`: file
   updated → persist OK, suspect shared-state echo/guard (instrument with
   a temporary log line in `onToggled` vs `setConfigValue`).
2. File NOT updated → `saveConfig` failing (permissions/path) → fix the
   write path; the `loadConfig`-on-open revert explains everything.
3. Fix only the proven layer; both switches (popup + settings view share
   the section via `WifiContent`) must stick.

## `WifiContent.tsx`

- Delete the `Last result` row from the speed-test section (mock has none;
  results surface in the details table).
- Keep `runSpeedTest()` behind the existing `running()` guard; no UI
  loader here (change 8).

## Contract table

| Mock element (`state-2-stc-expanded`) | Code owner |
|---|---|
| Auto-run switch sticks | diagnosis fix + guarded `WifiSwitch` |
| Run button triggers a real test | `runSpeedTest()` + ookla mapping |
| No last-result row in section | deleted row |

## Verification

- Parity gate → 0. Live `Run now` against the real CLI: `lastResult()`
  holds finite numbers matching a manual `speedtest` run within noise;
  failure path (e.g. CLI missing) shows `Test failed`, never `undefined`.
  Auto-run survives close/reopen of both views.
