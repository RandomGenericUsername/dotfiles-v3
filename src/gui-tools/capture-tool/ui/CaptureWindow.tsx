import { Astal, Gdk, Gtk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import app from "ags/gtk4/app"
import { execAsync } from "ags/process"
import { registry } from "../lib/icon-registry"
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
// Kept inline (not a new lib module) because the provisioning role places the
// capture app per-file — a new file would not deploy. The GUI owns writes;
// the backend reads on every invocation. Reads are always safe: missing is
// first-run (silent defaults), corrupt degrades to defaults with a loud log.
// ---------------------------------------------------------------------------

type ConfigScreenshotFormat = "png" | "jpeg"
type ConfigScreenshotOutput = "clipboard" | "save"
type ConfigRecordingFps = 24 | 30 | 60
type ConfigRecordingQuality = "low" | "medium" | "high"
type ConfigRecordingAudio = "none" | "system" | "mic"

interface CaptureSettings {
  screenshot_dir: string
  recording_dir: string
  filename_pattern: string
  notifications: boolean
  screenshot: {
    format: ConfigScreenshotFormat
    output: ConfigScreenshotOutput
    cursor: boolean
  }
  recording: {
    fps: ConfigRecordingFps
    quality: ConfigRecordingQuality
    audio: ConfigRecordingAudio
    cursor: boolean
  }
}

const CONFIG_DIR = `${
  GLib.getenv("XDG_CONFIG_HOME") || `${GLib.get_home_dir()}/.config`
}/capture-tool`
const CONFIG_PATH = `${CONFIG_DIR}/config.json`

const DEFAULT_SETTINGS: CaptureSettings = {
  screenshot_dir: "~/Pictures/Screenshots",
  recording_dir: "~/Videos/Recordings",
  filename_pattern: "{kind}_%Y-%m-%d_%H-%M-%S",
  notifications: true,
  screenshot: { format: "png", output: "clipboard", cursor: false },
  recording: { fps: 60, quality: "high", audio: "system", cursor: true },
}

const CONFIG_SCREENSHOT_FORMATS: readonly ConfigScreenshotFormat[] = ["png", "jpeg"]
const CONFIG_SCREENSHOT_OUTPUTS: readonly ConfigScreenshotOutput[] = ["clipboard", "save"]
const CONFIG_RECORDING_FPS: readonly ConfigRecordingFps[] = [24, 30, 60]
const CONFIG_RECORDING_QUALITIES: readonly ConfigRecordingQuality[] = [
  "low",
  "medium",
  "high",
]
const CONFIG_RECORDING_AUDIO: readonly ConfigRecordingAudio[] = ["none", "system", "mic"]

function configOneOf<T>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback
}

function configBool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback
}

function configString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() !== "" ? value : fallback
}

/** A fresh deep copy of the defaults (GJS has no structuredClone). */
function defaultSettings(): CaptureSettings {
  return {
    ...DEFAULT_SETTINGS,
    screenshot: { ...DEFAULT_SETTINGS.screenshot },
    recording: { ...DEFAULT_SETTINGS.recording },
  }
}

function mergeSettings(raw: unknown): CaptureSettings {
  const record = raw !== null && typeof raw === "object" ? (raw as Record<string, unknown>) : {}
  const shot =
    record.screenshot !== null && typeof record.screenshot === "object"
      ? (record.screenshot as Record<string, unknown>)
      : {}
  const rec =
    record.recording !== null && typeof record.recording === "object"
      ? (record.recording as Record<string, unknown>)
      : {}
  return {
    screenshot_dir: configString(record.screenshot_dir, DEFAULT_SETTINGS.screenshot_dir),
    recording_dir: configString(record.recording_dir, DEFAULT_SETTINGS.recording_dir),
    filename_pattern: configString(record.filename_pattern, DEFAULT_SETTINGS.filename_pattern),
    notifications: configBool(record.notifications, DEFAULT_SETTINGS.notifications),
    screenshot: {
      format: configOneOf(shot.format, CONFIG_SCREENSHOT_FORMATS, DEFAULT_SETTINGS.screenshot.format),
      output: configOneOf(shot.output, CONFIG_SCREENSHOT_OUTPUTS, DEFAULT_SETTINGS.screenshot.output),
      cursor: configBool(shot.cursor, DEFAULT_SETTINGS.screenshot.cursor),
    },
    recording: {
      fps: configOneOf(rec.fps, CONFIG_RECORDING_FPS, DEFAULT_SETTINGS.recording.fps),
      quality: configOneOf(rec.quality, CONFIG_RECORDING_QUALITIES, DEFAULT_SETTINGS.recording.quality),
      audio: configOneOf(rec.audio, CONFIG_RECORDING_AUDIO, DEFAULT_SETTINGS.recording.audio),
      cursor: configBool(rec.cursor, DEFAULT_SETTINGS.recording.cursor),
    },
  }
}

