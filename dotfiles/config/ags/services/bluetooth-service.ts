import GLib from "gi://GLib?version=2.0"
import Wp from "gi://AstalWp?version=0.1"
import { createState } from "ags"
import {
  DBUS_PROPERTIES_IFACE,
  asBusError,
  call,
  getAll,
  subscribe,
  watchProperties,
} from "./nm-client"
import { registry } from "../lib/icon-registry"
import { notifier } from "../lib/notifier"

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

/**
 * How long we wait in silence before deciding a paired device is gone.
 *
 * Silence is ambiguous, and that is the whole problem. BlueZ emits
 * `PropertiesChanged` for `RSSI` only when the VALUE CHANGES, so a device
 * sitting still emits nothing while sitting right there. "Present but quiet"
 * and "switched off" look identical until enough time passes.
 *
 * 120s is sized from MEASUREMENT, not taste (2026-10-07, 4-minute trace):
 * a device that was demonstrably present for 170s still went 59.5s between
 * RSSI reports, and another went 35.5s. A previous 20s window was below both
 * AND below the ~20-30s floor set by BlueZ's scan duty cycle plus LE
 * advertising intervals, so it reported present devices out-of-range roughly
 * half the time (MEASURED `-55` stable for 30s+). 120s is ~2x the worst
 * observed gap.
 *
 * What it costs, stated plainly: an off device still offers Connect for up
 * to this long, and a device that somehow stays silent past it reads
 * "Not in range" with Connect disabled. One window for both means both
 * costs are paid at this value; the alternative (a short window for the
 * glyph, a long one for the button) buys a faster-looking row at the price
 * of a new visual state.
 *
 * THE CLOCK ONLY RUNS WHILE A SCAN IS ACTUALLY RUNNING. That is not a
 * detail — aging on wall-clock was a real bug in an earlier version. A
 * closed panel runs no scan, so nothing can be heard, so nothing may be
 * declared gone; and right after a scan STARTS there must be grace, or
 * every paired device reads "Not in range" the instant the panel opens.
 * `scanStartedAt` supplies that grace. See `applyRssiAgeing`.
 */
const RSSI_STALE_MS = 120000

/** Monotonic milliseconds; immune to wall-clock jumps. */
function nowMonoMs(): number {
  return Math.trunc(GLib.get_monotonic_time() / 1000)
}

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
  /**
   * Monotonic ms of the last time BlueZ SAID SOMETHING about this device —
   * an `InterfacesAdded`, or a `PropertiesChanged` carrying `RSSI`. This is
   * the only evidence of presence there is; a re-read of the frozen value
   * must never touch it, or a silent device would look freshly heard.
   */
  lastHeardAt: number
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
//: Action failures are NOT panel state. They used to render as an in-panel
//: `.settings-msg` row (`popup-failed` in the mock); the owner rejected that —
//: a failure is a transient message and belongs on the notification surface,
//: the same one that already reports a successful connect (Blueman posts that
//: card via `org.freedesktop.Notifications`, rendered by the session's AGS
//: notifd host). There is deliberately no `bluetoothFailure` accessor: if a
//: failure needs showing and the notification is missed, the row simply reads
//: as it did before the attempt. See `postBluetoothNotification`.
//: The LOCAL CONTROLLER's hardware address (`Adapter1.Address`), never a
//: device's. Empty string means "not read yet / no adapter"; BlueZ always
//: publishes it, so `""` is a real absence rather than a formatting default.
const [bluetoothAdapterAddress, setAdapterAddress] = createState("")
//: DOES AN ADAPTER OBJECT EXIST ON THE BUS? A different fact from
//: `bluetoothAdapterAddress`, and deliberately not derived from it.
//:
//: The two came apart the moment the header switch needed a `sensitive` flag:
//: conflating "we have read the address" with "a radio exists" makes the switch
//: insensitive for two different reasons (no adapter, vs. a first read that has
//: not landed yet) that demand opposite behaviour, and it makes the flag a
//: proxy that quietly reports absence when it means lateness. This is the real
//: signal — `true` the moment `setAdapter` has an `Adapter1` object in hand,
//: and `false` from `clearAdapter` when `InterfacesRemoved` takes it away.
const [bluetoothReady, setReadyState] = createState(false)
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

