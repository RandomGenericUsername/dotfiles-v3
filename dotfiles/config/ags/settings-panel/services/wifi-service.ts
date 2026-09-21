import GLib from "gi://GLib?version=2.0"
import { createComputed, createState } from "ags"
import {
  DBUS_PROPERTIES_IFACE,
  NM,
  NM_ACCESS_POINT_IFACE,
  NM_CONNECTION_IFACE,
  NM_DEVICE_IFACE,
  NM_MANAGER_PATH,
  NM_SETTINGS_IFACE,
  NM_SETTINGS_PATH,
  NM_WIRELESS_IFACE,
  asBusError,
  call,
  getAll,
  subscribe,
  watchProperties,
} from "./nm-client"

/**
 * NetworkManager Wi-Fi service (design §2).
 *
 * NetworkManager D-Bus is the single source of truth: device discovery, the
 * access-point model, scanning, saved-profile lookup, activation and the
 * one-flight connect state machine all live here. The UI is a thin view over
 * the exported accessors and actions — no subprocess, no blocking bus call.
 */

//: org.freedesktop.NetworkManager.DeviceType
const DEVICE_TYPE_WIFI = 2

//: org.freedesktop.NetworkManager.Connection.Active
const NM_ACTIVE_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Connection.Active"

//: opt-in tracing (`AGS_WIFI_DEBUG=1`) — the bar logs it to its instance log.
const DEBUG = GLib.getenv("AGS_WIFI_DEBUG") === "1"
function log(message: string): void {
  if (DEBUG) console.log(`wifi-service: ${message}`)
}

//: org.freedesktop.NetworkManager.DeviceState
const DEVICE_STATE_UNAVAILABLE = 20
const DEVICE_STATE_DISCONNECTED = 30
const DEVICE_STATE_PREPARE = 40
const DEVICE_STATE_CONFIG = 50
const DEVICE_STATE_NEED_AUTH = 60
const DEVICE_STATE_IP_CONFIG = 70
const DEVICE_STATE_ACTIVATED = 100
const DEVICE_STATE_DEACTIVATING = 110
const DEVICE_STATE_FAILED = 120

//: org.freedesktop.NetworkManager.DeviceStateReason
const REASON_NO_SECRETS = 7
const REASON_SUPPLICANT_DISCONNECT = 8
const REASON_SUPPLICANT_CONFIG_FAILED = 9
const REASON_SUPPLICANT_FAILED = 10
const REASON_SUPPLICANT_TIMEOUT = 11
const REASON_DHCP_START_FAILED = 15
const REASON_DHCP_ERROR = 16
const REASON_DHCP_FAILED = 17
const REASON_REMOVED = 19

const SCAN_INTERVAL_MS = 6000
const AP_REFRESH_DEBOUNCE_MS = 250
const WATCHDOG_MS = 45000
//: NetworkManager flashes NEED_AUTH (60) even for a saved profile that has
//: stored secrets — it then immediately finds them and continues. Only treat
//: need-auth as a real prompt when the device is still there after this grace.
const NEED_AUTH_GRACE_MS = 1500
//: Upper bound on waiting for the previous connection to deactivate before a
//: switch; after this we activate anyway and let NetworkManager arbitrate.
const DISCONNECT_WAIT_MS = 8000
//: Drop an AP whose `LastSeen` trails the newest by more than this, so a
//: switched-off hotspot disappears instead of lingering in NM's cache.
const STALE_AP_SECONDS = 12

export type WifiPhase =
  | "idle"
  | "preparing"
  | "needAuth"
  | "activating"
  | "failed"

export interface WifiConnectState {
  phase: WifiPhase
  ssid: string | null
  reason: string | null
}

export interface WifiNetwork {
  ssid: string
  strength: number
  secured: boolean
  connected: boolean
  saved: boolean
}

interface ApInfo {
  path: string
  ssid: string
  strength: number
  secured: boolean
  //: NetworkManager `LastSeen` (CLOCK_BOOTTIME seconds) — used to drop APs that
  //: vanished but linger in NM's cache (a switched-off hotspot must not stay
  //: clickable). Relative lag vs. the newest AP is clock-independent.
  lastSeen: number
}

interface StateWaiter {
  test: (state: number) => boolean
  resolve: () => void
  reject: (error: Error) => void
}

