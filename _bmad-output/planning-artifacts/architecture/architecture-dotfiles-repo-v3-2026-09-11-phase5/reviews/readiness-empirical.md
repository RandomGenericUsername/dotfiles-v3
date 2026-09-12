# Empirical Readiness Test — `Type=dbus` + `BusName` on the user (session) bus

- **Date:** 2026-09-11
- **Host:** Arch Linux, systemd 261, `systemd --user` (user@1000.service), Hyprland/Wayland session
- **Repo:** `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3`
- **Test bus name (positive):** `org.dotfiles.ReadinessTest`
- **Operator UID:** `uid=1000(inumaki)`

## Hypothesis under test

A `systemd --user` unit with `Type=dbus` + `BusName=<name>` becomes `active` **only** when some process owns that name on the **session** D-Bus, and it fails (not silently hangs) if the name is never acquired.

---

## Step 1 — Baseline

### Command

```sh
systemctl --version
systemctl --user show-environment | grep -i dbus
echo "$DBUS_SESSION_BUS_ADDRESS"
echo "$XDG_RUNTIME_DIR"
ls -l "$XDG_RUNTIME_DIR/bus"
```

### Raw output

```
systemd 261 (261.2-1-arch)
+PAM +AUDIT -SELINUX +APPARMOR -IMA +IPE +SMACK +SECCOMP +GCRYPT +GNUTLS +OPENSSL +ACL +BLKID +CURL +ELFUTILS +FIDO2 +IDN2 +KMOD +LIBCRYPTSETUP +LIBCRYPTSETUP_PLUGINS +LIBFDISK +PCRE2 +PWQUALITY +P11KIT +QRENCODE +TPM2 +BZIP2 +LZ4 +XZ +ZLIB +ZSTD +BPF_FRAMEWORK +BTF +XKBCOMMON +UTMP +LIBARCHIVE
---ENV---
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
---DBUS_SESSION_BUS_ADDRESS---
unix:path=/run/user/1000/bus
---XDG_RUNTIME_DIR---
/run/user/1000
---bus socket---
srw-rw-rw- 1 inumaki inumaki 0 sep 11 08:09 /run/user/1000/bus
```

### Tool availability

```
---systemd user status---
running
---python dbus---
dbus-python OK 1.4.0
---gjs---
/usr/bin/gjs
gjs 1.88.1
---busctl---
/usr/bin/busctl
systemd 261 (261.2-1-arch)
```

### Default timeouts (queried from the user manager)

```sh
systemctl --user show | grep -i timeout
```

```
DefaultTimeoutStartUSec=1min 30s
DefaultTimeoutStopUSec=1min 30s
DefaultTimeoutAbortUSec=1min 30s
DefaultDeviceTimeoutUSec=1min 30s
```

**Baseline note:** `~/.config/systemd/user/` did **not** exist before the test; it was created for this experiment and is empty again after cleanup.

---

## Step 2 — Bus-name owner (python3 + dbus-python + GLib main loop)

### Script `/tmp/opencode/readiness-test/own_name.py`

```python
#!/usr/bin/env python3
import sys
import time
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

NAME = "org.dotfiles.ReadinessTest"

def log(msg):
    print(f"[owner {time.strftime('%H:%M:%S')}] {msg}", flush=True)

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    try:
        bus = dbus.SessionBus()
        log(f"connected to session bus: {bus.get_unique_name()}")
    except Exception as e:
        log(f"FATAL: cannot connect to session bus: {e}")
        return 2

    # try to own the name without queueing
    try:
        name = dbus.service.BusName(NAME, bus, do_not_queue=True)
        log(f"OWNER_ACQUIRED {NAME} (do_not_queue)")
    except dbus.exceptions.NameExistsException as e:
        log(f"FATAL: name {NAME} already owned: {e}")
        return 3

    loop = GLib.MainLoop()

    def on_lost(*args, **kwargs):
        log(f"name lost: {args} {kwargs}")

    bus.add_signal_receiver(
        on_lost,
        signal_name="NameLost",
        dbus_interface="org.freedesktop.DBus",
        path="/org/freedesktop/DBus",
    )

    log("running GLib main loop")
    try:
        loop.run()
    except KeyboardInterrupt:
        log("interrupted")
    log("exiting")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Manual sanity run (outside systemd)

```sh
cd /tmp/opencode/readiness-test
timeout 4 python3 own_name.py > owner_manual.log 2>&1 &
sleep 1.5
cat owner_manual.log
busctl --user list | grep -i Readiness
wait
busctl --user list | grep -i Readiness
```

```
[owner 19:20:00] connected to session bus: :1.489
[owner 19:20:00] OWNER_ACQUIRED org.dotfiles.ReadinessTest (do_not_queue)
[owner 19:20:00] running GLib main loop
org.dotfiles.ReadinessTest                        259778 python3         inumaki :1.489        user@1000.service -       -
(grep: none)
```

Result: script acquires the name while alive, releases it on exit. Owner mechanism works.

---

## Step 3 — Temp user units

### Positive unit `~/.config/systemd/user/readiness-dbus-test.service`

```ini
[Unit]
Description=Readiness empirical test - dbus name owner (positive)

