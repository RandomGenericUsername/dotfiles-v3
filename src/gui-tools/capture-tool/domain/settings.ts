// ---------------------------------------------------------------------------
// Settings config (add-capture-settings): the app-owned
// `$XDG_CONFIG_HOME/capture-tool/config.json` contract (design.md §1/§3).
//
// The GUI owns writes; the backend reads on every invocation. Reads are always
// safe: missing is first-run (silent defaults), corrupt degrades to defaults
// with a loud log.
//
// PURE LAYER (design.md §2/§3.1, task 3.1): no `ags/*`, no `gi://*`, no I/O.
// The persistence half (`loadSettings`/`saveSettings`) is deliberately NOT here
// — it owns the GLib file reads/writes and the recursive directory creation, and
// moves to `adapters/glib-settings-store.ts` at A5. What stays is the
// vocabulary and the merge, which is where every tolerance rule lives.
// ---------------------------------------------------------------------------

export type ConfigScreenshotFormat = "png" | "jpeg"
export type ConfigScreenshotOutput = "clipboard" | "save"
export type ConfigRecordingFps = 24 | 30 | 60
export type ConfigRecordingQuality = "low" | "medium" | "high"
export type ConfigRecordingAudio = "none" | "system" | "mic"

export interface CaptureSettings {
  screenshot_dir: string
  recording_dir: string
  filename_pattern: string
  notifications: boolean
  /** Bar feedback mode: true = bar shows the dot + timer only and the popup
   *  carries pause/resume/stop; false = the bar carries the buttons itself. */
  bar_compact_controls: boolean
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

export const DEFAULT_SETTINGS: CaptureSettings = {
  screenshot_dir: "~/Pictures/Screenshots",
  recording_dir: "~/Videos/Recordings",
  filename_pattern: "{kind}_%Y-%m-%d_%H-%M-%S",
  notifications: true,
  bar_compact_controls: false,
  screenshot: { format: "png", output: "clipboard", cursor: false },
  recording: { fps: 60, quality: "high", audio: "system", cursor: true },
}

export const CONFIG_SCREENSHOT_FORMATS: readonly ConfigScreenshotFormat[] = ["png", "jpeg"]
export const CONFIG_SCREENSHOT_OUTPUTS: readonly ConfigScreenshotOutput[] = ["clipboard", "save"]
export const CONFIG_RECORDING_FPS: readonly ConfigRecordingFps[] = [24, 30, 60]
export const CONFIG_RECORDING_QUALITIES: readonly ConfigRecordingQuality[] = [
  "low",
  "medium",
  "high",
]
export const CONFIG_RECORDING_AUDIO: readonly ConfigRecordingAudio[] = ["none", "system", "mic"]

export function configOneOf<T>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback
}

export function configBool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback
}

export function configString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() !== "" ? value : fallback
}

/** A fresh deep copy of the defaults (GJS has no structuredClone). */
export function defaultSettings(): CaptureSettings {
  return {
    ...DEFAULT_SETTINGS,
    screenshot: { ...DEFAULT_SETTINGS.screenshot },
    recording: { ...DEFAULT_SETTINGS.recording },
  }
}

export function mergeSettings(raw: unknown): CaptureSettings {
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
    bar_compact_controls: configBool(
      record.bar_compact_controls,
      DEFAULT_SETTINGS.bar_compact_controls,
    ),
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

/** Validate settings before persisting; returns an error string or null. */
export function validateSettings(settings: CaptureSettings): string | null {
  if (settings.screenshot_dir.trim() === "") return "Screenshot folder cannot be empty."
  if (settings.recording_dir.trim() === "") return "Recording folder cannot be empty."
  const pattern = settings.filename_pattern.trim()
  if (pattern === "") return "Filename pattern cannot be empty."
  if (pattern.includes("/") || pattern.includes("\0")) {
    return "Filename pattern cannot contain a path separator."
  }
  return null
}

// ---------------------------------------------------------------------------
// Environment seam for `expandDir` (design.md §7.2, task 3.3).
//
// `expandDir` is pure string manipulation over two environment lookups, so the
// lookups are injected instead of imported: `domain/` must not reach `gi://`
// (gate check 1). `getenv` mirrors `GLib.getenv` (null when unset) and `home`
// mirrors `GLib.get_home_dir`; both are FUNCTIONS so the values are resolved at
// call time exactly as the pre-move `GLib.getenv`/`GLib.get_home_dir` calls
// inside `expandDir` were.
//
// Wiring (A5, landed): `adapters/glib-settings-store.ts` — the only layer
// allowed to touch GLib's environment — constructs this object as
// `{ getenv: (name) => GLib.getenv(name), home: () => GLib.get_home_dir() }`
// and passes it in. `ui/CaptureWindow.tsx` no longer supplies it.
// ---------------------------------------------------------------------------

export interface Environment {
  /** `GLib.getenv` semantics: the variable's value, or null when unset. */
  getenv(name: string): string | null
  /** `GLib.get_home_dir` semantics. */
  home(): string
}

/** Expand `~` and `$VAR`/`${VAR}` references in a configured directory. */
export function expandDir(value: string, env: Environment): string {
  let expanded = value
  if (expanded === "~" || expanded.startsWith("~/")) {
    expanded = `${env.home()}${expanded.slice(1)}`
  }
  expanded = expanded.replace(/\$\{(\w+)\}|\$(\w+)/g, (match, braced, bare) => {
    const name = braced ?? bare
    const resolved = env.getenv(name)
    return resolved ?? match
  })
  return expanded
}