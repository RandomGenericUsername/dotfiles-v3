# Design: speed-test run feedback via events + animated bar card

## Event contract

- Reuse `lib/event-bus.ts` shared consumer (subscribe-before-read
  hydration, epoch/seq dedup — the same path capture/notifications use).
- Emit `speedtest.finished` with the contract's exact
  `{down_mbps, up_mbps, latency_ms}` payload on completion. The established
  topic schema has no `ranAt` or running-state fields, so neither is added.
- Run state is already shared in-process by the AGS service. Both the popup
  and bar card read that `running()` accessor; the result is published through
  the hub for other consumers. This avoids inventing a topic or weakening the
  hub's contract validation.

## UI work

- Run button (`WifiContent.tsx`): `visible`/`sensitive` swap on `running()`:
  `<Gtk.Spinner class="settings-spinner" spinning>` + `Testing…` label,
  `.stc-run-btn.running` (dimmed, default cursor). Matches `state-2b-running`.
- Bar card (`network.tsx` + `style.css`): toggle `.speedtesting` on the
  existing `.widget.network-widget` button from the subscribed running
  state; keyframes pulse `transparent ↔ alpha(@color_13, 0.22)` + border
  (mock: 1.6s ease-in-out infinite). When the test ends the class drops and
  the card fades back — no icon-path changes, no `bar_mappings` touched.

## Contract table

| Mock element | Code owner |
|---|---|
| Loader button (`state-2b-running`) | `running()`-driven button swap |
| Animated bar card (`bar-testing-card`) | `.speedtesting` class + keyframes |
| Untouched icon art | explicitly NO icon/template changes |

## Verification

- Parity gate → 0. Live: click Run → button loader + bar card pulsing
  within a frame; spam-clicks during run do nothing (guard); on finish,
  button restores + card fades + result lands (change 7's mapping).
  Screenshot both mock frames mid-run.