[Service]
Type=dbus
BusName=org.dotfiles.ReadinessTest
ExecStart=/usr/bin/python3 /tmp/opencode/readiness-test/own_name.py
```

### Negative unit `~/.config/systemd/user/readiness-dbus-never.service`

```ini
[Unit]
Description=Readiness empirical test - dbus BusName never acquired (negative)

[Service]
Type=dbus
BusName=org.dotfiles.ReadinessNeverTest
ExecStart=/bin/sleep 300
```

```sh
systemctl --user daemon-reload
```

```
daemon-reload rc=0
---fragment paths---
FragmentPath=/home/inumaki/.config/systemd/user/readiness-dbus-test.service

FragmentPath=/home/inumaki/.config/systemd/user/readiness-dbus-never.service
```

---

## Step 4 — POSITIVE test: name IS acquired

### Command

```sh
timeout 20 systemctl --user start readiness-dbus-test.service; echo "rc=$?"
systemctl --user show -p Type -p BusName -p ActiveState -p SubState -p Result readiness-dbus-test.service
systemctl --user status --no-pager readiness-dbus-test.service
busctl --user list | grep -i Readiness
```

### Raw output

```
rc=0
=== show ===
ActiveState=active
SubState=running
Type=dbus
BusName=org.dotfiles.ReadinessTest
Result=success
=== status ===
● readiness-dbus-test.service - Readiness empirical test - dbus name owner (positive)
     Loaded: loaded (/home/inumaki/.config/systemd/user/readiness-dbus-test.service; static)
     Active: active (running) since Fri 2026-09-11 19:20:34 -05; 9ms ago
 Invocation: f0418ec086b84e29a11575ece60c5075
   Main PID: 260669 (python3)
      Tasks: 1 (limit: 18571)
     Memory: 14.2M (peak: 14.2M)
        CPU: 67ms
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/readiness-dbus-test.service
             └─260669 /usr/bin/python3 /tmp/opencode/readiness-test/own_name.py

sep 11 19:20:34 juan-... systemd[4110]: Starting Readiness empirical test - dbus name owner (positive)...
sep 11 19:20:34 juan-... python3[260669]: [owner 19:20:34] connected to session bus: :1.492
sep 11 19:20:34 juan-... python3[260669]: [owner 19:20:34] OWNER_ACQUIRED org.dotfiles.ReadinessTest (do_not_queue)
sep 11 19:20:34 juan-... systemd[4110]: Started Readiness empirical test - dbus name owner (positive).
sep 11 19:20:34 juan-... python3[260669]: [owner 19:20:34] running GLib main loop
=== busctl ===
org.dotfiles.ReadinessTest                        260669 python3         inumaki :1.492        user@1000.service -       -
```

**Result:** `systemctl start` returns `0` almost immediately. Unit is `active (running)`, `Result=success`, and the bus name is present on the **session** bus. The readiness signal behaves as specified.

---

## Step 5 — NEGATIVE test: name is NEVER acquired (process stays alive)

Unit `readiness-dbus-never.service` runs `/bin/sleep 300` and never calls `RequestName`.

### Command

```sh
start=$(date +%s.%N)
timeout 130 systemctl --user start readiness-dbus-never.service
rc=$?
end=$(date +%s.%N)
echo "rc=$rc elapsed=$(awk "BEGIN{printf \"%.2f\", $end-$start}")s"
systemctl --user show -p Type -p BusName -p ActiveState -p SubState -p Result -p TimeoutStartUSec readiness-dbus-never.service
```

### Raw output

```
Job for readiness-dbus-never.service failed because a timeout was exceeded.
See "systemctl --user status readiness-dbus-never.service" and "journalctl --user -xeu readiness-dbus-never.service" for details.
rc=1 elapsed=90.14s
=== show immediately after ===
ActiveState=failed
SubState=failed
Type=dbus
TimeoutStartUSec=1min 30s
BusName=org.dotfiles.ReadinessNeverTest
Result=timeout
```

### Status + journal

```
× readiness-dbus-never.service - Readiness empirical test - dbus BusName never acquired (negative)
     Loaded: loaded (.../readiness-dbus-never.service; static)
     Active: failed (Result: timeout) since Fri 2026-09-11 19:22:08 -05; 4s ago
    Process: 260781 ExecStart=/bin/sleep 300 (code=killed, signal=TERM)
   Main PID: 260781 (code=killed, signal=TERM)
