# Contract Robustness Review — Phase 5 Event Contract

- **Reviewer:** contract-robustness (VALIDATE gate, ad-hoc lens; spine not edited)
- **Subject:** `contracts/event-contract.md`, `contracts/event-contract.json`, assessed against `ARCHITECTURE-SPINE.md` (AD‑33..AD‑42) and `.memlog.md`
- **Scope:** engineering robustness the spine underspecifies — delivery, ordering, correlation, evolution, typing, backpressure, idempotency, hydration, versioning, and whether the rung‑2 JSON can express it all.
- **Verdict:** **REJECT — do not implement the contract as written.** The names, topics, and drift-test decision are sound, but the *semantics* of the interface are absent. Findings C1–C2 are blocking; H1–H5 must be closed before any story in epic 5‑2/5‑4 is written, because two conformant implementers (Python hub, GJS bar/jobs) would build incompatible lifecycles from the same document.

Method: assume two teams implement only this contract verbatim (hub in Python, consumers in GJS), then test the documented scenarios — capture mid‑recording, speed‑test animation, daemon restart, `Events1`→`Events2`, and the hub's authorization/validation duty. Every finding below is a point where the two teams diverge or a scenario has no defined outcome. Where the review prompt posited an ambiguity not present in the artifacts, that is stated, not invented.

---

## Critical

### C1 — CRITICAL — Lifecycle signals have no producer path on the hub interface

- **Evidence:** `event-contract.md:52-81` defines the hub interface with exactly three methods (`Emit`, `GetActiveJobs`, `GetTopicState`) and four signals (`JobStarted`, `JobProgress`, `JobFinished`, `DomainEvent`). The only inbound method is `Emit(topic:s, payload:a{sv})`. Spine AD‑38 (`ARCHITECTURE-SPINE.md:75`) says "Jobs and tools emit through the hub's interface and never `RequestName`", and AD‑37 (`:66`) says a lifetime job "publishe[s] lifecycle + domain events".
- **Problem:** There is no mapping from an inbound `Emit(topic, payload)` to the `JobStarted` / `JobProgress` / `JobFinished` *signals*. `Emit` produces a `DomainEvent` (it carries `producer` and emits the `DomainEvent` signal, per the introspection). So a job cannot emit its own lifecycle: `JobStarted`/`JobFinished` are unreachable from any documented call. Conversely, if the hub itself emits lifecycle, it can only do so for children it owns — but capture/speed‑test jobs are spawned by the bar (epic 5‑4), not the daemon, so the hub never sees `fork`/`exit`. Either reading leaves at least one of AD‑37/AD‑38 unimplementable.
- **Concrete decision (minimal):** add explicit lifecycle methods to the hub, one per phase or one generic:
  - `JobStarted(kind:s) → job_id:s` (hub allocates the id and emits the signal),
  - `JobProgress(job_id:s, fraction:d)` (hub validates ownership, emits),
  - `JobFinished(job_id:s, exit_code:i)` (hub validates ownership, emits, deregisters),
  and state plainly in the contract that `Emit` is the **domain-only** path and can never produce a `Job*` signal. Add these method signatures to `event-contract.json`.

### C2 — CRITICAL — `job_id` generation, scope, lifetime, and restart behaviour are undefined

- **Evidence:** `job_id:s` appears in three signals (`event-contract.md:64-75`) and in `GetActiveJobs` (`a{ss}`), but nothing states who creates it, its uniqueness domain, or its lifetime. AD‑38 forbids jobs from owning well-known names, so jobs are transient unique-name connections.
- **Problem:** Two implementers diverge immediately: one lets the job mint `pid:starttime`, the other uses a UUID; the contract cannot interoperate or reconcile them. Worse, the hub's active-job registry is in-memory (it is the only state holder, `memlog.md:51`). On `Restart=on-failure` (AD‑33), a restarted daemon has no knowledge of jobs that started before it: a later `JobFinished(old_id)` is either rejected as unknown or accepted into an empty registry; a bar that hydrated `GetActiveJobs` before the restart keeps rendering a job that no longer exists, forever. `GetActiveJobs` returns `id→kind` only, so the bar cannot even tell that the entry is stale.
- **Concrete decision (minimal):** the **hub** allocates `job_id` = random 128‑bit UUID returned synchronously from `JobStarted`; the hub records `(job_id → caller unique name, kind, CLOCK_MONOTONIC start)`. On hub startup the registry is empty by definition; emit a single `JobsCleared` signal (or `JobFinished(exit_code=-1)` for each known job on graceful shutdown) and add a monotonic `epoch:u` to every `Job*` signal and to `GetActiveJobs` so consumers drop ids not from the current epoch. Never let a job choose its own id.