//: Surfaces currently asking for a scan, keyed by an OWNER ID, not a counter.
//:
//: WHY A SET AND NOT A NUMBER: a plain counter leaked to 205 on a live session
//: (MEASURED 2026-10-07). AGS creates this component's effects outside a
//: `createRoot`, so they are never disposed — the bar's own log says so
//: ("effects created outside a `createRoot` will never be disposed"). Every
//: re-render therefore adds ANOTHER live effect, each calling
//: `startBluetoothDiscovery` with no matching stop. Consequences measured:
//: the count climbed 142 -> 205, `scanStartedAt` never reset (the count never
//: reached zero), so the grace-on-open never applied and a device briefly
//: showed reachable then was aged out instantly.
//:
//: With owner ids the operation is IDEMPOTENT: a leaked effect re-acquiring
//: the same surface is a no-op, so the set can never exceed the number of real
//: surfaces (popup + settings subview). The count is bounded by design rather
//: than by trusting every cleanup to run.
const discoveryHolders = new Set<string>()

//: Monotonic ms at which the CURRENT scan run began, or 0 for no run. The
//: reachability clock is anchored to `max(lastHeardAt, scanStartedAt)` so a
//: fresh scan grants grace before any device may be declared gone. Set on the
//: empty -> non-empty transition only: a second surface joining a running scan
//: must not extend the grace window and thereby prolong a stale "in range".
let scanStartedAt = 0

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
    lastHeardAt: nowMonoMs(),
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
  //: An `Adapter1` object is in hand, so a power write can land. Set before the
  //: `adapterPath === path` early return, for the same reason `Address` is
  //: forwarded before it: a re-read of the SAME adapter must not be the thing
  //: that first reports readiness.
  setReadyState(true)
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
  //: No `Adapter1` left on the bus — the honest reason for an insensitive
  //: header switch, as opposed to `bluetoothAdapterAddress` being merely
  //: unread, which is not this.
  setReadyState(false)
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
      (changed, invalidated) => applyDeviceProps(path, changed, invalidated),
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

/**
 * Re-read every cached device's properties from BlueZ.
 *
 * WHY THIS EXISTS. Reachability is derived from `RSSI`:
 * `inRange = connected() || rssi() < 0`, and an absent RSSI normalises to 0, so
 * a FRESH read shows a quiet device as out of range. But BlueZ does not emit
 * PropertiesChanged when a device merely stops advertising — it just stops
 * reporting the property. So with events alone the row keeps the last in-range
 * value it ever saw.
 *
 * MEASURED, on a real TOZO NC9 sitting in its charging case:
 *
 *   device                 RSSI     Paired  Connected
 *   Infinix NOTE 40 Pro    None     1       0
 *   TOZO NC9               None     1       0
 *   51-21-D7-6B-40-B6      -38      0       0     <- heard by the scan
 *
 * Both paired devices have NO RSSI property at all; the devices the scan just
 * heard do. The Infinix row read correctly only because the scan had just
 * rediscovered it and pushed a fresh value through the event path; the TOZO had
 * not been rediscovered, so its row offered a live Connect button for hardware
 * that was switched off.
 *
 * WHY THIS IS CALLED ON VIEW, NOT ON A TIMER. The reading only matters while
 * someone is looking at the panel, and every event that can change it still
 * arrives normally in between — RSSI during an active scan, plus
 * connect/disconnect/pairing. A timer would be paying for an answer nobody reads.
 *
 * An ABSENT property is deliberately destructive here, unlike
 * `applyDeviceProps` which only applies keys present in `changed`: for RSSI,
 * absence is the signal, so it must overwrite the stale value rather than
 * skip. That is the whole reachability rule — a present reading counts
 * however old it is (see the note above `BluetoothDevice`), and only
 * absence clears it.
 */
