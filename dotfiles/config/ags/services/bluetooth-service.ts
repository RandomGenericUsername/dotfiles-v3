import GLib from "gi://GLib?version=2.0"
import Wp from "gi://AstalWp?version=0.1"
import { createState } from "ags"
import {
  DBUS_PROPERTIES_IFACE,
  asBusError,
  call,
  subscribe,
  watchProperties,
} from "./nm-client"

/**
 * BlueZ Bluetooth service (design §3).
 *
 * `org.bluez` D-Bus is the single source of truth: adapter resolution, power,
 * discovery, the device list, and pair/connect/disconnect/unpair all live here.
 * The UI is a thin view over the exported accessors — no subprocess, no legacy
 * control binding, no blocking bus call.
 */

const BLUEZ = "org.bluez"
const OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
const OBJECT_MANAGER_PATH = "/"
const ADAPTER_IFACE = "org.bluez.Adapter1"
const DEVICE_IFACE = "org.bluez.Device1"
const BATTERY_IFACE = "org.bluez.Battery1"

const DEFAULT_ADAPTER_PATH = "/org/bluez/hci0"

//: One bounded watchdog per action; it exists to surface a hung BlueZ call and
//: cancels itself on every completion.
const WATCHDOG_MS = 30000

export type BluetoothAction = "pair" | "connect" | "disconnect" | "unpair"

export interface BluetoothBusy {
  address: string | null
  action: BluetoothAction | null
}

export interface BluetoothDevice {
  path: string
  address: string
  alias: string
  name: string
  connected: boolean
  paired: boolean
  trusted: boolean
  rssi: number
  icon: string
  adapter: string
  battery: number
}

//: Naming convention, kept strict because the public API now collides with one
//: of these: `set<X>State` writes the raw accessor, and a same-named exported
//: function is an INTENT that validates and talks to BlueZ. `setBluetoothPowered`
//: is the intent (design §5) and forced the raw writer to be renamed `setPoweredState`.
const [bluetoothDevices, setBluetoothDevices] = createState<BluetoothDevice[]>([])
const [bluetoothPowered, setPoweredState] = createState(false)
const [bluetoothDiscovering, setDiscoveringState] = createState(false)
const [bluetoothBusy, setBluetoothBusy] = createState<BluetoothBusy>({
  address: null,
  action: null,
})
const [bluetoothFailure, setBluetoothFailure] = createState("")
//: The LOCAL CONTROLLER's hardware address (`Adapter1.Address`), never a
//: device's. Empty string means "not read yet / no adapter"; BlueZ always
//: publishes it, so `""` is a real absence rather than a formatting default.
const [bluetoothAdapterAddress, setAdapterAddress] = createState("")
//: Where the sound ACTUALLY went. `null` until a routing attempt proves an
//: endpoint, and `null` again if its bounded window expires — that is the
//: record of a failure, not a missing value.
const [bluetoothAudioTarget, setAudioTarget] = createState<string | null>(null)

// ── Mutable service state ────────────────────────────────────────────────

let adapterPath: string | null = null
let unwatchAdapter: (() => void) | null = null

const deviceCache = new Map<string, BluetoothDevice>()
const unwatchDevices = new Map<string, () => void>()
const unwatchBatteries = new Map<string, () => void>()

let watchdogId = 0

//: Number of surfaces currently asking for a scan. NOT a mirror of BlueZ's
//: `Discovering` property — it counts interested callers, which is why the
//: increment happens before the already-discovering guard in `runStartDiscovery`.
let discoveryUsers = 0

const wp = Wp.get_default()

// ── Helpers ──────────────────────────────────────────────────────────────

function dictEntries<T>(value: unknown): Array<[string, T]> {
  if (value instanceof Map) return [...value.entries()] as Array<[string, T]>
  if (Array.isArray(value)) return value as Array<[string, T]>
  if (value !== null && typeof value === "object") {
    return Object.entries(value as Record<string, T>)
  }
  return []
}

