import { createComputed, createEffect } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back } from "../state"
import {
  BluetoothDeviceList,
  BluetoothToggle,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothFailure,
  bluetoothPowered,
  routeAudioToDevice,
  startBluetoothDiscovery,
  stopBluetoothDiscovery,
} from "../controls/bluetooth"

export function BluetoothView() {
  const hasDevices = createComputed(() => bluetoothDevices().length > 0)
  const showList = createComputed(() => bluetoothPowered() && hasDevices())

  // Discovery runs while this view is open and the adapter is powered; leaving
  // the view (or powering off) stops it so BlueZ does not scan forever.
  createEffect(() => {
    if (activeView() !== "bluetooth") return
    if (!bluetoothPowered()) return
    startBluetoothDiscovery()
    return () => stopBluetoothDiscovery()
  })

  // Devices that connected outside the panel (auto-connect) still need the
  // audio sink defaulted; routing is idempotent.
  createEffect(() => {
    if (activeView() !== "bluetooth") return
    if (!bluetoothPowered()) return
    for (const device of bluetoothDevices()) {
      if (device.connected) {
        void routeAudioToDevice(device.alias || device.name)
      }
    }
  })

  // Failure is derived from the service state — no manual message timer.
  const failure = createComputed(() => bluetoothFailure())

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
        class="settings-message"
        xalign={0}
        wrap
        maxWidthChars={34}
        label={failure}
        visible={createComputed(() => failure() !== "")}
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
