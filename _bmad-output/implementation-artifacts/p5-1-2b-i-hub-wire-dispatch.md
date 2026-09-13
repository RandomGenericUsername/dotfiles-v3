# P5‑1‑2b‑i: Hub Wire Binding — jeepney Adapter + Job-Method Dispatch + Typed Errors + Conformance

Status: done

baseline_commit: a82eb73

Gate‑1 ruling note (amended at DEV time, Gate‑2 approved as pre-authorized):
the story specified `dasbus` 1.7, but dasbus unconditionally imports `gi`
(PyGObject) at module import, and `gi` is absent from the hermetic uv venv
(`ModuleNotFoundError`, reproduced at build time) — so dasbus is unwirable
both in tests and in the deployed `uv tool` env, exactly the trigger for
the story's own pre-authorized fallback. **Ruling executed: `jeepney`
0.9.0** (pure Python, sync blocking API, zero native deps, `uv add`-able;
hermetic-safe). AC 1, Dev Notes, and Q2 are amended accordingly;
everything else stands as approved.
Gate 2: applied — Items 1–3 (adapter correctness: Hello deletion,
RequestName error mapping, re-acquire re-arm, answer/thread guards,
bus-death routing, foreign-interface reply, arity naming, spin/None
guards; seam table + deviation notes + jeepney story amendment; six
tests). Verified: runtime 1151 passed, 2 skipped; layering green;
contracts-check green; mypy --strict clean on the adapter; ruff no new;
plus a LIVE bus smoke (acquire/serve/call/release + contention, bus
left clean).
(dirty tree observed at draft time, NOT committed: `M
_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md`,
`M
_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md` —
no code changes made by this draft.)

Gate 1: APPROVED (recs as-is: split yes; jeepney executed per the amended
ruling above; caps carried from 2a Gate‑1: 64 KiB / 8 / 60-min for 2b‑ii;
topic store hub-owned in-memory; seq per-topic within epoch; rate key
(sender, topic) + global ceiling; synthetic-expiry queue-then-emit;
NameOwnerChanged → restart).

