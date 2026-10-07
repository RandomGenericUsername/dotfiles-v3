import { createState } from "ags"

/**
 * Panel-agnostic Bluetooth popup state.
 *
 * Owned by an overlay that is not the settings panel, so it must not import
 * from `settings-panel/**` (one-way dependency). Mutual exclusion with the
 * panel is coordinated by the callers, not here.
 */

const [bluetoothPopupVisible, setBluetoothPopupVisible] = createState(false)

// X (monitor-relative) of the status-bar Bluetooth icon centre — written by the
// bar widget so the popup can be anchored beneath the icon rather than pinned to
// an edge.
const [bluetoothIconX, setBluetoothIconXState] = createState<number | null>(null)

export { bluetoothPopupVisible, bluetoothIconX }

export function openBluetoothPopup(): void {
  setBluetoothPopupVisible(true)
}

export function closeBluetoothPopup(): void {
  setBluetoothPopupVisible(false)
}

export function toggleBluetoothPopup(): void {
  if (bluetoothPopupVisible()) closeBluetoothPopup()
  else openBluetoothPopup()
}

export function setBluetoothIconX(x: number): void {
  setBluetoothIconXState(x)
}