const [wifiNetworks, setWifiNetworks] = createState<WifiNetwork[]>([])
const [wirelessEnabled, setWirelessEnabled] = createState(false)
const [wirelessHardwareEnabled, setWirelessHardwareEnabled] = createState(true)
const [connectState, setConnectState] = createState<WifiConnectState>({
  phase: "idle",
  ssid: null,
  reason: null,
})

const wifiEnabled = createComputed(
  () => wirelessEnabled() && wirelessHardwareEnabled(),
)

// ── Mutable service state ────────────────────────────────────────────────

let devicePath: string | null = null
let activeConnectionPath: string | null = null
let activeApPath: string | null = null
//: The active-connection object exposes its settings profile (`Connection`,
//: an `/Settings/N` path to match against `savedWifi`) and its associated AP
//: (`SpecificObject`). Resolving through these is authoritative; the device's
//: `ActiveAccessPoint` is only a fallback.
let activeSettingsPath: string | null = null
let activeSpecificApPath: string | null = null
let lastDeviceState = 0

let unwatchDevice: (() => void) | null = null
let unwatchWireless: (() => void) | null = null
let unwatchDeviceSignals: Array<() => void> = []

const apCache = new Map<string, ApInfo>()
let savedWifi = new Map<string, string>()

let waiters: StateWaiter[] = []

//: One connect attempt may be in flight; every user intent gets a fresh
//: generation so a superseded promise chain can never mutate state.
let generation = 0

let watchdogId = 0
//: Deferred need-auth decision (see NEED_AUTH_GRACE_MS) and the SSID it is for.
let needAuthTimerId = 0
let pendingAuthSsid: string | null = null
let lastLoggedActiveSsid: string | null = null

let scanning = false
let scanTimerId = 0
let apRefreshTimerId = 0

//: NetworkManager briefly reports an empty access-point list while the device
//: deactivates/re-associates during a network switch. A single empty read is
//: therefore not authoritative — only a sustained empty read is.
let emptyApReads = 0

// ── AP / SSID helpers ────────────────────────────────────────────────────

function encodeSsid(text: string): Uint8Array {
  if (typeof TextEncoder === "function") return new TextEncoder().encode(text)
  const out = new Uint8Array(text.length)
  for (let i = 0; i < text.length; i++) out[i] = text.charCodeAt(i) & 0xff
  return out
}

function decodeSsid(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value
  let bytes: Uint8Array | null = null
  if (value instanceof Uint8Array) bytes = value
  else if (value instanceof ArrayBuffer) bytes = new Uint8Array(value)
  else if (Array.isArray(value)) bytes = Uint8Array.from(value as number[])
  else if (typeof value === "object") {
    const toArray = (value as { toArray?: () => number[] }).toArray
    if (typeof toArray === "function") bytes = Uint8Array.from(toArray())
  }
  if (bytes === null) return ""
  try {
    if (typeof TextDecoder === "function") return new TextDecoder("utf-8").decode(bytes)
    let out = ""
    for (let i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i])
    return out
  } catch {
    return ""
  }
}

function clampStrength(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

function isSecured(props: Record<string, unknown>): boolean {
  const flags = Number(props.Flags ?? 0)
  const wpa = Number(props.WpaFlags ?? 0)
  const rsn = Number(props.RsnFlags ?? 0)
  return (flags & 0x1) !== 0 || wpa !== 0 || rsn !== 0
}

function normalizePath(value: unknown): string | null {
  if (typeof value !== "string" || value === "" || value === "/") return null
  return value
}

function reasonToMessage(reason: number): string {
  switch (reason) {
    case REASON_NO_SECRETS:
      return "Authentication required"
    case REASON_SUPPLICANT_DISCONNECT:
    case REASON_SUPPLICANT_FAILED:
      return "Incorrect password or authentication failed"
    case REASON_SUPPLICANT_CONFIG_FAILED:
      return "Wi-Fi authentication could not be configured"
    case REASON_SUPPLICANT_TIMEOUT:
      return "Authentication timed out"
    case 4:
      return "Connection failed to configure"
    case 5:
    case 6:
    case REASON_DHCP_START_FAILED:
    case REASON_DHCP_ERROR:
    case REASON_DHCP_FAILED:
      return "Could not obtain an IP address"
    case REASON_REMOVED:
      return "Network is no longer available"
    default:
      return "Connection failed"
  }
}

// ── Device-state waiters ─────────────────────────────────────────────────

function waitForDeviceState(test: (state: number) => boolean): Promise<void> {
  if (test(lastDeviceState)) return Promise.resolve()
  return new Promise((resolve, reject) => {
    waiters.push({ test, resolve, reject })
  })
}

/**
 * Wait until the device matches `test`, but PROCEED after `timeoutMs` instead of
 * hanging. Used before a switch so an unavailable/never-30 device cannot stall
 * the whole attempt until the watchdog; NetworkManager arbitrates the rest.
 */
function waitForDeviceStateOrTimeout(
  test: (state: number) => boolean,
  timeoutMs: number,
): Promise<void> {
  if (test(lastDeviceState)) return Promise.resolve()
  return new Promise((resolve) => {
    const waiter: StateWaiter = {
      test,
      resolve,
      reject: () => resolve(),
    }
    waiters.push(waiter)
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeoutMs, () => {
      const index = waiters.indexOf(waiter)
      if (index >= 0) waiters.splice(index, 1)
      resolve()
      return false
    })
  })
}

