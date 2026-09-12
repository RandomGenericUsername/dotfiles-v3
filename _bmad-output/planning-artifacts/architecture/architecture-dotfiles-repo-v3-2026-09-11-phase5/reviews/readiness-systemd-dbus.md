# Readiness review — `Type=dbus` + `BusName=` for a session-bus `systemd --user` service

- **Date:** 2026-09-11
- **Target:** Ubuntu/Arch-like Linux, systemd `--user` managers under a Wayland/uwsm session
- **Scope:** Phase 5 AD-33 (daemon lifecycle/supervision) and AD-38 (single `org.dotfiles.Events` owner), specifically the proposed fix `Type=dbus` + `BusName=org.dotfiles.Events` recorded in `reviews/review-reality.md` C1
- **Method:** authoritative-source verification only — local `man systemd.service(5)`, `man systemd.unit(5)`, `man systemd.special(5)`, `man sd_bus_default(3)`, `systemctl --user show`, plus systemd v261 source (`src/core/{service,unit,dbus}.c`) and the D-Bus specification; then live empirical tests on this machine. Nothing asserted from memory.
- **Runtime verified on:** `systemd 261 (261.2-1-Arch)`; uwsm `0.26.7`; dbus-broker user bus.

---

## Verdict

**Viable and clean — with one non-negotiable rider on the restart policy.**

`Type=dbus` + `BusName=` is a correct, first-class fit for a session-bus user service. On a `systemd --user` manager it tracks the **session bus** (verified from source and on this machine), it provides genuine readiness semantics (the unit is `activating` until the well-known name is owned), and a never-acquired name is a hard failure that reaches `failed`, not a silent success.

It is **not** a turnkey "no silently dead watcher" fix on its own. `Type=dbus` converts *name-never-acquired* into a failure/timeout, but *name lost while running* is classified as a **clean success** (`Result=success`) and is therefore **not restarted by `Restart=on-failure`**. To satisfy AD-33's stated purpose with `Type=dbus` you must do one of:

