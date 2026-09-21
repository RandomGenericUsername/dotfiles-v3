import { createState } from "ags"

/**
 * Panel-agnostic Wi-Fi popup state.
 *
 * Owned by an overlay that is not the settings panel, so it must not import
 * from `settings-panel/**` (one-way dependency). Mutual exclusion with the
 * panel is coordinated by the callers, not here.
 */

const [wifiPopupVisible, setWifiPopupVisible] = createState(false)

// X (monitor-relative) of the status-bar Wi-Fi icon centre — written by the bar
// widget so the popup can be anchored beneath the icon rather than pinned to an
// edge.
const [wifiIconX, setWifiIconXState] = createState<number | null>(null)

export { wifiPopupVisible, wifiIconX }

export function openWifiPopup(): void {
  setWifiPopupVisible(true)
}

export function closeWifiPopup(): void {
  setWifiPopupVisible(false)
}

export function toggleWifiPopup(): void {
  if (wifiPopupVisible()) closeWifiPopup()
  else openWifiPopup()
}

export function setWifiIconX(x: number): void {
  setWifiIconXState(x)
}
