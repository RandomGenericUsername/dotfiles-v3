# Event Contract — Runtime ↔ Shell

Companion to `ARCHITECTURE-SPINE.md` (Phase 5). This is the **only** thing the
Python runtime world and the GJS/AGS shell world share — neither imports the
other's code; both obey this document. A rename or shape change here is a spine
change, not an implementation detail.

Per AD‑44 the wire **interface** is defined by **`event-contract.xml`**
(the source GJS parses natively and Python checks against); **`event-contract.json`**
keeps topics, payload schemas, and delivery semantics pinned to it. Both are
machine-checked by executable conformance; this prose is descriptive.

## Transport and ownership

- **Bus:** the per-user **session bus** (`DBUS_SESSION_BUS_ADDRESS`).
- **Well-known name (versionless):** `org.dotfiles.Events` — owned by **exactly
  one** process, the runtime daemon (`dotfiles-runtime daemon run`), the **hub**
  (AD‑38). Jobs/tools emit **through** the hub and never request an
  `org.dotfiles.*` name; if the daemon is absent they publish nothing.
- **Object path:** `/org/dotfiles/Events`
- **Interface (versioned):** `org.dotfiles.Events1`

A breaking change becomes `org.dotfiles.Events2`. **Additive** changes — a new
method, signal, topic, or optional field — stay on `…Events1`; a **removed,
retyped, or newly-required** field is breaking. `Events1` and `Events2` may
coexist on the bus under distinct interface names while consumers migrate.

## Methods (hub)

| Method | Signature | Purpose |
| --- | --- | --- |
| `Emit` | `in: topic:s, payload:a{sv}` | publish a domain event |
| `BeginJob` | `in: kind:s, ttl:u` → `out: job_id:s` | register a job with a **lease**; hub allocates `job_id` |
| `RenewJob` | `in: job_id:s` | extend the lease |
| `AdoptJob` | `in: job_id:s, pid:u` | record the observed child PID (wrapper hand‑off) |
| `ReportProgress` | `in: job_id:s, fraction:d` | 0.0–1.0 |
| `EndJob` | `in: job_id:s, exit_code:i` | finish a job |
| `Control` | `in: job_id:s, action:s` | invoke a registered job action (pause/resume/stop) |
| `GetActiveJobs` | `out: jobs:a{ss}` | hydration: `job_id` → `kind` |
| `GetTopicState` | `in: topic:s` → `out: state:a{sv}` | hydration: last value + `_epoch`/`_seq` |

## Signals (hub is the sole emitter; every signal carries `epoch`)

| Signal | Members | Meaning |
| --- | --- | --- |
| `JobStarted` | `job_id:s, kind:s, epoch:u` | a job began |
| `JobProgress` | `job_id:s, fraction:d, epoch:u` | progress, 0.0–1.0 |
| `JobFinished` | `job_id:s, exit_code:i, epoch:u` | a job ended (0 = success; a lease expiry emits `exit_code = -1`) |
| `DomainEvent` | `topic:s, producer:s, seq:u, epoch:u, payload:a{sv}` | a tool-specific event |
| `JobsCleared` | `epoch:u` | the hub (re)started; all prior `job_id`s and topic state are invalid |

## Delivery, ordering, hydration

- Signals are **at-most-once**.
- `seq` is per-topic monotonic **within an `epoch`**; the `epoch` bumps on every
  hub start and resets `seq`. The hub emits **`JobsCleared(epoch)` on first start
  and every restart**; a consumer also treats D‑Bus `NameOwnerChanged` on
  `org.dotfiles.Events` as a restart signal (belt and braces, since
  `JobsCleared` is itself at‑most‑once).
- A consumer MUST **subscribe first, then hydrate** via `GetTopicState` /
  `GetActiveJobs`, and then **discard any signal whose `(epoch, seq)` is not
  greater than the hydrated pair**. `GetTopicState` returns reserved `_epoch: u`
  and `_seq: u` members; consumers compare `(epoch, seq)`, never `seq` alone.
- Consumers tolerate `JobsCleared` by re‑hydrating. A UI indicator is driven by
  that tool's **domain events**, never by `JobStarted`/`JobFinished` (AD‑37).

## Jobs and control

A job obtains a `job_id` via `BeginJob`, **renews its lease** while alive
(`RenewJob`), and ends with `EndJob`. A job that dies without ending is **expired
by the hub** (synthetic `JobFinished` with `exit_code = -1`). A wrapper that
spawns the observed process and exits **adopts** it (`AdoptJob`) so the hub
records the child. A job that exposes control registers its allowed actions
(`pause`/`resume`/`stop` for capture); the hub is the **single control path**
(`Control`), so a UI never shells the tool directly.

## Known topics and payload schemas

| Topic | Producer | Payload |
| --- | --- | --- |
| `icme.saved` | ICME (on save) | `{ "path": s }` |
| `capture.state` | capture controller | `{ "state": s (idle\|recording\|paused), "elapsed_seconds": x }` |
| `speedtest.finished` | speed-test job | `{ "down_mbps": d, "up_mbps": d, "latency_ms": d }` |

The capture controller updates `capture.state` on every transition **and at
least once per second while recording**, so the bar renders the pushed value
(and may interpolate locally) — it derives **no** time from a file or a shared
wall clock, avoiding clock‑skew and suspend artifacts.

## Errors (typed)

`Emit`/job methods fail with typed D‑Bus errors: `UnknownTopic`,
`PayloadTooLarge`, `RateLimited`, `UnknownJob`, `JobEnded`, `NotControllable`.
A hub method call has a client‑side timeout; a caller treats a timeout as a
transient failure and re‑hydrates (never assumes success).

## Limits and validation

The hub validates every `Emit` **structurally** — schema, a maximum payload size
and nesting depth, and a publish rate — and rejects non‑conforming events. It
does **not** authenticate the sender: the session bus is a trusted same‑user
domain (AD‑38). Payloads are bounded, JSON‑compatible D‑Bus scalars and
containers, with no opaque binary. The hub never advertises a topic absent from
`event-contract.json`.

## Rules

- Producers never assume a consumer is present; consumers never assume a
  producer is running. Absence is a no-op, never an error.
- State is pushed, never polled.
