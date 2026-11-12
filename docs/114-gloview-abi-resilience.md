# GloView ABI resilience across Hyprland upgrades

- **Status:** proposed — investigation/design only
- **Date:** 2026-11-12
- **Host probe:** Hyprland `0.57.2-1`, `gloview-git 0.3.0.r34.67857e6-1`,
  `/usr/lib/gloview.so` BuildID `fec83e2e7901438e3c44eeee31d2e574734fa183`
- **Scope:** activation/detection/remediation design. No code, live config,
  package install, sudo change or tag in this document.

## 1. Problem statement

GloView is a Hyprland plugin (`/usr/lib/gloview.so`) supplied by the
`gloview-git` AUR package. A Hyprland plugin is loaded into the compositor
process and resolves Hyprland's internal C++ symbols at `dlopen` time. The
plugin and the **running Hyprland binary** must therefore be built from the
same headers/commit. After a Hyprland upgrade, the previously built `.so`
fails with `undefined symbol: …` and the compositor continues without
gestures/overview. The failure is currently easy to miss and remediation is a
manual `yay` rebuild plus relog.

## 2. Current flow and why it fails silently

Flow on this host:

1. `dotfiles-assets/configs/hypr/autostart.lua:48` calls
   `$HOME/.local/bin/gloview-activate` from `hl.on("hyprland.start", …)`.
2. `gloview-activate` (source of truth:
   `dotfiles-v3/dotfiles/provisioning/scripts/gloview-activate:1-70`, deployed
   by `dotfiles-provision/ansible/roles/cli_tools/tasks/main.yml:77-82`):
   waits up to 60 s for Hyprland IPC, checks `hyprctl plugin list`, loads
   `/usr/lib/gloview.so`, reloads config so `gloview.lua`'s pcall-guarded binds
   register, verifies the plugin appears in `hyprctl plugin list`, and touches
   `~/.local/state/dotfiles/gloview-active`.
3. `dotfiles-assets/configs/hypr/gloview.lua:3-5` guards the config block and
   gestures on `pcall(function() return hl.plugin.gloview.toggle end)`;
   `input.lua:16-30` and `keybindings.lua:8-12` are **not** guarded and call
   `hyprctl gloviewnext|gloviewprev|gloview`.

Silent-failure chain (evidence in §3):

- **`hyprctl plugin load` is not a reliable success oracle.** Observed on this
  host: `hyprctl plugin load /nonexistent.so` prints
  `Plugin /nonexistent.so could not be loaded: …` and **exits 0**. The script's
  `if ! hyprctl plugin load "$plugin_so"` at line 53 therefore never fires on a
  compositor-reported failure; the generic final check at line 63 is the only
  detector.
- **The useful error is discarded.** The load call redirects both streams to
  `/dev/null` (line 53), so the exact `undefined symbol` / path / loader error
  never reaches the journal or the user. The notification is generic.
- **Success is inferred from a text grep.** `grep -qi gloview` can match a
  description or another plugin; it does not prove the expected artifact
  loaded.
- **Failure leaves a stale green marker.** `gloview-active` is only touched on
  success and never removed. A previous session's marker survives, so any
  consumer treating it as health is wrong.
- **No failure state in systemd/journal.** This is a one-shot `hl.exec_cmd`
  with no unit. A non-zero exit is not surfaced in `systemctl --user --failed`,
  and stderr goes to the Hyprland launch environment, not a durable log.
- **Notification timing.** `notify-send` is best-effort (`|| true`). If it runs
  before the notification daemon owns `org.freedesktop.Notifications`, the
  critical notice is lost. The activation also intentionally cannot rebuild
  (no sudo from a login task), so the user gets no durable remediation path.
- **Unconditional binds become dead.** When the plugin is absent,
  `gloview.lua` disables itself, but `SUPER+TAB` and three-finger left/right
  still invoke `hyprctl gloview…`; Hyprland rejects the unknown dispatcher.
  The user sees "gestures stopped working" with no single place explaining why.

