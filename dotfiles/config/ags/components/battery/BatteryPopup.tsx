import { Gdk } from "ags/gtk4"
import { createEffect } from "ags"
import { closeBatteryPopup, batteryIconX, batteryPopupVisible } from "./state"
import { wifiPopupVisible } from "../wifi/state"
import { BatteryContent } from "./BatteryContent"
import { PopupCatcher, PopupHost, type PopupSurfaceSpec } from "../../kit/popup-host"

/**
 * The battery surface body (spine AD-10): a factory, mounted by `PopupHost` only
 * while the popup is visible. No keyboard mode is ever requested: nothing in it
 * accepts TYPED input (no entry, no password prompt), so claiming the keyboard
 * would cost every keystroke to the bar for no benefit.
 */
export const batterySurface: PopupSurfaceSpec = {
  id: "battery",
  width: 312,
  body: ({ visible }) => <BatteryContent visible={visible} />,
}

export function BatteryPopupCatcher(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupCatcher
      name="battery-popup-catcher"
      gdkmonitor={gdkmonitor}
      visible={batteryPopupVisible}
      onClose={closeBatteryPopup}
    />
  )
}

export function BatteryPopup(gdkmonitor: Gdk.Monitor) {
  // THE OTHER HALF OF THE WI-FI EXCLUSION. The battery bar icon closes the Wi-Fi
  // popup before opening this one, so the direction "battery opens, wifi must go"
  // is covered at the click site. This covers the reverse without editing
  // `bar/widgets/network.tsx`: if the Wi-Fi popup ever becomes visible while this
  // panel is up, stand down.
  //
  // WHY IT MATTERS. Both panels are OVERLAY/IGNORE windows with their own
  // full-screen catcher, and the catcher is registered FIRST so its panel stacks
  // above. Two of them open at once means two live catchers, and the top one
  // swallows every click outside itself, so the panel underneath is not merely
  // ugly, it is UNREACHABLE.
  createEffect(() => {
    if (wifiPopupVisible()) closeBatteryPopup()
  })
  return (
    <PopupHost
      spec={batterySurface}
      name="battery-popup"
      gdkmonitor={gdkmonitor}
      visible={batteryPopupVisible}
      anchorX={batteryIconX}
      onClose={closeBatteryPopup}
    />
  )
}