export async function refreshBluetoothDevices(): Promise<void> {
  const entries = [...deviceCache.entries()]
  if (entries.length === 0) return
  await Promise.all(
    entries.map(async ([path, device]) => {
      let props: Record<string, unknown>
      try {
        props = await getAll(path, DEVICE_IFACE, BLUEZ)
      } catch (error) {
        // KEEP the cached entry. A failed read is not evidence of absence:
        // BlueZ can fail a `GetAll` transiently (mid-teardown, under load)
        // while the object still exists, and the only reliable absence
        // signal is `InterfacesRemoved`, which has its own handler. The old
        // code dropped the device here — silently, with an empty catch — and
        // the drop was PERMANENT BY CONSTRUCTION: this refresh only iterates
        // the cache (self-sealing, a dropped device is never re-read) and
        // the full resync `refreshManagedObjects` runs once at bootstrap, so
        // nothing ever re-added it short of a bar restart. That is exactly
        // the reported symptom: disconnect, reopen the panel, the phone is
        // gone although BlueZ still has it (`Paired=1`). MEASURED 2026-10-07:
        // the disconnect sequence keeps `Device1` (only `Battery1` and the
        // media endpoints are removed), so the disappearance was never in
        // the disconnect path at all — it was in this reopen path.
        console.error(
          `bluetooth-service: refresh of ${path} failed, keeping cached entry: ${error}`,
        )
        return
      }
      const next: BluetoothDevice = { ...device }
      if ("Alias" in props) next.alias = String(props.Alias)
      if ("Name" in props) next.name = String(props.Name)
      if ("Connected" in props) next.connected = Boolean(props.Connected)
      if ("Paired" in props) next.paired = Boolean(props.Paired)
      if ("Trusted" in props) next.trusted = Boolean(props.Trusted)
      if ("Icon" in props) next.icon = String(props.Icon)
      // `?? 0` rather than a presence check: absence IS the signal.
      next.rssi = Number(props.RSSI ?? 0)
      deviceCache.set(path, next)
    }),
  )
  applyDevices()
}

/**
 * Mark a device gone once a running scan has failed to hear it for too long.
 *
 * The anchor is `max(lastHeardAt, scanStartedAt)`, and both halves matter:
 * `lastHeardAt` is the last real reception, and `scanStartedAt` grants grace
 * after a scan begins. Without the second, every paired device reads
 * "Not in range" the moment the panel opens — the scan has had no chance to
 * hear anything yet. Without the first, a device heard a moment ago would be
 * aged out against the scan's start time instead of its own.
 *
 * A re-read of the frozen BlueZ value must NEVER advance `lastHeardAt`, or a
 * switched-off device would look freshly heard every time the panel opened.
 * That is why `refreshBluetoothDevices` sets `rssi` but not this.
 *
 * Returns whether anything changed, so the caller can skip a re-render.
 */
function applyRssiAgeing(device: BluetoothDevice): boolean {
  // Nothing to age when there is no live reading: `rssi >= 0` already means
  // "absent", and the row is already showing "Not in range".
  if (device.rssi >= 0) return false
  const anchor = Math.max(device.lastHeardAt, scanStartedAt)
  if (nowMonoMs() - anchor <= RSSI_STALE_MS) return false
  device.rssi = 0
  return true
}

/**
 * Re-age cached readings. No bus traffic — a timestamp comparison per device.
 *
 * REFUSES TO RUN WHILE NO SCAN IS ACTIVE, deliberately. With no scan there is
 * no chance to hear anything, so declaring a device gone would be measuring
 * our own silence, not the device's. This is the bug an earlier version had
 * and it is the reason a closed panel never ages anything out.
 *
 * `lastHeardAt` survives the aging, so a device that comes back is judged
 * from the moment it was last actually heard.
 */
export function ageOutStaleReadings(): void {
  if (discoveryHolders.size === 0) return
  let changed = false
  for (const device of deviceCache.values()) {
    if (applyRssiAgeing(device)) changed = true
  }
  if (changed) applyDevices()
}

