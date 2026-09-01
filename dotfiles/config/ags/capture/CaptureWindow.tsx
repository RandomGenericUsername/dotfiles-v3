import { Astal, Gdk, Gtk } from "ags/gtk4"
import { createState } from "ags"
import app from "ags/gtk4/app"
import { execAsync } from "ags/process"

export type CaptureTarget = "region" | "screen" | "window"

function hideCaptureWindow() {
  const window = app.get_window("capture-window")
  if (window) window.visible = false
}

function startRecording(target: CaptureTarget) {
  hideCaptureWindow()
  setTimeout(() => execAsync(["capture-tool", "start", "--target", target]).catch(console.error), 150)
}

function takeScreenshot(target: CaptureTarget) {
  hideCaptureWindow()
  setTimeout(() => execAsync(["capture-tool", "screenshot", "--target", target]).catch(console.error), 150)
}

export function CaptureWindow(gdkmonitor: Gdk.Monitor) {
  const [mode, setMode] = createState<"screenshot" | "recording">("screenshot")

  return (
    <window
      visible={false}
      name="capture-window"
      class="capture-window"
      gdkmonitor={gdkmonitor}
      anchor={0}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      halign={Gtk.Align.CENTER}
      valign={Gtk.Align.CENTER}
    >
      <box class="capture-panel" orientation={Gtk.Orientation.VERTICAL} spacing={12}>
        <label class="capture-title" label="Capture" />
        <box class="capture-tabs" spacing={4}>
          <button
            class={mode((value) => value === "screenshot" ? "capture-tab active" : "capture-tab")}
            label="Screenshot"
            onClicked={() => setMode("screenshot")}
          />
          <button
            class={mode((value) => value === "recording" ? "capture-tab active" : "capture-tab")}
            label="Recording"
            onClicked={() => setMode("recording")}
          />
        </box>
        <box
          visible={mode((value) => value === "screenshot")}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={12}
        >
          <label class="capture-section" label="Capture target" />
          <box class="capture-targets" spacing={8}>
            <button label="Region" onClicked={() => takeScreenshot("region")} />
            <button label="Screen" onClicked={() => takeScreenshot("screen")} />
            <button label="Window" onClicked={() => takeScreenshot("window")} />
          </box>
          <label class="capture-hint" label="Choose what to capture, then complete the selection if prompted." />
        </box>
        <box
          visible={mode((value) => value === "recording")}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={12}
        >
          <label class="capture-section" label="Capture target" />
          <box class="capture-targets" spacing={8}>
            <button label="Region" onClicked={() => startRecording("region")} />
            <button label="Screen" onClicked={() => startRecording("screen")} />
            <button label="Window" onClicked={() => startRecording("window")} />
          </box>
          <label class="capture-hint" label="Recording controls and timer appear in the AGS tray while recording." />
        </box>
        <box spacing={8} halign={Gtk.Align.END}>
          <button label="Close" onClicked={hideCaptureWindow} />
        </box>
      </box>
    </window>
  )
}
