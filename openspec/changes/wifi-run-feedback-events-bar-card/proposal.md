# Proposal: speed-test run feedback via events + animated bar card

## Why

Today a test run is invisible: no loader, no state, repeated clicks pile up
behind the `running()` guard with zero feedback. Owner requirement: emit run
state over the project's event hub, swap the Run button for a loader while
running, and animate the status-bar Wi-Fi icon's card (transparent ↔
scheme-color transition) for the duration.

## What Changes

- `services/speedtest-service.ts`: emit the contract-shaped finished result
  on the existing hub surface (`speedtest.finished`). Running state stays in
  the shared AGS service accessor and drives the popup and bar directly; the
  topic schema does not define a started state.
- `components/wifi/WifiContent.tsx`: Run button consumes the truthful
  `running()` from change 7 — swaps label for `Gtk.Spinner` + `Testing…`
  (`.stc-run-btn.running`), insensitive while running.
- `bar/widgets/network.tsx` + `style.css`: button gains a `.speedtesting`
  class while a test runs (subscribed via the hub like other bar consumers,
  thin-consumer discipline); CSS animates the card background
  transparent ↔ scheme accent (`@keyframes`, 1.6s ease-in-out — as mocked);
  **icon art untouched** (bar group stays guard-clean, no re-render).

## Non-goals

- No new hub infrastructure (reuse `event-bus.ts` consumer + hub `Control`
  surface as-is).
- No changes to test logic/parse (change 7).
- No status-bar icon swaps — class-only change, deliberately.

## Mock anchors

- `state-2b-running` (loader button)
- `bar-testing-card` (animated card demo)
