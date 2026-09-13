# Gate 2 Review — Epic 5‑2 (Event Contract & Bus: Bar Consumer Binding)

Verdict: **APPROVED-WITH-FOLLOWUPS** — the consumer binding and the
per-language drift gate are real, self-contained, and green. No blocking
findings. Follow-ups concern the gap between the tested Python binding and
the shipped GJS bar, and the reach of the drift scan.

Artifact: `epic5-2-bar-consumer-binding.md` (status "complete — nothing
committed"; actually committed in `b1674aa`). Reviewed at `b1674aa`,
clean tree.

## Verification (executed by reviewer)

| Check | Result |
| --- | --- |
| `pytest tests/unit/test_bar_subscriber.py` | **29 passed** (matches artifact) |
| `pytest tests/unit/test_event_contract_drift.py` | **7 passed** |
| `make contracts-check` | **22 passed** (includes the new drift gate; `Makefile` updated) |
| Full suite / layering | **1372 passed, 2 skipped** / 100 passed |
| `ags bundle dotfiles/config/ags/app.tsx … --gtk 4` | **exit 0** (independently re-run; `ags 3.1.0`) |

Verified claims:

- **No runtime-core import (AD‑34).** `bar_subscriber.py` imports only
  jeepney + stdlib; contract constants parsed at import from
  `contracts/event-contract.json` via `_find_contract`
  (`bar_subscriber.py:82‑113`, `:116‑140`). A layering/rust test asserts
  jeepney stays in `adapters/` (`test_dbus_conformance.py:194‑210`).
- **Subscribe-before-read.** `start()` registers the three match rules then
  hydrates every tracked topic (`bar_subscriber.py:296‑328`), tested at
  `test_bar_subscriber.py`.
- **Stale drop on the `(epoch, seq)` pair, lexicographic**, with baseline
  advance on acceptance (`bar_subscriber.py:374‑381`).
- **Restart re-hydration** on `JobsCleared` (new epoch only) and
  `NameOwnerChanged` gain (`:397‑416`).
- **Consumer caps mirror the hub's** 64 KiB / depth 8 (`:150‑188`), pinned
  equal by the drift test (`test_event_contract_drift.py:148‑151`).
- **Handler containment** for topic and restart handlers
  (`:391‑395`, `:418‑423`).
- **Drift gate is bidirectional and stronger than the 2b conformance
  test:** `test_hub_adapter_tables_match_contract` asserts
  `table_methods == xml_methods == data["methods"]`
  (`test_event_contract_drift.py:114`) — unlike
  `test_dbus_conformance.py:63‑86`, which is subset-only. Good.

## Findings (all non-blocking)

- **N1 — the tested binding is not the shipped bar.** Epic 5‑2's ACs are
  met by the Python `BarSubscriber`, but production is the GJS
  `dotfiles/config/ags/lib/event-bus.ts`, which has **no
  subscribe-before-read hydration and no `(epoch, seq)` stale-drop** — it
  destructures and discards `_seq`/`_epoch` and renders every push
  (`event-bus.ts:97‑114`). The 5‑4 artifact tracks hydration as a follow-up
  (#5) but not stale-drop. Consequence: duplicate/reordered DomainEvents
  after a hub restart can render out of order in the real bar. Recommend
  extending the follow-up to cover the epoch/seq drop.
- **N2 — drift scan scope.** The shell-leg textual scan only walks
  `dotfiles/config/ags` (`test_event_contract_drift.py:178‑186`). The
  Epic 5‑4 GJS publisher
  `src/gui-tools/icon-color-mapping-editor/lib/event-bus.ts` hardcodes
  `org.dotfiles.Events` / `/org/dotfiles/Events` / `...Events1` and is
  **not** covered, so a drift there would pass silently. Recommend adding
  that path to the scan.
- **N3 — hydration failure mid-restart silently suppresses the restart
  notification.** `_on_name_owner_changed` only notifies when the epoch
  actually advanced (`bar_subscriber.py:412‑416`); `_hydrate_all` swallows
  per-topic failures (`:323‑328`), so if `GetTopicState` is not yet
  answering when the new owner appears, the bar can miss the restart
  callback. `JobsCleared` is the primary path, so impact is low.
- **N4 — `BarSubscriber` never enforces `sender`;** any same-user
  connection can emit a `DomainEvent` on the interface/path and advance the
  bar's baseline. This matches the contract's
  `validation.identity: none (trusted same-user session bus)` and AD‑38, so
  it is accepted, not a defect.
- **N5 — bookkeeping:** the artifact says "nothing committed" and reports a
  red full suite due to a concurrent 5‑3 workstream
  (`epic5-2-bar-consumer-binding.md:3‑5`, `:177`). At `b1674aa` everything is
  committed and the full suite is green. The status text is stale.

## Panel notes

- Blind Hunter: no correctness blockers. Trusts `_as_uint` coercion
  (`:210‑214`) and variant unwrap (`:194‑207`); both total on hostile input.
- Edge Hunter: oversized/overdeep payload dropped not rendered; wrong arity
  ignored; untracked topic ignored; restart dedup correct; `stop()`
  idempotent. No unhandled path found.
- Acceptance Auditor: AC1–AC11 MET for the Python binding + drift gate.
  AC8's shell-leg claim is accurately scoped to `dotfiles/config/ags`
  (N2 is a scope extension, not a false claim).

## Follow-ups

1. Add `(epoch, seq)` filtering + `GetTopicState` hydration to the GJS bar
   (extend 5‑4 follow-up #5).
2. Include `src/gui-tools/icon-color-mapping-editor/lib/event-bus.ts` in the
   drift shell scan.
3. Fix the stale status/test results in the 5‑2 artifact at the next
   bookkeeping pass.
