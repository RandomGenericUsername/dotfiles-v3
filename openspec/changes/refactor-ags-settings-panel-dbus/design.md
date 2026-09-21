# Design: refactor-ags-settings-panel-dbus

Reference: `openspec/changes/add-ags-settings-panel` (UI, placement, dismissal,
primitives — unchanged). This change replaces only the *control* path.

## 0. Invariants (non-negotiable)

1. **One source of truth.** Wi-Fi state comes from NetworkManager D-Bus;
   Bluetooth state comes from BlueZ D-Bus. No subprocess (`nmcli`, `iw`,
   `bluetoothctl`, `rfkill`), no AstalNetwork/AstalBluetooth control bindings
   for mutable state, no parallel caches.
2. **Never block the main loop.** No `call_sync` / `call_with_unix_fd_list_sync`
   in the service layer. All bus I/O is asynchronous (`Gio.DBusConnection.call`
   with a callback or `call_finish`). The existing synchronous `getAll()` /
   `wifiInterface()` helpers are deleted.
3. **Single connect state machine.** Exactly one connect attempt may be in
   flight; a new user intent re-targets it (cancel + deactivate + activate the
   new target). No click is ever dropped silently.
4. **Feedback is derived from state, not timers.** Spinners/„Connecting…“ are
   computed from the state machine and the NM device state; the only timer
   permitted is a bounded watchdog that exists solely to surface a failure and
   is cancelled on every terminal transition.
5. **Thin UI.** Files under `controls/` and `views/` contain GTK/AGS markup and
   accessor reads only. No bus calls, no command construction, no `execAsync`.

## 1. `services/nm-client.ts` — async bus plumbing

Minimal, dependency-free wrapper over `Gio.DBusConnection` (system bus),
mirroring the cache pattern already used by `icon-registry.ts` where sensible.

- `systemBus(): Gio.DBusConnection` — lazily `Gio.bus_get_sync` **once** at
  module init (a single sync connect at startup is acceptable; it is not per
  interaction). All later calls async.
- `call(dest, path, iface, method, params: GLib.Variant, timeoutMs?): Promise<GLib.Variant>`
  — promisified `connection.call(...)`; rejects with a typed `NMBusError`
  carrying the D-Bus error name (`org.freedesktop.NetworkManager.*`) and message.
- `getAll(path, iface): Promise<Record<string, unknown>>` — `GetAll` via async
  `call`.
- `getProperty(path, iface, name): Promise<GLib.Variant>`
- `subscribe(sender, path, iface, signal, cb): () => void` — wraps
  `connection.signal_subscribe`, returns an unsubscribe closure.
- `watchProperties(path, iface, cb): () => void` — subscribes to
  `org.freedesktop.DBus.Properties.PropertiesChanged` for `(path, iface)` and
  delivers the changed dict.
- `variantToJs(v: GLib.Variant): unknown` — `recursiveUnpack` helper.

Error taxonomy: `NMBusError` with `.name` used by the Wi-Fi service to detect
`NM_DEVICE_STATE_REASON_*`/`NoSecrets`/`SecretsRequired` where needed.

## 2. `services/wifi-service.ts`

### 2.1 Device discovery

- `NM = "org.freedesktop.NetworkManager"`, manager path
  `/org/freedesktop/NetworkManager`.
- On init: `GetDevices` → for each path `GetAll(path, Device)` → pick
  `DeviceType === NM_DEVICE_TYPE_WIFI (2)`. Cache the device object path and
  interface name. Re-run when the manager emits `DeviceAdded`/`DeviceRemoved`.
- Device state via `GetAll(device, Device)` initial read plus
  `watchProperties(device, Device)` for `State` and `ActiveConnection`.

### 2.2 Access points

- `GetAccessPoints` → array of AP object paths. Each AP read via `GetAll(ap,
  AccessPoint)` for `Ssid` (`ay` → bytes → UTF-8), `Strength` (0–100),
  `Flags`/`WpaFlags`/`RsnFlags` (secured = any nonzero), and `LastSeen`
  metadata if needed.
- Live updates: `watchProperties(device, Device.Wireless)` for `LastScan` and
  subscribe to `AccessPointAdded`/`AccessPointRemoved`; refresh the AP cache
  on AP signals (debounced ~250ms) and when `RequestScan` completes.
- **Scan**: `RequestScan` on `Device.Wireless` (`a{sv}` empty options). NM
  throttles; a rejected scan is ignored (the cache still updates). While the
  Wi-Fi view is open, request a scan at a modest cadence (see 2.5) but **pause
  scanning while a connect is in flight** (scanning during association
  destabilizes the switch).
- **Connected AP**: the AP whose object path equals the active connection's
  `SpecificObject` (read from the active connection's `Connection` object or,
  equivalently, compare SSID + `ActiveAccessPoint` on the device). Use the
  device property `ActiveAccessPoint` — authoritative, no string matching.
- **Saved network detection**: to decide prompt-vs-activate without `nmcli`,
  use `NM.Settings` (`org.freedesktop.NetworkManager.Settings`) →
  `ListConnections` → each `GetSettings` → `connection.type ==
  "802-11-wireless"` and `802-11-wireless.ssid == ap.ssid`. Cache by SSID;
  invalidate on `Settings.ConnectionAdded`/`ConnectionRemoved`.

### 2.3 Activation

- Saved profile: `ActivateConnection(connectionPath, devicePath, apPath)` —
  `(ooo)` returning the active connection path. `apPath` is the specific AP so
  NM associates with the chosen BSSID.
