import { Gtk, Gdk } from "ags/gtk4"
import {
  bluetoothIconX,
  bluetoothPopupVisible,
  closeBluetoothPopup,
} from "./state"
import { BluetoothContent, dismissUnpairConfirm } from "./BluetoothContent"
import { WifiSwitch } from "../primitives/WifiSwitch"
import {
  bluetoothPowered,
  bluetoothReady,
  setBluetoothPowered,
} from "../../services/bluetooth-service"
import { PopupCatcher, PopupHost, type PopupSurfaceSpec } from "../../kit/popup-host"

/**
 * The Bluetooth surface body (spine AD-10): a factory, mounted by `PopupHost`
 * only while the popup is visible.
 */
export const bluetoothSurface: PopupSurfaceSpec = {
  id: "bluetooth",
  width: 312,
  // Keymode NONE, permanently — unlike the Wi-Fi popup this surface never widens
  // it. An unconditional ON_DEMAND grabs the keyboard, the bar swallows the
  // first click, and same-spot collapse stops working; Wi-Fi survives that only
  // by widening to ON_DEMAND while a field that accepts TYPED input is on
  // screen. Bluetooth has none: the shipped pairing agent is NoInputNoOutput
  // (Just Works), so there is no password prompt and no Gtk.Entry. If a
  // PIN/passkey field is ever added, add a `keyboard` accessor that reads true
  // only while that field is on screen — never unconditionally.
  body: ({ visible }) => (
    <>
      {/* Header is a SIBLING of the scrolledwindow, never a child: inside the
          scroll area it scrolls away with the content, which is exactly what
          SubviewHeader.tsx exists to undo. */}
      <box class="settings-nav-header" spacing={9}>
        <label class="settings-nav-title" xalign={0} hexpand label="Bluetooth" />
        {/* `sensitive={bluetoothReady}` — the SAME accessor the settings
            subview's header passes, so both surfaces go insensitive for one and
            the same reason: no `Adapter1` on the bus, so a power write cannot
            land. */}
        <box valign={Gtk.Align.CENTER}>
          <WifiSwitch active={bluetoothPowered} sensitive={bluetoothReady} onToggled={(v) => { void setBluetoothPowered(v) }} />
        </box>
      </box>
      <scrolledwindow
        class="settings-scroll"
        vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
        hscrollbarPolicy={Gtk.PolicyType.NEVER}
        propagateNaturalHeight
        // The settings panel's rule, not the Wi-Fi popup's: Bluetooth rows carry
        // a 26-char name plus two action buttons; an unwrapped Gtk.Label reports
        // its full text as natural width, so an unclamped row grows the surface
        // past the 312px the marginLeft maths assumes and runs it off the right
        // of the monitor.
        propagateNaturalWidth={false}
        maxContentHeight={420}
      >
        <BluetoothContent visible={visible} owner="popup" />
      </scrolledwindow>
    </>
  ),
}

export function BluetoothPopupCatcher(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupCatcher
      name="bluetooth-popup-catcher"
      gdkmonitor={gdkmonitor}
      visible={bluetoothPopupVisible}
      onClose={() => {
        // Order is the requirement, not a style preference: an open unpair
        // confirm is dismissed BEFORE the surface closes, so the two events are
        // never conflated into one and a confirm can never outlive the popup it
        // was opened in.
        dismissUnpairConfirm()
        closeBluetoothPopup()
      }}
    />
  )
}

export function BluetoothPopup(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupHost
      spec={bluetoothSurface}
      name="bluetooth-popup"
      gdkmonitor={gdkmonitor}
      visible={bluetoothPopupVisible}
      anchorX={bluetoothIconX}
      onClose={() => {
        // Same before-the-surface ordering as the catcher.
        dismissUnpairConfirm()
        closeBluetoothPopup()
      }}
    />
  )
}
