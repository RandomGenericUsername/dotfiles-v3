import Network from "gi://AstalNetwork"
import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { Accessor, createBinding, createComputed, createEffect, createState } from "ags"
import { execAsync } from "ags/process"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { CapabilityTile, IconToggle } from "../primitives"
import { show } from "../state"

/**
 * Wi-Fi control.
 *
 * Reads are reactive via AstalNetwork; connection activation is NOT exposed by
 * AstalNetwork, so writes go through the provisioned NetworkManager CLI
 * (`nmcli`) using the array form of `execAsync` — the SSID/password are never
 * shell-interpolated.
 */

const network = Network.get_default()

const wifiDevice: Accessor<unknown | null> = network
  ? createBinding(network, "wifi")
  : createComputed(() => null)
const enabledRaw: Accessor<boolean | null> = network
  ? createBinding(network, "wifi", "enabled")
  : createComputed(() => false)
const ssidRaw: Accessor<string | null> = network
  ? createBinding(network, "wifi", "ssid")
  : createComputed(() => null)
// Also read the active strength/device state so the tile can show a connecting
// state instead of a stale "Not connected".
const strengthRaw: Accessor<number | null> = network
  ? createBinding(network, "wifi", "strength")
  : createComputed(() => 0)
const stateRaw: Accessor<number | null> = network
  ? createBinding(network, "wifi", "state")
  : createComputed(() => 0)

const enabled = createComputed(() => enabledRaw() === true)

export { enabled as wifiEnabled, ssidRaw as wifiSsid }

export interface WifiNetwork {
  ssid: string
  strength: number
  secured: boolean
  connected: boolean
}

const [wifiList, setWifiList] = createState<WifiNetwork[]>([])

// The list is an authoritative `iw scan` (nl80211). NetworkManager's and Astal's
// access-point caches hide disappeared APs (Astal's access-point objects never
// refresh at all), which is why a switched-off hotspot lingered and stayed
// clickable. Provisioning installs `iw` and grants it CAP_NET_ADMIN so the user
// can scan without sudo; the interface name comes from NetworkManager's D-Bus.
const NM = "org.freedesktop.NetworkManager"
const NM_DEVICE = "org.freedesktop.NetworkManager.Device"
//: NM_DEVICE_TYPE_WIFI
const DEVICE_TYPE_WIFI = 2

let nmBus: Gio.DBusConnection | null = null
function bus(): Gio.DBusConnection {
  if (!nmBus) nmBus = Gio.bus_get_sync(Gio.BusType.SYSTEM, null)
  return nmBus
}

function getAll(path: string, iface: string): Record<string, unknown> {
  const reply = bus().call_sync(
    NM,
    path,
    "org.freedesktop.DBus.Properties",
    "GetAll",
    new GLib.Variant("(s)", [iface]),
    null,
    Gio.DBusCallFlags.NONE,
    -1,
    null,
  )
  const [dict] = reply.recursiveUnpack() as [Record<string, unknown>]
  return dict ?? {}
}

function wifiInterface(): string | null {
  const nm = getAll("/org/freedesktop/NetworkManager", NM)
  const devices = (nm.Devices as string[]) ?? []
  for (const path of devices) {
    const dev = getAll(path, NM_DEVICE)
    if (Number(dev.DeviceType) === DEVICE_TYPE_WIFI) {
      const iface = dev.Interface
      return typeof iface === "string" && iface ? iface : null
    }
  }
  return null
}

function dbmToPercent(dbm: number): number {
  if (!Number.isFinite(dbm)) return 0
  return Math.max(0, Math.min(100, Math.round(2 * (dbm + 100))))
}

