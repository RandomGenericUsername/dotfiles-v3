## Why

The settings panel (`openspec/changes/add-ags-settings-panel`) shipped with an
acceptable UI but a Wi-Fi/Bluetooth control path that accumulated eight
consecutive workaround commits. The owner reports two concrete failures and
correctly diagnoses the code as workaround-driven rather than architected:

1. **No feedback while connecting.** `controls/wifi.tsx` sets the row spinner
   (`connectingSsid`) only *after* `await savedWifiConnection()` — which spawns
   `nmcli connection show` plus one serial `nmcli` call per saved profile
   (`wifi.tsx:283-319`). A click produces seconds of total silence before any
   feedback, so connecting feels like nothing is happening.

2. **~40s lockout when switching networks sequentially.** All other Connect
   buttons are disabled while a connect is in flight (`wifi.tsx:479`), and a
   click during that window returns *silently* (`wifi.tsx:348`). The 40s
   watchdog (`wifi.tsx:359`) is the only thing that ever un-sticks the UI. The
   root cause is that `run()`'s timeout (`wifi.tsx:254-263`) rejects the promise
   but **cannot kill the underlying `nmcli` process** (`execAsync` is
   uncancellable), so a hung `connection up` (AP not found after a switch) plus
   its `device wifi connect` fallback leave the device contended for ~40s.

The implementation also violates the runtime architecture:

- Blocking `Gio` `call_sync` runs on the GTK main loop (`wifi.tsx:69-96`).
- Three competing sources of truth: AstalNetwork bindings, an `iw scan` list,
  and `nmcli` profiles.
- Hand-rolled GLib timer juggling (message timer, watchdog, scheduled refreshes)
  spread across a 560-line file that also owns all UI.
- `bluetooth.tsx` duplicates the same `run`/timeout/spinner patterns and shells
  out to `bluetoothctl`/`rfkill`.

A workaround-only `iw` dependency was added to provisioning (package + a
`setcap CAP_NET_ADMIN` grant) solely to make the scan list "fresh". With a
NetworkManager D-Bus implementation that dependency is dead weight.

## What Changes

### NetworkManager D-Bus service layer (new)

Replace every subprocess and every blocking call with one async service layer
that treats **NetworkManager D-Bus as the single source of truth**:

```
dotfiles/config/ags/settings-panel/services/
├── nm-client.ts          # async Gio system-bus wrapper (call, signals, property watch)
├── wifi-service.ts       # device + AP model, scan, activation, connect state machine
└── bluetooth-service.ts  # BlueZ Adapter1/Device1, agent re-wire
```

- **Access points** — `org.freedesktop.NetworkManager.Device.Wireless.GetAccessPoints`
  plus the `AccessPoint` / `LastScan` signals; scan via `RequestScan`. No `iw`,
  no `nmcli` list parsing, no `last-seen` filtering heuristics.
- **State** — the device `State` property and `StateChanged` signal
  (prepare/config/need-auth/ip-config/activated/deactivating + failure reason).
  This is what produces truthful "Connecting…" feedback and detects
  `NEED_AUTH`, replacing all timers.
- **Activation** — `NM.ActivateConnection` for saved profiles,
  `NM.AddAndActivateConnection` for new networks (PSK supplied inline from the
  password prompt).
- **Connect state machine** — one accessor
  `idle → preparing → needAuth → activating → activated → failed`, with
  *switchable one-flight* semantics: switching networks deactivates the current
  connection explicitly, waits for the disconnected state, then activates the
  target; a new click re-targets the pending sequence instead of being dropped.
  No 40s watchdog — NetworkManager's own timeouts drive progress, with a single
  sane UI fallback.

### Thin Wi-Fi and Bluetooth UI

`controls/wifi.tsx`, `views/WifiView.tsx`, `controls/bluetooth.tsx`,
`views/BluetoothView.tsx` become pure views over the services. Deleted:
the `iw` scan parser, all `nmcli` orchestration, the saved-profile lookup,
the silent in-flight return, the 40s watchdog, `scheduleListRefresh`, the
message timer scaffolding, and `resetWifiConnecting`. The spinner and
"Connecting…" states are driven by the state machine and appear on the first
frame after a press. Bluetooth drops `bluetoothctl`/`rfkill` subprocess calls
for BlueZ D-Bus; the existing pairing agent (`bluetooth-agent.ts`) is re-wired
rather than replaced.

### Stale dependency purge (provisioning)

`iw` and its `CAP_NET_ADMIN`/`CAP_NET_RAW` grant were introduced only for the
workaround scan. Remove them end to end:

- `dotfiles/provisioning/packages.yaml`
- `src/provisioning/ansible/group_vars/arch.yml`, `debian-family.yml`
- `src/provisioning/ansible/roles/packages/tasks/main.yml` (getcap check +
  setcap grant)
- `src/provisioning/ansible/roles/verify/tasks/main.yml` (+ `verify/vars/main.yml`)
- the three unit tests referencing `iw`

`nmcli` remains (ships with NetworkManager; the bar and other tooling still use
it) but the settings panel no longer shells out to it.

## Capabilities

### Modified Capabilities

- **`ags-settings-panel`** — the Wi-Fi/Bluetooth connect contract is rewritten:
  instant acknowledgement on press, truthful state-driven progress,
  switchable in-flight connects, surfaced failure reasons, NEED_AUTH password
  prompt. The old "one connect at a time, all buttons disabled" and
  timer/watchdog behavior is removed.
- **`settings-panel-provisioning`** — the `iw` package and capability grant are
  removed from the provision and its verify gate; the gate asserts only
  NetworkManager/BlueZ-provisioned capabilities.

## Impact

- **New files**: `settings-panel/services/nm-client.ts`,
  `settings-panel/services/wifi-service.ts`,
  `settings-panel/services/bluetooth-service.ts`.
- **Rewritten**: `settings-panel/controls/{wifi,bluetooth}.tsx`,
  `settings-panel/views/{WifiView,BluetoothView}.tsx`.
- **Removed deps**: `iw` from `packages.yaml`, both group_vars, the packages
  role setcap tasks, the verify gate + vars, three unit-test references.
- **Tests**: provisioning unit suite (`src/provisioning/.venv`, pytest) must
  stay green after the `iw` removal.
- **Runtime**: async only; no subprocesses, no blocking bus calls, no new
  packages. AGS config has no TS toolchain, so correctness is verified by review
  and the runtime smoke matrix in `tasks.md`.
- **Supersedes**: tasks 8.17–8.23 of `add-ags-settings-panel` (the workaround
  chain); those entries are annotated as superseded.