function resolveWaiters(state: number): void {
  if (waiters.length === 0) return
  const pending = waiters
  waiters = []
  for (const waiter of pending) {
    if (waiter.test(state)) waiter.resolve()
    else waiters.push(waiter)
  }
}

function rejectWaiters(error: Error): void {
  const pending = waiters
  waiters = []
  for (const waiter of pending) waiter.reject(error)
}

function setLastDeviceState(state: number): void {
  lastDeviceState = state
  resolveWaiters(state)
}

// ── Watchdog (the only connect timer) ────────────────────────────────────

function clearWatchdog(): void {
  if (watchdogId === 0) return
  try {
    GLib.source_remove(watchdogId)
  } catch {
    /* already removed */
  }
  watchdogId = 0
}

function startWatchdog(gen: number, ssid: string): void {
  clearWatchdog()
  watchdogId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, WATCHDOG_MS, () => {
    watchdogId = 0
    if (gen !== generation) return false
    generation++
    rejectWaiters(new Error("timed out"))
    setConnectState({ phase: "failed", ssid, reason: "Connection timed out" })
    return false
  })
}

// ── Deferred need-auth prompt ────────────────────────────────────────────

function clearNeedAuthTimer(): void {
  if (needAuthTimerId !== 0) {
    try {
      GLib.source_remove(needAuthTimerId)
    } catch {
      /* already removed */
    }
    needAuthTimerId = 0
  }
  pendingAuthSsid = null
}

/**
 * NetworkManager reports NEED_AUTH for a saved profile that has stored secrets
 * too — it then finds them and continues within milliseconds. Prompting on the
 * raw signal locked the row and hid the list. So defer: prompt only if the
 * device is STILL in need-auth after the grace window.
 */
function scheduleNeedAuthPrompt(ssid: string | null): void {
  if (pendingAuthSsid === ssid && needAuthTimerId !== 0) return
  clearNeedAuthTimer()
  pendingAuthSsid = ssid
  needAuthTimerId = GLib.timeout_add(
    GLib.PRIORITY_DEFAULT,
    NEED_AUTH_GRACE_MS,
    () => {
      needAuthTimerId = 0
      const state = connectState()
      const stillPending =
        state.phase === "preparing" || state.phase === "activating"
      if (!stillPending || ssid === null || state.ssid !== ssid) return false
      if (lastDeviceState !== DEVICE_STATE_NEED_AUTH) return false
      generation++
      clearWatchdog()
      log(`need-auth prompt for ${ssid}`)
      setConnectState({ phase: "needAuth", ssid, reason: null })
      return false
    },
  )
}

// ── Derived AP list ──────────────────────────────────────────────────────

function currentConnectedSsid(): string | null {
  // Nothing is "connected" until the device reports ACTIVATED. Without this, a
  // just-requested activation (whose active-connection object exists before the
  // handshake completes) would light up the Connected badge prematurely.
  if (lastDeviceState !== DEVICE_STATE_ACTIVATED) return null
  // The active connection is authoritative for "which network are we on":
  // its specific AP, then its settings profile (matched against savedWifi),
  // then the device's ActiveAccessPoint as a fallback (its property change can
  // be missed, leaving a stale AP path that reports the previous network).
  if (activeSpecificApPath !== null) {
    const ap = apCache.get(activeSpecificApPath)
    if (ap !== undefined) return ap.ssid
  }
  if (activeSettingsPath !== null) {
    for (const [ssid, path] of savedWifi) {
      if (path === activeSettingsPath) return ssid
    }
  }
  if (activeApPath !== null) {
    const ap = apCache.get(activeApPath)
    if (ap !== undefined) return ap.ssid
  }
  if (activeConnectionPath !== null) {
    for (const [ssid, path] of savedWifi) {
      if (path === activeConnectionPath) return ssid
    }
  }
  return null
}

