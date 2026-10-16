import type { BarWidgetSpec } from "../../kit/widget"
import { iconByVariant } from "ags-platform/adapters/icon"
import { setIconCenterX, toggle } from "../../settings-panel/state"

/**
 * Status-bar settings button, expressed as a widget descriptor.
 *
 * The "simple one" that exercises the parts the launchers do not: an overlay is
 * opened (`toggle`) and the follower anchor is recorded. The pointer x is
 * captured by the kit's motion controller and handed to `primary`; this file
 * decides what to do with it — anchor the panel, then toggle. The old widget
 * carried its own motion controller and `lastIconX`; here the kit owns that
 * mechanism once.
 */
export const settingsWidget: BarWidgetSpec<undefined> = {
  id: "settings",
  read: () => undefined,
  class: "settings-widget",
  icon: iconByVariant("settings", () => "default"),
  tooltip: () => "Settings",
  primary: (_state, anchorX) => {
    if (anchorX !== null) setIconCenterX(anchorX)
    toggle()
  },
}
