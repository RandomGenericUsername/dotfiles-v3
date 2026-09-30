import { createComputed } from "ags"
import { activeView, panelVisible } from "../state"
import { BluetoothContent } from "../../components/bluetooth/BluetoothContent"

/**
 * The Bluetooth subview BODY only — the header moved to SubviewHeader so it
 * pins above the scrolled window instead of scrolling away with the content.
 * See SubviewHeader.tsx.
 */
export function BluetoothView() {
  return (
    <box orientation={1}>
      <BluetoothContent
        visible={createComputed(
          () => panelVisible() && activeView() === "bluetooth",
        )}
      />
    </box>
  )
}
