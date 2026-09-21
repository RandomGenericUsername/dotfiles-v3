import { createComputed } from "ags"
import { registry } from "../../lib/icon-registry"
import { CapabilityTile } from "../primitives"
import {
  bluetoothDevices,
  bluetoothPowered,
  toggleBluetooth,
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
        if (!bluetoothPowered()) return "Off"
        const connected = bluetoothDevices().find((device) => device.connected)
        return connected?.name || connected?.alias || "Not connected"
      })}
      active={bluetoothPowered}
      onToggle={toggleBluetooth}
      onOpen={() => show("bluetooth")}
      toggleTooltip="Toggle Bluetooth"
    />
  )
}
