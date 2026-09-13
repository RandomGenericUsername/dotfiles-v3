# P5‑1‑2b‑ii‑a: Hub Event Surface — Emit + Validation + Topic Store/Seq + GetTopicState

Status: draft (Gate‑1 ballot pending)

baseline_commit: 2681e97

Gate‑1 ruling note: pending — sub-decisions Q1–Q9 below require owner
ruling before DEV. Recommendations are recorded inline; recs marked
"(rule now, implement in ii‑b)" shape ii‑b's seam the way 2b‑i's Q3–Q7
shaped this slice.
Gate 2: not yet run.

Epic: Phase 5 epic 5‑1 — Daemon foundation, observability & safety (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`;
spine `ARCHITECTURE-SPINE.md` status `final`, AD‑34/AD‑38/AD‑44).

## Story

As the daemon operator,
I want the hub serving its event surface on the session bus — a validated
`Emit(topic, payload)` with structural enforcement per the contract topics
table, a hub-owned in-memory topic store with per-topic `seq` within the
epoch, and `GetTopicState` hydration carrying reserved `_epoch`/`_seq`,
so producers can publish domain events through the hub and consumers can
hydrate last-value state before the signal slice (P5‑1‑2b‑ii‑b) attaches
live delivery.

## Context (why this slice, what 2b‑i left, what it must match)

Epic 5‑1 as written is too big for one commit, and P5‑1‑2b‑ii as scoped
(`Emit` + schema/size/depth/rate validation + topic store + per-topic
`seq` + `GetTopicState` + all 5 signal emissions + synthetic-expiry
wiring + `NameOwnerChanged` restart + signals/topics conformance +
`daemon run` full surface) is still too big for one surgical, landable
commit (pytest/ruff/mypy/layering green, one behavior) — the same
argument that split 2a and 2b‑i. So P5‑1‑2b‑ii splits:

- **P5‑1‑2b‑ii‑a (this story):** the EMIT + STATE slice — `Emit` dispatch
  (`topic:s, payload:a{sv}`) with structural validation (known-topic-only
  → `UnknownTopic`; schema/size/depth/sv-compatibility → `PayloadTooLarge`;
  per-(sender,topic) + global rate → `RateLimited` per the 2b‑i Gate‑1
  ruling: 64 KiB / 8 / 60‑min), hub-owned in-memory topic store
  (`topic → (payload, seq)`, per-topic `seq` within epoch, reset on epoch
  bump by construction), `GetTopicState` with reserved `_epoch`/`_seq`,
  `IEventPublisher` bound to the same validated path, executable
  methods+topics conformance extension, `daemon run` serving the two new
  methods. The sink records a `domain_event` entry per accepted `Emit`
  (the record ii‑b binds to the `DomainEvent` signal) but emits NO bus
  signal yet.
- **P5‑1‑2b‑ii‑b (next):** the SIGNAL + RESTART slice — bus emission of
  all 5 signals with epoch (`JobStarted`/`JobProgress`/`JobFinished` from
  sink records, `DomainEvent` on `Emit`, `JobsCleared` on start),
  synthetic-expiry → `JobFinished` queue-then-emit wiring (Q8 rules the
  shape now), `NameOwnerChanged` subscription → restart path (fresh epoch,
  empty registry, `JobsCleared` first), `IEventSubscriber` binding,
  signals-block conformance, `daemon run` serves the FULL surface.

What 2b‑i built (this story binds, does not rebuild):
`adapters/dbus_event_bus.py` (`HubService.dispatch` over `IJobRegistry`,
`METHODS` as the single source, `introspect_xml()` generated from it,
`wire_error_name`, `JeepneyNameOwner` serve loop), `domain/hub.py`
(`EventHub` + `HubEvent` with sink-must-not-raise + single-threaded-caller
preconditions), `ports/event_bus.py` (`IEventPublisher`/`IEventSubscriber`/
`IJobRegistry` ABCs), daemon wiring in `cli/main.py` (`_build_hub` with
in-memory epoch counter, `_log_hub_event` sink, `_run_daemon_run`
name-first serve).

What this story inherits from the 2b‑i Gate‑2 review (preconditions, all
load-bearing): sink-must-not-raise (no bus emission inside a registry
call — ii‑a preserves it by recording `domain_event` to the sink only,
emission arrives in ii‑b); single-threaded caller (the dispatcher-side
lock already serializes; the rate limiter and topic store sit behind the
same lock); wire-width validation owed is done for job methods; the
`Emit`/`GetTopicState` absence-that-fails-loud becomes presence.

Contract files this story must match (read-only, no extension needed):
`contracts/event-contract.md`, `contracts/event-contract.json`,
`contracts/event-contract.xml` (AD‑44 wire source). The contracts already
specify `Emit`/`GetTopicState` signatures, the 6 typed errors, the 3
known topics with payload schemas + the `capture.state.state` enum, and
`delivery` (per-topic `seq` within `epoch`; `_epoch`/`_seq` reserved
members; subscribe-before-read). **ii‑a needs NO contract change.** Two
deliberate carries from 2b‑i: (1) structural cap NUMBERS (64 KiB / depth
8 / 60‑min + global ceiling Q4) live in code + tests, NOT in the contract
files (JSON `validation.structural` lists categories only); (2) the
signals block stays pinned-but-absent until ii‑b.

What ii‑a deliberately does NOT include (ii‑b or later own it): bus
signal emission of any kind, synthetic-expiry → `JobFinished` wiring
(shape ruled in Q8 now), `NameOwnerChanged`, `IEventSubscriber`, watches
/ converge (P5‑1‑3), bar binding (epics 5‑2/5‑4), status surface
(P5‑1‑4), new topics, Events2.

## Acceptance Criteria

1. `Emit` dispatch per the wire source: `METHODS` gains exactly
   `Emit(in: topic:s, payload:a{sv})` and `GetTopicState(in: topic:s,
   out: state:a{sv})` with argument names/order/directions byte-matching
   `event-contract.xml`; `introspect_xml()` regenerates from the table
   (no hand-written XML to drift); calling any still-unbound member
   keeps failing loud with `UnknownMethod`. (AC 1)
2. Known-topic-only: `Emit`/`GetTopicState` on a topic absent from the
   JSON topics table fail with typed `UnknownTopic` (never a silent
   no-op, never an auto-created topic — the hub never advertises a topic
   absent from the contract). (AC 2)
3. Structural validation on every `Emit` (AD‑38): JSON-Schema per the
   topics table incl. the `capture.state.state` enum (Q2 mechanics);
   maximum payload size 64 KiB (Q3 measurement); maximum nesting depth 8
   (Q3 counting); `a{sv}` compatibility (str keys; values JSON-compatible
   D-Bus scalars/containers only, no opaque binary) — any structural
   rejection crosses the wire as typed `PayloadTooLarge` with the detail
   preserved (the contract's typed list has no `BadSchema`; see Q2).
   (AC 3)
4. Rate enforcement: sliding-window accounting keyed on
   (sender unique-name, topic) at 60/min plus a hub-wide global ceiling
   (Q4 number), window/clock per Q1 — excess crosses the wire as typed
   `RateLimited`; sender is the bus-attested unique name from the
   message, never self-asserted (AD‑38 accounting, not identity
   authorization, per the 2b‑i Gate‑1 Q5 ruling). (AC 4)
5. Topic-state store (2b‑i Gate‑1 Q3 ruling, restated): hub-owned
   in-memory `topic → (payload, seq)` in `EventHub`; per-topic counters
   start at 1 on first `Emit` and reset by construction on epoch bump (a
   fresh hub per start owns a fresh store — no cross-module consistency
   protocol, persistence buys nothing since `JobsCleared` invalidates
   all prior state); each accepted `Emit` records a `domain_event` sink
   entry carrying `(topic, producer, seq, epoch)` for ii‑b's signal
   binding. (AC 5)
6. `GetTopicState` hydration: returns the last payload PLUS reserved
   `_epoch: u` / `_seq: u` members; a known-but-never-emitted topic
   returns `{_epoch, _seq: 0}` (Q5 — 0 is the "nothing yet" sentinel,
   consistent with epoch 0 as the consumer never-hydrated sentinel);
   unknown topic → `UnknownTopic`; consumers compare the `(epoch, seq)`
   pair, never `seq` alone. (AC 6)
7. Typed errors extended: `UnknownTopic`/`PayloadTooLarge`/`RateLimited`
   cross the wire as `org.dotfiles.Events1.<Name>` via the same
   `wire_error_name` seam as the 2b‑i job trio (new domain exception
   types in `domain/models.py` mirroring the `UnknownJob` pattern);
   value/shape violations that are NOT in the typed list stay generic
   (`InvalidArgs`/`Failed`) per the 2b‑i precedent. (AC 7)
8. Port binding (half): `IEventPublisher.publish` is implemented by the
   validated emit path (same validator + hub `emit`, sender recorded per
   Q6); `IEventSubscriber` is explicitly deferred to ii‑b (there is
   nothing to subscribe to before signals exist) — pinned in tests, not
   forgotten. Serialization (dispatcher-side lock) and sink infallibility
   (no bus emission inside registry calls) hold unchanged. (AC 8)
9. Executable conformance extension: the 2b‑i methods-block test extends
   to `Emit`/`GetTopicState`; a NEW topics-block test pins the adapter's
   embedded schema table against the JSON topics table (names, payload
   shapes, enum values); the signals block stays asserted as ii‑b-owned
   (present in contract, absent on the wire). (AC 9)
10. `daemon run` serves the emit surface: `_run_daemon_run` serves
    `Emit`/`GetTopicState` alongside the job surface (comment + log line
    updated — the "Emit … arrive in 2b‑ii" note is retired for these two
    methods); STILL no signals, no converge, no use-case call, no lock
    across calls, no mutation beyond the hub registry. (AC 10)
11. Surgical scope: one commit; `uv run --directory src/runtime pytest` +
    `ruff` + `mypy --strict` + layering gate
    (`tests/architecture/test_layering.py`) green; contracts diff empty;
    no new third-party dependency (Q2). (AC 11)

## Tasks / Subtasks

- [ ] Domain: `EventHub.emit(topic, payload) → seq` + `topic_state(topic)`
  owning the hub-side store (`topic → (payload, seq)`), per-topic `seq`
  from 1, `domain_event` sink record `(topic, producer, seq, epoch)`,
  defensive `UnknownTopic` on off-table topics via an embedded topic
  frozenset (AC: 5, 6, 7)
- [ ] Domain models: `UnknownTopic` / `PayloadTooLarge` / `RateLimited`
  exception types in `domain/models.py` mirroring the job-error pattern
  (AC: 7)
- [ ] Validation unit (transport-free, adapter layer): schema table
  embedded from the contract topics JSON + compiled validators (Q2) +
  size/depth/sv-compatibility checks (Q3) + sliding-window rate limiter
  with injected clock (Q1) and global ceiling (Q4); raises the typed
  errors (AC: 2, 3, 4)
- [ ] Adapter: `METHODS` += `Emit`/`GetTopicState`; dispatch arms (sender
  unique-name extracted from the message per Q6, validation BEFORE the
  registry call, widths `s`/`a{sv}` pass-through); `wire_error_name` +=
  the three Emit-side names (AC: 1, 4, 7)
- [ ] Port: `IEventPublisher.publish` binding over the same validator +
  hub `emit` (AC: 8)
- [ ] Conformance tests (executable, no live bus): XML↔`METHODS`↔JSON
  methods block incl. the two new methods; embedded-schema-table ↔ JSON
  topics block (names/shapes/enums); signals block pinned as ii‑b-owned
  (AC: 9)
- [ ] Dispatch tests (no live bus): happy-path `Emit` → store+`seq`+sink
  record; `UnknownTopic` both methods; schema/enum violation, oversize,
  over-depth, binary payload → `PayloadTooLarge`; 61st event in the
  window and global-ceiling breach → `RateLimited`; per-(sender,topic)
  isolation (one chatty producer does not starve another); never-emitted
  topic → `{_epoch, _seq: 0}`; `_epoch`/`_seq` reserved-member
  passthrough; `publish` binding parity; layering (no new imports
  outside `adapters/`) (AC: 2–8, 11)
- [ ] Daemon wiring: serve the two new methods in `_run_daemon_run`;
  retire the 2b‑i deferral note for them (signals/converge notes stay)
  (AC: 10)

## Dev Notes

- **Where:** domain gains `emit`/`topic_state` in `domain/hub.py`
  (transport-free; the topic-name frozenset is an embedded constant, not
  I/O — same standing as `CONTROL_ALLOWLIST`); validation unit + rate
  limiter live in `adapters/` (the ONLY layer that sees senders and the
  bus clock); dispatch arms in `adapters/dbus_event_bus.py` behind the
  existing dispatcher lock; `IEventPublisher` binding in the adapter
  layer; wiring in the `cli/main.py` composition root only.
- **Layering (AD‑1/13/14/25, AD‑34):** core never imports D-Bus — the
  adapter stays the ONLY module importing `jeepney`; the new validator
  imports only the schema compiler (Q2 — already declared) + stdlib.
  Third-party imports must be declared in `pyproject.toml` — ii‑a adds
  NONE (a ruling constraint, not an oversight).
- **Validation-before-mutation:** the adapter validates schema/size/
  depth/rate BEFORE calling `EventHub.emit`, so a rejected `Emit` leaves
  no store entry, no `seq` gap, and no sink record (consumers never see a
  `seq` skip — every `seq` they can hydrate corresponds to a stored
  payload). The domain's defensive `UnknownTopic` is unreachable through
  the adapter but keeps the in-process path honest.
- **Size/depth semantics (Q3 ruling to encode):** size = UTF‑8 bytes of
  canonical JSON (`sort_keys=True`, compact separators) of the payload;
  depth = container-nesting level of the payload value (top-level dict
  is depth 1; scalars depth 0; max 8). `a{sv}` compatibility is a
  hand-check (str keys; `str`/`int`/`float`/`bool`/`None`→variant-empty /
  `list`/`dict` leaves only) — the schema compiler cannot express the
  no-opaque-binary rule, so it stays explicit.
- **Rate accounting identity (AD‑38):** the key's sender half is the
  bus-attested unique name (`:1.x`) taken from the message header by the
  adapter, never a client-supplied string — keying on it is accounting,
  not authorization (2b‑i Gate‑1 Q5). The in-process `publish` binding
  uses a fixed local sender id (Q6) so local publishes are rate-counted
  but never collide with bus peers.
- **Daemon holds no lock across use-case calls (AD‑35):** unchanged —
  hub calls are registry mutations, not use-case calls; the dispatcher
  lock guards hub + limiter + store check-then-act only.
- **Hub emits lifecycle signals; jobs report via methods (AD‑37):**
  restated for the ii‑b boundary — ii‑a records `domain_event` sink
  entries but emits nothing; a UI indicator is driven by DOMAIN events
  only, never job lifecycle.
- **Contract-name mapping (2a Gate‑2, extended):** sink tag
  `domain_event` → signal `DomainEvent` (ii‑b maps it); `GetTopicState`
  reserved members stay `_epoch`/`_seq` (leading underscore, never a
  real payload key — the validator rejects payloads containing them).
- **Out of scope:** bus signal emission, synthetic-expiry wiring (Q8
  rules now, ii‑b implements), `NameOwnerChanged`, `IEventSubscriber`,
  watches, converge, bar, status.

## Gate‑1 sub‑decisions (owner ruling required)

1. **Confirm the split:** ii‑a as scoped here (Emit dispatch +
   validation + topic-store/seq + `GetTopicState` + `IEventPublisher` +
   topics conformance + serve the two methods, sink records but NO bus
   signals) with ii‑b owning all signal emission + synthetic-expiry
   wiring + `NameOwnerChanged` + `IEventSubscriber` — *recommended: yes;
   the full event surface is not one landable commit (same argument that
   split 2a and 2b‑i); ii‑a is independently testable with the sink
   still emission-free, and ii‑b attaches to the exact seam ii‑a leaves
   (`domain_event` sink records + queue-then-emit + restart path)*.
2. **Payload schema validation mechanics:** hand-checks vs a schema
   library. `jsonschema` is NOT in `pyproject.toml` — adding it grows the
   deployed `uv tool` closure and needs a layering-test declared-dep
   amendment. `fastjsonschema` (already declared, already the R‑4
   structural-file enforcement engine) compiles the topics-table schemas
   to validators with identical verdicts to `ajv` on the prototype
   corpus. *Recommended: `fastjsonschema`, compiled once per topic from
   an adapter-embedded table; executable conformance pins the embedded
   table to `contracts/event-contract.json` topics (AD‑44 "embedded per
   side + gated by a repo test" — the installed tool cannot read the
   repo `contracts/` path, so embedding is mandatory, not optional).
   Any structural rejection (schema, enum, size, depth, sv-compat) maps
   to `PayloadTooLarge` with detail — the typed list has no `BadSchema`,
   per the 2b‑i `BadFraction` precedent.*
3. **Size/depth measurement:** *recommended: size = UTF‑8 byte length of
   canonical JSON (`json.dumps(sort_keys=True,
   separators=(",", ":"))`), cap 64 KiB; depth = container nesting with
   the top-level payload dict at depth 1, cap 8* — deterministic across
   callers, bus-representation-independent, and unit-testable without a
   bus. (Alternatives — measuring the jeepney-marshalled body, or
   `sys.getsizeof` — are transport-coupled or allocator-dependent;
   rejected.)
4. **Global rate ceiling (the per-key 60/min is already ruled):**
   *recommended: 600 `Emit`/min hub-wide (10× the per-key budget) as a
   pure backstop* — sized so it never fires unless many distinct
   (sender, topic) pairs burst together; both numbers stay named
   constants in code + tests, NOT in the contract files.
5. **Rate-limiter clock source + window shape:** *recommended: injected
   monotonic clock (`time.monotonic` in production, fake in tests —
   same pattern as `EventHub`'s clock, keeps the limiter deterministic
   and hermetic) with a SLIDING 60 s window (per-key deque of timestamps,
   prune-then-count)* — vs a fixed window (admits 2× bursts at
   boundaries and needs wall-clock alignment; rejected). Pruning happens
   inside the dispatcher's existing lock, so the 2a single-threaded
   precondition covers the limiter's check-then-act.
6. **`DomainEvent.producer` value (ii‑b emits; rule now so ii‑a's sink
   record carries it):** the contract topics table has a descriptive
   "Producer" column (ICME, capture controller…), but AD‑38/C3 forbid
   trusting self-asserted identity. *Recommended: the bus-attested
   sender unique-name (`:1.x`) for wire `Emit`, and a fixed
   `"(local)"` marker for the in-process `IEventPublisher` path* — the
   table's producer column stays descriptive prose (which tool emits
   which topic), never a wire value; consumers MUST NOT dispatch on
   `producer` identity.
7. **Signal emission failure routing (ii‑b implements; rule now to
   protect the 2a precondition):** *recommended: failed send →
   log-and-continue serving (AD‑41 recoverable flavor), NEVER stop-serve*
   — a transient bus failure must not take the name off the bus (that
   converts a recoverable blip into a supervisor-visible restart with an
   epoch bump and a `JobsCleared` storm); stop-serve is reserved for bus
   DEATH (`OSError` on receive/send, the existing 2b‑i routing). The
   at-most-once contract already permits a dropped signal; hydration
   repairs it.
8. **Queue-then-emit queue location (ii‑b implements; rule now):**
   *recommended: adapter-side drain — the lazy sweep keeps recording
   synthetic finishes to the sink (registry call stays emission-free,
   preserving sink-must-not-raise verbatim), and the adapter, AFTER the
   registry call returns and OUTSIDE the dispatcher lock, drains newly
   recorded `job_finished(exit_code=-1)` entries into `JobFinished`
   signals* — vs a domain-side outbox (leaks transport ordering into the
   pure core; rejected) or direct emission in the sweep (rejected by the
   2b‑i Gate‑1 Q6 ruling for the stated wedge reason). Same drain
   carries `job_started`/`job_progress`/`job_finished`/`domain_event`
   sink records to their signals in ii‑b.
9. **`GetActiveJobs` + `GetTopicState` hydration ordering vs
   subscribe-before-read (document, no code):** the contract requires
   subscribe-first-then-hydrate, but the daemon (ii‑b) cannot subscribe
   to its own signals — it IS the emitter. *Documented (no code): the
   hub reads its own store directly (no race — single-threaded behind
   the dispatcher lock); the subscribe-before-read rule binds CONSUMERS
   (bar, jobs), and ii‑b's conformance notes the hub's exemption
   explicitly so a future reviewer does not "fix" it into a self-
   subscription.*
