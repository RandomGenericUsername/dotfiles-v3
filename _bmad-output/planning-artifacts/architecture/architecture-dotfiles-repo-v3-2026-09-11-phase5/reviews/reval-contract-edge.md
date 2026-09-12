# Re-evaluation — Event Contract Edge-Case Hunt

- **Reviewer:** edge-case-hunter (no prior context; independent pass)
- **Subject:** `contracts/event-contract.md` (144 lines), `contracts/event-contract.json` (52 lines), against `ARCHITECTURE-SPINE.md` AD-34/AD-37/AD-38/AD-44 (Phase 5)
- **Method:** walk every boundary named in the task, assume two independent AD-conformant implementers (Python hub; GJS bar/jobs), and ask "what does the document make each of them do at this edge?" Findings are limited to boundaries with no defined outcome or a defined-but-wrong outcome.
- **Status legend:** `HANDLED` = enough text to implement deterministically; `MISHANDLED` = defined outcome that is wrong/unsafe; `UNTESTED` = no outcome defined, two implementers diverge; `BLOCKING` = must be pinned before story 5-2/5-4 code.

**Verdict: CONDITIONAL — the transport, ownership, and topic names are sound, but the delivery identity, job lifecycle, and time semantics are not implementation-ready. 5 blocking edges (E1, E2, E3, E4, E5) and 9 non-blocking edges remain undefined or untested. Do not write 5-2/5-4 conformance tests until E1–E5 are pinned.**

The rule at `event-contract.md:54` ("discard any signal whose `(epoch, seq)` is not greater than the hydrated pair") is the contract's central correctness mechanism. Four of the five blockers are cases where the wire cannot supply that pair, or where the trigger that establishes the epoch is itself lossy.

---

## Summary of boundaries

| # | Boundary | Status | Citation |
| --- | --- | --- | --- |
| E1 | `(epoch, seq)` discard rule vs signal members | **BLOCKING — UNTESTED** | md:43–47, 54, 60–61 |
| E2 | `JobsCleared` lost / hub-start-while-down | **BLOCKING — UNTESTED** | md:47, 51, 62; json:25 |
| E3 | Job liveness: crash without `EndJob`, child not spawned by hub, job outlives hub restart | **BLOCKING — UNTESTED** | md:33–36, 44–45; spine:65 |
| E4 | `BeginJob`/`Emit` timeout; `EndJob`/`ReportProgress` unknown/ended id | **BLOCKING — UNTESTED** | md:33–35 |
| E5 | `capture.state.started_at` wall-clock vs monotonic convention | **BLOCKING — MISHANDLED** | md:70, 73–75; spine:117 |
| E6 | Unknown / never-emitted / empty-value topic | UNTESTED | md:37, 60–61; json:41–46 |
| E7 | `seq`/`epoch` overflow, wrap, reset vs bump, epoch persistence | UNTESTED | md:56–61; json:29–30 |
| E8 | Two hubs / epoch collision | HANDLED (name) / UNTESTED (epoch) | md:15–18; spine:39, 74 |
| E9 | `job_id` reuse/collision; epoch on `GetActiveJobs` | UNTESTED | md:36; json:17 |
| E10 | Payload size/depth caps unquantified; rejection mechanism | UNTESTED | md:79–81; json:32–35 |
| E11 | Rate-limit backpressure: drop / error / coalesce | UNTESTED | md:79–81 |
| E12 | Unknown topic emission; additive topic/field vs strict consumer | UNTESTED | md:22–25, 79–81 |
| E13 | `DomainEvent.producer` self-asserted, not validated | MISHANDLED (framing) | md:46, 67–71, 79–81; json:24, 37–50 |
| E14 | Bus/session restart mid-operation | UNTESTED | md:142–144 |
| E15 | `GetActiveJobs` `a{ss}` cannot express staleness/epoch/progress | UNTESTED | md:36; json:17 |

---

## Blocking findings

### E1 — BLOCKING — The discard rule cannot be applied to the signals that exist

**Boundary:** consumer starts between a `DomainEvent` and its `GetTopicState`; hydration/restart reconciliation in general.

**Evidence:** `md:54` requires dropping "any signal whose `(epoch, seq)` is not greater than the hydrated pair"; `md:60–61` says "consumers compare `(epoch, seq)` pairs, never `seq` alone." But:
- `DomainEvent` carries `topic, producer, seq, payload` (`md:46`; json:24) — **no `epoch`**.
- `JobStarted`, `JobProgress`, `JobFinished` (`md:43–45`) carry **neither `epoch` nor `seq`**.
- `JobsCleared` carries `epoch` but no `seq` (`md:47`).
- Only the hydration reply supplies both, as reserved keys (`md:60–61`).

