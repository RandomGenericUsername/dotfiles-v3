import Network from "gi://AstalNetwork"
import { createBinding } from "ags"
import { registry } from "../../lib/icon-registry"

const network = Network.get_default()
const wifi = createBinding(network, "wifi")
const wired = createBinding(network, "wired")

function getWifiStateKey(strength: number): string {
  if (strength > 66) return "wifi-high"
  if (strength > 33) return "wifi-medium"
  return "wifi-low"
}

function getNetworkIconPath(): string | null {
  const mappings = registry.getBarMappings("network")
  if (!mappings) return null

  const currentWifi = network.wifi
  const currentWired = network.wired

  let stateKey: string
  if (currentWifi) {
    stateKey = getWifiStateKey(currentWifi.strength)
  } else if (currentWired) {
    stateKey = "ethernet"
  } else {
    stateKey = "wifi-disabled"
  }

  const variant = mappings.states[stateKey]
  if (!variant) return null

  return registry.resolve("network", variant)
}

function getNetworkLabel(): string {
  const currentWifi = network.wifi
  const currentWired = network.wired

  if (currentWifi) return currentWifi.ssid ?? "Wifi"
  if (currentWired) return "Ethernet"
  return "Disconnected"
}

export function NetworkStatus() {
  return (
    <box class="widget network-widget" spacing={4}>
      <image
        class="widget-icon"
        icon={wifi(() => getNetworkIconPath() ?? "")}
      />
      <label label={wifi(() => getNetworkLabel())} />
    </box>
  )
}