function parseIwScan(out: string): WifiNetwork[] {
  const strongest = new Map<string, WifiNetwork>()
  let ssid: string | undefined
  let dbm = -100
  let secured = false
  let associated = false
  let inBss = false

  const flush = () => {
    if (inBss && ssid) {
      const net: WifiNetwork = {
        ssid,
        strength: dbmToPercent(dbm),
        secured,
        connected: associated,
      }
      const prev = strongest.get(ssid)
      if (!prev || net.connected || net.strength > prev.strength) {
        strongest.set(ssid, net)
      }
    }
    ssid = undefined
    dbm = -100
    secured = false
    associated = false
    inBss = false
  }

  for (const raw of out.split("\n")) {
    const line = raw.trim()
    if (line.startsWith("BSS ")) {
      flush()
      inBss = true
      associated = line.includes("-- associated")
      continue
    }
    if (!inBss) continue
    if (line.startsWith("signal:")) {
      const match = line.match(/-?\d+(\.\d+)?/)
      if (match) dbm = Number(match[0])
    } else if (line.startsWith("SSID:")) {
      ssid = line.slice(5).trim()
    } else if (
      line.startsWith("RSN:") ||
      line.startsWith("WPA:") ||
      line.includes("Privacy")
    ) {
      secured = true
    }
  }
  flush()

  return [...strongest.values()].sort((a, b) =>
    a.connected === b.connected
      ? b.strength - a.strength
      : a.connected
        ? -1
        : 1,
  )
}

export function refreshWifiList() {
  const iface = wifiInterface()
  if (!iface) return
  execAsync(["iw", "dev", iface, "scan"])
    .then((out) => setWifiList(parseIwScan(out)))
    .catch(() => {
      /* scan failed or is throttled; keep the last list */
    })
}

export { wifiList as wifiNetworks }

const [passwordTarget, setPasswordTarget] = createState<string | null>(null)
const [joinError, setJoinError] = createState("")
const [listMessage, setListMessage] = createState("")
// SSID currently being connected to — drives the row spinner so a Connect press
// is visibly acknowledged.
const [connectingSsid, setConnectingSsid] = createState<string | null>(null)

export {
  passwordTarget as wifiPasswordTarget,
  listMessage as wifiMessage,
  connectingSsid as wifiConnecting,
}

export function wifiIconOn(): string | null {
  return registry.resolve("settings-panel", "wifi")
}

export function wifiIconOff(): string | null {
  return registry.resolve("settings-panel", "wifi-off")
}

export function toggleWifi() {
  const device = network?.wifi
  if (device) device.enabled = !device.enabled
}

/**
 * Force a fresh NetworkManager scan when the list opens. `access_points` is
 * NM's cache and refreshes on its own schedule; a scan makes the list current.
 * NM rate-limits scans (a too-soon call errors), so failures are ignored — the
 * reactive cache still updates.
 */
export function scanWifi() {
  // `iw scan` performs the scan itself and returns only what is on the air now.
  refreshWifiList()
}

/** Clear a pending connect when leaving the list (safety). */
export function resetWifiConnecting() {
  setConnectingSsid(null)
}

// List messages auto-clear; without this a connect error stayed forever (and,
// unwrapped, pushed the layout wide).
let messageTimer = 0
function showListMessage(text: string) {
  setListMessage(text)
  if (messageTimer) {
    try {
      GLib.source_remove(messageTimer)
    } catch {
      /* already gone */
    }
  }
  messageTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 6000, () => {
    messageTimer = 0
    setListMessage("")
    return false
  })
}

function clearListMessage() {
  if (messageTimer) {
    try {
      GLib.source_remove(messageTimer)
    } catch {
      /* already gone */
    }
    messageTimer = 0
  }
  setListMessage("")
}

export { clearListMessage as clearWifiMessage }

// Run a command with a hard timeout so a hung nmcli can never leave the UI
// stuck (a stuck `connection up` used to leave every Connect button disabled
// forever, which looked like "clicking does nothing").
function run(args: string[], timeoutMs = 30000): Promise<string> {
  const execution = execAsync(args)
  const timeout = new Promise<string>((_resolve, reject) => {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeoutMs, () => {
      reject(new Error(`timed out: ${args.join(" ")}`))
      return false
    })
  })
  return Promise.race([execution, timeout])
}

function connectToNetwork(name: string, password?: string): Promise<string> {
  const args = ["nmcli", "device", "wifi", "connect", name]
  if (password !== undefined && password !== "") {
    args.push("password", password)
  }
  return run(args)
}

function splitLastColon(line: string): [string, string] {
  const idx = line.lastIndexOf(":")
  if (idx < 0) return [line, ""]
  return [line.slice(0, idx), line.slice(idx + 1)]
}

