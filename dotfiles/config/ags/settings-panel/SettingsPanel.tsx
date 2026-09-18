import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { activeView, close, panelVisible, viewEpoch } from "./state"
import { MainView } from "./views/MainView"
import { WifiView } from "./views/WifiView"
import { BluetoothView } from "./views/BluetoothView"

/**
 * The click-outside catcher: a full-screen transparent layer surface, created
 * BEFORE the panel so the panel stacks above it. Shown only while the panel is
 * visible.
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
      $={(self) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("pressed", () => close())
        self.add_controller(click)
      }}
    >
      <box class="settings-catcher-fill" hexpand vexpand />
    </window>
  )
}

/**
 * The settings panel: a second Astal.Window in the always-on bar instance,
 * anchored top-right on the primary monitor only. Subviews swap in place so the
 * panel dimensions stay stable.
 */
export function SettingsPanel(gdkmonitor: Gdk.Monitor) {
  const { TOP, RIGHT } = Astal.WindowAnchor
  let scroll: Gtk.ScrolledWindow | null = null

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
      anchor={TOP | RIGHT}
      exclusivity={Astal.Exclusivity.NORMAL}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      marginTop={56}
      marginRight={8}
      visible={panelVisible}
      $={(self) => {
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
