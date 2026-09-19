import { createComputed, createEffect } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back } from "../state"
import {
  BluetoothDeviceList,
  BluetoothToggle,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothPowered,
  routeAudioToDevice,
  startBluetoothDiscovery,
  stopBluetoothDiscovery,
} from "../controls/bluetooth"

export function BluetoothView() {
  const hasDevices = createComputed(() => bluetoothDevices().length > 0)
  const showList = createComputed(() => bluetoothPowered() && hasDevices())

  // Discovery is not automatic: start it while this view is shown and the
  // adapter is powered, stop it when leaving (so BlueZ actually reports
  // nearby, not-yet-known devices).
  createEffect(() => {
    if (activeView() === "bluetooth" && bluetoothPowered()) {
      startBluetoothDiscovery()
      // Devices that connected outside the panel (auto-connect) still need the
      // audio sink defaulted; routing is idempotent.
      for (const device of bluetoothDevices()) {
        if (device.connected) {
          void routeAudioToDevice(device.alias || device.name)
        }
      }
      return () => stopBluetoothDiscovery()
    }
    stopBluetoothDiscovery()
  })

  return (
    <box orientation={1} spacing={8}>
      <NavHeader title="Bluetooth" onBack={back} trailing={<BluetoothToggle />} />

      <label
        class="settings-empty"
        xalign={0}
        label="Bluetooth is off"
        visible={createComputed(() => !bluetoothPowered())}
      />

      <label
        class="settings-empty"
        xalign={0}
        label="Scanning…"
        visible={createComputed(
          () => bluetoothPowered() && bluetoothDiscovering() && !hasDevices(),
        )}
      />

      <label
        class="settings-empty"
        xalign={0}
        label="No devices found"
        visible={createComputed(
          () => bluetoothPowered() && !bluetoothDiscovering() && !hasDevices(),
        )}
      />

      <box orientation={1} spacing={4} visible={showList}>
        <BluetoothDeviceList />
      </box>
    </box>
  )
}
