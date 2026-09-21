import { createComputed } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back, panelVisible } from "../state"
import {
  BluetoothContent,
  BluetoothToggle,
} from "../../components/bluetooth/BluetoothContent"

export function BluetoothView() {
  return (
    <box orientation={1} spacing={8}>
      <NavHeader title="Bluetooth" onBack={back} trailing={<BluetoothToggle />} />

      <BluetoothContent
        visible={createComputed(
          () => panelVisible() && activeView() === "bluetooth",
        )}
      />
    </box>
  )
}
