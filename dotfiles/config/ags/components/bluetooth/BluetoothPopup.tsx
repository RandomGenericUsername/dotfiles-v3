import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed } from "ags"
import {
  bluetoothIconX,
  bluetoothPopupVisible,
  closeBluetoothPopup,
} from "./state"
import { BluetoothContent } from "./BluetoothContent"
import { WifiSwitch } from "../primitives/WifiSwitch"
import {
  bluetoothPowered,
  setBluetoothPowered,
} from "../../services/bluetooth-service"

export function BluetoothPopupCatcher(gdkmonitor: Gdk.Monitor) {
  const { TOP, BOTTOM, LEFT, RIGHT } = Astal.WindowAnchor
  return (
    <window
      name="bluetooth-popup-catcher"
      class="settings-catcher"
      gdkmonitor={gdkmonitor}
      anchor={TOP | BOTTOM | LEFT | RIGHT}
      // IGNORE, not NORMAL: with NORMAL Hyprland offsets the overlay below the
      // bar's reserved zone and *then* applies marginTop, which pushes the
      // popup ~48px too low. IGNORE leaves the anchor maths as the only source
      // of the offset. The same hard-won lesson as the Wi-Fi popup.
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      visible={bluetoothPopupVisible}
    >
      <box class="settings-catcher-fill" hexpand vexpand $={(self) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("released", () => closeBluetoothPopup())
        self.add_controller(click)
      }} />
    </window>
  )
}

export function BluetoothPopup(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT } = Astal.WindowAnchor
  const PANEL_WIDTH = 312
  const monitorWidth = gdkmonitor.get_geometry().width
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - PANEL_WIDTH - 8
    const centre = bluetoothIconX()
    if (centre == null) return rightMost
    const left = Math.round(centre - PANEL_WIDTH / 2)
    return Math.min(Math.max(left, 8), rightMost)
  })

  return (
    <window
      name="bluetooth-popup"
      class="settings-panel"
      gdkmonitor={gdkmonitor}
      anchor={TOP | LEFT}
      // IGNORE, not NORMAL: NORMAL makes Hyprland offset the overlay below the
      // bar's reserved zone and then applies marginTop, pushing the popup far
      // too low. This is the Wi-Fi popup's hard-won lesson.
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      // NONE, permanently — unlike the Wi-Fi popup this surface never widens
      // it. An unconditional ON_DEMAND grabs the keyboard, the bar swallows the
      // first click, and same-spot collapse stops working; Wi-Fi survives that
      // only by widening to ON_DEMAND while a field that accepts TYPED input
      // is on screen. Bluetooth has none: the shipped pairing agent is
      // NoInputNoOutput (Just Works), so there is no password prompt and no
      // Gtk.Entry. If a PIN/passkey field is ever added, widen to ON_DEMAND
      // only while that field is on screen — never unconditionally.
      keymode={Astal.Keymode.NONE}
      marginTop={52}
      marginLeft={marginLeft}
      visible={bluetoothPopupVisible}
      $={(self) => {
        // Escape dismissal, mirroring WifiPopup's handler. It is currently
        // unreachable: with keymode NONE and no entry to type into, no
        // keystroke is routed here, and dismissal rides on the catcher or on
        // `ags request popup-close` (the external control surface the popups'
        // NONE keymode makes necessary). Registered anyway so the behaviour is
        // live the instant a PIN/passkey field raises the keymode to
        // ON_DEMAND, rather than needing this file reopened then.
        const key = new Gtk.EventControllerKey()
        key.connect("key-pressed", (_controller, keyval) => {
          if (keyval === Gdk.KEY_Escape) { closeBluetoothPopup(); return true }
          return false
        })
        self.add_controller(key)
      }}
    >
      <box class="settings-surface" orientation={1} widthRequest={312}>
        {/* Header is a SIBLING of the scrolledwindow, never a child: inside
            the scroll area it scrolls away with the content, which is exactly
            what SubviewHeader.tsx exists to undo. */}
        <box class="settings-nav-header" spacing={9}>
          <label class="settings-nav-title" xalign={0} hexpand label="Bluetooth" />
          <box valign={Gtk.Align.CENTER}>
            <WifiSwitch active={bluetoothPowered} onToggled={(v) => { void setBluetoothPowered(v) }} />
          </box>
        </box>
        <scrolledwindow
          class="settings-scroll"
          vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
          hscrollbarPolicy={Gtk.PolicyType.NEVER}
          propagateNaturalHeight
          // The settings panel's rule, not the Wi-Fi popup's. Bluetooth rows
          // carry a 26-char name plus two action buttons; an unwrapped
          // Gtk.Label reports its full text as natural width, so an unclamped
          // row grows the surface past the 312px the marginLeft maths assumes
          // and runs it off the right of the monitor.
          propagateNaturalWidth={false}
          maxContentHeight={420}
        >
          <BluetoothContent visible={bluetoothPopupVisible} />
        </scrolledwindow>
      </box>
    </window>
  )
}