# Readiness Review — Session Bus & Hyprland/uwsm Environment for a systemd `--user` Service

**Reviewer:** session-environment integration reviewer (evidence-only)
**Date:** 2026-09-11
**Repo:** `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3`
**Host/OS:** Arch Linux, dbus 1.16.2, dbus-broker 37-3, uwsm 0.26.7, Hyprland 0.56.2
**Session:** Hyprland under uwsm (`DESKTOP_SESSION=hyprland-uwsm`, `XDG_CURRENT_DESKTOP=Hyprland`), AGS/GJS apps
**Mandate:** determine, with local evidence (and web where a distro convention must be pinned), whether a repo-provisioned systemd `--user` unit can cleanly obtain (a) the per-user session bus and (b) the Wayland/Hyprland environment, and what `WantedBy=`/`After=`/`PartOf=` it must carry.

---

## VERDICT

**YES — a user unit can cleanly obtain both the session bus and the full Hyprland env, with no manual `import-environment`.**

Use the distro-standard interface `graphical-session.target`:

```ini
[Unit]
Description=...
PartOf=graphical-session.target
After=graphical-session.target
Requires=graphical-session.target          # recommended (see F3)
ConditionEnvironment=WAYLAND_DISPLAY       # recommended: skip cleanly with no session
[Service]
Type=simple
ExecStart=%h/.local/bin/dotfiles-runtime daemon run
Restart=on-failure
Slice=session.slice
[Install]
WantedBy=graphical-session.target
```

- **Do not** bind to `wayland-session@hyprland.desktop.target` or any `hyprland-session.target` (which does not exist) — those are runtime-generated, machine/session-specific uwsm internals, not a stable provisioning interface.
- The env is guaranteed present **because `wayland-session-waitenv.service` runs `Before=graphical-session.target`** and blocks until `WAYLAND_DISPLAY` + `HYPRLAND_INSTANCE_SIGNATURE` are in the systemd manager activation environment. A unit ordered `After=graphical-session.target` therefore cannot race the env import.
- The session bus address is in the manager environment before the graphical session is reached (`dbus.socket` `ExecStartPost` sets it), so a `graphical-session.target` unit also has `DBUS_SESSION_BUS_ADDRESS`.

---

## Environment snapshot (evidence)

```
$ echo "$XDG_RUNTIME_DIR $DBUS_SESSION_BUS_ADDRESS $WAYLAND_DISPLAY"
/run/user/1000 unix:path=/run/user/1000/bus wayland-1

$ echo "$HYPRLAND_INSTANCE_SIGNATURE"
efb50993780079460b0cbed1363e2166a2de1d9f_1789132265_284911308

$ echo "$DESKTOP_SESSION"
hyprland-uwsm

$ systemctl --user show-environment | grep -E 'DBUS|WAYLAND|HYPRLAND|XDG_(RUNTIME|SESSION)'
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
XDG_RUNTIME_DIR=/run/user/1000
DESKTOP_SESSION=hyprland-uwsm
HYPRLAND_INSTANCE_SIGNATURE=efb50993780079460b0cbed1363e2166a2de1d9f_1789132265_284911308
WAYLAND_DISPLAY=wayland-1
XDG_BACKEND=wayland
XDG_CURRENT_DESKTOP=Hyprland
XDG_SESSION_DESKTOP=Hyprland
XDG_SESSION_TYPE=wayland
UWSM_FINALIZE_VARNAMES=HYPRLAND_INSTANCE_SIGNATURE HYPRLAND_CMD HYPRCURSOR_THEME HYPRCURSOR_SIZE XCURSOR_SIZE XCURSOR_THEME
UWSM_WAIT_VARNAMES=HYPRLAND_INSTANCE_SIGNATURE
```

The compositor unit is active and is the real session owner:

```
$ systemctl --user status 'wayland-wm@hyprland.desktop.service' | head -6
● wayland-wm@hyprland.desktop.service - Main service for Hyprland, …
     Active: active (running) since Fri 2026-09-11 08:11:06 -05; 11h ago
     Drop-In: /run/user/1000/systemd/user/wayland-wm@hyprland.desktop.service.d
              └─50_custom.conf
   Main PID: 6612 (start-hyprland)
```

---

## Q1 — Is the session bus the per-user bus at `$XDG_RUNTIME_DIR/bus`? What address does the systemd user manager have?

