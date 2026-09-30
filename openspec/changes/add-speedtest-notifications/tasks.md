# Tasks: add-speedtest-notifications

Ordered so every gate is written and green before the code it polices exists, and so the contract is pinned before any producer or consumer is built.

## Phase 0 — Contract first (GATE)

- [x] 0.1 In `contracts/event-contract.json`, replace the `speedtest.finished` topic with `speedtest.state`: payload `{ state, trigger }`, `state` enum `["starting", "done", "error"]`, `trigger` enum `["scheduled", "manual", "connect"]`, with `down_mbps`/`up_mbps`/`latency_ms` required on `done` and a short `reason` on `error`. Mirror the `wallpaper.state` entry's structure (producer, payload, enum, cadence, notes).
- [x] 0.2 Extend the event-contract drift test to pin the new keys and both enums, and to fail when a `speedtest.state` payload key is read by TypeScript but absent from the contract. GATE: `make contracts-check` is green before task 1.0. NOTE the pre-existing discrepancy — the wallpaper card reads a `stage` key that was never pinned; do not repeat it, and record it as a known issue rather than widening this change to fix it.
- [x] 0.3 Confirm with the requester that superseding `speedtest.finished` (rather than adding a second topic) is acceptable — it currently has no subscriber, so nothing observable changes.

**Deviation from the plan's Impact section — the rename ripples further than listed.**
The proposal named only `contracts/event-contract.json`. The topic is also baked
into five other places, all of which are drift-gated and had to move with it:
`runtime/domain/hub.py` `KNOWN_TOPICS` (the hub rejects off-table topics),
`runtime/adapters/emit_validation.py` `TOPIC_SCHEMAS` (compiled per known
topic), `runtime/adapters/bar_subscriber.py` `BAR_TOPICS`, the Python
`SpeedTestJob` publisher, `event-bus-core.ts` in both the AGS bar and its
`hypr-pano` sibling, the icon-color-mapping-editor node drift test, and six
test files. Nothing was added — every one of these is an existing copy of a
constant the change renames.

`SpeedTestJob` needed a decision the plan does not mention: the new payload
requires `trigger`, and the job has no trigger notion (it is a supervised
lifetime job, never user-initiated). It declares `scheduled` explicitly and
emits only the terminal half — the `starting` edge belongs to whoever
schedules the run, which is the AGS service.


## Phase 1 — Harnesses before code (GATE)

- [x] 1.0 Move the approved mock to `openspec/changes/add-speedtest-notifications/mock.html` with stable anchors `state-stc-running`, `state-stc-result`, `state-stc-error`, `state-stc-setting`. Confirm the render in Firefox and record the approval in the change.
- [x] 1.1 Write `scripts/speedtest-mock-parity.py` modelled line-for-line on `scripts/wifi-mock-parity.py`. GATE verified: exits 0 on the unimplemented tree with **56** known-gap warnings, and it was separately proven to fail on all three spec scenarios (uncovered token, broken mapping, missing mapped file) by running it against a scratch tree with `KNOWN_GAPS` emptied.
- [x] 1.2 Write `scripts/speedtest-no-new-architecture.py`. GATE verified: exits 0 today, and separately proven to fail on all six spec scenarios by injecting each violation into a scratch tree.
- [x] 1.3 Wire both into CI alongside the existing wifi parity gate, so a future change cannot quietly drop them.

**Two additions to the wifi harness's table set, each forced by this mock.**
- `RUNTIME_BEHAVIOUR` — the mock DRAWS the indeterminate pulse as a CSS
  animation (`.bar.pulse > i`); the shipped code pulses the `Gtk.ProgressBar`
  from its 100 ms timer, because GTK4 has no CSS pulse. The mock token is real
  and gated, but the thing that satisfies it is a CALL, not a selector. Without
  this table the harness would have forced a dead CSS class into the stylesheet.
- `STATE_MODIFIER_BASES` — the mock composes state as `class="step active"`
  while the code expresses it as `.speedtest-progress-step.active`. Resolved by
  construction so a NEW modifier is still caught, and only against bases whose
  mock token is present in that state.

**One ordering deviation.** `KNOWN_GAPS` is checked BEFORE `CLASS_MAP` (the
wifi harness checks `CLASS_MAP` first, but its `KNOWN_GAPS` is always empty so
the ordering never surfaces). With `CLASS_MAP` first, the day-one gate would
have FAILED on classes that simply had not shipped yet — the mapping branch
verifies its target exists. The two tables are kept disjoint so a token can
never be reported as a warning while its mapping sits untested behind it.

**CI reality.** There was no CI to wire into: `.github/` held only agent
prompts and skills, and `wifi-mock-parity.py` was run by hand. `.github/workflows/gates.yml`
was added running all four gates as separate jobs, and `make gates` runs the
same four locally so a green local run is a green CI run.


## Phase 2 — Producer

