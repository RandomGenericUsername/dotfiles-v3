import { Astal, Gdk, Gtk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import app from "ags/gtk4/app"
import { execAsync } from "ags/process"

export type CaptureTarget = "region" | "screen" | "window"
type ScreenshotFormat = "png" | "jpeg"
type RecordingFormat = "mp4" | "webm" | "gif"
type RecordingQuality = "low" | "medium" | "high"

function hideCaptureWindow() {
  const window = app.get_window("capture-window")
  if (window) window.visible = false
}

function startRecording(target: CaptureTarget, fps: number, format: RecordingFormat, quality: RecordingQuality) {
  hideCaptureWindow()
  setTimeout(() => execAsync([
    "capture-tool", "start", "--target", target,
    "--fps", String(fps), "--format", format, "--quality", quality,
  ]).catch(console.error), 150)
}

function takeScreenshot(target: CaptureTarget, delay: number, format: ScreenshotFormat, saveToFile: boolean) {
  hideCaptureWindow()
  const args = ["capture-tool", "screenshot", "--target", target, "--delay", String(delay), "--format", format]
  if (saveToFile) {
    const pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) ?? `${GLib.get_home_dir()}/Pictures`
    args.push("--output", `${pictures}/Screenshots/screenshot-${Date.now()}.${format}`)
  }
  setTimeout(() => execAsync(args).catch(console.error), 150)
}