// The saved Wi-Fi connection for an SSID, matched by the profile's SSID (a
// profile's name can differ from the SSID). Activating that profile is the
// reliable way to switch between known networks — `device wifi connect` can
// race/fail when another network is already active.
async function savedWifiConnection(ssid: string): Promise<string | null> {
  try {
    const out = await execAsync([
      "nmcli",
      "-t",
      "-f",
      "NAME,TYPE",
      "connection",
      "show",
    ])
    for (const line of out.split("\n")) {
      if (!line.trim()) continue
      const [rawName, type] = splitLastColon(line)
      if (type.trim() !== "802-11-wireless") continue
      const name = rawName.replace(/\\:/g, ":").replace(/\\\\/g, "\\")
      if (name === ssid) return name
      try {
        const savedSsid = (
          await execAsync([
            "nmcli",
            "-g",
            "802-11-wireless.ssid",
            "connection",
            "show",
            name,
          ])
        ).trim()
        if (savedSsid === ssid) return name
      } catch {
        /* profile has no SSID; skip */
      }
    }
  } catch {
    /* nmcli unavailable */
  }
  return null
}

// The connected state comes from the periodic iw scan; after issuing a connect,
// refresh a few times so the switch shows up promptly.
function scheduleListRefresh() {
  for (const delay of [1200, 3500, 7000]) {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
      refreshWifiList()
      return false
    })
  }
}

function openWifiPassword(name: string) {
  clearListMessage()
  setJoinError("")
  setPasswordTarget(name)
}

function closeWifiPassword() {
  setJoinError("")
  setPasswordTarget(null)
}

export { closeWifiPassword as closeWifiPasswordPrompt }

async function activateNetwork(n: WifiNetwork) {
  clearListMessage()
  if (n.connected) return
  if (connectingSsid() !== null) return // one connect at a time

  const saved = await savedWifiConnection(n.ssid)
  if (n.secured && saved === null) {
    openWifiPassword(n.ssid)
    return
  }

  // Known/open network: switch immediately, with a row spinner for feedback.
  setConnectingSsid(n.ssid)
  // Watchdog: never leave every Connect button disabled if a step misbehaves.
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 40000, () => {
    if (connectingSsid() === n.ssid) setConnectingSsid(null)
    return false
  })
  try {
    if (saved !== null) {
      // `connection up` activates the saved profile but does NOT scan for the
      // AP, so it fails with "network could not be found" when NM's cache is
      // cold (the usual "nothing happens"). Scan first, then activate; fall
      // back to `device wifi connect`, which scans itself.
      await run(["nmcli", "device", "wifi", "rescan"], 10000).catch(() => "")
      try {
        await run(["nmcli", "connection", "up", "id", saved])
      } catch {
        await connectToNetwork(n.ssid)
      }
    } else {
      await connectToNetwork(n.ssid)
    }
    scheduleListRefresh()
  } catch {
    showListMessage(`Couldn't connect to "${n.ssid}".`)
  } finally {
    if (connectingSsid() === n.ssid) setConnectingSsid(null)
  }
}

/** Header/standalone power toggle for the Wi-Fi subview. */
export function WifiToggle() {
  return (
    <IconToggle
      iconOn={wifiIconOn()}
      iconOff={wifiIconOff()}
      active={enabled}
      onClicked={toggleWifi}
      tooltip="Toggle Wi-Fi"
      size={22}
    />
  )
}

export function WifiTile() {
  return (
    <CapabilityTile
      iconOn={wifiIconOn()}
      iconOff={wifiIconOff()}
      title="Wi-Fi"
      subtitle={createComputed(() => {
        if (!wifiDevice()) return "Unavailable"
        if (!enabled()) return "Off"
        const activeSsid = ssidRaw()
        if (activeSsid) {
          const strength = Number(strengthRaw() ?? 0)
          return strength > 0 ? `${activeSsid} · ${strength}%` : activeSsid
        }
        const state = Number(stateRaw() ?? 0)
        if (state >= 40 && state < 100) return "Connecting…"
        return "Not connected"
      })}
      active={enabled}
      onToggle={toggleWifi}
      onOpen={() => show("wifi")}
      toggleTooltip="Toggle Wi-Fi"
    />
  )
}