```

```
19:20:38 systemd[4110]: Starting Readiness empirical test - dbus BusName never acquired (negative)...
19:22:08 systemd[4110]: readiness-dbus-never.service: start operation timed out. Terminating.
19:22:08 systemd[4110]: readiness-dbus-never.service: Failed with result 'timeout'.
19:22:08 systemd[4110]: Failed to start Readiness empirical test - dbus BusName never acquired (negative).
```

**Result:** Start blocks for **90.14 s** — exactly the manager default `DefaultTimeoutStartSec=1min 30s` (no per-unit `JobTimeoutSec`/`TimeoutStartSec` set). Then the unit is `failed (Result: timeout)` and the ExecStart process is sent `SIGTERM` (`code=killed, signal=TERM`). Failure is explicit; there is no indefinite hang.

---

## Step 6 — Name contention

The positive unit was still `active (running)` owning `org.dotfiles.ReadinessTest` (PID 260669, unique name `:1.492`).

### 6a. Second process requesting the same name (`DO_NOT_QUEUE`)

```sh
timeout 8 python3 /tmp/opencode/readiness-test/own_name.py; echo "A rc=$?"
```

```
[owner 19:22:17] connected to session bus: :1.495
[owner 19:22:17] FATAL: name org.dotfiles.ReadinessTest already owned: Bus name already exists: org.dotfiles.ReadinessTest
A rc=3
```

### 6b. Raw D-Bus `RequestName` semantic codes

```sh
# flags=4 (DO_NOT_QUEUE)
busctl --user call org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus RequestName su org.dotfiles.ReadinessTest 4

# flags=0 (allow queueing)
busctl --user call org.freedesktop.DBus /org/freedesktop/DBus \
  org.freedesktop.DBus RequestName su org.dotfiles.ReadinessTest 0
```

```
u 3      # 3 = DBUS_REQUEST_NAME_REPLY_EXISTS
u 2      # 2 = DBUS_REQUEST_NAME_REPLY_IN_QUEUE
```

### 6c. Second **systemd unit** declaring the same `BusName`

Unit `readiness-dbus-contend.service` (same `BusName=org.dotfiles.ReadinessTest`):

```sh
systemctl --user daemon-reload
timeout 30 systemctl --user start readiness-dbus-contend.service; echo "rc=$?"
systemctl --user show -p Type -p BusName -p ActiveState -p SubState -p Result readiness-dbus-contend.service
systemctl --user status --no-pager readiness-dbus-contend.service
```

```
Failed to start readiness-dbus-contend.service: Unit readiness-dbus-contend.service failed to load properly, please adjust/correct and reload service manager: File exists
rc=1 elapsed=0.01s
=== show contend ===
ActiveState=inactive
SubState=dead
Type=dbus
BusName=org.dotfiles.ReadinessTest
Result=success
=== status contend ===
○ readiness-dbus-contend.service - Readiness empirical test - contend for same BusName
     Loaded: error (Reason: Unit ... failed to load properly ...: File exists)
     Active: inactive (dead)