export function CaptureWindow(gdkmonitor: Gdk.Monitor) {
  let screenshotView: Gtk.Box | null = null
  let recordingView: Gtk.Box | null = null
  let screenshotTab: Gtk.Button | null = null
  let recordingTab: Gtk.Button | null = null
  let screenshotTarget: CaptureTarget = "region"
  let screenshotDelay = 0
  let screenshotFormat: ScreenshotFormat = "png"
  let screenshotSave = false
  let recordingTarget: CaptureTarget = "region"
  let recordingFps = 60
  let recordingFormat: RecordingFormat = "mp4"
  let recordingQuality: RecordingQuality = "high"

  const screenshotTargetButtons: Gtk.Button[] = []
  const screenshotDelayButtons: Gtk.Button[] = []
  const screenshotFormatButtons: Gtk.Button[] = []
  const screenshotOutputButtons: Gtk.Button[] = []
  const recordingTargetButtons: Gtk.Button[] = []
  const recordingFpsButtons: Gtk.Button[] = []
  const recordingFormatButtons: Gtk.Button[] = []
  const recordingQualityButtons: Gtk.Button[] = []

  function select(button: Gtk.Button, group: Gtk.Button[]) {
    for (const item of group) item.remove_css_class("selected")
    button.add_css_class("selected")
  }

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
            <button label="Region" class="selected" $={(self) => screenshotTargetButtons.push(self)} onClicked={(self) => { screenshotTarget = "region"; select(self, screenshotTargetButtons) }} />
            <button label="Screen" $={(self) => screenshotTargetButtons.push(self)} onClicked={(self) => { screenshotTarget = "screen"; select(self, screenshotTargetButtons) }} />
            <button label="Window" $={(self) => screenshotTargetButtons.push(self)} onClicked={(self) => { screenshotTarget = "window"; select(self, screenshotTargetButtons) }} />
          </box>
          <label class="capture-section" label="Delay" />
          <box class="capture-options" spacing={6}>
            <button label="None" class="selected" $={(self) => screenshotDelayButtons.push(self)} onClicked={(self) => { screenshotDelay = 0; select(self, screenshotDelayButtons) }} />
            <button label="3s" $={(self) => screenshotDelayButtons.push(self)} onClicked={(self) => { screenshotDelay = 3; select(self, screenshotDelayButtons) }} />
            <button label="5s" $={(self) => screenshotDelayButtons.push(self)} onClicked={(self) => { screenshotDelay = 5; select(self, screenshotDelayButtons) }} />
            <button label="10s" $={(self) => screenshotDelayButtons.push(self)} onClicked={(self) => { screenshotDelay = 10; select(self, screenshotDelayButtons) }} />
          </box>
          <label class="capture-section" label="Format" />
          <box class="capture-options" spacing={6}>
            <button label="PNG" class="selected" $={(self) => screenshotFormatButtons.push(self)} onClicked={(self) => { screenshotFormat = "png"; select(self, screenshotFormatButtons) }} />
            <button label="JPEG" $={(self) => screenshotFormatButtons.push(self)} onClicked={(self) => { screenshotFormat = "jpeg"; select(self, screenshotFormatButtons) }} />
          </box>
          <label class="capture-section" label="Output" />
          <box class="capture-options" spacing={6}>
            <button label="Clipboard" class="selected" $={(self) => screenshotOutputButtons.push(self)} onClicked={(self) => { screenshotSave = false; select(self, screenshotOutputButtons) }} />
            <button label="Save" $={(self) => screenshotOutputButtons.push(self)} onClicked={(self) => { screenshotSave = true; select(self, screenshotOutputButtons) }} />
          </box>
          <button class="capture-primary" label="Take Screenshot" onClicked={() => takeScreenshot(screenshotTarget, screenshotDelay, screenshotFormat, screenshotSave)} />
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
            <button label="Region" class="selected" $={(self) => recordingTargetButtons.push(self)} onClicked={(self) => { recordingTarget = "region"; select(self, recordingTargetButtons) }} />
            <button label="Screen" $={(self) => recordingTargetButtons.push(self)} onClicked={(self) => { recordingTarget = "screen"; select(self, recordingTargetButtons) }} />
            <button label="Window" $={(self) => recordingTargetButtons.push(self)} onClicked={(self) => { recordingTarget = "window"; select(self, recordingTargetButtons) }} />
          </box>
          <label class="capture-section" label="FPS" />
          <box class="capture-options" spacing={6}>
            <button label="24" $={(self) => recordingFpsButtons.push(self)} onClicked={(self) => { recordingFps = 24; select(self, recordingFpsButtons) }} />
            <button label="30" $={(self) => recordingFpsButtons.push(self)} onClicked={(self) => { recordingFps = 30; select(self, recordingFpsButtons) }} />
            <button label="60" class="selected" $={(self) => recordingFpsButtons.push(self)} onClicked={(self) => { recordingFps = 60; select(self, recordingFpsButtons) }} />
          </box>
          <label class="capture-section" label="Format" />
          <box class="capture-options" spacing={6}>
            <button label="MP4" class="selected" $={(self) => recordingFormatButtons.push(self)} onClicked={(self) => { recordingFormat = "mp4"; select(self, recordingFormatButtons) }} />
            <button label="WebM" $={(self) => recordingFormatButtons.push(self)} onClicked={(self) => { recordingFormat = "webm"; select(self, recordingFormatButtons) }} />
            <button label="GIF" $={(self) => recordingFormatButtons.push(self)} onClicked={(self) => { recordingFormat = "gif"; select(self, recordingFormatButtons) }} />
          </box>
          <label class="capture-section" label="Audio" />
          <box class="capture-options" spacing={6}>
            <button label="None" class="selected" />
            <button label="System" />
            <button label="Mic" />
          </box>
          <label class="capture-section" label="Quality" />
          <box class="capture-options" spacing={6}>
            <button label="Low" $={(self) => recordingQualityButtons.push(self)} onClicked={(self) => { recordingQuality = "low"; select(self, recordingQualityButtons) }} />
            <button label="Medium" $={(self) => recordingQualityButtons.push(self)} onClicked={(self) => { recordingQuality = "medium"; select(self, recordingQualityButtons) }} />
            <button label="High" class="selected" $={(self) => recordingQualityButtons.push(self)} onClicked={(self) => { recordingQuality = "high"; select(self, recordingQualityButtons) }} />
          </box>
          <label class="capture-section" label="Duration" />
          <box class="capture-options" spacing={6}>
            <button label="∞" class="selected" />
            <button label="10s" />
            <button label="30s" />
            <button label="60s" />
          </box>
          <button class="capture-primary" label="Start Recording" onClicked={() => startRecording(recordingTarget, recordingFps, recordingFormat, recordingQuality)} />
        </box>
        <box spacing={8} halign={Gtk.Align.END}>
          <button label="Close" onClicked={hideCaptureWindow} />
        </box>
      </box>
    </window>
  )
}
