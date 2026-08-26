import Network from "gi://AstalNetwork"
import { execAsync } from "ags/process"
import { createBinding, createComputed, createEffect } from "ags"
import { registry } from "../../lib/icon-registry"

const network = Network.get_default()
const wifi = createBinding(network, "wifi")
const wired = createBinding(network, "wired")

function getWifiStateKey(strength: number): string {
  if (strength > 66) return "wifi-high"
  if (strength > 33) return "wifi-medium"
  return "wifi-low"
}

function getNetworkIconPath(w: unknown, wd: unknown): string | null {
  const mappings = registry.getBarMappings("network")
  if (!mappings) return null

  let stateKey: string
  if (w) {
    const wifi = w as { state?: number; strength: number }
    stateKey = getWifiStateKey(wifi.strength)
  } else if (wd) {
    stateKey = "ethernet"
  } else {
    stateKey = "wifi-disabled"
  }

  const variant = mappings.states[stateKey]
  if (!variant) return null

  return registry.resolve("network", variant)
}

function getNetworkLabel(w: unknown, wd: unknown): string {
  if (w) return (w as { ssid?: string }).ssid ?? "WiFi"
  if (wd) return "Ethernet"
  return "No network"
}

export function NetworkStatus() {
  return (
    <button
      class="widget network-widget"
      onClicked={() => execAsync(["kitty", "--", "wifitui", "tui"])}
    >
      <box spacing={4}>
        <image
          class="widget-icon"
          $={(self) => {
            createEffect(() => {
              self.set_from_file(getNetworkIconPath(wifi(), wired()) ?? "")
            })
          }}
        />
        <label
          label={createComputed(() => getNetworkLabel(wifi(), wired()))}
        />
      </box>
    </button>
  )
}