19:22:22 systemd[4110]: readiness-dbus-contend.service: Two services allocated for the same bus name org.dotfiles.ReadinessTest, refusing operation.
19:22:22 systemd[4110]: readiness-dbus-contend.service: Two services allocated for the same bus name org.dotfiles.ReadinessTest, refusing operation.
19:22:22 systemd[4110]: readiness-dbus-contend.service: Two services allocated for the same bus name org.dotfiles.ReadinessTest, refusing operation.
```

**Result:** systemd refuses to even load a second unit that allocates the same `BusName` ("Two services allocated for the same bus name … refusing operation"). Contention between two managed units is therefore prevented at load time, not resolved at runtime. At the raw D-Bus layer, a second owner is rejected (`EXISTS`) or queued (`IN_QUEUE`) with standard semantics.

---

## Additional finding A — owner process dies → unit deactivates, name released

```sh
PID=$(systemctl --user show -p MainPID --value readiness-dbus-test.service)   # 260669
kill -KILL "$PID"; sleep 1.5
systemctl --user show -p ActiveState -p SubState -p Result -p ExecMainStatus -p ExecMainCode readiness-dbus-test.service
busctl --user list | grep -i Readiness
```

```
ActiveState=failed
SubState=failed
Result=signal
ExecMainCode=2
ExecMainStatus=9
```

```
19:22:42 systemd[4110]: readiness-dbus-test.service: Main process exited, code=killed, status=9/KILL
19:22:42 systemd[4110]: readiness-dbus-test.service: Failed with result 'signal'.
=== bus name ===
(none)
```

**Result:** On process death the name is released and the unit leaves `active` (here `failed/Result=signal` because it was `SIGKILL`ed). Ownership and unit liveness are tied together.

---

## Additional finding B — ExecStart exits 0 BEFORE acquiring the name → `Result=success` (silent)

This is a `Type=dbus` readiness **hole** and was re-confirmed twice.

```ini
[Service]
Type=dbus
BusName=org.dotfiles.ReadinessExitTest
ExecStart=/bin/true
```

```
start rc=0 elapsed=0.03s
ActiveState=inactive
SubState=dead
BusName=org.dotfiles.ReadinessExitTest
Result=success
ExecMainCode=0
ExecMainStatus=0
journal: "Starting ..." then "Started ..."   (no failure, no "Main process exited")
```

Non-zero exit is handled differently:

```ini
ExecStart=/bin/false        # BusName=org.dotfiles.ReadinessExit2Test
```

```
Job for readiness-dbus-exit2.service failed because the control process exited with error code.
start rc=1 elapsed=0.02s
ActiveState=failed
SubState=failed
Result=exit-code
ExecMainCode=1
ExecMainStatus=1
journal: "Main process exited, code=exited, status=1/FAILURE" / "Failed with result 'exit-code'."
```

Re-confirmation (fresh units, incl. a 2 s delay before exit 0):

```
=== retest-true: start rc=0 elapsed=0.03s ===   # ExecStart=/bin/true
ActiveState=inactive  SubState=dead  Result=success  ExecMainStatus=0