- [x] 2.1 In `dotfiles/config/ags/lib/event-bus.ts`, replace `publishSpeedTestFinished` with `publishSpeedTestState(state, trigger, measurements?)`.
- [x] 2.2 In `services/speedtest-service.ts`, emit `starting` with the correct `trigger` at the top of `runSpeedTest`, and exactly one terminal `done` or `error` on every exit path, including the watchdog abandonment.
- [x] 2.3 Add `notify_on_test: boolean` (default `true`) to `SpeedTestConfig`, `DEFAULT_CONFIG`, and the `loadConfig` merge.
- [x] 2.4 Gate emission on `notify_on_test` in the producer, before any event is built.
- [x] 2.5 GATE: `speedtest-no-new-architecture.py` still exits 0.

**One terminal event per run needed a real guard.** The watchdog and the
`execAsync` promise race: whichever loses would have published a second
terminal event and left the card showing a result the other path had already
overwritten. A `settled` latch on the first terminal emission makes the second
impossible, which is the only way "exactly one of `done`/`error`" survives the
race. The watchdog abandonment is a terminal `error`, not silence — the user
(or the timer) asked and nothing came back.

**`setConfigValue` needed a guard it did not previously need.** It restarts the
scheduler on every call, which was correct while every config field was a
scheduler input. Adding a presentational field meant a notification-preference
flip would silently reset how long was left on the interval timer. Now only
`interval_ms` and `run_on_connect` restart it.

**One place the plan's spec and its own payload definition conflict — see
`known-issues.md` and the note under task 3.4.** The spec asks the success body
to name "the connected network and test server"; the payload it pins
(`{state, trigger}` + three measurements + `reason`) has nowhere to put either,
and the no-new-architecture rule forbids the consumer reaching for Wi-Fi state.
Implemented as the trigger phrase plus a pointer to the panel, and flagged
rather than silently widened.


## Phase 3 — Consumer

- [x] 3.1 Add `src/gui-tools/notifications/lib/speedtest-events.ts` as a sibling of `wallpaper-events.ts`. A SIBLING, not a generalization: two single-topic clients each owning their connection and stale-replay baseline. A shared baseline would let one topic's replay suppress another's fresh event; a per-topic map plus a registry is real machinery for a second subscriber. The duplication is the cheaper end, and it is documented as such at the module.
- [x] 3.2 In `NotificationsWindow.tsx`, add `speedtestUpdate(payload, source)` following `wallpaperUpdate`'s structure.
- [x] 3.3 Build the card from the shipped wallpaper card primitives.
- [x] 3.4 On `done`: fill the three result cells, `set_fraction(1)`, schedule the 5 s auto-dismiss.
- [x] 3.5 On `error`: mark the step failed with `!`, render the caution treatment, state that the next interval will retry, do not auto-dismiss.
- [x] 3.6 Add `speedtest-progress-*` rules to the notifications `style.css` on `@color_*` tokens only.
- [x] 3.7 GATE: `speedtest-no-new-architecture.py` exits 0; `speedtest-mock-parity.py` passes with `KNOWN_GAPS` drained to zero entries.

**Task 3.3's "factor the shared rendering if that is the smaller change" — it
was not, so nothing was refactored.** GTK4 has no selector aliasing, so the
shared step/marker/label intent can only be expressed by naming both selectors
in one rule (`.wallpaper-progress-step.active .speedtest-progress-step-label,
.speedtest-progress-step.active .speedtest-progress-step-label`). Factoring the
card construction into a shared builder would have meant threading ~14 closure
variables through it — the wallpaper card's widget references are closure state
by design — which is a far larger change to a working, unrelated card than two
selector lists.

**The card has no `wallpaperHash` to key on, and does not need one.** The
wallpaper card keys on the hash because several wallpaper operations can be in
flight at once. A speed test is serialised by construction — the service's
`if (running()) return` guard rejects a second run outright — so at most one
speed-test run exists, and one boolean replaces the hash.

**The two cards may be on screen at once, and neither dismisses the other.**
This is the hazard `design.md` asked to be decided explicitly. A speed test
says nothing about the wallpaper's lifecycle, so dropping the wallpaper card
because a measurement started would be a lie about what happened; both cards
`prepend`, newest on top. A *previous speed-test* card IS superseded by a new
run, though — its steps and result describe a run that no longer exists — so
`starting` dismisses it before creating the replacement. Verified live: two
consecutive failures leave exactly one card.

