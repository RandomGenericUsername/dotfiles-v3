import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import {
  closeWifiPopup,
  wifiIconX,
  wifiPopupVisible,
} from "./state"
import {
  WifiContent,
} from "./WifiContent"
import { WifiSwitch } from "../primitives/WifiSwitch"
import { setWifiEnabled, wifiEnabled, wifiReady } from "../../services/wifi-service"
import { stcExpanded, wifiPromptVisible } from "./WifiContent"

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
        // Keyboard mode NONE unless a field that needs TYPED input is on
        // screen — the same rule the settings panel uses, and the reason the
        // settings icon's same-spot collapse works there.
        //
        // This effect previously forced ON_DEMAND unconditionally, which is why
        // the Wi-Fi icon alone would not collapse on a second same-spot click:
        // grabbing keyboard focus makes the bar swallow the first click. The
        // spec states it outright (add-ags-settings-panel/spec.md, "The panel
        // SHALL NOT grab keyboard focus in a way that makes the bar swallow the
        // first click"), and task 8.16 records the fix. The settings panel and
        // the audio popup both honour it; this popup was the one outlier.
        //
        // ON_DEMAND is still required at the two moments that actually accept
        // keystrokes: the Wi-Fi password prompt, and the speed-test interval
        // Gtk.Entry (which only exists while that section is expanded, with the
        // radio on and no prompt up — mirroring the block's own visible=).
        createEffect(() => {
          const stcFieldVisible = stcExpanded() && wifiEnabled() && !wifiPromptVisible()
          const needsKeyboard = wifiPromptVisible() || stcFieldVisible
          self.keymode = needsKeyboard
            ? Astal.Keymode.ON_DEMAND
            : Astal.Keymode.NONE
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
          <box valign={Gtk.Align.CENTER}>
            <WifiSwitch active={wifiEnabled} sensitive={wifiReady} onToggled={(v) => { void setWifiEnabled(v) }} />
          </box>
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