/** Read the config; missing/corrupt degrade to defaults (corrupt logs loudly). */
function loadSettings(): CaptureSettings {
  try {
    if (!GLib.file_test(CONFIG_PATH, GLib.FileTest.EXISTS)) return defaultSettings()
    const [ok, bytes] = GLib.file_get_contents(CONFIG_PATH)
    if (!ok || bytes === null) return defaultSettings()
    return mergeSettings(JSON.parse(new TextDecoder().decode(bytes)))
  } catch (error) {
    console.error(`capture-tool: cannot read settings config: ${error}`)
    return defaultSettings()
  }
}

/** Expand `~` and `$VAR`/`${VAR}` references in a configured directory. */
function expandDir(value: string): string {
  let expanded = value
  if (expanded === "~" || expanded.startsWith("~/")) {
    expanded = `${GLib.get_home_dir()}${expanded.slice(1)}`
  }
  expanded = expanded.replace(/\$\{(\w+)\}|\$(\w+)/g, (match, braced, bare) => {
    const name = braced ?? bare
    const resolved = GLib.getenv(name)
    return resolved ?? match
  })
  return expanded
}

/** Validate settings before persisting; returns an error string or null. */
function validateSettings(settings: CaptureSettings): string | null {
  if (settings.screenshot_dir.trim() === "") return "Screenshot folder cannot be empty."
  if (settings.recording_dir.trim() === "") return "Recording folder cannot be empty."
  const pattern = settings.filename_pattern.trim()
  if (pattern === "") return "Filename pattern cannot be empty."
  if (pattern.includes("/") || pattern.includes("\0")) {
    return "Filename pattern cannot contain a path separator."
  }
  return null
}

/**
 * Persist settings (validated), creating the config dir and both output
 * directories with parents. Returns an error string, or null on success.
 */
function saveSettings(settings: CaptureSettings): string | null {
  const error = validateSettings(settings)
  if (error !== null) return error
  try {
    GLib.mkdir_with_parents(CONFIG_DIR, 0o755)
    for (const dir of [settings.screenshot_dir, settings.recording_dir]) {
      const expanded = expandDir(dir).trim()
      if (expanded !== "") GLib.mkdir_with_parents(expanded, 0o755)
    }
    GLib.file_set_contents(CONFIG_PATH, `${JSON.stringify(settings, null, 2)}\n`)
    return null
  } catch (cause) {
    console.error(`capture-tool: cannot write settings config: ${cause}`)
    return `Could not save settings: ${cause}`
  }
}

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
// ---------------------------------------------------------------------------

