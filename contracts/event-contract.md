# Event Contract — Runtime ↔ Shell

Companion to `ARCHITECTURE-SPINE.md` (Phase 5). This is the **only** thing the
Python runtime world and the GJS/AGS shell world share. Neither imports the
other's code; both obey this document. A rename or shape change here is a spine
change, not an implementation detail (mirrors `shared-data-contract.md`).

## Transport and ownership

- **Bus:** the per-user **session bus** (`DBUS_SESSION_BUS_ADDRESS`).
- **Well-known name:** `org.dotfiles.Events` — owned by **exactly one** process,
  the runtime daemon (`dotfiles-runtime daemon run`), which is the signal hub
  (spine AD-38).
- **Object path:** `/org/dotfiles/Events`
- **Interface:** `org.dotfiles.Events1`

Jobs and tools emit **through the hub**; they never request an `org.dotfiles.*`
name. If the daemon is absent, they publish nothing (consumers show no state).

Version is carried in the interface name. A breaking change becomes
`org.dotfiles.Events2`; consumers migrate on their own schedule.

## Signals

| Signal | Members | Meaning |
| --- | --- | --- |
| `JobStarted` | `job_id: s`, `kind: s` | a job began (`kind` e.g. `capture`, `speedtest`) |
| `JobProgress` | `job_id: s`, `fraction: d` | progress, 0.0–1.0 |
| `JobFinished` | `job_id: s`, `exit_code: i` | a job ended (0 = success) |
| `DomainEvent` | `topic: s`, `producer: s`, `payload: a{sv}` | a tool-specific event; `topic` is dotted |

No state properties are exposed for polling. A consumer needing current state
**hydrates once** via the hub's `GetTopicState(topic)` (domain state) or
`GetActiveJobs` (job list), then tracks signals — it never polls, and never
reads a tool's write-behind state file for truth.

Lifecycle (`Job*`) and domain (`DomainEvent`) events are distinct: a supervisor
can infer lifecycle from owning the child; only the tool can emit domain events.
UI indicators for a tool are driven by that tool's **domain events**, not by
`JobStarted`/`JobFinished` (spine AD-37).

The hub authorizes publishers: it pins a caller→topic mapping and rejects a
non-conforming `Emit`; `producer` is hub-validated, never self-asserted (spine
AD-38).

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
      <arg name="payload" type="a{sv}"/>
    </signal>
  </interface>
</node>
```

## Known topics and payload schemas

`event-contract.json` carries these schemas and is the test-time source of
truth. A shape change is a breaking change (`…Events2`).

| Topic | Producer | Payload schema |
| --- | --- | --- |
| `icme.saved` | ICME (on save) | `{ "path": s }` |
| `capture.state` | capture controller | `{ "state": s }` — allowed values per `event-contract.json` |
| `speedtest.finished` | speed-test job | `{ "down_mbps": d, "up_mbps": d, "latency_ms": d }` |

## Drift enforcement (rung 2 — no codegen)

`event-contract.json` is the test-time source of truth for **names and payload
schemas**. Each language bakes its constants and ships one small test asserting
they equal the JSON (and the schema shape). No generator, no build step. A
rename or shape change on either side without updating the JSON fails that
side's test.

## Rules

- Producers never assume a consumer is present; consumers never assume a
  producer is running. Absence is a no-op, never an error.
- State is pushed, never polled. Timers may render continuous values only, from
  a monotonic clock plus one recorded start.
- Payloads are JSON-compatible scalars/containers (`s`, `d`, `i`, `b`, `a{sv}`);
  no opaque binary.
