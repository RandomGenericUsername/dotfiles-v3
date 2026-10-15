import { execAsync } from "ags/process"
import { iconByStateKey } from "../../platform/adapters/icon"
import { overlays } from "../../kit/overlay"
import type { DescriptorSpec } from "../../kit/widget"
import { batteryStateKey } from "../../components/battery/battery-icon"
import {
  formatBatteryStatusLine,
  formatPercentage,
} from "../../components/battery/presentation"
import { activeProfile } from "../../services/power-service"
import { createBatteryReadModel } from "../../domains/battery/astal"
import type { BatteryReading } from "../../domains/battery/read-model"

/**
 * The status-bar battery indicator, as a `DescriptorSpec` (spine AD-8; doc 101
 * §5): an icon + a tooltip, so it is the descriptor shape.
 *
 * This widget is a VIEW: the `domains/battery` read model supplies the reading
 * (AD-2/AD-3), the icon is a state-key ref resolved through the one chain
 * (AD-7), and the shell owns the root button, the tooltip, the anchor record and
 * the gestures. The power-profile D-Bus proxy and the `/etc/power-options`
 * monitor live in `services/power-service.ts`, never here.
 *
 * The power-profile `<popover>` this used to carry is gone: profiles are in the
 * panel, where the daemon's `active_profile` index decides the mode.
 */

/** Tooltip fallback when the daemon reports no capacity at all. */
const NO_PERCENTAGE = "—"

/**
 * The battery glyph, as a state-key ref (spine AD-7): code emits the key
 * (`charging-75`), the manifest's `bar_mappings.states` maps it to a variant,
 * and the registry maps the variant to art. A key with no table entry blanks
 * rather than throwing.
 */
const batteryIcon = iconByStateKey(
  "battery",
  (s: BatteryReading) => batteryStateKey(s.percentage, s.charging),
)

export function createBatteryWidget(): DescriptorSpec<BatteryReading> {
  const reading = createBatteryReadModel()

  return {
    id: "battery",
    read: () => reading(),
    class: "battery-widget",
    pixelSize: 36,
    visible: (s) => s.isPresent,
    tooltip: (s) => {
      // Both halves of this line are presentation decisions, made in
      // presentation.ts and only composed here: the percentage through
      // `formatPercentage` (one rounding for the tooltip AND the panel header)
      // and the status line through `formatBatteryStatusLine` (one state word,
      // one missing-estimate degradation). Re-deriving either in this widget is
      // exactly how a tooltip ends up disagreeing with the panel it opens.
      //
      // The reading is a 0..1 FRACTION; the helpers take 0..100.
      const pct = formatPercentage(s.percentage * 100) ?? NO_PERCENTAGE
      const prof = activeProfile()
      // A null profile means the daemon has not answered yet. Printing the raw
      // value, or a boot default that looks like a real reading, both lie;
      // dropping the segment keeps the line that IS known.
      const head = prof === null ? pct : `${pct} — ${prof}`
      const seconds = s.charging ? s.timeToFull : s.timeToEmpty
      return `${head}\n${formatBatteryStatusLine(seconds, s.charging)}`
    },
    icon: batteryIcon,
    // Left click opens the panel; the coordinator closes the other overlays
    // first (settings, Wi-Fi, Bluetooth, audio), so they stay mutually
    // exclusive, and stores the pointer x for follower anchoring.
    primary: (_s, anchorX) => overlays.toggle("battery", anchorX),
    // Right click keeps the daemon's own GTK frontend, which is what it has
    // always done on this widget — and which the panel's last row now also
    // offers. Left/right rather than a popover keeps the two behaviours
    // reachable without a third surface.
    secondary: () => {
      execAsync(["power-options-gtk"]).catch((e) => {
        console.error("power-options-gtk launch failed:", e)
      })
    },
  }
}
