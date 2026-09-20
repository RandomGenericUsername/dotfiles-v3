import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { setIconCenterX, toggle } from "../../settings-panel/state"

function getSettingsIconPath(): string | null {
  return registry.resolve("settings", "default")
}

// Last pointer x (surface coords == monitor coords, the bar spans the monitor).
// Recorded by a motion controller — which does NOT claim clicks — so the
// button's own activation still fires. Re-recorded on every hover, so moving
// the icon in the bar just works.
let lastIconX: number | null = null

export function Settings() {
  return (
    <button
      class="widget settings-widget"
      tooltipText="Settings"
      onClicked={() => {
        if (lastIconX !== null) setIconCenterX(lastIconX)
        toggle()
      }}
      $={(self) => {
        // Track the pointer x (surface coords == monitor coords; the bar spans
        // the monitor) so the panel anchors under the icon. A motion controller
        // does not claim clicks, so the button's own activation is unaffected.
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
      }}
    >
      <image
        pixel_size={28}
        class="widget-icon"
        $={(self) => self.set_from_file(getSettingsIconPath() ?? "")}
      />
    </button>
  )
}