**Why it breaks:** a consumer must synthesize the epoch from the last `JobsCleared` it happened to receive. Because `JobsCleared` is at-most-once (`md:51`), that epoch may be stale; the consumer then either drops fresh events (if derived epoch is "ahead" after wrap) or admits stale-epoch events (if "behind"). For a fresh consumer that starts after a `DomainEvent` but before its `GetTopicState`: it can reconcile a buffered `DomainEvent` against the hydrated pair correctly *only if* it also knows the epoch of that buffered event — which is not on the wire. If a restart happened in the window, the buffered event is indistinguishable from a current one except by `seq`, which is explicitly the wrong key. Lifecycle signals have no key at all, so a late `JobStarted` delivered after a `GetActiveJobs` reply that already omitted the job will re-add a finished job forever.

**Minimal fix:** put `epoch:u` on every signal that carries `seq` or `job_id` — `DomainEvent`, `JobStarted`, `JobProgress`, `JobFinished` — and return `epoch` from `GetActiveJobs` as well. Restate `md:54` as: compare `(epoch, seq)` per topic for `DomainEvent`; compare `epoch` for `Job*` and treat any `job_id` not in an `epoch`-tagged hydration as foreign. Add `seq` to `JobProgress`/`JobFinished` if per-job ordering is wanted. These are additive members on `Events1` (json:8–10).

---

### E2 — BLOCKING — `JobsCleared` is at-most-once and is the only restart trigger

**Boundary:** consumer starts while hub is down then hub starts/restarts (no `JobsCleared` seen); `JobsCleared` lost leaving stale `job_id`s.

**Evidence:** `md:51` ("Signals are at-most-once — a consumer that is not listening misses them"); `md:47` makes `JobsCleared(epoch)` the sole "hub restarted" signal; `md:62` tells consumers to "tolerate `JobsCleared` by re-hydrating." The only hydration instruction is subscribe-then-read (`md:52–54`), which is defined for a consumer that *starts* — nothing re-hydrates a consumer that is already running when the hub dies.

