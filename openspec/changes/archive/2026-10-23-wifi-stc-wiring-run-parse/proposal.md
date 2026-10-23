# Proposal: wire auto-run + Run button, parse real ookla JSON

## Why

Two owner reports in one area: the auto-run switch "clicks and snaps back",
and the Run button "isn't wired to anything". Inspection shows the button
*is* wired — to a parser that casts raw ookla CLI JSON straight into
`{down_mbps, up_mbps, latency_ms}`, while real `speedtest --format=json`
returns nested `{download:{bandwidth}, upload:{bandwidth}, ping:{latency}}`.
So results land as `undefined`/garbage or vanish, and `lastResult` never
usefully updates. `SPEEDTEST_FINISHED_TOPIC` is imported but never emitted.

## What Changes

- `services/speedtest-service.ts`: real ookla schema mapping —
  `download.bandwidth` / `upload.bandwidth` (bytes/s → Mbps, ÷125000),
  `ping.latency` (ms); handle `type: "result"` vs error payloads; surface
  failures as a result-state the UI can show (no more silent
  `catch {}`); keep the `running()` guard against double-clicks.
- Prefer Ookla when `speedtest` is installed; fall back to distro-provided
  `speedtest-cli --json` when it is absent, converting its bit/s values to
  Mbps. Provision the compatible CLI package on Arch and Debian-family.
- Auto-run switch: diagnose-then-fix the snap-back (ranked: file-persist
  failure reverted by `loadConfig` on next view-open vs. shared-state echo
  between the two mounted `WifiContent` instances vs. guard misclassification;
  the guarded `WifiSwitch` + explicit `setConfigValue` already landed — this
  change proves which layer snaps and fixes it, with a regression note
  recorded here).
- `WifiContent.tsx`: remove the `Last result` row from the speed-test
  section per approved mock (results live in the details table, change 2).

## Non-goals

- No running-state UI/event work (change 8 — this change makes `running()`
  and `lastResult()` truthful so 8 can consume them).
- No interval work (change 6).

## Mock anchors

- `state-2-stc-expanded` (Run button, auto-run switch, NO last-result row)
