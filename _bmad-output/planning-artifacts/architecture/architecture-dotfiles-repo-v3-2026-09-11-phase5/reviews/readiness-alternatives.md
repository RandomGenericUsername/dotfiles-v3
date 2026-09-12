# Readiness Alternatives Review — session-bus hub (`org.dotfiles.Events`)

**Role:** adversarial/alternatives reviewer (independent of the primary gate).
**Subject:** the Phase 5 runtime daemon's systemd readiness model.
**Artifacts bound:** `ARCHITECTURE-SPINE.md` AD-33 (daemon lifecycle/supervision) and
AD-38 (one bus-name owner), `.memlog.md` (esp. lines 21–26, 45, 51), and
`contracts/event-contract.md` (lines 10–15).
**Decision under review:** the spine currently pins `Type=simple` + `Restart=on-failure`
(AD-33, line 40). The question is whether a session-bus service that must own
`org.dotfiles.Events` should instead be `Type=dbus` + `BusName=org.dotfiles.Events`.

**Method:** local `man systemd.service`, `man systemd.unit`, `man systemd.special`,
`man systemd-system.conf`; web verification of `systemd.service(5)` (freedesktop,
man7, Arch), systemd issues #892 and #36859; repo inspection (no `*.service` unit
exists yet — confirmed; `contracts/event-contract.{md,json}`; prior gate review
`reviews/review-reality.md` C1, `reviews/validation-report.md`).
**Assumption:** target is Arch + uwsm + a socket-activated session bus
(`$XDG_RUNTIME_DIR/bus` via `dbus.socket` / `dbus-broker.service` or `dbus.service`),
which is the only configuration the spine's Stack table ("system-provided
uwsm-managed session") supports.

---

## 0. What "ready" has to mean here

AD-38's invariant is *exactly one* process owns the well-known name
`org.dotfiles.Events` and is the signal hub. Therefore unit readiness is only
meaningful if it answers one question: **is the hub's name owned?** Any model whose
"active" state is a proxy for "the process was spawned" leaks the difference into
every consumer and every ordering edge. The comparison is judged against that.

---

## 1. Mechanism, stated from the docs

### Model A — `Type=dbus` + `BusName=org.dotfiles.Events`

`systemd.service(5)`, **Type=** (dbus):

> "Behavior of `dbus` is similar to `simple`; however, units of this type must have
> the `BusName=` specified and the service manager will consider the unit up when
> the specified bus name has been acquired. This type is the default if `BusName=`
> is specified. … A service unit of this type is considered to be in the activating
> state until the specified bus name is acquired. It is considered activated while
> the bus name is taken. **Once the bus name is released the service is considered
> being no longer functional which has the effect that the service manager attempts
> to terminate any remaining processes belonging to the service.** Services that
> drop their bus name as part of their shutdown logic thus should be prepared to
> receive a `SIGTERM` …"

Implicit dependencies (`systemd.service(5)`, **Automatic Dependencies**):

> "Services with `Type=dbus` set automatically acquire dependencies of type
> `Requires=` and `After=` on `dbus.socket`."

Consequences:

- **Readiness is name ownership**; `Active: activating (start)` until acquired,
  `active (running)` when owned. Dependent units ordered `After=` this unit are
  genuinely gated on the hub existing.
- **Name loss is supervised by systemd**, not by the daemon: the manager watches
  the bus, force-terminates the unit's processes, and applies the `Restart=` policy.
  Detection does not depend on the daemon's own event loop.
- **Session-bus caveat.** In a user instance, `Type=dbus` watches the bus the user
  manager is connected to — the *user bus*, which in a standard/most-desktop setup
  is the *session bus* at `$XDG_RUNTIME_DIR/bus` (systemd/systemd#892; resolved for
  dbus-user-session / dbus-broker setups). `dbus.socket` is that socket. If an
  environment ever ran a session bus that is *not* the systemd-managed one, A would
  hang in `activating` until `TimeoutStartSec` (default 90s, `TimeoutStartSec=`).