function deviceFromProps(
  path: string,
  props: Record<string, unknown>,
): BluetoothDevice | null {
  const address = String(props.Address ?? "")
  if (address === "") return null
  return {
    path,
    address,
    alias: String(props.Alias ?? props.Name ?? address),
    name: String(props.Name ?? props.Alias ?? address),
    connected: Boolean(props.Connected),
    paired: Boolean(props.Paired),
    trusted: Boolean(props.Trusted),
    rssi: Number(props.RSSI ?? 0),
    icon: String(props.Icon ?? ""),
    adapter: String(props.Adapter ?? ""),
    battery: 0,
  }
}

function deviceByAddress(address: string): BluetoothDevice | null {
  for (const device of deviceCache.values()) {
    if (device.address === address) return device
  }
  return null
}

function applyDevices(): void {
  const list = [...deviceCache.values()]
  list.sort((a, b) => {
    const sa = a.connected ? 3 : a.paired ? 2 : 1
    const sb = b.connected ? 3 : b.paired ? 2 : 1
    if (sa !== sb) return sb - sa
    return b.rssi - a.rssi
  })
  setBluetoothDevices(list)
}

function actionLabel(action: BluetoothAction): string {
  switch (action) {
    case "pair":
      return "Pairing"
    case "connect":
      return "Connecting"
    case "disconnect":
      return "Disconnecting"
    case "unpair":
      return "Unpairing"
  }
}

// ── Adapter ──────────────────────────────────────────────────────────────

function updateAdapterProps(props: Record<string, unknown>): void {
  if ("Powered" in props) setPoweredState(Boolean(props.Powered))
  if ("Discovering" in props) setDiscoveringState(Boolean(props.Discovering))
  //: `Address` is read-only on Adapter1, so BlueZ never emits it in a
  //: PropertiesChanged — the ONLY source is the full property set, which
  //: `setAdapter` forwards here *before* its `adapterPath === path` early
  //: return. Removing that ordering would leave the address permanently "",
  //: so the first read is the one that matters and it must keep flowing.
  if ("Address" in props) setAdapterAddress(String(props.Address ?? ""))
}

function setAdapter(path: string, props: Record<string, unknown>): void {
  updateAdapterProps(props)
  if (adapterPath === path) return
  if (unwatchAdapter !== null) {
    unwatchAdapter()
    unwatchAdapter = null
  }
  adapterPath = path
  unwatchAdapter = watchProperties(
    path,
    ADAPTER_IFACE,
    (changed) => updateAdapterProps(changed),
    BLUEZ,
  )
}

function clearAdapter(): void {
  if (unwatchAdapter !== null) {
    unwatchAdapter()
    unwatchAdapter = null
  }
  adapterPath = null
  setPoweredState(false)
  setDiscoveringState(false)
  //: The address belonged to the adapter object that just went away; keeping it
  //: would show a controller MAC that is no longer this machine's radio.
  setAdapterAddress("")
}

// ── Device cache / watches ───────────────────────────────────────────────

function installDeviceWatch(path: string): void {
  if (unwatchDevices.has(path)) return
  unwatchDevices.set(
    path,
    watchProperties(
      path,
      DEVICE_IFACE,
      (changed) => applyDeviceProps(path, changed),
      BLUEZ,
    ),
  )
}

function installBatteryWatch(path: string): void {
  if (unwatchBatteries.has(path)) return
  unwatchBatteries.set(
    path,
    watchProperties(
      path,
      BATTERY_IFACE,
      (changed) => {
        if ("Percentage" in changed) updateBattery(path, Number(changed.Percentage))
      },
      BLUEZ,
    ),
  )
}

function applyDeviceProps(
  path: string,
  changed: Record<string, unknown>,
): void {
  const device = deviceCache.get(path)
  if (device === undefined) return
  const next: BluetoothDevice = { ...device }
  if ("Alias" in changed) next.alias = String(changed.Alias)
  if ("Name" in changed) next.name = String(changed.Name)
  if ("Connected" in changed) next.connected = Boolean(changed.Connected)
  if ("Paired" in changed) next.paired = Boolean(changed.Paired)
  if ("Trusted" in changed) next.trusted = Boolean(changed.Trusted)
  if ("RSSI" in changed) next.rssi = Number(changed.RSSI)
  if ("Icon" in changed) next.icon = String(changed.Icon)
  deviceCache.set(path, next)
  applyDevices()
}

