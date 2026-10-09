import { execAsync } from "ags/process"
import type { BarWidgetSpec } from "../../kit/widget"
import { iconByStateKey } from "../../kit/icon"

/**
 * Status-bar power menu launcher, expressed as a widget descriptor.
 *
 * Uses `iconByStateKey` (the `power-menu` group's `bar_mappings.states` table)
 * rather than `iconByVariant`, exercising the state-key resolution path in the
 * kit — the path the battery/network/bluetooth widgets will use.
 */
export const powerMenuWidget: BarWidgetSpec<undefined> = {
  id: "power-menu",
  read: () => undefined,
  class: "power-menu-widget",
  icon: iconByStateKey("power-menu", () => "default"),
  primary: () => {
    execAsync(["wlogout"]).catch(console.error)
  },
}