- **Stop ordering caveat.** `Type=dbus` adds `After=dbus.socket`, **not**
  `After=dbus.service`/`dbus-broker.service` (systemd/systemd#36859). Startup only
  needs the socket; clean stop-before-bus requires adding the service ordering
  explicitly.
- Not fork (types other than `forking` expect the `ExecStart` process to be main).
- If a D-Bus *activation* file were shipped, do **not** ship `[Install]`
  (`systemd.service(5)`, Example 7). We do not want bus-activation here (see §7.9).

### Model B — `Type=simple` + `RequestName(DO_NOT_QUEUE)` + exit non-zero on failure/loss + `Restart=always`

`systemd.service(5)`, **Type=** (simple):

> "the service manager will consider the unit started immediately after the main
> service process has been forked off … before the new process has called `execve()`
> … `systemctl start` command lines for simple services will report success even if
> the service's binary cannot be invoked successfully."

Consequences:

- **No readiness signal.** "active" ≠ name owned. The name may be acquired hundreds
  of ms later, or never, while the unit reports `active (running)`.
- **No implicit session-bus dependency.** `Requires=`/`After=dbus.socket` must be
  added by hand if you want the same start ordering.
- **Name loss is the daemon's job** — it must receive `NameLost`/`NameOwnerChanged`
  and exit non-zero. If the chosen Python D-Bus client does not service the
  connection (a real risk given the spine defers the client library and demands a
  sync-friendly one, `.memlog.md:42`), the daemon can keep running without the name:
  a *silent shadow-less dead hub* that `systemctl status` reports as healthy.
- `DO_NOT_QUEUE` correctly makes contention fail (`-EEXIST` / `Exists`, see
  `sd_bus_request_name(3)`), which is the behavior AD-38 wants.

### Restart / limit knobs (both models)

- `Restart=on-failure` restarts on non-zero exit, unclean signal, timeout, watchdog —
  **not on a clean exit(0)** (`systemd.service(5)`, `Restart=`). `always` restarts
  regardless, but still not after a systemd-initiated stop.
- `RestartSec=` default **100 ms**.
- `StartLimitIntervalSec=` default **10 s**, `StartLimitBurst=` default **5**
  (`systemd-system.conf(5)` / `systemd.unit(5)`). Reaching the limit **stops all
  further restarts** and parks the unit in `failed` ("A restarted service enters the
  failed state only after the start limits are reached"). Nothing re-arms it except a
  manual start/timer or `systemctl reset-failed`.
- `TimeoutStartSec=` default **90 s**.
- `graphical-session.target` semantics (`systemd.special(7)`): "Such services should
  have `PartOf=graphical-session.target`"; `WantedBy=`/`Wants=` determine start.

---

## 2. Concrete failure scenarios

Legend: A = `Type=dbus`; B = `Type=simple` + `DO_NOT_QUEUE` + `Restart=always`
(+ `RestartSec=`, `StartLimit*` pinned as B requires).

| # | Scenario | A outcome | B outcome | Winner |
| --- | --- | --- | --- | --- |
| S1 | **Login race** — unit starts before the session bus exists | Implicit `Requires=`/`After=dbus.socket` orders the bus socket first; normally no race. If still unconnectable, `activating` → `TimeoutStartSec` → failure → restart | No implicit dep; daemon connect fails, exits non-zero; restart every 100 ms; 5/10 s → **`failed`, not retried** even after the bus arrives | **A** (B can permanently strand on a transient race) |
| S2 | **Foreign owner / double instance** — a stray `dotfiles-runtime daemon run` or second unit already owns the name | Daemon `RequestName(DO_NOT_QUEUE)` → `Exists` → exits non-zero; systemd sees main process die before name acquired → start failure → restart. Unit never reads `active` | Same daemon behavior, but `Type=simple` reported `active (running)` from fork while the hub was absent; only once StartLimit parks it does status become truthful | **A** (readiness never lies) |
| S3 | **Name lost after acquisition, daemon still alive** — bus connection dropped, object unexported, client loop wedged | systemd observes the release and force-terminates → failure → restart. Independent of daemon code | Depends entirely on the daemon catching `NameLost` and exiting non-zero. A bug or a sync client that never pumps the connection leaves a process that is `active` but owns nothing | **A** (robust to daemon defects) |
| S4 | **Session bus restarts** (dbus-broker/dbus-daemon bounce) | Name lost → systemd restarts; `After=dbus.socket` ensures reconnect after the bus is back; long outages still need StartLimit tuning | Restart loop with no ordering guarantee; more likely to trip StartLimit and park | **A** |
| S5 | **Persistent startup error** — e.g. reconcile raises `"nothing to reconcile"`, `ENOSPC`, bad env | Fails before ready (`activating` → `failed`); hub was never advertised. Still needs `StartLimit*` pinned + visible failure | Fails repeatedly but shows `active` between attempts; false readiness. Same StartLimit need | **A** on observability; both need pinned limits |
| S6 | **Daemon wedged while still holding the name** (deadlock) | Not detected — `Type=dbus` checks ownership, not liveness | Not detected either | **Tie** (both need `WatchdogSec=`/`sd_notify` to ever catch this) |
| S7 | **Logout / session end** | `PartOf=graphical-session.target` stops it cleanly; `Type=dbus` sends SIGTERM on release; add `After=dbus.service` if stop-before-bus is required (#36859) | No name tracking; bus teardown can crash the process uncleanly; `Restart=always` will fight the shutdown unless bound to the session | **A** |
| S8 | **Start-limit parking = "silently dead watcher"** | Subject to the same limit; but a genuine repeated failure is surfaced as `failed` and was never `active` | Same limit; failure is masked by `active` windows until the limit trips | **A** |
| S9 | **Wrong bus** — unit env lacks `DBUS_SESSION_BUS_ADDRESS` / daemon targets a different bus than systemd watches | systemd waits for a name it will never see → `TimeoutStartSec` → `failed` (**loud**). This is A's one real caveat, but it fails visibly | systemd says `active` regardless; if the bus is wrong the hub is simply unreachable and **nothing is visible** | **A** (fails loud, not silent) |
| S10 | **Slow acquisition** | `TimeoutStartSec` (90 s) is generous; lower it (e.g. 15 s) so misconfig is fast | Immediate "ready" — functionally says nothing | **A** |
| S11 | **`systemctl --user restart`** | stop (name released → SIGTERM) → start → reacquire | start is "ready" instantly; reacquire happens later, unobserved | **A** |

The pattern is not subtle: A is correct on S1–S5, S7–S11, ties S6, and its only
liability (S9, wrong bus) fails *visibly* — which is the property AD-33 exists to
protect ("a silently dead watcher").

---

## 3. Evaluation axes

| Axis | A `Type=dbus` | B `Type=simple` + flags |
| --- | --- | --- |
| Readiness correctness | Ready **iff** name owned | Ready at fork; name ownership invisible |
| Name loss | systemd watches & terminates | Daemon code must watch & exit |
| Contention (`DO_NOT_QUEUE`) | Fails start; never reports ready | Fails but reports active until StartLimit |
| Restart-storm / StartLimit | Same knob; fast-fail path trips limit; timeout path is a slow infinite loop unless tuned | Same knob; 100 ms default makes bursts likely, StartLimit catches; risk of stranding (S1) |
| Start order vs session bus | Implicit `Requires=`/`After=dbus.socket` | Must be added manually |
| Observability (`systemctl status`) | `activating` → `active` tracks the invariant; dependents can order `After=` and be guaranteed the hub | Misleading; dependents cannot rely on it |
| Failure modes | One environment assumption (same bus), fails loud | Multiple bespoke failure paths (connect, request, NameLost, exit-code contract), several fail silent |
| Design cleanliness | Delegates supervision to systemd; daemon stays a foreground loop; declarative | Reimplements systemd's supervision in Python; more code, more surface; but runs outside systemd |

---

## 4. Recommendation: **A, with caveats**

Adopt `Type=dbus` + `BusName=org.dotfiles.Events` as the primary model. Mechanism,
not taste: the unit's readiness predicate then *is* AD-38's invariant, name-loss
supervision moves from hand-written Python to systemd, and the session-bus start
ordering is provided implicitly. Every alternative failure mode of B that matters to
AD-33/AD-38 is a *silent* one (S2, S3, S5, S9), and this system's stated threat is
precisely the silently dead watcher.

Caveats (all must be resolved, because A is not free):

1. **Same-bus assumption must be proven on target.** systemd --user and the daemon
   must use the same bus. On Arch/uwsm with a socket-activated `$XDG_RUNTIME_DIR/bus`
   they do; provisioning/doctor must *assert* it (see §6 spike). If a deployment ever
   lacks that identity, fall back to a documented B profile.
2. **`DO_NOT_QUEUE` is still required under A.** Sole ownership is enforced by the
   daemon's `RequestName` flags, not by systemd's name watch. Under A, request
   failure must exit non-zero *immediately* so the unit fails fast rather than
   waiting out `TimeoutStartSec`.
3. **Exit-on-name-loss is not required under A** (systemd owns it) and must not be
   the stated mechanism; the daemon must instead handle `SIGTERM` and release the
   name on `systemctl stop` (the AD-41 kill switch) without a restart.
4. **Fallback B profile** (only if the spike disproves A): `Type=simple`,
   `Restart=always` (not `on-failure`), explicit `Requires=`/`After=dbus.socket`,
   `RestartSec=` (e.g. 2 s), `StartLimitIntervalSec=`/`StartLimitBurst=` pinned,
   `RequestName(DO_NOT_QUEUE)` exiting non-zero on acquisition failure or loss, and
   `PartOf=graphical-session.target`. Record it as a named fallback, not the default.

---

## 5. What the spine must state regardless of A/B

These are correctness obligations, not implementation details; several are currently
missing or contradicted.

1. **Exact bus name.** `BusName=org.dotfiles.Events` — the **versionless** well-known
   name. The interface is `org.dotfiles.Events1` (`event-contract.md:11–20`); the two
   must not be conflated. This is a correctness trap: pointing `BusName=` at
   `org.dotfiles.Events1` would make A wait forever for a name the daemon never owns.
   The spine currently contradicts itself — the consistency convention says "well-known
   names … version is a trailing integer" (`ARCHITECTURE-SPINE.md:105`), and the
   structural-seed diagram writes the bus as `org.dotfiles.Events1` (line 151), while
   AD-38 and the contract correctly say `org.dotfiles.Events`. **Pin the convention:
   bus name versionless, interface versioned.**
2. **`Type=`** pinned explicitly (currently `simple`; recommend `dbus`).
3. **`Restart=`** pinned. With `on-failure`, the daemon must exit non-zero on every
   unrecoverable condition and never clean-exit on a fault; otherwise use `always`.
   Either way, *explicitly forbid a clean exit while unhealthy*.
4. **`RestartSec=`** pinned explicitly (default 100 ms is a storm generator). State
   the intended backoff and reconcile it with the conventions' "logged and retried
   with backoff" (`ARCHITECTURE-SPINE.md:112`).
5. **`StartLimitIntervalSec=`/`StartLimitBurst=`** pinned explicitly, with the intent
   stated: bounded restarts ("no participant crash-loops", line 111) **and** a
   visible `failed` state. A limit that parks the unit silently is worse than a slow
   loop; pair the limit with `OnFailure=` or the AD-41 inspect surface.
6. **Session target & ordering.** `WantedBy=graphical-session.target` +
   `After=graphical-session.target` for start; decide `PartOf=graphical-session.target`
   for stop-on-logout; and add `After=dbus.service` (or the broker equivalent) if
   clean stop-before-bus ordering is required (systemd #36859). Do **not** bind the
   unit to the compositor unit — a Hyprland reload must not kill the reactive loop
   (AD-33's stated purpose).
7. **Session-bus dependency.** Explicit if B; implicit under A but should be stated so
   it is not accidentally removed.
8. **Environment import.** The daemon needs `DBUS_SESSION_BUS_ADDRESS`,
   `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE` (its use cases
   call `hyprctl`/AGS). A default user unit inherits none of these (already raised in
   `review-rubric.md` F-something and `.memlog.md:25`). Pin the import mechanism and
   a provisioning/doctor assertion that the daemon and systemd target the same bus.
9. **Activation policy.** Do not ship a D-Bus activation `.service` file in
   `dbus-1/services/`: it would let an arbitrary caller start the hub and create a
   second activation path, conflicting with the single-owner/kill-switch posture. If
   activation is ever wanted, ship it without `[Install]`.
10. **No fork** (both types expect the `ExecStart` process to be main); and
    **graceful `SIGTERM`** releasing the name.
11. **Observability.** State that `systemctl --user status` is the status surface
    (AD-41) and that under A its `activating`/`active` distinction is authoritative.
    Add `OnFailure=`/inspect so a start-limit `failed` unit is discoverable.

---

## 6. Verification spike (de-risk A before it binds)

Run on the actual target before finalizing AD-33:

1. `systemctl --user show-environment | grep -E 'DBUS|XDG_RUNTIME'`;
   `readlink -f /run/user/$UID/bus`; confirm `$DBUS_SESSION_BUS_ADDRESS` resolves to
   the systemd-managed session bus.
2. Minimal `Type=dbus` `BusName=org.dotfiles.Spike` unit with a script that acquires
   the name after a delay; confirm `systemctl --user status` shows
   `activating (start)` → `active (running)` and that a dependent `After=` unit is
   held.
3. Squat the name (`busctl --user`) then start the unit with `DO_NOT_QUEUE`; confirm
   it fails rather than reporting ready.
4. Force name loss (kill the owner / bounce the bus); confirm systemd terminates and
   restarts per policy, and record how many restarts occur vs the start limit.
5. Repeat 2–4 with `TimeoutStartSec=` lowered; confirm misconfiguration surfaces fast.

Only after this passes should A be written as the AD-33 rule; otherwise adopt the
named B fallback.

---

## 7. Residual risks / open questions

- **S6 (wedged-but-name-owning)** is unhandled by A and B. Neither `Type=dbus` nor
  `Type=simple` tests liveness. `WatchdogSec=` + `sd_notify` is the only mechanism;
  defer explicitly or schedule it.
- **`Type=dbus` foreign-owner semantics** are the least-documented corner. The
  recommendation does not rely on systemd detecting a foreign owner; it relies on the
  daemon's `DO_NOT_QUEUE`. The spike (step 3) closes this.
- **StartLimit intent** is a values decision: unbounded retry (`StartLimitIntervalSec=0`)
  keeps a memory-bounded daemon self-healing but can mask a hard fault; bounded
  retry is safer if `failed` is visible. The spine must pick one and say why.
- **Bus restart storm** applies to both models; tune and test (spike step 4).

---

## Appendix — source excerpts

- `systemd.service(5)` **Type=dbus** (activating/activated/released + terminate;
  implicit `Requires=`/`After=dbus.socket`); **Type=simple** ("started immediately
  after … fork() … before execve()"); **Restart=** (on-failure vs always; clean exit
  not restarted; systemd-initiated stop not restarted); **RestartSec=** (100 ms
  default); **TimeoutStartSec=** (90 s default); **BusName=** (mandatory for dbus).
- `systemd.unit(5)` **StartLimitIntervalSec=/StartLimitBurst=** (defaults 10 s / 5;
  reaching the limit stops further restarts and enters `failed`).
- `systemd.special(7)` **graphical-session.target** ("services … should have
  `PartOf=graphical-session.target`").
- systemd/systemd#892 — "Type=dbus services with BusName= set should watch the user
  bus for the systemd user instance …"; works on dbus-user-session / `$XDG_RUNTIME_DIR/bus`.
- systemd/systemd#36859 — `Type=dbus` gives `After=dbus.socket` but not
  `After=dbus.service`; add it if the service must stop before the bus.
- `contracts/event-contract.md:10–20` — bus `org.dotfiles.Events`, interface
  `org.dotfiles.Events1`, session bus only.
- Prior gate: `reviews/review-reality.md` C1; `reviews/validation-report.md:63–69`.