function applyDeviceProps(
  path: string,
  changed: Record<string, unknown>,
  invalidated: string[] = [],
): void {
  const device = deviceCache.get(path)
  if (device === undefined) return
  const next: BluetoothDevice = { ...device }
  if ("Alias" in changed) next.alias = String(changed.Alias)
  if ("Name" in changed) next.name = String(changed.Name)
  if ("Connected" in changed) next.connected = Boolean(changed.Connected)
  if ("Paired" in changed) next.paired = Boolean(changed.Paired)
  if ("Trusted" in changed) next.trusted = Boolean(changed.Trusted)
  if ("RSSI" in changed) {
    next.rssi = Number(changed.RSSI)
    // The one place a reading is known to be FRESH: BlueZ told us it moved.
    // This is a reception event, not a value change — it is the evidence of
    // presence the whole reachability clock is anchored to.
    next.lastHeardAt = nowMonoMs()
  }
  // BlueZ clearing RSSI: it INVALIDATES the property rather than sending a new
  // value (MEASURED 2026-10-07 — `PropertiesChanged {} INVALIDATED ['RSSI']`).
  // Absence IS the signal, exactly as it is on a re-read: the device's signal
  // is no longer known, so the row must stop claiming it is reachable. Without
  // this the frozen value was served indefinitely, because invalidation used to
  // be dropped before it reached here. `lastHeardAt` is deliberately untouched
  // — being forgotten is not being heard.
  if (invalidated.includes("RSSI")) next.rssi = 0
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
    const device = deviceByAddress(address)
    postBluetoothNotification(
      device?.alias || device?.name || "Bluetooth",
      `${actionLabel(action)} timed out`,
    )
    return false
  })
}

function finishAction(address: string): void {
  if (bluetoothBusy().address !== address) return
  clearWatchdog()
  setBluetoothBusy({ address: null, action: null })
}

/**
 * BlueZ error names → something a person can act on.
 *
 * WHY THIS EXISTS: the failure row used to interpolate the raw D-Bus string, so
 * a failed pairing rendered as
 *
 *   Pairing failed: GDBus.Error:org.bluez.Error.ConnectionAttemptFailed: Page Timeout
 *
 * which is three lines of protocol noise, names an API the user cannot see, and
 * says nothing they can do. MEASURED on a real TOZO NC9 asleep in its case. The
 * mock has always specified the alternative — `popup-failed` says "Pairing timed
 * out", behind a caution glyph.
 *
 * Only the NAME is mapped, because that is the stable machine-readable part; the
 * message string is free-form and can be anything the daemon felt like saying.
 * The raw text is still logged, so the diagnosis survives without being shown.
 */
// Terse on purpose. The failure row is 312px wide with the text wrapping to two
// lines at ~30 characters; the earlier draft ("timed out — the device may be out
// of range or asleep") wrapped to three and was the complaint that prompted this
// table. The row says what happened; the LOG line below says why.
const BLUEZ_ERROR_TEXT: Record<string, string> = {
  ConnectionAttemptFailed: "timed out",
  AuthenticationTimeout: "timed out",
  AuthenticationFailed: "was rejected — wrong PIN or passkey",
  AuthenticationRejected: "was rejected",
  AuthenticationCanceled: "was cancelled",
  AuthenticationRequired: "needs a PIN or passkey",
  NotAvailable: "is not available",
  AlreadyExists: "is already paired",
  InProgress: "is already in progress",
  Rejected: "was rejected",
  NotSupported: "is not supported by this device",
  NotReady: "could not start — adapter not ready",
  Busy: "could not start — adapter is busy",
  NoDefaultAdapter: "could not start — no adapter",
  NotPermitted: "was refused by the system",
  InvalidArguments: "was rejected as invalid",
  Failed: "failed",
}

