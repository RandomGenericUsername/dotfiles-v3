import { createComputed } from "ags"
import { registry } from "../../lib/icon-registry"
import { CapabilityTile } from "../primitives"
import {
  connectState,
  toggleWifi,
  wifiEnabled,
  wifiNetworks,
} from "../../services/wifi-service"
import { show } from "../state"

/**
 * Wi-Fi tile for the settings panel main view (thin view over
 * `services/wifi-service`). The list/prompt body lives in
 * `components/wifi/WifiContent` so the bar popup can reuse it.
 */

export function wifiIconOn(): string | null {
  return registry.resolve("settings-panel", "wifi")
}

export function wifiIconOff(): string | null {
  return registry.resolve("settings-panel", "wifi-off")
}

export function WifiTile() {
  return (
    <CapabilityTile
      iconOn={wifiIconOn()}
      iconOff={wifiIconOff()}
      title="Wi-Fi"
      subtitle={createComputed(() => {
        if (!wifiEnabled()) return "Off"
        const conn = connectState()
        if (conn.phase === "preparing" || conn.phase === "activating") {
          return "Connecting…"
        }
        const active = wifiNetworks().find((network) => network.connected)
        if (active) {
          return active.strength > 0
            ? `${active.ssid} · ${active.strength}%`
            : active.ssid
        }
        return "Not connected"
      })}
      active={wifiEnabled}
      onToggle={toggleWifi}
      onOpen={() => show("wifi")}
      toggleTooltip="Toggle Wi-Fi"
    />
  )
}