**Task 3.4's "set the body to the connected network and server" — NOT DONE, and
this is the one place reality contradicted the plan.** The pinned payload has no
member for either value, and the two available "make it true" routes are both
excluded: putting them in the payload contradicts the spec's own payload
definition, and having the consumer read Wi-Fi state is new coupling the
no-new-architecture rule exists to prevent. The success body reads the trigger
phrase plus a pointer to the panel instead ("Scheduled run · also shown in the
Wi-Fi panel"). Closing this properly needs a payload change, which is a spec
change, not an implementation detail — raised rather than guessed at.

**No percentage anywhere.** The bar is pulsed from a 100 ms timer while in
flight, `set_show_text(false)` so Gtk prints no `0%` either, `set_fraction(1)`
on success, and `set_fraction(0)` on failure (a run that did not finish must
not read as done). There is nothing to interpolate: `speedtest-cli --json`
returns one blob at the end.


## Phase 4 — Setting UI

- [x] 4.1 In `WifiContent.tsx`, add the preference row inside the existing speed-test section, matching the `run_on_connect` row exactly.
- [x] 4.2 Confirm the row respects the panel's keyboard-mode rule.

## Phase 5 — Verification

- [x] 5.1 `make contracts-check` green; both new harnesses green; existing `wifi-mock-parity.py` still green.
- [x] 5.2 Manual: toggle off → run completes with no card, measurement still persists. Toggle on → card appears at `starting`, mutates in place, settles on the result.
- [x] 5.3 Manual: forced failure → caution card, persists, names the step, no retry storm.
- [x] 5.4 Manual: no new `ags list` instance and no new bus name.
- [~] 5.5 Confirm the card honours a wallpaper palette swap (`colors.css` reapply). **PARTIAL** — the card renders entirely from `@color_*` tokens (no literal colour appears in the new rules), so it restyles with the palette by construction, and it was observed rendering in the live desktop's accent (an orange `@color_06`/bar and `@color_03`/caution). A live wallpaper swap was NOT performed: changing the user's wallpaper to produce a screenshot is a visible side effect on their desktop, and was not authorised. The wallpaper card's `refreshPaletteCss()` path is unchanged and the notification app already re-applies `colors.css` on every wallpaper event, which is the same mechanism the existing cards rely on.
- [x] 5.6 Record the outcome in the change and clear any remaining `KNOWN_GAPS` entries (drained to zero).

### Verification record

Gates (all green, `make gates`):

| Gate | Result |
| --- | --- |
| `contracts-check` | 33 passed |
| full runtime suite | 1843 passed, 1 skipped |
| `wifi-mock-parity` | PASS — 8 states, 103 tokens, 0 known-gap warnings |
| `speedtest-mock-parity` | PASS — 4 states, 55 tokens, 0 known-gap warnings |
| `speedtest-no-new-architecture` | PASS — all 5 checks |
| `ags bundle` (notifications + main) | clean |
| hypr-pano / icme / wallpaper-selector node drift tests | all green |

Live behaviour, observed on the running desktop (screenshots taken with `grim`
against the real notification stack, events observed with `busctl monitor`):

1. **Running** — `starting` then `done` on `speedtest.state`; one card at
   `starting`, bar pulsing, steps `✓ / · / ○ / ○`, footer naming the trigger.
2. **Result** — the SAME card mutated in place: title/body changed, bar at
   fraction 1, the three cells filled (Download / Upload / Ping, matching the
   panel's split), all four steps `✓`.
3. **Auto-dismiss** — captured the card, then 8 s later: gone.
4. **Failure** — forced by shadowing both `speedtest` and `speedtest-cli` on
   `PATH` with a script emitting non-JSON. Caution card, `!` on the step it
   stopped at, "It will retry on the next interval.", bar NOT full. Still on
   screen 20 s later — sticky, as specified.
5. **Supersession** — with a failing run every 20 s, the second failure left
   exactly ONE card. The stale card was replaced, not stacked.
6. **Preference off** — `notify_on_test: false` persisted to
   `wifi-speedtest.json`, service restarted: **zero** `speedtest.state` events
   over a full interval, while `wifi-speedtest-last.json` was rewritten with a
   fresh measurement. The run still happened and the measurement still stuck.
7. **Preference back on** — card returns.
8. **No new surface** — `ags list` unchanged across every restart.

Deployment note: `~/.config/ags` is a symlink to a plain deployed COPY, so each
changed file was `cp`'d. The installed `dotfiles-runtime` is a real
(non-editable) `uv tool install`, so it was reinstalled
(`uv tool install --force src/runtime`) and the hub restarted — otherwise the
live hub's baked `KNOWN_TOPICS` would have rejected `speedtest.state` as
`UnknownTopic`.

### Not verified

- **The settings row was never seen on screen.** There is no keybind for the
  settings panel (it opens from a tray click) and no input-injection tool
  (`wtype`/`ydotool`) is installed, so opening it non-destructively was not
  possible. Its correctness rests on the parity gate resolving `s-row`,
  `s-label`, `s-sub`, `toggle` and `s-title` against `WifiContent.tsx` and
  `WifiSwitch.tsx`, a clean `ags bundle`, and a live read of the persisted
  value. The row's LAYOUT should be eyeballed once by the requester.
- **Live wallpaper palette swap** (task 5.5) — see above.
- **The `connect` trigger** was never exercised: the run-on-connect watcher
  needs a network transition. The `manual` and `scheduled` triggers were both
  observed on the wire.

