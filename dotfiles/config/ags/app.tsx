import app from "ags/gtk4/app"
import Gtk from "gi://Gtk?version=4.0"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import Bar from "./bar/Bar"
import { SettingsCatcher, SettingsPanel } from "./settings-panel/SettingsPanel"
import { WifiPopup, WifiPopupCatcher } from "./components/wifi/WifiPopup"
import { BluetoothPopup, BluetoothPopupCatcher } from "./components/bluetooth/BluetoothPopup"
import { registerBluetoothAgent } from "./settings-panel/bluetooth-agent"
import { close as closeSettings } from "./settings-panel/state"
import { AudioCatcher, AudioPopup } from "./audio/AudioPopup"
import { audioPanelBinding, audioPanelTraceLines } from "./audio/composition"
import { close as closeAudio, open as openAudio } from "./audio/ui-state"
import { closeBluetoothPopup } from "./components/bluetooth/state"
import { BatteryPopup, BatteryPopupCatcher } from "./components/battery/BatteryPopup"
import { closeBatteryPopup } from "./components/battery/state"
import { closeWifiPopup } from "./components/wifi/state"

/**
 * Register one top-level window with the application.
 *
 * gnim types a JSX element — what every `Foo(primary)` call below returns — as
 * `JSX.Element`, which it declares as the base `GObject.Object`, and AGS's
 * `app.add_window` is typed to take a `Gtk.Window`. At runtime the object a JSX
 * root call returns IS the `Gtk.Window` the tree was rooted in (the bar cannot
 * start otherwise), so the cast states a runtime truth the compiler cannot see
 * rather than widening the call. The cast is `Object -> Gtk.Window`, a plain
 * downcast, and it lives here ONCE: eleven casts at the call sites would be the
 * same fix written eleven times.
 */
function addWindow(element: JSX.Element): void {
  app.add_window(element as Gtk.Window)
}

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
          // These two were missing from the first version of this dump, and
          // their absence read as `null` in the JSON -- which sent a debugging
          // session chasing a preferred-output bug that had not been measured.
          // A dump must carry every field being reasoned about.
          preferredOutputId: model.preferredOutputId,
          preferredOutput: model.preferredOutput,
          // App-scoped intent is not a row field, so it must be dumped from the
          // session or the paused-routing fix is unverifiable. Same mistake as
          // preferredOutputId above: an omitted field reads as a bug.
          sessionAppIntents: model.appIntents,
          // Rolling per-row trace: shows what a row reported immediately before
          // and after an action, which is the only way to see a one-frame
          // transient such as the Firefox seek flash.
          trace: [...audioPanelTraceLines()],
          preferredInputId: model.preferredInputId,
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
    // The audio composition root is assembled ONCE and shared by the bar
    // indicators and the popup, so every audio surface observes the same
    // session. Created before the monitor loop because the bar consumes it too.
    const audio = audioPanelBinding()
    for (const monitor of app.get_monitors()) {
      addWindow(Bar(monitor, audio))
    }
    const primary = app.get_monitors()[0]
    if (primary) {
      // Catcher first so the panel stacks above it on the overlay layer.
      addWindow(SettingsCatcher(primary))
      addWindow(SettingsPanel(primary))
      // Same ordering rule for the Wi-Fi popup: catcher first, popup above it.
      addWindow(WifiPopupCatcher(primary))
      addWindow(WifiPopup(primary))
      // Same ordering rule for the Bluetooth popup: catcher first, popup above
      // it.
      addWindow(BluetoothPopupCatcher(primary))
      addWindow(BluetoothPopup(primary))
      // Battery popup: catcher first, popup above it, same rule again.
      addWindow(BatteryPopupCatcher(primary))
      addWindow(BatteryPopup(primary))
      // Audio popup: catcher + popup, same stacking order. The binding comes
      // from the composition root (audio/composition.ts), which assembles the
      // session runtime, adapters and view model, and is shared with the bar
      // indicators above.
      addWindow(AudioCatcher(primary))
      addWindow(AudioPopup(primary, audio))
    }
  },
})