---

## High

### H1 — HIGH — Hydration/subscribe race is unguarded (lost updates)

- **Evidence:** `event-contract.md:32-35` tells a consumer to "hydrate once via `GetTopicState`/`GetActiveJobs`, then track signals". `memlog.md:51` makes `GetTopicState` "the sole domain-state hydration path".
- **Problem:** "hydrate, then subscribe" has a lost-update window. Between the `GetTopicState` reply and the consumer's `AddMatch` for `DomainEvent`, the hub may emit a transition (e.g. capture `recording`→`idle`). The consumer now holds a stale snapshot and will never see the transition, so it renders `recording` indefinitely. Nothing in the contract gives a revision, sequence, or atomicity guarantee; D‑Bus has no "snapshot + stream" primitive.
- **Concrete decision (minimal):** require **subscribe before hydrate**, and make hydration versioned: every `GetTopicState` reply and every `DomainEvent` for a topic carries a hub-maintained monotonic `seq:u` in the payload (per topic). The consumer adds its match first, then hydrates, and discards the hydrate result if a signal with `seq` greater than the snapshot's has already arrived. State the ordering rule in the contract; the bar's reconnect path (H4/M4) reuses it.

### H2 — HIGH — At‑most‑once signals with no state topic: mid‑event starts and missed terminals are undefined

- **Evidence:** `event-contract.md:104-107` ("Absence is a no‑op, never an error") and D‑Bus signals are fire‑and‑forget. Only `capture.state` has a resumable domain topic (`:93`); `speedtest.finished` (`:94`) is terminal-only, and `GetActiveJobs` returns `a{ss}` (id→kind, no progress/start).
- **Problem:** the two epics' primary use cases break on cold start:
  - A bar that starts **mid‑speed‑test** misses `JobStarted`/`JobProgress`; `GetActiveJobs` tells it a `speedtest` exists but not the fraction or start, and there is no `speedtest.state` topic — the wifi animation cannot be initialized from any documented source.
  - A consumer that misses `JobFinished` (slow reader buffer, job crashes before calling in, hub restarted) has no terminal reconciliation; the indicator sticks. The contract never says a missed terminal is recoverable.
- **Concrete decision (minimal):** make every job kind have a resumable state topic (e.g. `speedtest.state` = `{state, started_at_monotonic, fraction}`), and/or change `GetActiveJobs` to return the full job record (`a{s(ssd)}`: id→(kind,state,fraction)) so hydration is complete. Declare lifecycle signals lossy; declare **state topics authoritative and retrievable**, and require the hub to synthesize `JobFinished(exit_code=-1)` when a job's unique name disappears without a clean finish.

### H3 — HIGH — `capture.state` payload cannot support the mandated continuous-display convention

- **Evidence:** `event-contract.md:93` pins `capture.state` to `{ "state": s }` with enum `idle|recording|paused`. Spine conventions (`ARCHITECTURE-SPINE.md:106`) require elapsed/continuous display to derive "from a monotonic clock plus one recorded start". `memlog.md:50` repeats it.
- **Problem:** no recorded start is on the wire. A bar that hydrates `capture.state` gets `{state:"recording"}` with no origin, so it cannot compute elapsed; if it restarts mid‑recording it has nothing to anchor the monotonic clock to. Pause semantics are also undefined (does elapsed freeze, or accumulate?). This is the user's stated use case #1 (`recording.tsx` polling every 500 ms) and the contract cannot replace it as written.
- **Concrete decision (minimal):** add `started_at` (CLOCK_MONOTONIC µs) and either `accumulated_ms` + `resumed_at` or a plain `elapsed_ms` to `capture.state`; define pause as freeze-and-resume of the monotonic anchor. A timer in the bar may then advance the display locally (allowed by the convention) without re-reading state.

