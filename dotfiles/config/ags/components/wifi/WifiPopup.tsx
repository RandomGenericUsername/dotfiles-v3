import { Gtk, Gdk } from "ags/gtk4"
import { createComputed } from "ags"
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
import { PopupCatcher, PopupHost, type PopupSurfaceSpec } from "../../kit/popup-host"

/**
 * The Wi-Fi surface body (spine AD-10): a factory, mounted by `PopupHost` only
 * while the popup is visible. The header is a SIBLING of the scrolledwindow so
 * it stays pinned; inside the scroll area it would scroll away.
 */
export const wifiSurface: PopupSurfaceSpec = {
  id: "wifi",
  width: 312,
  // Keyboard mode NONE unless a field that needs TYPED input is on screen — the
  // same rule the settings panel uses. ON_DEMAND is required at exactly two
  // moments: the Wi-Fi password prompt, and the speed-test interval Gtk.Entry
  // (which only exists while that section is expanded, with the radio on and no
  // prompt up). An unconditional ON_DEMAND would grab keyboard focus, make the
  // bar swallow the first click, and break same-spot collapse.
  keyboard: createComputed(() => {
    const stcFieldVisible = stcExpanded() && wifiEnabled() && !wifiPromptVisible()
    return wifiPromptVisible() || stcFieldVisible
  }),
  body: ({ visible }) => (
    <>
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
        <WifiContent visible={visible} />
      </scrolledwindow>
    </>
  ),
}

export function WifiPopupCatcher(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupCatcher
      name="wifi-popup-catcher"
      gdkmonitor={gdkmonitor}
      visible={wifiPopupVisible}
      onClose={closeWifiPopup}
    />
  )
}

export function WifiPopup(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupHost
      spec={wifiSurface}
      name="wifi-popup"
      gdkmonitor={gdkmonitor}
      visible={wifiPopupVisible}
      anchorX={wifiIconX}
      onClose={closeWifiPopup}
    />
  )
}