function humanBusMessage(error: unknown): string {
  const bus = asBusError(error)
  // `dbusName`, NOT `name`: NMBusError sets `name` to the literal "NMBusError"
  // and keeps the remote error in `dbusName`. Reading `.name` here would yield
  // "NMBusError", match nothing in the table, and silently fall through to the
  // raw message — which is the bug this whole function exists to remove.
  const name = bus.dbusName
    .replace(/^org\.bluez\.Error\./, "")
    .replace(/^org\.freedesktop\.DBus\.Error\./, "")
  const mapped = BLUEZ_ERROR_TEXT[name]
  if (mapped !== undefined) return mapped
  // Unmapped: fall back to the daemon's own text with the transport wrapper
  // stripped — never the raw `GDBus.Error:...` form.
  const text = bus.message
    .replace(/^GDBus\.Error:[^:]*:\s*/, "")
    .replace(/^org\.bluez\.Error\.\w+:\s*/, "")
    .trim()
  return text.length > 0 ? text : "failed"
}

/**
 * Post a transient failure card on the session notification surface.
 *
 * PRECEDENT, not invention: this is the capture-tool emission contract
 * (`src/gui-tools/capture-tool/bin/capture-tool`, "Notifications" section) —
 * a one-shot `Notify` on `org.freedesktop.Notifications`, rendered by the
 * session's AGS notifd host. It is deliberately NOT the speedtest/wallpaper
 * domain-event path (`org.dotfiles.Events` + bespoke in-place card): that one
 * exists for live-updating progress, and its gate forbids `Notify` on its own
 * path. A pairing failure is a single transient message — exactly what
 * freedesktop notifications are for — and the success card the user already
 * sees comes down this same wire (Blueman is the sender there).
 *
 * Routed through the `Notifier` port (spine AD-11): the sender posts an intent
 * and no longer constructs the freedesktop call. The transient route (no key, no
 * progress) lands on the freedesktop wire, unchanged: the same app name, icon,
 * summary, body, and timeout.
 *
 * Fire-and-forget, and every failure is swallowed inside the adapter: a toast
 * must never fail an action that already failed. `app` carries the device-facing
 * identity so a missed icon still renders the same initial-letter tile as a
 * connect success; the icon is the absolute path to the rendered ITR glyph — the
 * host only resolves absolute paths to files (`NotificationsWindow.tileContent`
 * lets icon NAMES fall through to that tile), so sending a name would be the
 * same as sending nothing. Resolved through the same registry the panel rows
 * use, never a hardcoded path: a missing render yields no icon and the fallback
 * tile, never a crash.
 */
export function postBluetoothNotification(
  summary: string,
  body: string,
): void {
  // The caution mark — the same glyph the removed in-panel `popup-failed`
  // row drew (`assets/settings-panel-info-caution.svg` in the mock). The card
  // reports a failure, so it wears the failure tint, not the radio's glyph.
  // Same group the rows resolve; a missing render yields the fallback tile,
  // never a crash.
  const icon = registry.resolve("settings-panel", "info-caution")
  notifier.post({
    app: "Bluetooth",
    summary,
    body,
    icon: icon === null ? undefined : { kind: "file", path: icon },
    timeoutMs: 8000,
  })
}

function failAction(
  address: string,
  action: BluetoothAction,
  error: unknown,
): void {
  if (bluetoothBusy().address !== address) return
  clearWatchdog()
  setBluetoothBusy({ address: null, action: null })
  const message = `${actionLabel(action)} ${humanBusMessage(error)}`
  // The raw protocol error is logged even though the user never sees it: this is
  // the only place the underlying cause survives.
  console.error(
    `bluetooth-service: ${action} ${address} -> ${message}` +
      `  [raw: ${asBusError(error).dbusName} ${asBusError(error).message}]`,
  )
  const device = deviceByAddress(address)
  postBluetoothNotification(
    device?.alias || device?.name || "Bluetooth",
    message,
  )
}