- New network / prompt: `AddAndActivateConnection(settings, devicePath, apPath)`
  — `(a{sa{sv}}, oo)`; settings include:
  ```text
  connection:      { id: ssid, type: "802-11-wireless" }
  802-11-wireless: { ssid: <ay>, mode: "infrastructure" }
  802-11-wireless-security: { key-mgmt: "wpa-psk", psk: password }
  ```
  Key management is derived from the AP's RSN/WPA flags (WPA-PSK vs WPA-EAP is
  out of scope; PSK only). If NM responds `SecretsRequired`, transition to
  `needAuth` rather than failing.
- **Switching**: before activating a different network, if a different active
  connection exists on the device, call `DeactivateConnection(activeConnPath)`
  and wait for device `State === 30 (DISCONNECTED)` (or the `StateChanged`
  signal) before issuing the new activation. This removes the nmcli race that
  produced the "network could not be found" / contention failures.
- **Cancellation**: a new user intent while `preparing`/`activating` cancels the
  pending promise chain (generation counter), deactivates if necessary, and
  starts the new target. The superseded chain must not mutate state.

### 2.4 Connect state machine

```ts
type WifiPhase = "idle" | "preparing" | "needAuth" | "activating" | "failed"
interface WifiConnectState {
  phase: WifiPhase
  ssid: string | null       // target of the in-flight attempt
  reason: string | null     // human-readable failure reason
}
```

Transitions:
- `activate(ssid, password?)`:
  - `preparing` immediately (this is what makes the spinner appear on the first
    frame).
  - saved → `activating` → `ActivateConnection`; unsaved+secured and no
    password → `needAuth`; unsaved with password → `activating` →
    `AddAndActivateConnection`.
- NM `StateChanged` (device) drives progress detail and terminal outcomes:
  states 40/50/70 map to „Connecting…“, 100 → `activated` → `idle` (success
  message cleared), 120 (FAILED) → `failed` with the reason code.
- **Watchdog**: a single bounded timer (e.g. `connection.wait-device-timeout` +
  margin, ~45s) that, if the attempt has not reached a terminal transition,
  sets `failed("timed out")` and **cancels itself** on any terminal transition.
  This is the only timer in the module, and it exists to surface a hung NM, not
  to paper over an uncancellable subprocess.
- Exposed accessors: `connectState` (read-only accessor), `wifiNetworks`
  (derived AP list with `connected`/`saved`/`secured`/`strength`), `wifiEnabled`
  (device `Powered`/`State` derived), `scanState` (optional freshness for the
  view).

### 2.5 View cadence

`WifiView` asks the service to `startScanning()` on open and `stopScanning()` on
close. The service issues `RequestScan` every ~6s while active **and** not
connecting, and updates the list from AP signals immediately. No `iw`, no
per-file `last-seen` heuristics.

## 3. `services/bluetooth-service.ts`

BlueZ D-Bus (`org.bluez`), replacing `bluetoothctl`/`rfkill` subprocesses.

- Adapter (`/org/bluez/hci0`, resolved via ObjectManager): `Adapter1.Powered`
  read/write; `Discovering`; `StartDiscovery`/`StopDiscovery`;
  `SetDiscoveryFilter` (Transport "auto", DuplicateData false).
- Devices: `GetManagedObjects` → `Device1` entries (`Address`, `Alias`, `Paired`,
  `Connected`, `Trusted`, `RSSI`, `UUIDs`, `Icon`). Subscribe to
  `InterfacesAdded`/`InterfacesRemoved` and `PropertiesChanged` for live lists.
- Actions: `Pair()`, `Connect()`, `Disconnect()`, `CancelPairing()`; on
  successful pair set `Trusted=true` then `Connect()` (preserves current
  behavior). Unpair via `Adapter1.RemoveDevice(device)`.
- Agent: keep `bluetooth-agent.ts` as the `org.bluez.Agent1`
  NoInputNoOutput default agent; re-wire registration through
  `nm-client`-style async plumbing if needed (it already talks D-Bus — minimum
  change).
- State machine: per-device `{ paired, connected, busy: "pair"|"connect"|"disconnect"|null }`
  with an accessor; the UI spinner reads `busy`.
- Radio soft-block: keep using BlueZ `Powered`; a soft block makes the setter
  fail, which the service surfaces as `failed`. Provisioning already clears a
  soft block at provision time (unchanged by this change).

## 4. UI (thin)

- `controls/wifi.tsx` exports: `WifiTile`, `WifiRow`, `WifiPasswordPrompt`,
  `WifiToggle`, plus `wifiNetworks`, `wifiEnabled`, `connectState`. It contains
  no bus/command code. Row:
  - `busy = connectState().ssid === item.ssid && phase !== "idle"`;
  - Connect button `sensitive` only when `phase === "idle"` **or** the click
    targets a different SSID (re-target), never disabled en masse;
  - spinner visible immediately on press; label shows `Connecting…`.
- `views/WifiView.tsx`: `startScanning()`/`stopScanning()` on the active-view
  effect; password prompt driven by `connectState().phase === "needAuth"` **or**
  a local explicit selection (secured + unsaved).
- `controls/bluetooth.tsx` / `views/BluetoothView.tsx`: same treatment over
  `bluetooth-service`.
- `style.css`: drop classes orphaned by the deleted code, keep existing visual
  language unchanged.

## 5. Provisioning purge

Remove `iw` and its capability grant (see proposal Impact). Verify keeps its
NetworkManager/BlueZ assertions; the iw/cap gate and vars are deleted and the
three unit tests updated so the suite stays green.

## 6. Verification

- Provisioning: `src/provisioning/.venv` pytest suite green.
- Runtime smoke matrix (owner): see `tasks.md` §6.
- AGS TS review: grep the panel tree for `execAsync|nmcli|iw |bluetoothctl|rfkill|call_sync`
  — must return nothing in `services/`/`controls/`/`views/`.
