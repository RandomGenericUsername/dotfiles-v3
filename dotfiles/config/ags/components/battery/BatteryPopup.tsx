import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { closeBatteryPopup, batteryIconX, batteryPopupVisible } from "./state"
import { wifiPopupVisible } from "../wifi/state"
import { BatteryContent } from "./BatteryContent"

/**
 * The battery popup: a click-catcher plus the panel itself.
 *
 * TWO WINDOWS, NOT ONE. The panel is `Astal.Layer.OVERLAY` with
 * `Astal.Exclusivity.IGNORE`, so it does not dim or block the desktop and
 * clicks fall through it. The catcher is a second full-screen window on the
 * same layer whose only job is to absorb the click that lands OUTSIDE the
 * panel. Registration order in `app.tsx` is therefore load-bearing: the catcher
 * is added FIRST so the panel stacks ABOVE it, and a click on the panel itself
 * reaches the panel rather than the catcher underneath. Mirrors `WifiPopup`.
 */
export function BatteryPopupCatcher(gdkmonitor: Gdk.Monitor) {
  const { TOP, BOTTOM, LEFT, RIGHT } = Astal.WindowAnchor
  return (
    <window
      name="battery-popup-catcher"
      class="settings-catcher"
      gdkmonitor={gdkmonitor}
      anchor={TOP | BOTTOM | LEFT | RIGHT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      visible={batteryPopupVisible}
    >
      <box class="settings-catcher-fill" hexpand vexpand $={(self) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("released", () => closeBatteryPopup())
        self.add_controller(click)
      }} />
    </window>
  )
}

export function BatteryPopup(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT } = Astal.WindowAnchor
  const PANEL_WIDTH = 312
  const monitorWidth = gdkmonitor.get_geometry().width
  // Anchored under the status-bar battery icon, clamped into the monitor: the
  // icon is near the RIGHT edge, so a naive centre-the-panel offset would push
  // most of it off-screen. `batteryIconX` is written by the bar widget's motion
  // controller on every hover, so the anchor follows the icon for free; when it
  // has never been written (panel opened without hovering) the panel falls back
  // to the right-most on-screen position rather than to `null`/0.
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - PANEL_WIDTH - 8
    const centre = batteryIconX()
    if (centre == null) return rightMost
    const left = Math.round(centre - PANEL_WIDTH / 2)
    return Math.min(Math.max(left, 8), rightMost)
  })

  return (
    <window
      name="battery-popup"
      class="settings-panel"
      gdkmonitor={gdkmonitor}
      anchor={TOP | LEFT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      marginTop={52}
      marginLeft={marginLeft}
      visible={batteryPopupVisible}
      $={(self) => {
        // No keyboard mode is ever requested for this panel: nothing in it
        // accepts TYPED input (no entry, no password prompt), so claiming the
        // keyboard would cost every keystroke to the bar for no benefit. The
        // settings panel and the Wi-Fi popup both earn ON_DEMAND conditionally;
        // this panel never does, and `NONE` is the honest answer rather than a
        // copy of their default. Escape still arrives via the key controller,
        // which the compositor delivers without ON_DEMAND.
        const key = new Gtk.EventControllerKey()
        key.connect("key-pressed", (_controller, keyval) => {
          if (keyval === Gdk.KEY_Escape) { closeBatteryPopup(); return true }
          return false
        })
        self.add_controller(key)
        createEffect(() => {
          // Keep the keymode pinned even as the window is shown/hidden: the
          // comment above states the invariant, so the effect reasserts it
          // rather than relying on the initial prop alone.
          self.keymode = Astal.Keymode.NONE
          void batteryPopupVisible()
        })
        // THE OTHER HALF OF THE WI-FI EXCLUSION. The battery bar icon closes
        // the Wi-Fi popup before opening this one, so the direction "battery
        // opens, wifi must go" is covered at the click site. This covers the
        // reverse without editing `bar/widgets/network.tsx`: if the Wi-Fi popup
        // ever becomes visible while this panel is up, stand down.
        //
        // WHY IT MATTERS. Both panels are OVERLAY/IGNORE windows with their own
        // full-screen catcher, and the catcher is registered FIRST so its panel
        // stacks above. Two of them open at once means two live catchers, and the
        // top one swallows every click outside itself, so the panel underneath
        // is not merely ugly, it is UNREACHABLE, and a click that looks like it
        // dismissed one overlay has silently dismissed neither.
        createEffect(() => {
          if (wifiPopupVisible()) closeBatteryPopup()
        })
      }}
    >
      <box class="settings-surface" orientation={1} widthRequest={312}>
        <BatteryContent visible={batteryPopupVisible} />
      </box>
    </window>
  )
}