1. use `Restart=always` (or `on-success`), and tune `StartLimitIntervalSec`/`StartLimitBurst` so a genuine crash-loop fails loudly instead of silently parking in `failed`; **or**
2. keep `Restart=on-failure` and have the daemon exit **non-zero** when it loses the name (verified: a non-zero exit on the manager's SIGTERM is recorded as `Result=exit-code` and *does* trigger `on-failure`).

Additionally, `Restart=on-failure` + `Type=dbus` + default start limits does **not** by itself prevent the "silently dead watcher" outcome: a never-acquired name cycles `timeout → restart → … → start-limit-hit → failed` (reproduced live). The restart policy and start limits are part of the correctness argument, not implementation detail.

---

## Q1 — `Type=dbus` + `BusName=` readiness semantics

**When is the unit "started"?** When the specified well-known bus name has been acquired by *some* owner on the manager's bus.

- `systemd.service(5)` (local, line 154–157): *"Behavior of `dbus` is similar to `simple`; however, units of this type must have the `BusName=` specified and the service manager will consider the unit up when the specified bus name has been acquired. This type is the default if `BusName=` is specified."*
- `systemd.service(5)` (line 159–168): *"A service unit of this type is considered to be in the activating state until the specified bus name is acquired. It is considered activated while the bus name is taken. Once the bus name is released the service is considered being no longer functional which has the effect that the service manager attempts to terminate any remaining processes belonging to the service."*
- `ExecStartPost=` runs only after readiness is reached for `Type=dbus` (*"or the `BusName=` has been taken for `Type=dbus`"*, `systemd.service(5)` line 342–344).

Source confirmation (`src/core/service.c`, v261):
- `service_enter_start()` for `SERVICE_DBUS` sets the main PID then `service_set_state(s, SERVICE_START)` — it does **not** enter running (`service.c:2821-2828`).
- `service_bus_name_owner_change()` promotes the unit on a non-null owner: `else if (s->state == SERVICE_START && new_owner) service_enter_start_post(s);` (`service.c:5670-5706`).
- Readiness is purely a `NameOwnerChanged` observation; the owner PID is **not** checked against the unit's cgroup (see Q3).

**If the name is never acquired:** the start timeout applies and the unit goes to `failed`.

- `systemd.service(5)` line 539–547: *"`TimeoutStartSec=` … If a daemon service does not signal start-up completion within the configured time, the service will be considered failed and will be shut down again."* Default on this box (user manager): `DefaultTimeoutStartUSec=1min 30s` (`systemctl --user show`).
- Source: on timer expiry in `SERVICE_START`, `service_dispatch_timer()` calls `service_enter_signal(s, SERVICE_STOP_SIGTERM, SERVICE_FAILURE_TIMEOUT)` (`service.c:4885-4901`). `TimeoutStartFailureMode=` defaults to `terminate` (`systemd.service(5)` line 627–644), i.e. SIGTERM (default `KillSignal=`), then SIGKILL after `TimeoutStopSec=`.
- **Live reproduction:** a `Type=dbus` transient unit with `BusName=org.dotfiles.Rdy2`, `TimeoutStartSec=8`, whose `ExecStart` never owns the name, reached `ActiveState=failed`, `SubState=failed`, `Result=timeout`, `ExecMainCode=2` (killed), `ExecMainStatus=15` (SIGTERM). Journal: `start operation timed out. Terminating.` → `Failed with result 'timeout'.`

**Answer:** started ⇔ name acquired; never-acquired ⇒ start timeout ⇒ `failed` (`Result=timeout`). Yes, there is a start timeout; yes, the unit goes to `failed`.

---

## Q2 — Which bus does `Type=dbus` bind to for a `systemd --user` unit?

**The session/user bus** — not the system bus.

Definitive mechanism (systemd v261 `src/core/dbus.c`, `bus_init_api()` at lines 820–862):

```c
/* The API and system bus is the same if we are running in system mode */
if (MANAGER_IS_SYSTEM(m) && m->system_bus)
        bus = sd_bus_ref(m->system_bus);
else {
        if (MANAGER_IS_SYSTEM(m))
                r = sd_bus_open_system_with_description(&bus, "bus-api-system");
        else
                r = sd_bus_open_user_with_description(&bus, "bus-api-user");
        ...
}
...
m->api_bus = TAKE_PTR(bus);
```

`BusName=` readiness is installed on that `manager->api_bus` (`src/core/unit.c` `unit_watch_bus_name()` lines 3709–3733: `unit_install_bus_match(u, u->manager->api_bus, name)`; the match itself at `unit_install_bus_match()` lines 3641–3707). Therefore a user manager watches the **user bus**, and the system manager watches the system bus.

`man sd_bus_default(3)` (local, line 40–68): `sd_bus_default()` *"acquires a bus connection object to the user bus when invoked from within a user slice (any session under `user-*.slice`, e.g. `user@1000.service`), or to the system bus otherwise"*; `sd_bus_default_user()` connects to the user bus and `sd_bus_open_user()` *"connects only to the user bus."* A user manager runs inside `user@UID.service`, i.e. `user-1000.slice`.

`man sd_bus_default(3)` lines 82–85: for the user bus, *"If the `$DBUS_SESSION_BUS_ADDRESS` environment variable is set … it will be used as the address of the user bus … If this variable is not set, a suitable default for the default user D-Bus instance will be used."* On this machine the two coincide:

- `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`
- `systemctl --user show dbus.socket -p Listen` → `Listen=/run/user/1000/bus (Stream)`; the unit file is `/usr/lib/systemd/user/dbus.socket` with `ListenStream=%t/bus` and `ExecStartPost=-/usr/bin/systemctl --user set-environment DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus`.
- `busctl --user list | grep org.freedesktop.systemd1` → `org.freedesktop.systemd1  4110 systemd inumaki :1.1 user@1000.service` (the user manager is on the session bus). The system manager's copy is on the system bus (`busctl --system`).

The `BusName=` implicit `dbus.socket` dependency also resolves to the **user** `dbus.socket` (`src/core/service.c:1067-1076`, `SPECIAL_DBUS_SOCKET` looked up in the manager's namespace). Local evidence for the same unit shows `Before=… dbus-broker.service sockets.target …`.

**On the "session-bus asymmetry" (systemd#892):** the concern that `Type=dbus` only watches the system bus is **not** current behaviour. `systemd/systemd#892` was closed as misconfiguration: a maintainer stated *"Type=dbus services with BusName= set should watch the user bus for the systemd user instance and the system bus for the systemd system instance"*; the reporter's distro used a non-standard socket path (`%t/dbus/user_bus_socket`); after switching to upstream's `%t/bus` the reporter confirmed `org.freedesktop.systemd1` appeared on the bus and `Type=dbus` worked. The man page's Example 7 wording *"acquired on the system bus"* is written for system services; the mechanism is the manager's API bus, and for `--user` that is the session bus.

**Answer:** the user manager observes the **session bus** (`$XDG_RUNTIME_DIR/bus` / `DBUS_SESSION_BUS_ADDRESS`), confirmed by source, `sd_bus_default(3)`, and live bus ownership.

---

## Q3 — `BusName=` matching, `RequestName` flags, and contention

**Exact match on the well-known name.** The installed match rule is built verbatim (`src/core/unit.c:3660-3665`):

```
type='signal',sender='org.freedesktop.DBus',path='/org/freedesktop/DBus',
interface='org.freedesktop.DBus',member='NameOwnerChanged',arg0='<BusName>'
```

plus an initial `GetNameOwner("<BusName>")` (`unit.c:3679-3699`). There is no wildcard/prefix matching and no support for matching a unique name.

**systemd does not inspect `RequestName` flags or replies at all.** Readiness observes only whether a `NameOwnerChanged` transition produces a (new) owner. `service_bus_name_owner_change()` takes `new_owner` as a plain string and never consults the service's `RequestName` return value (`service.c:5670-5706`). The flags are therefore a property of the *service's* `RequestName` call, not of `BusName=`.

D-Bus specification (`org.freedesktop.DBus.RequestName`, `dbus-specification.html`, "RequestName"): each name has a queue; the head is the primary owner; each owner records `ALLOW_REPLACEMENT`/`DO_NOT_QUEUE`; `REPLACE_EXISTING` may replace a current owner only if that owner set `ALLOW_REPLACEMENT`; `DO_NOT_QUEUE` refuses queueing. Reply codes: `PRIMARY_OWNER=1`, `IN_QUEUE=2`, `EXISTS=3`, `ALREADY_OWNER=4`.

**What happens if another process already owns the name:**

- Pre-existing owner and no ownership change during the start window ⇒ systemd sees no `NameOwnerChanged` transition ⇒ the unit stays `activating` and **times out**, even though the initial `GetNameOwner` set `bus_name_good=true`; `service_enter_start()` never short-circuits on a pre-existing owner. **Live reproduction:** a squatter owned `org.dotfiles.Rdy3`; a `Type=dbus` service whose process called `RequestName(org.dotfiles.Rdy3, DO_NOT_QUEUE)` got `EXISTS` and (because it stayed alive) the unit still hit `ActiveState=failed`, `Result=timeout`.
- If the service is coded to **fail loud** on a non-`PRIMARY_OWNER` reply (`DO_NOT_QUEUE`, then exit non-zero), the unit fails fast and loudly: **live reproduction** gave `Result=exit-code`, `ExecMainStatus=1`, state `failed` within ~1 s (not a timeout). This is the recommended daemon behaviour.
- If the current owner set `ALLOW_REPLACEMENT` and the service requests `REPLACE_EXISTING`, the service takes the name ⇒ `NameOwnerChanged` to the service ⇒ unit becomes active.
- If the service merely queues (`IN_QUEUE`), no ownership change occurs ⇒ start timeout.

**Ownership is not cgroup-attributed.** For `Type=dbus`, `service_bus_name_owner_change()` treats *any* new owner as readiness; it does not verify the owner PID belongs to the unit. So a *different* process acquiring the name during the start window can satisfy systemd's readiness while the service is not the owner. This is a trust caveat for AD-38's "exactly one process owns `org.dotfiles.Events`" (D-Bus itself guarantees a single *primary* owner at a time, but systemd is not the thing enforcing that the primary owner is the daemon). systemd does refuse two *units* watching the same name at load: `unit_watch_bus_name()` returns `-EEXIST` → *"Two services allocated for the same bus name %s, refusing operation."* (`service.c:1078-1082`).

**Answer:** exact-name match via `NameOwnerChanged(arg0=name)` + `GetNameOwner`; systemd ignores `RequestName` flags/replies; a pre-existing owner causes a timeout unless the daemon fails loud (or wins `REPLACE_EXISTING`); a queued request never becomes ready.

---

## Q4 — `Restart=` and `StartLimitIntervalSec`/`StartLimitBurst`

**Name never acquired ⇒ timeout ⇒ failure ⇒ restart policy applies.** `Restart=` text: *"Timeouts include … a service start, reload, and stop operation timeout."* (`systemd.service(5)` line 694–703). Table 1 (`systemd.service(5)` lines 735–759) marks `Timeout` as restarting for `always`, `on-failure`, `on-abnormal`. Source: `service_dispatch_timer()` sets `SERVICE_FAILURE_TIMEOUT` for `SERVICE_START`; `service_shall_restart()` returns true for `always`/`on-failure`/`on-abnormal` on that result (`service.c:2281-2337`).

**Live reproduction of the crash-loop:** `Type=dbus`, name never acquired, `TimeoutStartSec=3`, `Restart=on-failure`, `RestartSec=100ms`, `StartLimitIntervalSec=60`, `StartLimitBurst=3` → three `timeout` restarts, then `Start request repeated too quickly`, final `ActiveState=failed`, `Result=start-limit-hit`, `NRestarts=3`. Defaults on this box: `DefaultStartLimitBurst=5`, `DefaultStartLimitIntervalUSec=10s`; rate limiting is the mechanism described in `systemd.unit(5)` lines 982–1026 and `systemd.service(5)` lines 768–770.

**Name lost while running is NOT a failure for `Type=dbus`.** `service_bus_name_owner_change()` on `new_owner == NULL` while running calls `service_enter_running(s, SERVICE_SUCCESS)` (`service.c:5670-5706`); `service_good()` returns false because `bus_name_good` is clear (`service.c:2620`), so the unit is stopped with `Result=success`.

- **Live reproduction (`Restart=on-failure`):** name acquired, then released while the process stayed alive → the manager SIGTERM'd it and the unit went `inactive/dead`, `Result=success`, `NRestarts=0`. It did **not** restart.
- **Live reproduction (`Restart=always`):** same script → auto-restart cycled (`NRestarts=2` in ~7 s, state `activating/auto-restart`).
- **Live reproduction (`Restart=on-failure`, daemon exits non-zero on SIGTERM):** the daemon released the name, then exited `7` on the manager's SIGTERM → journal `Main process exited, code=exited, status=7` → `Failed with result 'exit-code'` → `Scheduled restart job, restart counter is at 1`; `NRestarts=2`, unit active. So a non-zero exit on the stop path **does** turn name-loss into an `on-failure` restart.
- A manual `systemctl --user stop` sets `forbid_restart` (`service_shall_restart()`, `service.c:2285-2289`); no restart is scheduled and the counter is reset (observed `NRestarts=0` after stop).

**Answer:** a name-acquisition timeout *is* a failure and *does* trigger `Restart=`; auto-restarts are rate-limited by `StartLimitIntervalSec`/`StartLimitBurst` and can end in `failed` (`Result=start-limit-hit`). Name *loss* is a *clean* stop and is **not** restarted by `on-failure` unless the daemon exits non-zero on the resulting SIGTERM; `always`/`on-success` restart it.

---

## Q5 — Does `Type=dbus` need D-Bus activation / `dbus.service`?

**No activation; only the bus socket.** `Type=dbus` adds `Requires=` + `After=` on `dbus.socket` (source `service.c:1067-1076`; `systemd.service(5)` line ~automatic deps; `systemd.special(5)` lines 101–103: *"All units with `Type=dbus` automatically gain a dependency on this unit."*). It does **not** pull in `dbus.service`, and it does not itself perform D-Bus *activation*. It is purely a readiness observation of the manager's bus. Bus activation is the separate `SystemdService=` mechanism in a D-Bus `.service` file (`systemd.service(5)` Example 7, lines 1534–1543) and is not needed for a session service that is started by the manager.

For a user manager the referenced `dbus.socket` is the session-bus socket, which is socket-activated into `dbus-broker.service` (Alias `dbus.service`); local `dbus.socket` runs `ListenStream=%t/bus` and `dbus-broker.service` has `Requires=dbus.socket`. The special-unit description in `systemd.special(5)` says "system bus socket" because it is written for PID 1, but unit resolution happens in the calling manager's namespace, so in `--user` it is the user socket.

**Answer:** no `dbus.service`/system-bus activation is required; `Type=dbus` only requires the (session) `dbus.socket` and observes session-bus name ownership.

---

## Q6 — Edge cases / gotchas for user services

1. **The manager must actually be connected to the session bus.** If the user manager cannot reach `$XDG_RUNTIME_DIR/bus`, `BusName=` can never become ready and every such unit times out. systemd#892's reporter hit exactly this (non-standard socket path). On this target the standard path is `%t/bus` and the manager is connected (`busctl --user` shows `org.freedesktop.systemd1`).
2. **Adding `BusName=` silently changes the type.** `Type=dbus` *is* the default when `BusName=` is set (`systemd.service(5)` line 157; `service_add_extras()`, `service.c:1092-1099`). If you set `BusName=` on a unit but forget an explicit `Type=`, it becomes `dbus`. Always pin `Type=` explicitly.
3. **A pre-existing/squatting owner does not block by itself and does not satisfy readiness** — it produces a timeout unless the daemon fails loud or wins `REPLACE_EXISTING` (Q3). For AD-38 use `RequestName(DO_NOT_QUEUE)` and exit non-zero when not primary.
4. **Do not daemonize.** `Type=dbus` expects the foreground process that acquires the name to *be* the main process (`systemd.service(5)` Example 7: *"The service should not fork (daemonize)."*).
5. **Name loss kills the process.** Dropping the bus name during shutdown causes the manager to SIGTERM the service (`systemd.service(5)` line 163–168). A daemon that releases the name as normal shutdown must expect SIGTERM (and should exit cleanly to avoid an unintended `on-failure` restart).
6. **Start limits can mask a persistent readiness failure.** Default `5 starts / 10 s` leaves the unit `failed` (`Result=start-limit-hit`) — the failure mode AD-33 exists to prevent. Pin `StartLimitIntervalSec=`/`StartLimitBurst=`, or `StartLimitIntervalSec=0`.
7. **Session-bus startup ordering is already handled.** `dbus.socket` is wanted by `sockets.target` and is ordered `Before=` the Type=dbus user services on this box (`dconf`, `gvfs-*`, `xdg-desktop-portal*`, `at-spi-dbus-bus`); `Type=dbus` additionally Requires+After it. With uwsm 0.26.7, `wayland-session@.target` is bound to `graphical-session.target` (`man uwsm`), so a session service that must run after the compositor should be `WantedBy=graphical-session.target` + `After=graphical-session.target` (and optionally `PartOf=` for stop), per `systemd.special(5)` lines 951–984. `graphical-session.target` is active on this box.
8. **Ownership is not cgroup-attributed** (Q3): a foreign process acquiring the name during the start window can satisfy systemd readiness. Treat the name as observed, not as proof that the daemon owns it.

**Answer:** the notable practical edges are (a) manager must be on `%t/bus`, (b) `BusName=` implies `Type=dbus`, (c) contention needs fail-loud/loud restart design, (d) no daemonizing, (e) name-loss ⇒ SIGTERM (clean stop unless exit code is non-zero), (f) tune start limits, (g) hook the session via `graphical-session.target` (uwsm runs the compositor at that stage).

---

## Top findings (with citations)

1. **A user-manager `Type=dbus`/`BusName=` watches the session bus.** `bus_init_api()` opens `bus-api-user` via `sd_bus_open_user_with_description()` for non-system managers (`systemd v261 src/core/dbus.c:820-862`); `unit_watch_bus_name()` installs the match on `manager->api_bus` (`src/core/unit.c:3641-3733`); `man sd_bus_default(3)` lines 40–68; live `busctl --user` shows `org.freedesktop.systemd1` on the session bus and `dbus.socket` listens on `/run/user/1000/bus`. The #892 "session-bus asymmetry" is closed/misconfiguration.

2. **Readiness = a `NameOwnerChanged` transition for the exact well-known name.** Match rule `arg0='<BusName>'` plus `GetNameOwner` (`src/core/unit.c:3641-3707`); `systemd.service(5)` lines 154–168. systemd never inspects `RequestName` flags/replies, and it accepts *any* new owner (no cgroup attribution).

3. **Never-acquired name ⇒ `TimeoutStartSec` expiry ⇒ `failed` (`Result=timeout`).** `systemd.service(5)` lines 539–547; `service_dispatch_timer()` → `SERVICE_FAILURE_TIMEOUT` (`src/core/service.c:4885-4901`); default `DefaultTimeoutStartUSec=1min 30s` (`systemctl --user show`); reproduced live.

4. **A squatted name does not fail-soft — it times out** unless the daemon uses `DO_NOT_QUEUE` and exits non-zero on `EXISTS`, in which case it fails fast (`Result=exit-code`). Reproduced live both ways. (D-Bus spec `RequestName`.)

5. **Name lost while running is a *clean* stop (`Result=success`) and `Restart=on-failure` does not restart it.** `service_bus_name_owner_change()` → `service_enter_running(SERVICE_SUCCESS)` (`src/core/service.c:5670-5706`, `2615-2634`); reproduced: `Result=success`, `NRestarts=0`. `Restart=always` cycles it; a non-zero exit on the SIGTERM makes `on-failure` restart it.

6. **Auto-restarts are rate-limited and end in `failed` (`start-limit-hit`).** `systemd.unit(5)` lines 982–1026; `systemd.service(5)` lines 768–770; reproduced with `StartLimitBurst=3` → `Result=start-limit-hit`.

7. **`Type=dbus` needs only `dbus.socket` (session-bus socket), not D-Bus activation / `dbus.service`.** `service_setup_bus_name()` (`src/core/service.c:1058-1085`); `systemd.special(5)` lines 101–103; `systemd.service(5)` Example 7.

8. **Ordering/edge cases:** `BusName=` implies `Type=dbus` if `Type=` is unset (`service.c:1092-1099`); no daemonizing; start limits must be tuned; session services should hook `graphical-session.target`, which uwsm's `wayland-session@.target` binds to (`man systemd.special(5)` 951–984; `man uwsm`).

---

## Design implications for AD-33 / AD-38

- The review's requested verification passes: **`Type=dbus` + `BusName=org.dotfiles.Events` does track the session bus** on this target. Adopting it is sound.
- But `Type=dbus` + `Restart=on-failure` (as AD-33 currently reads) still yields a silently dead hub on **name loss** (`Result=success`, no restart) and can park in `failed` on `start-limit-hit` for a persistent readiness failure. The corrected rule must combine the type with the restart policy:
  - `Type=dbus` + `BusName=org.dotfiles.Events` for readiness/ownership, **plus**
  - `Restart=always` (or `on-success`) with explicit `StartLimitIntervalSec`/`StartLimitBurst` (or `StartLimitIntervalSec=0`) — **or** `Restart=on-failure` with the daemon exiting non-zero on `NameLost`/non-primary `RequestName`.
  - `RequestName(..., DO_NOT_QUEUE)` and non-zero exit when not primary (fail loud on a squatter).
  - `WantedBy=graphical-session.target` + `After=graphical-session.target`; do **not** `PartOf=`/`BindsTo=` the compositor unit (preserves the Hyprland-reload independence AD-33 wants). `Requires=dbus.socket` is supplied implicitly.
- Residual trust note for AD-38: systemd's `Type=dbus` readiness does not prove the owner is the daemon's own process; the caller→topic authorization must still be pinned at the hub (as AD-38 already requires).

Suggested unit shape:

```ini
[Unit]
Description=dotfiles reactive runtime (signal hub)
After=graphical-session.target
PartOf=graphical-session.target
Requires=dbus.socket
After=dbus.socket

[Service]
Type=dbus
BusName=org.dotfiles.Events
ExecStart=%h/.local/bin/dotfiles-runtime daemon run
Restart=always
RestartSec=2s
StartLimitIntervalSec=60
StartLimitBurst=5

[Install]
WantedBy=graphical-session.target
```

(`Requires=`/`After=dbus.socket` are redundant with the implicit dependency but harmless and self-documenting.)

---

## Empirical evidence appendix (this machine, 2026-09-11)

All tests used transient `systemd-run --user` units + a Python/Gio helper that connected to the session bus and called `RequestName`/`ReleaseName` on `org.dotfiles.*`. All test units were stopped and cleaned up afterwards.

| Test | Unit / config | Observed | Meaning |
| --- | --- | --- | --- |
| Positive readiness | `Type=dbus`, `BusName=org.dotfiles.Rdy1`, `TimeoutStartSec=15` | `ActiveState=active`, `SubState=running` within ~1 s; journal `Started …` after `RequestName -> PRIMARY_OWNER` | Name acquisition drives `Type=dbus` readiness on the session bus |
| Never acquired | `Type=dbus`, `BusName=org.dotfiles.Rdy2`, `TimeoutStartSec=8` | after 8 s: `failed`, `Result=timeout`, `ExecMainStatus=15` (SIGTERM) | Start timeout ⇒ `failed` |
| Contention, queued (no fail-loud) | squatter owns `org.dotfiles.Rdy3`; service `DO_NOT_QUEUE` → `EXISTS`, stays alive | `failed`, `Result=timeout` | Pre-existing owner ⇒ no readiness transition, even with `bus_name_good` set at load |
| Contention, fail-loud | same squatter; `DO_NOT_QUEUE` + exit 1 on non-primary | `failed`, `Result=exit-code`, `ExecMainStatus=1` in ~1 s | Fail-loud turns contention into an immediate, visible failure |
| Name loss, `Restart=on-failure` | acquire then release name, process stays alive | `inactive/dead`, `Result=success`, `NRestarts=0` | Name loss is a clean stop; `on-failure` does not restart |
| Name loss, `Restart=always` | same, release every 2 s | `NRestarts=2` in ~7 s (`activating/auto-restart`) | `always` restarts on name loss |
| Name loss, non-zero exit on SIGTERM | release name; daemon exits 7 on SIGTERM; `Restart=on-failure` | `Result=exit-code`, `Scheduled restart job`, `NRestarts=2` | A non-zero exit on the stop path makes `on-failure` restart |
| Start-limit | never acquired, `TimeoutStartSec=3`, `Restart=on-failure`, `StartLimitBurst=3` | `failed`, `Result=start-limit-hit`, `NRestarts=3` | Persistent readiness failure ends `failed` (silently dead watcher) |
| Bus facts | — | `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`; `dbus.socket` `Listen=/run/user/1000/bus`; `busctl --user` shows `org.freedesktop.systemd1`; `DefaultTimeoutStartUSec=1min 30s`; `DefaultStartLimitBurst=5`; `DefaultStartLimitIntervalUSec=10s` | Session-bus binding and defaults confirmed locally |

---

## Sources

- `man systemd.service(5)` — local, systemd 261 (Type= / BusName= / TimeoutStartSec= / Restart= / Table 1 / Example 7): lines 154–168, 299–344, 539–566, 694–770, 1515–1543.
- `man systemd.unit(5)` — local, StartLimitIntervalSec/StartLimitBurst: lines 982–1026.
- `man systemd.special(5)` — local, `dbus.service`/`dbus.socket`: lines 97–103; `graphical-session.target`: lines 951–995.
- `man sd_bus_default(3)` — local, user bus vs system bus and `DBUS_SESSION_BUS_ADDRESS`: lines 40–68, 82–85.
- `man uwsm(1)` — local, uwsm 0.26.7, `wayland-session@.target` bound to `graphical-session.target`.
- systemd v261 source: `src/core/dbus.c` (`bus_init_api` 820–862); `src/core/unit.c` (`unit_install_bus_match` 3641–3707, `unit_watch_bus_name` 3709–3733); `src/core/service.c` (`service_setup_bus_name` 1058–1085, `service_add_extras` 1092–1099, `service_enter_start` 2741–2832, `service_good` 2615–2634, `service_enter_dead` 2356–2394, `service_shall_restart` 2281–2337, `service_sigchld_event` ~4513–4700, `service_bus_name_owner_change` 5670–5706, `service_dispatch_timer` 4885–4901). Fetched from `https://raw.githubusercontent.com/systemd/systemd/v261/…` (also mirrored via jsDelivr).
- D-Bus specification — `RequestName`, `ReleaseName`, `NameOwnerChanged`, flags and reply codes: `https://dbus.freedesktop.org/doc/dbus-specification.html`.
- systemd issue #892 — `Type=dbus service needs option for session bus services` (closed; maintainer statement; misconfiguration root cause): `https://github.com/systemd/systemd/issues/892`.
- Live commands on this machine: `systemctl --user show`, `systemctl --user status`, `journalctl --user`, `busctl --user`, `systemd-run --user`, and the `~/.config/systemd/user/dbus.socket` unit file.