### H4 — HIGH — The rung‑2 JSON cannot express or validate `a{sv}` payloads; the hub's "reject non‑conforming Emit" is unimplementable

- **Evidence:** AD‑38 (`ARCHITECTURE-SPINE.md:75`) requires the hub to "reject a non‑conforming `Emit`" and to validate `producer`. `event-contract.json:18-32` encodes each topic payload as a plain object of letter types (`{"state":"s"}`), and `Emit`/`DomainEvent` carry `payload:a{sv}`. There is no required/optional marker, no numeric range, no variant-signature field, and the enum exists only for `capture.state`.
- **Problem:** an `a{sv}` value's D‑Bus signature is chosen at runtime per entry. The JSON `{ "down_mbps": "d" }` is not machine-checkable against a wire dict that could arrive as `i`, or with extra/missing keys. A hub cannot decide conformance, so AD‑38's rejection duty and `producer` validation have no testable definition. The `memlog.md:51` claim "allowed enum values, not just types" is true only for one topic and still not wire-enforceable.
- **Concrete decision (minimal):** extend each topic schema to a machine-checkable form, e.g. `{"state":{"sig":"s","required":true,"enum":[...]}}`, and require the hub to validate (a) known topic, (b) authorized caller for that topic, (c) exact variant signature and required-key set before emitting `DomainEvent`. Declare `Emit` rejection semantics: a D‑Bus error (`org.dotfiles.Events1.Rejected`) is returned, never a silent drop. Consumers MUST ignore unknown payload keys (forward compat).

### H5 — HIGH — Drift test as specified defeats additive schema evolution and forward compatibility

- **Evidence:** `event-contract.md:96-102`: each language "bakes its constants and ships one small test asserting they equal the JSON"; `:88` says a shape change is breaking (`…Events2`).
- **Problem:** "asserting they equal the JSON" makes the two sides lockstep. Adding a new topic, or a new optional payload field, to `event-contract.json` breaks the *other* side's drift test until it ships simultaneously — directly contradicting `:20-21` ("consumers migrate on their own schedule") and AD‑34's whole reason for versioning. Unknown fields and unknown topics are also unspecified: a producer adding a key can crash a strict consumer. The contract has no notion of additive vs breaking.
- **Concrete decision (minimal):** the drift test asserts the consumer's known name set is a **subset** of the JSON, not equal. Declare: (1) consumers MUST ignore unknown topics and unknown payload keys; (2) adding a topic, or an optional field (with a documented default), is **non‑breaking and does not bump the interface version**; (3) only removed/renamed/retyped fields or changed semantics bump `Events1`→`Events2`. Encode `required`/`optional` in the JSON so "optional addition" is checkable.

### H6 — HIGH — Caller identity for authorization is undefined, and conflicts with the no‑well‑known‑name rule

- **Evidence:** AD‑38 (`ARCHITECTURE-SPINE.md:75`) pins "a caller→topic authorization mapping (allowed **sender identity** per topic)"; AD‑38 also forbids jobs from owning an `org.dotfiles.*` name. `event-contract.md:42-44` restates it without saying what identity is checked.
- **Problem:** the hub's `Emit` validation can only authorize by (a) connection unique name (`:1.42`, unpredictable per run), (b) process credentials via `GetConnectionUnixProcessID` → executable path, or (c) a well‑known name the job is forbidden to own. The contract names none. A transient job that reconnects gets a new unique name, so a static mapping cannot exist; "reject non‑conforming `Emit`" is therefore not implementable or testable.
- **Concrete decision (minimal):** authorize on **process executable path** resolved via `GetConnectionUnixProcessID` (e.g. the capture controller binary, the speed‑test binary), pinned in `event-contract.json` as `allowed_producers` per topic; document that unique names are not identity. Note the deferred Python client must support credential lookup, or the trust boundary (AD‑38) is void.

---

## Medium

### M1 — MEDIUM — Ordering guarantees are unstated; cross‑sender reordering is possible