=== retest-sleep: start rc=0 elapsed=2.03s ===  # ExecStart=/bin/sh -c 'sleep 2; exit 0'
ActiveState=inactive  SubState=dead  Result=success  ExecMainStatus=0
```

**Result:** if the `ExecStart` process terminates with status `0` before owning the `BusName`, `systemctl start` returns **success**, the unit ends `inactive (dead)`, and `Result=success`. systemd does **not** report "exited before acquiring bus name" in this version (261). A dependent that only observes start-job success / `After=` ordering would proceed even though the unit is not active and no process owns the name. A non-zero early exit does fail (`Result=exit-code`).

---

## Step 7 — Cleanup and verification

### Commands

```sh
systemctl --user stop  readiness-dbus-test readiness-dbus-never readiness-dbus-contend readiness-dbus-exit readiness-dbus-exit2
systemctl --user disable <the same units>     # no-op: units are static (no [Install])
systemctl --user reset-failed
rm -v ~/.config/systemd/user/readiness-dbus-*.service
systemctl --user daemon-reload
rm -rf /tmp/opencode/readiness-test
```

### Raw output (selected)

```
stop readiness-dbus-test rc=0
stop readiness-dbus-never rc=0
Failed to stop readiness-dbus-contend.service: Unit readiness-dbus-contend.service not loaded.
stop readiness-dbus-contend rc=5
stop readiness-dbus-exit rc=0
stop readiness-dbus-exit2 rc=0
...
removed '/home/inumaki/.config/systemd/user/readiness-dbus-test.service'
removed '/home/inumaki/.config/systemd/user/readiness-dbus-never.service'
removed '/home/inumaki/.config/systemd/user/readiness-dbus-contend.service'
removed '/home/inumaki/.config/systemd/user/readiness-dbus-exit.service'
removed '/home/inumaki/.config/systemd/user/readiness-dbus-exit2.service'
daemon-reload rc=0
```

### Final verification (after cleanup)

```
-- unit files --                          (empty)
-- readiness units --                     (none)
-- bus names --                           (none)
-- processes --                           (no python3)
transient units: app-*.scope, dbus-:1.*-org.a11y.atspi.Registry, kitty-*.scope, podman-pause-*.scope   (all pre-existing, unrelated)
```

No test unit files, no `Readiness*` bus names, no lingering `python3`/`own_name.py` processes remain. `~/.config/systemd/user/` is empty again as at baseline.

---

## Verdict

**Yes — `Type=dbus` + `BusName` is a valid, clean readiness signal on this machine, with one important caveat.**

- When a process acquires the session-bus name, the unit goes `active (running)`, `Result=success`, and start returns immediately (sub-second). It is not active before the name is owned (the start job blocks until then).
- When the name is never acquired and the process stays alive, the start job blocks and then fails hard at the manager default `DefaultTimeoutStartSec` = **90 s**, with `Result=timeout`, `ActiveState=failed`, `SubState=failed`, and the ExecStart process `SIGTERM`-killed. It does not hang indefinitely.
- Ownership is lifecycle-coupled: when the owning process dies, the name is released and the unit leaves `active` (here `failed/Result=signal` for `SIGKILL`).
- Contention is handled two ways: at the raw bus layer via standard D-Bus semantics (`EXISTS` for `DO_NOT_QUEUE`, `IN_QUEUE` for queueing), and at the systemd-manager layer by refusing to load a second unit that allocates the same `BusName` ("Two services allocated for the same bus name … refusing operation").
- **Caveat:** `Type=dbus` does not fail the unit if `ExecStart` exits `0` without acquiring the name. In systemd 261 that yields start `rc=0`, unit `inactive (dead)`, `Result=success`, with only `Starting`/`Started` in the journal. The bus name is therefore a valid readiness gate **only while the ExecStart process remains alive**; a wrapper that daemonizes, or a script that returns 0 early, can produce a false "success" start. A non-zero early exit does fail the unit (`Result=exit-code`).

## Top findings

1. **Positive readiness holds:** name owned → `active (running)` / `Result=success`; start returns in milliseconds. The signal is tied to actual session-bus ownership.
2. **Never-acquired name fails at 90 s, not before:** default `TimeoutStartSec=1min 30s`, measured **90.14 s**, result `timeout`, state `failed/failed`, process `SIGTERM`-killed. Per-unit `TimeoutStartSec`/`JobTimeoutSec` is required to shorten this.
3. **False-success hole:** `ExecStart` exiting `0` before acquiring the name gives start `rc=0`, `Result=success`, unit `inactive (dead)` — no error. `Type=dbus` readiness is only sound if the process does not exit early; a non-zero early exit does fail correctly (`exit-code`).
4. **Contention is prevented at manager level:** a second unit with the same `BusName` fails to *load* ("Two services allocated for the same bus name … refusing operation"). Raw-bus second owners get `EXISTS` (`DO_NOT_QUEUE`) or `IN_QUEUE`.
5. **Name loss = deactivation:** killing the owner releases the name and removes the unit from `active`; ownership and unit liveness are coupled.
6. **Cleanup verified clean:** no unit files, no `Readiness*` bus names, no lingering processes; `~/.config/systemd/user/` returned to its pre-test empty state.

## Test artifacts

- Log: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/reviews/readiness-empirical.md`
- Temp units and scripts were created under `~/.config/systemd/user/` and `/tmp/opencode/readiness-test/` and have been **removed**.
