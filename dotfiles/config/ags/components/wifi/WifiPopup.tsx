import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import {
  closeWifiPopup,
  wifiIconX,
  wifiPopupVisible,
} from "./state"
import {
  WifiContent,
  WifiToggle,
  wifiPromptVisible,
} from "./WifiContent"

/**
 * The click-outside catcher for the Wi-Fi popup: a full-screen layer surface,
 * created BEFORE the popup so the popup stacks above it. Shown only while the
 * popup is visible.
 *
 * It must be hit-testable to receive clicks; a fully transparent layer surface
 * is not (see the 1%-opacity background in style.css). Covering the whole
 * screen — including the bar — makes both same-spot (the Wi-Fi icon) and
 * outside clicks close the popup via this single, deterministic path.
 */
export function WifiPopupCatcher(gdkmonitor: Gdk.Monitor) {
  const { TOP, BOTTOM, LEFT, RIGHT } = Astal.WindowAnchor

  return (
    <window
      name="wifi-popup-catcher"
      class="settings-catcher"
      gdkmonitor={gdkmonitor}
      anchor={TOP | BOTTOM | LEFT | RIGHT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      visible={wifiPopupVisible}
    >
      <box
        class="settings-catcher-fill"
        hexpand
        vexpand
        $={(self) => {
          const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
          click.connect("released", () => closeWifiPopup())
          self.add_controller(click)
        }}
      />
    </window>
  )
}

/**
 * The Wi-Fi popup: a window anchored beneath the status-bar Wi-Fi icon, shown
 * on right-click. It reuses the settings-panel surface styling but is otherwise
 * independent of it (one-way dependency).
 */
export function WifiPopup(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT } = Astal.WindowAnchor

  // Anchor beneath the Wi-Fi icon rather than an edge: left margin = icon
  // centre − half the width, clamped to the monitor. Matches the panel's 312px.
  const PANEL_WIDTH = 312
  const monitorWidth = gdkmonitor.get_geometry().width
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - PANEL_WIDTH - 8
    const centre = wifiIconX()
    if (centre == null) return rightMost
    const left = Math.round(centre - PANEL_WIDTH / 2)
    return Math.min(Math.max(left, 8), rightMost)
  })

  return (
    <window
      name="wifi-popup"
      class="settings-panel"
      gdkmonitor={gdkmonitor}
      anchor={TOP | LEFT}
      /* IGNORE (not NORMAL): a popup must not request an exclusive zone, or
         Hyprland offsets the overlay surface below the bar's reserved area and
         then applies marginTop — pushing the popup ~48px too low. */
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      marginTop={52}
      marginLeft={marginLeft}
      visible={wifiPopupVisible}
      $={(self) => {
        // Keyboard mode is NONE by default so the popup does not steal focus;
        // that is what lets the bar keep click activation (reliable same-spot
        // collapse). Switch to ON_DEMAND only while the Wi-Fi password field is
        // shown, which needs typed input.
        createEffect(() => {
          self.keymode = wifiPromptVisible()
            ? Astal.Keymode.ON_DEMAND
            : Astal.Keymode.NONE
        })
        // Esc closes while the popup holds keyboard (i.e. password entry).
        const key = new Gtk.EventControllerKey()
        key.connect("key-pressed", (_controller, keyval) => {
          if (keyval === Gdk.KEY_Escape) {
            closeWifiPopup()
            return true
          }
          return false
        })
        self.add_controller(key)
      }}
    >
      <box class="settings-surface" orientation={1} widthRequest={312}>
        <box class="settings-nav-header" spacing={9}>
          <label
            class="settings-nav-title"
            xalign={0}
            hexpand
            label="Wi-Fi"
          />
          <WifiToggle />
        </box>
        {/* Bound the list height and scroll it: the popup must not grow to the
            full window height when many networks are in range. The header stays
            fixed; only the content scrolls. */}
        <scrolledwindow
          class="settings-scroll"
          vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
          hscrollbarPolicy={Gtk.PolicyType.NEVER}
          propagateNaturalHeight
          maxContentHeight={420}
        >
          <WifiContent visible={wifiPopupVisible} />
        </scrolledwindow>
      </box>
    </window>
  )
}