**Why it breaks:** D-Bus match rules do not survive a hub name owner change in a way that guarantees delivery of a signal the hub emits immediately after acquiring the name. A consumer subscribed before the hub existed may or may not receive the first `JobsCleared`. If it misses it:
- it never re-hydrates, so stale `job_id`s (`GetActiveJobs` persisted only in the bar's memory) render forever;
- its derived epoch never advances, so every post-restart signal is mis-compared (E1);
- if the hub never emits `JobsCleared` on its *first* start (the text says "on restart the epoch bumps," `md:57–58`), a consumer that started while the hub was down gets no signal at all.

**Minimal fix:** require consumers to also monitor `NameOwnerChanged` for `org.dotfiles.Events` and to re-run subscribe-then-hydrate + drop all known topics/jobs on owner loss (`md:62` becomes the secondary path, not the only one). Require the hub to emit `JobsCleared(epoch)` on **every** start including the first, with `epoch` initialized to 1 from a persisted counter. Define a hub-absent method reply as `ServiceUnknown` and state the consumer must treat it as "no state + retry on owner appearance," not as a no-op error (`md:142–143`).

---

### E3 — BLOCKING — No liveness path for a job the hub never spawned

**Boundary:** job crashes without `EndJob`; job outlives a hub restart; transitive ownership.

**Evidence:** AD-37 (`spine:65`) says lifetime-job ownership is transitive — "if a wrapper spawns it and would exit, ownership is handed to the hub" — and "the **hub** emits the lifecycle signals." The contract gives the hub only `BeginJob`/`ReportProgress`/`EndJob` calls (`md:33–35`); it has no child handle, no `waitpid`, and (by `md:144` and spine:117) no polling. `EndJob` is the only way a job leaves the registry.

**Why it breaks:**
1. The hub cannot detect an exit of a process it did not fork. If the job process dies (crash, SIGKILL, session EOF) without calling `EndJob`, the registry entry leaks and no `JobFinished` is emitted — the bar's indicator sticks forever.
2. If the caller is a short-lived wrapper (the current `capture-tool` is described as exactly this in the source memlog), the caller's D-Bus connection disappears immediately while the observed child lives. Tying liveness to the caller connection would synthesize a false `JobFinished`; tying it to the child is impossible for the hub. The contract cannot express transitive ownership at all.
3. Job outliving a hub restart: the job keeps running and later calls `ReportProgress`/`EndJob` against a hub whose in-memory registry is empty. Outcome undefined (E4). The bar hydrates an empty job list while the process genuinely runs — silent divergence.

**Minimal fix:** pin the model explicitly: a lifetime job MUST be a **long-lived, D-Bus-connected controller** that holds the observed child for the child's whole life and calls `EndJob`; a wrapper may not `BeginJob`. Require the hub to bind each `job_id` to the caller's unique bus name and synthesize `JobFinished(job_id, exit_code=-1)` when that name vanishes without `EndJob` (this covers crash). For hub restart: either persist active jobs under `state_root` and re-adopt on start (emitting `JobStarted` for adopted ids before `JobsCleared`, or after but in the new epoch), or define that a job finding itself absent from `GetActiveJobs` re-calls `BeginJob`. AD-37's "ownership handed to the hub" needs a decision (hub-as-registry vs hub-as-supervisor).

---

### E4 — BLOCKING — Method timeout and out-of-registry method semantics undefined

**Boundary:** bus disconnection mid-operation; method call timeout on `BeginJob`/`Emit`; `EndJob` for unknown/already-ended job; `ReportProgress` after `JobFinished`.

**Evidence:** `md:33–35` define the three job methods and `Emit`, with no error names and no idempotency/timeout clause. `md:79–81` validates `Emit` structurally but says nothing about method arguments; `fraction` range is stated (`md:34`) but not enforced. At-most-once (`md:51`) means retries can duplicate.

**Why it breaks:**
- `BeginJob` timeout: the job cannot know whether the hub registered it. If it retries, two jobs exist (or two `JobStarted` signals). If it doesn't, it may be invisible.
- `Emit` timeout: the producer cannot know whether the event was published; a retry may duplicate a `DomainEvent` (there is no dedupe key). Under same-UID trust, duplicates are a correctness nuisance (e.g. `icme.saved` triggers a second regen).
- `EndJob` unknown/already-ended: two conformant hubs differ (idempotent no-op vs `UnknownJob` error), so a retrying job behaves differently per hub.
- `ReportProgress` after `JobFinished`: no rule; the hub may emit progress after the terminal, violating `JobStarted < JobProgress* < JobFinished`.

**Minimal fix:** define typed errors on `org.dotfiles.Events1` (`UnknownJob`, `Rejected`, `RateLimited`) and state which methods are idempotent. Make `EndJob` on an unknown/ended id an idempotent no-op that emits no second `JobFinished`; make `ReportProgress`/`EndJob` for a non-current-epoch id a no-op (or `UnknownJob`). State that a timed-out `BeginJob` MUST be retried until an id is returned and that a job MUST NOT begin visible work before it holds an id. For `Emit`, either add a client-generated `emit_id` to `DomainEvent` for dedupe or explicitly declare duplicate `DomainEvent`s benign and consumers idempotent.

---

### E5 — BLOCKING — `capture.state.started_at` is wall-clock against a monotonic-clock convention

**Boundary:** `started_at` epoch ambiguity (clock skew/adjustments; 0 sentinel; restart); "can the bar reconstruct elapsed correctly."

**Evidence:** `md:70` pins `started_at` as "unix secs, 0 when idle" (json:43–45). `md:73–75` requires continuous display to derive "from `started_at` plus a local tick" and "MUST NOT re-read any state file." The spine convention (`spine:117`) says elapsed "derives from a monotonic clock plus one recorded start."

**Why it breaks:**
- Unix seconds are CLOCK_REALTIME; an NTP step or manual clock change makes `now_wall − started_at` jump or go negative. The bar's "local tick" is CLOCK_MONOTONIC, a different clock domain, so it cannot anchor to a wall-clock `started_at` without a one-time conversion — which is invalid across a step or suspend (`CLOCK_MONOTONIC` may exclude suspend where `CLOCK_BOOTTIME` includes it). A recording spanning suspend will show wrong elapsed.
- `0` as the idle sentinel overloads a real value and collides with `E6`'s empty-state problem; a bar cannot distinguish "idle" from "field missing."
- On controller restart mid-recording there is no re-emit duty, so the original anchor is lost and elapsed resets.

**Minimal fix:** make the anchor monotonic: `started_at` = `CLOCK_MONOTONIC` (or BOOTTIME) nanoseconds since an explicit origin, and carry a separate wall-clock `started_wall` only for display. Define idle as **omitting** `started_at` (or a `null`/`-1` sentinel), never `0`. Require the controller to re-emit `capture.state` on (re)connect and the bar to re-anchor on a detected clock step. If wall-clock seconds must stay, the contract must state the timer is best-effort across clock adjustments and suspend, which contradicts `spine:117`.

---

## Non-blocking findings

### E6 — UNTESTED — Unknown / never-emitted / legitimately-empty topic

- `GetTopicState` (`md:37`; json:18) returns `state:a{sv}` with no error for an unknown topic. `md:60–61` only promises reserved `_epoch`/`_seq`. A consumer cannot distinguish unknown topic / known-never-emitted / known-empty-payload. `md:51`'s "absence is a no-op" is about producers, not queries.
- A topic whose payload is legitimately empty (or whose string value is `""`) is indistinguishable from "no state" if the never-emitted reply is `{}`.
- **Minimal decision:** define `org.dotfiles.Events1.UnknownTopic` for topics absent from `event-contract.json`; define known-never-emitted as exactly `{"_epoch":E,"_seq":0}`; always emit the reserved keys; forbid wholly-empty payloads for topics with required keys (E12).

### E7 — UNTESTED — `seq`/`epoch` overflow, wrap, reset-vs-bump, persistence

- `seq:u` and `epoch:u` are 32-bit (`md:56–59`; json:24–30). No wrap rule; `md:54`'s "not greater" is broken by wrap (`65535 > 0`).
- "The epoch bumps on restart" (`md:57–58`) implies persistence, but no storage is specified. An in-memory epoch restarts at 0/1 — a *decrease*, not a bump — and all consumers holding the prior epoch drop every new event.
- **Minimal decision:** persist `epoch` under `state_root` as a monotonically-increasing counter (refuse to emit `JobsCleared` if it would wrap; escalate as fatal). State unsigned lexicographic `(epoch, seq)` comparison explicitly. Same for `seq` per topic, or declare wrap = new epoch.

### E8 — HANDLED (name) / UNTESTED (epoch) — Two hubs / epoch collision

- `md:15–18` + `spine:39,74` (DO_NOT_QUEUE, fail-fast on contention) make simultaneous ownership impossible, so a shadow hub cannot coexist. That part is handled.
- The epoch source is not pinned, so a rolling restart can reuse an epoch value; `NameOwnerChanged` and `GetActiveJobs` give the consumer no way to distinguish a reused epoch from the current one if values collide.
- **Minimal decision:** make `epoch` a persisted strictly-increasing counter (E7); state that epoch collision is impossible while name ownership is exclusive, and that a second candidate exits non-zero (already AD-33).

### E9 — UNTESTED — `job_id` reuse/collision; no epoch on `GetActiveJobs`

- `md:33` says only "hub allocates `job_id`"; uniqueness scope/lifetime unstated. A per-epoch counter reuses ids after restart; `GetActiveJobs` (`md:36`; json:17) returns `a{ss}` with no epoch, so a consumer cannot scope an id to an epoch. A reused id is attributed to the wrong job.
- **Minimal decision:** `job_id` is a random 128-bit id (or `epoch:counter`) never reused; change `GetActiveJobs` to include the hub `epoch` (ties to E1/E15).

### E10 — UNTESTED — Payload caps unquantified; rejection mechanism unspecified

- `md:79–81` and json:32–35 name `max_payload_bytes`, `max_payload_depth`, `publish_rate` but give **no numbers**, so two hubs reject at different thresholds and a producer cannot size payloads.
- "rejects non-conforming events" (`md:81`) does not say whether rejection is a D-Bus error, a silent drop, or disconnect. A producer cannot tell success from rejection.
- **Minimal decision:** pin numeric caps in `event-contract.json` (e.g. 64 KiB, depth 8, N/s per connection); specify a typed `org.dotfiles.Events1.Rejected` error and that a rejected `Emit` emits **no** `DomainEvent`.

### E11 — UNTESTED — Rate-limit backpressure behavior

- `md:79–81` mentions "a publish rate" but no behavior on exceed. AD-40 coalesces **file** events only (`spine:87`); bus events are unaddressed. Drop vs error vs coalesce are all conformant.
- **Minimal decision:** return a typed `RateLimited` error (retryable) for `Emit` rather than silent drop; explicitly permit the hub to coalesce only `JobProgress` (as in the earlier M2 recommendation), never `JobStarted`/`JobFinished`/`DomainEvent`.

### E12 — UNTESTED — Unknown topic / additive field vs strict consumer

- `md:22–25` declares additive changes non-breaking, but the JSON payload blocks (`json:41–50`) mark no key `required` vs `optional`, and the contract never states "consumers MUST ignore unknown keys/topics." A strict consumer that hard-fails on an unknown key breaks additive evolution; conversely a hub that validates an exact key set makes additive impossible.
- **Minimal decision:** encode per-key `required:true|false`; require the hub to accept unknown *optional* keys and reject missing required ones; require consumers to ignore unknown topics and unknown payload keys. (The hub is the sole broker/emitter, so a new topic can ship in JSON + hub together without consumer lockstep.)

### E13 — MISHANDLED (framing) — `DomainEvent.producer` is self-asserted

- `md:46` carries `producer:s`; json:37–50 pins a producer per topic; `md:67–71` presents "Producer" as if authoritative; yet `md:79–81` and `spine:74` state the hub does **not authenticate the sender** (structural validation only, same-UID trust). The confirmatory pass already calls the field "advisory/self-asserted" (review-confirmatory.md:93), contradicting the prose framing.
- Consistent with AD-38's structural-only validation, but the field is redundant and can disagree with the topic→producer map; a drift test must not treat it as authoritative. The earlier "hub validates `producer`" intent (memlog:51 NEW-1) is void.
- **Minimal decision:** drop `producer` from `DomainEvent` (topic→producer map in JSON is the single source of truth), or explicitly declare it informational and ignored by consumers and not cross-checked by the hub.

### E14 — UNTESTED — Bus/session restart mid-operation

- `md:142–144` covers producer/consumer absence but not a `dbus-daemon` restart: all connections and matches drop, the hub loses its name and restarts (AD-33 `Requires=dbus.socket`), and any in-flight method call is lost. There is no `NameOwnerChanged` (it is a bus-daemon signal) and the session address may change.
- **Minimal decision:** state that a bus/session restart is equivalent to a hub restart (epoch bumps from the persisted counter), that all in-flight calls are failed and retried, and that consumers re-subscribe/re-hydrate on successful reconnection; document that signals emitted during the outage are lost by design.

### E15 — UNTESTED — `GetActiveJobs` `a{ss}` cannot express staleness

- `md:36`; json:17 return only `job_id → kind`. No `epoch` (can't tell whether the reply is from the consumer's epoch), no `started_at` (can't detect a stuck job), no `fraction` (the speed-test animation cannot hydrate — `md:71` is terminal-only). Combined with E2 (lossy `JobsCleared`), a consumer that hydrated before a restart cannot detect that its list is stale.
- **Minimal decision:** return `(epoch:u, jobs:a{s(ssd)})` — id → `(kind, started_at, fraction)` — or add a resumable `speedtest.state` topic; at the least return the hub `epoch` so the consumer can scope the set (ties to E1/E9).

---

## Top 5

1. **E1 (blocking):** `(epoch, seq)` is the mandated correctness key (`md:54,60–61`) but `DomainEvent` lacks `epoch` (`md:46`) and `Job*` signals lack both — the discard rule is inapplicable and the hydrate/restart race is unguarded.
2. **E2 (blocking):** `JobsCleared` is at-most-once (`md:51`) and is the only re-hydration trigger (`md:62`); a missed one strands stale jobs and a stale epoch forever. No `NameOwnerChanged` duty; no `JobsCleared` on first start.
3. **E3 (blocking):** no liveness path for a job the hub did not spawn (crash without `EndJob`) and no re-registration protocol across hub restart; AD-37's transitive ownership (`spine:65`) is inexpressible with call-only methods.
4. **E4 (blocking):** `BeginJob`/`Emit` timeout and `EndJob`/`ReportProgress` unknown/ended-id semantics are undefined; at-most-once plus no idempotency key yields duplicate or orphaned jobs.
5. **E5 (blocking):** `capture.state.started_at` is wall-clock unix seconds (`md:70`) against a monotonic-clock convention (`spine:117`); clock steps/suspend break elapsed and `0` overloads the idle sentinel.

## Minimal decision set (one revision)

1. Add `epoch:u` to `DomainEvent`, `JobStarted`, `JobProgress`, `JobFinished`; return `epoch` from `GetActiveJobs` and `GetTopicState`; restate `md:54` per signal.
2. Require `NameOwnerChanged`-driven re-hydration in addition to `JobsCleared`; require `JobsCleared` on every start; define hub-absent replies and retry.
3. Pin job liveness: long-lived controller owns the child; hub synthesizes `JobFinished(-1)` on caller-name loss; define hub-restart re-adoption/re-registration.
4. Add typed `UnknownJob`/`Rejected`/`RateLimited` errors; pin idempotency of `EndJob`; define timeout + `BeginJob` retry-before-work; add `emit_id` or declare duplicates benign.
5. Make `started_at` monotonic (or add `started_at_monotonic`), define idle by omission, require re-emit on reconnect.
6. Non-blocking: pin payload caps and rejection behavior; encode `required`/`optional`; declare consumers ignore unknown keys/topics; drop or demote `producer`; persist and never-wrap `epoch`; random `job_id`; define unknown-topic error.
