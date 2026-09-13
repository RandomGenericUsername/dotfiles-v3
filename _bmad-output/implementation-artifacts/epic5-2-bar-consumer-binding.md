# Epic 5‑2 — Event Contract & Bus: Bar Consumer Binding (P5‑2)

Status: **complete** — all new/owned suites green; the full-runtime suite is
red only on a concurrently-landing Phase 5‑3 workstream (not owned here; see
"Exact test results").

baseline_commit: `2681e97`

Epic: Phase 5 epic 5‑2 — Event contract & bus (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`; spine
`ARCHITECTURE-SPINE.md` status `final`, AD‑34/AD‑37/AD‑38/AD‑44).

Related: P5‑1‑2b‑ii‑a (`Emit`/`GetTopicState` + validation, uncommitted
baseline), P5‑1‑2b‑ii‑b (signal emission + restart, uncommitted baseline).

## Story

As the bar,
I want a correct binding to the hub's `org.dotfiles.Events1` surface — I
subscribe to the contract's domain signals filtered by topic, hydrate via
`GetTopicState` **after** subscribing, drop any signal whose `(epoch, seq)`
is not greater than what I hydrated, re-hydrate when the hub restarts, and
validate a payload structurally before I render it —

so that the shell reacts to pushed state through the one shared contract,
never by polling, and never by importing the runtime's code.

## Context (what this slice adds and what it must not do)

P5‑1‑2b delivered the **hub/emitter** side of the contract (methods, five
signals, `(epoch, seq)` per topic, `JobsCleared` restart, structural
validation on `Emit`). P5‑2 completes the **consumer** side:

- `src/runtime/src/runtime/adapters/bar_subscriber.py` — the bar's binding.
  It is intentionally **self-contained**: it imports only jeepney + stdlib
  and reads its contract constants from `contracts/event-contract.json`
  **at import time**. It does not import `runtime.domain`,
  `runtime.ports`, or any other runtime module (AD‑34: the bar depends on
  the contract, never on the runtime).

The file in the working tree before this story was orphaned and broken
(wrong `parents[3]` contract path → import-time `FileNotFoundError`,
`self._default_handler` undefined, an invalid `arg0namespace` match rule,
and an envelope/payload handler mix-up). It was replaced with the correct
binding below.

Out of scope (owner names in parentheses): the GJS/AGS bar widgets
(5‑4), watches/converge (5‑3), daemon/CLI wiring (5‑1; `cli/main.py` is
owned by another agent), watches/status, new topics, `Events2`.

## Acceptance Criteria

1. **Consumer binding exists and is wired by tests.** A concrete
   `BarSubscriber` subscribes to `DomainEvent` (filtered by the topics the
   bar tracks) and `JobsCleared`, hydrates via `GetTopicState`, drops stale
   `(epoch, seq)` signals, validates payloads, and contains handler errors.
   No live bus is required to exercise any of it. (AC 1)
2. **No runtime-core import (AD‑34).** The adapter imports only jeepney +
   stdlib; contract constants (`BUS_NAME`, `OBJECT_PATH`, `INTERFACE`,
   `KNOWN_TOPICS`, `DomainEvent` arg order) are parsed from
   `contracts/event-contract.json`. (AC 2)
3. **Subscribe-before-read hydration.** `start()` installs the D-Bus match
   rules (`DomainEvent`, `JobsCleared`, `NameOwnerChanged`) *before* it
   calls `GetTopicState` for every tracked topic.
   `GetTopicState` returns reserved `_epoch`/`_seq`; both are recorded as
   the per-topic `(epoch, seq)` baseline. (AC 3)
4. **Stale-signal drop on the pair.** A `DomainEvent` is discarded when
   `(epoch, seq) <= hydrated[topic]`; comparison is lexicographic on the
   pair, so a new epoch with a lower `seq` is correctly accepted and an
   equal `seq`/`epoch` is dropped. An accepted pair advances the baseline
   (at-most-once; no replay). (AC 4)
5. **Restart re-hydration.** `JobsCleared(new_epoch)` (and the
   belt-and-braces `NameOwnerChanged` on `org.dotfiles.Events`) clears the
   hydrated state, re-reads `GetTopicState`, and notifies restart handlers;
   a stale/duplicate restart (epoch not greater than the last seen) is
   ignored. (AC 5)
6. **Consumer-side structural validation before dispatch.** Payload size
   (> 64 KiB) and nesting depth (> 8; top-level dict = 1) are checked before
   any render handler runs; a violation is logged and dropped, never
   rendered. Caps mirror the hub's (`emit_validation`) values exactly. (AC 6)
7. **Handler containment.** A raising topic handler or restart handler is
   logged and swallowed; sibling handlers still run. (AC 7)
8. **Executable per-language drift gate (AD‑44).** A Python test parses
   `contracts/event-contract.xml` **and** `.json` and asserts equality with
   (a) the hub adapter's `METHODS`/`SIGNALS` tables, (b) the port's
   `BUS_NAME`, and (c) the bar binding's constants, signal-arg order, and
   structural caps. Because there is no JS test runner (schema-evaluation
   §2 / review-rubric F8), the shell leg is a self-tested textual scan:
   any `org.dotfiles.*`/object-path literal in `dotfiles/config/ags` must be
   a contract value. (AC 8)
9. **Layering preserved.** jeepney imports remain in `adapters/` only; the
   architecture gate stays green. (AC 9)
10. **No contract change.** `contracts/event-contract.xml|json` are
    untouched; no new third-party dependency. (AC 10)
11. **Story artifact.** This file records status, ACs, tasks, dev notes,
    and exact command results. (AC 11)

## Tasks / Subtasks

- [x] Replace `adapters/bar_subscriber.py` with a correct, self-contained
  consumer binding: contract-JSON constant loading via robust walk-up;
  `DomainEvent` arg order derived from the contract; subscribe-before-read
  `start()`; per-topic `(epoch, seq)` hydration; lexicographic staleness
  drop; `JobsCleared`/`NameOwnerChanged` re-hydration + restart notify;
  size/depth validation; handler containment; a blocking `run()` receive
  loop with real jeepney decode (AC 1–7)
- [x] `tests/unit/test_bar_subscriber.py` (29 tests, fake connection): match
  registration precedes hydration; every tracked topic hydrated; variant
  unwrap; idempotent start; fresh/stale equal/lower `seq`; new-epoch-lower-
  seq fresh; baseline advance; untracked topic and wrong-arity ignored;
  oversize/overdeep/non-object dropped and depth-cap-boundary dispatched;
  handler + restart containment; `JobsCleared` re-hydrate and stale-ignore;
  old-epoch dropped/new-epoch accepted after restart; `NameOwnerChanged`
  new-owner/loss/other-name; subscribe validation; receive-loop decode of a
  real jeepney signal; `stop()` closes (AC 1, 3–7)
- [x] `tests/unit/test_event_contract_drift.py` (7 tests): XML↔JSON; hub
  `METHODS`/`SIGNALS`↔both; port `BUS_NAME`↔contract; bar constants and
  `DomainEvent` arg order↔contract; consumer caps == hub caps == 64 KiB/8;
  shell-source literal scanner self-test + live scan (AC 8)
- [x] Wire the drift test into the repo contract gate `make contracts-check`
  (AC 8)
- [x] Verify: new suites green, layering gate green, `make contracts-check`
  green, ruff clean on owned files (AC 9–11)

## Dev Notes

- **Contract is the only import-time dependency.** `_find_contract()` walks
  up from `__file__` to `contracts/event-contract.json`, so it survives a
  repo move/alternate depth. `DOMAIN_EVENT_ARGS` is parsed from
  `signals.DomainEvent`, not hand-typed — decode order cannot drift.
- **Why `a{sv}` is unwrapped on both paths.** jeepney delivers variant
  values as `(signature, value)` tuples, both for `GetTopicState` out-args
  and `DomainEvent` payloads; `_unwrap` normalizes recursively. The
  receive-loop test round-trips a real serialized `DomainEvent` through
  `Message.serialise`/`from_buffer` to pin the wire shape.
- **Staleness is pair-wise.** `(epoch, seq) > hydrated` — never `seq`
  alone. An epoch bump resets `seq`, so `(6, 1) > (5, 99)`. The baseline is
  advanced as soon as a pair is accepted, even if the payload is later
  dropped, so an at-most-once redelivery cannot be replayed.
- **Validation order on the consumer.** Shape (`dict`) → size (canonical
  JSON UTF-8) → depth, exactly the hub's caps. Consumer validation is
  defense-in-depth (AD‑44 "embedded per side"); the hub remains the sole
  structural authority (AD‑38).
- **Restart de-dup.** `JobsCleared(epoch)` and `NameOwnerChanged` both route
  through re-hydration; a restart whose epoch is not greater than the last
  observed is ignored, so the belt-and-braces owner-change path cannot
  double-fire a restart handler.
- **Match rules.** Signals are emitted on `path=/org/dotfiles/Events`,
  `interface=org.dotfiles.Events1`; the old adapter's `arg0namespace=` rule
  was invalid and was replaced with `path=`. The `NameOwnerChanged` rule
  uses `sender=/interface=org.freedesktop.DBus`, `arg0=org.dotfiles.Events`.
- **Domain events only for a UI indicator (AD‑37).** The binding subscribes
  to `DomainEvent` + `JobsCleared` and never to `JobStarted`/`JobFinished`.
- **AD‑34 positioning.** The bar binding depends on the contract, not the
  runtime. It deliberately does not import/add `IEventSubscriber`; the
  handler shape `(topic, payload)` mirrors that port so a future in-process
  bridge is trivial, but the import boundary stays clean.
- **No contract change, no new dependency.** Only `jeepney` (already
  declared, adapters-only) is used.

## Exact test results

Run against the live tree, which is concurrently carrying another agent's
uncommitted Phase 5‑3 `desired.json` relocation / watch work (see note
below). Scoped results are stable; the full-suite row is a moving target
while that workstream lands.

| Command | Result |
| --- | --- |
| `uv run --directory src/runtime pytest tests/unit/test_bar_subscriber.py` | **29 passed** |
| `uv run --directory src/runtime pytest tests/unit/test_event_contract_drift.py` | **7 passed** |
| `uv run --directory src/runtime pytest` (event/bus scope: bar subscriber + drift + `test_dbus_conformance` + `test_dbus_dispatch` + `test_emit_validation` + `test_hub_registry`) | **180 passed** |
| `uv run --directory src/runtime pytest tests/architecture/test_layering.py` | **90 passed** |
| `make contracts-check` (now includes the drift test) | **22 passed** |
| `uv run --directory src/runtime ruff check src/runtime/adapters/bar_subscriber.py tests/unit/test_bar_subscriber.py tests/unit/test_event_contract_drift.py` | **All checks passed** |
| `uv run --directory src/runtime mypy src/runtime/adapters/bar_subscriber.py` | **Success: no issues found** |
| `uv run --directory src/runtime pytest` (full, latest snapshot) | **1284 passed, 1 failed, 2 skipped** — the sole failure is `test_watch_roots.py::test_enumeration_never_uses_repo_resolution`, owned by the concurrent 5‑3 workstream; none reference this story's modules |
| `uv run --directory src/runtime ruff check src` (full) | 3 errors, none owned here: `cli/main.py:224,349` B008 (other agent's edits) and `domain/models.py:35` E501 (pre-existing) |

Full-suite note: the working tree changed under this story throughout. At the
baseline it was 1206 passed; after a concurrent workstream modified
`adapters/desired_state_reader.py`, `adapters/seeder.py`, `cli/main.py`,
`domain/models.py`, and added `domain/watch.py`, `application/watch.py`,
`adapters/watch_roots.py`, `adapters/inotify_watch_source.py`,
`tests/unit/test_watch_roots.py` (all visible in `git status`), an
intermediate full-suite snapshot showed 17 failures, all confined to that
workstream's `test_cli_*`/`test_desired_state`/`test_prune_cli` tests. The
latest snapshot is down to the single 5‑3 watch test above. Every failure is
unrelated to the event contract, hub adapter, or bar binding; the scoped
suites above are green.

## Files changed

- **New:** `src/runtime/src/runtime/adapters/bar_subscriber.py` (replaced the
  broken orphan of the same path)
- **New:** `src/runtime/tests/unit/test_bar_subscriber.py`
- **New:** `src/runtime/tests/unit/test_event_contract_drift.py`
- **Edited:** `Makefile` (`contracts-check` now runs the new drift gate)
- **New:** this artifact
- **Untouched (constraints):** `contracts/event-contract.{xml,json,md}`,
  `src/runtime/src/runtime/cli/main.py`, watch/daemon code; nothing committed.
