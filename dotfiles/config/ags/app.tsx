import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import Bar from "./bar/Bar"
import { SettingsCatcher, SettingsPanel } from "./settings-panel/SettingsPanel"
import { WifiPopup, WifiPopupCatcher } from "./components/wifi/WifiPopup"
import { registerBluetoothAgent } from "./settings-panel/bluetooth-agent"
import { close as closeSettings } from "./settings-panel/state"
import { AudioCatcher, AudioPopup } from "./audio/AudioPopup"
import { close as closeAudio, debugAudioState } from "./audio/state"
import { BatteryPopup, BatteryPopupCatcher } from "./components/battery/BatteryPopup"
import { closeBatteryPopup } from "./components/battery/state"
import { closeWifiPopup } from "./components/wifi/state"

app.start({
  css: style,
  // External control surface for the popups: a Hyprland keybind runs
  // `ags request popup-close` because the popups run with keyboard mode NONE
  // (so plain Escape can't reach them without stealing app input). One global
  // Esc dismisses whichever popup is open.
  //
  // EVERY overlay that can be opened from the bar must be closed here, or Esc
  // strands it: the request handler is the only dismissal path that does not
  // depend on the pointer being over the popup, and the popups hold no keyboard
  // to catch Escape themselves. That is why this list enumerates the surfaces
  // rather than calling a shared "close everything" helper — a helper would have
  // to know the full set anyway, and each name here is a visible obligation to
  // add the next one. (The Wi-Fi popup was missing from this list before this
  // change; it is a pre-existing gap of exactly this class, not a new one.)
  requestHandler(argv: string[], res: (response: unknown) => void) {
    if (argv[0] === "popup-close") {
      closeSettings()
      closeAudio()
      closeWifiPopup()
      closeBatteryPopup()
      res("ok")
      return
    }
    // Legacy name kept for compatibility with older keybinds.
    if (argv[0] === "settings-close") {
      closeSettings()
      res("ok")
      return
    }
    // Bar-process introspection: dumps the audio state AS THE BAR SEES IT
    // (wp.nodes binding contents, row resolution). Read-only.
    if (argv[0] === "audio-debug") {
      try {
        res(JSON.stringify(debugAudioState()))
      } catch (e) {
        res(`audio-debug failed: ${String(e)}`)
      }
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
      // Battery popup: catcher first, popup above it, same rule again.
      app.add_window(BatteryPopupCatcher(primary))
      app.add_window(BatteryPopup(primary))
      // Audio popup: catcher + popup, same stacking order.
      app.add_window(AudioCatcher(primary))
      app.add_window(AudioPopup(primary))
    }
  },
})
