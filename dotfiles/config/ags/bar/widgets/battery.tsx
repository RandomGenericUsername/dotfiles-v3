import Battery from "gi://AstalBattery"
import { createBinding, createEffect } from "ags"
import { registry } from "../../lib/icon-registry"

const device = Battery.get_default()
const percentage = createBinding(device, "percentage")
const charging = createBinding(device, "charging")
const isPresent = createBinding(device, "is-present")

function getBatteryStateKey(pct: number, chg: boolean): string {
  const level =
    pct < 0.25 ? "0"
    : pct < 0.5 ? "25"
    : pct < 0.75 ? "50"
    : pct < 1 ? "75"
    : "100"

  return chg ? `charging-${level}` : `discharging-${level}`
}

function getBatteryIconPath(pct: number, chg: boolean): string | null {
  const mappings = registry.getBarMappings("battery")
  if (!mappings) return null

  const stateKey = getBatteryStateKey(pct, chg)
  const variant = mappings.states[stateKey]
  if (!variant) return null

  return registry.resolve("battery", variant)
}

function getBatteryLabel(pct: number): string {
  return `${Math.round(pct * 100)}%`
}

export function BatteryIndicator() {
  return (
    <box
      class="widget battery-widget"
      visible={isPresent((present) => present)}
    >
      <image
        class="widget-icon"
        $={(self) => {
          createEffect(() => {
            self.set_from_file(
              getBatteryIconPath(percentage(), device.charging) ?? ""
            )
          })
        }}
      />
    </box>
  )
}