### Why it works today

The host was rebuilt after the last Hyprland upgrade:
`gloview-git` Build Date `2026-11-11 10:32:40`, Hyprland install date
`2026-11-10 19:34:36`, and `hyprctl plugin list -j` currently reports
`GloView / 0.3.0`. The user-reported `0.3.0.r28` is stale; the installed
package is `r34.67857e6` (upstream commit `67857e6`, *Port to Hyprland 0.57*).
This confirms the failure is rebuild-timing, not a permanent setup error.

## 3. Read-only host evidence (2026-11-12)

| Probe | Observed |
| --- | --- |
| `pacman -Q hyprland gloview-git` | `hyprland 0.57.2-1`; `gloview-git 0.3.0.r34.67857e6-1` |
| `hyprctl version -j` | `.version=0.57.2`, `.abiHash=11cbc6c5…_aq_0.16_hu_0.14_hg_0.6_hc_0.1_hlg_0.6` |
| `hyprctl plugin list -j` | `[{"name":"GloView","author":"Vergil","version":"0.3.0",…}]` |
| `pacman -Qi gloview-git` | Build Date `2026-11-11 10:32:40`; Packager `Unknown Packager`; depends `hyprland` (unversioned) |
| `expac -Q '%n\|%v\|%b\|%i' hyprland gloview-git` | Hyprland build `Mon Nov 9 06:34:30 2026`, install `Tue Nov 10 19:34:36 2026`; gloview build `Wed Nov 11 10:32:40 2026` |
| `readelf -n /usr/lib/gloview.so` | BuildID `fec83e2e7901438e3c44eeee31d2e574734fa183`; no Hyprland commit embedded |
| `strings /usr/lib/gloview.so \| grep -E '0\.[0-9]+\.[0-9]+\|abi'` | no Hyprland ABI/version string; only plugin-API strings |
| `nm -D /usr/lib/gloview.so` | exports `pluginAPIVersion`, `pluginInit`, `pluginExit` |
| `/usr/include/hyprland/src/plugins/PluginAPI.hpp:21` | `HYPRLAND_API_VERSION "0.2"` — API version, **not** a build ABI |
| `ldd -r /usr/lib/gloview.so` | reports undefined `IPassElement`, `CConfigValueBase`, `CWindowMetadata`, … even on the **healthy** build (they resolve from the Hyprland executable) |
| `hyprctl plugin load /nonexistent.so; echo $?` | compositor error printed, **exit 0** |
| `systemctl --user show-environment` | `HYPRLAND_INSTANCE_SIGNATURE` and `WAYLAND_DISPLAY` are present (uwsm imports them) |
| `gdbus … org.freedesktop.Notifications.GetCapabilities` | `actions`, `body-markup`, `persistence` supported |
| `pacman -Ss hyprpm` | `extra/hyprpm 0.57.2-1` exists; **not installed** |
| `pacman -Ss hyprexpo` / `hyprspace` | no installed native overview; alternatives are plugins |
| `hyprctl plugin load` absence test | `HYPRLAND_INSTANCE_SIGNATURE` is available to the systemd user manager |

Key conclusion: **`ldd -r`, ELF BuildID and package version cannot prove ABI
compatibility.** The only authoritative test is asking the running compositor
to load the `.so` and then verifying the loaded-plugin list. Everything else is
a heuristic for warning earlier.

Useful machine-readable primitives:

```bash
hyprctl version -j | jq -r '.version, .abiHash'
hyprctl plugin list -j | jq -r '.[] | select(.name=="GloView") | .version'
expac -Q '%n|%v|%b|%i' hyprland gloview-git
readelf -n /usr/lib/gloview.so | awk '/Build ID/ {print $3}'
```

## 4. Options considered