function representativeAp(ssid: string): ApInfo | null {
  let best: ApInfo | null = null
  for (const ap of apCache.values()) {
    if (ap.ssid !== ssid) continue
    if (best === null) {
      best = ap
      continue
    }
    if (ap.path === activeApPath) {
      best = ap
      continue
    }
    if (best.path !== activeApPath && ap.strength > best.strength) best = ap
  }
  return best
}

function applyNetworks(): void {
  const activeSsid = currentConnectedSsid()
  if (activeSsid !== lastLoggedActiveSsid) {
    lastLoggedActiveSsid = activeSsid
    log(`connected ssid -> ${activeSsid ?? "none"} (activeAp=${activeApPath ?? "none"} activeConn=${activeConnectionPath ?? "none"})`)
  }
  const bySsid = new Map<string, ApInfo>()
  for (const ap of apCache.values()) {
    const existing = bySsid.get(ap.ssid)
    if (existing === undefined) {
      bySsid.set(ap.ssid, ap)
      continue
    }
    if (ap.path === activeApPath) {
      bySsid.set(ap.ssid, ap)
      continue
    }
    if (existing.path !== activeApPath && ap.strength > existing.strength) {
      bySsid.set(ap.ssid, ap)
    }
  }

  const list: WifiNetwork[] = []
  for (const ap of bySsid.values()) {
    list.push({
      ssid: ap.ssid,
      strength: ap.strength,
      secured: ap.secured,
      connected: ap.ssid === activeSsid,
      saved: savedWifi.has(ap.ssid),
    })
  }
  list.sort((a, b) => {
    if (a.connected !== b.connected) return a.connected ? -1 : 1
    if (a.saved !== b.saved) return a.saved ? -1 : 1
    return b.strength - a.strength
  })
  setWifiNetworks(list)
}

// ── Bus reads ────────────────────────────────────────────────────────────

/**
 * Resolve the device's active connection to its settings profile and AP. The
 * `ActiveConnection` path is an `/ActiveConnection/N` object; matching it
 * directly against `savedWifi` (which holds `/Settings/N` paths) never worked,
 * so the connected SSID was derived only from the (sometimes stale) AP path.
 */
async function resolveActiveConnection(connPath: string | null): Promise<void> {
  activeConnectionPath = connPath
  activeSettingsPath = null
  activeSpecificApPath = null
  if (connPath === null) {
    applyNetworks()
    return
  }
  try {
    const ac = await getAll(connPath, NM_ACTIVE_CONNECTION_IFACE)
    if (activeConnectionPath !== connPath) return
    activeSettingsPath = normalizePath(ac.Connection)
    activeSpecificApPath = normalizePath(ac.SpecificObject)
  } catch {
    /* active connection vanished */
  }
  applyNetworks()
}

async function refreshManager(): Promise<void> {
  try {
    const props = await getAll(NM_MANAGER_PATH, NM)
    setWirelessEnabled(Boolean(props.WirelessEnabled))
    setWirelessHardwareEnabled(Boolean(props.WirelessHardwareEnabled))
  } catch (error) {
    console.error(`wifi-service: manager read failed: ${error}`)
  }
}

async function refreshDeviceProps(): Promise<void> {
  const path = devicePath
  if (path === null) return
  try {
    const props = await getAll(path, NM_DEVICE_IFACE)
    if (path !== devicePath) return
    setLastDeviceState(Number(props.State ?? 0))
    await resolveActiveConnection(normalizePath(props.ActiveConnection))
  } catch {
    /* device vanished */
  }
  try {
    const wireless = await getAll(path, NM_WIRELESS_IFACE)
    if (path !== devicePath) return
    activeApPath = normalizePath(wireless.ActiveAccessPoint)
  } catch {
    /* device vanished */
  }
  applyNetworks()
}