function updateBattery(path: string, level: number): void {
  const device = deviceCache.get(path)
  if (device === undefined) return
  deviceCache.set(path, { ...device, battery: level })
  applyDevices()
}

function removeDevice(path: string): void {
  const off = unwatchDevices.get(path)
  if (off) {
    off()
    unwatchDevices.delete(path)
  }
  const batteryOff = unwatchBatteries.get(path)
  if (batteryOff) {
    batteryOff()
    unwatchBatteries.delete(path)
  }
  if (deviceCache.delete(path)) applyDevices()
}

function handleDeviceInterfaces(
  path: string,
  interfaces: Record<string, Record<string, unknown>>,
): void {
  const deviceProps = interfaces[DEVICE_IFACE]
  const percentage = interfaces[BATTERY_IFACE]?.Percentage

  if (deviceProps !== undefined) {
    const device = deviceFromProps(path, deviceProps)
    if (device === null) return
    if (percentage !== undefined) device.battery = Number(percentage)
    deviceCache.set(path, device)
    installDeviceWatch(path)
    if (percentage !== undefined) installBatteryWatch(path)
    return
  }

  if (percentage !== undefined) {
    updateBattery(path, Number(percentage))
    installBatteryWatch(path)
  }
}

// ── Managed-objects read ─────────────────────────────────────────────────

async function refreshManagedObjects(): Promise<void> {
  let reply: GLib.Variant
  try {
    reply = await call(
      BLUEZ,
      OBJECT_MANAGER_PATH,
      OBJECT_MANAGER_IFACE,
      "GetManagedObjects",
      null,
    )
  } catch (error) {
    console.error(`bluetooth-service: GetManagedObjects failed: ${error}`)
    return
  }

  const unpacked = reply.recursiveUnpack()
  const objects = (Array.isArray(unpacked) ? unpacked[0] : unpacked) as unknown
  const entries = dictEntries<Record<string, Record<string, unknown>>>(objects)

  let chosen: [string, Record<string, unknown>] | null = null
  for (const [path, interfaces] of entries) {
    const props = interfaces[ADAPTER_IFACE]
    if (props === undefined) continue
    if (path === DEFAULT_ADAPTER_PATH) {
      chosen = [path, props]
      break
    }
    if (chosen === null) chosen = [path, props]
  }
  if (chosen !== null) setAdapter(chosen[0], chosen[1])

  for (const [path, interfaces] of entries) handleDeviceInterfaces(path, interfaces)

  applyDevices()
}

// ── ObjectManager signal handlers ────────────────────────────────────────

function handleInterfacesAdded(parameters: GLib.Variant): void {
  const [path, interfaces] = parameters.recursiveUnpack() as [
    string,
    Record<string, Record<string, unknown>>,
  ]
  const adapterProps = interfaces[ADAPTER_IFACE]
  if (adapterProps !== undefined) {
    if (adapterPath === null || path === DEFAULT_ADAPTER_PATH) {
      setAdapter(path, adapterProps)
    }
  }
  handleDeviceInterfaces(path, interfaces)
}

function handleInterfacesRemoved(parameters: GLib.Variant): void {
  const [path, interfaces] = parameters.recursiveUnpack() as [string, string[]]
  if (interfaces.includes(ADAPTER_IFACE)) clearAdapter()
  if (interfaces.includes(DEVICE_IFACE)) {
    removeDevice(path)
    return
  }
  if (interfaces.includes(BATTERY_IFACE)) {
    const batteryOff = unwatchBatteries.get(path)
    if (batteryOff) {
      batteryOff()
      unwatchBatteries.delete(path)
    }
    const device = deviceCache.get(path)
    if (device !== undefined) {
      deviceCache.set(path, { ...device, battery: 0 })
      applyDevices()
    }
  }
}

// ── Watchdog (the only action timer) ─────────────────────────────────────

function clearWatchdog(): void {
  if (watchdogId === 0) return
  try {
    GLib.source_remove(watchdogId)
  } catch {
    /* already removed */
  }
  watchdogId = 0
}

