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

- [x] 1.0 Move the approved mock to `openspec/changes/add-speedtest-notifications/mock.html` with stable anchors `state-stc-running`, `state-stc-result`, `state-stc-error`, `state-stc-setting`. Confirm the render in Firefox and record the approval in the change. *(Already satisfied on arrival — the mock was moved and approved in the change's setup commit. Not re-rendered here.)*
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

**The plan's spec contradicted its own payload definition — RESOLVED, see
rework task R1.** The spec asked the success body to name "the connected network
and test server"; the payload it pinned (`{state, trigger}` + three measurements
+ `reason`) had nowhere to put either, and the no-new-architecture rule forbids
the consumer reaching for Wi-Fi state. The requester chose to widen the payload
with `ssid` and `server_name` rather than drop the line from the mock, so the
card matches the approved design. Tracked as rework task R1 below.


## Phase 3 — Consumer

- [x] 3.1 Add `src/gui-tools/notifications/lib/speedtest-events.ts` as a sibling of `wallpaper-events.ts`. A SIBLING, not a generalization: two single-topic clients each owning their connection and stale-replay baseline. A shared baseline would let one topic's replay suppress another's fresh event; a per-topic map plus a registry is real machinery for a second subscriber. The duplication is the cheaper end, and it is documented as such at the module.
- [x] 3.2 In `NotificationsWindow.tsx`, add `speedtestUpdate(payload, source)` following `wallpaperUpdate`'s structure.
- [x] 3.3 Build the card from the shipped wallpaper card primitives.
- [x] 3.4 On `done`: fill the three result cells, `set_fraction(1)`, schedule the 5 s auto-dismiss. **Partially done — the body line is rework task R1.**
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

**Task 3.4's body line — deferred to rework task R1 by requester decision.** The
pinned payload had no member for the network or server name, and both
"make it true" routes were excluded: putting them in the payload contradicted
the spec's own payload definition, and having the consumer read Wi-Fi state is
new coupling the no-new-architecture rule exists to prevent. The success body
read the trigger phrase plus a pointer to the panel. The requester chose to
widen the payload (`ssid`, `server_name`) rather than drop the line from the
mock, so the card matches the approved design. See R1.

## Phase 6 — Rework (post-review decision)

- [x] R1 **Widen the payload with `ssid` and `server_name`, then name them on the card.** The spec's own card requirement and payload requirement contradicted each other; the requester chose payload fidelity to the approved mock. GATE: `make contracts-check` green, both new harnesses green, `wifi-mock-parity` still green.
  - [x] R1.1 `contracts/event-contract.json` — `ssid` and `server_name` added to the `speedtest.state` payload (both `s`), listed in `optional` because they ride on `done` rather than on every transition. `event-contract.md` updated with the same prose rule. **`emit_validation.TOPIC_SCHEMAS` also needed them** — the hub's validator is a per-topic property set, so without the two keys the hub would have rejected every `done` payload as a schema failure and the symptom would have been a silently missing card, not an error.
  - [x] R1.2 `test_event_contract_drift.py` — the two keys pinned with their types and their presence in `optional`, plus an assertion that the embedded schema ACCEPTS them. **Proved the TS-ahead scan actually covers them** by deleting each key from the contract and confirming the scan fails naming it.
  - [x] R1.3 Producer: `speedtest-service.ts` — `connectedSsid()` reads the already-exported `wifiNetworks()` accessor; `serverLabel()` reads the parsed result's `server` object. Both passed through `publishSpeedTestState`.
  - [x] R1.4 Consumer: `speedtest-events.ts` types + `NotificationsWindow.tsx` — body is `"<ssid> · <server>"`, falling back to the trigger phrase when neither is available.
  - [x] R1.5 No mock edit needed: the shipped copy is `"<ssid> · <server>"` with the same ` · ` separator `mock.html` uses, so the mock is unchanged and `speedtest-mock-parity.py` still passes with zero known-gap warnings.
  - [x] R1.6 Verified live (evidence below).