async function refreshAccessPoints(): Promise<void> {
  const path = devicePath
  if (path === null) {
    applyNetworks()
    return
  }

  let apPaths: string[] = []
  try {
    const reply = await call(NM, path, NM_WIRELESS_IFACE, "GetAccessPoints", null)
    apPaths = reply.recursiveUnpack()[0] as string[]
  } catch {
    return
  }

  const read: ApInfo[] = []
  for (const apPath of apPaths) {
    try {
      const props = await getAll(apPath, NM_ACCESS_POINT_IFACE)
      const ssid = decodeSsid(props.Ssid)
      if (ssid === "") continue
      read.push({
        path: apPath,
        ssid,
        strength: clampStrength(Number(props.Strength ?? 0)),
        secured: isSecured(props),
        lastSeen: Number(props.LastSeen ?? 0),
      })
    } catch {
      /* AP disappeared mid-read */
    }
  }

  // Drop APs NM still reports but that have not been seen recently (a hotspot
  // switched off lingers in NM's cache for tens of seconds). The AP we are
  // associated with is always kept.
  const newestLastSeen = read.reduce((max, ap) => Math.max(max, ap.lastSeen), 0)
  const active = activeSpecificApPath ?? activeApPath
  const next = new Map<string, ApInfo>()
  for (const ap of read) {
    const isActive = active !== null && ap.path === active
    if (
      !isActive &&
      newestLastSeen > 0 &&
      ap.lastSeen > 0 &&
      newestLastSeen - ap.lastSeen > STALE_AP_SECONDS
    ) {
      continue
    }
    next.set(ap.path, ap)
  }

  if (path !== devicePath) return

  emptyApReads = next.size === 0 ? emptyApReads + 1 : 0
  const connecting =
    connectState().phase === "preparing" || connectState().phase === "activating"

  // A transient empty read (device mid-association) must not blank the view;
  // keep the last good list and let the next scan correct it. Never blank while
  // a connect/switch is in flight, and treat a sustained empty read as real so
  // vanished networks still drop promptly.
  if (next.size === 0 && apCache.size > 0 && (connecting || emptyApReads < 2)) {
    return
  }

  apCache.clear()
  for (const [key, value] of next) apCache.set(key, value)
  applyNetworks()
}

async function refreshSavedConnections(): Promise<void> {
  try {
    const reply = await call(NM, NM_SETTINGS_PATH, NM_SETTINGS_IFACE, "ListConnections", null)
    const paths = reply.recursiveUnpack()[0] as string[]
    const next = new Map<string, string>()
    for (const path of paths) {
      try {
        const settingsReply = await call(NM, path, NM_CONNECTION_IFACE, "GetSettings", null)
        const unpacked = settingsReply.recursiveUnpack() as [
          Record<string, Record<string, unknown>>,
        ]
        const settings = unpacked[0]
        const connection = settings?.["connection"]
        if (!connection || connection.type !== "802-11-wireless") continue
        const ssid = decodeSsid(settings["802-11-wireless"]?.ssid)
        if (ssid !== "") next.set(ssid, path)
      } catch {
        /* profile vanished mid-read */
      }
    }
    savedWifi = next
    applyNetworks()
  } catch (error) {
    console.error(`wifi-service: saved-connection refresh failed: ${error}`)
  }
}

// ── Subscriptions ────────────────────────────────────────────────────────

function applyDeviceProps(changed: Record<string, unknown>): void {
  if ("State" in changed) setLastDeviceState(Number(changed.State))
  if ("ActiveConnection" in changed) {
    void resolveActiveConnection(normalizePath(changed.ActiveConnection))
  }
}

function handleStateChanged(newState: number, reason: number): void {
  setLastDeviceState(newState)
  const state = connectState()
  log(`state ${newState} reason ${reason} phase ${state.phase} ssid ${state.ssid}`)
  const inFlight =
    state.phase === "preparing" ||
    state.phase === "activating" ||
    state.phase === "needAuth"
  if (!inFlight) return

  // Any real progress means the attempt is alive: drop a lingering need-auth
  // prompt decision and resume the activating phase.
  if (newState === DEVICE_STATE_ACTIVATED) {
    generation++
    clearWatchdog()
    clearNeedAuthTimer()
    setConnectState({ phase: "idle", ssid: null, reason: null })
    // Re-resolve which network is actually active so the list/row badges are
    // correct immediately (not only after the next scan).
    void refreshDeviceProps()
    return
  }
  if (newState === DEVICE_STATE_NEED_AUTH) {
    // Deferred: only becomes a prompt if the device is still here after the
    // grace window (a saved profile flash-resolves its stored secrets).
    scheduleNeedAuthPrompt(state.ssid)
    return
  }
  if (
    newState === DEVICE_STATE_PREPARE ||
    newState === DEVICE_STATE_CONFIG ||
    newState === DEVICE_STATE_IP_CONFIG ||
    newState === DEVICE_STATE_DEACTIVATING
  ) {
    clearNeedAuthTimer()
    if (state.phase === "needAuth" || state.phase === "preparing") {
      setConnectState({ phase: "activating", ssid: state.ssid, reason: null })
    }
    return
  }
  if (newState === DEVICE_STATE_FAILED) {
    clearNeedAuthTimer()
    if (reason === REASON_NO_SECRETS) {
      generation++
      clearWatchdog()
      setConnectState({ phase: "needAuth", ssid: state.ssid, reason: null })
      return
    }
    failAttempt(state.ssid, reasonToMessage(reason))
  }
}

