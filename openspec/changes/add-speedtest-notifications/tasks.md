# Tasks: add-speedtest-notifications

Ordered so every gate is written and green before the code it polices exists, and so the contract is pinned before any producer or consumer is built.

## Phase 0 — Contract first (GATE)

- [ ] 0.1 In `contracts/event-contract.json`, replace the `speedtest.finished` topic with `speedtest.state`: payload `{ state, trigger }`, `state` enum `["starting", "done", "error"]`, `trigger` enum `["scheduled", "manual", "connect"]`, with `down_mbps`/`up_mbps`/`latency_ms` required on `done` and a short `reason` on `error`. Mirror the `wallpaper.state` entry's structure (producer, payload, enum, cadence, notes).
- [ ] 0.2 Extend the event-contract drift test to pin the new keys and both enums, and to fail when a `speedtest.state` payload key is read by TypeScript but absent from the contract. GATE: `make contracts-check` is green before task 1.0. NOTE the pre-existing discrepancy — the wallpaper card reads a `stage` key that was never pinned; do not repeat it, and record it as a known issue rather than widening this change to fix it.
- [ ] 0.3 Confirm with the requester that superseding `speedtest.finished` (rather than adding a second topic) is acceptable — it currently has no subscriber, so nothing observable changes.

## Phase 1 — Harnesses before code (GATE)

- [ ] 1.0 Move the approved mock to `openspec/changes/add-speedtest-notifications/mock.html` with stable anchors `state-stc-running`, `state-stc-result`, `state-stc-error`, `state-stc-setting`. Confirm the render in Firefox and record the approval in the change.
- [ ] 1.1 Write `scripts/speedtest-mock-parity.py` modelled line-for-line on `scripts/wifi-mock-parity.py`: `ANCHORS`, `STATE_TSX` (mapping each state to `src/gui-tools/notifications/ui/NotificationsWindow.tsx`, `src/gui-tools/notifications/style.css`, and `dotfiles/config/ags/components/wifi/WifiContent.tsx` for the settings row), `ALLOWLIST` (mock page chrome only, each with a reason), `CLASS_MAP` (mock token → shipped class, e.g. `stack`/`col`/`notif-card` → `notif-card`, `progress-card` → `wallpaper-progress-card`-style shipped equivalent, `tile` → `notif-tile`, `step` → `wallpaper-progress-step`, `bar` → `wallpaper-progress-bar`, `cell` → the shipped result cell, `s-row`/`s-label` → `settings-stc-row`/`settings-stc-label`, `toggle` → `settings-switch`), and an empty `KNOWN_GAPS`. GATE: exits 0 against the current (unimplemented) tree with every mock token landing in `KNOWN_GAPS` as a loud warning — proving the harness runs and reports honestly rather than passing vacuously.
- [ ] 1.2 Write `scripts/speedtest-no-new-architecture.py`: assert no `Notify`/`replaces_id` in the speed-test path, no new AGS instance name beyond `{ags, capture, notifications, hypr-pano}`, no second event-bus client in the notifications app beyond `speedtest-events.ts`, no `GLib.timeout_add` poll in `speedtest-events.ts`, and no new well-known D-Bus name. GATE: exits 0 today.
- [ ] 1.3 Wire both into CI alongside the existing wifi parity gate, so a future change cannot quietly drop them.

## Phase 2 — Producer

