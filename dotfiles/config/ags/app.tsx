import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import Bar from "./bar/Bar"
import { SettingsCatcher, SettingsPanel } from "./settings-panel/SettingsPanel"
import { WifiPopup, WifiPopupCatcher } from "./components/wifi/WifiPopup"
import { registerBluetoothAgent } from "./settings-panel/bluetooth-agent"
import { close } from "./settings-panel/state"

app.start({
  css: style,
  // External control surface for the panel: a Hyprland keybind runs
  // `ags request settings-close` because the panel itself runs with keyboard
  // mode NONE (so plain Escape can't reach it without stealing app input).
  requestHandler(argv: string[], res: (response: unknown) => void) {
    if (argv[0] === "settings-close") {
      close()
      res("ok")
      return
    }
    res(`unknown request: ${argv.join(" ")}`)
  },
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    // BlueZ needs an org.bluez.Agent1 on the bus to complete pairing; register
    // our headless (NoInputNoOutput) agent once for the session.
    registerBluetoothAgent()
    for (const monitor of app.get_monitors()) {
      app.add_window(Bar(monitor))
    }
    const primary = app.get_monitors()[0]
    if (primary) {
      // Catcher first so the panel stacks above it on the overlay layer.
      app.add_window(SettingsCatcher(primary))
      app.add_window(SettingsPanel(primary))
      // Same ordering rule for the Wi-Fi popup: catcher first, popup above it.
      app.add_window(WifiPopupCatcher(primary))
      app.add_window(WifiPopup(primary))
    }
  },
})
