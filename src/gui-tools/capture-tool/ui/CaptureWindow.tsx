import { Astal, Gdk, Gtk } from "ags/gtk4"
import app from "ags/gtk4/app"
import { registry } from "../lib/icon-registry"
import { type CapturePorts } from "../ports/capture-ports"
import {
  type CaptureSettings,
  type ConfigRecordingAudio,
  type ConfigRecordingFps,
  type ConfigRecordingQuality,
  type ConfigScreenshotFormat,
  type ConfigScreenshotOutput,
} from "../domain/settings"
import { recordingArgs, screenshotArgs } from "../domain/cli-args"
import type { RecordingRequest, ScreenshotRequest } from "../domain/capture-request"
import {
  DEFAULT_RECORDING,
  DEFAULT_SCREENSHOT,
  type RecordingUiState,
  type ScreenshotUiState,
  configDefaults,
  durationSelection,
  isGif,
} from "../domain/ui-state"
import type {
  AudioSource,
  CaptureTarget,
  GifScale,
  RecordingFormat,
  RecordingQuality,
  ScreenshotFormat,
} from "../types"

// Kept for the (unused) scaffold stubs that import it from here.
export type { CaptureTarget }

type Mode = "screenshot" | "recording"
type View = Mode | "settings"

// ---------------------------------------------------------------------------
// Settings config (add-capture-settings): the app-owned
// `$XDG_CONFIG_HOME/capture-tool/config.json` contract (design.md §1/§3).
//
// The GUI owns writes; the backend reads on every invocation. Reads are always
// safe: missing is first-run (silent defaults), corrupt degrades to defaults
// with a loud log.
//
// Split three ways as of A5. The vocabulary, defaults, merge and validation
// are pure and live in `domain/settings.ts` (A3). The `GLib.file_*` /
// `mkdir_with_parents` persistence and the `expandDir` Environment live in
// `adapters/glib-settings-store.ts` (A5). What remains HERE is the port type
// in `ports/settings-store.ts` and, below, the calls into the injected store.
// The view no longer knows the config lives in a file at all.
// ---------------------------------------------------------------------------

// Frozen `capture-tool` icon variants (design.md §1).
type IconVariant =
  | "camera"
  | "video"
  | "region"
  | "monitor"
  | "window"
  | "clipboard"
  | "save"
  | "speaker"
  | "mic"
  | "info"

// ---------------------------------------------------------------------------
// Icons: resolved through the AGS icon registry. Every button keeps its text
// label, so a missing manifest/render degrades to text — never a crash.
// ---------------------------------------------------------------------------

function captureIcon(variant: IconVariant, size: number): Gtk.Widget | null {
  const path = registry.resolve("capture-tool", variant)
  if (path === null) return null
  try {
    // Gtk.Image + pixel_size (bar precedent): forces the SVG to render at
    // exactly `size` px. Gtk.Picture + set_size_request is NOT equivalent —
    // the request is only a minimum and the 1024px SVG natural size still
    // drives measurement, inflating every tile to screen scale.
    const image = Gtk.Image.new_from_file(path)
    image.set_pixel_size(size)
    image.set_halign(Gtk.Align.CENTER)
    image.set_valign(Gtk.Align.CENTER)
    return image
  } catch (error) {
    console.error(`capture-tool: cannot load icon ${path}: ${error}`)
    return null
  }
}

/** Prepend the resolved icon to a button-content box (label stays as fallback). */
function withIcon(variant: IconVariant, size: number) {
  return (self: Gtk.Box) => {
    const icon = captureIcon(variant, size)
    if (icon !== null) self.prepend(icon)
  }
}

// ---------------------------------------------------------------------------
// Persisted UI state (GUI-local JSON; no provisioning surface).
//
// The state shape, first-run constants, option vocabularies, the
// settings→defaults precedence rule and the merge all live in
// `domain/ui-state.ts` (A3). The read, the write and the
// missing-is-silent / corrupt-is-loud degradation live in
// `adapters/glib-ui-state-store.ts` (A5), behind `ports/ui-state-store.ts`.
// The calls are the only trace of persistence left in this file.
// ---------------------------------------------------------------------------

const WINDOW_NAME = "capture-window"

function hideCaptureWindow() {
  const window = app.get_window(WINDOW_NAME)
  if (window) window.visible = false
}

/**
 * Re-assert the layer surface size after a view switch.
 *
 * GTK does not shrink a layer-shell surface when its content gets shorter:
 * measured live, the surface stayed 718px tall after returning to the 590px
 * screenshot view, so the panel ended up glued to the top of a too-tall
 * transparent window.
 *
 * Deliberately SYNCHRONOUS (no idle callback): deferring the size change made
 * GTK paint an intermediate frame with the new, shorter content still inside
 * the OLD surface, and the panel's clipped shadow in that leftover area read as
 * a rectangle trailing the window. Measuring and resizing in the same turn lets
 * GTK resize and repaint atomically. GTK's measure() recomputes on demand, so
 * the visibility changes made just before this are already reflected.
 */
function syncWindowSize() {
  const window = app.get_window(WINDOW_NAME)
  const panel = window?.get_child()
  if (!window || !panel) return
  const [, width] = panel.measure(Gtk.Orientation.HORIZONTAL, -1)
  const [, height] = panel.measure(Gtk.Orientation.VERTICAL, width)
  window.set_default_size(width, height)
}

