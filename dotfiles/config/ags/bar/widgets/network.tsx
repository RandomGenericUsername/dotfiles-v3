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
  if (w) return ""
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
          pixel_size={24}
          class="widget-icon"
          $={(self) => {
            let cleanup: (() => void) | null = null
            createEffect(() => {
              if (cleanup) {
                cleanup()
                cleanup = null
              }
              const w = wifi()
              const update = () => self.set_from_file(getNetworkIconPath(wifi(), wired()) ?? "")
              update()
              if (w && (w as any).connect) {
                const id = (w as any).connect("notify::strength", update)
                cleanup = () => (w as any).disconnect(id)
                return () => {
                  if (cleanup) {
                    cleanup()
                    cleanup = null
                  }
                }
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