# Tasks: refactor-ags-settings-panel-dbus

Workstreams map 1:1 to orchestrated agents (A1–A6). Do not start a workstream
before its dependencies are merged into the working tree.

## 1. NetworkManager D-Bus service layer (A1 — depends on nothing) — DONE

- [x] 1.1 Create `settings-panel/services/nm-client.ts`: async `call`,
  `getAll`, `getProperty`, `subscribe`, `watchProperties`, `variantToJs`,
  typed `NMBusError`; no `call_sync` outside the one startup bus connect
- [x] 1.2 Create `settings-panel/services/wifi-service.ts` device discovery via
  `GetDevices`/`Device.DeviceType == 2`, cached path, re-resolve on
  `DeviceAdded`/`DeviceRemoved`
- [x] 1.3 AP model from `Device.Wireless.GetAccessPoints` + AP signals; SSID
  bytes → string, strength, secured flags; refresh debounced on AP signals
- [x] 1.4 Scan via `RequestScan`, ignore throttled rejections; `startScanning`/
  `stopScanning` with ~6s cadence paused while connecting
- [x] 1.5 Connected AP from device `ActiveAccessPoint`; saved-network lookup via
  `NM.Settings.ListConnections`/`GetSettings`, cached and invalidated on
  connection add/remove
- [x] 1.6 Activation: `ActivateConnection` (saved, specific AP) and
  `AddAndActivateConnection` (new, PSK settings); switch = `DeactivateConnection`
  → wait `State == 30` → activate target
- [x] 1.7 Connect state machine `idle/preparing/needAuth/activating/failed` with
  generation-counter cancellation (re-target), `StateChanged`-driven terminal
  transitions, and one bounded self-cancelling watchdog; expose `connectState`,
  `wifiNetworks`, `wifiEnabled`
- [x] 1.8 Handle `SecretsRequired` → `needAuth`; map NM failure reason codes to
  human-readable messages

## 2. Wi-Fi UI rework + workaround deletion (A2 — depends on A1) — DONE

- [x] 2.1 Rewrite `controls/wifi.tsx` as a thin view over `wifi-service`:
  `WifiTile`, `WifiRow`, `WifiPasswordPrompt`, `WifiToggle`; spinner/states from
  `connectState`
- [x] 2.2 Row semantics: spinner appears on first frame after press; Connect
  sensitive during `idle` or when re-targeting a different SSID; no mass-disable
- [x] 2.3 `views/WifiView.tsx`: `startScanning`/`stopScanning` on view
  open/close; prompt on `needAuth` or explicit secured+unsaved selection
- [x] 2.4 Delete the `iw` scan parser, `wifiInterface`/`getAll` sync helpers,
  all `nmcli` orchestration, `savedWifiConnection`, `scheduleListRefresh`, the
  40s watchdog, `run`, message timers, and `resetWifiConnecting`
- [x] 2.5 Grep the panel tree: `execAsync|nmcli|iw |call_sync` returns nothing in
  the Wi-Fi path

## 3. Provisioning purge (A3 — independent, runs in parallel) — DONE

- [x] 3.1 Remove `iw` from `dotfiles/provisioning/packages.yaml`
- [x] 3.2 Remove `iw` from `src/provisioning/ansible/group_vars/arch.yml` and
  `debian-family.yml`
- [x] 3.3 Remove the getcap check + setcap grant from
  `src/provisioning/ansible/roles/packages/tasks/main.yml`
- [x] 3.4 Remove the iw/capability verify gate from
  `src/provisioning/ansible/roles/verify/tasks/main.yml` and iw vars from
  `verify/vars/main.yml`
- [x] 3.5 Update the three unit tests referencing `iw`
  (`test_verify_role.py`, `test_yaml_manifest_reader.py`,
  `test_ansible_scaffold.py`)
- [x] 3.6 Annotate tasks 8.21–8.23 of `add-ags-settings-panel/tasks.md` as
  superseded by this change

## 4. Bluetooth service + UI (A4 — depends on A1, then A2 patterns) — DONE

- [x] 4.1 Create `settings-panel/services/bluetooth-service.ts`: adapter
  discovery, power toggle, discovery start/stop + filter, device list from
  `GetManagedObjects` + signals, pair/connect/disconnect/unpair, per-device busy
  state
- [x] 4.2 Re-wire `settings-panel/bluetooth-agent.ts` to the shared bus plumbing;
  no behavior change to the agent contract
- [x] 4.3 Rewrite `controls/bluetooth.tsx` + `views/BluetoothView.tsx` as thin
  views; delete `bluetoothctl`/`rfkill` subprocess code and duplicated
  `run`/timeout helpers
- [x] 4.4 Grep confirms no subprocess calls remain in the Bluetooth path

## 5. Cleanup sweep (A5 — depends on A2 + A4) — DONE

- [x] 5.1 Remove `style.css` classes orphaned by the deleted workaround markup
  (removed dead `.settings-tile-main`; all other 40 classes still referenced)
- [x] 5.2 Confirm `SettingsPanel.tsx`/`app.tsx` wiring needs no change beyond
  imports; reconcile any accessor names
- [x] 5.3 Full-panel grep for workaround leftovers and dead exports
- [x] 5.4 Spec-vs-code audit: every MODIFIED scenario has a corresponding
  implementation path (no GAPs)

## 6. Verification (A6 + owner)