- [ ] 2.1 In `dotfiles/config/ags/lib/event-bus.ts`, replace `publishSpeedTestFinished` with `publishSpeedTestState(state, trigger, measurements?)` emitting `speedtest.state` with the contract's shape; keep it non-fatal when the hub is absent, and log like the current publisher does.
- [ ] 2.2 In `services/speedtest-service.ts`, emit `starting` with the correct `trigger` at the top of `runSpeedTest` (distinguish scheduled / manual / connect — thread the trigger through from the scheduler, the Run-now button, and the run-on-connect watcher), and exactly one terminal `done` or `error` on every exit path, including the watchdog abandonment.
- [ ] 2.3 Add `notify_on_test: boolean` (default `true`) to `SpeedTestConfig`, `DEFAULT_CONFIG`, and the `loadConfig` merge; a file without the key loads the default and does not trigger a write. Persist through the existing `saveConfig` path so it lands in `wifi-speedtest.json` beside the interval.
- [ ] 2.4 Gate emission on `notify_on_test` in the producer, before any event is built — the fail-open rule the capture tool uses: when off, nothing is constructed and nothing is emitted, while the run still executes and the panel still updates.
- [ ] 2.5 GATE: `speedtest-no-new-architecture.py` still exits 0 (the producer must not call `Notify`).

## Phase 3 — Consumer

- [ ] 3.1 Add `src/gui-tools/notifications/lib/speedtest-events.ts` as a sibling of `wallpaper-events.ts`: same single-topic/single-handler/subscribe-before-read shape, same stale-replay guard on `(epoch, seq)`, same `NameOwnerChanged` re-hydration. No polling.
- [ ] 3.2 In `NotificationsWindow.tsx`, add `speedtestUpdate(payload, source)` following `wallpaperUpdate`'s structure: create the card on `starting` if none matches, mutate in place, and treat a `done`/`error` payload for an unknown or superseded run as ignorable.
- [ ] 3.3 Build the card from the shipped wallpaper card primitives: `.notif-card` base, `CARD_WIDTH`, the icon tile, title, body, close button, `Gtk.ProgressBar` with `pulse()` at 100 ms while busy, the four-step checklist with the `○`/`·`/`✓`/`!` markers, and the footer. Reuse the step-row CSS rather than duplicating it — factor the shared step/checklist rendering out of the wallpaper card if that is the smaller change, and note the refactor in the change.
- [ ] 3.4 On `done`: fill the three result cells (Download / Upload / Ping) to match the panel's row split, set the body to the connected network and server, `set_fraction(1)`, and schedule the 5 s auto-dismiss.
- [ ] 3.5 On `error`: mark the current step failed with `!`, render the caution treatment, state that the next interval will retry, and do not auto-dismiss.
- [ ] 3.6 Add `speedtest-progress-*` rules to the notifications `style.css` on `@color_*` tokens only — no literal colours, no new token. Reuse the existing `.wallpaper-progress-*` rules wherever they already express the intent.
- [ ] 3.7 GATE: `speedtest-no-new-architecture.py` exits 0; `speedtest-mock-parity.py` now passes with `KNOWN_GAPS` emptied as each class ships.

## Phase 4 — Setting UI

- [ ] 4.1 In `WifiContent.tsx`, add the preference row inside the existing speed-test section, matching the `run_on_connect` row exactly: `settings-stc-row` + `settings-stc-label` + `WifiSwitch` bound to a `createComputed` over `getConfig().notify_on_test`, with `onToggled={(v) => setConfigValue({ notify_on_test: v })}`.
- [ ] 4.2 Confirm the row respects the panel's keyboard-mode rule — a `Gtk.Switch` needs no typed input, so the panel's `ON_DEMAND` condition must NOT be widened for it (that condition exists for the two `Gtk.Entry` fields only).

## Phase 5 — Verification

- [ ] 5.1 `make contracts-check` green; both new harnesses green; existing `wifi-mock-parity.py` still green (the settings row touches a file it maps).
- [ ] 5.2 Manual: toggle off → a run completes with no card, panel rows still update, and the measurement still persists across a restart. Toggle on → a card appears at `starting`, mutates in place, and settles on the result.
- [ ] 5.3 Manual: force a failure (point the service at a bad server, or stop the network mid-run) → caution card, persists, names the step, no retry storm.
- [ ] 5.4 Manual: confirm no new `ags list` instance and no new bus name on the session bus.
- [ ] 5.5 Confirm the card honours a wallpaper palette swap (`colors.css` reapply) like every other notification card.
- [ ] 5.6 Record the outcome in the change and clear any remaining `KNOWN_GAPS` entries.