function clearDeviceSubscriptions(): void {
  if (unwatchDevice !== null) {
    unwatchDevice()
    unwatchDevice = null
  }
  if (unwatchWireless !== null) {
    unwatchWireless()
    unwatchWireless = null
  }
  for (const off of unwatchDeviceSignals) off()
  unwatchDeviceSignals = []
}

function installDeviceSubscriptions(path: string): void {
  unwatchDevice = watchProperties(path, NM_DEVICE_IFACE, (changed) =>
    applyDeviceProps(changed),
  )
  unwatchWireless = watchProperties(path, NM_WIRELESS_IFACE, (changed) => {
    if ("LastScan" in changed) {
      void refreshAccessPoints()
    }
    if ("ActiveAccessPoint" in changed) {
      activeApPath = normalizePath(changed.ActiveAccessPoint)
      applyNetworks()
    }
  })
  unwatchDeviceSignals = [
    subscribe(NM, path, NM_DEVICE_IFACE, "StateChanged", (parameters) => {
      const unpacked = parameters.recursiveUnpack() as [number, number, number]
      handleStateChanged(Number(unpacked[0]), Number(unpacked[2] ?? 0))
    }),
    subscribe(NM, path, NM_WIRELESS_IFACE, "AccessPointAdded", () =>
      scheduleApRefresh(),
    ),
    subscribe(NM, path, NM_WIRELESS_IFACE, "AccessPointRemoved", () =>
      scheduleApRefresh(),
    ),
  ]
}

async function resolveDevice(): Promise<void> {
  let devices: string[] = []
  try {
    const reply = await call(NM, NM_MANAGER_PATH, NM, "GetDevices", null)
    devices = reply.recursiveUnpack()[0] as string[]
  } catch (error) {
    console.error(`wifi-service: GetDevices failed: ${error}`)
    return
  }

  let found: string | null = null
  let readFailed = false
  for (const path of devices) {
    try {
      const props = await getAll(path, NM_DEVICE_IFACE)
      if (Number(props.DeviceType) === DEVICE_TYPE_WIFI) {
        found = path
        break
      }
    } catch {
      //: A transient read failure must not be mistaken for "no Wi-Fi device".
      readFailed = true
    }
  }

  if (found === null && readFailed) {
    //: We could not determine the device list — keep the current device rather
    //: than tearing it down and blanking the network list.
    return
  }

  if (found === devicePath) {
    if (found !== null) await refreshDeviceProps()
    return
  }

  clearDeviceSubscriptions()
  devicePath = found
  activeConnectionPath = null
  activeApPath = null
  activeSettingsPath = null
  activeSpecificApPath = null
  apCache.clear()

  if (found === null) {
    setWifiNetworks([])
    return
  }

  await refreshDeviceProps()
  installDeviceSubscriptions(found)
  await refreshAccessPoints()
}

// ── AP-signal debounce / scan cadence ────────────────────────────────────

function scheduleApRefresh(): void {
  if (apRefreshTimerId !== 0) return
  apRefreshTimerId = GLib.timeout_add(
    GLib.PRIORITY_DEFAULT,
    AP_REFRESH_DEBOUNCE_MS,
    () => {
      apRefreshTimerId = 0
      void refreshAccessPoints()
      return false
    },
  )
}

function scheduleScan(): void {
  if (!scanning || scanTimerId !== 0) return
  scanTimerId = GLib.timeout_add(
    GLib.PRIORITY_DEFAULT,
    SCAN_INTERVAL_MS,
    () => {
      scanTimerId = 0
      if (!scanning) return false
      void requestScan()
      scheduleScan()
      return false
    },
  )
}

