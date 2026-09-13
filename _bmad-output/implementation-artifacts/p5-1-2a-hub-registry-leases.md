# P5‑1‑2a: Hub Domain Core — Job Registry + Leases + Epoch (No Wire)

Status: done

baseline_commit: 5e06485

Gate 1: approved (recs as-is: split yes; dasbus for 2b; caps 64 KiB / 8 /
60-min for 2b; in-memory epoch from 1; kind-keyed static table; ValueError
progress).
Gate 2: applied — Items 1–3 (correctness hardenings: sweep snapshot,
sink-must-not-raise precondition, unhashable-action guard, factory
validation + bounded retries, `-1` reservation, allowlist copy, single
clock sample, OverflowError→ValueError, `-0.0` norm, begin-sweep order,
contract-name alignment, thread/retention/width docs, N818 contract-name
markers; eight tests; this landing note). Verified: runtime 1096 passed,
2 skipped; layering green; contracts-check green; mypy --strict clean on
new files; ruff no new issues.
(dirty tree observed at draft time, NOT committed: `M
_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md`,
`M
_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md` —
no code changes made by this draft.)

Epic: Phase 5 epic 5‑1 — Daemon foundation, observability & safety (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`;
spine `ARCHITECTURE-SPINE.md` status `final`, AD‑33/AD‑34/AD‑35/AD‑37/AD‑38).

## Story

As the daemon operator,
I want the hub's job-registry domain core (Begin/Renew/Adopt/ReportProgress/End/Control/GetActiveJobs,
lease expiry with synthetic finish, epoch + JobsCleared-on-start, typed errors)
implemented transport-free behind pure ports,
so the registry semantics land testably with no live bus before the D‑Bus wire
binding (P5‑1‑2b) attaches them to `org.dotfiles.Events1`.

## Context (why this slice, what P5‑1‑1 left, what it must match)

Epic 5‑1 as written is too big for one commit, and the hub slice alone
(P5‑1‑2: 9 methods + 5 signals + epoch/seq + JobsCleared + leases/expiry +
AdoptJob + Control + typed errors + structural validation + ports/adapters +
XML/JSON conformance) is still too big for one surgical, landable commit
(pytest/ruff/mypy/layering green, one behavior). So P5‑1‑2 splits:

- **P5‑1‑2a (this story):** hub DOMAIN core — job registry, leases + lazy
  expiry, AdoptJob, Control allowlist, epoch counter + JobsCleared-on-start as a
  domain event, typed domain errors, pure ports (`IEventPublisher` /
  `IEventSubscriber` + hub port), in-process fake transport. Zero D‑Bus imports.
- **P5‑1‑2b (next):** the WIRE binding — real D‑Bus client, method dispatch per
  `event-contract.xml` signatures, signal emission with epoch, `Emit` +
  structural validation (schema/size/depth/rate caps), topic-state store +
  `GetTopicState` + per-topic `seq`, `NameOwnerChanged` handling, executable
  XML/JSON conformance tests.

What P5‑1‑1 left: `ports/bus_name_owner.py` (`IBusNameOwner` seam),
`adapters/dbus_name_owner.py` (deferred placeholder whose `acquire()` always
fails `BusUnavailableError`), and `daemon run` in `cli/main.py`
(name-first acquire → park on a release-driven event). P5‑1‑2a fills the hub
LOGIC behind these seams; the deferred real D‑Bus client stays deferred until
2b. `daemon run` in 2a constructs the hub in-process (registry starts empty,
epoch assigned, JobsCleared recorded) but still serves nothing on the wire —
the unit steady-state note from P5‑1‑1 (start-limit-hit until the real client
lands) is unchanged.

Contract files this story must match (read-only, no extension needed):
`contracts/event-contract.md`, `contracts/event-contract.json`,
`contracts/event-contract.xml` (AD‑44 wire source). Finding: **the contracts
already specify the complete hub surface** — all 9 methods with D‑Bus
signatures (XML), all 5 signals with members, the 6 typed errors (JSON
`errors`), lease/expiry semantics (`job_lease`), epoch/restart semantics
(`delivery`). **2a needs NO contract change.** Two deliberate deferrals to 2b:
(1) structural cap NUMBERS — JSON `validation.structural` lists only
categories (`schema`, `max_payload_bytes`, `max_payload_depth`,
`publish_rate`, `known_topic_only`), so 2b picks numbers at Gate‑1 without a
contract edit; (2) `GetTopicState` — its store is written by `Emit`, so it
travels with 2b, not 2a.

What 2a deliberately does NOT include (2b or later own it): any D‑Bus import,
method dispatch, signal emission on the bus, `Emit`, topic-state store,
`GetTopicState`, `seq`, structural validation, `NameOwnerChanged`, watches /
converge (P5‑1‑3), bar binding (epics 5‑2/5‑4), status surface (P5‑1‑4).

## Acceptance Criteria

1. Job lifecycle registry (pure domain, no I/O): `BeginJob(kind, ttl)` allocates
   an opaque unique `job_id` and records `(kind, lease_deadline, live)`; `RenewJob`
   extends the lease or raises typed `UnknownJob` (never seen) / `JobEnded`
   (ended or expired); `ReportProgress(fraction)` validates `0.0–1.0` (out of
   range → typed `ValueError`-class domain error, NOT a D‑Bus error yet) and
   rejects unknown/ended jobs; `EndJob(exit_code)` marks ended (idempotent
   second End → `JobEnded`); every state change appends to an injectable
   lifecycle sink (the 2b signal-emission seam). (AC 1)
2. Lease expiry without polling: expiry is **lazy** — evaluated on every hub
   method invocation against an injectable monotonic clock (default
   `time.monotonic`); a live job past its deadline is expired by the hub with a
   synthetic finish (`exit_code = -1`) recorded in the sink before the invoking
   call proceeds; no background thread, no timer, no sweep loop. Renew-then-use
   and expire-then-Renew (`JobEnded`) paths covered. (AC 2)
3. `AdoptJob(job_id, pid)` records the observed child PID on a live job
   (AD‑37 transitive ownership — a wrapper may hand off the observed child);
   unknown → `UnknownJob`, ended/expired → `JobEnded`; adopting twice updates
   the recorded PID. (AC 3)
4. `Control(job_id, action)` is the single control path (H1): allowed actions
   come from a **kind-keyed allowlist table** in the hub (e.g. `capture →
   {pause, resume, stop}`) — NO contract change, NO new `BeginJob` parameter
   (which would be breaking → `Events2`, rejected); unknown job → `UnknownJob`,
   ended → `JobEnded`, action not in the kind's set → `NotControllable`. (AC 4)
5. Epoch + restart invalidation: the hub owns a monotonic `epoch` counter
   starting at **1** (`0` reserved as the consumer "never hydrated" sentinel);
   every hub start assigns a fresh epoch (bumped, never reused) and records a
   `JobsCleared(epoch)` domain event FIRST — all prior `job_id`s are invalid
   (registry starts empty, so any stale id → `UnknownJob`); `epoch` is exposed
   on every sink record. (AC 5)
6. `GetActiveJobs` returns `{job_id: kind}` for live (non-ended, non-expired)
   jobs only — the hydration path for 2b's wire method; expired-but-unswept
   jobs are expired lazily first so they never appear. (AC 6)
7. Layering (AD‑1/13/14/25, AD‑34): domain hub logic is pure (injectable clock
   + sink, no I/O, no D‑Bus import); ports hold ABCs only
   (`IEventPublisher` / `IEventSubscriber` + hub port per spine structural seed
   `ports/event_bus.py`); the ONLY concrete transport in 2a is an in-process
   fake in `adapters/`; the daemon holds **no lock across hub calls** (hub
   calls are not use-case calls; AD‑35 `flock` non-reentrancy preserved).
   (AC 7)
8. Surgical scope: one commit; `uv run --directory src/runtime pytest` + `ruff`
   + `mypy --strict` + layering gate (`tests/architecture/test_layering.py`)
   green; **no live bus, no timers, no threads** in tests — clock and sink are
   fakes. (AC 8)

## Tasks / Subtasks

- [x] Domain: `JobRegistry` (+ `HubHub`/`EventHub` service if needed) — pure,
  clock-injected (`Callable[[], float]`, default `time.monotonic`), sink-injected
  lifecycle records `(kind, job_id, epoch, …)`; `job_id` allocation opaque +
  unique (uuid4 hex); ttl seconds as `float`/`int` per contract `ttl:u`
  (AC: 1, 2)
- [x] Domain errors: typed exceptions `UnknownJob`, `JobEnded`, `UnknownTopic`,
  `PayloadTooLarge`, `RateLimited`, `NotControllable` (names mirror the contract
  JSON `errors` list; 2b maps them to D‑Bus error names) — each carrying the
  offending `job_id`/detail; `ReportProgress` range violation is a domain
  `ValueError`, not a D‑Bus typed error (AC: 1, 4)
- [x] Adopt + Control: `adopt(job_id, pid)` PID record; kind-keyed control
  allowlist table (`capture: {pause,resume,stop}`; unknown kinds → empty set,
  so any `Control` on them → `NotControllable`); document why `BeginJob` keeps
  its 2-arg contract signature (AC: 3, 4)
- [x] Epoch + start: hub constructor/factory takes `epoch` (production: bumped
  per start; tests: explicit); records `JobsCleared(epoch)` FIRST on start;
  `epoch` on every sink record; reserve `0` sentinel, document it (AC: 5)
- [x] Ports: `ports/event_bus.py` — `IEventPublisher` / `IEventSubscriber`
  (pure ABCs, per spine structural seed) + hub/lifecycle port consumed by the
  daemon; re-export nothing D‑Bus-specific (AC: 7)
- [x] Adapter (fake only): in-process fake hub transport in `adapters/`
  implementing the hub port against the domain registry; records sink events
  for assertions; the ONLY adapter in 2a — real D‑Bus client stays deferred
  to 2b (AC: 7)
- [x] Daemon wiring: `daemon run` constructs the hub (epoch bump placeholder —
  in-memory counter, see Gate‑1 Q4) behind the `IBusNameOwner` seam; still
  serves nothing on the wire; no use-case call, no lock, no mutation
  (AC: 5, 7)
- [x] Tests (no live bus): begin/renew/end happy path; renew-unknown
  (`UnknownJob`); use-after-end and use-after-expiry (`JobEnded`); lazy expiry
  emits synthetic finish `exit_code=-1` with fake clock advanced past ttl;
  adopt happy/unknown/ended; control allowlist + `NotControllable`;
  `JobsCleared` first + epoch on every record; `GetActiveJobs` excludes
  ended/expired; layering (no `dbus`/`gi`/`dasbus` import outside `adapters/`,
  and none at all in 2a); run pytest + ruff + mypy + test_layering (AC: 1–8)

## Dev Notes

- **Where:** domain registry under `domain/` (pure — check the layering test's
  `_DOMAIN_ALLOWED_STDLIB` before importing `uuid`/`time`; inject both if
  cleaner); ports in `ports/event_bus.py` (ABCs only — the layering test
  forbids concrete classes in `ports/`); fake in `adapters/`; wiring in the
  `cli/main.py` composition root only (same pattern as `_build_bus_name_owner`).
  Application layer untouched unless orchestration is genuinely needed — prefer
  domain + ports + fake.
- **Layering (AD‑1/13/14/25, AD‑34):** core never imports D‑Bus — vacuously true
  in 2a (no D‑Bus dependency exists yet; add none). Third-party imports must be
  declared in `pyproject.toml` (layering test rule) — so 2b's client library
  MUST land as a real dependency there, not an ad-hoc import.
- **Daemon holds no lock across use-case calls (AD‑35):** hub calls are registry
  mutations, not use-case calls — no `.seed.lock`/`.history.lock` involvement
  in 2a. Preserve the invariant for P5‑1‑3 (converge calls use cases; the daemon
  must not pre-hold either lock).
- **Hub emits lifecycle signals; jobs report via methods (AD‑37):** 2a records
  lifecycle transitions in the injectable sink (the domain-side "emission");
  2b binds sink records to real `JobStarted`/`JobProgress`/`JobFinished`
  signals. A UI indicator is driven by DOMAIN events only, never job lifecycle
  (AD‑37) — restate at the 2b boundary.
- **Structural caps numbers need Gate‑1 confirmation (deferred to 2b):**
  starting proposal for 2b — `max_payload_bytes = 64 KiB`, `max_payload_depth =
  8`, per-producer publish rate `60/min` with `RateLimited` on excess; schema
  from `event-contract.json` topics table. Numbers live in code + 2b tests, NOT
  in the contract files (JSON lists categories only — no contract edit needed).
- **In-memory vs persisted registry/epoch (recommendation: in-memory):**
  `JobsCleared` on every start already invalidates all prior `job_id`s by
  design, so persisting the registry buys nothing and risks resurrecting stale
  jobs; the persisted last-converged backstop record is P5‑1‑3's separate
  concern (AD‑36/H3, lives under `state_root`). Epoch bump source still needs
  Gate‑1 ruling (Q4 below).
- **Out of scope:** everything with a bus address — dispatch, signals on the
  wire, `Emit`, topic store, `GetTopicState`, `seq`, validation, `Control`
  actuation beyond allowlist checking (2b wires action delivery), watches,
  converge, bar, status.

## Gate‑1 sub‑decisions (owner ruling required)

1. **Confirm the split:** 2a as scoped here (registry + leases + epoch as pure
   domain, fake transport, no wire) with 2b owning dispatch + signals + `Emit`
   + validation + `GetTopicState` + conformance — *recommended: yes; the full
   hub is not one landable commit, and 2a is independently testable with zero
   bus dependency*.
2. **Python D‑Bus client library (THE deferred decision from P5‑1‑1 — ruling
   needed before 2b, non-blocking for 2a): *recommended: `dasbus`*** (pure-PyPI,
   `uv add`-able, GLib-backed, sync API for client + service publication, no
   asyncio). Evidence surveyed at draft time: `pyproject.toml`/`uv.lock` carry
   ZERO D‑Bus deps today; system `python3` has `gi` (PyGObject) AND `dbus`
   (dbus-python) but NO `dasbus`/`dbus-fast`/`jeepney`/`sdbus`; the project uv
   venv (hermetic, py3.14.7) imports NEITHER `gi` NOR `dbus` — so Gio or
   dbus-python would break hermetic builds (system-site-packages or apt-managed
   dep outside uv). `dbus-fast` is asyncio-first → conflicts with the binding
   sync-core constraint (spine: "prefer a GLib/sync client over an
   asyncio-first one"; it served only as the prototype's XML parser). `jeepney`
   (pure-Python blocking, zero native deps) is the fallback if GLib ever proves
   unavailable, at the cost of hand-rolled service-side dispatch. Gio symmetry
   with the GJS side (`Gio.DBusNodeInfo` parsing the wire XML natively, per
   AD‑44) is real but requires non-hermetic packaging — accept only if the
   owner prefers symmetry over hermetic `uv` builds. Whichever wins lands as a
   declared `pyproject.toml` dependency in 2b (layering-test rule).
3. **Structural cap numbers (for 2b, rule now):** `max_payload_bytes = 64 KiB`,
   `max_payload_depth = 8`, `60 emits/min` per producer → `RateLimited` —
   *recommended as starting values; confirm or retune*. Schema source is the
   `event-contract.json` topics table; no contract-file edit needed.
4. **Epoch bump source (in-memory vs persisted):** (a) in-memory counter
   starting at 1 per process start — restart always yields a fresh process, so
   the epoch trivially never repeats within a bus session, and `JobsCleared` +
   `NameOwnerChanged` belt-and-braces already covers crash-restart
   *(recommended — simplest, matches "registry is not persisted")*; vs (b)
   persisted epoch counter under `state_root` (survives restarts, costs a
   read/write path + crash-torn-file handling for zero consumer-visible gain,
   since consumers compare pairs, not absolute values).
5. **Control allowlist shape:** kind-keyed static table in the hub (`capture →
   {pause,resume,stop}`, unknown kinds → deny-all) *(recommended — no contract
   change, stays additive-compatible on `Events1`)* vs a hub `RegisterActions`
   method (new method is technically additive/non-breaking, but adds surface
   2a doesn't need; defer unless a 5‑4 job needs dynamic actions).
6. **`ReportProgress` out-of-range:** domain `ValueError` (2b maps to a generic
   D‑Bus error, NOT a typed contract error — the contract's typed list has no
   `BadFraction`) *(recommended)* vs extending the typed-error list (contract
   edit + `Events1` additive signal — heavier than the case deserves).
