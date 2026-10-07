import { createEffect } from "ags"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { bluetoothPowered } from "../../services/bluetooth-service"
import {
  setBluetoothIconX,
  toggleBluetoothPopup,
} from "../../components/bluetooth/state"
import { close } from "../../settings-panel/state"

/**
 * The status-bar Bluetooth indicator (design §3, the `bluetooth` bar group).
 *
 * The structural twin of `network.tsx`: same registry resolution path, same
 * pointer-x recording for follower anchoring, same click-to-open.
 *
 * Reads `bluetoothPowered` straight from `bluetooth-service` — there is NO hub
 * subscription, because design §6 declined the `bluetooth.state` topic: the
 * D-Bus binding is in-process and lossless, so there is no lossy boundary for a
 * topic to protect, and RSSI would force a per-advertisement-frame publish rate
 * onto a closed `KNOWN_TOPICS` set. Accessor reads are reactive by construction,
 * so the same thing a hub subscription would have provided is already here.
 */

// Two states only, per the owner's artwork: `off` is distinguished from `on` by
// the slash in the glyph's SHAPE, never by opacity or tint. That is also why the
// glyph needs no background, pill or label of its own here — the artwork is the
// whole signal, and the contrast guard retargets its stroke to the wallpaper.
function getBluetoothIconPath(): string | null {
  const mappings = registry.getBarMappings("bluetooth")
  if (!mappings) return null

  // NOTE the keys: `bluetooth-on` / `bluetooth-off`, NOT bare `on` / `off`.
  // YAML 1.1 resolves a bare `on:`/`off:` key to a boolean, so the manifest
  // comes out of the parser with `True`/`False` keys and every lookup below
  // misses silently. Do not "simplify" these to match the variant names.
  const stateKey = bluetoothPowered() ? "bluetooth-on" : "bluetooth-off"
  const variant = mappings.states[stateKey]
  if (!variant) return null

  return registry.resolve("bluetooth", variant)
}

// Last pointer x (surface coords == monitor coords, the bar spans the monitor).
// Recorded by a motion controller — which does NOT claim clicks — so the
// button's own activation still fires. Re-recorded on every hover, so moving
// the icon in the bar just works.
let lastIconX: number | null = null

export function BluetoothStatus() {
  return (
    <button
      class="widget"
      tooltipText="Bluetooth"
      onClicked={() => {
        // Record before toggling: the follower reads this the moment the popup
        // becomes visible, so writing it after the toggle would anchor the
        // surface to the previous frame's position.
        if (lastIconX !== null) setBluetoothIconX(lastIconX)
        // Mutual exclusion is the caller's job (the state module deliberately
        // knows nothing about the settings panel), same as network.tsx: one
        // connectivity surface at a time.
        close()
        toggleBluetoothPopup()
      }}
      $={(self) => {
        // Track the pointer x so the popup can anchor under the icon. A motion
        // controller does not claim clicks, so the button's own activation is
        // unaffected. There is deliberately NO right-click gesture and NO
        // scroll gesture here (unlike network.tsx): Bluetooth is discrete, so
        // there is no continuous value to nudge and no secondary action to
        // invent.
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
        $={(self) => {
          // Inside createEffect so `bluetoothPowered()` stays subscribed and the
          // glyph swaps the moment the adapter's Powered property changes —
          // including the boot sync and the echo of the header switch's write.
          createEffect(() => {
            self.set_from_file(getBluetoothIconPath() ?? "")
          })
        }}
      />
    </button>
  )
}
