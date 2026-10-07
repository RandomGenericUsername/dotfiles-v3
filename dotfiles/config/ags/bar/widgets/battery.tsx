import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import Battery from "gi://AstalBattery"
import { createBinding, createComputed, createEffect } from "ags"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import { batteryStateKey } from "../../components/battery/battery-icon"
import {
  formatBatteryStatusLine,
  formatPercentage,
} from "../../components/battery/presentation"
import { setBatteryIconX, toggleBatteryPopup } from "../../components/battery/state"
import { closeWifiPopup } from "../../components/wifi/state"
import { close } from "../../settings-panel/state"
import { activeProfile } from "../../services/power-service"

/**
 * The status-bar battery indicator.
 *
 * This widget is a VIEW: it binds the battery, resolves a glyph, and opens or
 * dismisses surfaces. The power-profile D-Bus proxy and the
 * `/etc/power-options` monitor used to be built HERE at module scope, which
 * meant they were created as a side effect of the widget module loading and had
 * no teardown path; they now live in `services/power-service.ts`, alongside the
 * wifi service's ownership of the NetworkManager bus.
 *
 * The power-profile `<popover>` this used to carry is gone. A `<popover>` is a
 * GtkPopover, which the compositor places by its own idea of where "below the
 * widget" is — it does not honour the panel's anchoring, does not follow the
 * icon, and is not dismissable by the same click-outside/Escape paths as every
 * other overlay in this bar. The profiles are now in the panel, where the
 * daemon's `active_profile` index decides which mode and variant are selected.
 */

const device = Battery.get_default()
const percentage = createBinding(device, "percentage")
const charging = createBinding(device, "charging")
const isPresent = createBinding(device, "isPresent")
const timeToFull = createBinding(device, "timeToFull")
const timeToEmpty = createBinding(device, "timeToEmpty")

function getBatteryIconPath(): string | null {
  const mappings = registry.getBarMappings("battery")
  if (!mappings) return null
  const variant = mappings.states[batteryStateKey(percentage(), charging())]
  if (!variant) return null
  return registry.resolve("battery", variant)
}

/** Tooltip fallback when the daemon reports no capacity at all. */
const NO_PERCENTAGE = "—"

// Last pointer x (surface coords == monitor coords, the bar spans the monitor).
// Recorded by a motion controller — which does NOT claim clicks — so the
// button's own activation still fires. Re-recorded on every hover, so moving the
// icon in the bar just works.
let lastIconX: number | null = null

export function BatteryIndicator() {
  return (
    <box
      visible={isPresent((present) => present)}
      tooltipText={createComputed(() => {
        // Both halves of this line are presentation decisions, made in
        // presentation.ts and only composed here: the percentage through
        // `formatPercentage` (one rounding for the tooltip AND the panel header)
        // and the status line through `formatBatteryStatusLine` (one state
        // word, one missing-estimate degradation). Re-deriving either in this
        // widget is exactly how a tooltip ends up disagreeing with the panel it
        // opens.
        //
        // The binding is a 0..1 FRACTION; the helpers take 0..100.
        const pct = formatPercentage(percentage() * 100) ?? NO_PERCENTAGE
        const prof = activeProfile()
        // A null profile means the daemon has not answered yet. Printing the
        // raw value, or a boot default that looks like a real reading, both
        // lie; dropping the segment keeps the line that IS known.
        const head = prof === null ? pct : `${pct} — ${prof}`
        const isCharging = charging()
        const seconds = isCharging ? timeToFull() : timeToEmpty()
        return `${head}\n${formatBatteryStatusLine(seconds, isCharging)}`
      })}
    >
      <button
        class="widget battery-widget"
        onClicked={() => {
          // Left click opens the panel. Closing the OTHER overlays first is
          // what makes them mutually exclusive from this side:
          //
          //  - the settings panel, whose `open()` in turn calls
          //    `closeBatteryPopup()`, so neither can be left stranded on top;
          //  - the Wi-Fi popup, which is the one overlay whose own open path
          //    (`bar/widgets/network.tsx`) cannot know this panel exists, so
          //    the exclusion has to be driven from here. Without it, clicking
          //    the battery icon while the Wi-Fi popup is up opens a SECOND
          //    overlay on the same layer, and both catchers are live: the top
          //    one eats every click outside itself and the panel underneath is
          //    unreachable.
          close()
          closeWifiPopup()
          if (lastIconX !== null) setBatteryIconX(lastIconX)
          toggleBatteryPopup()
        }}
        $={(self) => {
          // A motion controller (which does not claim clicks) records the
          // pointer x so the popup can be positioned under the icon.
          const motion = new Gtk.EventControllerMotion()
          motion.connect("motion", () => {
            const event = motion.get_current_event()
            if (!event) return
            // Gdk.Event.get_position() -> [ok, x, y] in gjs.
            const pos = event.get_position() as unknown
            if (Array.isArray(pos) && pos.length >= 3) {
              const x = Number(pos[1])
              if (Number.isFinite(x) && x > 0) lastIconX = x
            }
          })
          self.add_controller(motion)

          // Right click keeps the daemon's own GTK frontend, which is what it
          // has always done on this widget — and which the panel's last row now
          // also offers. Left/right rather than a popover keeps the two
          // behaviours reachable without a third surface.
          const secondary = new Gtk.GestureClick({ button: Gdk.BUTTON_SECONDARY })
          secondary.connect("pressed", () => {
            execAsync(["power-options-gtk"]).catch((e) => {
              console.error("power-options-gtk launch failed:", e)
            })
          })
          self.add_controller(secondary)
        }}
      >
        <image
          pixel_size={36}
          class="widget-icon"
          $={(self) => {
            createEffect(() => {
              self.set_from_file(getBatteryIconPath() ?? "")
            })
          }}
        />
      </button>
    </box>
  )
}