function SignalBars({ strength }: { strength: number }) {
  const level = strength >= 75 ? 4 : strength >= 50 ? 3 : strength >= 25 ? 2 : 1
  return (
    <box class="settings-signal" valign={Gtk.Align.END} spacing={2}>
      {[1, 2, 3, 4].map((i) => (
        <box
          class={i <= level ? "settings-signal-bar on" : "settings-signal-bar"}
          valign={Gtk.Align.END}
        />
      ))}
    </box>
  )
}

export function WifiRow({ network: item }: { network: WifiNetwork }) {
  const connected = createComputed(() => ssidRaw() === item.ssid)
  const cls = createComputed(() =>
    connected() ? "settings-net sel" : "settings-net",
  )

  // Mirror the Bluetooth row: the row is a box and the action is an explicit
  // button. A whole-row <button> wrapping labels/boxes did not receive clicks
  // on this GTK build, so the action is a sibling button (which does).
  function act() {
    void activateNetwork(item)
  }

  const busy = createComputed(() => connectingSsid() === item.ssid)

  return (
    <box class={cls} spacing={10}>
      <box orientation={1} hexpand>
        <label class="settings-net-name" xalign={0} label={item.ssid} />
        <label
          class="settings-net-sub"
          xalign={0}
          label={item.secured ? "Secured" : "Open network"}
        />
      </box>
      <label
        class="settings-badge conn"
        label="Connected"
        valign={Gtk.Align.CENTER}
        visible={connected}
      />
      <box visible={createComputed(() => !connected())} valign={Gtk.Align.END}>
        <SignalBars strength={item.strength} />
      </box>
      <button
        class="settings-rowact"
        onClicked={act}
        canFocus={false}
        visible={createComputed(() => !connected())}
        sensitive={createComputed(() => connectingSsid() === null)}
      >
        <box spacing={6}>
          <Gtk.Spinner
            class="settings-spinner"
            visible={busy}
            spinning={busy}
          />
          <label label="Connect" visible={createComputed(() => !busy())} />
        </box>
      </button>
    </box>
  )
}

export function WifiPasswordPrompt() {
  const [password, setPassword] = createState("")
  const [busy, setBusy] = createState(false)
  let entry: Gtk.Entry | null = null

  // Reset the field and focus it each time a network is chosen. The prompt is
  // mounted permanently and only its container is visibility-toggled, so this
  // effect (not a mount callback) is what reacts to the target changing.
  createEffect(() => {
    if (passwordTarget() === null) return
    setPassword("")
    GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
      entry?.grab_focus()
      return false
    })
  })

  function join() {
    const name = passwordTarget()
    if (!name || busy()) return
    setBusy(true)
    setJoinError("")
    connectToNetwork(name, password())
      .then(() => {
        setListMessage("")
        closeWifiPassword()
        scheduleListRefresh()
      })
      .catch(() => {
        setJoinError("Couldn't join. Check the password and try again.")
      })
      .finally(() => setBusy(false))
  }

  return (
    <box class="settings-password" orientation={1} spacing={8}>
      <label class="settings-field-label" xalign={0} label="Password" />
      <box class="settings-field-input">
        <entry
          class="settings-field-entry"
          hexpand
          visibility={false}
          placeholderText="Network password"
          onActivate={join}
          onNotifyText={(self: { text: string }) => setPassword(self.text)}
          $={(self) => {
            entry = self
          }}
        />
      </box>
      <label
        class="settings-field-error"
        xalign={0}
        label={joinError}
        visible={createComputed(() => joinError() !== "")}
      />
      <box class="settings-btnrow" spacing={8} homogeneous>
        <button class="settings-btn cancel" onClicked={closeWifiPassword} canFocus={false}>
          <label label="Cancel" />
        </button>
        <button class="settings-btn join" onClicked={join} canFocus={false}>
          <label label={createComputed(() => (busy() ? "Joining…" : "Join"))} />
        </button>
      </box>
    </box>
  )
}