function armWatchdog(address: string, action: BluetoothAction): void {
  clearWatchdog()
  watchdogId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, WATCHDOG_MS, () => {
    watchdogId = 0
    if (bluetoothBusy().address !== address) return false
    setBluetoothBusy({ address: null, action: null })
    setBluetoothFailure(`${actionLabel(action)} timed out`)
    return false
  })
}

function finishAction(address: string): void {
  if (bluetoothBusy().address !== address) return
  clearWatchdog()
  setBluetoothBusy({ address: null, action: null })
}

function failAction(
  address: string,
  action: BluetoothAction,
  error: unknown,
): void {
  if (bluetoothBusy().address !== address) return
  clearWatchdog()
  setBluetoothBusy({ address: null, action: null })
  setBluetoothFailure(`${actionLabel(action)} failed: ${asBusError(error).message}`)
}

async function runAction(
  address: string,
  action: BluetoothAction,
  fn: (device: BluetoothDevice) => Promise<void>,
): Promise<void> {
  if (bluetoothBusy().address !== null) return
  const device = deviceByAddress(address)
  if (device === null) return

  setBluetoothFailure("")
  setBluetoothBusy({ address, action })
  armWatchdog(address, action)
  try {
    await fn(device)
    finishAction(address)
  } catch (error) {
    failAction(address, action, error)
  }
}

async function connectDeviceInternal(device: BluetoothDevice): Promise<void> {
  await call(BLUEZ, device.path, DEVICE_IFACE, "Connect", null)
}

// ── Audio routing ────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
      resolve()
      return false
    })
  })
}

/**
 * Route audio to a freshly connected Bluetooth device.
 *
 * BlueZ connecting alone does not make the headset the default PipeWire sink,
 * and active streams keep playing on the previous sink — so the headphones
 * look "Connected" but sound stays on the speakers. Poll for the device's
 * speaker endpoint (the audio profile lags the BlueZ connect by a few seconds),
 * make it the default, and move active streams onto it.
 *
 * Every exit path records what it actually achieved in `bluetoothAudioTarget`:
 * a proven endpoint on success, `null` on the early bail and on an exhausted
 * window. The value is recorded in state and deliberately NOT rendered — the
 * popup showing a PipeWire row would mix concerns (owner ruling, design §5) —
 * but its absence from the UI must not be its absence from the service, which
 * is what made this failure invisible in the first place.
 */
export async function routeAudioToDevice(label: string): Promise<void> {
  //: Clear first, unconditionally: the attempt is unproven until an endpoint
  //: is found and actually defaulted. Setting it after the guards instead
  //: would let the `!wp || !label` bail inherit the PREVIOUS attempt's answer
  //: and report a route that is no longer in effect.
  setAudioTarget(null)
  if (!wp || !label) return
  for (let attempt = 0; attempt < 16; attempt++) {
    const endpoint = (wp.audio?.speakers ?? []).find(
      (speaker: { name?: string; description?: string }) => {
        const n = speaker.name ?? ""
        const d = speaker.description ?? ""
        return n === label || d === label || n.includes(label) || d.includes(label)
      },
    )
    if (endpoint) {
      //: Track whether the default write landed, separately from finding the
      //: endpoint: a vanished endpoint throws here, and recording it as the
      //: target would claim the sound moved when it did not.
      let defaulted = false
      try {
        endpoint.is_default = true
        defaulted = true
      } catch {
        /* endpoint vanished */
      }
      for (const stream of wp.audio?.streams ?? []) {
        try {
          stream.target_endpoint = endpoint
        } catch {
          /* stream may be gone */
        }
      }
      //: Only a successful `is_default` is a real answer. The PipeWire node name
      //: first because it is the stable identifier the endpoint is keyed by,
      //: `description` because it is what WirePlumber shows a human when the
      //: node name is opaque, and `label` last so the accessor never holds ""
      //: masquerading as a target. `||`, not `??` — an unset WirePlumber string
      //: property reads back as "", and `??` treats "" as present.
      if (defaulted) {
        setAudioTarget(String(endpoint.name || endpoint.description || label))
      }
      return
    }
    await sleep(500)
  }
  //: 16 × 500ms expired with no matching speaker endpoint — the profile never
  //: materialised. The loop falls through with `bluetoothAudioTarget` still
  //: `null`; that null IS the record, so there is no throw and no toast.
}