// The return type is annotated because the JSX runtime's inferred element type
// widens to `Object`, which `app.add_window` rejects. `<window>` maps to
// Astal.Window (see ags/gtk4/jsx-runtime), so the annotation names the real
// type; see the cast on the return below for why TS cannot infer it.
//
// `ports` (design.md §2, task 5.9) is the injected hexagon: settings
// persistence, UI-state persistence, capture launching and the backend probe.
// The composition root builds the adapters and passes them in, so this file
// contains no filesystem access and no process spawning — only calls into
// interfaces it was handed.
export function CaptureWindow(gdkmonitor: Gdk.Monitor, ports: CapturePorts): Astal.Window {
  const { settingsStore, uiStateStore, launcher, backendProbe } = ports

  let mode: Mode = "screenshot"

  let screenshotView: Gtk.Box | null = null
  let recordingView: Gtk.Box | null = null
  let screenshotTab: Gtk.Button | null = null
  let recordingTab: Gtk.Button | null = null

  // GIF-mode conditional rows.
  let audioRow: Gtk.Box | null = null
  let stdFpsRow: Gtk.Box | null = null
  let gifFpsRow: Gtk.Box | null = null
  let sizeRow: Gtk.Box | null = null
  let recFooterStd: Gtk.Box | null = null
  let recFooterGif: Gtk.Box | null = null

  // Settings view (add-capture-settings): a third top-level view that
  // replaces the mode switch + mode views while open.
  let modeSwitch: Gtk.Box | null = null
  let settingsView: Gtk.Box | null = null
  let settingsBody: Gtk.Box | null = null
  let settingsError: Gtk.Label | null = null
  let backendReadout: Gtk.Label | null = null
  let view: View = "screenshot"
  // Draft settings edited in the view; persisted on Back/Escape/Enter.
  let settingsConfig: CaptureSettings = settingsStore.load()
  // Active inline path editor, so Enter/Escape commit/cancel it instead of
  // being swallowed by the window's capture-phase key controller.
  let pathEditor: { commit: () => void; cancel: () => void } | null = null

  // Custom-duration inline editor.
  let customBox: Gtk.Box | null = null
  let customSpin: Gtk.SpinButton | null = null
  let applyingState = false

  let screenshot: ScreenshotUiState = { ...DEFAULT_SCREENSHOT }
  let recording: RecordingUiState = { ...DEFAULT_RECORDING }

  // Button groups carry their value so persisted state can re-select them.
  const screenshotTargetGroup: Array<{ value: CaptureTarget; button: Gtk.Button }> = []
  const screenshotDelayGroup: Array<{ value: number; button: Gtk.Button }> = []
  const screenshotFormatGroup: Array<{ value: ScreenshotFormat; button: Gtk.Button }> = []
  const screenshotOutputGroup: Array<{ value: boolean; button: Gtk.Button }> = []
  const recordingTargetGroup: Array<{ value: CaptureTarget; button: Gtk.Button }> = []
  const recordingFpsGroup: Array<{ value: number; button: Gtk.Button }> = []
  const recordingGifFpsGroup: Array<{ value: number; button: Gtk.Button }> = []
  const recordingFormatGroup: Array<{ value: RecordingFormat; button: Gtk.Button }> = []
  const recordingAudioGroup: Array<{ value: AudioSource; button: Gtk.Button }> = []
  const recordingQualityGroup: Array<{ value: RecordingQuality; button: Gtk.Button }> = []
  // Duration: 0/10/30/60 seconds, -1 = custom (editor value in `recording`).
  const recordingDurationGroup: Array<{ value: number; button: Gtk.Button }> = []
  const recordingSizeGroup: Array<{ value: GifScale; button: Gtk.Button }> = []

  function select(button: Gtk.Button, group: Gtk.Button[]) {
    for (const item of group) item.remove_css_class("selected")
    button.add_css_class("selected")
  }

  function applyGroup<T>(group: Array<{ value: T; button: Gtk.Button }>, value: T) {
    for (const entry of group) {
      if (entry.value === value) entry.button.add_css_class("selected")
      else entry.button.remove_css_class("selected")
    }
  }

  function applyGifMode() {
    const gif = isGif(recording)
    if (audioRow) audioRow.visible = !gif
    if (stdFpsRow) stdFpsRow.visible = !gif
    if (gifFpsRow) gifFpsRow.visible = gif
    if (sizeRow) sizeRow.visible = gif
    if (recFooterStd) recFooterStd.visible = !gif
    if (recFooterGif) recFooterGif.visible = gif
    // Swapping audio for size changes the height, so the surface must follow.
    syncWindowSize()
  }

  function refreshCustomBox() {
    if (customBox) customBox.visible = durationSelection(recording) === -1
  }

  function selectMode(next: Mode) {
    mode = next
    view = next
    // Leaving settings must restore the mode switch: openSettings() hides it,
    // and without this the whole tab row (Screenshot + Recording) stayed
    // hidden for the rest of the session after one visit to settings.
    if (modeSwitch) modeSwitch.visible = true
    if (settingsView) settingsView.visible = false
    const screenshotSelected = next === "screenshot"
    if (screenshotView) screenshotView.visible = screenshotSelected
    if (recordingView) recordingView.visible = !screenshotSelected
    if (screenshotTab) {
      screenshotTab.remove_css_class("active")
      if (screenshotSelected) screenshotTab.add_css_class("active")
    }
    if (recordingTab) {
      recordingTab.remove_css_class("active")
      recordingTab.remove_css_class("record")
      if (!screenshotSelected) {
        recordingTab.add_css_class("active")
        recordingTab.add_css_class("record")
      }
    }
    // Views differ in height; the surface must shrink as well as grow.
    syncWindowSize()
  }

  function takeScreenshot() {
    uiStateStore.save(screenshot, recording)
    const config = settingsStore.load()
    // Build the request, then TRANSLATE it. The argv vocabulary -- including
    // the `--size 75` (not `75%`) and `--audio mic` (not `microphone`) traps --
    // belongs to `domain/cli-args.ts` (A6), the one module that owns it, so the
    // next layout shares it instead of re-deriving it here.
    const request: ScreenshotRequest = {
      target: screenshot.target,
      delay: screenshot.delay,
      format: screenshot.format,
      // The backend owns the default save path (config dir + pattern); the
      // clipboard default is preserved unless Save was chosen.
      save: screenshot.save,
      cursor: config.screenshot.cursor,
    }
    hideCaptureWindow()
    // The 150ms hide-then-spawn delay lives in the launcher (A5), not here:
    // it is a compositor fact, so a second layout inherits it for free.
    launcher.launch(screenshotArgs(request))
  }

  function startRecording() {
    uiStateStore.save(screenshot, recording)
    const config = settingsStore.load()
    // Same seam as takeScreenshot: the GIF fps branch, the `--size` scale
    // mapping and the `microphone`→`mic` conversion are the translator's, not
    // the view's.
    const request: RecordingRequest = {
      target: recording.target,
      fps: recording.fps,
      gifFps: recording.gifFps,
      format: recording.format,
      audio: recording.audio,
      quality: recording.quality,
      duration: recording.duration,
      size: recording.size,
      cursor: config.recording.cursor,
    }
    hideCaptureWindow()
    launcher.launch(recordingArgs(request))
  }

  function onKey(keyval: number): boolean {
    if (keyval === Gdk.KEY_Escape) {
      // An open inline path editor owns Escape (cancel the edit).
      if (view === "settings" && pathEditor !== null) {
        pathEditor.cancel()
        pathEditor = null
        return true
      }
      // Hierarchy: settings → mode view → hide window.
      if (view === "settings") closeSettings()
      else hideCaptureWindow()
      return true
    }
    if (keyval === Gdk.KEY_Return || keyval === Gdk.KEY_KP_Enter) {
      // An open inline path editor owns Enter (commit the edit).
      if (view === "settings" && pathEditor !== null) {
        pathEditor.commit()
        pathEditor = null
        return true
      }
      if (view === "settings") closeSettings()
      else if (mode === "screenshot") takeScreenshot()
      else startRecording()
      return true
    }
    return false
  }

  function applyStateToUi() {
    applyingState = true
    try {
      // Last-used UI state > settings defaults > hardcoded constants.
      const state = uiStateStore.load(configDefaults(settingsStore.load()))
      screenshot = state.screenshot
      recording = state.recording
      applyGroup(screenshotTargetGroup, screenshot.target)
      applyGroup(screenshotDelayGroup, screenshot.delay)
      applyGroup(screenshotFormatGroup, screenshot.format)
      applyGroup(screenshotOutputGroup, screenshot.save)
      applyGroup(recordingTargetGroup, recording.target)
      applyGroup(recordingFpsGroup, recording.fps)
      applyGroup(recordingGifFpsGroup, recording.gifFps)
      applyGroup(recordingFormatGroup, recording.format)
      applyGroup(recordingAudioGroup, recording.audio)
      applyGroup(recordingQualityGroup, recording.quality)
      applyGroup(recordingDurationGroup, durationSelection(recording))
      applyGroup(recordingSizeGroup, recording.size)
      if (customSpin) customSpin.set_value(recording.customDuration)
      applyGifMode()
      refreshCustomBox()
    } finally {
      applyingState = false
    }
  }

  function setRecordingFormat(format: RecordingFormat, button: Gtk.Button) {
    recording.format = format
    select(button, recordingFormatGroup.map((entry) => entry.button))
    applyGifMode()
  }

  // -------------------------------------------------------------------------
  // Settings view (add-capture-settings). The view is rebuilt from disk each
  // time it opens so it always reflects the current config; edits mutate a
  // draft (`settingsConfig`) that is persisted on leave. Live capture
  // selections (`screenshot`/`recording`) are never touched here.
  // -------------------------------------------------------------------------

  function settingsLabel(text: string, cssClass: string): Gtk.Label {
    const label = new Gtk.Label({ label: text, halign: Gtk.Align.START })
    label.add_css_class(cssClass)
    return label
  }

  function settingsItem(name: string, desc: string | null, control: Gtk.Widget): Gtk.Box {
    const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 18 })
    row.add_css_class("settings-item")
    const left = new Gtk.Box({
      orientation: Gtk.Orientation.VERTICAL,
      spacing: 2,
      hexpand: true,
      valign: Gtk.Align.CENTER,
    })
    left.append(settingsLabel(name, "settings-name"))
    if (desc !== null) left.append(settingsLabel(desc, "settings-desc"))
    row.append(left)
    control.set_valign(Gtk.Align.CENTER)
    row.append(control)
    return row
  }

  function settingsGroup(title: string, rows: Gtk.Widget[]): Gtk.Box {
    const box = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2 })
    box.add_css_class("settings-group")
    box.append(settingsLabel(title, "settings-group-title"))
    for (const row of rows) box.append(row)
    return box
  }

  /** Persist settings immediately after every change.
   *
   * They used to save only through closeSettings (the Back button / Enter), so
   * toggling something and then dismissing the window — pressing the keybind
   * again, switching apps — silently discarded the change. That read as "the
   * cursor toggle does nothing": the screenshot kept using the old value.
   */
  function persistSettings(): void {
    const error = settingsStore.save(settingsConfig)
    if (settingsError) {
      settingsError.set_label(error ?? "")
      settingsError.visible = error !== null
    }
  }

  function pathRow(
    name: string,
    desc: string,
    getValue: () => string,
    setValue: (value: string) => void,
  ): Gtk.Box {
    const control = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 })
    const chip = new Gtk.Button({ label: getValue() })
    chip.add_css_class("path-chip")
    const entry = new Gtk.Entry({ text: getValue() })
    entry.add_css_class("path-entry")
    entry.set_width_chars(24)
    entry.set_visible(false)
    const commit = () => {
      if (!entry.get_visible()) return
      setValue(entry.get_text())
      chip.set_label(getValue())
      entry.set_visible(false)
      chip.set_visible(true)
      pathEditor = null
      persistSettings()
    }
    const cancel = () => {
      entry.set_text(getValue())
      entry.set_visible(false)
      chip.set_visible(true)
      pathEditor = null
    }
    chip.connect("clicked", () => {
      entry.set_text(getValue())
      chip.set_visible(false)
      entry.set_visible(true)
      entry.grab_focus()
      entry.select_region(0, -1)
      pathEditor = { commit, cancel }
    })
    entry.connect("activate", commit)
    const focus = new Gtk.EventControllerFocus()
    focus.connect("leave", commit)
    entry.add_controller(focus)
    control.append(chip)
    control.append(entry)
    return settingsItem(name, desc, control)
  }

  function toggleRow(
    name: string,
    desc: string | null,
    getValue: () => boolean,
    setValue: (value: boolean) => void,
  ): Gtk.Box {
    // Gtk.Switch, not a hand-rolled track+knob: a GtkBox ignores a child's
    // main-axis alignment, so the old knob's halign START/END never moved it and
    // both states looked identical (you could not tell whether the cursor
    // toggle was on). The native switch owns the knob, its position and its
    // transition; the palette styling lives in style.css.
    const control = new Gtk.Switch()
    control.add_css_class("palette-switch")
    control.set_active(getValue())
    control.set_halign(Gtk.Align.END)
    control.set_valign(Gtk.Align.CENTER)
    control.connect("state-set", (_self, state: boolean) => {
      setValue(state)
      persistSettings()
      return false // let the switch animate to the new state
    })
    return settingsItem(name, desc, control)
  }

  function pillRow<T>(
    name: string,
    options: Array<{ label: string; value: T }>,
    getValue: () => T,
    setValue: (value: T) => void,
  ): Gtk.Box {
    const segments = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 })
    segments.add_css_class("segments")
    const buttons: Array<{ value: T; button: Gtk.Button }> = []
    for (const option of options) {
      const button = new Gtk.Button({ label: option.label })
      button.add_css_class("segment")
      button.add_css_class("compact")
      if (option.value === getValue()) button.add_css_class("selected")
      button.connect("clicked", () => {
        setValue(option.value)
        persistSettings()
        for (const item of buttons) {
          if (item.value === option.value) item.button.add_css_class("selected")
          else item.button.remove_css_class("selected")
        }
      })
      buttons.push({ value: option.value, button })
      segments.append(button)
    }
    return settingsItem(name, null, segments)
  }

  function clearChildren(container: Gtk.Box) {
    let child = container.get_first_child()
    while (child !== null) {
      const next = child.get_next_sibling()
      container.remove(child)
      child = next
    }
  }

  function refreshBackendReadout() {
    const readout = backendReadout
    // The probe, the spawn and the `?? "none"` fallback are the adapter's
    // (A5). All that is left here is rendering. Note the `readout ===` re-check:
    // settings can be rebuilt while the probe is in flight, and a stale label
    // would outlive its view.
    backendProbe
      .backend()
      .then((name) => {
        if (readout !== null && readout === backendReadout) {
          readout.set_label(name === "none" ? "Automatic (unavailable)" : `Automatic (${name})`)
        }
      })
      .catch(() => {
        if (readout !== null && readout === backendReadout) readout.set_label("Automatic")
      })
  }

  function renderSettings() {
    if (settingsBody === null) return
    settingsConfig = settingsStore.load()
    clearChildren(settingsBody)
    if (settingsError) {
      settingsError.set_label("")
      settingsError.visible = false
    }

    const general = settingsGroup("General", [
      pathRow(
        "Screenshot folder",
        "Where saved screenshots go",
        () => settingsConfig.screenshot_dir,
        (value) => {
          settingsConfig.screenshot_dir = value
        },
      ),
      pathRow(
        "Recording folder",
        "Where finished recordings go",
        () => settingsConfig.recording_dir,
        (value) => {
          settingsConfig.recording_dir = value
        },
      ),
      pathRow(
        "Filename pattern",
        "Timestamp tokens are expanded at capture time",
        () => settingsConfig.filename_pattern,
        (value) => {
          settingsConfig.filename_pattern = value
        },
      ),
      toggleRow(
        "Show notifications",
        null,
        () => settingsConfig.notifications,
        (value) => {
          settingsConfig.notifications = value
        },
      ),
      toggleRow(
        "Compact bar indicator",
        "Bar shows only the timer; pause/stop appear in the popup. Off: the bar shows the buttons and opens no popup.",
        () => settingsConfig.bar_compact_controls,
        (value) => {
          settingsConfig.bar_compact_controls = value
        },
      ),
    ])

    const screenshotGroup = settingsGroup("Screenshot", [
      pillRow<ConfigScreenshotFormat>(
        "Default format",
        [
          { label: "PNG", value: "png" },
          { label: "JPEG", value: "jpeg" },
        ],
        () => settingsConfig.screenshot.format,
        (value) => {
          settingsConfig.screenshot.format = value
        },
      ),
      pillRow<ConfigScreenshotOutput>(
        "Default output",
        [
          { label: "Clipboard", value: "clipboard" },
          { label: "Save", value: "save" },
        ],
        () => settingsConfig.screenshot.output,
        (value) => {
          settingsConfig.screenshot.output = value
        },
      ),
      toggleRow(
        "Include cursor",
        "Draw the pointer into the shot",
        () => settingsConfig.screenshot.cursor,
        (value) => {
          settingsConfig.screenshot.cursor = value
        },
      ),
    ])

    backendReadout = new Gtk.Label({ label: "Automatic", halign: Gtk.Align.END })
    backendReadout.add_css_class("settings-readout")
    const recordingGroup = settingsGroup("Recording", [
      pillRow<ConfigRecordingFps>(
        "Default frame rate",
        [
          { label: "24", value: 24 },
          { label: "30", value: 30 },
          { label: "60", value: 60 },
        ],
        () => settingsConfig.recording.fps,
        (value) => {
          settingsConfig.recording.fps = value
        },
      ),
      pillRow<ConfigRecordingQuality>(
        "Default quality",
        [
          { label: "Low", value: "low" },
          { label: "Medium", value: "medium" },
          { label: "High", value: "high" },
        ],
        () => settingsConfig.recording.quality,
        (value) => {
          settingsConfig.recording.quality = value
        },
      ),
      pillRow<ConfigRecordingAudio>(
        "Default audio",
        [
          { label: "None", value: "none" },
          { label: "System", value: "system" },
          { label: "Mic", value: "mic" },
        ],
        () => settingsConfig.recording.audio,
        (value) => {
          settingsConfig.recording.audio = value
        },
      ),
      toggleRow(
        "Include cursor",
        "Draw the pointer into the recording",
        () => settingsConfig.recording.cursor,
        (value) => {
          settingsConfig.recording.cursor = value
        },
      ),
      settingsItem(
        "Recorder backend",
        "Chosen automatically after detection",
        backendReadout,
      ),
    ])

    settingsBody.append(general)
    settingsBody.append(screenshotGroup)
    settingsBody.append(recordingGroup)
    refreshBackendReadout()
  }

  function openSettings() {
    view = "settings"
    if (modeSwitch) modeSwitch.visible = false
    if (screenshotView) screenshotView.visible = false
    if (recordingView) recordingView.visible = false
    if (settingsView) settingsView.visible = true
    renderSettings()
    // Settings is the tallest view; the surface must grow to fit it.
    syncWindowSize()
  }

  function closeSettings() {
    const error = settingsStore.save(settingsConfig)
    if (error !== null) {
      if (settingsError) {
        settingsError.set_label(error)
        settingsError.visible = true
      }
      return
    }
    // Save applies forward: mode selections stay exactly as they were.
    selectMode(mode)
  }

  return (
    <window
      visible={false}
      name="capture-window"
      class="capture-window"
      namespace="capture"
      gdkmonitor={gdkmonitor}
      // NONE, not 0. `Astal.WindowAnchor` is a bitfield with no zero member
      // (NONE=1, TOP=2, RIGHT=4, LEFT=8, BOTTOM=16), so the bare literal was
      // never a valid value. It anchored to no edge, and so does NONE:
      // astal_window_set_anchor() reads only bits 1/2/3/4 and never tests bit 0,
      // so 0 and NONE both hand gtk_layer_shell four anchored=false edges.
      // Behaviour is identical; only the type is now honest.
      anchor={Astal.WindowAnchor.NONE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      halign={Gtk.Align.CENTER}
      valign={Gtk.Align.CENTER}
      $={(self) => {
        // Capture phase so Enter/Escape fire even when a pill has focus.
        const keys = new Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", (_controller, keyval, _keycode, _state) => onKey(keyval))
        self.add_controller(keys)
        // Re-read persisted choices on every show so the window reflects
        // captures that happened while it was hidden.
        self.connect("map", () => {
          applyStateToUi()
          // ON_DEMAND (like hypr-pano) never steals the keyboard from other
          // AGS windows; present() asks the compositor to focus on show.
          self.present()
        })
      }}
    >
      {/* CenterBox, not a Box. The window allocates its whole area to its
          direct child, and a GtkBox ignores a child's main-axis alignment
          (verified live: panel allocated 950 while its own content was 590), so
          the panel still stretched to the stale surface size and painted its
          background as a rectangle below the content during a view switch.
          CenterBox centres its centre widget by construction, so the panel
          keeps its natural size and the leftover area stays transparent. */}
      <centerbox class="capture-root">
        <box
          $type="center"
          class="capture-panel"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
        >
        <box
          class="mode-switch"
          homogeneous
          spacing={0}
          $={(self) => {
            modeSwitch = self
          }}
        >
          <button
            class="active"
            $={(self) => {
              screenshotTab = self
              selectMode("screenshot")
            }}
            onClicked={() => selectMode("screenshot")}
          >
            <box
              orientation={Gtk.Orientation.HORIZONTAL}
              spacing={9}
              halign={Gtk.Align.CENTER}
              valign={Gtk.Align.CENTER}
              $={withIcon("camera", 18)}
            >
              <label label="Screenshot" />
            </box>
          </button>
          <button
            $={(self) => {
              recordingTab = self
            }}
            onClicked={() => selectMode("recording")}
          >
            <box
              orientation={Gtk.Orientation.HORIZONTAL}
              spacing={9}
              halign={Gtk.Align.CENTER}
              valign={Gtk.Align.CENTER}
              $={withIcon("video", 18)}
            >
              <label label="Recording" />
            </box>
          </button>
        </box>

        {/* ------------------------------------------------ Screenshot view */}
        <box
          visible
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
          $={(self) => {
            screenshotView = self
          }}
        >
          <box class="settings" orientation={Gtk.Orientation.VERTICAL} spacing={15}>
            <box class="setting-block" orientation={Gtk.Orientation.VERTICAL} spacing={0}>
              <label class="setting-label" label="CAPTURE TARGET" halign={Gtk.Align.START} />
              <box class="targets" homogeneous spacing={9}>
                <button
                  class="target selected"
                  $={(self) => screenshotTargetGroup.push({ value: "region", button: self })}
                  onClicked={(self) => {
                    screenshot.target = "region"
                    select(self, screenshotTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("region", 24)}
                  >
                    <label label="Region" />
                  </box>
                </button>
                <button
                  class="target"
                  $={(self) => screenshotTargetGroup.push({ value: "screen", button: self })}
                  onClicked={(self) => {
                    screenshot.target = "screen"
                    select(self, screenshotTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("monitor", 24)}
                  >
                    <label label="Screen" />
                  </box>
                </button>
                <button
                  class="target"
                  $={(self) => screenshotTargetGroup.push({ value: "window", button: self })}
                  onClicked={(self) => {
                    screenshot.target = "window"
                    select(self, screenshotTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("window", 24)}
                  >
                    <label label="Window" />
                  </box>
                </button>
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="DELAY"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="None"
                  $={(self) => screenshotDelayGroup.push({ value: 0, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 0
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="3s"
                  $={(self) => screenshotDelayGroup.push({ value: 3, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 3
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="5s"
                  $={(self) => screenshotDelayGroup.push({ value: 5, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 5
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="10s"
                  $={(self) => screenshotDelayGroup.push({ value: 10, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 10
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="FORMAT"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="PNG"
                  $={(self) => screenshotFormatGroup.push({ value: "png", button: self })}
                  onClicked={(self) => {
                    screenshot.format = "png"
                    select(self, screenshotFormatGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="JPEG"
                  $={(self) => screenshotFormatGroup.push({ value: "jpeg", button: self })}
                  onClicked={(self) => {
                    screenshot.format = "jpeg"
                    select(self, screenshotFormatGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="OUTPUT"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  $={(self) => screenshotOutputGroup.push({ value: false, button: self })}
                  onClicked={(self) => {
                    screenshot.save = false
                    select(self, screenshotOutputGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("clipboard", 15)}
                  >
                    <label label="Clipboard" />
                  </box>
                </button>
                <button
                  class="segment"
                  $={(self) => screenshotOutputGroup.push({ value: true, button: self })}
                  onClicked={(self) => {
                    screenshot.save = true
                    select(self, screenshotOutputGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("save", 15)}
                  >
                    <label label="Save" />
                  </box>
                </button>
              </box>
            </box>

            <button class="primary" onClicked={takeScreenshot}>
              <box
                orientation={Gtk.Orientation.HORIZONTAL}
                spacing={10}
                halign={Gtk.Align.CENTER}
                valign={Gtk.Align.CENTER}
                $={withIcon("camera", 18)}
              >
                <label label="Take Screenshot" />
              </box>
            </button>
          </box>

          <box class="panel-footer" spacing={8}>
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="cancel  ·" />
              <label class="kbd" label="Enter" />
              <label class="footer-note" label="capture" />
            </box>
            <box hexpand halign={Gtk.Align.END} spacing={10}>
              <label
                class="footer-note"
                label="Remembers your last choices"
                valign={Gtk.Align.CENTER}
              />
              <button class="ghost" label="Settings" onClicked={openSettings} />
            </box>
          </box>
        </box>

        {/* ------------------------------------------------ Recording view */}
        <box
          visible={false}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
          $={(self) => {
            recordingView = self
          }}
        >
          <box class="settings" orientation={Gtk.Orientation.VERTICAL} spacing={15}>
            <box class="setting-block" orientation={Gtk.Orientation.VERTICAL} spacing={0}>
              <label class="setting-label" label="CAPTURE TARGET" halign={Gtk.Align.START} />
              <box class="targets" homogeneous spacing={9}>
                <button
                  class="target selected"
                  $={(self) => recordingTargetGroup.push({ value: "region", button: self })}
                  onClicked={(self) => {
                    recording.target = "region"
                    select(self, recordingTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("region", 24)}
                  >
                    <label label="Region" />
                  </box>
                </button>
                <button
                  class="target"
                  $={(self) => recordingTargetGroup.push({ value: "screen", button: self })}
                  onClicked={(self) => {
                    recording.target = "screen"
                    select(self, recordingTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("monitor", 24)}
                  >
                    <label label="Screen" />
                  </box>
                </button>
                <button
                  class="target"
                  $={(self) => recordingTargetGroup.push({ value: "window", button: self })}
                  onClicked={(self) => {
                    recording.target = "window"
                    select(self, recordingTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("window", 24)}
                  >
                    <label label="Window" />
                  </box>
                </button>
              </box>
            </box>

            <box
              class="setting-row"
              spacing={14}
              $={(self) => {
                stdFpsRow = self
              }}
            >
              <label
                class="setting-label"
                label="FRAME RATE"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment"
                  label="24"
                  $={(self) => recordingFpsGroup.push({ value: 24, button: self })}
                  onClicked={(self) => {
                    recording.fps = 24
                    select(self, recordingFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="30"
                  $={(self) => recordingFpsGroup.push({ value: 30, button: self })}
                  onClicked={(self) => {
                    recording.fps = 30
                    select(self, recordingFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment selected"
                  label="60"
                  $={(self) => recordingFpsGroup.push({ value: 60, button: self })}
                  onClicked={(self) => {
                    recording.fps = 60
                    select(self, recordingFpsGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>
            <box
              visible={false}
              class="setting-row"
              spacing={14}
              $={(self) => {
                gifFpsRow = self
              }}
            >
              <label
                class="setting-label"
                label="FRAME RATE"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment"
                  label="10"
                  $={(self) => recordingGifFpsGroup.push({ value: 10, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 10
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment selected"
                  label="15"
                  $={(self) => recordingGifFpsGroup.push({ value: 15, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 15
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="20"
                  $={(self) => recordingGifFpsGroup.push({ value: 20, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 20
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="30"
                  $={(self) => recordingGifFpsGroup.push({ value: 30, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 30
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>


            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="FORMAT"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="MP4"
                  $={(self) => recordingFormatGroup.push({ value: "mp4", button: self })}
                  onClicked={(self) => setRecordingFormat("mp4", self)}
                />
                <button
                  class="segment"
                  label="WebM"
                  $={(self) => recordingFormatGroup.push({ value: "webm", button: self })}
                  onClicked={(self) => setRecordingFormat("webm", self)}
                />
                <button
                  class="segment"
                  label="GIF"
                  $={(self) => recordingFormatGroup.push({ value: "gif", button: self })}
                  onClicked={(self) => setRecordingFormat("gif", self)}
                />
              </box>
            </box>

            <box
              class="setting-row"
              spacing={14}
              $={(self) => {
                audioRow = self
              }}
            >
              <label
                class="setting-label"
                label="AUDIO"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  $={(self) => recordingAudioGroup.push({ value: "system", button: self })}
                  onClicked={(self) => {
                    recording.audio = "system"
                    select(self, recordingAudioGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("speaker", 15)}
                  >
                    <label label="System" />
                  </box>
                </button>
                <button
                  class="segment"
                  $={(self) => recordingAudioGroup.push({ value: "microphone", button: self })}
                  onClicked={(self) => {
                    recording.audio = "microphone"
                    select(self, recordingAudioGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("mic", 15)}
                  >
                    <label label="Mic" />
                  </box>
                </button>
                <button
                  class="segment"
                  label="None"
                  $={(self) => recordingAudioGroup.push({ value: "none", button: self })}
                  onClicked={(self) => {
                    recording.audio = "none"
                    select(self, recordingAudioGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box
              visible={false}
              class="setting-row"
              spacing={14}
              $={(self) => {
                sizeRow = self
              }}
            >
              <label
                class="setting-label"
                label="SIZE"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="Original"
                  $={(self) => recordingSizeGroup.push({ value: "original", button: self })}
                  onClicked={(self) => {
                    recording.size = "original"
                    select(self, recordingSizeGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="75%"
                  $={(self) => recordingSizeGroup.push({ value: "75%", button: self })}
                  onClicked={(self) => {
                    recording.size = "75%"
                    select(self, recordingSizeGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="50%"
                  $={(self) => recordingSizeGroup.push({ value: "50%", button: self })}
                  onClicked={(self) => {
                    recording.size = "50%"
                    select(self, recordingSizeGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="QUALITY"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment"
                  label="Low"
                  $={(self) => recordingQualityGroup.push({ value: "low", button: self })}
                  onClicked={(self) => {
                    recording.quality = "low"
                    select(self, recordingQualityGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="Medium"
                  $={(self) => recordingQualityGroup.push({ value: "medium", button: self })}
                  onClicked={(self) => {
                    recording.quality = "medium"
                    select(self, recordingQualityGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment selected"
                  label="High"
                  $={(self) => recordingQualityGroup.push({ value: "high", button: self })}
                  onClicked={(self) => {
                    recording.quality = "high"
                    select(self, recordingQualityGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="DURATION"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="∞"
                  $={(self) => recordingDurationGroup.push({ value: 0, button: self })}
                  onClicked={(self) => {
                    recording.duration = 0
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="10s"
                  $={(self) => recordingDurationGroup.push({ value: 10, button: self })}
                  onClicked={(self) => {
                    recording.duration = 10
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="30s"
                  $={(self) => recordingDurationGroup.push({ value: 30, button: self })}
                  onClicked={(self) => {
                    recording.duration = 30
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="60s"
                  $={(self) => recordingDurationGroup.push({ value: 60, button: self })}
                  onClicked={(self) => {
                    recording.duration = 60
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="Custom"
                  $={(self) => recordingDurationGroup.push({ value: -1, button: self })}
                  onClicked={(self) => {
                    recording.duration = recording.customDuration
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <box
                  visible={false}
                  class="custom-duration"
                  spacing={6}
                  orientation={Gtk.Orientation.HORIZONTAL}
                  valign={Gtk.Align.CENTER}
                  $={(self) => {
                    customBox = self
                    const adjustment = new Gtk.Adjustment({
                      lower: 5,
                      upper: 3600,
                      step_increment: 5,
                      page_increment: 30,
                      value: recording.customDuration,
                    })
                    customSpin = new Gtk.SpinButton({ adjustment, digits: 0 })
                    customSpin.set_halign(Gtk.Align.START)
                    customSpin.set_valign(Gtk.Align.CENTER)
                    customSpin.connect("value-changed", () => {
                      if (applyingState || customSpin === null) return
                      recording.customDuration = customSpin.get_value_as_int()
                      recording.duration = recording.customDuration
                    })
                    self.append(customSpin)
                    const unit = new Gtk.Label({ label: "sec" })
                    unit.add_css_class("footer-note")
                    self.append(unit)
                  }}
                />
              </box>
            </box>

            <button class="primary record" onClicked={startRecording}>
              <box
                orientation={Gtk.Orientation.HORIZONTAL}
                spacing={10}
                halign={Gtk.Align.CENTER}
                valign={Gtk.Align.CENTER}
              >
                <box class="record-dot" valign={Gtk.Align.CENTER} />
                <label label="Start Recording" />
              </box>
            </button>
          </box>

          <box
            class="panel-footer"
            spacing={8}
            $={(self) => {
              recFooterStd = self
            }}
          >
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="cancel" />
            </box>
            <box hexpand halign={Gtk.Align.END} spacing={10}>
              <label
                class="footer-note"
                label="Runs in the background — controls move to the bar"
                valign={Gtk.Align.CENTER}
              />
              <button class="ghost" label="Settings" onClicked={openSettings} />
            </box>
          </box>
          <box
            visible={false}
            class="panel-footer"
            spacing={8}
            $={(self) => {
              recFooterGif = self
            }}
          >
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="cancel" />
            </box>
            <box hexpand halign={Gtk.Align.END} spacing={10}>
              <label
                class="footer-note"
                label="GIF mode — audio hardware is never opened"
                valign={Gtk.Align.CENTER}
              />
              <button class="ghost" label="Settings" onClicked={openSettings} />
            </box>
          </box>
        </box>

        {/* ------------------------------------------------ Settings view */}
        <box
          visible={false}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
          $={(self) => {
            settingsView = self
          }}
        >
          <box class="settings-page" orientation={Gtk.Orientation.VERTICAL} spacing={12}>
            <label
              class="settings-title"
              label="Capture settings"
              halign={Gtk.Align.START}
            />
            <box
              orientation={Gtk.Orientation.VERTICAL}
              spacing={0}
              $={(self) => {
                settingsBody = self
              }}
            ></box>
            <label
              visible={false}
              class="settings-error"
              wrap
              halign={Gtk.Align.START}
              $={(self) => {
                settingsError = self
              }}
            />
          </box>
          <box class="panel-footer" spacing={8}>
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="back  ·" />
              <label class="kbd" label="Enter" />
              <label class="footer-note" label="save" />
            </box>
            <box hexpand halign={Gtk.Align.END}>
              <button class="ghost" label="Back" onClicked={closeSettings} />
            </box>
          </box>
        </box>
        </box>
      </centerbox>
    </window>
    // Type-level only. gnim types every intrinsic element as `CC | FC`, i.e.
    // a constructor yielding `GObject.Object`, so the JSX expression widens to
    // `GObject.Object` no matter which tag is used — gnim's own source says
    // "intrinsicElements always resolve as FC / so we can't narrow it down".
    // `<window>` really is an Astal.Window (ags/gtk4/jsx-runtime maps it), so
    // this cast records a fact rather than hiding a bug. Nothing at runtime
    // changes: `jsx()` already called `new Astal.Window(props)`.
  ) as unknown as Astal.Window
}