async function requestScan(): Promise<void> {
  const path = devicePath
  if (path === null) return
  const state = connectState()
  if (state.phase === "preparing" || state.phase === "activating") return

  try {
    await call(
      NM,
      path,
      NM_WIRELESS_IFACE,
      "RequestScan",
      new GLib.Variant("(a{sv})", [{}]),
      8000,
    )
  } catch {
    //: NM throttles rapid scans; the cached list is still authoritative.
  }
  if (path !== devicePath) return
  await refreshAccessPoints()
}

// ── Activation ───────────────────────────────────────────────────────────

function buildWirelessSettings(
  ssid: string,
  password: string,
): Record<string, Record<string, GLib.Variant>> {
  const settings: Record<string, Record<string, GLib.Variant>> = {
    connection: {
      id: new GLib.Variant("s", ssid),
      type: new GLib.Variant("s", "802-11-wireless"),
    },
    "802-11-wireless": {
      ssid: new GLib.Variant("ay", encodeSsid(ssid)),
      mode: new GLib.Variant("s", "infrastructure"),
    },
  }
  if (password !== "") {
    settings["802-11-wireless-security"] = {
      "key-mgmt": new GLib.Variant("s", "wpa-psk"),
      psk: new GLib.Variant("s", password),
    }
  }
  return settings
}

function isSecretsError(error: { dbusName: string; message: string }): boolean {
  const name = error.dbusName.toLowerCase()
  const message = error.message.toLowerCase()
  return name.includes("secret") || message.includes("secrets")
}

function failAttempt(ssid: string | null, message: string): void {
  generation++
  clearWatchdog()
  clearNeedAuthTimer()
  setConnectState({ phase: "failed", ssid, reason: message })
}

async function prepareSwitch(gen: number, targetSsid: string): Promise<void> {
  if (currentConnectedSsid() === targetSsid) return
  const active = activeConnectionPath
  if (active === null) return

  log(`deactivate ${active} to switch to ${targetSsid}`)
  try {
    await call(NM, NM_MANAGER_PATH, NM, "DeactivateConnection", new GLib.Variant("(o)", [active]))
  } catch {
    //: Already gone / not deactivatable — activation below is authoritative.
  }
  if (gen !== generation) return
  // Proceed once the device is no longer on the old connection. Waiting for
  // exactly DISCONNECTED can miss the state (autoconnect races) or never come
  // (device went UNAVAILABLE); the bounded wait keeps the switch moving.
  await waitForDeviceStateOrTimeout(
    (state) =>
      state === DEVICE_STATE_DISCONNECTED ||
      state === DEVICE_STATE_UNAVAILABLE ||
      state === DEVICE_STATE_FAILED,
    DISCONNECT_WAIT_MS,
  )
}

async function runActivate(ssid: string, password?: string): Promise<void> {
  const gen = ++generation
  clearWatchdog()
  clearNeedAuthTimer()
  log(`request "${ssid}" current=${currentConnectedSsid() ?? "none"} device=${devicePath ?? "none"} ap=${representativeAp(ssid)?.path ?? "missing"}`)
  setConnectState({ phase: "preparing", ssid, reason: null })

  if (devicePath === null) {
    await resolveDevice().catch(() => {})
    if (gen !== generation) return
  }
  if (devicePath === null) {
    failAttempt(ssid, "No Wi-Fi device")
    return
  }

  if (currentConnectedSsid() === ssid) {
    clearWatchdog()
    setConnectState({ phase: "idle", ssid: null, reason: null })
    return
  }

  const ap = representativeAp(ssid)
  if (ap === null) {
    failAttempt(ssid, `"${ssid}" is not available`)
    return
  }

  const saved = savedWifi.get(ssid) ?? null
  log(`activate ${ssid} saved=${saved ?? "none"} secured=${ap.secured}`)
  if (saved === null && ap.secured && (password === undefined || password === "")) {
    clearWatchdog()
    setConnectState({ phase: "needAuth", ssid, reason: null })
    return
  }

  startWatchdog(gen, ssid)
  try {
    await prepareSwitch(gen, ssid)
    if (gen !== generation) return
    setConnectState({ phase: "activating", ssid, reason: null })

    //: A saved profile with no user-supplied secret activates by its existing
    //: connection object. Anything else (new network, or a secret the user just
    //: typed for a saved profile) goes through AddAndActivateConnection, which
    //: reuses/updates the matching profile the same way the NetworkManager CLI
    //: does.
    const useSaved = saved !== null && (password === undefined || password === "")
    if (useSaved) {
      const reply = await call(
        NM,
        NM_MANAGER_PATH,
        NM,
        "ActivateConnection",
        new GLib.Variant("(ooo)", [saved, devicePath, ap.path]),
      )
      const unpacked = reply.recursiveUnpack() as [string]
      await resolveActiveConnection(normalizePath(unpacked[0]))
    } else {
      const settings = buildWirelessSettings(ssid, password ?? "")
      const reply = await call(
        NM,
        NM_MANAGER_PATH,
        NM,
        "AddAndActivateConnection",
        new GLib.Variant("(a{sa{sv}}oo)", [settings, devicePath, ap.path]),
      )
      const unpacked = reply.recursiveUnpack() as [string, string]
      if (unpacked[0]) savedWifi.set(ssid, unpacked[0])
      await resolveActiveConnection(normalizePath(unpacked[1]))
    }

    if (gen !== generation) return
    if (lastDeviceState === DEVICE_STATE_ACTIVATED) {
      generation++
      clearWatchdog()
      setConnectState({ phase: "idle", ssid: null, reason: null })
    }
    //: Otherwise StateChanged drives the terminal transition, or the watchdog fires.
  } catch (error) {
    if (gen !== generation) return
    const busError = asBusError(error)
    if (isSecretsError(busError)) {
      clearWatchdog()
      setConnectState({ phase: "needAuth", ssid, reason: null })
      return
    }
    failAttempt(ssid, busError.message)
  }
}