async function runAction(
  address: string,
  action: BluetoothAction,
  fn: (device: BluetoothDevice) => Promise<void>,
): Promise<void> {
  if (bluetoothBusy().address !== null) {
    console.error(
      `bluetooth-service: ${action}(${address}) dropped, ${bluetoothBusy().action} already busy`,
    )
    return
  }
  const device = deviceByAddress(address)
  if (device === null) {
    // Was a SILENT return: the row's button no-ops and the user is told
    // nothing at all, which is indistinguishable from a broken button.
    console.error(
      `bluetooth-service: ${action}(${address}) dropped, no such device in the cache`,
    )
    return
  }

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
/**
 * In-flight routing attempts, keyed by device label.
 *
 * WHY THIS EXISTS. `routeAudioToDevice` polls — up to 16 attempts 500 ms apart —
 * because WirePlumber's speaker endpoint lags the BlueZ connect by seconds. Its
 * caller is a `createEffect` over `bluetoothDevices()`, and during an active scan
 * RSSI updates mutate that list constantly, so the effect re-ran on almost every
 * advertisement tick. With no guard, each re-run started ANOTHER 8-second poll
 * and began by calling `setAudioTarget(null)` — so the audio target was being
 * repeatedly nulled while overlapping polls competed to set it. That is the
 * sluggishness reported from the panel.
 *
 * The old comment on that caller claimed "routing is idempotent". It was not,
 * and could not be: the unconditional `setAudioTarget(null)` at the top of this
 * function is the opposite of idempotent.
 *
 * The guard is here rather than at the call site so every caller is protected,
 * including future ones. Re-entry for the SAME label is dropped; a DIFFERENT
 * label still proceeds immediately, because switching the default sink to
 * another device must not queue behind an attempt for the first.
 */
const routeInFlight = new Set<string>()

export async function routeAudioToDevice(label: string): Promise<void> {
  if (label && routeInFlight.has(label)) return
  if (label) routeInFlight.add(label)
  try {
    await routeAudioToDeviceImpl(label)
  } finally {
    if (label) routeInFlight.delete(label)
  }
}

async function routeAudioToDeviceImpl(label: string): Promise<void> {
  //: Clear first, unconditionally: the attempt is unproven until an endpoint
  //: is found and actually defaulted. Setting it after the guards instead
  //: would let the `!wp || !label` bail inherit the PREVIOUS attempt's answer
  //: and report a route that is no longer in effect.
  setAudioTarget(null)
  if (!wp || !label) return
  for (let attempt = 0; attempt < 16; attempt++) {
    const endpoint = (wp.audio?.speakers ?? []).find((speaker) => {
      // No parameter annotation on purpose: AstalWp types these as
      // `string | null`, and a narrower hand-written annotation breaks the
      // `find` overloads (caught by bar-typecheck — `ags bundle` never would).
      const n = speaker.name ?? ""
      const d = speaker.description ?? ""
      return n === label || d === label || n.includes(label) || d.includes(label)
    })
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
 * Reference-counted discovery, keyed by OWNER ID rather than a counter.
 *
 * INVARIANT: `discoveryHolders` is the set of surfaces holding a live
 * `visible`-scoped scan. Each caller passes a stable id for its surface, and
 * both operations are IDEMPOTENT on it.
 *
 * WHY IDEMPOTENT, AND NOT A COUNTER — this is the fix for a MEASURED leak.
 * The previous counter reached 205 on a live session because AGS creates this
 * component's effects outside a `createRoot` and never disposes them (the
 * bar's own log: "effects created outside a `createRoot` will never be
 * disposed"). Every re-render added another live effect that called `start`
 * with no matching `stop`, so the count only ever grew. Two measured
 * consequences: `scanStartedAt` never reset (the count never reached zero), so
 * the grace-on-open never applied and a device would flash reachable then be
 * aged out instantly; and `ageOutStaleReadings` never stopped running.
 *
 * With owner ids, a leaked effect re-acquiring the same surface is a no-op, so
 * the set is bounded by the number of real surfaces (popup + settings subview)
 * no matter how many effects leak. Correctness no longer depends on every
 * cleanup running — which is exactly the assumption the leak invalidated.
 *
 * Deliberately NOT reset by `clearAdapter`: the set tracks mounted surfaces,
 * and an adapter disappearing does not unmount them. Clearing it would orphan
 * a still-visible surface — its later `stop` would find nothing to release and
 * hand the `StopDiscovery` to whichever surface stops next, stopping the scan
 * out from under a live one. Letting it survive costs at most one
 * `StopDiscovery` against a fresh, non-scanning adapter, which BlueZ answers
 * with a swallowed no-op — the cheap direction to be wrong in.
 */
export function startBluetoothDiscovery(owner: string): void {
  //: Idempotent: a leaked effect re-acquiring the same surface changes nothing.
  if (discoveryHolders.has(owner)) return
  //: Anchor the reachability grace to the RUNNING scan, not to each caller.
  //: Only the empty -> non-empty transition resets it: a second surface
  //: joining a scan that is already running must not extend the grace window,
  //: or a stale "in range" would be prolonged every time a panel reopened.
  if (discoveryHolders.size === 0) scanStartedAt = nowMonoMs()
  discoveryHolders.add(owner)
  void runStartDiscovery()
}

async function runStartDiscovery(): Promise<void> {
  const path = adapterPath
  if (path === null || !bluetoothPowered()) return
  //: NO GATE ON `bluetoothDiscovering()` HERE. This used to read
  //: `if (bluetoothDiscovering()) return`, on the reasoning that re-issuing
  //: `StartDiscovery` to an already-scanning adapter was merely redundant.
  //: It was not redundant, it was load-bearing in the wrong direction:
  //: `bluetoothDiscovering` is a LOCAL MIRROR of BlueZ's `Discovering`
  //: property, seeded at module load and thereafter updated only from
  //: PropertiesChanged notifications -- it is never re-read from BlueZ.
  //:
  //: MEASURED on this machine: `StopDiscovery` answers "No discovery started"
  //: while `Discovering` simultaneously reads 1. The mirror and the adapter
  //: desync. Once the mirror stuck at `true`, every `startBluetoothDiscovery`
  //: short-circuited, `StartDiscovery` was NEVER issued again, and the panel
  //: could not discover anything for the rest of the session. The only thing
  //: that recovered it was toggling the adapter's power, because that forces
  //: BlueZ to re-emit `Discovering` and resets the mirror -- which is exactly
  //: why the reported workaround was "I have to toggle enable/disable bt".
  //:
  //: Balance is unaffected. `StartDiscovery`/`StopDiscovery` are refcounted by
  //: BlueZ per connection, and the holder set here is acquired per surface
  //: unconditionally and decremented by exactly one matching `stop` from each
  //: surface's own effect cleanup. So issuing a start per surface-open keeps
  //: BlueZ's count equal to ours, which is strictly better than skipping it:
  //: the old gate let BlueZ's count run LOWER than ours, so the first surface
  //: to hide stopped the scan out from under a surface that was still visible.
  //: The mirror is still worth keeping -- it drives the UI's scanning
  //: indicator -- it just must not decide whether to scan.

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

export function stopBluetoothDiscovery(owner: string): void {
  //: Idempotent release: an unknown owner (or a repeated stop from a leaked
  //: cleanup) is a no-op, never a decrement of somebody else's hold.
  if (!discoveryHolders.delete(owner)) return
  //: Other surfaces are still visible and still want the scan. This is the
  //: popup-close-racing-panel-open case: without the set, the popup's cleanup
  //: would stop a scan the subview had just started.
  if (discoveryHolders.size > 0) return
  //: The scan run is over. The reachability clock refuses to run without one
  //: (see `ageOutStaleReadings`), so this only clears stale bookkeeping — a
  //: closed panel must never age a device out on the strength of its own
  //: silence.
  scanStartedAt = 0
  //: Guarded on the adapter, not the count: no holders means "stop it", and
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
    postBluetoothNotification(
      "Bluetooth",
      "No Bluetooth adapter available",
    )
    return
  }
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
    postBluetoothNotification(
      "Bluetooth",
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
    console.error(
      `bluetooth-service: Adapter1.RemoveDevice(${device.path}) via ${path}`,
    )
    await call(
      BLUEZ,
      path,
      ADAPTER_IFACE,
      "RemoveDevice",
      new GLib.Variant("(o)", [device.path]),
    )
    console.error(`bluetooth-service: RemoveDevice returned for ${address}`)
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
  bluetoothPowered,
  bluetoothReady,
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
