import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import Bar from "./bar/Bar"
import { SettingsCatcher, SettingsPanel } from "./settings-panel/SettingsPanel"
import { WifiPopup, WifiPopupCatcher } from "./components/wifi/WifiPopup"
import { BluetoothPopup, BluetoothPopupCatcher } from "./components/bluetooth/BluetoothPopup"
import { registerBluetoothAgent } from "./settings-panel/bluetooth-agent"
import { close as closeSettings } from "./settings-panel/state"
import { AudioCatcher, AudioPopup } from "./audio/AudioPopup"
import { audioPanelBinding } from "./audio/composition"
import { close as closeAudio, debugAudioState, open as openAudio } from "./audio/state"
import { closeBluetoothPopup } from "./components/bluetooth/state"
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
      closeBluetoothPopup()
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
    // Dumps the NEW hexagonal projection (audio/composition.ts) to
    // ~/.local/state/ags/panel-debug.json. Exists because the panel rendered
    // with an empty session while every static gate passed: reading the source
    // could not tell us whether volume/position data was absent, zero, or never
    // refreshed. This asks the running pipeline instead. Read-only.
    // Opens the audio popup so it can be measured. Added because the panel's
    // height was being diagnosed from screenshots, which cannot distinguish
    // "the window is capped" from "the content is long" -- the layer geometry
    // can. Debug-only; the bar icon remains the real entry point.
    if (argv[0] === "audio-panel-open") {
      openAudio()
      res("ok")
      return
    }
    if (argv[0] === "audio-panel-debug") {
      try {
        const model = audioPanelBinding().model()
        const dump = {
          outputs: model.outputs.map((o) => ({ id: o.id, name: o.name, available: o.available, volume: o.volume })),
          inputs: model.inputs.map((i) => ({ id: i.id, name: i.name, available: i.available, volume: i.volume })),
          input: model.input,
          inputConsumers: model.inputConsumers,
          rows: model.rows.map((r) => ({
            appId: r.appId,
            appName: r.appName,
            title: r.title,
            artist: r.artist,
            routeLabel: r.routeLabel,
            routeIntent: r.routeIntent,
            observedEndpointId: r.observedEndpointId,
            streamIds: r.streamIds,
            streams: r.streams,
            volume: r.volume,
            mixedLevel: r.mixedLevel,
            positionUs: r.positionUs,
            durationUs: r.durationUs,
            canSeek: r.canSeek,
            hasCurrentPlayer: r.hasCurrentPlayer,
            hasCurrentStream: r.hasCurrentStream,
            playback: r.playback,
            artworkUri: r.artworkUri,
            artworkPath: r.artworkPath,
            iconName: r.iconName,
          })),
        }
        const text = JSON.stringify(dump, null, 2)
        GLib.file_set_contents(`${GLib.get_user_state_dir()}/ags/panel-debug.json`, text)
        res(`wrote ${text.length} bytes`)
      } catch (e) {
        res(`audio-panel-debug failed: ${String(e)}`)
      }
      return
    }
    res(`unknown request: ${argv.join(" ")}`)
  },
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    // The redesigned panel's stylesheet (tasks.md 6.0e). It was written but
    // imported by nothing, so all 345 lines were dead and the popup fell back
    // to the pre-existing `.audio-*` rules in style.css that styled the panel
    // this change replaces.
    //
    // Applied at runtime from the deployed config dir, alongside colors.css,
    // rather than via a static `import ... from "./audio/audio-panel.css"`.
    // `ags bundle` strips CSS entirely -- it emitted no rule for either
    // stylesheet -- so bundling cannot verify a CSS import here, and this
    // file already has a proven runtime path for generated CSS.
    app.apply_css(`${GLib.get_user_config_dir()}/ags/audio/audio-panel.css`)
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
// Same ordering rule for the Bluetooth popup: catcher first, popup above
      // it.
      app.add_window(BluetoothPopupCatcher(primary))
      app.add_window(BluetoothPopup(primary))
      // Battery popup: catcher first, popup above it, same rule again.
      app.add_window(BatteryPopupCatcher(primary))
      app.add_window(BatteryPopup(primary))
      // Audio popup: catcher + popup, same stacking order. The binding comes
      // from the composition root (audio/composition.ts), which assembles the
      // session runtime, adapters and view model. Passing it here is the whole
      // of tasks.md 6.0: without it the popup had no data source and rendered
      // only its placeholder.
      const audio = audioPanelBinding()
      app.add_window(AudioCatcher(primary))
      app.add_window(AudioPopup(primary, audio))
    }
  },
})