- [x] 6.1 `src/provisioning/.venv` pytest suite green after the iw purge
  (624 passed)
- [x] 6.2 Runtime smoke (owner): panel opens; Wi-Fi list populates from NM
- [ ] 6.3 Runtime smoke: connect to a new secured network via the prompt —
  spinner visible immediately, password prompt behaves, success reflected
- [x] 6.4 Runtime smoke: switch between two known networks back-to-back —
  spinner on press, completes fast, no dead buttons, re-target works (owner
  confirmed after 6.12/6.13)
- [x] 6.5 Runtime smoke: vanished AP drops promptly (owner confirmed after 6.14);
  wifi off/on
- [ ] 6.6 Runtime smoke: Bluetooth discovery/pair/connect/audio route; busy
  spinner on actions
- [x] 6.7 Grep gate: panel tree free of
  `execAsync|nmcli|iw |bluetoothctl|rfkill|call_sync` (Wi-Fi/Bluetooth paths)
- [x] 6.8 Bundle gate: `ags bundle app.tsx` exits 0 after every workstream
- [x] 6.9 Smoke-fix: switching networks briefly blanked the list to "No networks
  found" because NetworkManager reports an empty access-point list while the
  device deactivates/re-associates. `wifi-service.ts` now keeps the last good AP
  list on a transient empty read (never blanks while a connect/switch is in
  flight; accepts an empty read only once sustained), and `resolveDevice` no
  longer tears down the device on a transient device-property read failure.
  Re-verify in 6.4
- [x] 6.10 Smoke-fix: a saved network was "locked" (row disabled, password
  prompt stuck) because NetworkManager flashes `NEED_AUTH (60)` for a saved
  profile that has stored secrets, then immediately continues — and the state
  machine treated any 60 as terminal and then ignored the later ACTIVATED.
  `handleStateChanged` now defers the prompt (`NEED_AUTH_GRACE_MS`, only if the
  device is still in need-auth), resumes `activating` on PREPARE/CONFIG/
  IP_CONFIG/DEACTIVATING, clears to idle on ACTIVATED from any in-flight phase,
  and prompts on FAILED reason `NO_SECRETS`. `prepareSwitch` now uses a bounded
  wait (state 30/20/120 or 8s) instead of requiring exactly state 30, so a
  switch cannot stall until the watchdog. Re-verify in 6.4
- [x] 6.11 Deploy the 6.9/6.10 fix and relaunch the bar with `AGS_WIFI_DEBUG=1`
  tracing to `~/.local/state/ags/bar-debug.log` (opt-in; no output unless the
  env var is set).
- [x] 6.12 Smoke-fix: the connected network was resolved from the device's
  `ActiveAccessPoint`, and the fallback compared the active-connection path
  (`/ActiveConnection/N`) against `savedWifi` settings paths (`/Settings/N`) —
  which never matched. A stale AP path therefore reported the *previous*
  network, so the target row was marked "Connected" and its action did nothing.
  `wifi-service.ts` now resolves the active connection's own `Connection`
  (settings) and `SpecificObject` (AP) properties, re-resolves on change and on
  ACTIVATED, and recomputes the list.
- [x] 6.13 Smoke-fix: the Wi-Fi row's only hit target was the small `Connect`
  pill, so presses on the name/signal area did nothing ("works sometimes").
  The whole row is now the action (the proven `GestureClick` pattern from
  `CapabilityTile`); the trailing affordance is non-interactive. `act()` reads
  the live connected accessor instead of the stale row prop.
- [x] 6.14 Smoke-fix: a switched-off hotspot lingered ~30s and could be
  "connected" to. Two causes: NetworkManager keeps vanished APs in its cache,
  and a requested activation marked the network connected before the handshake.
  APs now carry `LastSeen` and are dropped when they trail the newest by
  `STALE_AP_SECONDS` (the associated AP is always kept), and
  `currentConnectedSsid()` returns null unless the device state is ACTIVATED,
  so the Connected badge can't light up early.

## 7. Provisioning completion (A7) — DONE

- [x] 7.1 Deploy the settings-panel services dir + three D-Bus service files:
  `compositor_configs_config_dirs` gains `ags/settings-panel/services`, and
  `compositor_configs_skeleton_files` gains `nm-client.ts`, `wifi-service.ts`,
  and `bluetooth-service.ts` entries (copy does not create dest parents).
- [x] 7.2 Extend the verify gate: the three services added to
  `verify_compositor_skeleton_files` so a provision that omits them fails
  instead of shipping a panel whose controls crash on import.
- [x] 7.3 Purge the stale AstalBluetooth dependency: removed the manifest entry
  (`astal-bluetooth`) + its `libastal-bluetooth-git` AUR package, the
  `astal-bluetooth` group_vars mappings, and the binding from
  `verify_astal_binding_packages` (renamed `verify_astal_wp_binding_packages`,
  AstalWp only). BlueZ daemon (`bluez`/`bluez-utils`, `bluetooth.service`,
  rfkill soft-block clearing) and PipeWire bluez5 audio all stay.
- [x] 7.4 Tests green: `src/provisioning` unit suite 624 passed (compositor
  skeleton count 44 → 47; verify fixture carries the services; AstalBluetooth
  references replaced consistently).
- [x] 7.5 Bundle gate still exits 0: `ags bundle app.tsx --gtk 4`.