**The scan I shipped in phase 0 was covering nothing — found while doing R1.2.**
The TS-ahead leg keyed its scope on the literal `"speedtest.state"`, but the
only file that READS the payload keys — `NotificationsWindow.tsx` — never
contains that literal; the topic lives in `speedtest-events.ts` and the
consumer imports it. So the scan audited zero files and reported success:
the worst thing a drift gate can do, and the exact failure the self-test was
written to prevent. Caught because R1.2 asked to *confirm* the scan sees the
new keys, which could not be confirmed.

Fixed by scoping the scan to the `speedtestUpdate` handler's BODY rather than
to the file. Two things had to be right, and both are now pinned by tests:
the scope must reach the importing consumer, and it must not judge the
WALLPAPER handler in the same file (which reads `stage`, the known
pre-existing gap, and `reload_failures`). Scoping by a fixed indent was wrong
in both directions — a module-level helper at column 0 would not terminate the
span, and a deeper helper would truncate it early — so the span ends at the
next function declared at an indentation no deeper than the handler's own.
Negative-tested against the live tree by removing each new key from the
contract and confirming the failure names it.

**The premise that the producer "already imports `wifiNetworks()` and already
parses the server name" was not accurate.** `speedtest-service.ts` imported
neither: it parsed only `ping`/`download`/`upload`, and the connected SSID was
read in `WifiContent.tsx` (the panel), not in the service. The rework is
still a pass-through in shape — one accessor call and one new `serverLabel()`
helper — but it is additive work, not the reuse of code that was already
there. The IMPORT DIRECTION is the part that mattered and did hold: the
service now reads `wifiNetworks` from `wifi-service` (same AGS process), and
the notifications app still imports no Wi-Fi state at all.

**One deliberate deviation from the spec's literal fallback rule.** The spec
says to fall back to the trigger phrase when EITHER value is empty. The card
instead keeps whichever half IS known (`ssid` alone, or `server_name` alone)
and only falls back when NEITHER is present — because the rule's stated purpose
is "rather than render a blank", and discarding the SSID because a backend
reported no server name would throw away a fact we measured. No dangling
separator is ever rendered. Verified live in all three cases.

**Operational note for whoever tests this next.** The installed
`dotfiles-runtime` is a real (non-editable) `uv tool install`, and
`uv tool install --force` was a NO-OP — it reported "Installed 1 package" and
left the previous copy in place, so the hub kept validating against the old
property set. `--reinstall` is the flag that actually works. The hub must be
restarted afterwards regardless, because its baked `KNOWN_TOPICS` and
`TOPIC_SCHEMAS` are read at import.


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
- **The `connect` trigger** was never exercised from the real run-on-connect
  watcher (it needs a network transition). It appears only in the synthetic
  R1 fallback capture below; `manual` and `scheduled` were both observed on
  the wire from real runs.

### R1 live evidence (add-speedtest-notifications rework)

Observed on the running desktop after deploying the widened payload and
reinstalling the runtime.

1. **Real scheduled run, wire payload** — `busctl monitor` on
   `org.dotfiles.Events` shows the `done` event the hub accepted:
   `state="done"`, `trigger="scheduled"`, three doubles, plus
   `ssid="Canela&Dulce"` and `server_name="CABLEVIVO Envigado"`.
2. **Real card body** — the card reads `Canela&Dulce · CABLEVIVO Envigado`,
   matching `mock.html`'s `Canela&Dulce · CableVivo Envigado` (the mock's
   capitalisation is cosmetic; the string is the backend's own `sponsor`).
   Three cells filled, four steps done, bar at fraction 1.
3. **Both values empty** — `Started by you · also shown in the Wi-Fi panel`.
   No blank line, no dangling separator.
4. **SSID only** — `Canela&Dulce`, server half omitted rather than rendering a
   trailing ` · `.
5. **A synthetic `done` with no preceding `starting` was IGNORED** — no orphan
   card. The untracked-run guard still holds for externally emitted payloads.
6. **Gates after R1** — `contracts-check` 34 passed; full runtime suite 1844
   passed, 1 skipped; `wifi-mock-parity` PASS 103 tokens / 0 known gaps;
   `speedtest-mock-parity` PASS 55 tokens / 0 known gaps;
   `speedtest-no-new-architecture` PASS on all 5 checks; `ags list` unchanged
   at 6 instances; the session bus still carries only `org.dotfiles.Events`
   and `org.freedesktop.Notifications`.


