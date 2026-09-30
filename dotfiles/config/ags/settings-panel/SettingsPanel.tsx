import { Astal, Gtk, Gdk } from "ags/gtk4"
import { createComputed, createEffect } from "ags"
import { activeView, close, iconCenterX, panelVisible, viewEpoch } from "./state"
import { wifiPromptVisible } from "../components/wifi/WifiContent"
import { MainView } from "./views/MainView"
import { WifiView } from "./views/WifiView"
import { BluetoothView } from "./views/BluetoothView"
import { SubviewHeader } from "./views/SubviewHeader"

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
             in the viewport instead. The tray popup sets the height equivalent
             (propagateNaturalHeight) but never needed this — its content is
             width-bounded already. GTK4 CSS cannot express this: it has no
             `width`/`max-width` properties, only min-*. */
          propagateNaturalWidth={false}
          $={(self) => {
            scroll = self
          }}
        >
          {/* spacing 0: this is the top of the scroll viewport, directly under
              the pinned header. The old spacing={8} wrappers existed to separate
              the (then-scrolling) header from the body; with the header hoisted
              out they would just indent every view by 8px at the top of the
              scroll area. MainView keeps its own internal spacing. */}
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
      </box>
    </window>
  )
}