Epic: Phase 5 epic 5‑1 — Daemon foundation, observability & safety (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`;
spine `ARCHITECTURE-SPINE.md` status `final`, AD‑33/AD‑34/AD‑38).

## Story

As the daemon operator,
I want the 2a hub serving its job-registry surface on the session bus behind
the owned name — a real jeepney-based D‑Bus adapter dispatching the job
methods per `event-contract.xml` signatures with wire-width validation and
typed errors,
so the registry semantics 2a proved in-process become callable over
`org.dotfiles.Events1` before the Emit/topic-state/signal slice (P5‑1‑2b‑ii)
attaches the event surface.

## Context (why this slice, what 2a left, what it must match)

Epic 5‑1 as written is too big for one commit; P5‑1‑2 as scoped (9 methods +
5 signals + epoch/seq + JobsCleared + leases/expiry + AdoptJob + Control +
typed errors + structural validation + ports/adapters + XML/JSON conformance
+ daemon serve) is still too big for one surgical, landable commit
(pytest/ruff/mypy/layering green, one behavior) — the same argument that
split 2a. So P5‑1‑2b splits:

- **P5‑1‑2b‑i (this story):** the WIRE transport + job-method dispatch —
  `jeepney` as a declared dependency, a real session-bus adapter publishing
  the job surface (`BeginJob`/`RenewJob`/`AdoptJob`/`ReportProgress`/
  `EndJob`/`Control`/`GetActiveJobs`) per `event-contract.xml` signatures,
  wire-width validation (`ttl:u`, `pid:u`, `exit_code:i`, `fraction:d`),
  typed domain errors mapped to D‑Bus error names, executable XML↔JSON
  conformance for the methods block, `daemon run` serving the job surface
  (replacing the deferred-placeholder path for these methods).
- **P5‑1‑2b‑ii (next):** the EVENT surface — `Emit` + structural validation
  (schema/size/depth/rate caps per the 2a Gate‑1 ruling: 64 KiB / 8 /
  60-min → `RateLimited`; known_topic_only), topic-state store + per-topic
  `seq` + `GetTopicState` (reserved `_epoch`/`_seq`), signal emission with
  epoch (`JobStarted`/`JobProgress`/`JobFinished`/`DomainEvent`/
  `JobsCleared`), synthetic-expiry → `JobFinished` wiring, `NameOwnerChanged`
  handling.

What 2a built (this story binds, does not rebuild): `domain/hub.py`
(`EventHub` + `HubEvent` with kind/job_id/epoch/fraction/exit_code/pid
fields), `ports/event_bus.py` (`IEventPublisher`/`IEventSubscriber`/
`IJobRegistry` ABCs), `adapters/in_process_hub.py` (fake),
`adapters/dbus_name_owner.py` (deferred placeholder whose `acquire()`
always fails), daemon wiring in `cli/main.py` (`_build_bus_name_owner`,
`_build_hub`, `_run_daemon_run` — hub constructed in-process, epoch
assigned, `JobsCleared` recorded, nothing on the wire).

What 2b‑i inherits from the 2a Gate‑2 review (preconditions, all load-bearing
— see `p5-1-2a-hub-registry-leases-gate2-review.md` Item 1):
sink-must-not-raise (state stored before append; the emitter must be
infallible by construction — queue-then-emit or emit outside the registry);
single-threaded caller (check-then-act assumes no concurrency — the
dispatcher must serialize); wire-width validation owed (domain takes
`float` ttls and unbounded ints; dispatch validates `u`/`i` widths);
contract-name mapping snake_case sink tags ↔ PascalCase signal/method names;
`job_adopted`/`pid` dropped on the wire (no contract signal carries a pid —
adoption stays observable in-process); `-1` reservation (explicit
`EndJob(job, -1)` rejected in-domain; the synthetic path writes the
constant directly).

Contract files this story must match (read-only, no extension needed):
`contracts/event-contract.md`, `contracts/event-contract.json`,
`contracts/event-contract.xml` (AD‑44 wire source). The contracts already
specify the complete surface — all 9 methods with D‑Bus signatures (XML),
all 5 signals with members, the 6 typed errors (JSON `errors`),
lease/expiry semantics (`job_lease`), epoch/restart semantics (`delivery`).
**2b‑i needs NO contract change.** Two deliberate deferrals to 2b‑ii:
(1) structural cap NUMBERS live in code + tests, NOT in the contract files
(JSON `validation.structural` lists categories only); (2) the topic-state
store is written by `Emit`, so it travels with 2b‑ii, not 2b‑i. The
conformance tests in 2b‑i pin the methods block; the signals/topics blocks
are pinned executable in 2b‑ii.

What 2b‑i deliberately does NOT include (2b‑ii or later own it): `Emit`,
topic-state store, `GetTopicState`, `seq`, structural validation, signal
emission on the bus, `NameOwnerChanged`, watches / converge (P5‑1‑3), bar
binding (epics 5‑2/5‑4), status surface (P5‑1‑4), new topics, Events2.

## Acceptance Criteria

1. Declared transport dependency: `jeepney` lands via `uv add jeepney` in
   `src/runtime/pyproject.toml` (amended Gate‑1 ruling — see header note:
   dasbus rejected on evidenced `gi` absence; jeepney is pure-Python,
   sync, hermetic-safe); the layering test's declared-deps rule stays
   green; the D‑Bus client import lives in `adapters/` ONLY — domain,
   ports, application, and CLI stay transport-agnostic. (AC 1)
2. Job-method dispatch per the wire source: the adapter publishes exactly
   the 2a-owned surface on `/org/dotfiles/Events` /
   `org.dotfiles.Events1` — `BeginJob(kind:s, ttl:u)→job_id:s`,
   `RenewJob(job_id:s)`, `AdoptJob(job_id:s, pid:u)`,
   `ReportProgress(job_id:s, fraction:d)`, `EndJob(job_id:s, exit_code:i)`,
   `Control(job_id:s, action:s)`, `GetActiveJobs()→jobs:a{ss}` — with
   argument names/order/directions byte-matching `event-contract.xml`;
   `Emit`/`GetTopicState` are NOT published yet (2b‑ii adds them; their
   absence must fail loud, never silently no-op). (AC 2)
3. Wire-width validation at dispatch (the owed 2a Gate‑2 item): `ttl:u`
   rejects negatives, non-ints, and over-`u32` values before the domain
   ever sees them; `pid:u` likewise; `exit_code:i` rejects out-of-`i32`
   values; `fraction:d` range violations stay a domain `ValueError` mapped
   to a generic D‑Bus error (NOT a typed contract error — the typed list
   has no `BadFraction`, per 2a Gate‑1 rec 6). (AC 3)
4. Typed errors mapped to D‑Bus error names: `UnknownJob`, `JobEnded`,
   `NotControllable` (the 2a-owned subset of the JSON `errors` list) cross
   the wire as `org.dotfiles.Events1.<Name>` with the offending
   `job_id`/detail preserved; `UnknownTopic`/`PayloadTooLarge`/
   `RateLimited` are Emit-side and arrive with 2b‑ii. (AC 4)
5. Serialization (2a single-threaded-caller precondition): all dispatch
   into the hub is serialized outside the registry (one lock in the
   adapter/dispatcher, never in domain); no concurrent caller can interleave
   a check-then-act sequence. (AC 5)
6. Sink infallibility preserved (2a sink-must-not-raise precondition): the
   dispatch path performs NO bus emission inside a registry call — the sink
   stays the log-only sink in 2b‑i (signals arrive in 2b‑ii), so no raising
   emitter can wedge registry state ahead of the event stream. (AC 6)
7. Executable conformance: a test parses `contracts/event-contract.xml`
   and asserts the adapter's published methods (names, arg names/types/
   directions, out-args) match the methods block exactly, and asserts the
   JSON `methods` table agrees; the signals/topics blocks are asserted as
   2b‑ii-owned (present in contract, absent on the wire — pinned, not
   forgotten). (AC 7)
8. `daemon run` serves the job surface: `_build_bus_name_owner` wires the
   real jeepney owner (replacing the deferred placeholder for the served
   methods), `_build_hub` stays the composition root (epoch bumped
   in-memory per start, `JobsCleared` recorded first), and the daemon owns
   the name first (AD‑33 `RequestName(DO_NOT_QUEUE)`, fail-fast) before
   serving; the P5‑1‑1 unit steady-state note (start-limit-hit until the
   real client lands) is retired for the job surface. (AC 8)
9. Surgical scope: one commit; `uv run --directory src/runtime pytest` +
   `ruff` + `mypy --strict` + layering gate
   (`tests/architecture/test_layering.py`) green; contract-name mapping
   snake↔Pascal documented at the seam (`job_started`→`JobStarted`, …;
   `job_adopted`/`pid` dropped on the wire per 2a Gate‑2). (AC 9)

## Tasks / Subtasks

- [x] Dependency: `uv add jeepney` in `src/runtime` (declared in
  `pyproject.toml`, satisfying the layering-test third-party rule); no
  other new dependency (AC: 1)
- [x] Adapter: `adapters/dbus_event_bus.py` (per the spine structural seed)
  — session-bus service publishing the 7 job methods against the domain
  `EventHub` via the `IJobRegistry` port; the ONLY module importing
  `jeepney` (AC: 1, 2)
- [x] Dispatch: one handler per XML method signature (arg names/order/
  directions per `event-contract.xml`); unbound `Emit`/`GetTopicState`
  fail loud (absent from the published interface, never a silent no-op)
  (AC: 2)
- [x] Width validation at dispatch: `ttl:u` / `pid:u` / `exit_code:i`
  bounds-checked to wire widths before domain calls; `fraction:d` range
  stays domain-`ValueError` → generic D‑Bus error (AC: 3)
- [x] Error mapping: `UnknownJob`/`JobEnded`/`NotControllable` →
  `org.dotfiles.Events1.<Name>` with detail preserved (AC: 4)
- [x] Serialization: single dispatcher-side lock around every hub call
  (2a precondition; domain stays lock-free) (AC: 5)
- [x] Conformance tests (executable, no live bus required for the parse
  half): XML methods block ↔ adapter surface ↔ JSON `methods` table;
  signals/topics blocks pinned as 2b‑ii-owned (AC: 7)
- [x] Dispatch tests (no live bus): happy paths per method; unknown/ended
  jobs (`UnknownJob`/`JobEnded`); width rejections; unhashable action →
  `NotControllable`; stale id on a fresh hub → `UnknownJob`; `-1` exit
  rejected; layering (no `jeepney` import outside `adapters/`, no `dasbus`
  import anywhere); run pytest
  + ruff + mypy + test_layering (AC: 1–6, 9)
- [x] Daemon wiring: real owner in `_build_bus_name_owner`, serve job
  surface in `_run_daemon_run` after name-first acquire; no use-case call,
  no lock across calls, no mutation (AC: 8)

## Dev Notes

- **Where:** adapter under `adapters/` (check the layering test's allowed
  targets before adding; domain/ports import nothing new). Ports in
  `ports/event_bus.py` need NO change (ABCs already pin the seam).
  Application layer untouched. Wiring in the `cli/main.py` composition
  root only (same pattern as `_build_bus_name_owner` / `_build_hub`).
- **Transport evidence (dasbus rejected at build time, jeepney executed
  — amended DEV ruling, see header):** `dasbus` 1.7 downloads cleanly as a
  pure-Python wheel, BUT it unconditionally imports `gi` (PyGObject) at
  module import, and `gi` is absent from the hermetic uv venv
  (`ModuleNotFoundError`, reproduced) — so dasbus is unwirable both in
  tests and in the deployed `uv tool` env, exactly the story's
  pre-authorized fallback trigger. Executed: **`jeepney` 0.9.0**
  (pure-Python blocking, zero native deps, `uv add`-able, hermetic-safe)
  at the cost of hand-rolled service-side dispatch (jeepney ships no
  service framework — `open_dbus_connection` + `RequestName` + a
  receive-loop thread + manual reply construction). The project uv venv
  imports `jeepney` today via the declared dependency (layering-test
  rule satisfied).
- **Layering (AD‑1/13/14/25, AD‑34):** core never imports D‑Bus — the
  adapter is the ONLY module that may import `jeepney` (same standing as
  the former `dbus_name_owner.py` header rule). Third-party imports must be
  declared in `pyproject.toml` — `jeepney` landed there in THIS story.
- **Daemon holds no lock across use-case calls (AD‑35):** hub calls are
  registry mutations, not use-case calls — no `.seed.lock`/
  `.history.lock` involvement. The dispatcher-side serialization lock (AC 5)
  guards hub check-then-act only and is never held across a use-case call
  (preserve for P5‑1‑3 converge).
- **Hub emits lifecycle signals; jobs report via methods (AD‑37):** 2b‑i
  serves the REPORT side (methods); the sink stays log-only; 2b‑ii binds
  sink records to real `JobStarted`/`JobProgress`/`JobFinished` signals.
  A UI indicator is driven by DOMAIN events only, never job lifecycle
  (AD‑37) — restate at the 2b‑ii boundary.
- **Contract-name mapping (2a Gate‑2):** sink tags stay snake_case
  (`job_started`, …); wire names are PascalCase (`JobStarted`, …) —
  document the pure-rename table at the seam; `job_adopted`/`pid` have no
  wire signal and are dropped on the wire (ownership trail stays
  in-process for 5‑4).
- **Out of scope:** `Emit`, topic store, `GetTopicState`, `seq`,
  structural validation, signal emission, `NameOwnerChanged`, watches,
  converge, bar, status.

## Gate‑1 sub‑decisions (owner ruling required)

1. **Confirm the split:** 2b‑i as scoped here (transport + job-method
   dispatch + widths + job-subset typed errors + methods conformance +
   serve) with 2b‑ii owning Emit + validation + topic-store/seq +
   `GetTopicState` + all signals + synthetic-expiry wiring +
   `NameOwnerChanged` — *recommended: yes; the full wire binding is not
   one landable commit (same argument that split 2a), and 2b‑i is
   independently testable with the sink still log-only*.
2. **Transport ruling — EXECUTED at DEV as `jeepney` 0.9.0** (amended;
   see header note): the specified `dasbus` 1.7 proved unwirable —
   unconditional `import gi` fails in the hermetic venv *and* the deployed
   `uv tool` env. Gio symmetry with the GJS side is real but requires
   non-hermetic packaging — rejected in favor of hermetic `uv` builds per
   the story's own fallback clause. Landed as a declared
   `pyproject.toml` dependency in THIS story (layering-test rule).
3. **Topic-state store location (shapes 2b‑ii; rule now so 2b‑i's seam
   fits): *recommended: hub-owned in-memory dict*** (`topic →
   (payload, seq)`, reset on epoch bump) — the store is written by
   `Emit` and invalidated by `JobsCleared` by design, so hub ownership
   keeps write + invalidate + `GetTopicState` in one place with no
   cross-module consistency protocol; vs a separate adapter-side state
   (splits the writer from the invalidator across the port for zero
   gain; persistence buys nothing — `JobsCleared` already invalidates
   all prior state on every start).
4. **Seq reset scope (2b‑ii implements; rule now): *recommended:
   per-topic counters reset to 0 on every epoch bump***, exactly per the
   contract `delivery.ordering` ("per-topic monotonic seq (u) within an
   epoch (u); epoch bumps and seq resets on every hub start") — consumers
   compare the `(epoch, seq)` pair, never `seq` alone, so absolute values
   carry no meaning across restarts.
5. **Rate-limit accounting key (2b‑ii implements; rule now): *recommended:
   (sender unique-name, topic) with a global per-hub ceiling as
   backstop*** — the sender unique name is bus-attested (supplied by the
   daemon, never self-asserted), so keying on it does NOT violate AD‑38's
   structural-only trust (which forbids per-sender IDENTITY
   authorization, not bus-attested accounting); vs per-topic-only (one
   chatty producer starves the topic) or global-only (one producer
   starves the hub). Numbers stay the 2a Gate‑1 ruling (60/min →
   `RateLimited`) unless retuned here.
6. **Synthetic-expiry emission path (2b‑ii implements; rule now to
   protect the 2a precondition): *recommended: queue-then-emit*** — the
   lazy sweep records synthetic finishes to an internal queue inside the
   registry call and the adapter emits `JobFinished(exit_code=-1)` AFTER
   the call returns, so the sink/emitter can never raise inside a
   registry mutation (preserves sink-must-not-raise); vs direct emission
   in the sweep path (a bus failure mid-sweep wedges registry state
   ahead of the event stream — the exact failure the 2a Gate‑2 review
   rejected rollback discipline for).
7. **NameOwnerChanged handling shape (2b‑ii implements; rule now):
   *recommended: treat as restart → epoch bump + `JobsCleared`*** —
   belt-and-braces per the contract (`delivery.restart_signal`:
   consumers already treat `NameOwnerChanged` as a restart signal since
   `JobsCleared` is itself at-most-once); the daemon side subscribes to
   `NameOwnerChanged` on `org.dotfiles.Events` and re-runs the
   start path (fresh epoch, empty registry, `JobsCleared` first) rather
   than attempting to resume prior `job_id`s.
