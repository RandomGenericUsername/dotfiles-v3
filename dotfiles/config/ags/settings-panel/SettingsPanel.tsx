import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { activeView, close, iconCenterX, panelVisible, viewEpoch } from "./state"
import { wifiPromptVisible } from "../components/wifi/WifiContent"
import { MainView } from "./views/MainView"
import { WifiView } from "./views/WifiView"
import { BluetoothView } from "./views/BluetoothView"

/**
 * The click-outside catcher: a full-screen layer surface, created BEFORE the
 * panel so the panel stacks above it. Shown only while the panel is visible.
 *
 * It must be hit-testable to receive clicks; a fully transparent layer surface
 * is not (see the 1%-opacity background in style.css). Covering the whole
 * screen — including the bar — makes both same-spot (the status-bar icon) and
 * outside clicks close the panel via this single, deterministic path.
 */
export function SettingsCatcher(gdkmonitor: Gdk.Monitor) {
  const { TOP, BOTTOM, LEFT, RIGHT } = Astal.WindowAnchor

  return (
    <window
      name="settings-catcher"
      class="settings-catcher"
      gdkmonitor={gdkmonitor}
      anchor={TOP | BOTTOM | LEFT | RIGHT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      visible={panelVisible}
    >
      <box
        class="settings-catcher-fill"
        hexpand
        vexpand
        $={(self) => {
          const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
          click.connect("released", () => close())
          self.add_controller(click)
        }}
      />
    </window>
  )
}

/**
 * The settings panel: a second Astal.Window in the always-on bar instance,
 * anchored top-right on the primary monitor only. Subviews swap in place so the
 * panel dimensions stay stable.
 */
export function SettingsPanel(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT } = Astal.WindowAnchor
  let scroll: Gtk.ScrolledWindow | null = null

  // Anchor the panel beneath the status-bar settings icon rather than the
  // screen's right edge: left margin = icon centre − half the panel width,
  // clamped to the monitor. The surface width matches the content's 312px.
  const PANEL_WIDTH = 312
  const monitorWidth = gdkmonitor.get_geometry().width
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - PANEL_WIDTH - 8
    const centre = iconCenterX()
    if (centre == null) return rightMost
    const left = Math.round(centre - PANEL_WIDTH / 2)
    return Math.min(Math.max(left, 8), rightMost)
  })

  createEffect(() => {
    // `show(view)` / `back()` / `open()` bump viewEpoch; reset the scroll then.
    viewEpoch()
    panelVisible()
    if (scroll) scroll.get_vadjustment().set_value(0)
  })

  const mainVisible = createComputed(() => activeView() === "main")
  const wifiVisible = createComputed(() => activeView() === "wifi")
  const bluetoothVisible = createComputed(() => activeView() === "bluetooth")

  return (
    <window
      name="settings-panel"
      class="settings-panel"
      gdkmonitor={gdkmonitor}
      anchor={TOP | LEFT}
      /* IGNORE (not NORMAL): a popup must not request an exclusive zone, or
         Hyprland offsets the overlay surface below the bar's reserved area and
         then applies marginTop — pushing the panel ~48px too low. */
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      marginTop={52}
      marginLeft={marginLeft}
      visible={panelVisible}
      $={(self) => {
        // Keyboard mode is NONE by default so the panel does not steal focus —
        // that is what lets the bar keep click activation (reliable same-spot
        // collapse). Switch to ON_DEMAND only while the Wi-Fi password field is
        // shown, which needs typed input.
        createEffect(() => {
          self.keymode = wifiPromptVisible()
            ? Astal.Keymode.ON_DEMAND
            : Astal.Keymode.NONE
        })
        // Esc closes while the panel holds keyboard (i.e. password entry).
        const key = new Gtk.EventControllerKey()
        key.connect("key-pressed", (_controller, keyval) => {
          if (keyval === Gdk.KEY_Escape) {
            close()
            return true
          }
          return false
        })
        self.add_controller(key)
      }}
    >
      <box class="settings-surface" orientation={1} widthRequest={312}>
        <scrolledwindow
          class="settings-scroll"
          heightRequest={372}
          hscrollbarPolicy={Gtk.PolicyType.NEVER}
          vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
          $={(self) => {
            scroll = self
          }}
        >
          <box orientation={1} spacing={8}>
            <box orientation={1} spacing={8} visible={mainVisible}>
              <MainView />
            </box>
            <box orientation={1} spacing={8} visible={wifiVisible}>
              <WifiView />
            </box>
            <box orientation={1} spacing={8} visible={bluetoothVisible}>
              <BluetoothView />
            </box>
          </box>
        </scrolledwindow>
      </box>
    </window>
  )
}
