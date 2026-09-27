import { Gtk } from "ags/gtk4"
import { Accessor } from "ags"

/**
 * Backend-driven power switch.
 *
 * Gtk.Switch emits `notify::active` for BOTH user flips and programmatic
 * `active=` updates (e.g. the first authoritative NM read after boot, or the
 * echo of our own Set). Calling the backend unconditionally from that handler
 * self-oscillates: backend update -> notify -> Set -> backend update -> ...
 * and a blind `toggle()` amplifies every echo into a state flip.
 *
 * So this control is strictly user-intent-only:
 * - `lastHandled` is adopted at mount ($ setup); only genuine edges proceed.
 * - an edge that matches the backend (`self.active === active()`) is a
 *   backend echo (boot sync, our own Set landing, another client, hardware
 *   killswitch) and is adopted silently, never forwarded.
 * - only an edge that DISAGREES with the backend is a user flip and reaches
 *   `onToggled` — with the explicit new value, never a blind toggle.
 * Call sites must honor that contract: `onToggled={(v) => setX(v)}`.
 */
export function WifiSwitch({
  active,
  onToggled,
  sensitive = true,
}: {
  active: Accessor<boolean>
  onToggled: (value: boolean) => void
  sensitive?: Accessor<boolean> | boolean
}) {
  let lastHandled: boolean | null = null
  return (
    <Gtk.Switch
      class="settings-switch"
      active={active}
      sensitive={sensitive}
      onNotifyActive={(self) => {
        const now = self.active
        if (lastHandled === null) {
          lastHandled = now
          console.log("wifi-switch: mount adoption", now)
          return
        }
        if (now === lastHandled) { console.log("wifi-switch: no edge", now, lastHandled); return }
        lastHandled = now
        if (now === active()) { console.log("wifi-switch: backend echo", now); return }
        console.log("wifi-switch: user flip", now)
        onToggled(now)
      }}
      $={(self) => {
        lastHandled = self.active
      }}
      canFocus={false}
    />
  )
}
