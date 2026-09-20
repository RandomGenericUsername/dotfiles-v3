import Network from "gi://AstalNetwork"
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

function splitEscaped(line: string): string[] {
  const out: string[] = []
  let cur = ""
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === "\\") {
      cur += line[++i] ?? ""
      continue
    }
    if (ch === ":") {
      out.push(cur)
      cur = ""
      continue
    }
    cur += ch
  }
  out.push(cur)
  return out
}

const [wifiList, setWifiList] = createState<WifiNetwork[]>([])

// Source the list from `nmcli`, not AstalNetwork's `access-points`: on this
// stack Astal's access-point objects never refresh (their `last-seen` and
// strength stay frozen), so the panel showed a stale list — e.g. a switched-off
// hotspot lingered and stayed clickable. nmcli reflects NetworkManager's live
// cache and updates as networks appear and disappear.
export function refreshWifiList() {
  execAsync([
    "nmcli",
    "-t",
    "-f",
    "IN-USE,SSID,BSSID,SIGNAL,SECURITY",
    "device",
    "wifi",
    "list",
  ])
    .then((out) => {
      const strongest = new Map<string, WifiNetwork>()
      for (const line of out.split("\n")) {
        if (!line.trim()) continue
        const fields = splitEscaped(line)
        if (fields.length < 5) continue
        const [inUse, ssid, , signal, security] = fields
        if (!ssid) continue
        const net: WifiNetwork = {
          ssid,
          strength: Number(signal) || 0,
          secured: security !== "" && security !== "--",
          connected: inUse === "*",
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
    })
    .catch(() => {
      /* nmcli unavailable; keep the last list */
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
  // Ask NetworkManager for a fresh scan (rate-limited; errors ignored) and
  // re-read its live list.
  execAsync(["nmcli", "device", "wifi", "rescan"]).catch(() => {
    /* throttled; the current list is still read below */
  })
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
