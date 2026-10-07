import { createState } from "ags"

/**
 * Panel-agnostic battery popup state.
 *
 * Owned by an overlay that is not the settings panel, so it must not import
 * from `settings-panel/**` (one-way dependency). Mutual exclusion with the
 * panel is coordinated by the callers, not here.
 *
 * This is why `closeBatteryPopup` is called from `settings-panel/state.ts`'s
 * `open()` rather than the other way round: the panel owns the exclusion, the
 * popup just exposes the door. Mirrors `components/wifi/state.ts` exactly.
 */

const [batteryPopupVisible, setBatteryPopupVisible] = createState(false)

// X (monitor-relative) of the status-bar battery icon centre — written by the
// bar widget so the popup can be anchored beneath the icon rather than pinned
// to an edge.
const [batteryIconX, setBatteryIconXState] = createState<number | null>(null)

export { batteryPopupVisible, batteryIconX }

export function openBatteryPopup(): void {
  setBatteryPopupVisible(true)
}

export function closeBatteryPopup(): void {
  setBatteryPopupVisible(false)
}

export function toggleBatteryPopup(): void {
  if (batteryPopupVisible()) closeBatteryPopup()
  else openBatteryPopup()
}

export function setBatteryIconX(x: number): void {
  setBatteryIconXState(x)
}