// ── Public API ───────────────────────────────────────────────────────────

export function activate(ssid: string, password?: string): void {
  void runActivate(ssid, password)
}

export function submitPassword(password: string): void {
  const state = connectState()
  if (state.phase !== "needAuth" || state.ssid === null) return
  void runActivate(state.ssid, password)
}

export function cancel(): void {
  generation++
  clearWatchdog()
  clearNeedAuthTimer()
  rejectWaiters(new Error("cancelled"))
  setConnectState({ phase: "idle", ssid: null, reason: null })
}

export function startScanning(): void {
  if (scanning) return
  scanning = true
  void requestScan()
  scheduleScan()
}

export function stopScanning(): void {
  scanning = false
  if (scanTimerId !== 0) {
    try {
      GLib.source_remove(scanTimerId)
    } catch {
      /* already removed */
    }
    scanTimerId = 0
  }
}

/** Power toggle (manager `WirelessEnabled`), kept here so the UI stays thin. */
export async function setWifiEnabled(enabled: boolean): Promise<void> {
  try {
    await call(
      NM,
      NM_MANAGER_PATH,
      DBUS_PROPERTIES_IFACE,
      "Set",
      new GLib.Variant("(ssv)", [NM, "WirelessEnabled", new GLib.Variant("b", enabled)]),
    )
  } catch (error) {
    console.error(`wifi-service: setting WirelessEnabled failed: ${error}`)
  }
}

export function toggleWifi(): void {
  void setWifiEnabled(!wifiEnabled())
}

export { connectState, wifiEnabled, wifiNetworks }

/** Opt-in tracing hook (`AGS_WIFI_DEBUG=1`) for the thin UI layer. */
export function wifiLog(message: string): void {
  log(message)
}

// ── Bootstrap ────────────────────────────────────────────────────────────

let started = false

async function bootstrap(): Promise<void> {
  await refreshManager()
  subscribe(NM, NM_MANAGER_PATH, NM, "DeviceAdded", () => {
    void resolveDevice()
  })
  subscribe(NM, NM_MANAGER_PATH, NM, "DeviceRemoved", () => {
    void resolveDevice()
  })
  subscribe(NM, NM_SETTINGS_PATH, NM_SETTINGS_IFACE, "ConnectionAdded", () => {
    void refreshSavedConnections()
  })
  subscribe(NM, NM_SETTINGS_PATH, NM_SETTINGS_IFACE, "ConnectionRemoved", () => {
    void refreshSavedConnections()
  })
  watchProperties(NM_MANAGER_PATH, NM, (changed) => {
    if ("WirelessEnabled" in changed) {
      setWirelessEnabled(Boolean(changed.WirelessEnabled))
    }
    if ("WirelessHardwareEnabled" in changed) {
      setWirelessHardwareEnabled(Boolean(changed.WirelessHardwareEnabled))
    }
  })
  await resolveDevice()
  await refreshSavedConnections()
}

function start(): void {
  if (started) return
  started = true
  void bootstrap().catch((error) =>
    console.error(`wifi-service: bootstrap failed: ${error}`),
  )
}

start()
