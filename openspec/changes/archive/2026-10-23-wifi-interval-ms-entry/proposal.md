# Proposal: interval as ms entry (Sally spec) + config migration

## Why

The interval "dropdown" is actually a cycling button over a fixed set
`[0,5,15,30]` — it shows only the current value and offers nothing to
select, which is exactly the owner's complaint. Per Sally (owner-approved):
a raw milliseconds entry with a live humanized hint, rule caption, and
preset chips.

## What Changes

- `components/wifi/WifiContent.tsx`: replace the cycling button with:
  numeric entry (ms) + `ms` suffix + live hint (`900000`→`15 min`,
  `0`/empty→`Off`) + caption `Min 1000 ms · 0 = Off · Enter/leave to apply,
  junk reverts` + preset chips `5m 15m 30m Off`. Commit on Enter/focus-leave;
  invalid input reverts to last good; values in `(0,1000)` clamp to `1000`;
  `0`/empty = Off. (Assumed floor 1000 ms — owner to confirm; one-line
  constant either way.)
- Config migration: `interval_min` (minutes) → `interval_ms`
  (milliseconds) in `SpeedTestConfig`, `wifi-speedtest.json`, and the
  scheduler (`interval_ms` used directly as the timeout). `loadConfig()`
  migrates legacy files (`interval_min * 60000`, then saves back) so existing
  machines don't lose their setting.

## Non-goals

- No auto-run/run-button changes (change 7).
- No scheduler behavior changes beyond the unit conversion.

## Mock anchors

- `state-2-stc-expanded` (entry + hint + caption + chips)
