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

function decodeSsid(value: unknown): string {
  try {
    if (typeof value === "string") return value
    const bytes = Uint8Array.from(Array.from(value as ArrayLike<number>))
    const TD = (globalThis as { TextDecoder?: typeof TextDecoder }).TextDecoder
    if (TD) return new TD().decode(bytes)
    return String.fromCharCode(...bytes)
  } catch {
    return ""
  }
}

const [wifiList, setWifiList] = createState<WifiNetwork[]>([])

// The list is read straight from NetworkManager's D-Bus and filtered by
// LastSeen. AstalNetwork's access-point objects never refresh (their last-seen
// and strength stay frozen), and nmcli's cache hides nothing, so a switched-off
// hotspot lingered and could still be clicked. NM's own LastSeen does advance
// (verified), so an AP not seen in the recent scans is dropped here.
const NM = "org.freedesktop.NetworkManager"
const NM_DEVICE = "org.freedesktop.NetworkManager.Device"
const NM_WIRELESS = "org.freedesktop.NetworkManager.Device.Wireless"
const NM_AP = "org.freedesktop.NetworkManager.AccessPoint"
//: NM_DEVICE_TYPE_WIFI
const DEVICE_TYPE_WIFI = 2
const AP_STALE_SECONDS = 20

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

function wifiDevicePath(): string | null {
  const nm = getAll("/org/freedesktop/NetworkManager", NM)
  const devices = (nm.Devices as string[]) ?? []
  for (const path of devices) {
    if (Number(getAll(path, NM_DEVICE).DeviceType) === DEVICE_TYPE_WIFI) return path
  }
  return null
}

export function refreshWifiList() {
  try {
    const devicePath = wifiDevicePath()
    if (!devicePath) return
    const wireless = getAll(devicePath, NM_WIRELESS)
    const paths = (wireless.AccessPoints as string[]) ?? []
    const activePath = (wireless.ActiveAccessPoint as string) ?? ""

    const aps = paths.map((path) => ({
      path,
      props: getAll(path, NM_AP),
    }))
    const newest = aps.reduce(
      (max, ap) => Math.max(max, Number(ap.props.LastSeen) || 0),
      0,
    )

    const strongest = new Map<string, WifiNetwork>()
    for (const { path, props } of aps) {
      const ssid = decodeSsid(props.Ssid)
      if (!ssid) continue
      const lastSeen = Number(props.LastSeen) || 0
      const stale =
        newest > 0 && lastSeen > 0 && newest - lastSeen > AP_STALE_SECONDS
      if (stale) continue
      const net: WifiNetwork = {
        ssid,
        strength: Number(props.Strength) || 0,
        secured:
          (Number(props.WpaFlags) || 0) > 0 ||
          (Number(props.RsnFlags) || 0) > 0 ||
          ((Number(props.Flags) || 0) & 1) === 1,
        connected: path === activePath,
      }
      const prev = strongest.get(ssid)
      if (!prev || net.connected || net.strength > prev.strength) {
        strongest.set(ssid, net)
      }
    }

    const list = [...strongest.values()].sort((a, b) =>
      a.connected === b.connected
        ? b.strength - a.strength
        : a.connected
          ? -1
          : 1,
    )
    setWifiList(list)
  } catch {
    /* NM unavailable; keep the last list */
  }
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
  try {
    const devicePath = wifiDevicePath()
    if (devicePath) {
      bus().call_sync(
        NM,
        devicePath,
        NM_WIRELESS,
        "RequestScan",
        new GLib.Variant("(a{sv})", [{}]),
        null,
        Gio.DBusCallFlags.NONE,
        -1,
        null,
      )
    }
  } catch {
    /* NM throttles scans; the list is still read below */
  }
  refreshWifiList()
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

function connectToNetwork(name: string, password?: string): Promise<void> {
  const args = ["nmcli", "device", "wifi", "connect", name]
  if (password !== undefined && password !== "") {
    args.push("password", password)
  }
  const run = execAsync(args).then(() => undefined)
  // Never leave the row spinner stuck / the UI silent if nmcli hangs waiting on
  // NetworkManager.
  const timeout = new Promise<void>((_resolve, reject) => {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 30000, () => {
      reject(new Error("connect timed out"))
      return false
    })
  })
  return Promise.race([run, timeout])
}

function networkIsKnown(name: string): Promise<boolean> {
  const lookup = execAsync(["nmcli", "-t", "-f", "NAME", "connection", "show"])
    .then((out) => out.split("\n").some((line) => line.trim() === name))
    .catch(() => false)
  // Never let a slow nmcli leave the UI silent — treat a timeout as unknown.
  const timeout = new Promise<boolean>((resolve) => {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 3000, () => {
      resolve(false)
      return false
    })
  })
  return Promise.race([lookup, timeout])
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

  const known = await networkIsKnown(n.ssid)
  if (n.secured && !known) {
    openWifiPassword(n.ssid)
    return
  }

  // Saved/open network: connect directly, with a row spinner for feedback.
  setConnectingSsid(n.ssid)
  try {
    await connectToNetwork(n.ssid)
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
        sensitive={createComputed(() => !busy())}
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