// ── Discovery ────────────────────────────────────────────────────────────

/**
 * Reference-counted discovery (design §5).
 *
 * INVARIANT: `discoveryUsers` counts surfaces holding a live `visible`-scoped
 * effect, not whether BlueZ happens to be scanning. Every `start` is matched
 * by exactly one `stop` from the SAME effect cleanup, so the counter is
 * incremented unconditionally — before `runStartDiscovery`'s guards, and
 * crucially before its `if (bluetoothDiscovering()) return`.
 *
 * That ordering is the whole point. If the increment sat behind that guard, a
 * second surface opening while a scan was already running would skip its
 * increment while still registering a cleanup; its later `stop` would then
 * decrement a count that never included it, driving the count to zero while
 * the first surface was still visible, and the next `stop` would clamp at zero
 * forever — the next scan would never be stopped. Skipping the increment is
 * what made the leak half-invisible and the double-stop half-real.
 *
 * The mirror-image hazard is symmetric: `stop` must clamp at zero rather than
 * trust its caller, because an unmatched or repeated `stop` would otherwise
 * go negative and strand a real holder's decrement.
 *
 * Deliberately NOT reset by `clearAdapter`. The count tracks mounted effects,
 * and an adapter disappearing does not unmount them — a `visible`-scoped
 * effect has no accessor dependency on `adapterPath`, so it does not re-run
 * when the adapter is yanked and replugged. Zeroing there would orphan a
 * still-visible surface: its later `stop` would clamp at zero and hand the
 * `StopDiscovery` to whichever surface stops next, stopping the scan out from
 * under a live one. Letting the count survive costs at most one `StopDiscovery`
 * against a fresh, non-scanning adapter, which BlueZ answers with a swallowed
 * no-op — the cheap direction to be wrong in.
 */
export function startBluetoothDiscovery(): void {
  discoveryUsers++
  void runStartDiscovery()
}

async function runStartDiscovery(): Promise<void> {
  const path = adapterPath
  if (path === null || !bluetoothPowered()) return
  //: Now purely an optimisation: skip re-issuing StartDiscovery to an adapter
  //: BlueZ already reports as scanning. It must NOT gate the reference count
  //: — the reference is held by a caller, not by the scan.
  if (bluetoothDiscovering()) return

  try {
    await call(
      BLUEZ,
      path,
      ADAPTER_IFACE,
      "SetDiscoveryFilter",
      new GLib.Variant("(a{sv})", [
        {
          Transport: new GLib.Variant("s", "auto"),
          DuplicateData: new GLib.Variant("b", false),
        },
      ]),
    )
  } catch {
    //: Older BlueZ may reject the filter; discovery still works without it.
  }
  if (path !== adapterPath) return

  try {
    await call(BLUEZ, path, ADAPTER_IFACE, "StartDiscovery", null)
  } catch {
    //: Already discovering, or a transient adapter state.
  }
}

export function stopBluetoothDiscovery(): void {
  //: Clamp BEFORE the bus call: the count must not go negative on an
  //: unmatched stop, or a subsequent real holder's decrement is silently lost
  //: and discovery never stops again.
  discoveryUsers = Math.max(0, discoveryUsers - 1)
  //: Other surfaces are still visible and still want the scan. This is the
  //: popup-close-racing-panel-open case: without the count, the popup's
  //: cleanup would stop a scan the subview had just started.
  if (discoveryUsers > 0) return
  //: Guarded on the adapter, not the count: zero holders means "stop it", and
  //: there is nothing to stop when BlueZ has no adapter to ask.
  const path = adapterPath
  if (path === null) return
  void call(BLUEZ, path, ADAPTER_IFACE, "StopDiscovery", null).catch(() => {
    /* not discovering */
  })
}

// ── Power ────────────────────────────────────────────────────────────────