**Yes.** The session bus is the systemd-socket-activated per-user bus, socket `%t/bus` = `/run/user/1000/bus`, broker `dbus-broker.service`. Both the login shell and the systemd user manager carry `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`.

Evidence:

```
$ ls -la /run/user/1000/bus
srw-rw-rw- 1 inumaki inumaki 0 sep 11 08:09 /run/user/1000/bus

$ systemctl --user status dbus.socket | head -8
● dbus.socket - D-Bus User Message Bus Socket
     Active: active (running) since Fri 2026-09-11 08:09:28 -05
   Triggers: ● dbus-broker.service
     Listen: /run/user/1000/bus (Stream)

$ systemctl --user status dbus.service | head -6
● dbus-broker.service - D-Bus User Message Bus
     Active: active (running) since Fri 2026-09-11 08:09:58 -05
   Main PID: 4216 (dbus-broker-lau)

$ cat /usr/lib/systemd/user/dbus.socket
[Socket]
ListenStream=%t/bus
ExecStartPost=-/usr/bin/systemctl --user set-environment DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus
```

The **manager** address is asserted by `systemctl --user show-environment` (above) and by the manager's saved pre-import env file (written by `uwsm aux prepare-env` before any compositor variables were merged):

```
$ head -1 /run/user/1000/uwsm/env_pre | tr '\0' '\n' | grep DBUS
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
```

Mechanism: `dbus.socket`'s `ExecStartPost=` calls `systemctl --user set-environment DBUS_SESSION_BUS_ADDRESS=%t/bus`. `dbus.socket` is pulled by `sockets.target` ← `basic.target` ← `graphical-session.target` (`Requires=basic.target`), so the address is installed in the manager environment **before** the graphical session target is reached. `busctl --user list` succeeds, confirming a live broker on that socket.

---

## Q2 — Does a systemd `--user` service started under this session inherit/reach the session bus and the Wayland/Hyprland env? Which mechanism imports it?

