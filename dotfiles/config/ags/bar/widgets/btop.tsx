import { execAsync } from "ags/process"
import type { BarWidgetSpec } from "../../kit/widget"
import { iconByVariant } from "../../platform/adapters/icon"

/**
 * Status-bar btop launcher, expressed as a widget DESCRIPTOR (kit/widget).
 *
 * Prototype of the descriptor model: the icon (source + variant), the tooltip
 * and the activation are data. The bar renders it through `BarWidgetButton`; this
 * file owns no JSX, no gesture wiring and no anchor bookkeeping — those are the
 * kit's, once.
 */
export const btopWidget: BarWidgetSpec<undefined> = {
  id: "btop",
  read: () => undefined,
  class: "btop-widget",
  icon: iconByVariant("btop", () => "btop"),
  tooltip: () => "System monitor (btop)",
  primary: () => {
    execAsync(["kitty", "--", "btop"]).catch(console.error)
  },
}
