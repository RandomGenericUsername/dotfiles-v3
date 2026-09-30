# Design: add-speedtest-notifications

## Context

A speed-test run completes silently. The panel's Download/Upload/Ping rows update, and if you are not looking at the panel the measurement is gone until the next interval. Failures are quieter still — `lastError` is only visible with the section expanded.

The fix is not new machinery. Two halves of the plumbing already exist:

1. **A proven progress-reporting model.** The wallpaper change already reports itself, and its implementation is unusual and worth copying exactly: the notification app subscribes to `wallpaper.state` and builds a **bespoke card it mutates in place**. It never calls `org.freedesktop.Notifications.Notify`, never uses `replaces_id`, and never sends a burst of per-phase notifications. It holds widget references in closure variables (`wallpaperProgress`, `wallpaperTitle`, `wallpaperStepRows`, …) and mutates them from a single event handler.

2. **An unwired producer.** `publishSpeedTestFinished()` in `dotfiles/config/ags/lib/event-bus.ts` already emits `speedtest.finished` on `org.dotfiles.Events`, called from `speedtest-service.ts` on every successful run. Nothing subscribes.

So the work is: widen the existing event to cover the run's lifecycle, add the consumer beside the wallpaper one, and gate it.

## The reuse mapping (this is the core constraint)

Every element in the proposal maps onto something that already exists. The design's job is to make inventing anything new *hard*, which is what the two harnesses do.

| Need | Reuse | Do NOT |
|---|---|---|
| Deliver a card | `NotificationsWindow` stack, `.notif-card`, `CARD_WIDTH` | Call `Notify` from the producer |
| Progress UI | `wallpaper-progress-card` construction + `setWallpaperStatus` step treatment | Build a second progress widget family |
| Indeterminate progress | `Gtk.ProgressBar.pulse()` at 100 ms | Show a percentage — see below |
| Event client | `lib/wallpaper-events.ts` shape, copied | Add a polling loop or a second bus client |
| Payload envelope | `wallpaper.state`'s `{ state, trigger }` | Invent a new envelope shape |
| Stale-replay guard | `event-bus-core.ts`'s `(epoch, seq)` check | Re-derive it |
| Setting row | `run_on_connect` row + `WifiSwitch` | Add a new toggle primitive |
| Setting storage | `SpeedTestConfig` + `wifi-speedtest.json` | A second config file or a new key namespace |
| Palette | `@color_*` tokens; caution via existing critical treatment | Literal colours or new tokens |

## Why the progress bar pulses instead of showing a percentage

`speedtest-cli --json` returns a single JSON blob when the run completes. It reports no intermediate progress, and the producer has no way to learn a fraction. A determinate bar would require inventing a number, and a plausible-looking wrong number is worse than an honest indeterminate one: it would imply the system knows something it does not.

The four-step checklist gives the eye something to land on without claiming precision — and the steps are not invented either, they are the order the tool actually performs: latency, then download, then upload.

## Why one card, not a burst

A run is one logical operation. Four separate notifications would be noise, and each would need its own dismissal. The wallpaper model already solves this with in-place mutation plus a single keyed card, and the keying question is handled by the same `hash`-style matching it uses: a terminal payload for a run we are not tracking is ignored rather than rendered as an orphan card.

## Why the event is superseded, not extended

`speedtest.finished` has no subscriber, so widening it to `speedtest.state` is observationally free. Adding a second topic alongside it would leave two ways to say "a speed test happened" and invite drift. `trigger` is included because the card's footer and the failure copy both benefit from distinguishing a scheduled run from a manual one, and because `wallpaper.state` already established `trigger` as the convention for naming the operation that produced a transition.

## Contract discipline — the one real hazard

The wallpaper card reads a `stage` key that is **not in the pinned contract** at `contracts/event-contract.json`. The TypeScript is ahead of the contract, and the drift test only pins `state`, `wallpaper_hash`, `trigger`, and their enums. That gap is exactly what the drift gate exists to prevent, and it is why Phase 0 is a hard gate here: every key and enum this change introduces is pinned in the contract and asserted by the drift test *before* any producer or consumer code is written.

The pre-existing `stage` discrepancy is recorded, not fixed — widening this change to repair another capability's contract is how changes stop being reviewable. It belongs in its own change.

## Harness design

`scripts/speedtest-mock-parity.py` follows `scripts/wifi-mock-parity.py` closely rather than inventing a new mechanism: same `ANCHORS` / `STATE_TSX` / `ALLOWLIST` / `CLASS_MAP` / `KNOWN_GAPS` structure, same per-token resolution (literal in the notifications `style.css`, literal in the mapped TSX, or a `CLASS_MAP` entry naming the shipped equivalent), same loud failure naming the state and token, same exit codes. Reusing the shape means the maintainer already knows how to read its output and how to clear a `KNOWN_GAP` when a class ships.

Its gate on day one is deliberately inverted: written before the implementation, it must exit 0 *with every mock token in `KNOWN_GAPS` as a warning*. That proves the harness genuinely runs and reports — a parity gate that passes vacuously because nothing matched would be worse than no gate.

`scripts/speedtest-no-new-architecture.py` is the anti-invention check, and it exists because "reuse the existing architecture" is otherwise unenforceable prose. Each assertion maps to a specific way this change could quietly grow a new surface: a `Notify` call sneaking into the producer (the most likely failure, because it is how capture does it and it looks reasonable), a new instance name, a second event-bus client, a polling loop, a new well-known bus name.

## Risks

- **Trigger threading.** `run_onTest` is called from three places (scheduler, Run-now, run-on-connect watcher) and the trigger must be correct at each. Threading a parameter through is mechanical but touches the run path; a wrong trigger shows up only as wrong footer copy.
- **Card lifecycle vs. the wallpaper card.** Both are singleton cards in one stack. The wallpaper card uses `stack.prepend` and holds a `wallpaperHash`; the speed-test card must not collide with it or with a previous speed-test card. Worth deciding explicitly whether the two progress cards can be visible simultaneously (two `prepend`s, newest on top) or whether one dismisses the other.
- **Palette reapply.** The card must restyle on a wallpaper swap like every other card, which it gets for free from `colors.css` — but only if no literal colour slipped into the new rules.
