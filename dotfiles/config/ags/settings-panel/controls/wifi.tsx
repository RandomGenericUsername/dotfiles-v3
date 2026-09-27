import { Accessor, createComputed } from "ags"
import { registry } from "../../lib/icon-registry"
import { wifiSignalIconKey } from "../../lib/wifi-signal"
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

/**
 * Reactive tile glyph: the circle-badged `wifi-signal-*` icon matching the
 * active network's strength (same step table as the popup rows, shared via
 * `lib/wifi-signal`). Falls back to the static `wifi` glyph when the radio
 * is on but nothing is connected (or strength is unknown); the muted
 * `wifi-off` glyph stays on `iconOff` for the radio-off state. Passed to
 * `CapabilityTile` WITHOUT calling it so the glyph swaps live with signal
 * changes and never crashes on a null active network.
 */
export const wifiSignalIcon: Accessor<string | null> = createComputed(() => {
  const active = wifiNetworks().find((network) => network.connected)
  if (active && active.strength > 0) {
    return (
      registry.resolve("settings-panel", wifiSignalIconKey(active.strength)) ??
      registry.resolve("settings-panel", "wifi")
    )
  }
  return registry.resolve("settings-panel", "wifi")
})

export function WifiTile() {
  return (
    <CapabilityTile
      iconOn={wifiSignalIcon}
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
