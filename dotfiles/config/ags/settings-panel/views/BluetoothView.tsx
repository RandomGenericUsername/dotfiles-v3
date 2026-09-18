import { createComputed } from "ags"
import { NavHeader } from "../primitives"
import { back } from "../state"
import {
  BluetoothDeviceList,
  BluetoothToggle,
  bluetoothDevices,
  bluetoothPowered,
} from "../controls/bluetooth"

export function BluetoothView() {
  const hasDevices = createComputed(() => bluetoothDevices().length > 0)
  const showList = createComputed(() => bluetoothPowered() && hasDevices())

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
        label="No devices"
        visible={createComputed(() => bluetoothPowered() && !hasDevices())}
      />

      <box orientation={1} spacing={4} visible={showList}>
        <BluetoothDeviceList />
      </box>
    </box>
  )
}
