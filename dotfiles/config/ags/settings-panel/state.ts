import { createState } from "ags"
import { execAsync } from "ags/process"

/**
 * Shared settings-panel state.
 *
 * The panel is a second window in the existing always-on bar AGS instance.
 * Only the bar settings button and the panel itself write this state.
 */
export type SettingsView = "main" | "wifi" | "bluetooth"

// The panel runs with keyboard mode NONE (so it does not steal focus and the
// bar toggle stays reliable). Plain Escape therefore cannot reach it, so while
// the panel is open we switch Hyprland into the "settings" submap (defined in
// config/hypr/keybindings.lua), where Escape closes it.
function setSubmap(name: "settings" | "reset") {
  execAsync(["hyprctl", "dispatch", `hl.dsp.submap("${name}")`]).catch(() => "")
}

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
  setSubmap("settings")
}

export function close() {
  setPanelVisible(false)
  // Return to the main view so the next open starts clean.
  setActiveView("main")
  setSubmap("reset")
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
