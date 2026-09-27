import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import {
  closeWifiPopup,
  wifiIconX,
  wifiPopupVisible,
} from "./state"
import {
  WifiContent,
  wifiPromptVisible,
} from "./WifiContent"
import { WifiSwitch } from "../primitives/WifiSwitch"
import { setWifiEnabled, wifiEnabled, wifiReady } from "../../services/wifi-service"

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
      <box class="settings-catcher-fill" hexpand vexpand $={(self) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("released", () => closeWifiPopup())
        self.add_controller(click)
      }} />
    </window>
  )
}

export function WifiPopup(gdkmonitor: Gdk.Monitor) {
  console.error("WifiPopup: rendered, wifiPopupVisible=" + wifiPopupVisible())
  const { TOP, LEFT } = Astal.WindowAnchor
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
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      marginTop={52}
      marginLeft={marginLeft}
      visible={wifiPopupVisible}
      $={(self) => {
        createEffect(() => {
          self.keymode = wifiPromptVisible() ? Astal.Keymode.ON_DEMAND : Astal.Keymode.NONE
        })
        const key = new Gtk.EventControllerKey()
        key.connect("key-pressed", (_controller, keyval) => {
          if (keyval === Gdk.KEY_Escape) { closeWifiPopup(); return true }
          return false
        })
        self.add_controller(key)
      }}
    >
      <box class="settings-surface" orientation={1} widthRequest={312}>
        <box class="settings-nav-header" spacing={9}>
          <label class="settings-nav-title" xalign={0} hexpand label="Wi-Fi" />
          <WifiSwitch active={wifiEnabled} sensitive={wifiReady} onToggled={(v) => { void setWifiEnabled(v) }} />
        </box>
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