| Option | Security / sudo | Detects | Remediation | Verdict |
| --- | --- | --- | --- | --- |
| **A. Keep one-shot autostart, improve script** | none | load result + ABI stamp | notify + exact log | **Adopt as P0** |
| **B. systemd user oneshot service** | none (user scope) | same as A, plus unit failure/journal | notify + one-click action | **Adopt**; env is available under uwsm |
| **C. systemd user timer (periodic ABI/package check)** | none | package/build-date drift before relog | notify only | Optional P1; no need by default |
| **D. pacman `PostTransaction` hook** | root; runs in upgrade transaction | package upgrade happened | write a marker / root-run helper | **Reject for rebuild**; at most a marker |
| **E. pin/lock Hyprland (`IgnorePkg`)** | root | prevents the upgrade | none | Last-resort; whole stack must be pinned; not recommended |
| **F. auto `yay -S gloview-git` from login/service** | needs sudo/polkit; AUR code | n/a | auto-install | **Unsafe; reject** |
| **G. hyprpm** | user; needs live IPC/headers | builds against current headers | `hyprpm update` + reload | Not applicable today; gloview has no `hyprpm.toml`, and hyprpm is not installed |
| **H. native gestures/overview fallback** | none | n/a | native gesture, no overview | Partial fallback only; Hyprland 0.57 has no built-in overview |

### Why automatic `yay -S gloview-git` is not acceptable

- The AUR build must run as the **login user**, not root; system/login
  services run without an interactive TTY and cannot answer `sudo`/polkit
  prompts securely.
- It executes an **untrusted PKGBUILD** and network fetch unattended. That is a
  supply-chain and availability risk, especially at login.
- A failed build/cache write can leave the machine without `/usr/lib/gloview.so`;
  there is no rollback of the live session.
- Upstream HEAD may contain unrelated changes beyond the ABI fix; unattended
  rebuild silently changes behavior.
- The rebuild is not hot-safe: the old `.so` is mapped into the compositor.
  Reloading in place is racy; a relog is the safe completion step.
- `yay -Syu --devel` only rebuilds VCS packages when **upstream** HEAD moves.
  A Hyprland upgrade alone does not move gloview's HEAD, so `--devel` alone
  does not fix this. `yay -S gloview-git` can reuse the cached package because
  `pkgver` is unchanged (`r34`). Use `yay -S --rebuild gloview-git` when a
  rebuild is actually required.

### Why `hyprpm` is not the answer here

- `hyprpm` is now a separate package (`extra/hyprpm 0.57.2-1`) and is not
  installed. The gloview AUR PKGBUILD installs a plain `.so`; the upstream
  checkout in the yay cache has **no `hyprpm.toml`**.
- `hyprpm` still must rebuild after each Hyprland ABI change and still needs a
  live IPC session and matching headers. It would replace one package manager
  with another, not remove the rebuild requirement.
- Revisit only if upstream publishes a hyprpm repo; the AUR path is simpler for
  this machine.

### Why pinning is not recommended

`IgnorePkg = hyprland` in `/etc/pacman.conf` leaves the compositor stale and
does not protect the rest of the stack: `aquamarine`, `hyprutils`, `hyprlang`,
`hyprcursor` and `hyprgraphics` can still upgrade, and Hyprland itself links
against them. A partial upgrade can break Hyprland without GloView. If pinning
is ever chosen, pin the whole Hyprland stack and document an explicit
"upgrade + rebuild + relog" ritual. Default recommendation: do not pin.

## 5. Recommended design

### 5.1 Detection (authoritative + early warning)

Authoritative, every session:

1. Read `hyprctl version -j` → `version`, `abiHash`.
2. Read the stored stamp (if any) at
   `~/.local/state/dotfiles/gloview/status.json`.
3. If the stamp exists and `abiHash` differs, record `abi_changed` but still
   attempt the load (a rebuild may not be strictly needed).
4. Load only if not already present:
   `out=$(hyprctl plugin load /usr/lib/gloview.so 2>&1)`; **do not trust the
   exit status**.