const UI_STATE_DIR = `${
  GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`
}/capture-tool`
const UI_STATE_PATH = `${UI_STATE_DIR}/capture-ui.json`

interface ScreenshotUiState {
  target: CaptureTarget
  delay: number
  format: ScreenshotFormat
  save: boolean
}

interface RecordingUiState {
  target: CaptureTarget
  fps: number
  format: RecordingFormat
  audio: AudioSource
  quality: RecordingQuality
  duration: number
  gifFps: number
  size: GifScale
  customDuration: number
}

// First-run defaults per spec: Region/PNG/Clipboard and
// Region/60fps/MP4/System/High/∞ (GIF extras: 15fps, Original, 120s custom).
const DEFAULT_SCREENSHOT: ScreenshotUiState = {
  target: "region",
  delay: 0,
  format: "png",
  save: false,
}

const DEFAULT_RECORDING: RecordingUiState = {
  target: "region",
  fps: 60,
  format: "mp4",
  audio: "system",
  quality: "high",
  duration: 0,
  gifFps: 15,
  size: "original",
  customDuration: 120,
}

function oneOf<T>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback
}

const TARGETS = ["region", "screen", "window"] as const
const SCREENSHOT_DELAYS = [0, 3, 5, 10] as const
const SCREENSHOT_FORMATS = ["png", "jpeg"] as const
const RECORDING_FPS = [24, 30, 60] as const
const GIF_FPS = [10, 15, 20, 30] as const
const RECORDING_FORMATS = ["mp4", "webm", "gif"] as const
const AUDIO_SOURCES = ["system", "microphone", "none"] as const
const QUALITIES = ["low", "medium", "high"] as const
const DURATIONS = [0, 10, 30, 60] as const
const GIF_SIZES = ["original", "75%", "50%"] as const

/** Config `mic` ↔ UI `microphone` (the two vocabularies in play). */
function audioToUi(audio: ConfigRecordingAudio): AudioSource {
  return audio === "mic" ? "microphone" : audio
}

/**
 * Initial-selection defaults sourced from the settings config (precedence:
 * last-used UI state > settings defaults > hardcoded constants).
 */
function configDefaults(config: CaptureSettings): {
  screenshot: ScreenshotUiState
  recording: RecordingUiState
} {
  return {
    screenshot: {
      ...DEFAULT_SCREENSHOT,
      format: config.screenshot.format as ScreenshotFormat,
      save: config.screenshot.output === "save",
    },
    recording: {
      ...DEFAULT_RECORDING,
      fps: config.recording.fps,
      quality: config.recording.quality as RecordingQuality,
      audio: audioToUi(config.recording.audio),
    },
  }
}

function loadUiState(base: {
  screenshot: ScreenshotUiState
  recording: RecordingUiState
}): { screenshot: ScreenshotUiState; recording: RecordingUiState } {
  const fallback = {
    screenshot: { ...base.screenshot },
    recording: { ...base.recording },
  }
  try {
    // First run has no state file yet — fall back silently, not loudly.
    if (!GLib.file_test(UI_STATE_PATH, GLib.FileTest.EXISTS)) return fallback
    const [ok, bytes] = GLib.file_get_contents(UI_STATE_PATH)
    if (!ok || bytes === null) return fallback
    const parsed = JSON.parse(new TextDecoder().decode(bytes)) as {
      screenshot?: Partial<ScreenshotUiState>
      recording?: Partial<RecordingUiState>
    }
    const screenshot = { ...base.screenshot, ...parsed.screenshot }
    const recording = { ...base.recording, ...parsed.recording }
    return {
      screenshot: {
        target: oneOf(screenshot.target, TARGETS, base.screenshot.target),
        delay: oneOf(screenshot.delay, SCREENSHOT_DELAYS, base.screenshot.delay),
        format: oneOf(screenshot.format, SCREENSHOT_FORMATS, base.screenshot.format),
        save: typeof screenshot.save === "boolean" ? screenshot.save : base.screenshot.save,
      },
      recording: {
        target: oneOf(recording.target, TARGETS, base.recording.target),
        fps: oneOf(recording.fps, RECORDING_FPS, base.recording.fps),
        format: oneOf(recording.format, RECORDING_FORMATS, base.recording.format),
        audio: oneOf(recording.audio, AUDIO_SOURCES, base.recording.audio),
        quality: oneOf(recording.quality, QUALITIES, base.recording.quality),
        duration:
          typeof recording.duration === "number" && recording.duration >= 0
            ? recording.duration
            : base.recording.duration,
        gifFps: oneOf(recording.gifFps, GIF_FPS, base.recording.gifFps),
        size: oneOf(recording.size, GIF_SIZES, base.recording.size),
        customDuration:
          typeof recording.customDuration === "number" && recording.customDuration >= 5
            ? Math.min(3600, Math.round(recording.customDuration))
            : base.recording.customDuration,
      },
    }
  } catch (error) {
    console.error(`capture-tool: cannot read UI state: ${error}`)
    return fallback
  }
}

function saveUiState(screenshot: ScreenshotUiState, recording: RecordingUiState): void {
  try {
    GLib.mkdir_with_parents(UI_STATE_DIR, 0o755)
    GLib.file_set_contents(UI_STATE_PATH, JSON.stringify({ screenshot, recording }))
  } catch (error) {
    console.error(`capture-tool: cannot write UI state: ${error}`)
  }
}

// CLI contract (design.md §4): --audio {none,system,mic}, --duration <seconds>
// (0 = infinite). GIF additionally takes --size {original,75,50} (backend
// contract — NOT percents; the backend argparse rejects anything else).
const GIF_SIZE_ARG: Record<GifScale, string> = {
  original: "original",
  "75%": "75",
  "50%": "50",
}

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

export function CaptureWindow(gdkmonitor: Gdk.Monitor) {
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
  let settingsConfig: CaptureSettings = loadSettings()
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

  function isGif(): boolean {
    return recording.format === "gif"
  }

  function applyGifMode() {
    const gif = isGif()
    if (audioRow) audioRow.visible = !gif
    if (stdFpsRow) stdFpsRow.visible = !gif
    if (gifFpsRow) gifFpsRow.visible = gif
    if (sizeRow) sizeRow.visible = gif
    if (recFooterStd) recFooterStd.visible = !gif
    if (recFooterGif) recFooterGif.visible = gif
    // Swapping audio for size changes the height, so the surface must follow.
    syncWindowSize()
  }

  function durationSelection(): number {
    return DURATIONS.includes(recording.duration as (typeof DURATIONS)[number])
      ? recording.duration
      : -1
  }

  function refreshCustomBox() {
    if (customBox) customBox.visible = durationSelection() === -1
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
    saveUiState(screenshot, recording)
    const config = loadSettings()
    const args = [
      "capture-tool",
      "screenshot",
      "--target",
      screenshot.target,
      "--delay",
      String(screenshot.delay),
      "--format",
      screenshot.format,
    ]
    // The backend owns the default save path (config dir + pattern); the
    // clipboard default is preserved unless Save was chosen.
    if (screenshot.save) args.push("--save")
    if (config.screenshot.cursor) args.push("--cursor")
    hideCaptureWindow()
    setTimeout(() => execAsync(args).catch(console.error), 150)
  }

  function startRecording() {
    saveUiState(screenshot, recording)
    const config = loadSettings()
    const audioFlag = recording.audio === "microphone" ? "mic" : recording.audio
    const args = [
      "capture-tool",
      "start",
      "--target",
      recording.target,
      "--fps",
      String(isGif() ? recording.gifFps : recording.fps),
      "--format",
      recording.format,
      "--quality",
      recording.quality,
      "--audio",
      audioFlag,
      "--duration",
      String(recording.duration),
    ]
    if (isGif()) args.push("--size", GIF_SIZE_ARG[recording.size])
    if (config.recording.cursor) args.push("--cursor")
    hideCaptureWindow()
    setTimeout(() => execAsync(args).catch(console.error), 150)
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
      const state = loadUiState(configDefaults(loadSettings()))
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
      applyGroup(recordingDurationGroup, durationSelection())
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
    const track = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL })
    track.add_css_class("toggle")
    const knob = new Gtk.Box()
    knob.add_css_class("toggle-knob")
    track.append(knob)
    const apply = (on: boolean) => {
      if (on) {
        track.add_css_class("on")
        knob.set_halign(Gtk.Align.END)
      } else {
        track.remove_css_class("on")
        knob.set_halign(Gtk.Align.START)
      }
    }
    apply(getValue())
    const button = new Gtk.Button()
    button.add_css_class("toggle-button")
    button.set_child(track)
    button.connect("clicked", () => {
      const next = !getValue()
      setValue(next)
      apply(next)
    })
    return settingsItem(name, desc, button)
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
    execAsync(["capture-tool", "backend"])
      .then((out) => {
        let name = "none"
        try {
          name = (JSON.parse(out) as { backend?: string }).backend ?? "none"
        } catch {
          name = "none"
        }
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
    settingsConfig = loadSettings()
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
    const error = saveSettings(settingsConfig)
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
      gdkmonitor={gdkmonitor}
      anchor={0}
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
      {/* The panel HUGS its content (halign/valign CENTER) instead of filling the
          window. It is the window's child, so a filling panel is stretched to
          the surface size — and while the surface is briefly still at the old
          (taller) size after a view switch, that stretch painted the panel
          background below the content as a rectangle trailing the window.
          Centred, the leftover area paints nothing (the window is transparent). */}
      <box
        class="capture-panel"
        orientation={Gtk.Orientation.VERTICAL}
        spacing={0}
        halign={Gtk.Align.CENTER}
        valign={Gtk.Align.CENTER}
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
    </window>
  )
}
