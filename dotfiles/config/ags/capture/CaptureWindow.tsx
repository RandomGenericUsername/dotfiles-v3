import { Astal, Gdk, Gtk } from "ags/gtk4"
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
  let screenshotView: Gtk.Box | null = null
  let recordingView: Gtk.Box | null = null
  let screenshotTab: Gtk.Button | null = null
  let recordingTab: Gtk.Button | null = null

  function selectMode(mode: "screenshot" | "recording") {
    const screenshotSelected = mode === "screenshot"
    if (screenshotView) screenshotView.visible = screenshotSelected
    if (recordingView) recordingView.visible = !screenshotSelected
    if (screenshotTab) {
      screenshotTab.remove_css_class("active")
      if (screenshotSelected) screenshotTab.add_css_class("active")
    }
    if (recordingTab) {
      recordingTab.remove_css_class("active")
      if (!screenshotSelected) recordingTab.add_css_class("active")
    }
  }

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
            class="capture-tab active"
            label="Screenshot"
            $={(self) => {
              screenshotTab = self
              selectMode("screenshot")
            }}
            onClicked={() => selectMode("screenshot")}
          />
          <button
            class="capture-tab"
            label="Recording"
            $={(self) => {
              recordingTab = self
            }}
            onClicked={() => selectMode("recording")}
          />
        </box>
        <box
          visible
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={12}
          $={(self) => {
            screenshotView = self
          }}
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
          visible={false}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={12}
          $={(self) => {
            recordingView = self
          }}
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
