import { execAsync } from "ags/process"
import type { BarWidgetSpec } from "../../kit/widget"
import { iconByVariant } from "../../platform/adapters/icon"

/** Status-bar Thunderbird launcher, expressed as a widget descriptor. */
export const thunderbirdWidget: BarWidgetSpec<undefined> = {
  id: "thunderbird",
  read: () => undefined,
  class: "thunderbird-widget",
  icon: iconByVariant("thunderbird", () => "thunderbird"),
  tooltip: () => "Mail (Thunderbird)",
  primary: () => {
    execAsync(["thunderbird"]).catch(console.error)
  },
}