async function setAdapterPowered(enabled: boolean): Promise<void> {
  const path = adapterPath
  if (path === null) {
    setBluetoothFailure("No Bluetooth adapter available")
    return
  }
  setBluetoothFailure("")
  try {
    await call(
      BLUEZ,
      path,
      DBUS_PROPERTIES_IFACE,
      "Set",
      new GLib.Variant("(ssv)", [
        ADAPTER_IFACE,
        "Powered",
        new GLib.Variant("b", enabled),
      ]),
    )
    setPoweredState(enabled)
  } catch (error) {
    console.error(`bluetooth-service: setting Powered failed: ${error}`)
    setBluetoothFailure(
      enabled
        ? "Could not turn Bluetooth on (adapter may be soft-blocked)"
        : "Could not turn Bluetooth off",
    )
  }
}

/**
 * The power control's only entry point — the mirror of `setWifiEnabled`
 * (design §5). Explicit value, never a read-modify-write: the popup header
 * switch and the settings tile glyph are both mounted at once, so each holds
 * its own copy of the last state it saw. A toggle would read whichever copy
 * was stale and write the inverse of what the user actually asked for.
 *
 * The adapter may have disappeared between render and click, so `enabled` is
 * what the user asked for even when the write fails — the failure line says
 * so rather than the radio silently staying where it was.
 */
export async function setBluetoothPowered(enabled: boolean): Promise<void> {
  await setAdapterPowered(enabled)
}

/**
 * Back-compat blind toggle, retained for call sites not yet migrated to
 * `setBluetoothPowered`. It reads `bluetoothPowered()` and inverts, which is
 * exactly the read-modify-write hazard above — so treat it as deprecated and
 * migrate rather than reuse. Kept because the popup header and the settings
 * tile are separate surfaces landing separately, and deleting this before
 * both are converted would break whichever has not converted yet.
 */
export function toggleBluetooth(): void {
  void setBluetoothPowered(!bluetoothPowered())
}

// ── Device actions ───────────────────────────────────────────────────────

export function pairDevice(address: string): void {
  void runAction(address, "pair", async (device) => {
    await call(BLUEZ, device.path, DEVICE_IFACE, "Pair", null)
    try {
      await call(
        BLUEZ,
        device.path,
        DBUS_PROPERTIES_IFACE,
        "Set",
        new GLib.Variant("(ssv)", [
          DEVICE_IFACE,
          "Trusted",
          new GLib.Variant("b", true),
        ]),
      )
    } catch {
      //: Some devices refuse trust; connect still works.
    }
    await connectDeviceInternal(device)
    void routeAudioToDevice(device.alias || device.name).catch(() => {})
  })
}

export function connectDevice(address: string): void {
  void runAction(address, "connect", async (device) => {
    await connectDeviceInternal(device)
    void routeAudioToDevice(device.alias || device.name).catch(() => {})
  })
}

export function disconnectDevice(address: string): void {
  void runAction(address, "disconnect", async (device) => {
    await call(BLUEZ, device.path, DEVICE_IFACE, "Disconnect", null)
  })
}

export function unpairDevice(address: string): void {
  void runAction(address, "unpair", async (device) => {
    const path = adapterPath
    if (path === null) throw new Error("No Bluetooth adapter")
    await call(
      BLUEZ,
      path,
      ADAPTER_IFACE,
      "RemoveDevice",
      new GLib.Variant("(o)", [device.path]),
    )
  })
}

// Accessors only; the intent functions (`setBluetoothPowered`,
// `startBluetoothDiscovery`, `stopBluetoothDiscovery`, `toggleBluetooth`, the
// device actions) carry `export` at their own declaration, so listing them
// again here would be a duplicate export.
export {
  bluetoothAdapterAddress,
  bluetoothAudioTarget,
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothFailure,
  bluetoothPowered,
}

// ── Bootstrap ────────────────────────────────────────────────────────────

let started = false

async function bootstrap(): Promise<void> {
  subscribe(
    BLUEZ,
    OBJECT_MANAGER_PATH,
    OBJECT_MANAGER_IFACE,
    "InterfacesAdded",
    handleInterfacesAdded,
  )
  subscribe(
    BLUEZ,
    OBJECT_MANAGER_PATH,
    OBJECT_MANAGER_IFACE,
    "InterfacesRemoved",
    handleInterfacesRemoved,
  )
  await refreshManagedObjects()
}

function start(): void {
  if (started) return
  started = true
  void bootstrap().catch((error) =>
    console.error(`bluetooth-service: bootstrap failed: ${error}`),
  )
}

start()