5. Verify with `hyprctl plugin list -j` and match `name == "GloView"`, polling
   briefly because load is asynchronous.
6. On success: atomically write the new stamp and remove any stale
   `gloview-active` marker.
7. On failure: write `status.json` with the captured `out`, the current
   `abiHash`, package versions/build dates, `.so` BuildID/mtime, and a UTC
   timestamp; remove `gloview-active`; notify once; exit non-zero.

Early warning heuristics (never used to declare success/failure):

- **ABI stamp difference:** the stored `abiHash` records the ABI under which the
  plugin last loaded. A difference means "the compositor changed; expect a
  rebuild", not "the plugin is broken".
- **Package chronology:** `gloview-git` `BUILDDATE` < `hyprland` `INSTALLDATE`
  means the plugin predates the installed Hyprland package. Read the integer
  epochs from `/var/lib/pacman/local/*/desc` or `expac`, not localized
  `pacman -Qi` text. This catches upgrades even before the next relog.
- **Running vs installed Hyprland:** compare `hyprctl version -j .version` with
  `pacman -Q hyprland`; a mismatch means "upgraded but not relogged". A rebuild
  now targets the installed headers and becomes loadable only after relog.

Do **not** use `ldd -r`, ELF BuildID alone, `pacman -Q` version equality, or
grep on `plugin list` as ABI proof. `ldd -r` is guaranteed to show Hyprland
symbols on a healthy build because they live in the executable, not a library.

### 5.2 Activation surface: systemd user oneshot

Move activation ownership from the fire-and-forget autostart line to a user
unit so failures are observable and can wait for the notification daemon:

`~/.config/systemd/user/dotfiles-gloview.service`

```ini
[Unit]
Description=Load the GloView Hyprland plugin and verify ABI
Requires=dbus.socket
After=dbus.socket graphical-session.target dotfiles-ags-notifications.service
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=%h/.local/bin/gloview-activate
TimeoutStartSec=90
# No sudo, no package manager, no network. Detection and notification only.

[Install]
WantedBy=graphical-session.target
```

- `HYPRLAND_INSTANCE_SIGNATURE` is already in the systemd user environment on
  this host (uwsm); verified with `systemctl --user show-environment`. Keep the
  script's own IPC wait as a fallback.
- Ordering after `dotfiles-ags-notifications.service` ensures `notify-send`
  has a daemon; capabilities include `actions` and `persistence`.
- Remove the `gloview-activate` line from `autostart.lua` (or make it a no-op
  comment) so there is exactly one owner, same pattern as the AGS always-on
  units. Keep `hyprctl reload` in the script for bind registration.
- Prefer `Type=oneshot` + `RemainAfterExit=yes`; a failed load leaves the unit
  in `failed`, visible via `systemctl --user --failed` and the journal.

Optional P1 timer (`dotfiles-gloview-doctor.timer`) every 6 h: run the
package-chronology/running-vs-installed checks only, and notify if a rebuild is
likely. Do not load/reload anything from the timer. Skip when
`HYPRLAND_INSTANCE_SIGNATURE` is absent. This is useful only if the user wants
a warning before relog; the session-start service is the primary detector.

### 5.3 One-click remediation (no privilege escalation)

`gloview-activate` on failure sends one critical notification with the exact
command and, because the daemon supports actions, an action that launches a
terminal:

```text
GloView unavailable
Hyprland 0.57.2 ABI changed; /usr/lib/gloview.so failed to load.
Rebuild: yay -S --rebuild gloview-git
Then: log out and back in (or restart the Hyprland session).
[Rebuild now] [Show log]
```

`[Rebuild now]` must open an **interactive terminal** running the provisioned
`gloview-rebuild` helper, not execute `yay` from the service:

```bash
#!/usr/bin/env bash
# gloview-rebuild — user-run, interactive; never called from autostart/systemd.
set -euo pipefail
command -v yay >/dev/null || { echo "yay not found" >&2; exit 1; }
echo "Hyprland running: $(hyprctl version -j | jq -r .version)"
echo "Hyprland installed: $(pacman -Q hyprland)"
echo "Rebuilding gloview-git against installed headers…"
yay -S --rebuild gloview-git
echo
echo "Rebuild complete. Log out and back in before using GloView."
```

- `yay` runs as the user and performs its own sudo/polkit prompt; never wrap
  it in `sudo`, never add a NOPASSWD rule for `yay`/`pacman`, never use
  `--noconfirm` for the AUR build.
- If the notification daemon does not honour actions (future change), fall
  back to a `.desktop` entry or rofi entry that opens the same terminal. The
  notification body must always include the literal command so it works even
  with no action support.
- After a successful rebuild, the safe completion is relog (or a full Hyprland
  restart). Do not rewrite/replace `/usr/lib/gloview.so` in place while it is
  mapped in the running compositor.

### 5.4 State and logging

Use `~/.local/state/dotfiles/gloview/` (0700), not a single touch file:

```json
{
  "schema": 1,
  "loadedAt": "2026-11-12T13:05:00Z",
  "ok": true,
  "hyprland": {
    "version": "0.57.2",
    "abiHash": "11cbc6c5…_aq_0.16_hu_0.14_hg_0.6_hc_0.1_hlg_0.6"
  },
  "gloview": {
    "package": "0.3.0.r34.67857e6-1",
    "buildDate": 1794411160,
    "installDate": 1794411648,
    "soBuildId": "fec83e2e7901438e3c44eeee31d2e574734fa183",
    "soMtime": 1794411160
  },
  "lastError": null
}
```

- Atomic write: write `status.json.tmp`, `fsync`, `mv`.
- Append the captured loader output to
  `~/.local/state/dotfiles/gloview/activate.log` with a size cap/rotation.
- Remove `gloview-active` on every failure; keep it only as a best-effort
  legacy marker while consumers migrate to `status.json`.
- Never put the full environment or secrets in the log.

### 5.5 Fallback when the plugin is missing/stale

Hyprland 0.57 has native gesture bindings but **no built-in overview**.
`hyprexpo`/`hyprspace` are also plugins with the same ABI constraint, so there
is no dependency-free native replacement.

Recommended fallback contract:

- `gloview.lua` keeps its pcall guard (config + up/down gestures disappear).
- Move/guard the `SUPER+TAB` bind (`keybindings.lua:8-12`) behind the same
  `gloview_loaded` flag, and guard the three-finger left/right binds
  (`input.lua:16-30`). When the plugin is absent, either leave them unbound or
  map left/right to native workspace switching. Do not leave dispatchers that
  always fail.
- The user-visible state is "overview unavailable; native workspace gestures
  still work", not a dead compositor. Hyprland itself must continue normally.

## 6. Exact next-step commands

Diagnose now (read-only):

```bash
hyprctl version -j | jq -r '.version, .abiHash'
hyprctl plugin list -j | jq -r '.[] | [.name,.version] | @tsv'
expac -Q '%n|%v|%b|%i' hyprland gloview-git
readelf -n /usr/lib/gloview.so | awk '/Build ID/ {print $3}'
systemctl --user status dotfiles-gloview.service   # after the unit exists
journalctl --user -u dotfiles-gloview.service -b --no-pager
```

Remediate manually (when GloView is actually stale):

```bash
yay -S --rebuild gloview-git     # user-run, interactive; do not sudo
# then log out and back in; verify after relog:
hyprctl plugin list -j | jq -r '.[] | select(.name=="GloView") | .version'
```

Do **not** use `yay -Syu --devel` as the only fix; it does not rebuild gloview
when only Hyprland changed.

## 7. Acceptance criteria

- **A-1** On a healthy host, activation exits 0, `hyprctl plugin list -j`
  contains `GloView`, `status.json` records the current `abiHash`, and no
  notification is sent.