**Yes — inherited from the systemd user-manager activation environment** (services get the manager's env unless overridden). Confirmed on units actually spawned by systemd (not by the compositor):

```
$ P=$(systemctl --user show at-spi-dbus-bus.service -p MainPID --value); tr '\0' '\n' < /proc/$P/environ | grep -E 'DBUS|WAYLAND|HYPRLAND|XDG_(RUNTIME|SESSION)'
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
XDG_RUNTIME_DIR=/run/user/1000
HYPRLAND_INSTANCE_SIGNATURE=efb50993780079460b0cbed1363e2166a2de1d9f_1789132265_284911308
WAYLAND_DISPLAY=wayland-1
XDG_SESSION_TYPE=wayland
XDG_CURRENT_DESKTOP=Hyprland

$ P=$(systemctl --user show xdg-desktop-portal-gtk.service -p MainPID --value); tr '\0' '\n' < /proc/$P/environ | grep -E 'DBUS|WAYLAND|HYPRLAND|XDG_RUNTIME'
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
XDG_RUNTIME_DIR=/run/user/1000
HYPRLAND_INSTANCE_SIGNATURE=efb50993780079460b0cbed1363e2166a2de1d9f_1789132265_284911308
WAYLAND_DISPLAY=wayland-1
```

`Environment=`/`EnvironmentFiles=` are empty for these units; the vars come solely from the manager environment. The compositor itself passes them down to its own children (hyprpaper, dunst both show the full set), but that is a separate path — the systemd-spawned units above are the relevant proof for the `--user` service case.

**Import mechanism (authoritative, from `uwsm 0.26.7`):** it is **uwsm**, not `systemctl --user import-environment` and not `dbus-update-activation-environment`.

1. `wayland-wm-env@.service` → `uwsm aux prepare-env` loads the login/session + profile + WM env files and diff-exports XDG/session vars into the manager via D-Bus `org.freedesktop.systemd1.Manager.SetEnvironment` (`/usr/share/uwsm/modules/uwsm/dbus.py:172`, `main.py:922`). It is bound to `graphical-session-pre.target`, i.e. it runs first.
2. `uwsm finalize` (called by the compositor's startup, see `dotfiles/config/hypr/autostart.lua` / the injected `ExecStart=uwsm aux exec` drop-in) exports `WAYLAND_DISPLAY`, `DISPLAY`, and `UWSM_FINALIZE_VARNAMES` (includes `HYPRLAND_INSTANCE_SIGNATURE`, `HYPRLAND_CMD`, cursor vars) through the same `SetEnvironment` (`main.py:2379-2446`).
3. `dbus-broker` is detected (`dbus.service` Id `dbus-broker.service`), so uwsm **skips** the legacy `UpdateActivationEnvironment` call — the manager env is the single source (`main.py:956-979`). If dbus-daemon were in use, uwsm would additionally call the bus's `UpdateActivationEnvironment`.
4. `graphical-session.target` is the coordination point that *waits* for the import (via `wayland-session-waitenv.service`), it does not itself import anything.

`systemctl --user import-environment` is a valid generic alternative but is **not used here** and is unnecessary under uwsm.

---

## Q3 — Correct `WantedBy=` / `After=` / `PartOf=` for a unit that must start with the graphical session

**Interface: `graphical-session.target`.** There is **no** `hyprland-session.target` (nor `wayland-session.target`); what uwsm creates is the templated instance `wayland-session@hyprland.desktop.target`.

```
$ systemctl --user list-units '*.target' --no-pager
  graphical-session-pre.target                          loaded active active
  graphical-session.target                              loaded active active
  wayland-session-envelope@hyprland.desktop.target       loaded active active
  wayland-session-pre@hyprland.desktop.target            loaded active active
  wayland-session-shutdown.target                        loaded inactive dead
  wayland-session-xdg-autostart@hyprland.desktop.target  loaded active active
  wayland-session@hyprland.desktop.target                loaded active active
```

`graphical-session.target` is the stable, generic systemd interface; uwsm binds its per-session target to it. From the unit files:

```
$ systemctl --user show 'wayland-session@hyprland.desktop.target' -p BindsTo -p WantedBy -p After
BindsTo=graphical-session.target
WantedBy=
After=wayland-session-pre@hyprland.desktop.target graphical-session-pre.target wayland-wm@hyprland.desktop.service wayland-session-waitenv.service

$ systemctl --user show graphical-session.target -p After -p BindsTo -p BoundBy -p RefuseManualStart
After=wayland-session@hyprland.desktop.target wayland-session-waitenv.service basic.target wayland-wm@hyprland.desktop.service graphical-session-pre.target
RefuseManualStart=yes
BoundBy=wayland-session@hyprland.desktop.target
```

So: uwsm's session target `BindsTo=graphical-session.target`; `graphical-session.target` stops when the compositor/session goes away. Bind the daemon to `graphical-session.target`, **not** to the templated uwsm target (whose instance id embeds the desktop file and is regenerated every start; `wayland-session-pre@` even has `RefuseManualStart=yes`).

**Canonical pattern, exactly as shipped by distro units already active in this session:**

```
$ cat /usr/lib/systemd/user/hyprpaper.service
[Unit]
PartOf=graphical-session.target
Requires=graphical-session.target
After=graphical-session.target
ConditionEnvironment=WAYLAND_DISPLAY
[Service]
Type=simple
ExecStart=/usr/bin/hyprpaper
Slice=session.slice
Restart=on-failure
[Install]
WantedBy=graphical-session.target
```

Same shape in `waybar.service` (`PartOf=`, `After=`, `Requisite=`, `WantedBy=graphical-session.target`) and `dunst.service` (`PartOf=`, `After=`).

Role of each key:
- **`PartOf=graphical-session.target`** — propagate *stop/restart*: when the session target stops (compositor exits / `wayland-session-shutdown`), this unit is stopped too. It does **not** pull or order.
- **`WantedBy=graphical-session.target`** — the pull: `systemctl --user enable` creates `~/.config/systemd/user/graphical-session.target.wants/<unit>`, so the unit starts when the target is reached.
- **`After=graphical-session.target`** — ordering: the unit starts only once the target (hence after `wayland-session-waitenv.service`) is active; this is what guarantees the env is populated.
- `Requires=graphical-session.target` (optional but recommended, as in hyprpaper) — if the target can't be reached, don't start a half-configured daemon.
- `ConditionEnvironment=WAYLAND_DISPLAY` (optional, recommended) — skip cleanly when there is no live session (e.g. a stray `systemctl --user start` outside the session) instead of failing.

**Provisioning note (already flagged in `.memlog.md:25`):** `systemctl --user enable` only works with a running user manager. If the provisioning role runs outside a live user D-Bus session, enabling the unit must be done by symlinking into `~/.config/systemd/user/graphical-session.target.wants/` rather than calling `systemctl --user enable`.

---

## Q4 — What if the unit starts before the bus/env is ready; how is ordering ensured?

**Ordering chain that guarantees readiness:**

```
boot(1) user@1000.service → systemd --user (PID 4110)
  └─ sockets.target → dbus.socket  ──ExecStartPost──▶ set-environment DBUS_SESSION_BUS_ADDRESS=%t/bus
  └─ basic.target
       └─ graphical-session-pre.target
            └─ wayland-wm-env@hyprland.desktop.service (uwsm aux prepare-env → SetEnvironment of XDG/session vars)
       └─ wayland-session-waitenv.service   Before=graphical-session.target
            (uwsm aux waitenv: polls manager Environment for WAYLAND_DISPLAY + UWSM_WAIT_VARNAMES,
             i.e. HYPRLAND_INSTANCE_SIGNATURE; timeout 30s; OnFailure=wayland-session-shutdown)
       └─ graphical-session.target  ← uwsm's wayland-session@…target BindsTo this
            └─ your unit (WantedBy + After)
```

Evidence for the wait gate:

```
$ systemctl --user cat wayland-session-waitenv.service | grep -E 'Before|After|ExecStart|Timeout'
Before=graphical-session.target
After=graphical-session-pre.target
ExecStart=/usr/bin/uwsm aux waitenv
TimeoutStartSec=30

$ systemctl --user show graphical-session.target -p After | tr ' ' '\n' | grep waitenv
wayland-session-waitenv.service
```

`uwsm aux waitenv` reads the manager activation environment each 0.5 s and returns only when all wait-vars are present (`/usr/share/uwsm/modules/uwsm/main.py:4435-4465`). `UWSM_WAIT_VARNAMES=HYPRLAND_INSTANCE_SIGNATURE` is appended by the Hyprland plugin (`/usr/share/uwsm/plugins/hyprland.sh`) and set in this session's env. Therefore `After=graphical-session.target` is sufficient — the target cannot be active before the env is exported.

**If a unit starts before readiness** (e.g. hooked to `default.target`, a `.wants/` of `basic.target`, or manually with no session):
- `DBUS_SESSION_BUS_ADDRESS` is usually already present (socket-level, set before `basic.target` completes), but `WAYLAND_DISPLAY` / `HYPRLAND_INSTANCE_SIGNATURE` may be absent; the unit then has no compositor to talk to.
- `ConditionEnvironment=WAYLAND_DISPLAY` makes this a clean skip rather than a failed/restarting unit.
- A D-Bus connect at that moment may still succeed (bus socket exists), so "bus reachable" ≠ "session env ready"; the ordering above is what makes both true.

The log shows the target is reached only after the manager and bus are up: `systemd[4110]: Reached target Current graphical user session.` at `08:11:06`, ~96 s after `dbus.socket` came up at `08:09:28`.

---

## Q5 — Repo claim that uwsm is present

**Confirmed (with one precision).**

- `src/provisioning/ansible/group_vars/arch.yml` declares `uwsm: uwsm` (line 16) with the rationale "wraps the Hyprland session in a systemd user unit (hyprland-uwsm desktop entry…)".
- `dotfiles/provisioning/packages.yaml:20` also declares `uwsm`.
- Runtime presence matches: `pacman -Q uwsm` → `uwsm 0.26.7-1`; `which uwsm` → `/usr/bin/uwsm`; the live session is `DESKTOP_SESSION=hyprland-uwsm`, and `wayland-wm@hyprland.desktop.service` is active with uwsm-injected drop-ins under `/run/user/1000/systemd/user/`.
- The uwsm desktop entry is installed: `/usr/share/wayland-sessions/hyprland-uwsm.desktop` → `Exec=uwsm start -e -D Hyprland hyprland.desktop`.

**Precision:** `dotfiles/config/hypr/autostart.lua` does **not** contain the string `uwsm`. It *assumes* the uwsm-managed session by invoking `systemctl --user start hyprpolkitagent`, `systemctl --user start xdg-desktop-portal-hyprland`, etc. That assumption holds here (those units inherit the manager env per Q2), but the file itself is not direct evidence of uwsm's presence — the direct evidence is `arch.yml`, `packages.yaml`, the installed desktop entry, and the running `hyprland-uwsm` session. The claim is true; the stated file is an indirect corroborator, not the source.

---

## Findings

**F1 — MEDIUM — `wayland-session@<id>.target` is the wrong binding target for a provisioned unit.** It is a runtime-generated, per-desktop template instance (`wayland-session@hyprland.desktop.target`), not a stable interface; provisioning cannot know the instance id ahead of time. Use `graphical-session.target` (which uwsm `BindsTo`). Evidence: `list-units '*.target'`; `wayland-session@` unit file.

**F2 — HIGH (for provisioning correctness) — `enable` vs symlink outside a live session.** The repo's own memlog (`.memlog.md:25`) flags this: provisioning a `~/.config/systemd/user/` unit is a new pattern and `systemctl --user enable` needs a running user manager/bus. If bootstrap can run outside the session, write the `graphical-session.target.wants/` symlink directly. This is the single most likely integration failure for AD-33's daemon.

**F3 — MEDIUM — bare `WantedBy=graphical-session.target` without ordering is insufficient.** `WantedBy` pulls but does not order; without `After=graphical-session.target` a `Type=simple` daemon can start while the env import is still pending. Ship `PartOf=` + `After=` + `WantedBy=` together (and preferably `Requires=` + `ConditionEnvironment=WAYLAND_DISPLAY`).

**F4 — LOW — do not rely on `systemctl --user import-environment`.** Under uwsm it is neither called nor needed; the import is `Manager.SetEnvironment` performed by `uwsm aux prepare-env` (early) and `uwsm finalize` (WAYLAND_DISPLAY + HYPRLAND_INSTANCE_SIGNATURE). Adding it to provisioning would be redundant and could shadow uwsm's lifecycle cleanup (`unset_systemd_vars` on shutdown).

**F5 — INFO — bus-ready ≠ env-ready.** `DBUS_SESSION_BUS_ADDRESS` is installed before `basic.target` via `dbus.socket` `ExecStartPost`, so bus access is available earlier than the Wayland env; only `After=graphical-session.target` synchronizes both.

**F6 — INFO — `Restart=on-failure` + `Type=simple` is the correct AD-33 shape and works with this pattern**, but note the daemon must tolerate being stopped by `PartOf=graphical-session.target` on every compositor exit (a Hyprland reload is not a session exit; a full session stop is). This matches AD-33's intent.

---

## Evidence appendix — commands run

```
echo "$XDG_RUNTIME_DIR $DBUS_SESSION_BUS_ADDRESS $WAYLAND_DISPLAY $HYPRLAND_INSTANCE_SIGNATURE $DESKTOP_SESSION"
systemctl --user show-environment
systemctl --user list-units '*.target' --all --no-pager
systemctl --user list-dependencies graphical-session.target --no-pager
systemctl --user show graphical-session.target -p After -p BindsTo -p BoundBy -p RefuseManualStart
systemctl --user show 'wayland-session@hyprland.desktop.target' -p BindsTo -p After -p Requires
systemctl --user show 'wayland-wm@hyprland.desktop.service' -p MainPID -p ActiveState -p EnvironmentFiles
systemctl --user status dbus.socket / dbus.service / 'wayland-wm@hyprland.desktop.service'
cat /usr/lib/systemd/user/{dbus.socket,graphical-session.target,wayland-session@.target,wayland-session-waitenv.service,wayland-wm@.service,wayland-wm-env@.service,hyprpaper.service,waybar.service,dunst.service,at-spi-dbus-bus.service}
tr '\0' '\n' < /proc/<MainPID>/environ   # at-spi-dbus-bus.service, xdg-desktop-portal-gtk.service
head -1 /run/user/1000/uwsm/env_pre          # manager env before import
cat /usr/share/uwsm/plugins/hyprland.sh      # UWSM_WAIT_VARNAMES/UWSM_FINALIZE_VARNAMES
rg 'SetEnvironment|prepare-env|finalize' /usr/share/uwsm/modules/uwsm/{main.py,dbus.py}
man uwsm | col -b
cat /usr/share/wayland-sessions/hyprland-uwsm.desktop
```

---

## Bottom line

A repo-provisioned `systemd --user` unit **can** cleanly reach the per-user session bus (`unix:path=/run/user/1000/bus`, set by `dbus.socket`) and the Hyprland env (`WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `HYPRLAND_INSTANCE_SIGNATURE`), with uwsm performing the import. The unit must use `PartOf=graphical-session.target`, `After=graphical-session.target`, and `WantedBy=graphical-session.target` (optionally `Requires=` + `ConditionEnvironment=WAYLAND_DISPLAY`), and provisioning must enable it via symlink if no live session is guaranteed. The only structural risk is the enable-on-a-dead-bus path, already noted in the repo's memlog.