- **Evidence:** no ordering clause anywhere in the contract. The hub is a single bus name, but jobs are separate connections; if jobs emit lifecycle through `Emit` (C1) and the hub also emits, events for one `job_id` originate from ≥2 senders.
- **Problem:** per D‑Bus, ordering is per sender only. A job's `JobProgress` and the hub's synthesized `JobFinished` can interleave such that the consumer applies progress after finish; two jobs' events interleave (fine) but consumers may wrongly assume global order. Nothing forbids this.
- **Concrete decision (minimal):** require the hub to author **all** lifecycle signals (per C1) so a single sender orders them; add a per‑job monotonic `seq` to `JobProgress`/`JobFinished`; specify "for a given `job_id`: `JobStarted` < `JobProgress*` < `JobFinished`, and consumers drop any event whose `seq` is ≤ the last applied for that id". No ordering is guaranteed across `job_id`s.

### M2 — MEDIUM — No backpressure or coalescing rule for high‑frequency `JobProgress`

- **Evidence:** `JobProgress` (`event-contract.md:68-71`) is a raw `fraction:d` signal with no rate limit; the speed test is a high‑frequency producer. AD‑40 coalesces *file* events (`ARCHITECTURE-SPINE.md:87`) but not bus events.
- **Problem:** an unthrottled progress stream can saturate the session bus (or the bar's main loop) and, because D‑Bus signals are lossy, progress (and possibly a co‑emitted terminal) can be dropped. Conversely, naive coalescing can drop the last progress before finish.
- **Concrete decision (minimal):** declare `JobProgress` **best‑effort and coalescible**: the hub enforces a per‑job minimum interval (e.g. ≤10 Hz) keeping only the latest fraction; `JobStarted`/`JobFinished` are non‑coalescible. Consumers MUST tolerate missing/duplicate/out‑of‑order progress and use the job's latest known fraction as advisory. Document this in the contract so the bar does not treat a dropped progress as an error.

### M3 — MEDIUM — Interface‑level versioning has no migration window

- **Evidence:** `event-contract.md:20-21` ("A breaking change becomes `org.dotfiles.Events2`; consumers migrate on their own schedule") plus AD‑34 (`:46`). The hub owns a single well‑known name and a single interface (`:52`).
- **Problem:** a payload change in one topic (`icme.saved`) bumps the whole interface, forcing the capture/speed‑test consumers to migrate too, and the contract never says the hub serves `Events1` **and** `Events2` concurrently. But AD‑33 makes the daemon long‑lived while bar and jobs are independently restarted, so a migration window is mandatory; "migrate on their own schedule" is not achievable with one interface at one name.
- **Concrete decision (minimal):** keep `org.dotfiles.Events1` stable; version *topics* (`capture.state.v2`) or add optional fields for additive change; reserve `Events2` for structural method/signal changes. If `Events2` is ever needed, require the hub to own both names during a deprecation window and document the overlap. A whole‑interface bump must not be the response to a single‑topic payload change.

### M4 — MEDIUM — Consumer idempotency and reconnect replay are unspecified

- **Evidence:** contract is silent on reconnect/duplication; `event-contract.md:104-107` covers only producer/consumer absence.
- **Problem:** GJS consumers reconnect (session/AGS restart, `NameOwnerChanged` on the hub, hub `Restart=on‑failure`). A re‑hydrate plus already‑delivered signals can apply a transition twice; a hub restart can replay `JobsCleared`/state with no dedupe rule. The contract gives consumers no basis to be idempotent.
- **Concrete decision (minimal):** declare state updates **idempotent last‑write‑wins per topic**, keyed by the `seq` from H1 (drop `seq` ≤ last applied). On `NameOwnerChanged` for `org.dotfiles.Events1`, consumers MUST re‑add matches and re‑hydrate all subscribed topics and the active‑job list. Duplicate `DomainEvent`s are harmless by construction.

### M5 — MEDIUM — Hub liveness is not guaranteed while the synchronous core reconciles

- **Evidence:** AD‑35 (`ARCHITECTURE-SPINE.md:52`) keeps the pipeline synchronous and imperative; the hub is the same daemon process (`:75`) running the reconcile loop.
- **Problem:** a synchronous reconcile blocks the process; if the D‑Bus service and the reconcile loop share one thread/`GLib.MainLoop`, then `GetTopicState`/`GetActiveJobs`/`Emit` block for the duration and `JobProgress`/`JobFinished` queue up. Consumers see an unresponsive hub exactly when state is changing most. The contract promises hydration but not responsiveness.
- **Concrete decision (minimal):** require the hub's D‑Bus interface to be serviced independently of the reconcile work (separate thread/loop), and document a bounded service deadline for `GetTopicState`/`GetActiveJobs`. If that cannot be met, the contract must state that hydration is best‑effort and that consumers retry — but silence is not acceptable.

---

## Low

### L1 — LOW — Per‑topic schema versioning is absent; only the interface is versioned

Covered structurally by M3/H5. If topics are not suffixed/versioned, a consumer cannot know which schema revision a `DomainEvent` for a topic used. Decision: include a `schema:u` in each `DomainEvent` payload (like `current.json`'s `schema_version:2`, `shared-data-contract.md`), so topic schemas can evolve additively under one interface.

### L2 — LOW — No global unit convention; units are name‑encoded only

- **Evidence:** `fraction` is documented `0.0–1.0` (`event-contract.md:28`). `speedtest.finished` encodes units only via field names (`down_mbps`, `latency_ms`, `:94`). Note: the review prompt's premise that the spine states both percent and fraction was **not found** — the artifacts consistently say `fraction 0.0–1.0` and contain no percent convention. The real risk is different: `a{sv}` permits any numeric variant, so an implementer can still send `75` for a fraction or bytes‑per‑second for `down_mbps` without any contract violation.
- **Concrete decision (minimal):** add a "Units" convention section: all fractions are `0.0–1.0` `d`; rates are bits/s with `_mbps`/`_bps` suffix; durations are `_ms`; timestamps are explicit (`*_at`). Require the hub to range‑check numeric payload fields declared in the JSON.

### L3 — LOW — `producer` on the wire is redundant with the topic→producer map, and unknown‑call semantics are undefined

- **Evidence:** `DomainEvent` carries `producer:s` (`:78`) while `event-contract.json` already pins one `producer` per topic (`:20,24,29`), and AD‑38 says the hub validates it.
- **Problem:** two sources of truth that can disagree; and `GetTopicState` for an unknown topic returns `a{sv}` with no defined error, so a consumer cannot distinguish "unknown topic" from "known topic with empty state" from "no producer".
- **Concrete decision (minimal):** either drop `producer` from the wire (derive from `topic`) or declare it hub‑authored and informational (consumers ignore it). Define `GetTopicState` on an unknown topic to raise `org.dotfiles.Events1.UnknownTopic`, and define an empty dict of a known topic as "no active state".

---

## Minimal decision set (if only one revision is made)

1. **C1/C2:** hub allocates `job_id`; add explicit `JobStarted/JobProgress/JobFinished` methods; hub authors all `Job*` signals; add `epoch` to guard restart.
2. **H1/M4:** subscribe‑before‑hydrate + per‑topic monotonic `seq`; idempotent last‑write‑wins; re‑hydrate on `NameOwnerChanged`.
3. **H2/H3:** every job kind gets a resumable state topic; `capture.state` gains a monotonic start/anchor; `GetActiveJobs` returns full job records.
4. **H4/H5:** make the JSON a checkable schema (signature/required/enum/range); hub validates and errors on rejection; consumers ignore unknown topics/keys; drift test is subset‑not‑equality; additive ≠ breaking.
5. **H6:** authorize by process executable path via `GetConnectionUnixProcessID`, pinned in the JSON.

## Consistency check against the spine

The contract does **not** contradict any AD; it is *underspecified relative to* AD‑37/38 (lifecycle emission and authorization), AD‑34 (version/migration intent), and the continuous‑display convention. Closing C1–C2 and H1–H6 requires editing the companion contract only for H1–H5/L1–L3; C1‑C2/H6 alter the hub interface and therefore the `event-contract.json` interface member set, which AD‑34 permits (JSON is the source of truth) but which the spine's "four signals" wording in `.memlog.md:51` assumes fixed — reconcile the wording when amending.