- **A-2** On an ABI mismatch (unit test with a fake `hyprctl`/stale fixture),
  activation exits non-zero, removes `gloview-active`, writes `ok:false` and
  the exact loader error, sends exactly one critical notification, and logs the
  captured output to `activate.log`.
- **A-3** The script never treats `hyprctl plugin load` exit status as success;
  it always verifies the JSON plugin list. A test where the load command exits
  0 but prints a failure must fail the activation.
- **A-4** A changed `abiHash` is reported as `abi_changed`; if the plugin still
  loads, the stamp is updated and no warning is emitted.
- **A-5** The package-chronology check warns when gloview `BUILDDATE` is older
  than Hyprland `INSTALLDATE`, and not when it is equal/newer.
- **A-6** Activation runs as a systemd user oneshot, not from `autostart.lua`;
  `systemctl --user --failed` shows it on failure and the journal contains the
  loader output.
- **A-7** No activation/service path invokes `sudo`, `yay`, `pacman`, or the
  network. `rg -n 'sudo|yay|pacman' gloview-activate` returns only comments.
- **A-8** The failure notification contains the exact command
  `yay -S --rebuild gloview-git` and the relog instruction; the action opens an
  interactive terminal and never runs the rebuild in the service.
- **A-9** When the plugin is absent, `SUPER+TAB` and GloView gestures are
  guarded/fallback-native; Hyprland remains usable and no unknown dispatcher
  errors are generated.
- **A-10** Activation is idempotent within a session (lock + list check), and a
  missing Hyprland IPC does not block login.

## 8. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Loading a badly mismatched `.so` can crash the compositor | Keep load at session start (current behavior); never auto-load after an upgrade in a live session; relog is the safe boundary. |
| `hyprctl` load/list is asynchronous; immediate verify races | Poll `plugin list -j` for a bounded interval (e.g. 5 s) before declaring failure. |
| Notification daemon not ready or actions unsupported | Order after `dotfiles-ags-notifications.service`; always put the literal command in the body; fall back to a desktop/rofi entry. |
| Rebuild succeeds but upstream drift breaks behavior | Interactive build with PKGBUILD diff; rebuild only on explicit user action; keep the previous package in the yay cache for rollback. |
| Hyprland upgraded, session not relogged; rebuild targets new headers but old compositor runs | Status reports running-vs-installed version mismatch; instruct "rebuild, then relog"; do not attempt to load the new `.so` into the old running compositor. |
| Notification spam | One notification per activation failure; state/timestamp dedupe; timer (if added) only on transition. |
| ABI hash changes without a needed rebuild | Still attempt load; success updates the stamp and clears the warning. |
| No plugin metadata to compare before loading | Accept load-test as authoritative; optionally upstream a `GIT_COMMIT_HASH`/ABI string in `pluginAPIVersion` or plugin version for pre-load detection. |

## 9. Optional upstream improvement

GloView's `.so` currently exposes only `pluginAPIVersion` (Hyprland API `0.2`)
and no build commit. If upstream embeds `GIT_COMMIT_HASH` (from Hyprland's
`version.h`) in the plugin version string or a new exported symbol, the
activator could compare the plugin's build commit to the running compositor's
commit **before** attempting a load. This is not required for the design above
(the success stamp + load test is authoritative), but it would make diagnosis
and pre-relog warnings exact. File upstream only if the manual workflow proves
insufficient.

## 10. Decision summary

Adopt **A + B**: a systemd user oneshot owns activation, verifies the load via
`hyprctl plugin list -j`, records an ABI/version stamp and exact error, removes
the stale success marker on failure, and notifies with a one-click interactive
rebuild helper. Do not auto-rebuild, do not add sudo, do not use a root pacman
hook to run `yay`, and do not pin Hyprland by default. Keep the AUR package as
the install source; revisit `hyprpm` only if upstream adds a `hyprpm.toml`.
