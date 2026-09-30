# add-speedtest-notifications

## Why

The speed test runs on a timer and reports nothing. A measurement completes, the panel's Download/Upload/Ping rows update, and if you are not looking at the panel at that moment the result is simply gone until the next interval. There is no signal that a test ran, no indication it failed, and no record in the notification surface the rest of the desktop already uses.

The architecture for this already exists and is proven — it is exactly how a wallpaper change reports itself. The notification app (`src/gui-tools/notifications/`) subscribes to a domain event and builds a bespoke card that it **mutates in place**: one card, a fixed step checklist, an indeterminate `Gtk.ProgressBar.pulse()` while busy, `set_fraction(1)` on completion, and a 5 s auto-dismiss. It deliberately never calls `Notify` and never uses `replaces_id`.

The producer half is already built and unwired. `publishSpeedTestFinished()` in `dotfiles/config/ags/lib/event-bus.ts` emits `speedtest.finished` on `org.dotfiles.Events` from `speedtest-service.ts` on every successful run — and **nothing subscribes to it**. A publisher with no consumer. This change adds the consumer, extends the event to cover the whole lifecycle, and gates it behind a setting.

The approved mock is `mock.html` (this directory), showing four states: running, result, failure, and the settings row.

## What Changes

- **New domain topic `speedtest.state`** replacing `speedtest.finished`, carrying `{ state, trigger, ssid, server_name }` with `state ∈ { starting, done, error }` and `trigger ∈ { scheduled, manual, connect }`. This mirrors the `wallpaper.state` contract shape (`state` + `wallpaper_hash` + `trigger`) rather than inventing a new envelope, so the existing subscribe-before-read and stale-replay guards in `event-bus-core.ts` apply unchanged. `ssid` and `server_name` are carried on `done` so the card can name what it measured; the producer already holds both (it imports Wi-Fi state and parses the server from the result), so this is a pass-through rather than new coupling.
- **Producer**: `speedtest-service.ts` emits `starting` when a run begins and `done` / `error` at the terminal transition. It already holds every state transition needed, and already has a watchdog that produces the `error` edge.
- **Consumer**: `src/gui-tools/notifications/lib/speedtest-events.ts`, a sibling of the existing `wallpaper-events.ts` (single-topic, single-handler, subscribe-before-read), plus a `speedtestUpdate()` handler in `NotificationsWindow.tsx` built from the wallpaper card code.
- **Card**: one in-place-mutated card, four fixed steps (Test scheduled → Latency measured → Download measured → Upload measured), a pulsing bar while running, a three-cell result grid on completion, and a caution-tinted sticky card on failure.
- **Setting**: `notify_on_test: boolean` added to `SpeedTestConfig` (default `true`), persisted through the existing `wifi-speedtest.json` path, with a row matching the shipped `run_on_connect` pattern (`settings-stc-row` + `settings-stc-label` + `WifiSwitch`).

## Capabilities

### New Capabilities

- `speedtest-notifications`: the `speedtest.state` event contract, the producer's phase emission and gating, the notification app's progress card, and the settings toggle.

### Modified Capabilities

*(None — `speedtest.finished` has no subscriber today, so nothing observable changes. It is superseded rather than altered.)*

## Impact

- **Event contract**: `contracts/event-contract.json` — `speedtest.finished` is replaced by `speedtest.state` with the enum pinned. **This is the gate**: the wallpaper card already reads a `stage` key that is not in the pinned contract (TS ahead of contract). The new keys are added to the contract and pinned by a drift test; the drift gate must be green before implementation proceeds, and the pre-existing `stage` discrepancy is called out rather than repeated.
- **Producer**: `dotfiles/config/ags/lib/event-bus.ts` (rename publisher, add `state`/`trigger`), `services/speedtest-service.ts` (phase emission, config field, gate).
- **Consumer**: new `src/gui-tools/notifications/lib/speedtest-events.ts`; `ui/NotificationsWindow.tsx` (handler + card); `style.css` (`speedtest-progress-*` rules on `@color_*` tokens only).
- **Panel**: `components/wifi/WifiContent.tsx` (the setting row only).
- **Provisioning**: none — the notifications app is already deployed and autostarted.
- **Anti-drift harnesses** (the reason this change is gated the way it is):
  - `scripts/speedtest-mock-parity.py` — same shape as `wifi-mock-parity.py`: every class token in each anchored mock state must resolve to a class shipped in the notifications `style.css` or the mapped TSX, via a literal, a `CLASS_MAP` entry, or a tracked `KNOWN_GAP`. Mock scaffolding is allowlisted with a reason.
  - `scripts/speedtest-no-new-architecture.py` — asserts the implementation reuses the existing seams rather than adding new ones: no new AGS instance, no new notification bus name, no `Notify` call and no `replaces_id` from the speed-test path, and `speedtest-events.ts` must not introduce a second polling timer or a second D-Bus connection beyond the wallpaper module's pattern.
  - Both run in CI; a failure names the state and token, as the existing gate does.
- **Out of scope for v1**: notification history, per-test actions (Open/Retry — the result is already in the panel), trend graphs, threshold alerts ("your speed dropped"), and closing the pre-existing gap where the capture tool's `notifications` preference has no AGS UI row.
