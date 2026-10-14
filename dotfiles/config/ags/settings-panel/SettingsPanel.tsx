import { Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { activeView, close, iconCenterX, panelVisible, viewEpoch } from "./state"
import {
  stcExpanded,
  wifiPromptVisible,
} from "../components/wifi/WifiContent"
import { wifiEnabled } from "../services/wifi-service"
import { MainView } from "./views/MainView"
import { WifiView } from "./views/WifiView"
import { BluetoothView } from "./views/BluetoothView"
import { SubviewHeader } from "./views/SubviewHeader"
import { PopupCatcher, PopupHost, type PopupSurfaceSpec } from "../kit/popup-host"

/**
 * The settings surface body (spine AD-10): a factory, mounted by `PopupHost` only
 * while the panel is visible. Subviews swap in place so the panel dimensions stay
 * stable.
 */
export const settingsSurface: PopupSurfaceSpec = {
  id: "settings",
  width: 312,
  // Keyboard mode is NONE by default so the panel does not steal focus — that is
  // what lets the bar keep click activation (reliable same-spot collapse). Switch
  // to ON_DEMAND only while a field that needs typed input is actually on screen.
  //
  // BOTH conditions are required, not just the password prompt: the speed-test
  // interval control is a Gtk.Entry too (WifiContent.tsx, IntervalMsControl), and
  // with keymode NONE the panel holds no keyboard, so clicking it focused nothing
  // and every keystroke went to the bar instead. `stcExpanded` gates that entry,
  // hence the dependency; and the speed-test block also requires Wi-Fi on and no
  // prompt up, so collapse the section while the radio is off and the panel must
  // NOT keep the keyboard.
  keyboard: createComputed(() => {
    const stcFieldVisible = stcExpanded() && wifiEnabled() && !wifiPromptVisible()
    return wifiPromptVisible() || stcFieldVisible
  }),
  body: () => {
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
      <>
        {/* Pinned above the scroll, matching the tray popup: the header is a
            SIBLING of the scrolled window there, so it stays put. Hidden on
            "main", which has no header. */}
        <SubviewHeader />
        <scrolledwindow
          class="settings-scroll"
          /* 372 was the full panel height back when the header scrolled INSIDE
             this area. The pinned header now sits above it, so the scroll
             region is reduced by the header's height (26px row + 7px bottom
             padding, see .settings-nav-header) to keep the overall panel the
             same size and stop it growing past the bar. */
          heightRequest={339}
          hscrollbarPolicy={Gtk.PolicyType.NEVER}
          vscrollbarPolicy={Gtk.PolicyType.AUTOMATIC}
          /* Without this the scrolled window propagates its child's natural
             width upward, so any row wider than 312 (a long SSID, the net
             action button) grows the surface past the PANEL_WIDTH the margin
             math assumes. marginLeft only clamps the LEFT edge to >= 8, so the
             grown panel runs off the right of the monitor. Stopping width
             propagation pins the surface at 312 and lets overlong content clip
             in the viewport instead. */
          propagateNaturalWidth={false}
          $={(self) => {
            scroll = self
          }}
        >
          {/* spacing 0: this is the top of the scroll viewport, directly under
              the pinned header. */}
          <box orientation={1}>
            <box visible={mainVisible}>
              <MainView />
            </box>
            <box visible={wifiVisible}>
              <WifiView />
            </box>
            <box visible={bluetoothVisible}>
              <BluetoothView />
            </box>
          </box>
        </scrolledwindow>
      </>
    )
  },
}

/**
 * The click-outside catcher. A full-screen layer surface, created BEFORE the
 * panel so the panel stacks above it. It must be hit-testable to receive clicks
 * (see the 1%-opacity background in style.css). Covering the whole screen —
 * including the bar — makes both same-spot (the status-bar icon) and outside
 * clicks close the panel via this single, deterministic path.
 */
export function SettingsCatcher(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupCatcher
      name="settings-catcher"
      gdkmonitor={gdkmonitor}
      visible={panelVisible}
      onClose={close}
    />
  )
}

/** The settings panel, anchored top-right on the primary monitor only. */
export function SettingsPanel(gdkmonitor: Gdk.Monitor) {
  return (
    <PopupHost
      spec={settingsSurface}
      name="settings-panel"
      gdkmonitor={gdkmonitor}
      visible={panelVisible}
      anchorX={iconCenterX}
      onClose={close}
    />
  )
}
