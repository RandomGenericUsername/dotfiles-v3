import { createState } from "ags"
import { closeWifiPopup } from "../components/wifi/state"
import { closeBluetoothPopup } from "../components/bluetooth/state"

/**
 * Shared settings-panel state.
 *
 * The panel is a second window in the existing always-on bar AGS instance.
 * Only the bar settings button and the panel itself write this state.
 */
export type SettingsView = "main" | "wifi" | "bluetooth"

const [panelVisible, setPanelVisible] = createState(false)
const [activeView, setActiveView] = createState<SettingsView>("main")

// X (monitor-relative) of the status-bar settings icon centre — written by the
// bar button on realization so the panel can be anchored beneath the icon
// rather than pinned to the screen's right edge.
const [iconCenterX, setIconCenterX] = createState<number | null>(null)

// Bumped on every open/show/back so the panel can reset its scroll position
// even when the view id itself does not change (e.g. reopening on "main").
const [viewEpoch, setViewEpoch] = createState(0)

export { panelVisible, activeView, viewEpoch, iconCenterX, setIconCenterX }

export function open() {
  setPanelVisible(true)
  setViewEpoch((n) => n + 1)
  // Keep the overlays mutually exclusive: opening the panel dismisses the
  // Wi-Fi and Bluetooth popups. Coordinated here (a caller), never inside
  // `components/*/state.ts` — the popup state modules must not import from
  // `settings-panel/**`, or the one-way dependency inverts.
  closeWifiPopup()
  closeBluetoothPopup()
}

export function close() {
  setPanelVisible(false)
  // Return to the main view so the next open starts clean.
  setActiveView("main")
}

export function toggle() {
  if (panelVisible()) close()
  else open()
}

export function show(view: SettingsView) {
  setActiveView(view)
  setViewEpoch((n) => n + 1)
}

export function back() {
  setActiveView("main")
  setViewEpoch((n) => n + 1)
}
