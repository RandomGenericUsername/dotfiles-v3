import Network from "gi://AstalNetwork"
import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import { execAsync } from "ags/process"
import { createBinding, createComputed, createEffect } from "ags"
import { registry } from "../../lib/icon-registry"
import { setWifiIconX, toggleWifiPopup } from "../../components/wifi/state"
import { close } from "../../settings-panel/state"

const network = Network.get_default()
const wifi = createBinding(network, "wifi")
const wired = createBinding(network, "wired")
const connectivity = createBinding(network, "connectivity")

// NMConnectivityState: NONE=0, PORTAL=1, LIMITED=2, FULL=3.
// NONE means the connectivity check is disabled, not "no internet",
// so only LIMITED/PORTAL count as no-internet.
const CONNECTIVITY_LIMITED = 2
const CONNECTIVITY_PORTAL = 1

// NMDeviceState: ACTIVATED=100; anything below means not associated/cable unplugged.
const DEVICE_STATE_ACTIVATED = 100

type WifiDevice = {
  enabled?: boolean
  state?: number
  strength: number
  ssid?: string | null
}

type WiredDevice = {
  state?: number
}

function hasNoInternet(conn: number): boolean {
  return conn === CONNECTIVITY_LIMITED || conn === CONNECTIVITY_PORTAL
}

function getWifiStrengthKey(strength: number): string {
  if (strength >= 80) return "wifi-full"
  if (strength >= 50) return "wifi-high"
  if (strength >= 25) return "wifi-medium"
  return "wifi-low"
}

function getNetworkStateKey(w: unknown, wd: unknown, conn: number): string {
  if (w) {
    const wf = w as WifiDevice
    const radioOn = wf.enabled !== false
    const activated = (wf.state ?? 0) === DEVICE_STATE_ACTIVATED
    if (!radioOn || !activated) return "wifi-not-connected"
    if (hasNoInternet(conn)) return "wifi-no-internet"
    return getWifiStrengthKey(wf.strength)
  }
  if (wd) {
    const wdd = wd as WiredDevice
    if ((wdd.state ?? 0) === DEVICE_STATE_ACTIVATED) {
      return hasNoInternet(conn) ? "ethernet-no-internet" : "ethernet-connected"
    }
    return "ethernet-not-connected"
  }
  return "wifi-not-connected"
}

function getNetworkIconPath(w: unknown, wd: unknown, conn: number): string | null {
  const mappings = registry.getBarMappings("network")
  if (!mappings) return null

  const stateKey = getNetworkStateKey(w, wd, conn)
  const variant = mappings.states[stateKey]
  if (!variant) return null

  return registry.resolve("network", variant)
}

function getNetworkLabel(w: unknown, wd: unknown): string {
  if (w) return ""
  if (wd) return "Ethernet"
  return "No network"
}

// Last pointer x (surface coords == monitor coords, the bar spans the monitor).
// Recorded by a motion controller — which does NOT claim clicks — so the
// button's own activation still fires. Re-recorded on every hover, so moving
// the icon in the bar just works.
let lastIconX: number | null = null

export function NetworkStatus() {
  return (
    <button
      class="widget network-widget"
      onClicked={() => {
        // Left click = the Wi-Fi popup, anchored under this icon. Close the
        // settings panel first so the two overlays never stack.
        close()
        if (lastIconX !== null) setWifiIconX(lastIconX)
        toggleWifiPopup()
      }}
      $={(self) => {
        // Left click opens the Wi-Fi popup (onClicked); right click keeps the
        // wifitui TUI. A motion controller (which does not claim clicks)
        // records the pointer x so the popup can be positioned under the icon.
        const motion = new Gtk.EventControllerMotion()
        motion.connect("motion", () => {
          const event = motion.get_current_event()
          if (!event) return
          // Gdk.Event.get_position() -> [ok, x, y] in gjs.
          const pos = event.get_position() as unknown
          if (Array.isArray(pos) && pos.length >= 3) {
            const x = Number(pos[1])
            if (Number.isFinite(x) && x > 0) lastIconX = x
          }
        })
        self.add_controller(motion)

        const secondary = new Gtk.GestureClick({ button: Gdk.BUTTON_SECONDARY })
        secondary.connect("pressed", () =>
          execAsync(["kitty", "--", "wifitui", "tui"]),
        )
        self.add_controller(secondary)
      }}
    >
      <box spacing={4}>
        <image
          pixel_size={28}
          class="widget-icon"
          $={(self) => {
            createEffect(() => {
              const w = wifi()
              const update = () =>
                self.set_from_file(getNetworkIconPath(wifi(), wired(), connectivity()) ?? "")
              update()
              const wAny = w as { connect?: (...a: unknown[]) => number; disconnect?: (id: number) => void }
              if (wAny?.connect && wAny?.disconnect) {
                const ids = ["strength", "state", "enabled"].map((prop) =>
                  wAny.connect!(`notify::${prop}`, update),
                )
                return () => ids.forEach((id) => wAny.disconnect!(id))
              }
            })
          }}
        />
        <label
          visible={createComputed(() => getNetworkLabel(wifi(), wired()) !== "")}
          label={createComputed(() => getNetworkLabel(wifi(), wired()))}
        />
      </box>
    </button>
  )
}
