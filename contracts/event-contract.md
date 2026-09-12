# Event Contract — Runtime ↔ Shell

Companion to `ARCHITECTURE-SPINE.md` (Phase 5). This is the **only** thing the
Python runtime world and the GJS/AGS shell world share — neither imports the
other's code; both obey this document. A rename or shape change here is a spine
change, not an implementation detail.

Per AD‑44 this contract has **one machine-checkable definition**
(`event-contract.json`); this prose is descriptive. A drift test on each side
fails when the two disagree.

## Transport and ownership

- **Bus:** the per-user **session bus** (`DBUS_SESSION_BUS_ADDRESS`).
- **Well-known name (versionless):** `org.dotfiles.Events` — owned by **exactly
  one** process, the runtime daemon (`dotfiles-runtime daemon run`), which is the
  **hub** (AD‑38). Jobs/tools emit **through** the hub and never request an
  `org.dotfiles.*` name; if the daemon is absent they publish nothing.
- **Object path:** `/org/dotfiles/Events`
- **Interface (versioned):** `org.dotfiles.Events1`

A breaking change to the interface becomes `org.dotfiles.Events2`. **Additive**
changes — a new method, signal, topic, or optional field — stay on
`org.dotfiles.Events1`; a **removed, retyped, or newly-required** field is
breaking. `Events1` and `Events2` may coexist on the bus under distinct interface
names while consumers migrate.

## Methods (hub)

| Method | Signature | Purpose |
| --- | --- | --- |
| `Emit` | `in: topic:s, payload:a{sv}` | publish a domain event |
| `BeginJob` | `in: kind:s` → `out: job_id:s` | register a job; hub allocates `job_id` |
| `ReportProgress` | `in: job_id:s, fraction:d` | 0.0–1.0 |
| `EndJob` | `in: job_id:s, exit_code:i` | finish a job |
| `GetActiveJobs` | `out: jobs:a{ss}` | hydration: current job_id → kind |
| `GetTopicState` | `in: topic:s` → `out: state:a{sv}` | hydration: last value for a topic (includes `_seq`) |

## Signals (hub is the sole emitter)

| Signal | Members | Meaning |
| --- | --- | --- |
| `JobStarted` | `job_id:s, kind:s` | a job began |
| `JobProgress` | `job_id:s, fraction:d` | progress, 0.0–1.0 |
| `JobFinished` | `job_id:s, exit_code:i` | a job ended (0 = success) |
| `DomainEvent` | `topic:s, producer:s, seq:u, payload:a{sv}` | a tool-specific event |
| `JobsCleared` | `epoch:u` | the hub restarted; all prior `job_id`s and topic state are invalid |

## Delivery, ordering, hydration

- Signals are **at-most-once** (a consumer that is not listening misses them).
- A consumer MUST **subscribe first, then hydrate** via `GetTopicState` /
  `GetActiveJobs`, and then **discard any signal whose `(epoch, seq)` is not
  greater than the hydrated pair.** This closes the hydrate/subscribe race
  without polling.
- `seq` is a per-topic monotonic counter (u) incremented by the hub **within an
  `epoch`**. The hub carries an `epoch` (u) that **bumps on restart and resets
  `seq`**; at that point it emits `JobsCleared(epoch)`, which invalidates all
  prior `job_id`s and topic state.
- `GetTopicState` returns the current value plus reserved `_epoch: u` and
  `_seq: u` members; consumers compare `(epoch, seq)` pairs, never `seq` alone.
- Consumers tolerate `JobsCleared` by re-hydrating; a tool UI is driven by that
  tool's **domain events**, never by `JobStarted`/`JobFinished` (AD‑37).

## Known topics and payload schemas

| Topic | Producer | Payload |
| --- | --- | --- |
| `icme.saved` | ICME (on save) | `{ "path": s }` |
| `capture.state` | capture controller | `{ "state": s (idle\|recording\|paused), "started_at": x (unix secs, 0 when idle) }` |
| `speedtest.finished` | speed-test job | `{ "down_mbps": d, "up_mbps": d, "latency_ms": d }` |

Continuous display (the recording timer) derives from `started_at` plus a local
tick — it MUST NOT re-read any state file. A tool's state file is a write-behind
projection, never the authority.

## Limits and validation

The hub validates every `Emit` **structurally** — schema, a maximum payload size
and nesting depth, and a publish rate — and rejects non-conforming events. It
does **not** authenticate the sender: the session bus is a trusted same-user
domain (AD‑38). Payloads are JSON-compatible scalars/containers (`s`, `d`, `i`,
`x`, `b`, `a{sv}`), bounded, with no opaque binary.

## Canonical introspection XML

```xml
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.dotfiles.Events1">
    <method name="Emit">
      <arg name="topic" type="s" direction="in"/>
      <arg name="payload" type="a{sv}" direction="in"/>
    </method>
    <method name="BeginJob">
      <arg name="kind" type="s" direction="in"/>
      <arg name="job_id" type="s" direction="out"/>
    </method>
    <method name="ReportProgress">
      <arg name="job_id" type="s" direction="in"/>
      <arg name="fraction" type="d" direction="in"/>
    </method>
    <method name="EndJob">
      <arg name="job_id" type="s" direction="in"/>
      <arg name="exit_code" type="i" direction="in"/>
    </method>
    <method name="GetActiveJobs">
      <arg name="jobs" type="a{ss}" direction="out"/>
    </method>
    <method name="GetTopicState">
      <arg name="topic" type="s" direction="in"/>
      <arg name="state" type="a{sv}" direction="out"/>
    </method>
    <signal name="JobStarted">
      <arg name="job_id" type="s"/>
      <arg name="kind" type="s"/>
    </signal>
    <signal name="JobProgress">
      <arg name="job_id" type="s"/>
      <arg name="fraction" type="d"/>
    </signal>
    <signal name="JobFinished">
      <arg name="job_id" type="s"/>
      <arg name="exit_code" type="i"/>
    </signal>
    <signal name="DomainEvent">
      <arg name="topic" type="s"/>
      <arg name="producer" type="s"/>
      <arg name="seq" type="u"/>
      <arg name="payload" type="a{sv}"/>
    </signal>
    <signal name="JobsCleared">
      <arg name="epoch" type="u"/>
    </signal>
  </interface>
</node>
```

## Rules

- Producers never assume a consumer is present; consumers never assume a
  producer is running. Absence is a no-op, never an error.
- State is pushed, never polled.
