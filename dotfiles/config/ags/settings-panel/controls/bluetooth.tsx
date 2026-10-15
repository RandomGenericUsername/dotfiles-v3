import { createComputed } from "ags"
import { registry } from "../../platform/adapters/icon-registry"
import { CapabilityTile } from "../primitives"
import {
  bluetoothDevices,
  bluetoothPowered,
  setBluetoothPowered,
} from "../../services/bluetooth-service"
import { show } from "../state"

/**
 * Bluetooth control tile (thin view over `services/bluetooth-service`).
 *
 * The full body lives in `components/bluetooth/BluetoothContent`; this file
 * only composes the main-view capability row and forwards intent.
 */

export function bluetoothIconOn(): string | null {
  return registry.resolve("settings-panel", "bluetooth")
}

export function bluetoothIconOff(): string | null {
  return registry.resolve("settings-panel", "bluetooth-off")
}

export function BluetoothTile() {
  return (
    <CapabilityTile
      iconOn={bluetoothIconOn()}
      iconOff={bluetoothIconOff()}
      title="Bluetooth"
      subtitle={createComputed(() => {
        // Four states, mirroring the Wi-Fi tile's shape exactly: off, on but
        // nothing connected, connected with a battery figure, connected with
        // none. BlueZ reports battery 0 when Battery1 is absent or unreadable,
        // so the percentage is only printed when there is a real reading —
        // same guard as the Wi-Fi tile's `strength > 0`.
        if (!bluetoothPowered()) return "Off"
        const connected = bluetoothDevices().find((device) => device.connected)
        if (!connected) return "Not connected"
        const label = connected.alias || connected.name
        if (!label) return "Not connected"
        return connected.battery > 0
          ? `${label} · ${connected.battery}%`
          : label
      })}
      active={bluetoothPowered}
      // `IconToggle`/`CapabilityTile` expose `clicked` with no payload — the
      // button's `clicked` fires only on genuine user activation, so there is no
      // `notify::active` echo to filter here the way `WifiSwitch` does, but that
      // also means no new value is handed to us. So the explicit value is
      // derived from the live accessor at click time and passed to
      // `setBluetoothPowered(enabled)` — never the deprecated `toggleBluetooth`,
      // which read-modify-writes and can write the inverse of what the user
      // asked for when the popup's header switch is mounted at the same time.
      onToggle={() => void setBluetoothPowered(!bluetoothPowered())}
      onOpen={() => show("bluetooth")}
      toggleTooltip="Toggle Bluetooth"
    />
  )
}
