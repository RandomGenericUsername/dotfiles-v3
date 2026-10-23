# Known issues recorded, not fixed, by this change

## `wallpaper.state` `stage` key is read by TypeScript but absent from the pinned contract

**Status:** pre-existing. Recorded here so `add-speedtest-notifications` does not
repeat it, and deliberately **not** repaired here.

`wallpaper.state` in `contracts/event-contract.json` pins exactly three payload
members: `state`, `wallpaper_hash`, `trigger` (with `trigger` marked optional).

Two consumers read a fourth member the contract does not declare:

- `src/gui-tools/notifications/ui/NotificationsWindow.tsx` — `wallpaperUpdate()`
  reads `payload["stage"]` and routes it through `stageIndex()` /
  `statusForStage()` / `failureForStage()`.

The publisher half lives outside this repo (the `wallpaper.state` emitter is a
`dotfiles-runtime` command), so only the consumer's reads are visible here — but
`emit_validation.py` accepting `stage` proves a publisher does send it.

`src/runtime/src/runtime/adapters/emit_validation.py` DOES carry a `stage`
property in its embedded `wallpaper.state` schema (with a seven-value enum), so
the hub accepts the payload — the contract JSON is the side that fell behind, not
the validator. That means the drift is invisible to the current gates: nothing
cross-checks the JSON's `payload` block against the embedded schema's property
set, so TypeScript can stay arbitrarily far ahead of the machine definition
without a test failing.

**Why this change does not fix it.** Pinning `stage` (and its enum) in
`contracts/event-contract.json` is a change to the `wallpaper.state`
capability's contract. Folding it in here would mean this change is no longer
reviewable on its own terms, and would couple two independent capabilities'
contract revisions to one approval. It belongs in its own change.

**How this change avoids repeating it.** `speedtest.state` pins every key it
introduces — `state`, `trigger`, `down_mbps`, `up_mbps`, `latency_ms`,
`reason` — and both enums, and
`src/runtime/tests/unit/test_event_contract_drift.py` gained a TS-ahead leg
(`test_ts_speedtest_keys_are_all_pinned`) that fails when a TypeScript file
naming `speedtest.state` reads a payload key the contract does not declare.
The scanner is self-tested (`test_ts_speedtest_key_scanner_flags_drift_self_test`)
so it cannot pass vacuously. The wall is scoped to `speedtest.state` on
purpose: widening it to `wallpaper.state` would turn a single-topic fix into the
cross-capability repair described above.

**Recommended follow-up change:** pin `stage` and its enum in
`contracts/event-contract.json`, and add a gate that cross-checks each contract
topic's `payload` block against `emit_validation.TOPIC_SCHEMAS`' property set so
this class of drift fails everywhere, not just where someone remembered to look.

## Resolved during review: the spec contradicted its own payload

**Symptom.** Task 3.4 asked the success card body to name "the connected network
and test server" (the approved mock reads `Canela&Dulce · CableVivo Envigado`),
but the payload pinned in this same change — `{state, trigger}` plus three
measurements and `reason` — had nowhere to put either value. Both ways of
making it true were excluded: adding the fields contradicted the spec's own
payload requirement, and having the consumer read Wi-Fi state is exactly the
coupling `speedtest-no-new-architecture.py` exists to prevent. Implemented as
the trigger phrase plus a panel pointer, and raised rather than guessed at.

**Root cause.** Not a runtime bug — an authoring error. The card requirement and
the payload requirement were written in the same document and were never checked
against each other, so the plan shipped internally inconsistent.

**Resolution (requester decision).** Widen the payload with `ssid` and
`server_name` rather than drop the line from the mock, keeping the card faithful
to the approved design. The producer already imports Wi-Fi state and already
parses the server name from the result, so this is a pass-through — which is why
a payload change is the right shape and consumer-side coupling is not.

Tracked as rework task **R1** in `tasks.md`. The spec's lifecycle-event and
in-place-card requirements have been updated to agree, and the card requirement
now explicitly states that the payload and the card must not disagree.
